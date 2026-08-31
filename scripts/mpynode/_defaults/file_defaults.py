"""Default source strings shipped with a brand-new mPyFile.create().

The three constants below are Python source code that is exec'd inside
the node's Init / Compute / Viewport tabs. Together they replicate the
behavior of MayaCustomFileNode's customFileTexture node.

The user can replace any of them via the Node Designer. Every line of
the color-space + kernel + sampling viewport is visible and editable
in the Init tab; the Compute and Viewport tabs are short glue.

DESIGN: kept as raw multi-line Python source rather than imported
helpers so users can read and edit every line in the Node Designer.
This mirrors MayaCustomFileNode/plug-ins/customFileTexture.py lines
~90-940 nearly verbatim (with the per-plug compute() / updateShader()
bodies moved into the Compute / Viewport tabs).
"""

from __future__ import annotations


DEFAULT_INIT_SOURCE = r'''# ----------------------------------------------------------------------
# mPyFile -- default Init source (runs once per file open)
#
# Defines the color-space catalogue, gamut matrices, transfer functions,
# pre-filter kernels, and bilinear-sampling helpers. Available to the
# Compute and Viewport tabs as bare names.
#
# Modify any of this code to change how the node loads / linearizes /
# samples images. Saved with the.ma; survives across reloads.
# ----------------------------------------------------------------------

import os
import struct
import sys
import zlib

import numpy as np

# omr is hoisted here so the merged init namespace exposes it to both
# Compute and Viewport tabs (avoids per-call ``import maya.api.OpenMayaRender``
# in every user expression).
import maya.api.OpenMayaRender as omr

# PIL is OPTIONAL: it does NOT ship with mayapy (neither 2024 nor 2026) -- it
# is only importable when the host happens to have Pillow on sys.path. When it
# is absent, _decode_rgba8 below falls through to Qt and then to the pure-Python
# _png_decode, all three of which produce identical bytes to the compiled
# kernel's nd_png_decode -- so the node reads the same pixels on every host.
try:
    from PIL import Image as _PILImage
except ImportError:
    _PILImage = None

try:
    from scipy.ndimage import convolve1d as _scipy_convolve1d
    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False


# ---- enum constants (kept in sync with the node's preset plug enums) ----
# NOTE: These are inlined here on purpose. This block is exec'd node source
# (editable in the Init tab and preserved by one-way .py bake/export), so it
# must stay self-contained -- it cannot `import` from the mpynode package.
# The canonical definition lives in the declarative SSOT
# (mpynode._common.interface.file_texture_interface); a drift-guard test
# (test_native_file_texture_interface) asserts these values equal the SSOT.
kFilterPoint = 0
kFilterLinear = 1
kFilterAnisotropic = 2

kMipmapNone = 0
kMipmapAuto = 1

kWrapWrap = 0
kWrapClamp = 1
kWrapMirror = 2
kWrapBorder = 3

kPreFilterBox = 0
kPreFilterQuadratic = 1
kPreFilterQuartic = 2
kPreFilterGaussian = 3


# ---- per-node linearized-pixel cache ----------------------------------
# Module-level dict in the per-node init namespace, so each mPyFile
# instance gets its OWN cache (init runs once per node per file open).
# Survives across both compute() and updateShader() calls, gets wiped on
# file close. Matches the cache pattern customFileTexture uses on its
# MPxNode + MPxShadingNodeOverride instances.
#
# Without this, Hypershade's swatch generator (which calls compute()
# once per swatch pixel -- 4096 calls per 64x64 swatch) re-reads the
# PNG from disk every call and freezes Maya for minutes.
_LINEAR_CACHE = {}
# Lock for thread-safe access. Hypershade swatch + VP2 may pull
# compute()/updateShader on worker / render threads concurrently;
# without serialization on the cache dict, two threads racing on a
# cache miss can both spend O(seconds) doing PIL load + linearize
# and clobber each other on insert. A simple lock keeps it safe.
import threading as _threading
_LINEAR_CACHE_LOCK = _threading.Lock()


# ---- gamut matrices (source primaries -> Rec.709 / sRGB linear, D65) ----
_M_AdobeRGB_to_Rec709 = np.array(
    [[1.39838, -0.39838, 0.00000],
     [0.00000,  1.00000, 0.00000],
     [0.00000, -0.04293, 1.04293]], dtype=np.float32)
_M_P3D65_to_Rec709 = np.array(
    [[1.22494, -0.22494, 0.00000],
     [-0.04205, 1.04205, 0.00000],
     [-0.01964, -0.07857, 1.09821]], dtype=np.float32)
_M_Rec2020_to_Rec709 = np.array(
    [[1.66049, -0.58764, -0.07286],
     [-0.12455, 1.13284, -0.00829],
     [-0.01815, -0.10058, 1.11873]], dtype=np.float32)
_M_AP0_to_Rec709 = np.array(
    [[2.52169, -1.13413, -0.38756],
     [-0.27648, 1.37272, -0.09624],
     [-0.01538, -0.15298, 1.16835]], dtype=np.float32)
_M_AP1_to_Rec709 = np.array(
    [[1.70505, -0.62179, -0.08326],
     [-0.13026, 1.14080, -0.01055],
     [-0.02400, -0.12897, 1.15297]], dtype=np.float32)
_M_AlexaWide_to_Rec709 = np.array(
    [[1.617523, -0.537366, -0.080156],
     [-0.070573, 1.334613, -0.264040],
     [-0.021102, -0.226858, 1.247961]], dtype=np.float32)
_M_REDWide_to_Rec709 = np.array(
    [[1.412341, -0.241346, -0.171015],
     [-0.011936, 1.045283, -0.033347],
     [-0.022867, -0.030676, 1.053542]], dtype=np.float32)
_M_SGamut3_to_Rec709 = np.array(
    [[1.628691, -0.764773, 0.136082],
     [-0.085391, 1.236164, -0.150774],
     [0.028601, -0.275313, 1.246712]], dtype=np.float32)


# ---- transfer functions (vectorized, no per-pixel loops) ----
def _srgb_eotf(rgb):
    """sRGB encoded -> linear (full piecewise)."""
    low = rgb / 12.92
    high = np.power((rgb + 0.055) / 1.055, 2.4)
    return np.where(rgb <= 0.04045, low, high).astype(np.float32)


def _gamma_eotf(rgb, gamma):
    """Pure-gamma EOTF. Clamps negatives to 0 for numeric stability."""
    return np.power(np.maximum(rgb, 0.0), gamma).astype(np.float32)


def _apply_matrix(rgb, M):
    """Apply 3x3 M to every pixel of HxWx3 in ONE einsum call."""
    return np.einsum("ij,hwj->hwi", M, rgb).astype(np.float32)


def _acescct_eotf(rgb):
    """ACEScct encoded -> linear (AP1 primaries)."""
    low = (rgb - np.float32(0.0729055341958355)) / np.float32(10.5402377416545)
    high = np.power(np.float32(2.0), rgb * np.float32(17.52) - np.float32(9.72))
    return np.where(rgb <= np.float32(0.155251141552511), low, high).astype(np.float32)


def _logc_v3_ei800_eotf(rgb):
    """ARRI LogC v3 EI=800 encoded -> linear (AlexaWideGamut)."""
    cut = np.float32(0.149658)
    low = (rgb - np.float32(0.092809)) / np.float32(5.367655)
    high = (
        np.power(np.float32(10.0), (rgb - np.float32(0.385537)) / np.float32(0.247190))
        - np.float32(0.052272)
    ) / np.float32(5.555556)
    return np.where(rgb > cut, high, low).astype(np.float32)


def _red_log3g10_eotf(rgb):
    """RED Log3G10 encoded -> linear (REDWideGamutRGB)."""
    return (
        (np.power(np.float32(10.0), rgb / np.float32(0.224282)) - np.float32(1.0))
        / np.float32(155.975327) - np.float32(0.01)
    ).astype(np.float32)


def _slog3_eotf(rgb):
    """Sony S-Log3 encoded -> linear (S-Gamut3)."""
    th = np.float32(171.2102946929 / 1023.0)
    high = np.power(
        np.float32(10.0),
        (rgb * np.float32(1023.0) - np.float32(420.0)) / np.float32(261.5),
    ) * np.float32(0.19) - np.float32(0.01)
    low = (
        (rgb * np.float32(1023.0) - np.float32(95.0))
        * np.float32(0.01125000)
        / np.float32(171.2102946929 - 95.0)
    )
    return np.where(rgb >= th, high, low).astype(np.float32)


def _adx10_eotf(rgb):
    """ACES ADX10 (10-bit printing density) -> linear (AP0). Preview."""
    density = (rgb * np.float32(1023.0) - np.float32(95.0)) * (
        np.float32(2.0) / np.float32(928.0)
    )
    return (
        np.float32(0.18) * np.power(np.float32(10.0), np.float32(1.6056) - density)
    ).astype(np.float32)


# ---- pre-filter kernel builders ----
def _gaussian_kernel(radius):
    """1D Gaussian kernel. Maya convention: sigma = radius / 2."""
    sigma = max(float(radius) / 2.0, 0.5)
    half = int(np.ceil(3.0 * sigma))
    x = np.arange(-half, half + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    return (k / k.sum()).astype(np.float32)


def _box_kernel(radius):
    """1D uniform (box) kernel."""
    half = max(1, int(round(float(radius))))
    n = 2 * half + 1
    return np.full(n, 1.0 / float(n), dtype=np.float32)


def _quadratic_kernel(radius):
    """1D triangular (tent / quadratic B-spline) kernel."""
    half = max(1, int(round(float(radius))))
    x = np.arange(-half, half + 1, dtype=np.float32)
    k = np.maximum(
        np.float32(0.0), np.float32(1.0) - np.abs(x) / np.float32(half + 1)
    )
    return (k / k.sum()).astype(np.float32)


def _quartic_kernel(radius):
    """1D iterated-binomial kernel. Self-convolves [1,2,1]/4 (2*r) times."""
    base = np.array([1.0, 2.0, 1.0], dtype=np.float32) / np.float32(4.0)
    n_iter = max(1, int(round(float(radius))) * 2)
    k = base.copy()
    for _ in range(n_iter - 1):
        k = np.convolve(k, base, mode="full")
    return (k / k.sum()).astype(np.float32)


def _blur_separable(image, k1d):
    """Apply a 1D kernel along axis 0 then axis 1. Reflect edges."""
    if _HAVE_SCIPY:
        out = _scipy_convolve1d(image, k1d, axis=0, mode="reflect")
        out = _scipy_convolve1d(out, k1d, axis=1, mode="reflect")
        return out.astype(np.float32)
    half = (len(k1d) - 1) // 2
    padded = np.pad(image, ((half, half), (half, half), (0, 0)), mode="reflect")
    conv0 = np.apply_along_axis(
        lambda col: np.convolve(col, k1d, mode="valid"), axis=0, arr=padded
    )
    conv1 = np.apply_along_axis(
        lambda row: np.convolve(row, k1d, mode="valid"), axis=1, arr=conv0
    )
    return conv1.astype(np.float32)


def _prefilter(linear_pixels, enabled, kernel, radius):
    """Apply CPU pre-filter blur to linearized float32 HxWx4 pixels."""
    if not enabled or linear_pixels is None or radius <= 0.0:
        return linear_pixels
    if kernel == kPreFilterGaussian:
        k1d = _gaussian_kernel(radius)
    elif kernel == kPreFilterBox:
        k1d = _box_kernel(radius)
    elif kernel == kPreFilterQuadratic:
        k1d = _quadratic_kernel(radius)
    elif kernel == kPreFilterQuartic:
        k1d = _quartic_kernel(radius)
    else:
        return linear_pixels
    return _blur_separable(linear_pixels, k1d)


# ---- linearize a uint8 RGBA image from a color space index ----
def _linearize(pixels_uint8, cs_index, unpremultiply=False):
    """Convert uint8 HxWx4 pixels from color space ``cs_index`` to
    float32 HxWx4 in scene-linear Rec.709 / sRGB primaries.

    Alpha is passed through unchanged. Indices match the colorSpace
    enum on the mPyFile node (25 entries, 0..24).

    ``unpremultiply`` undoes an ASSOCIATED-alpha decode -- see the same flag on
    the C++ twin ``nd_tex_linearize``. It has to happen before the transfer
    function, because the EOTF is non-linear: ``eotf(c*a) != eotf(c)*a``."""
    f = pixels_uint8.astype(np.float32) * (np.float32(1.0) / np.float32(255.0))
    rgb = f[...,:3]
    alpha = f[..., 3:4]

    if unpremultiply:
        # a == 0 carries no recoverable colour and contributes nothing; a == 1
        # is already straight. Written as a reciprocal MULTIPLY, not a divide,
        # so it rounds the same way the C++ twin's `r *= ia` does.
        partial = (alpha > np.float32(0.0)) & (alpha < np.float32(1.0))
        safe = np.where(partial, alpha, np.float32(1.0))
        rgb = np.minimum(rgb * (np.float32(1.0) / safe), np.float32(1.0))

    # Transfer function.
    if cs_index in (19, 8, 9, 10, 11, 12, 13):
        lin = rgb
    elif cs_index in (0, 4, 6, 14):
        lin = _srgb_eotf(rgb)
    elif cs_index == 1:
        lin = _gamma_eotf(rgb, 1.8)
    elif cs_index in (2, 5, 7, 15, 17):
        lin = _gamma_eotf(rgb, 2.2)
    elif cs_index in (3, 16):
        lin = _gamma_eotf(rgb, 2.4)
    elif cs_index == 18:
        lin = _gamma_eotf(rgb, 2.6)
    elif cs_index == 20:
        lin = _acescct_eotf(rgb)
    elif cs_index == 21:
        lin = _logc_v3_ei800_eotf(rgb)
    elif cs_index == 22:
        lin = _red_log3g10_eotf(rgb)
    elif cs_index == 23:
        lin = _slog3_eotf(rgb)
    elif cs_index == 24:
        lin = _adx10_eotf(rgb)
    else:
        lin = rgb

    # Gamut matrix (single einsum if needed).
    if cs_index in (7, 12, 17):
        lin = _apply_matrix(lin, _M_AdobeRGB_to_Rec709)
    elif cs_index in (6, 11, 18):
        lin = _apply_matrix(lin, _M_P3D65_to_Rec709)
    elif cs_index == 13:
        lin = _apply_matrix(lin, _M_Rec2020_to_Rec709)
    elif cs_index in (10, 24):
        lin = _apply_matrix(lin, _M_AP0_to_Rec709)
    elif cs_index in (9, 4, 5, 20):
        lin = _apply_matrix(lin, _M_AP1_to_Rec709)
    elif cs_index == 21:
        lin = _apply_matrix(lin, _M_AlexaWide_to_Rec709)
    elif cs_index == 22:
        lin = _apply_matrix(lin, _M_REDWide_to_Rec709)
    elif cs_index == 23:
        lin = _apply_matrix(lin, _M_SGamut3_to_Rec709)
    return np.concatenate([lin, alpha], axis=-1).astype(np.float32)


# ---- image-sequence path resolver (Compute tab) ----
def _resolve_seq_path(pattern, frame):
    """Substitute an image-sequence frame number into a ``#``-padded path.

    ``'render.####.png'`` at frame 42 -> ``'render.0042.png'``. The LAST run of
    ``#`` is the padding token (Maya's file-sequence convention); its length is
    the zero-pad width (``str(int(frame)).zfill(width)``, sign-aware). A pattern
    with no ``#`` is returned unchanged (a static single-image path).

    Use it in the Compute tab to drive a sequence off a time / frame input::

        linear = _load_linear_pixels(
            _resolve_seq_path(self.fileName, int(self.tIn)),
            int(self.colorSpace), ...)

    The per-node ``_LINEAR_CACHE`` is keyed by the RESOLVED path, so a new frame
    loads the new file automatically. The native compiler emits a byte-identical
    C++ ``nd_tex_resolve_seq`` for this exact idiom, so a compiled sequence node
    renders the same frame -- and reloads every frame -- as the Python node.
    """
    import re as _re
    pattern = str(pattern)
    runs = list(_re.finditer(r"#+", pattern))
    if not runs:
        return pattern
    m = runs[-1]
    width = m.end() - m.start()
    return pattern[:m.start()] + str(int(frame)).zfill(width) + pattern[m.end():]


# ---- exact PNG decode (straight alpha), twin of the C++ nd_png_* kernel ----
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_CHAN = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _png_supported(data):
    """Does the exact decoder handle these bytes? Twin of ``nd_png_supported``.

    Load-bearing for parity, not an optimization: BOTH tiers ask it of the same
    header bytes and take the exact path or the MImage path together. If they
    could answer differently, one tier would decode straight alpha while the
    other decoded associated alpha.
    """
    if len(data) < 33 or data[:8] != _PNG_SIG or data[12:16] != b"IHDR":
        return False
    depth, colour, comp, filt, interlace = struct.unpack("BBBBB", data[24:29])
    # Adam7 re-orders the image into seven sub-passes and the reference encoder
    # will not emit it, so there is no way to prove the tiers agree -> decline.
    if comp != 0 or filt != 0 or interlace != 0:
        return False
    if colour in (0, 3):
        # 16-bit greyscale is declined even though the spec allows it: PIL opens
        # it as a 32-bit integer image and CLIPS to 0..255 rather than scaling,
        # so there is no single narrowing rule for the C++ twin to match.
        if depth not in (1, 2, 4, 8):
            return False
    elif colour in (2, 4, 6):
        if depth not in (8, 16):
            return False
    else:
        return False
    if colour in (0, 2):
        # tRNS on greyscale / truecolour marks ONE colour transparent; the
        # reference behaviour is not pinned, so decline rather than guess.
        off = 8
        while off + 8 <= len(data):
            ln = struct.unpack(">I", data[off:off + 4])[0]
            typ = data[off + 4:off + 8]
            if typ == b"tRNS":
                return False
            if typ == b"IDAT":
                break
            off += 12 + ln
    return True


def _png_unfilter(raw, h, stride, fbpp):
    """Reverse the per-scanline filters. None/Sub/Up are whole-array operations
    -- Sub is a mod-256 cumulative sum down each byte lane -- so only Average
    and Paeth need the byte-at-a-time recurrence."""
    out = np.zeros((h, stride), np.uint8)
    prev = np.zeros((stride,), np.uint8)
    for y in range(h):
        base = y * (stride + 1)
        ft = raw[base]
        src = np.frombuffer(raw, np.uint8, stride, base + 1)
        if ft == 0:
            cur = src.copy()
        elif ft == 1:
            cur = np.empty((stride,), np.uint8)
            for lane in range(fbpp):
                cur[lane::fbpp] = np.cumsum(
                    src[lane::fbpp], dtype=np.uint64).astype(np.uint8)
        elif ft == 2:
            cur = (src.astype(np.uint16) + prev).astype(np.uint8)
        elif ft in (3, 4):
            s = src.tolist()
            p = prev.tolist()
            c = [0] * stride
            if ft == 3:
                for i in range(stride):
                    a = c[i - fbpp] if i >= fbpp else 0
                    c[i] = (s[i] + ((a + p[i]) >> 1)) & 0xFF
            else:
                for i in range(stride):
                    a = c[i - fbpp] if i >= fbpp else 0
                    b = p[i]
                    cc = p[i - fbpp] if i >= fbpp else 0
                    pp = a + b - cc
                    pa = pp - a if pp > a else a - pp
                    pb = pp - b if pp > b else b - pp
                    pc = pp - cc if pp > cc else cc - pp
                    if pa <= pb and pa <= pc:
                        pr = a
                    elif pb <= pc:
                        pr = b
                    else:
                        pr = cc
                    c[i] = (s[i] + pr) & 0xFF
            cur = np.array(c, np.uint8)
        else:
            return None
        out[y] = cur
        prev = cur
    return out


def _png_samples(rows, w, chan, depth):
    """Expand packed scanlines to (h, w*chan) uint8, narrowing the way the C++
    twin narrows: 16-bit keeps the HIGH byte, sub-byte fields come out unscaled
    (greyscale is scaled by the caller; palette indices must stay raw)."""
    if depth == 8:
        return rows[:, :w * chan]
    if depth == 16:
        return rows[:, 0:w * chan * 2:2]
    per = 8 // depth
    mask = (1 << depth) - 1
    out = np.empty((rows.shape[0], w * chan), np.uint8)
    for i in range(w * chan):
        shift = (per - 1 - (i % per)) * depth
        out[:, i] = (rows[:, i // per] >> shift) & mask
    return out


def _png_decode(data):
    """Decode PNG bytes to top-down (h, w, 4) uint8 RGBA with STRAIGHT alpha, or
    None for anything ``_png_supported`` declines or any malformed stream."""
    if not _png_supported(data):
        return None
    w, h = struct.unpack(">II", data[16:24])
    depth, colour = data[24], data[25]
    if w == 0 or h == 0:
        return None
    chan = _PNG_CHAN[colour]
    # Scanlines are bit-packed so the byte stride rounds UP; the filter offset is
    # "bytes per complete pixel, at least 1", which stops being the channel
    # count as soon as the depth stops being 8.
    stride = (w * chan * depth + 7) // 8
    fbpp = max(1, (chan * depth) // 8)

    idat = bytearray()
    plte = trns = b""
    off, n = 8, len(data)
    while off + 8 <= n:
        ln = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8]
        if off + 12 + ln > n:
            return None
        body = data[off + 8:off + 8 + ln]
        if typ == b"IDAT":
            idat += body                      # IDAT may be split across chunks
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IEND":
            break
        off += 12 + ln
    if not idat or (colour == 3 and len(plte) < 3):
        return None

    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    if len(raw) < (stride + 1) * h:
        return None

    rows = _png_unfilter(raw, h, stride, fbpp)
    if rows is None:
        return None
    s = _png_samples(rows, w, chan, depth)

    out = np.full((h, w, 4), 255, np.uint8)
    if colour in (0, 4):
        # Sub-byte greyscale stretches to full range by an exact integer factor.
        gs = (255 // ((1 << depth) - 1)) if depth < 8 else 1
        out[:, :, 0] = out[:, :, 1] = out[:, :, 2] = (s[:, 0::chan] * gs)
        if colour == 4:
            out[:, :, 3] = s[:, 1::chan]
    elif colour == 3:
        idx = s.reshape(h, w)
        pal = np.frombuffer(plte, np.uint8)
        npal = len(pal) // 3
        if int(idx.max()) >= npal:
            return None
        out[:, :, :3] = pal[:npal * 3].reshape(npal, 3)[idx]
        if trns:
            a = np.frombuffer(trns, np.uint8)
            full = np.full((npal,), 255, np.uint8)
            full[:min(len(a), npal)] = a[:npal]
            out[:, :, 3] = full[idx]
    else:
        out[:, :, 0] = s[:, 0::chan]
        out[:, :, 1] = s[:, 1::chan]
        out[:, :, 2] = s[:, 2::chan]
        if colour == 6:
            out[:, :, 3] = s[:, 3::chan]
    return out


def _qimage_rgba8(path, depth):
    """Decode via Qt, or None. Qt is present on every Maya host, and for bit
    depths 1/2/4/8 its PNG output is byte-identical to PIL's -- so it is a fast
    exact decoder for a PIL-less host.

    NOT used at depth 16: Qt ROUNDS 16-bit samples (round(v/257)) where PIL and
    the C++ twin TRUNCATE to the high byte.
    """
    if depth == 16:
        return None
    QImage = None
    for mod in ("PySide6.QtGui", "PySide2.QtGui"):
        try:
            QImage = __import__(mod, fromlist=["QImage"]).QImage
            break
        except ImportError:
            continue
    if QImage is None:
        return None
    fmt = (QImage.Format.Format_RGBA8888 if hasattr(QImage, "Format")
           else QImage.Format_RGBA8888)
    im = QImage(path)
    if im.isNull():
        return None
    im = im.convertToFormat(fmt)
    w, h, bpl = im.width(), im.height(), im.bytesPerLine()
    if w <= 0 or h <= 0:
        return None
    # Qt pads scanlines; honour bytesPerLine rather than assuming w*4.
    buf = bytes(im.constBits())[:h * bpl]
    if len(buf) < h * bpl:
        return None
    return np.frombuffer(buf, np.uint8).reshape(h, bpl)[:, :w * 4].reshape(h, w, 4)


# ---- image decode: exact where possible, MImage only as a last resort ----
def _decode_rgba8(path):
    """Decode ``path`` to ``(top-down uint8 HxWx4 RGBA, premultiplied)``.

    The second element is the ALPHA ASSOCIATION of the returned pixels, and it
    is the whole point of this function: the decoders disagree about it. A PNG
    stores colour and alpha separately and that is what the compositing math
    assumes, but MImage hands back colour already multiplied by alpha AND
    quantised to 8 bits, which is lossy on every antialiased edge. Reporting
    which decoder ran lets ``_linearize`` undo the association at the right point.

    The order below is chosen so that whatever runs here produces the SAME bytes
    the compiled tier's ``nd_png_decode`` produces:

      1. ``_png_supported`` -- the identical predicate the C++ twin uses.
      2. PIL, then Qt, then the pure-Python ``_png_decode``. Qt ships with every
         Maya; PIL does not (Maya 2024 has none), and the pure-Python path is
         the guarantee that a host with neither still matches.
      3. Anything declined -- interlaced, 16-bit greyscale, a non-PNG format --
         falls through to MImage, which is ALSO what the compiled tier falls
         back to, so the two stay in step.
    """
    try:
        # The WHOLE file, not just the header: for greyscale / truecolour the
        # predicate has to scan the chunk list for tRNS, and a short read would
        # let it answer "supported" where the C++ twin -- which always sees the
        # whole file -- answers "declined". The two must never disagree.
        with open(path, "rb") as fh:
            data = fh.read()
        if _png_supported(data):
            if _PILImage is not None:
                return (np.asarray(_PILImage.open(path).convert("RGBA"),
                                   dtype=np.uint8), False)
            qt = _qimage_rgba8(path, data[24])
            if qt is not None:
                return (qt, False)
            px = _png_decode(data)
            if px is not None:
                return (px, False)
    except (OSError, ValueError):
        pass  # unreadable / malformed -> let MImage have its turn

    import ctypes
    import maya.api.OpenMaya as om
    img = om.MImage()
    img.readFromFile(path)
    img.verticalFlip()  # MImage is bottom-up; PIL / numpy are top-down
    w, h = img.getSize()
    return (np.frombuffer(
        ctypes.string_at(img.pixels(), w * h * 4), dtype=np.uint8
    ).reshape(h, w, 4), True)


# ---- top-level image-load helper used by Compute + Viewport ----
def _load_linear_pixels(path, cs_index, prefilter, kernel, radius):
    """Load ``path``, linearize from color space ``cs_index``, apply
    optional CPU pre-filter, return float32 HxWx4. Returns None on
    missing file or load failure.

    Cached by (path, cs_index, prefilter, kernel, radius_quantized)
    in the per-node ``_LINEAR_CACHE`` so Hypershade swatch generation
    and per-frame VP2 updateShader calls don't re-read the file.
    Edit the file on disk + toggle a setting to bust the cache (or
    delete the cache key from ``_LINEAR_CACHE`` directly from your
    Compute / Viewport source).
    """
    radius_q = round(float(radius), 1) if radius else 0.0
    cache_key = (
        path, int(cs_index), bool(prefilter), int(kernel), radius_q
    )
    # Fast path: cached.
    with _LINEAR_CACHE_LOCK:
        if cache_key in _LINEAR_CACHE:
            return _LINEAR_CACHE[cache_key]

    # Negative caching for missing / unloadable files (still thread-safe).
    if not path or not os.path.isfile(path):
        with _LINEAR_CACHE_LOCK:
            _LINEAR_CACHE[cache_key] = None
        return None

    # Heavy load + linearize + prefilter happens OUTSIDE the lock so
    # concurrent loads of different textures don't serialize. The lock
    # is only held around the cache check + the cache write.
    try:
        raw, premultiplied = _decode_rgba8(path)
        lin = _linearize(raw, int(cs_index), unpremultiply=premultiplied)
        result = _prefilter(lin, prefilter, int(kernel), radius_q)
    except Exception as exc:
        sys.stderr.write(
            "[mPyFile init] failed to load %s (cs=%d): %s\n"
            % (path, cs_index, exc)
        )
        with _LINEAR_CACHE_LOCK:
            _LINEAR_CACHE[cache_key] = None
        return None

    with _LINEAR_CACHE_LOCK:
        # Double-check after load -- another thread may have populated it
        # while we were loading. Use their result to avoid storing twice.
        if cache_key in _LINEAR_CACHE and _LINEAR_CACHE[cache_key] is not None:
            return _LINEAR_CACHE[cache_key]
        _LINEAR_CACHE[cache_key] = result
    return result


# ---- UV wrap policy + bilinear sampler (Compute tab) ----
def _apply_wrap(coord, mode):
    """Apply a wrap / clamp / mirror policy to a single UV coordinate.

    Returns (coord_in_[0,1), out_of_bounds_flag). out_of_bounds_flag
    is True only for Border mode when the coord is outside [0, 1].
    """
    if mode == kWrapClamp:
        if coord < 0.0:
            return 0.0, False
        if coord > 1.0:
            return 1.0 - 1e-6, False
        return coord, False
    if mode == kWrapMirror:
        c = coord
        n = int(c // 1.0)
        frac = c - n
        if n % 2!= 0:
            frac = 1.0 - frac
        if frac >= 1.0:
            frac = 1.0 - 1e-6
        if frac < 0.0:
            frac = 0.0
        return frac, False
    if mode == kWrapBorder:
        if coord < 0.0 or coord > 1.0:
            return 0.0, True
        return coord, False
    return coord % 1.0, False


def _sample(pixels, u, v, wrap_u, wrap_v, border_color, missing=None):
    """Bilinear-sample float32 ``pixels`` (HxWx4 linearized) at UV
    (u, v) honoring wrap mode. Returns (r, g, b, a) in [0, 1].
    Magenta if pixels is None, unless ``missing`` overrides it.

    ``missing`` is the no-image substitute: None keeps the opaque magenta
    sentinel, an RGBA tuple replaces it. Kept in lock step with
    file_texture_ops.sample() and the C++ nd_tex_sample."""
    if pixels is None:
        if missing is None:
            return (1.0, 0.0, 1.0, 1.0)
        return (float(missing[0]), float(missing[1]),
                float(missing[2]), float(missing[3]))

    uu, u_oob = _apply_wrap(u, wrap_u)
    vv_raw, v_oob = _apply_wrap(v, wrap_v)
    if u_oob or v_oob:
        br, bg, bb = border_color
        return (float(br), float(bg), float(bb), 1.0)

    h, w, _ = pixels.shape
    # Maya V is bottom-up; image V is top-down.
    vv = 1.0 - vv_raw
    fx = uu * (w - 1)
    fy = vv * (h - 1)
    x0 = int(fx)
    y0 = int(fy)
    x1 = min(x0 + 1, w - 1)
    y1 = min(y0 + 1, h - 1)
    tx = fx - x0
    ty = fy - y0
    p00 = pixels[y0, x0]
    p10 = pixels[y0, x1]
    p01 = pixels[y1, x0]
    p11 = pixels[y1, x1]
    top = p00 * (1.0 - tx) + p10 * tx
    bottom = p01 * (1.0 - tx) + p11 * tx
    rgba = top * (1.0 - ty) + bottom * ty
    return (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))


# ---- VP2 enum maps (Viewport tab uses these) ----
def _vp2_filter_for(mode):
    """Map our filterMode enum to MSamplerState filter constant."""
    return {
        kFilterPoint: omr.MSamplerState.kMinMagMipPoint,
        kFilterLinear: omr.MSamplerState.kMinMagMipLinear,
        kFilterAnisotropic: omr.MSamplerState.kAnisotropic,
    }.get(int(mode), omr.MSamplerState.kMinMagMipLinear)


def _vp2_wrap_for(mode):
    """Map our wrapMode enum to MSamplerState address constant."""
    return {
        kWrapWrap: omr.MSamplerState.kTexWrap,
        kWrapClamp: omr.MSamplerState.kTexClamp,
        kWrapMirror: omr.MSamplerState.kTexMirror,
        kWrapBorder: omr.MSamplerState.kTexBorder,
    }.get(int(mode), omr.MSamplerState.kTexWrap)


def _upload_linear_texture(linear_pixels, fileName, colorSpace, mipmapMode,
                           preFilter, preFilterKernel, preFilterRadius):
    """Upload a float32 HxWx4 array to the GPU via the texture manager's
    in-memory acquireTexture(name, MTextureDescription, pixelData,
    gen_mips) overload. Bypasses Maya's file-based color management so
    the GPU samples our already-linearized data directly.

    Cache key is encoded into the texture name so different
    color-space / pre-filter settings get distinct cache entries.
    """
    if linear_pixels is None:
        return None
    texture_mgr = omr.MRenderer.getTextureManager()
    if texture_mgr is None:
        return None

    h, w, c = linear_pixels.shape
    if c!= 4:
        return None

    desc = omr.MTextureDescription()
    desc.setToDefault2DTexture()
    desc.fWidth = w
    desc.fHeight = h
    desc.fDepth = 1
    desc.fBytesPerRow = w * 4 * 4  # 4 channels * 4 bytes (float32)
    desc.fBytesPerSlice = desc.fBytesPerRow * h
    desc.fMipmaps = 1
    desc.fArraySlices = 1
    desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
    desc.fTextureType = omr.MTextureDescription.kImage2D
    desc.fEnvMapType = omr.MTextureDescription.kEnvNone

    if not linear_pixels.flags["C_CONTIGUOUS"]:
        linear_pixels = np.ascontiguousarray(linear_pixels)
    pixel_bytes = linear_pixels.tobytes()
    gen_mipmaps = int(mipmapMode) == kMipmapAuto

    radius_q = (
        round(float(preFilterRadius), 1) if preFilterRadius else 0.0
    )
    tex_name = "mpyfile::%s|cs=%d|pf=%d:%d:%.1f" % (
        fileName,
        int(colorSpace),
        int(bool(preFilter)),
        int(preFilterKernel),
        radius_q,
    )
    return texture_mgr.acquireTexture(tex_name, desc, pixel_bytes, gen_mipmaps)
'''


DEFAULT_COMPUTE_SOURCE = r'''# ----------------------------------------------------------------------
# mPyFile -- default Compute source (runs per DG compute() call)
#
# Uses the node's two blessed methods -- self.read_texture() and
# self.sample_texture() -- which the mPyFile API surfaces (the "M" rows
# in the Variables tab). They wrap the load + linearize + wrap-aware
# bilinear-sample helpers the Init tab ships (_load_linear_pixels /
# _sample), reading every preset input off self, so this Compute reads
# like a plain texture lookup and compiles to the SAME C++ as the
# hand-written spelling (nd_tex_load_linear + nd_tex_sample).
# ----------------------------------------------------------------------

# Load the linearized pixel buffer once per call (float32 HxWx4 or None).
buf = self.read_texture()

# self.uvCoord is a CompoundPlugProxy whose iterator yields the (u, v) floats.
u, v = self.uvCoord

# Wrap-aware bilinear sample at the requested UV -> (r, g, b, a).
r, g, b, a = self.sample_texture(buf, u, v)

self.outColor = (r, g, b)
self.outAlpha = a
'''


DEFAULT_VIEWPORT_SOURCE = r'''# ----------------------------------------------------------------------
# mPyFile -- default Viewport source (runs per VP2 updateShader call)
#
# Pushes the linearized pixel buffer + GPU sampler state into the
# mayaFileTexture shade-fragment graph the override registers.
# Available bridge bindings (read via self.X):
#
#   self.shader            -- MShaderInstance to push parameters into
#   self.mappings          -- MAttributeParameterMappingList from Maya
#   self.texture_manager   -- MRenderer.getTextureManager()
#   self.state_manager     -- omr.MStateManager (class)
#   plus every preset plug (self.fileName, self.colorSpace,...)
# ----------------------------------------------------------------------

# ``omr`` and ``np`` are imported by the Init tab -- exec_with_profile_watch
# merges Init's namespace into ours before this code runs, so they're
# already in scope.

# 1. Locate the fragment's texture + sampler parameters.
map_param = None
samp_param = None
for pname in self.shader.parameterList():
    try:
        ptype = self.shader.parameterType(pname)
    except Exception:
        continue
    if map_param is None and ptype == omr.MShaderInstance.kTexture2:
        map_param = pname
    elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
        samp_param = pname
    if map_param and samp_param:
        break

# 2. Upload the linearized pixels (helper defined in Init).
linear = _load_linear_pixels(
    self.fileName,
    int(self.colorSpace),
    bool(self.preFilter),
    int(self.preFilterKernel),
    float(self.preFilterRadius),
)
if linear is not None and map_param:
    texture = _upload_linear_texture(
        linear,
        self.fileName,
        int(self.colorSpace),
        int(self.mipmapMode),
        bool(self.preFilter),
        int(self.preFilterKernel),
        float(self.preFilterRadius),
    )
    if texture is not None:
        assignment = omr.MTextureAssignment()
        assignment.texture = texture
        self.shader.setParameter(map_param, assignment)
        try:
            self.texture_manager.releaseTexture(texture)
        except Exception:
            pass

# 3. Build + apply the sampler state.
if samp_param:
    border = np.asarray(self.borderColor, dtype=np.float32)
    desc = omr.MSamplerStateDesc()
    desc.setDefaults()
    desc.filter = _vp2_filter_for(int(self.filterMode))
    desc.maxAnisotropy = int(self.maxAnisotropy)
    desc.mipLODBias = float(self.mipLODBias)
    desc.minLOD = int(self.minLOD)
    desc.maxLOD = int(self.maxLOD)
    desc.addressU = _vp2_wrap_for(int(self.wrapModeU))
    desc.addressV = _vp2_wrap_for(int(self.wrapModeV))
    try:
        desc.borderColor = (
            float(border[0]), float(border[1]), float(border[2]), 1.0
        )
    except Exception:
        pass
    self.shader.setParameter(
        samp_param,
        self.state_manager.acquireSamplerState(desc),
    )
'''
