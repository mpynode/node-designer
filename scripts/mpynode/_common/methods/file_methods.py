"""Interpreted adapters for mPyFile's blessed methods. Bound onto `self`
by the SelfProxy blessed-method tier. Each receives the SelfProxy as `self`,
reads the node's own preset params, and delegates to the canonical texture
helpers (_load_linear_pixels / _sample) -- so parity with the C++ kernels is
inherited.

The helper is resolved off the node's OWN Init tab when it ships one, and
otherwise off the importable framework twin ``file_texture_ops``. See
_helper() for why."""
from __future__ import annotations

import hashlib
import os
import tempfile
import threading

import numpy as np


def _helper(self, init_name, ops_name):
    """Resolve a texture helper: the node's Init-tab copy first, the framework
    module second.

    A node that pastes the full default Init (``_defaults/file_defaults.py``)
    owns its own math and can edit it, so that copy must keep winning. Every
    OTHER mPyFile -- a template, or anything built from a trimmed Init -- used
    to get an AttributeError out of get_init_helper and could not call the
    blessed methods at all. The fallback makes load + colour management +
    pre-filter framework behaviour that is always available.

    Behaviour is identical either way: the two copies are held in lock-step by
    ``tests/nodes/test_file_texture_ops_drift`` (and both by the C++ nd_tex_*
    kernels), and the signatures match argument-for-argument."""
    try:
        return self.get_init_helper(init_name)
    except AttributeError:
        from mpynode._common.methods import file_texture_ops as ops
        return getattr(ops, ops_name)


# ---- embedded-image staging (the `fileName` miss fallback) ----
# md5(bytes) -> the temp path those bytes were staged to, so a repeated buffer
# is written once. The DECODE is not cached here: load_linear_pixels() already
# caches per (path, colorSpace, pre-filter), and staging is stable per md5, so
# the embedded image hits that cache exactly like a file on disk.
# Lock-guarded: Hypershade's swatch generator pulls compute() on a worker
# thread, so two threads can reach a cold buffer at once and would otherwise
# race writing the same temp file.
_EMBED_PATHS = {}
_EMBED_LOCK = threading.Lock()

# Serializes write_texture(). Same reason as _EMBED_LOCK: the swatch generator
# and the VP2 render thread both pull compute() off the main thread, and a
# stateful node bakes ONE fixed path every frame.
_WRITE_LOCK = threading.Lock()


def _ext_for_bytes(data):
    """Sniff an image extension from magic bytes so the temp file we hand to
    the loader has a suffix its readers key off. Defaults to .png.

    Twin of ``native/compiler/kernels/file_texture_cpp._ext_for_bytes``, which
    bakes the same sniff into generated C++. Kept a separate copy on purpose:
    the compiler must not acquire this module's numpy import."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:2] == b"BM":
        return ".bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tif"
    return ".png"


def _embedded_path(self):
    """This node's ``embeddedImage`` bytes staged to a temp file -> its path.

    Staging is what lets the SAME loader read them: the embedded image then
    gets exactly the colour management, pre-filtering and caching an on-disk
    file gets, instead of a second decode path that could drift from it.
    None when the node carries no bytes, or when staging fails."""
    data = getattr(self, "embeddedImage", None)
    if not data:
        return None
    key = hashlib.md5(data).hexdigest()
    with _EMBED_LOCK:
        if key in _EMBED_PATHS:
            return _EMBED_PATHS[key]
        path = None
        try:
            tmp = os.path.join(tempfile.gettempdir(),
                               "mpy_embed_%s%s" % (key, _ext_for_bytes(data)))
            if not os.path.isfile(tmp):
                with open(tmp, "wb") as fh:
                    fh.write(data)
            path = tmp
        except Exception:
            path = None
        _EMBED_PATHS[key] = path
        return path


def read_texture(self, path=None):
    """self.read_texture([path]) -> float32 HxWx4 linear buffer (or None).

    ``path`` defaults to this node's own ``fileName``. Pass one to run the
    SAME load + colour management + pre-filter over an arbitrary file -- what
    a multi-image node (compositing, a sequence, an atlas) needs. The preset
    inputs (colorSpace / preFilter / preFilterKernel / preFilterRadius) always
    come off the node either way, so every image a node reads is managed
    identically.

    EMBEDDED FALLBACK: when the node's OWN ``fileName`` does not load and the
    node carries baked ``embeddedImage`` bytes, those bytes are staged and read
    instead, so a node ships renderable with no file on disk. The compiled twin
    does the same thing (file_texture_cpp._emit_load emits the identical
    nullptr -> nd_img_embedded_path() retry), so both tiers agree.

    The fallback is deliberately suppressed when an explicit ``path`` is
    passed: that spelling means "read THIS file", and a compositor relies on a
    blank layer path returning None to drop the layer. Falling back there would
    paint the embedded image into every empty slot."""
    llp = _helper(self, "_load_linear_pixels", "load_linear_pixels")
    args = (int(self.colorSpace), bool(self.preFilter),
            int(self.preFilterKernel), float(self.preFilterRadius))
    buf = llp(self.fileName if path is None else path, *args)
    if buf is None and path is None:
        emb = _embedded_path(self)
        if emb:
            buf = llp(emb, *args)
    return buf


def sample_texture(self, buf, u, v, missing=None):
    """self.sample_texture(buf, u, v) -> (r, g, b, a) wrap-aware bilinear.

    ``missing`` selects what an unreadable buffer yields. None (the default)
    keeps the opaque magenta "no image" sentinel, so every existing node is
    unchanged; a literal RGBA 4-tuple substitutes that instead -- (0, 0, 0, 0)
    lets a compositor drop an unresolvable layer rather than have it cover the
    stack."""
    smp = _helper(self, "_sample", "sample")
    border = np.asarray(self.borderColor, dtype=np.float32)
    args = (buf, float(u), float(v),
            int(self.wrapModeU), int(self.wrapModeV),
            (float(border[0]), float(border[1]), float(border[2])))
    # Only widen the call when the caller actually asked for a substitute. A
    # node that pasted the full default Init owns its own `_sample`, and one
    # saved before `missing` existed still takes six arguments -- passing a
    # seventh unconditionally would TypeError every one of them.
    if missing is None:
        return smp(*args)
    return smp(*(args + (missing,)))


def composite_layers(self, layers, opacities, u, v, missing=(0.0, 0.0, 0.0, 0.0)):
    """self.composite_layers(layers, opacities, u, v) -> (r, g, b, a).

    Alpha-over the stack at ONE point, bottom (``layers[0]``) to top. This is
    the SSOT for the composite: the compiled tier lowers it to the
    ``nd_tex_composite_layers`` kernel, which is a statement-for-statement twin
    of the loop below, so the two tiers cannot drift apart the way two
    hand-written copies did.

    Opacity is a WEIGHT, not an on/off switch -- it scales the layer's alpha.
    0 removes a layer exactly; a NEGATIVE value subtracts, which is a real
    (if unusual) result rather than a skip. Anything that special-cased
    ``op > 0`` would disagree with this for negative and NaN weights, which is
    exactly the divergence this method exists to remove: whatever renders is
    what previews.

    A layer with no matching ``opacities`` element defaults to 1.0 -- a path you
    bothered to set is on unless you say otherwise.
    """
    n_ops = len(opacities)
    cr = cg = cb = ca = 0.0
    for i in range(len(layers)):
        buf = read_texture(self, layers[i])
        r, g, b, a_src = sample_texture(self, buf, u, v, missing=missing)
        op = float(opacities[i]) if i < n_ops else 1.0
        a = float(a_src) * op
        ia = 1.0 - a
        cr = float(r) * a + cr * ia
        cg = float(g) * a + cg * ia
        cb = float(b) * a + cb * ia
        ca = a + ca * ia
    return (cr, cg, cb, ca)


def _stamped_bake_path(path, frame):
    """``/tmp/x.png`` + frame 7 -> ``/tmp/x.0007.png``.

    The SSOT for the frame-stamp rule. Two other tiers reimplement it and MUST
    agree byte-for-byte: the ``nd_tex_write`` C++ kernel (the compiled node bakes
    the same files) and the OSL shader (Arnold reconstructs the name at shade
    time from the base path + its bakeFrame param). Mirrors os.path.splitext, so
    an extension-less path just gets the stamp appended.
    """
    stem, ext = os.path.splitext(path)
    return "%s.%04d%s" % (stem, int(frame), ext)


def write_texture(self, path, rgba, frame=None):
    """self.write_texture(path, rgba, frame=None) -> True on success, else False.

    Write an (H, W, 4) float RGBA buffer to ``path`` as an 8-bit PNG. This is
    the twin of read_texture(): a STATEFUL node (a simulation whose board cannot
    be evaluated from (u, v, t) alone) bakes its current frame to a file that an
    OSL/Arnold tier then samples.

    Rows are written flipped because MImage stores bottom-up, so a standard file
    -node / OSL texture() read lands buffer row 0 at the TOP -- matching the
    (1 - v) sampling convention the Compute tier uses.

    ``frame`` writes a frame-stamped SIBLING (``x.png`` -> ``x.0007.png``)
    instead of overwriting ``path``. Pass it whenever an OSL/Arnold tier samples
    the bake: Arnold's texture system caches by FILENAME and never re-stats, so
    re-baking a new board to one fixed path is invisible to it -- the render
    keeps showing whichever frame was read first. Measured on Arnold 7.4.3.2: the
    same path reports its ORIGINAL resolution after being overwritten at a new
    size, while distinct paths read fresh. Omit it (the default) to keep the
    single-file behaviour -- an existing caller is unaffected.

    NEVER raises: an unwritable path or a bad buffer returns False. That keeps
    the call a single lowerable expression -- a try/except around it in a compute
    would not transpile, so the guard lives here instead.

    Serialized and published atomically. Hypershade's swatch generator and the
    VP2 render thread both pull compute() off the main thread, so several
    threads can reach this for the SAME path -- and a stateful node bakes one
    fixed filename over and over, which is also the file the OSL/Arnold tier
    samples. ``MImage::writeToFile`` is not atomic, so a reader can otherwise
    catch a half-written PNG. Write a sibling temp then ``os.replace`` it, which
    is atomic within a filesystem; the lock keeps two bakers from fighting over
    the same temp name. Same reasoning as ``_EMBED_LOCK`` above."""
    tmp = None
    try:
        import maya.api.OpenMaya as om

        # The same two guards the nd_tex_write kernel applies, so the tiers agree
        # on what "cannot bake" means. MImage itself accepts both of these.
        if not path:
            return False
        if frame is not None:
            path = _stamped_bake_path(path, frame)
        arr = np.asarray(rgba, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[2] != 4:
            return False
        h, w = int(arr.shape[0]), int(arr.shape[1])
        buf = (np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
        buf = np.ascontiguousarray(buf[::-1])     # top-down -> MImage bottom-up
        img = om.MImage()
        img.create(w, h, 4, om.MImage.kByte)
        img.setPixels(buf.tobytes(), w, h)
        # Keep the temp beside the target: os.replace is only atomic within one
        # filesystem, and a temp dir can be on another volume.
        tmp = "%s.%d.tmp.png" % (path, os.getpid())
        with _WRITE_LOCK:
            img.writeToFile(tmp, "png")
            os.replace(tmp, path)
        return True
    except Exception:
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass
        return False
