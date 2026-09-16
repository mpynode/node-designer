"""osl_verify -- render-compare verifier for the mPyFile OSL pipeline
(increment 3).

Increments 1 and 2 answer "did the translation produce OSL?" -- the
deterministic transpiler's grammar (:mod:`osl_convert`) and, for the AI arm, a
structural gate plus a *compile* gate
(:func:`osl_targets.validate_osl_via_arnold`). Neither looks at a single pixel:
OSL that compiles can still render the wrong look. This module closes that gap
by RENDERING the shader and comparing the image.

Two tiers, mirroring increment 2's injected-callable shape so the core stays
Maya-free, Qt-free and unit-testable with fakes:

* The PURE core -- :func:`read_pfm`, :func:`diff_images`,
  :func:`image_is_constant`, :func:`compare_renders`,
  :func:`compare_render_to_reference`. The renderer is INJECTED as
  ``render_fn(osl_src, width, height) -> (image_or_None, error)``, the same
  ``(value, error)`` contract ``validate_fn`` already uses.
* The Arnold backend -- :func:`find_arnold_tools`,
  :func:`render_osl_via_arnold`, :func:`make_arnold_render_fn`. Pure
  subprocess (``oslc`` -> ``kick`` -> ``oiiotool``), so unlike
  :mod:`osl_targets` (in-Maya ``aiOslShader`` + ``OSLSceneModel``) it needs no
  Maya session and no main thread.

HONESTY CONTRACT -- the whole point of a verifier is that it cannot be mistaken
for one that ran:

* ``passed`` is only ever True when ``ran`` is True, and
  ``bool(result)`` is ``ran and passed`` -- a missing renderer, a dead
  ``render_fn`` or an uncompilable shader reports ``ran=False`` and is falsey.
* A comparison of two FEATURELESS images (both constant) is reported as
  ``vacuous`` and does NOT pass. That is the trap where a texture-sampling
  shader renders black because its ``filename`` parameter was never set: two
  black frames "match" while proving nothing.

RENDER CONTRACT. The backend renders the shader over a unit UV square through
an orthographic camera, so the returned image IS the shader sampled on a UV
grid: ``pixel_at(img, col, row)`` is the shader at
``u = (col + 0.5) / width``, ``v = (row + 0.5) / height`` (row 0 = v LOW).
Verified exact against ``color(u, v, .25)``.

LIMITATION (v1): shaders render with their DEFAULT parameter values -- nothing
here binds ``filename`` or the ``self.*``-derived params. Comparing two OSL arms
of the same node is therefore apples-to-apples, but a shader whose look lives
entirely behind an unset parameter renders featureless and is caught by the
vacuous guard rather than silently passing.
"""

from __future__ import annotations

import glob
import os
import struct
import subprocess
import sys
import tempfile
from collections import namedtuple

from .osl_targets import _osl_error_message

#: Pass criterion: the largest absolute per-channel difference allowed. Bit
#: parity is not the bar (OSL texture filtering and colour management make it
#: impossible even for a hand-written twin) -- this is the "renderer-approximate
#: pixels" tolerance the feature was designed around.
DEFAULT_TOLERANCE = 1e-3

#: Default comparison resolution. Small enough to render in milliseconds and to
#: stay under :data:`WATERMARK_SAFE_MAX`, large enough to resolve real look
#: differences.
DEFAULT_SIZE = 128

#: Largest frame an UNLICENSED Arnold renders without stamping watermarks over
#: it. Re-measured 2026-08-14 (darwin arm64, no license) on BOTH the 7.4.3.2 in
#: mtoa/2026 and the 7.5.0.0 in mtoa/2027 that :func:`find_arnold_tools`
#: actually resolves (it reverse-sorts, so the newest install wins). The edge is
#: the same on both: clean through 162px, contaminated from 163px up. Only the
#: TRANSITION is reproducible, not its size: a constant-blue probe's B channel
#: has an exactly 0.0 stddev at <=162 and a nonzero one from 163 up, but the
#: value varies run to run (three trials at 163 gave 0.00071 / 0.00061 /
#: 0.00058, and at 164 gave 0.0042 / 0.0039 / 0.0038) because an unlicensed
#: Arnold stamps a randomised pattern. Quote the edge, never the magnitude.
#: Watermark pixels would silently poison every metric in this module, so
#: :func:`render_osl_via_arnold` REFUSES a larger frame when kick reports it is
#: watermarking. 160 keeps two pixels of margin under the measured edge; a
#: licensed Arnold is not capped.
WATERMARK_SAFE_MAX = 160

_KICK_WATERMARK_MARKER = "rendering with watermarks"

#: An image whose float pixels are stored row-major, ROW 0 == v LOW (bottom),
#: channel-interleaved: ``pixels[(row * width + col) * channels + c]``.
OslImage = namedtuple("OslImage", "width height channels pixels")

#: Outcome of :func:`diff_images`. ``over_tolerance`` counts individual
#: CHANNEL SAMPLES past the tolerance (not pixels); ``over_fraction`` is that
#: count over the total sample count.
ImageDiff = namedtuple(
    "ImageDiff",
    "width height channels mean_abs max_abs rms over_tolerance over_fraction",
)

#: Absolute paths to the three Arnold standalone binaries the backend drives.
ArnoldTools = namedtuple("ArnoldTools", "kick oslc oiiotool")


class RenderCompareResult(object):
    """Verdict of a render comparison.

    ``ran``     -- a real pixel comparison was performed.
    ``passed``  -- ... and the images agree within tolerance. NEVER True when
                   ``ran`` is False.
    ``reason``  -- human/AI-readable explanation. On a renderer failure this
                   carries the oslc/kick diagnostic, so it can feed the same
                   self-repair prompt the compile gate feeds.
    ``diff``    -- the :class:`ImageDiff`, or ``None`` when nothing was
                   compared.
    """

    __slots__ = ("ran", "passed", "reason", "diff")

    def __init__(self, ran, passed, reason, diff=None):
        self.ran    = bool(ran)
        self.passed = bool(passed) and self.ran
        self.reason = reason or ""
        self.diff   = diff

    def __bool__(self):
        return self.passed

    __nonzero__ = __bool__  # py2-style truthiness, harmless here

    def __repr__(self):
        return ("RenderCompareResult(ran=%r, passed=%r, reason=%r)"
                % (self.ran, self.passed, self.reason))


# ---- Image IO ------------------------------------------------------------
def pixel_at(image, col, row):
    """Return the channel tuple at ``(col, row)``; row 0 is v LOW."""
    base = (row * image.width + col) * image.channels
    return tuple(image.pixels[base:base + image.channels])


def read_pfm(path):
    """Read a PFM (portable float map) into an :class:`OslImage`.

    PFM is the readback format because it is plain float32 with a 3-line ASCII
    header -- no image library needed -- and ``oiiotool`` (shipped next to
    ``kick``) writes it. PFM stores the BOTTOM row first, which is exactly the
    row-0-is-v-low convention this module promises, so no flip is applied.
    """
    with open(path, "rb") as handle:
        data = handle.read()

    fields = []
    pos    = 0
    while len(fields) < 3:
        nl = data.find(b"\n", pos)
        if nl < 0:
            raise ValueError("%s: truncated PFM header" % path)
        fields.append(data[pos:nl].decode("ascii", "replace").strip())
        pos = nl + 1

    magic = fields[0]
    if magic not in ("PF", "Pf"):
        raise ValueError("%s: not a PFM file (magic %r)" % (path, magic))
    channels = 3 if magic == "PF" else 1
    try:
        width, height = [int(tok) for tok in fields[1].split()]
        scale = float(fields[2])
    except ValueError:
        raise ValueError("%s: malformed PFM header %r" % (path, fields[1:]))

    count = width * height * channels
    need  = count * 4
    if len(data) - pos < need:
        raise ValueError(
            "%s: truncated PFM data (%d bytes, need %d)"
            % (path, len(data) - pos, need))
    order  = "<" if scale < 0 else ">"
    pixels = list(struct.unpack(order + "%df" % count, data[pos:pos + need]))
    return OslImage(width, height, channels, pixels)


# ---- The metric ----------------------------------------------------------
def diff_images(image_a, image_b, tolerance=DEFAULT_TOLERANCE):
    """Per-channel absolute difference statistics. Raises ``ValueError`` when
    the two images are not the same shape (there is no meaningful comparison to
    report, and quietly resampling would invent one)."""
    if (image_a.width, image_a.height, image_a.channels) != (
            image_b.width, image_b.height, image_b.channels):
        raise ValueError(
            "image shape mismatch: %dx%dx%d vs %dx%dx%d"
            % (image_a.width, image_a.height, image_a.channels,
               image_b.width, image_b.height, image_b.channels))

    total    = 0.0
    total_sq = 0.0
    max_abs  = 0.0
    over     = 0
    count    = 0
    for val_a, val_b in zip(image_a.pixels, image_b.pixels):
        delta = abs(val_a - val_b)
        total    += delta
        total_sq += delta * delta
        if delta > max_abs:
            max_abs = delta
        if delta > tolerance:
            over += 1
        count += 1
    if not count:
        raise ValueError("cannot compare empty images")
    return ImageDiff(
        width          = image_a.width,
        height         = image_a.height,
        channels       = image_a.channels,
        mean_abs       = total / count,
        max_abs        = max_abs,
        rms            = (total_sq / count) ** 0.5,
        over_tolerance = over,
        over_fraction  = float(over) / count,
    )


def image_is_constant(image, tolerance=DEFAULT_TOLERANCE):
    """True when every channel varies by no more than ``tolerance`` across the
    whole frame -- i.e. the image carries no structure a comparison at that
    tolerance could resolve."""
    channels = image.channels
    if not image.pixels:
        return True
    lows  = list(image.pixels[:channels])
    highs = list(lows)
    for index, value in enumerate(image.pixels):
        chan = index % channels
        if value < lows[chan]:
            lows[chan] = value
        elif value > highs[chan]:
            highs[chan] = value
    return all(hi - lo <= tolerance for lo, hi in zip(lows, highs))


# ---- The compare harness -------------------------------------------------
def _render(render_fn, osl_src, width, height):
    """Drive an injected ``render_fn``, normalising every failure mode to
    ``(None, reason)``. A render_fn that RAISES is a failure, not a pass."""
    try:
        image, error = render_fn(osl_src, width, height)
    except Exception as exc:
        return None, "the renderer raised: %s" % exc
    if image is None:
        return None, error or "the renderer produced no image"
    return image, ""


def _verdict(image_a, image_b, tolerance):
    """Compare two rendered images into a :class:`RenderCompareResult`."""
    try:
        diff = diff_images(image_a, image_b, tolerance=tolerance)
    except ValueError as exc:
        # Nothing was compared, so no verdict was reached -- ran=False.
        return RenderCompareResult(False, False, str(exc))

    if (image_is_constant(image_a, tolerance)
            and image_is_constant(image_b, tolerance)):
        return RenderCompareResult(
            True, False,
            "vacuous comparison: both renders are featureless, so they would "
            "match whatever the look-math does (max abs difference %.6g)"
            % diff.max_abs,
            diff)

    if diff.max_abs <= tolerance:
        return RenderCompareResult(
            True, True,
            "match: max abs difference %.6g <= tolerance %.6g"
            % (diff.max_abs, tolerance),
            diff)
    return RenderCompareResult(
        True, False,
        "mismatch: max abs difference %.6g > tolerance %.6g "
        "(mean %.6g, rms %.6g, %.2f%% of samples over tolerance)"
        % (diff.max_abs, tolerance, diff.mean_abs, diff.rms,
           100.0 * diff.over_fraction),
        diff)


def compare_renders(osl_a, osl_b, render_fn, width=DEFAULT_SIZE,
                    height=DEFAULT_SIZE, tolerance=DEFAULT_TOLERANCE):
    """Render two OSL sources and compare the images.

    This is the "deterministic arm vs AI arm" check: both sides are OSL, so no
    Maya and no reference image are needed -- when
    :func:`osl_convert.convert_compute_to_osl` CAN handle a Compute, its output
    is ground truth for whatever the AI arm produced for the same node.
    """
    image_a, error = _render(render_fn, osl_a, width, height)
    if image_a is None:
        return RenderCompareResult(False, False,
                                   "first shader did not render: %s" % error)
    image_b, error = _render(render_fn, osl_b, width, height)
    if image_b is None:
        return RenderCompareResult(False, False,
                                   "second shader did not render: %s" % error)
    return _verdict(image_a, image_b, tolerance)


def compare_render_to_reference(osl_src, reference, render_fn,
                                tolerance=DEFAULT_TOLERANCE):
    """Render one OSL source and compare it to a reference :class:`OslImage`
    (e.g. the node's own Compute sampled on the same UV grid). The render is
    requested at the reference's resolution."""
    image, error = _render(render_fn, osl_src, reference.width,
                           reference.height)
    if image is None:
        return RenderCompareResult(False, False,
                                   "shader did not render: %s" % error)
    return _verdict(image, reference, tolerance)


# ---- Arnold standalone backend -------------------------------------------
_ASS_TEMPLATE = """\
options
{
 AA_samples 1
 xres %(xres)d
 yres %(yres)d
 camera "mpyOslCam"
 outputs "RGBA RGBA mpyOslFilter mpyOslDriver"
 GI_diffuse_depth 0
 GI_specular_depth 0
 texture_automip off
 abort_on_license_fail off
}

box_filter
{
 name mpyOslFilter
}

driver_exr
{
 name mpyOslDriver
 filename "%(exr)s"
 color_space "linear"
}

ortho_camera
{
 name mpyOslCam
 screen_window_min -1 -1
 screen_window_max 1 1
 near_clip 0.001
 far_clip 10
 matrix
 1 0 0 0
 0 1 0 0
 0 0 1 0
 0 0 1 1
}

polymesh
{
 name mpyOslQuad
 nsides 1 1 UINT 4
 vidxs 4 1 UINT 0 1 2 3
 vlist 4 1 POINT
 -1 -1 0
  1 -1 0
  1  1 0
 -1  1 0
 uvidxs 4 1 UINT 0 1 2 3
 uvlist 4 1 POINT2
 0 0
 1 0
 1 1
 0 1
 shader "mpyOslShader"
}

osl
{
 name mpyOslShader
 shadername "%(oso)s"
}
"""


def _exe(name):
    return name + ".exe" if sys.platform.startswith("win") else name


def _default_search_dirs():
    """Where Arnold standalone is looked for, most specific first."""
    dirs     = []
    override = os.environ.get("MPYNODE_ARNOLD_BIN")
    if override:
        dirs.append(override)
    root = os.environ.get("ARNOLD_ROOT")
    if root:
        dirs.append(os.path.join(root, "bin"))
    patterns = [
        "/Applications/Autodesk/Arnold/mtoa/*/bin",
        "/opt/autodesk/arnold/maya*/bin",
        "/usr/autodesk/arnold/maya*/bin",
        "C:/Program Files/Autodesk/Arnold/maya*/bin",
    ]
    for pattern in patterns:
        # Newest install first (mtoa/2027 before mtoa/2024).
        dirs.extend(sorted(glob.glob(pattern), reverse=True))
    path_env = os.environ.get("PATH", "")
    dirs.extend(p for p in path_env.split(os.pathsep) if p)
    return dirs


def find_arnold_tools(search_dirs=None, use_defaults=True):
    """Locate ``kick`` + ``oslc`` + ``oiiotool`` in one directory.

    Returns an :class:`ArnoldTools`, or ``None`` when no directory holds all
    three -- callers must treat ``None`` as "cannot verify", never as "verified".
    ``search_dirs`` is tried before the defaults; ``use_defaults=False`` limits
    the search to it (used by the tests to prove absence is detected).
    """
    candidates = list(search_dirs or [])
    if use_defaults:
        candidates.extend(_default_search_dirs())
    for directory in candidates:
        if not directory or not os.path.isdir(directory):
            continue
        found = {}
        for tool in ("kick", "oslc", "oiiotool"):
            path = os.path.join(directory, _exe(tool))
            if os.path.isfile(path) and os.access(path, os.X_OK):
                found[tool] = path
        if len(found) == 3:
            return ArnoldTools(kick=found["kick"], oslc=found["oslc"],
                               oiiotool=found["oiiotool"])
    return None


def _run(argv, timeout):
    """Run a tool, returning ``(returncode, combined_output)``. A missing
    binary or a timeout is reported like a non-zero exit, never raised."""
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, "%s timed out after %ss" % (os.path.basename(argv[0]),
                                               timeout)
    except Exception as exc:
        return -1, "could not run %s: %s" % (argv[0], exc)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def render_osl_via_arnold(osl_src, width=DEFAULT_SIZE, height=DEFAULT_SIZE,
                          tools=None, timeout=300):
    """Render ``osl_src`` over a unit UV square with Arnold standalone.

    Returns ``(OslImage, "")`` or ``(None, reason)``. ``reason`` carries the
    real ``oslc`` / ``kick`` diagnostic (shaped by the same
    :func:`osl_targets._osl_error_message` the in-Maya compile gate feeds to AI
    self-repair), so a failed verification is an actionable repair signal
    rather than a bare "no".
    """
    if not osl_src or not osl_src.strip():
        return None, "empty OSL source"
    if tools is None:
        tools = find_arnold_tools()
    if tools is None:
        return None, ("Arnold standalone (oslc/kick/oiiotool) was not found -- "
                      "cannot render, so nothing was verified")

    with tempfile.TemporaryDirectory(prefix="mpy_osl_verify_") as workdir:
        def _p(name):
            return os.path.join(workdir, name).replace("\\", "/")

        osl_path, oso_path = _p("shader.osl"), _p("shader.oso")
        ass_path, exr_path = _p("scene.ass"), _p("out.exr")
        pfm_path = _p("out.pfm")

        with open(osl_path, "w") as handle:
            handle.write(osl_src)

        code, log = _run([tools.oslc, "-o", oso_path, osl_path], timeout)
        if code != 0 or not os.path.isfile(oso_path):
            return None, _osl_error_message("oslc exited with %s" % code, log)

        with open(ass_path, "w") as handle:
            handle.write(_ASS_TEMPLATE % {
                "xres": int(width), "yres": int(height),
                "exr": exr_path, "oso": oso_path[:-len(".oso")],
            })

        code, log = _run([tools.kick, "-i", ass_path, "-dw", "-dp",
                          "-nostdin", "-v", "1"], timeout)
        if code != 0 or not os.path.isfile(exr_path):
            return None, _osl_error_message("kick exited with %s" % code, log)

        # An unlicensed Arnold stamps watermarks over anything much bigger than
        # WATERMARK_SAFE_MAX. Those pixels are indistinguishable from a genuine
        # look difference, so refuse rather than measure them.
        if _KICK_WATERMARK_MARKER in log and (width > WATERMARK_SAFE_MAX
                                              or height > WATERMARK_SAFE_MAX):
            return None, (
                "Arnold is rendering with watermarks (no license) and %dx%d is "
                "larger than the %dpx watermark-free ceiling -- the image would "
                "be corrupted, so it was not measured"
                % (width, height, WATERMARK_SAFE_MAX))

        code, log = _run([tools.oiiotool, exr_path, "-o", pfm_path], timeout)
        if code != 0 or not os.path.isfile(pfm_path):
            return None, _osl_error_message("oiiotool exited with %s" % code,
                                            log)
        try:
            return read_pfm(pfm_path), ""
        except (ValueError, OSError) as exc:
            return None, "could not read the rendered image: %s" % exc


def make_arnold_render_fn(tools=None, timeout=300):
    """Bind :func:`render_osl_via_arnold` into the ``render_fn(osl, w, h)``
    callable :func:`compare_renders` expects. Resolves the tools up front so a
    comparison does not re-scan the filesystem per render (when Arnold is
    absent the lookup stays unresolved and every render reports that)."""
    if tools is None:
        tools = find_arnold_tools()

    def render_fn(osl_src, width, height):
        return render_osl_via_arnold(osl_src, width, height, tools=tools,
                                     timeout=timeout)
    return render_fn
