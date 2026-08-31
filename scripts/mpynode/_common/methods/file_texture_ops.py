"""Maya-free texture-ops math: the importable twin of the inline math in
``mpynode._defaults/file_defaults.py`` ``DEFAULT_INIT_SOURCE``.

This is the CANONICAL, importable copy of the color-space linearization,
pre-filter kernels, CPU blur, UV-wrap policy, bilinear sampler, and VP2
sampler-enum / GPU-upload helpers that ``customFileTexture`` (and mPyFile's
default Init source) implement inline.

TWO copies, ONE behavior:

  * ``DEFAULT_INIT_SOURCE`` (in ``_defaults/file_defaults.py``) is exec'd node
    source -- it is what a brand-new mPyFile ships in its editable Init tab, and
    it is preserved verbatim by the one-way ``.py`` bake/export. Being exec'd
    node source, it CANNOT ``import`` this module (a baked ``.py`` must stand
    alone). So it keeps its own inline copy of the math.

  * THIS module is the same math, importable from real Python (the api2 node's
    BAREBONES fast path, the porter, tests) with NO Maya at import time.

Because they cannot share code, they are kept in lock-step by the drift-guard
test ``mpynode._tests.test_file_texture_ops_drift`` -- it execs the inline
source and asserts every function/matrix here produces byte-identical output.
When you change the math in one, change the other and the drift test proves it.

Maya-free contract: this module lives under ``_common`` and MUST NOT import maya
at module-import time. The three VP2 helpers (``vp2_filter_for``,
``vp2_wrap_for``, ``upload_linear_texture``) lazy-import
``maya.api.OpenMayaRender`` inside their function bodies.

numpy / PIL / scipy are optional: guarded so a numpy-less create does not crash
at import. The gamut matrices degrade to ``None`` and the image helpers
early-return ``None`` when numpy is missing. PIL is NOT required -- it does not
ship with mayapy (Maya 2024 has none at all) -- so ``decode_rgba8`` walks a
chain of decoders that all produce IDENTICAL bytes; see its docstring.
"""

from __future__ import annotations

import os
import struct
import sys
import threading
import zlib

# Optional numpy / PIL / scipy. Guarded so the module imports without numpy --
# gamut matrices become None and the image helpers early-return None.
try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None
try:
    from PIL import Image as _PILImage
except ImportError:  # pragma: no cover
    _PILImage = None
try:
    from scipy.ndimage import convolve1d as _scipy_convolve1d
    _HAVE_SCIPY = True
except ImportError:  # pragma: no cover
    _scipy_convolve1d = None
    _HAVE_SCIPY = False

# Enum int constants -- REAL dedup from the declarative SSOT (no inline mirror).
from mpynode._common.interface.file_texture_interface import (
    kFilterPoint, kFilterLinear, kFilterAnisotropic,
    kMipmapNone, kMipmapAuto,
    kWrapWrap, kWrapClamp, kWrapMirror, kWrapBorder,
    kPreFilterBox, kPreFilterQuadratic, kPreFilterQuartic, kPreFilterGaussian,
)


# ---- per-process linearized-pixel cache ----
# Module-level (not per-instance) so the BAREBONES path is stateless across
# MPyFile instances of the same file. Hypershade swatch + VP2 can pull
# concurrently on worker/render threads; the lock is held ONLY around the dict
# check and write, so concurrent loads of different textures don't serialize.
_LINEAR_CACHE: dict = {}
_LINEAR_CACHE_LOCK = threading.Lock()


# ---- gamut matrices (source primaries -> Rec.709 / sRGB linear, D65) ----
# Kept named EXACTLY like the inline copy (``_M_*_to_Rec709``) -- the drift
# test compares them by name.
if np is not None:
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
else:  # pragma: no cover
    _M_AdobeRGB_to_Rec709 = None
    _M_P3D65_to_Rec709 = None
    _M_Rec2020_to_Rec709 = None
    _M_AP0_to_Rec709 = None
    _M_AP1_to_Rec709 = None
    _M_AlexaWide_to_Rec709 = None
    _M_REDWide_to_Rec709 = None
    _M_SGamut3_to_Rec709 = None


# ---- transfer functions (vectorized, no per-pixel loops) ----
def srgb_eotf(rgb):
    """sRGB encoded -> linear (full piecewise)."""
    low = rgb / 12.92
    high = np.power((rgb + 0.055) / 1.055, 2.4)
    return np.where(rgb <= 0.04045, low, high).astype(np.float32)


def gamma_eotf(rgb, gamma):
    """Pure-gamma EOTF. Clamps negatives to 0 for numeric stability."""
    return np.power(np.maximum(rgb, 0.0), gamma).astype(np.float32)


def apply_matrix(rgb, M):
    """Apply 3x3 M to every pixel of HxWx3 in ONE einsum call."""
    return np.einsum("ij,hwj->hwi", M, rgb).astype(np.float32)


def acescct_eotf(rgb):
    """ACEScct encoded -> linear (AP1 primaries)."""
    low = (rgb - np.float32(0.0729055341958355)) / np.float32(10.5402377416545)
    high = np.power(np.float32(2.0), rgb * np.float32(17.52) - np.float32(9.72))
    return np.where(rgb <= np.float32(0.155251141552511), low, high).astype(np.float32)


def logc_v3_ei800_eotf(rgb):
    """ARRI LogC v3 EI=800 encoded -> linear (AlexaWideGamut)."""
    cut = np.float32(0.149658)
    low = (rgb - np.float32(0.092809)) / np.float32(5.367655)
    high = (
        np.power(np.float32(10.0), (rgb - np.float32(0.385537)) / np.float32(0.247190))
        - np.float32(0.052272)
    ) / np.float32(5.555556)
    return np.where(rgb > cut, high, low).astype(np.float32)


def red_log3g10_eotf(rgb):
    """RED Log3G10 encoded -> linear (REDWideGamutRGB)."""
    return (
        (np.power(np.float32(10.0), rgb / np.float32(0.224282)) - np.float32(1.0))
        / np.float32(155.975327) - np.float32(0.01)
    ).astype(np.float32)


def slog3_eotf(rgb):
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


def adx10_eotf(rgb):
    """ACES ADX10 (10-bit printing density) -> linear (AP0). Preview."""
    density = (rgb * np.float32(1023.0) - np.float32(95.0)) * (
        np.float32(2.0) / np.float32(928.0)
    )
    return (
        np.float32(0.18) * np.power(np.float32(10.0), np.float32(1.6056) - density)
    ).astype(np.float32)


# ---- pre-filter kernel builders ----
def gaussian_kernel(radius):
    """1D Gaussian kernel. Maya convention: sigma = radius / 2."""
    sigma = max(float(radius) / 2.0, 0.5)
    half = int(np.ceil(3.0 * sigma))
    x = np.arange(-half, half + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    return (k / k.sum()).astype(np.float32)


def box_kernel(radius):
    """1D uniform (box) kernel."""
    half = max(1, int(round(float(radius))))
    n = 2 * half + 1
    return np.full(n, 1.0 / float(n), dtype=np.float32)


def quadratic_kernel(radius):
    """1D triangular (tent / quadratic B-spline) kernel."""
    half = max(1, int(round(float(radius))))
    x = np.arange(-half, half + 1, dtype=np.float32)
    k = np.maximum(
        np.float32(0.0), np.float32(1.0) - np.abs(x) / np.float32(half + 1)
    )
    return (k / k.sum()).astype(np.float32)


def quartic_kernel(radius):
    """1D iterated-binomial kernel. Self-convolves [1,2,1]/4 (2*r) times."""
    base = np.array([1.0, 2.0, 1.0], dtype=np.float32) / np.float32(4.0)
    n_iter = max(1, int(round(float(radius))) * 2)
    k = base.copy()
    for _ in range(n_iter - 1):
        k = np.convolve(k, base, mode="full")
    return (k / k.sum()).astype(np.float32)


def blur_separable(image, k1d):
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


def prefilter(linear_pixels, enabled, kernel, radius):
    """Apply CPU pre-filter blur to linearized float32 HxWx4 pixels."""
    if not enabled or linear_pixels is None or radius <= 0.0:
        return linear_pixels
    if kernel == kPreFilterGaussian:
        k1d = gaussian_kernel(radius)
    elif kernel == kPreFilterBox:
        k1d = box_kernel(radius)
    elif kernel == kPreFilterQuadratic:
        k1d = quadratic_kernel(radius)
    elif kernel == kPreFilterQuartic:
        k1d = quartic_kernel(radius)
    else:
        return linear_pixels
    return blur_separable(linear_pixels, k1d)


# ---- linearize a uint8 RGBA image from a color space index ----
def linearize(pixels_uint8, cs_index, unpremultiply=False):
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
        lin = srgb_eotf(rgb)
    elif cs_index == 1:
        lin = gamma_eotf(rgb, 1.8)
    elif cs_index in (2, 5, 7, 15, 17):
        lin = gamma_eotf(rgb, 2.2)
    elif cs_index in (3, 16):
        lin = gamma_eotf(rgb, 2.4)
    elif cs_index == 18:
        lin = gamma_eotf(rgb, 2.6)
    elif cs_index == 20:
        lin = acescct_eotf(rgb)
    elif cs_index == 21:
        lin = logc_v3_ei800_eotf(rgb)
    elif cs_index == 22:
        lin = red_log3g10_eotf(rgb)
    elif cs_index == 23:
        lin = slog3_eotf(rgb)
    elif cs_index == 24:
        lin = adx10_eotf(rgb)
    else:
        lin = rgb

    # Gamut matrix (single einsum if needed).
    if cs_index in (7, 12, 17):
        lin = apply_matrix(lin, _M_AdobeRGB_to_Rec709)
    elif cs_index in (6, 11, 18):
        lin = apply_matrix(lin, _M_P3D65_to_Rec709)
    elif cs_index == 13:
        lin = apply_matrix(lin, _M_Rec2020_to_Rec709)
    elif cs_index in (10, 24):
        lin = apply_matrix(lin, _M_AP0_to_Rec709)
    elif cs_index in (9, 4, 5, 20):
        lin = apply_matrix(lin, _M_AP1_to_Rec709)
    elif cs_index == 21:
        lin = apply_matrix(lin, _M_AlexaWide_to_Rec709)
    elif cs_index == 22:
        lin = apply_matrix(lin, _M_REDWide_to_Rec709)
    elif cs_index == 23:
        lin = apply_matrix(lin, _M_SGamut3_to_Rec709)
    return np.concatenate([lin, alpha], axis=-1).astype(np.float32)


# ---- exact PNG decode (straight alpha), the twin of PNG_CPP's nd_png_* ----
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_CHAN = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def png_supported(data):
    """Does the exact decoder handle these bytes? Twin of ``nd_png_supported``.

    This predicate is load-bearing for parity, not an optimization: BOTH tiers
    ask it of the same header bytes and take the exact path or the MImage path
    together. If they could answer differently, one tier would decode straight
    alpha while the other decoded associated alpha -- which is precisely the
    class of divergence the exact decoder exists to remove.
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
    """Reverse the per-scanline filters.

    None/Sub/Up are whole-array operations -- Sub in particular is just a
    mod-256 cumulative sum down each byte lane -- so only Average and Paeth
    need the byte-at-a-time recurrence, and those rows pay for it alone.
    """
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


def png_decode(data):
    """Decode PNG bytes to top-down (h, w, 4) uint8 RGBA with STRAIGHT alpha.

    Returns None for anything ``png_supported`` declines or any malformed
    stream, so the caller falls back exactly as the C++ twin does.
    """
    if not png_supported(data):
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
    the C++ twin TRUNCATE to the high byte, which would put the tiers one level
    apart on every channel.
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
def decode_rgba8(path):
    """Decode ``path`` to ``(top-down uint8 HxWx4 RGBA, premultiplied)``.

    The second element is the ALPHA ASSOCIATION of the returned pixels, and it
    is the whole point of this function: the decoders disagree about it. A PNG
    stores colour and alpha separately and that is what the compositing math
    assumes, but MImage hands back colour already multiplied by alpha AND
    quantised to 8 bits, which is lossy on every antialiased edge. Reporting
    which decoder ran lets ``linearize`` undo the association at the right point.

    The order below is chosen so that whatever runs here produces the SAME bytes
    the compiled tier's ``nd_png_decode`` produces:

      1. ``png_supported`` -- the identical predicate the C++ twin uses. When it
         says yes, all three exact decoders below agree byte-for-byte (verified
         over a 4,575-file corpus), and so does the C++ one.
      2. PIL, then Qt, then the pure-Python ``png_decode``. Qt ships with every
         Maya; PIL does not (Maya 2024 has none), and the pure-Python path is
         the guarantee that a host with neither still matches.
      3. Anything declined by the predicate -- interlaced, 16-bit greyscale, a
         non-PNG format -- falls through to MImage, which is ALSO what the
         compiled tier falls back to, so the two stay in step.

    (Maya-free contract: the MImage import is lazy, like the VP2 helpers below.)
    """
    try:
        # The WHOLE file, not just the header: for greyscale / truecolour the
        # predicate has to scan the chunk list for tRNS, and a short read would
        # let it answer "supported" where the C++ twin -- which always sees the
        # whole file -- answers "declined". The two must never disagree.
        with open(path, "rb") as fh:
            data = fh.read()
        if png_supported(data):
            if _PILImage is not None:
                return (np.asarray(_PILImage.open(path).convert("RGBA"),
                                   dtype=np.uint8), False)
            qt = _qimage_rgba8(path, data[24])
            if qt is not None:
                return (qt, False)
            px = png_decode(data)
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
def load_linear_pixels(path, cs_index, prefilter_on, kernel, radius):
    """Load ``path``, linearize from color space ``cs_index``, apply
    optional CPU pre-filter, return float32 HxWx4. Returns None on
    missing file or load failure (and when numpy is absent).

    Cached by (path, cs_index, prefilter_on, kernel, radius_quantized)
    in the module-level ``_LINEAR_CACHE`` so Hypershade swatch generation
    and per-frame VP2 updateShader calls don't re-read the file. The lock
    is held ONLY around the cache check + write; the heavy load runs
    outside it. (The prefilter flag param is named ``prefilter_on`` so it
    does not shadow the module-level ``prefilter`` function.)
    """
    if np is None:
        return None
    radius_q = round(float(radius), 1) if radius else 0.0
    cache_key = (
        path, int(cs_index), bool(prefilter_on), int(kernel), radius_q
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

    # Load + linearize + prefilter run OUTSIDE the lock; only the cache check
    # and write are inside it.
    try:
        raw, premultiplied = decode_rgba8(path)
        lin = linearize(raw, int(cs_index), unpremultiply=premultiplied)
        result = prefilter(lin, prefilter_on, int(kernel), radius_q)
    except Exception as exc:
        sys.stderr.write(
            "[file_texture_ops] failed to load %s (cs=%d): %s\n"
            % (path, cs_index, exc)
        )
        with _LINEAR_CACHE_LOCK:
            _LINEAR_CACHE[cache_key] = None
        return None

    with _LINEAR_CACHE_LOCK:
        # Re-check: another thread may have populated it meanwhile.
        if cache_key in _LINEAR_CACHE and _LINEAR_CACHE[cache_key] is not None:
            return _LINEAR_CACHE[cache_key]
        _LINEAR_CACHE[cache_key] = result
    return result


# ---- UV wrap policy + bilinear sampler (Compute tab) ----
def apply_wrap(coord, mode):
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


def sample(pixels, u, v, wrap_u, wrap_v, border_color, missing=None):
    """Bilinear-sample float32 ``pixels`` (HxWx4 linearized) at UV
    (u, v) honoring wrap mode. Returns (r, g, b, a) in [0, 1].
    Magenta if pixels is None, unless ``missing`` overrides it.

    ``missing`` is the no-image substitute: None keeps the opaque magenta
    sentinel (the historical behaviour), an RGBA tuple replaces it. Kept in
    lock step with nd_tex_sample's ``miss`` parameter in the C++ twin."""
    if pixels is None:
        if missing is None:
            return (1.0, 0.0, 1.0, 1.0)
        return (float(missing[0]), float(missing[1]),
                float(missing[2]), float(missing[3]))

    uu, u_oob = apply_wrap(u, wrap_u)
    vv_raw, v_oob = apply_wrap(v, wrap_v)
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


# ---- VP2 enum maps + GPU upload (Viewport path; lazy-import maya) ----
def vp2_filter_for(mode):
    """Map our filterMode enum to MSamplerState filter constant."""
    import maya.api.OpenMayaRender as omr
    return {
        kFilterPoint: omr.MSamplerState.kMinMagMipPoint,
        kFilterLinear: omr.MSamplerState.kMinMagMipLinear,
        kFilterAnisotropic: omr.MSamplerState.kAnisotropic,
    }.get(int(mode), omr.MSamplerState.kMinMagMipLinear)


def vp2_wrap_for(mode):
    """Map our wrapMode enum to MSamplerState address constant."""
    import maya.api.OpenMayaRender as omr
    return {
        kWrapWrap: omr.MSamplerState.kTexWrap,
        kWrapClamp: omr.MSamplerState.kTexClamp,
        kWrapMirror: omr.MSamplerState.kTexMirror,
        kWrapBorder: omr.MSamplerState.kTexBorder,
    }.get(int(mode), omr.MSamplerState.kTexWrap)


def upload_linear_texture(linear, fileName, colorSpace, mipmapMode,
                          preFilter, preFilterKernel, preFilterRadius,
                          *, name_prefix="mpyfile::", dummy_name=None):
    """Upload a float32 HxWx4 array to the GPU via the texture manager's
    in-memory acquireTexture(name, MTextureDescription, pixelData,
    gen_mips) overload. Bypasses Maya's file-based color management so
    the GPU samples our already-linearized data directly.

    The texture cache name is either ``dummy_name`` (verbatim, when given)
    or ``"<name_prefix><fileName>|cs=..|pf=.."`` so different color-space /
    pre-filter settings get distinct cache entries.
    """
    if linear is None or np is None:
        return None
    import maya.api.OpenMayaRender as omr
    texture_mgr = omr.MRenderer.getTextureManager()
    if texture_mgr is None:
        return None

    h, w, c = linear.shape
    if c != 4:
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

    if not linear.flags["C_CONTIGUOUS"]:
        linear = np.ascontiguousarray(linear)
    pixel_bytes = linear.tobytes()
    gen_mipmaps = int(mipmapMode) == kMipmapAuto

    radius_q = (
        round(float(preFilterRadius), 1) if preFilterRadius else 0.0
    )
    if dummy_name is not None:
        tex_name = dummy_name
    else:
        tex_name = "%s%s|cs=%d|pf=%d:%d:%.1f" % (
            name_prefix,
            fileName,
            int(colorSpace),
            int(bool(preFilter)),
            int(preFilterKernel),
            radius_q,
        )
    return texture_mgr.acquireTexture(tex_name, desc, pixel_bytes, gen_mipmaps)
