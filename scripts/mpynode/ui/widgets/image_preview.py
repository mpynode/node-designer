"""Inline image previews for the Watch + Variables tabs.

A stored variable that holds an image can be shown as a thumbnail in the
Value column instead of a text repr. Three value kinds are recognised:

  * ``PIL.Image.Image``                -> defaults to IMAGE view
  * an image ``bytes``/``bytearray``   -> defaults to SOURCE view
    blob (PNG/JPEG/GIF/BMP/TIFF/WEBP, sniffed by magic bytes; decoded
    natively by Qt -- no PIL needed)
  * a ``uint8`` numpy array shaped      -> defaults to SOURCE view
    ``(H,W)`` / ``(H,W,1|3|4)``

Ambiguous kinds (bytes / uint8 array -- might be data, might be a
picture) default to SOURCE and expose a right-click "Show as Image"
toggle; a real PIL image defaults to IMAGE. The per-row mode lives in
:data:`SHOW_IMAGE_ROLE`; the (lazily built) master pixmap in
:data:`PREVIEW_ROLE`.

Sizing: the thumbnail fits the value column at its ACTUAL aspect ratio
-- width == column width, height == width * (imgH/imgW) -- so the row is
exactly as tall as the image (no letterbox padding) and the variable
name stays top-aligned with it. Qt rescales the master pixmap at paint
time; a ``sectionResized`` hook only requests a relayout (it never
writes column widths, so it can't re-enter the resize loop that
previously crashed Maya).
"""

from __future__ import annotations

import os

from mpynode.ui.qt_wrapper import (
    QBuffer,
    QByteArray,
    QColor,
    QImage,
    QLabel,
    QMovie,
    QPainter,
    QPixmap,
    QSize,
    QStyledItemDelegate,
    Qt,
)

# Private item-data roles.
PREVIEW_ROLE = int(Qt.UserRole) + 137      # master QPixmap (lazy)
SHOW_IMAGE_ROLE = int(Qt.UserRole) + 138   # bool: render as image vs text
PREVIEWABLE_ROLE = int(Qt.UserRole) + 139  # "pil" / "bytes" / "uint8"
RAW_VALUE_ROLE = int(Qt.UserRole) + 140    # the original value (lazy build)
SHOW_WAVEFORM_ROLE = int(Qt.UserRole) + 141   # bool: render bytes as a waveform
AUDIO_CANDIDATE_ROLE = int(Qt.UserRole) + 142  # bool: bytes could be WAV/PCM audio

# Clamp so an extreme aspect / column width can't make a giant row.
_MAX_EDGE = 1024
# Tiny inset so the selection highlight peeks as a thin border.
_PAD = 2


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------
def preview_source_px() -> int:
    """Fixed master-thumbnail edge (px) from prefs; clamped to sane bounds."""
    px = 256
    try:
        from mpynode.ui import preferences

        px = int(preferences.get_pref("variables_image_preview_px", 256))
    except Exception:
        px = 256
    return max(32, min(px, 2048))


def animate_gif_pref_on() -> bool:
    """True when GIF value cells should animate (default on). Off -> the
    existing static first-frame thumbnail."""
    try:
        from mpynode.ui import preferences

        return bool(preferences.get_pref("variables_animate_gif", True))
    except Exception:
        return True


def render_waveform_pref_on() -> bool:
    """True when audio (WAV / raw PCM) value cells may render as a waveform
    (default on). Off -> audio bytes stay as their text repr."""
    try:
        from mpynode.ui import preferences

        return bool(preferences.get_pref("variables_render_waveform", True))
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def is_pil_image(value) -> bool:
    """True iff ``value`` is a PIL/Pillow image (import-guarded)."""
    try:
        from PIL import Image

        return isinstance(value, Image.Image)
    except Exception:
        return False


def _looks_like_image_bytes(value) -> bool:
    """Cheap magic-byte sniff for common image formats Qt can decode."""
    if not isinstance(value, (bytes, bytearray)):
        return False
    if len(value) < 12:
        return False
    head = bytes(value[:12])
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if head[:2] == b"BM":  # BMP
        return True
    if head[:4] in (b"II*\x00", b"MM\x00*"):  # TIFF (LE / BE)
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    return False


def _is_uint8_image_array(value) -> bool:
    """True iff ``value`` is a uint8 ndarray shaped like an image."""
    try:
        import numpy as np
    except Exception:
        return False
    if not isinstance(value, np.ndarray) or value.dtype != np.uint8:
        return False
    if value.ndim == 2:
        return True
    if value.ndim == 3 and value.shape[2] in (1, 3, 4):
        return True
    return False


def previewable_kind(value):
    """Return "pil" / "bytes" / "uint8" if ``value`` is image-previewable,
    else ``None``."""
    if is_pil_image(value):
        return "pil"
    if _is_uint8_image_array(value):
        return "uint8"
    if _looks_like_image_bytes(value):
        return "bytes"
    return None


def is_gif_bytes(value) -> bool:
    """True iff ``value`` is a GIF byte blob (GIF87a/GIF89a). The animated
    case is handled by QMovie, which plays whatever frames the blob holds
    (a single-frame GIF simply shows static), so a magic-byte check is all
    the row needs to opt into the QMovie path."""
    if not isinstance(value, (bytes, bytearray)):
        return False
    return bytes(value[:6]) in (b"GIF87a", b"GIF89a")


def _is_animated_pil_gif(value) -> bool:
    """True iff ``value`` is an animated PIL GIF image -- what
    ``Image.open('x.gif')`` returns (a PIL Image, NOT raw bytes)."""
    return (is_pil_image(value)
            and bool(getattr(value, "is_animated", False))
            and getattr(value, "format", "") == "GIF")


def is_animated_gif_value(value) -> bool:
    """True iff ``value`` is a GIF the QMovie path can animate -- raw GIF bytes
    OR an animated PIL GIF image (cheap: no decode / re-encode)."""
    return is_gif_bytes(value) or _is_animated_pil_gif(value)


def gif_movie_bytes(value):
    """Return GIF bytes a QMovie can play, or None. Raw GIF bytes pass through;
    an animated PIL GIF is sourced from its original file (best fidelity) or
    re-encoded with all frames."""
    try:
        if is_gif_bytes(value):
            return bytes(value)
        if _is_animated_pil_gif(value):
            fn = getattr(value, "filename", None)
            if fn and os.path.isfile(fn):
                with open(fn, "rb") as fh:
                    data = fh.read()
                if is_gif_bytes(data):
                    return data
            import io

            buf = io.BytesIO()
            value.save(buf, format="GIF", save_all=True)
            data = buf.getvalue()
            return data if is_gif_bytes(data) else None
    except Exception:
        pass
    return None


def _looks_like_wav_bytes(value) -> bool:
    """Cheap magic-byte sniff for a RIFF/WAVE container. Mirrors the WEBP
    branch in :func:`_looks_like_image_bytes` -- a WAV is ``RIFF....WAVE``."""
    if not isinstance(value, (bytes, bytearray)):
        return False
    if len(value) < 12:
        return False
    head = bytes(value[:12])
    return head[:4] == b"RIFF" and head[8:12] == b"WAVE"


# Real extension per container. Names both the temp file QMediaPlayer plays
# (so it picks the right native decoder) and the one QAudioDecoder reads.
_AUDIO_EXT = {
    "WAV": ".wav", "MP3": ".mp3", "OGG": ".ogg",
    "FLAC": ".flac", "AIFF": ".aiff", "M4A": ".m4a",
}


def _audio_container_kind(value):
    """Recognized audio container label ("WAV"/"MP3"/"OGG"/"FLAC"/"AIFF"/"M4A")
    from a leading magic-byte sniff, or None. Only these auto-render as a
    waveform; unrecognized bytes stay headerless raw PCM (opt-in via the
    per-row toggle)."""
    if not isinstance(value, (bytes, bytearray)):
        return None
    if len(value) < 12:
        return None
    head = bytes(value[:12])
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "WAV"
    # MP3: an ID3v2 tag, or a raw MPEG-audio frame sync (11 bits set).
    if head[:3] == b"ID3" or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "MP3"
    if head[:4] == b"OggS":
        return "OGG"
    if head[:4] == b"fLaC":
        return "FLAC"
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return "AIFF"
    # M4A/AAC in MP4: a ``ftyp`` box with an AUDIO brand. A video ``.mp4``
    # uses isom/mp42 and is intentionally NOT matched.
    if head[4:8] == b"ftyp" and head[8:12] in (b"M4A ", b"M4B ", b"M4P "):
        return "M4A"
    return None


def _compressed_audio_kind(value):
    """Container kind that the stdlib ``wave`` module CANNOT parse and so needs
    QAudioDecoder (everything recognized except WAV), or None."""
    k = _audio_container_kind(value)
    return None if k in (None, "WAV") else k


def _looks_like_binary_str(s) -> bool:
    """True for a Python-2 'bytes-as-str' binary blob (e.g. legacy raw PCM saved
    as a str): a latin-1 string large enough to be real binary data AND mostly
    NON-printable. Natural-language text -- even with accented (latin-1-high)
    characters -- stays predominantly printable ASCII and returns False, so
    plain string variables don't masquerade as audio. (Accents alone don't
    qualify: the discriminator is the printable-ASCII fraction, not the high
    bytes that accents and raw PCM share.)"""
    try:
        b = s.encode("latin-1")
    except Exception:
        return False
    if len(b) < 16:
        return False
    printable = sum(1 for c in b if 0x20 <= c <= 0x7e or c in (0x09, 0x0a, 0x0d))
    return printable / len(b) < 0.5


def _as_audio_bytes(value):
    """Audio bytes for a value, or None. Passes ``bytes``/``bytearray`` through
    and recovers a legacy Python-2 'bytes-as-str' raw-PCM value via latin-1.
    Older scenes (e.g. the ``ouch`` sample) stored uint8 PCM as a str (Py2 str
    == bytes); in Py3 it loads back as a str, which the byte-only audio path
    used to reject."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str) and _looks_like_binary_str(value):
        try:
            return value.encode("latin-1")
        except Exception:
            return None
    return None


def is_audio_candidate(value) -> bool:
    """True iff ``value`` could be rendered as a waveform.

    A real WAV container is auto-detectable. Raw PCM has no signature, so any
    non-image byte blob also qualifies -- the user opts it in via the per-row
    "Show as Waveform" toggle (it is then interpreted as uint8 mono). Image
    byte blobs are excluded (they get "Show as Image" instead). A legacy
    bytes-as-str raw-PCM value is coerced via :func:`_as_audio_bytes`."""
    b = _as_audio_bytes(value)
    if b is None:
        return False
    if _looks_like_wav_bytes(b):
        return True
    # Unknown non-image bytes could be raw PCM.
    return not _looks_like_image_bytes(b)


def image_caption(value) -> str:
    """Short human label for a previewable value (used as a tooltip)."""
    try:
        if is_pil_image(value):
            return f"PIL image  {value.mode}  {value.width}x{value.height}"
        import numpy as np

        if isinstance(value, np.ndarray):
            return f"uint8 image  {tuple(value.shape)}"
        if isinstance(value, (bytes, bytearray)):
            return f"image bytes  ({len(value)} bytes)"
    except Exception:
        pass
    return "image"


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def _numpy_to_qimage(arr):
    """uint8 ndarray (H,W) / (H,W,1|3|4) -> owned QImage, or None."""
    try:
        import numpy as np

        a = np.ascontiguousarray(arr)
        h, w = int(a.shape[0]), int(a.shape[1])
        if a.ndim == 2:
            fmt, bpl = QImage.Format_Grayscale8, w
        else:
            ch = a.shape[2]
            if ch == 1:
                a = np.ascontiguousarray(a[:, :, 0])
                fmt, bpl = QImage.Format_Grayscale8, w
            elif ch == 3:
                fmt, bpl = QImage.Format_RGB888, 3 * w
            elif ch == 4:
                fmt, bpl = QImage.Format_RGBA8888, 4 * w
            else:
                return None
        # ``.copy()`` so the QImage owns its pixels; the tobytes buffer is
        # freed once this returns.
        return QImage(a.tobytes(), w, h, bpl, fmt).copy()
    except Exception:
        return None


def make_preview_pixmap(value, source_px: int | None = None):
    """Build a master ``QPixmap`` (shrunk to ``source_px`` on its long
    edge, aspect preserved) for a previewable value, or ``None``. Never
    mutates the source value."""
    kind = previewable_kind(value)
    if kind is None:
        return None
    if source_px is None:
        source_px = preview_source_px()
    try:
        pm = QPixmap()
        if kind == "pil":
            import io

            im = value.convert("RGBA")
            im.thumbnail((source_px, source_px))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            if not pm.loadFromData(buf.getvalue(), "PNG"):
                return None
        elif kind == "bytes":
            if not pm.loadFromData(bytes(value)):
                return None
        elif kind == "uint8":
            qimg = _numpy_to_qimage(value)
            if qimg is None:
                return None
            pm = QPixmap.fromImage(qimg)
        if pm.isNull():
            return None
        # Only ever shrink the master; keeps memory + paint scaling cheap.
        if pm.width() > source_px or pm.height() > source_px:
            pm = pm.scaled(
                source_px, source_px, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        return pm
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Audio / waveform
# ---------------------------------------------------------------------------
# Rate assumed for HEADERLESS raw PCM only -- a common capture rate for legacy
# uint8 mono. A real WAV carries its own rate, read in decode_audio.
_DEFAULT_PCM_RATE = 22050


def decode_audio(value, default_rate: int = _DEFAULT_PCM_RATE):
    """Decode an audio byte blob to ``(mono_samples_float32, sample_rate)``.

    * A RIFF/WAVE container is parsed with the stdlib ``wave`` module; 8-bit
      is unsigned-centered, 16/32-bit are signed; multi-channel is mixed to
      mono. The container's own sample rate is returned.
    * Anything else is treated as raw uint8 mono PCM (centered at 128) at
      ``default_rate`` -- the headerless case (e.g. the ``ouch`` sample).

    Samples are normalised to roughly [-1, 1]. Returns an empty array on any
    failure so callers can render a blank waveform rather than crash."""
    import numpy as np

    b = _as_audio_bytes(value)
    if b is None:
        return np.zeros(0, dtype=np.float32), int(default_rate)
    try:
        if _looks_like_wav_bytes(b):
            import io
            import wave

            with wave.open(io.BytesIO(b), "rb") as w:
                nch = w.getnchannels()
                sw = w.getsampwidth()
                rate = w.getframerate()
                raw = w.readframes(w.getnframes())
            if sw == 1:  # unsigned 8-bit
                a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
                     - 128.0) / 128.0
            elif sw == 2:
                usable = (len(raw) // 2) * 2
                a = (np.frombuffer(raw[:usable], dtype="<i2")
                     .astype(np.float32) / 32768.0)
            elif sw == 3:  # signed little-endian 24-bit
                u = np.frombuffer(raw, dtype=np.uint8)
                usable = (u.size // 3) * 3
                u = u[:usable].reshape(-1, 3).astype(np.int32)
                val = u[:, 0] | (u[:, 1] << 8) | (u[:, 2] << 16)
                val = np.where(val >= (1 << 23), val - (1 << 24), val)
                a = val.astype(np.float32) / float(1 << 23)
            elif sw == 4:
                usable = (len(raw) // 4) * 4
                a = (np.frombuffer(raw[:usable], dtype="<i4")
                     .astype(np.float32) / 2147483648.0)
            else:  # exotic width -> best-effort centered uint8 (bounded)
                a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
                     - 128.0) / 128.0
            if nch > 1 and a.size:
                usable = (a.size // nch) * nch
                a = a[:usable].reshape(-1, nch).mean(axis=1)
            return a.astype(np.float32), int(rate)
        # Compressed containers go through QAudioDecoder. On failure / a
        # missing codec that returns an EMPTY array (a clean blank strip),
        # NEVER the compressed bytes reinterpreted as PCM noise.
        ck = _compressed_audio_kind(b)
        if ck is not None:
            return _decode_compressed_audio(b, ck, int(default_rate))
        # Headerless raw PCM: uint8 mono.
        a = (np.frombuffer(b, dtype=np.uint8).astype(np.float32)
             - 128.0) / 128.0
        return a, int(default_rate)
    except Exception:
        return np.zeros(0, dtype=np.float32), int(default_rate)


def _decode_compressed_audio(b, kind, default_rate):
    """Decode a recognized compressed container to ``(mono_float32, rate)`` via
    QtMultimedia's QAudioDecoder. Returns an EMPTY array (and ``default_rate``)
    when the decoder is unavailable or can't decode -- so the waveform renders
    as a clean blank strip rather than PCM noise. Playback still works because
    QMediaPlayer decodes the same blob natively (see :func:`_playable_audio_file`)."""
    import numpy as np

    try:
        from mpynode.ui.qt_wrapper import decode_audio_bytes_to_pcm
    except Exception:
        return np.zeros(0, dtype=np.float32), int(default_rate)
    suffix = _AUDIO_EXT.get(kind, "")
    try:
        pcm, sf, ch, rate = decode_audio_bytes_to_pcm(b, suffix)
    except Exception:
        pcm, sf, ch, rate = None, None, 0, 0
    if not pcm or not sf:
        return np.zeros(0, dtype=np.float32), int(rate or default_rate)
    try:
        # QAudioDecoder yields native-endian PCM; every target platform is
        # little-endian.
        if sf == "uint8":
            a = (np.frombuffer(pcm, dtype=np.uint8).astype(np.float32)
                 - 128.0) / 128.0
        elif sf == "int16":
            usable = (len(pcm) // 2) * 2
            a = (np.frombuffer(pcm[:usable], dtype="<i2")
                 .astype(np.float32) / 32768.0)
        elif sf == "int32":
            usable = (len(pcm) // 4) * 4
            a = (np.frombuffer(pcm[:usable], dtype="<i4")
                 .astype(np.float32) / 2147483648.0)
        elif sf == "float32":
            usable = (len(pcm) // 4) * 4
            a = np.frombuffer(pcm[:usable], dtype="<f4").astype(np.float32)
        else:
            return np.zeros(0, dtype=np.float32), int(rate or default_rate)
        ch = int(ch or 1)
        if ch > 1 and a.size:
            usable = (a.size // ch) * ch
            a = a[:usable].reshape(-1, ch).mean(axis=1)
        return a.astype(np.float32), int(rate or default_rate)
    except Exception:
        return np.zeros(0, dtype=np.float32), int(rate or default_rate)


def waveform_envelope(samples, n_cols: int):
    """Per-column (min, max) envelope of ``samples`` over ``n_cols`` buckets.

    Returns two float arrays of length ``min(n_cols, len(samples))`` (empty
    when there are no samples). Pure numpy; used to draw a peak-to-peak
    waveform that survives heavy downsampling."""
    import numpy as np

    s = np.asarray(samples, dtype=np.float32)
    n = int(s.shape[0]) if s.ndim else 0
    if n == 0 or n_cols <= 0:
        empty = np.zeros(0, dtype=np.float32)
        return empty, empty
    cols = min(int(n_cols), n)
    edges = np.linspace(0, n, cols + 1).astype(int)
    mins = np.empty(cols, dtype=np.float32)
    maxs = np.empty(cols, dtype=np.float32)
    for i in range(cols):
        a = edges[i]
        b = max(edges[i] + 1, edges[i + 1])
        chunk = s[a:b]
        mins[i] = float(chunk.min())
        maxs[i] = float(chunk.max())
    return mins, maxs


# Master size for the waveform pixmap; Qt scales it to the column width at
# paint time. Wide:short, so the row is a strip rather than a block.
_WAVE_SRC_W = 512
_WAVE_SRC_H = 128
_WAVE_BG = (43, 43, 43)        # Maya dark-theme cell background
_WAVE_FG = (120, 190, 240)     # soft blue trace
_WAVE_MID = (90, 90, 90)       # center (zero) line


def render_waveform_pixmap(value, width: int = _WAVE_SRC_W,
                           height: int = _WAVE_SRC_H,
                           default_rate: int = _DEFAULT_PCM_RATE):
    """Render an audio byte blob to a waveform ``QPixmap`` (peak-to-peak
    envelope drawn with QPainter). Never mutates the source value; returns a
    blank-but-valid pixmap if the audio can't be decoded."""
    width = max(1, int(width))
    height = max(1, int(height))
    pm = QPixmap(width, height)
    pm.fill(QColor(*_WAVE_BG))
    try:
        samples, _rate = decode_audio(value, default_rate)
        painter = QPainter(pm)
        try:
            mid = height / 2.0
            # zero line
            painter.setPen(QColor(*_WAVE_MID))
            painter.drawLine(0, int(mid), width, int(mid))
            if getattr(samples, "size", 0):
                mins, maxs = waveform_envelope(samples, width)
                painter.setPen(QColor(*_WAVE_FG))
                cols = len(mins)
                for x in range(cols):
                    # Clamp to [-1, 1], then map to pixel rows (y grows down).
                    hi = max(-1.0, min(1.0, float(maxs[x])))
                    lo = max(-1.0, min(1.0, float(mins[x])))
                    y_top = int(round(mid - hi * mid))
                    y_bot = int(round(mid - lo * mid))
                    if y_top == y_bot:
                        y_bot = y_top + 1
                    px = int(round(x * (width - 1) / max(1, cols - 1))) \
                        if cols > 1 else 0
                    painter.drawLine(px, y_top, px, y_bot)
        finally:
            painter.end()
    except Exception:
        pass
    return pm


def synthesize_wav_bytes(value, rate: int = _DEFAULT_PCM_RATE) -> bytes:
    """Return playable WAV bytes for an audio value.

    A real RIFF/WAVE blob is returned unchanged (already playable). Raw PCM is
    wrapped in a minimal uint8-mono WAV header at ``rate`` so any Qt player /
    QSoundEffect will accept it."""
    b = _as_audio_bytes(value)
    if b is None:
        b = bytes(value)
    if _looks_like_wav_bytes(b):
        return b
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(int(rate))
        w.writeframes(b)
    return buf.getvalue()


def _playable_audio_file(value, rate: int = _DEFAULT_PCM_RATE):
    """``(suffix, payload_bytes)`` to materialise for QMediaPlayer playback.

    A recognized container (WAV/MP3/OGG/FLAC/AIFF/M4A) is written VERBATIM with
    its real extension so QMediaPlayer picks the right native decoder -- MP3 in
    particular only plays when the temp file is named ``.mp3``, not ``.wav``.
    Headerless raw PCM is wrapped into a minimal WAV."""
    b = _as_audio_bytes(value)
    kind = _audio_container_kind(b) if b is not None else None
    ext = _AUDIO_EXT.get(kind)
    if ext and b is not None:
        return ext, b
    return ".wav", synthesize_wav_bytes(value, rate)


def audio_duration_ms(value, default_rate: int = _DEFAULT_PCM_RATE) -> int:
    """Approximate clip length in milliseconds (for scrub position mapping).
    Returns 0 if it can't be determined."""
    try:
        samples, rate = decode_audio(value, default_rate)
        n = int(getattr(samples, "size", 0))
        if n <= 0 or rate <= 0:
            return 0
        return int(round(1000.0 * n / float(rate)))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Item helpers (used by both tabs)
# ---------------------------------------------------------------------------
def _has_pixmap(item, col) -> bool:
    pm = item.data(col, PREVIEW_ROLE)
    return isinstance(pm, QPixmap) and not pm.isNull()


def attach_value(item, col, value, source_text: str):
    """Wire a value cell. Always sets the source text (DisplayRole). If
    the value is image-previewable, records the roles needed for the
    image view + toggle; a PIL image additionally builds its pixmap now
    and defaults to IMAGE view. Returns the kind or ``None``."""
    item.setText(col, source_text)
    kind = previewable_kind(value)
    audio = is_audio_candidate(value)
    if kind is None and not audio:
        return None
    item.setData(col, RAW_VALUE_ROLE, value)
    if kind is not None:
        item.setData(col, PREVIEWABLE_ROLE, kind)
    if audio:
        item.setData(col, AUDIO_CANDIDATE_ROLE, True)
    if kind == "pil":
        pm = make_preview_pixmap(value)
        if pm is not None:
            item.setData(col, PREVIEW_ROLE, pm)
            item.setData(col, SHOW_IMAGE_ROLE, True)
            item.setData(col, SHOW_WAVEFORM_ROLE, False)
            item.setToolTip(col, image_caption(value))
            return kind
    # A recognized container auto-renders as a waveform when the pref is on,
    # mirroring how a PIL image auto-shows as IMAGE. Headerless raw PCM has no
    # signature, so it stays SOURCE until the user opts in.
    if audio and _audio_container_kind(_as_audio_bytes(value)) is not None \
            and render_waveform_pref_on():
        if set_waveform_view(item, col, True):
            return kind
    # Ambiguous kinds / raw PCM / a failed build default to SOURCE view.
    item.setData(col, SHOW_IMAGE_ROLE, False)
    item.setData(col, SHOW_WAVEFORM_ROLE, False)
    if kind is not None:
        item.setToolTip(col, "Right-click \u25b8 Show as Image")
    else:
        item.setToolTip(col, "Right-click \u25b8 Show as Waveform")
    return kind


def is_previewable_item(item, col) -> bool:
    try:
        return bool(item.data(col, PREVIEWABLE_ROLE))
    except Exception:
        return False


def is_showing_image(item, col) -> bool:
    try:
        return bool(item.data(col, SHOW_IMAGE_ROLE))
    except Exception:
        return False


def toggle_value_mode(item, col):
    """Flip a previewable cell between SOURCE and IMAGE. Builds the
    master pixmap lazily on the first switch to IMAGE. Returns the new
    ``is_image`` bool, or ``None`` if the row isn't previewable / the
    image couldn't be built."""
    if not is_previewable_item(item, col):
        return None
    return set_image_view(item, col, not is_showing_image(item, col))


def set_image_view(item, col, show_image: bool):
    """Force a previewable cell into IMAGE or SOURCE view explicitly.

    Unlike :func:`toggle_value_mode`, this sets an absolute state and, when
    switching to IMAGE, (re)builds the master pixmap from the row's CURRENT
    raw value -- so a remembered "show as image" choice keeps rendering the
    LATEST value as the variable updates live (the previous pixmap was built
    from a stale value). No-op for non-previewable rows. Returns the applied
    bool, or ``None`` if the row isn't previewable / the image couldn't be
    built (in which case it falls back to SOURCE)."""
    if not is_previewable_item(item, col):
        return None
    if show_image:
        value = item.data(col, RAW_VALUE_ROLE)
        pm = make_preview_pixmap(value)
        if pm is None:
            item.setData(col, SHOW_IMAGE_ROLE, False)
            return False
        item.setData(col, PREVIEW_ROLE, pm)
        try:
            item.setToolTip(col, image_caption(value))
        except Exception:
            pass
        item.setData(col, SHOW_IMAGE_ROLE, True)
        item.setData(col, SHOW_WAVEFORM_ROLE, False)
        return True
    item.setData(col, SHOW_IMAGE_ROLE, False)
    return False


def is_audio_item(item, col) -> bool:
    """True iff the row's value was recorded as an audio candidate (WAV/PCM)."""
    try:
        return bool(item.data(col, AUDIO_CANDIDATE_ROLE))
    except Exception:
        return False


def is_showing_waveform(item, col) -> bool:
    try:
        return bool(item.data(col, SHOW_WAVEFORM_ROLE))
    except Exception:
        return False


def set_waveform_view(item, col, show_waveform: bool):
    """Force an audio-candidate cell into WAVEFORM or SOURCE view.

    Switching to WAVEFORM (re)builds the master waveform pixmap from the row's
    CURRENT raw value (so a remembered choice keeps rendering the latest value
    as it updates live) and clears the mutually-exclusive image view. No-op for
    non-audio rows. Returns the applied bool, or ``None`` if the row isn't an
    audio candidate / the waveform couldn't be built (falls back to SOURCE)."""
    if not is_audio_item(item, col):
        return None
    if show_waveform:
        value = item.data(col, RAW_VALUE_ROLE)
        pm = render_waveform_pixmap(value)
        if pm is None or pm.isNull():
            item.setData(col, SHOW_WAVEFORM_ROLE, False)
            return False
        item.setData(col, PREVIEW_ROLE, pm)
        item.setData(col, SHOW_IMAGE_ROLE, False)
        item.setData(col, SHOW_WAVEFORM_ROLE, True)
        try:
            item.setToolTip(col, _wave_caption(value))
        except Exception:
            pass
        return True
    item.setData(col, SHOW_WAVEFORM_ROLE, False)
    return False


def toggle_waveform_view(item, col):
    """Flip an audio-candidate cell between SOURCE and WAVEFORM. Returns the
    new ``is_waveform`` bool, or ``None`` if the row isn't an audio candidate /
    the waveform couldn't be built."""
    if not is_audio_item(item, col):
        return None
    return set_waveform_view(item, col, not is_showing_waveform(item, col))


def _wave_caption(value) -> str:
    """Tooltip for a waveform cell."""
    try:
        b = _as_audio_bytes(value) or b""
        dur = audio_duration_ms(value) / 1000.0
        n = len(b)
        kind = _audio_container_kind(b) or "PCM"
        return ("%s audio  %.2fs  (%d bytes)\nClick to play, drag to scrub"
                % (kind, dur, n))
    except Exception:
        return "audio — click to play, drag to scrub"


# ---------------------------------------------------------------------------
# Per-row media widget (animated GIF / interactive waveform)
# ---------------------------------------------------------------------------
def _value_sig(value):
    """Cheap content signature so a live-reconciling tab can tell whether a
    cell's media bytes actually changed (and avoid rebuilding the widget --
    which would restart a GIF / re-decode a waveform every poll tick)."""
    try:
        if is_pil_image(value):
            # A PIL image isn't bytes; key on a stable identity so a live
            # reconcile doesn't restart the movie every tick.
            return ("pil", getattr(value, "filename", "") or "",
                    getattr(value, "format", ""), tuple(value.size),
                    int(getattr(value, "n_frames", 1)))
        import hashlib

        b = _as_audio_bytes(value)
        if b is None:
            b = bytes(value)
        # FULL-buffer digest so an interior-only change invalidates the cache.
        # A head/tail summary collides on a fixed-length WAV (constant header)
        # or padded/looping PCM, showing a stale waveform / playing stale
        # audio. Mirrors watch._array_change_tag.
        return (len(b), hashlib.blake2b(b, digest_size=8).digest())
    except Exception:
        return (id(value),)


class MediaCell(QLabel):
    """Per-row overlay widget for an animated-GIF or interactive-waveform
    value cell. Installed via ``QTreeWidget.setItemWidget`` ONLY on media rows;
    static images + text stay on :class:`ImagePreviewDelegate`.

    * ``"movie"``    -- runs a QMovie (native animation) from in-memory GIF
      bytes (via a QBuffer), aspect-fit to the cell on resize.
    * ``"waveform"`` -- shows the waveform pixmap and, given a shared
      :class:`WaveformPlayer`, plays on click and scrubs on drag.
    """

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._mode = mode
        self._sig = None          # _value_sig of the bytes currently shown
        self._movie = None        # QMovie (movie mode) + GC anchor
        self._buffer = None       # QBuffer feeding the movie (GC anchor)
        self._bytes = None        # QByteArray backing the buffer (GC anchor)
        self._source = None       # waveform QPixmap (waveform mode)
        self._value = None        # raw audio bytes (waveform mode)
        self._rate = _DEFAULT_PCM_RATE
        self._player = None       # shared WaveformPlayer (waveform mode)
        self._dragging = False

    # -- movie mode -----------------------------------------------------
    def set_movie_bytes(self, data):
        self._stop_movie()
        try:
            # Parent both to this widget so Qt destroys them WITH the cell.
            # Children die in reverse creation order, so the movie (created
            # last) stops first, before its buffer. Python-ref-only objects
            # could instead free the buffer while the movie timer still reads
            # it -- a use-after-free crash at GC / interpreter shutdown.
            self._bytes = QByteArray(bytes(data))
            self._buffer = QBuffer(self._bytes)
            self._buffer.setParent(self)
            self._buffer.open(QBuffer.ReadOnly)
            mv = QMovie(self)
            mv.setDevice(self._buffer)
            try:
                mv.setCacheMode(QMovie.CacheAll)
            except Exception:
                pass
            self._movie = mv
            # QMovie.setScaledSize is nearest-neighbour and looks pixelated,
            # so keep the movie at native size and paint a smooth-scaled pixmap
            # per frame, matching the static-image delegate. Deliberately NOT
            # setMovie(), which would display at native size and fight us.
            mv.frameChanged.connect(self._on_movie_frame)
            mv.start()
            self._on_movie_frame()   # render frame 0 sharp up-front
        except Exception:
            self._stop_movie()

    def _on_movie_frame(self, *args):
        if self._movie is None:
            return
        try:
            pm = self._movie.currentPixmap()
            if pm is not None and not pm.isNull():
                self.setPixmap(pm.scaled(
                    self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def _fit_movie(self):
        # Re-render the current frame at the new cell size.
        self._on_movie_frame()

    def _stop_movie(self):
        if self._movie is not None:
            try:
                self._movie.stop()
            except Exception:
                pass
        self._movie = None
        if self._buffer is not None:
            try:
                self._buffer.close()
            except Exception:
                pass
        self._buffer = None
        self._bytes = None

    # -- waveform mode --------------------------------------------------
    def set_waveform(self, pixmap, value, player, rate: int = _DEFAULT_PCM_RATE):
        self._source = pixmap
        self._value = value
        self._player = player
        self._rate = rate
        try:
            self.setToolTip(_wave_caption(value))
        except Exception:
            pass
        self._fit_waveform()

    def _fit_waveform(self):
        if self._source is not None and not self._source.isNull():
            self.setPixmap(self._source.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # -- resize ---------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._mode == "movie":
            self._fit_movie()
        elif self._mode == "waveform":
            self._fit_waveform()

    # -- mouse (waveform: click = play, drag = scrub) -------------------
    def _fraction(self, event):
        try:
            x = event.position().x() if hasattr(event, "position") else event.x()
        except Exception:
            x = 0
        w = max(1, self.width())
        return max(0.0, min(1.0, float(x) / float(w)))

    def mousePressEvent(self, event):
        if (self._mode == "waveform" and self._player is not None
                and self._value is not None):
            try:
                left = event.button() == Qt.LeftButton
            except Exception:
                left = True
            if left:
                self._dragging = True
                try:
                    self._player.play(self._value, self._rate,
                                      self._fraction(event))
                except Exception:
                    pass
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._mode == "waveform" and self._dragging and self._player is not None:
            try:
                self._player.seek(self._fraction(event))
            except Exception:
                pass
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mode == "waveform" and self._dragging:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def cleanup(self):
        """Stop animation / release the GIF buffer. Called before the widget
        is replaced or removed so no timer/decoder lingers."""
        self._stop_movie()


class WaveformPlayer:
    """One reusable, un-muted audio player for a tab's waveform cells.

    Synthesizes a temp .wav from the (raw-PCM or WAV) bytes and plays it via
    ``qt_wrapper.make_audio_player`` (QMediaPlayer), supporting click-to-play
    + drag-to-scrub. Owns a single temp file + a single player at a time. A
    safe no-op when QtMultimedia is unavailable."""

    def __init__(self, parent=None):
        self._parent = parent
        self._player = None
        self._tmp_path = None
        self._cur_sig = None
        self._duration_ms = 0

    def _ensure_source(self, value, rate) -> bool:
        sig = _value_sig(value)
        if self._player is not None and sig == self._cur_sig:
            return True
        try:
            # Containers play verbatim with their real extension -- MP3 only
            # plays as ``.mp3``. Raw PCM is wrapped into a WAV.
            suffix, payload = _playable_audio_file(value, rate)
        except Exception:
            return False
        import tempfile

        self._stop_player()
        self._cleanup_tmp()
        path = None
        try:
            fd, path = tempfile.mkstemp(suffix=suffix, prefix="mpynode_wave_")
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
        except Exception:
            if path is not None:
                try:
                    os.remove(path)
                except Exception:
                    pass
            return False
        from mpynode.ui.qt_wrapper import make_audio_player

        player = make_audio_player(path, self._parent)
        if player is None:
            try:
                os.remove(path)
            except Exception:
                pass
            return False
        self._tmp_path = path
        self._player = player
        self._cur_sig = sig
        self._duration_ms = audio_duration_ms(value, rate)
        return True

    def play(self, value, rate: int = _DEFAULT_PCM_RATE,
             start_fraction: float = 0.0):
        if not self._ensure_source(value, rate):
            return
        try:
            self._player.setPosition(
                int(max(0.0, min(1.0, start_fraction)) * self._duration_ms))
            self._player.play()
        except Exception:
            pass

    def seek(self, fraction: float):
        if self._player is None:
            return
        try:
            self._player.setPosition(
                int(max(0.0, min(1.0, fraction)) * self._duration_ms))
            self._player.play()
        except Exception:
            pass

    def stop(self):
        self._stop_player()

    def _stop_player(self):
        # Stop AND release: the player is parented to the TAB widget, so just
        # dropping the Python ref accumulates stopped-but-undeleted
        # QMediaPlayers (and their QAudioOutputs) under it.
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
            try:
                self._player.deleteLater()
            except Exception:
                pass
            self._player = None

    def _cleanup_tmp(self):
        if self._tmp_path:
            try:
                os.remove(self._tmp_path)
            except Exception:
                pass
        self._tmp_path = None

    def dispose(self):
        self._stop_player()
        self._player = None
        self._cleanup_tmp()
        self._cur_sig = None


def _media_mode_for(item, col):
    """Return the per-row media widget mode for ``item`` -- ``"movie"`` for an
    animated GIF in image mode (animate pref on), ``"waveform"`` for a cell in
    waveform mode, else ``None`` (delegate handles it)."""
    try:
        if is_showing_waveform(item, col) and is_audio_item(item, col):
            return "waveform"
        if (bool(item.data(col, SHOW_IMAGE_ROLE)) and animate_gif_pref_on()
                and is_animated_gif_value(item.data(col, RAW_VALUE_ROLE))):
            return "movie"
    except Exception:
        pass
    return None


def refresh_media_widget(view, item, col, player=None) -> None:
    """Install / update / remove the per-row :class:`MediaCell` for ``item``
    at ``col`` based on its current view mode + the media prefs.

    ``view`` is the QTreeWidget; ``player`` is the tab's shared
    :class:`WaveformPlayer` (may be None). Idempotent + cheap on the live poll:
    an already-correct widget (same mode + same bytes) is left untouched so a
    GIF doesn't restart and a waveform isn't re-decoded every tick. Never
    raises -- it must not break a tab's row build."""
    try:
        want = _media_mode_for(item, col)
        existing = view.itemWidget(item, col)
        if want is None:
            if existing is not None:
                if isinstance(existing, MediaCell):
                    existing.cleanup()
                view.removeItemWidget(item, col)
            return
        value = item.data(col, RAW_VALUE_ROLE)
        sig = _value_sig(value)
        if (isinstance(existing, MediaCell) and existing._mode == want
                and existing._sig == sig):
            return  # already correct -- no rebuild
        if want == "movie":
            data = gif_movie_bytes(value)
            if not data:
                # No GIF frames: let the delegate paint the still pixmap
                # rather than install a broken movie cell.
                if isinstance(existing, MediaCell):
                    existing.cleanup()
                    view.removeItemWidget(item, col)
                return
        cell = MediaCell(want, view)
        cell._sig = sig
        if want == "movie":
            cell.set_movie_bytes(data)
        else:
            cell.set_waveform(item.data(col, PREVIEW_ROLE), value, player)
        if isinstance(existing, MediaCell):
            existing.cleanup()
        # setItemWidget deletes any previous widget and takes ownership.
        view.setItemWidget(item, col, cell)
    except Exception:
        pass


def cleanup_media_widgets(view, root=None) -> None:
    """Stop + remove every per-row :class:`MediaCell` overlay under ``root`` (a
    QTreeWidgetItem) -- or the whole ``view`` when ``root`` is None -- BEFORE
    the item/tree is cleared or the row removed.

    ``QTreeWidget.clear()`` / ``removeChild`` / ``takeTopLevelItem`` remove the
    item but do NOT destroy a widget installed via ``setItemWidget`` (it is
    reparented to the tree viewport and survives), so an animated-GIF cell's
    QMovie timer would keep firing on an orphaned widget. Calling ``cleanup()``
    (which stops the movie) and ``removeItemWidget`` first prevents that leak.
    Column-agnostic + idempotent; never raises (must not break a row teardown)."""
    try:
        cols = view.columnCount()
    except Exception:
        return

    def _walk(item):
        for c in range(cols):
            w = view.itemWidget(item, c)
            if isinstance(w, MediaCell):
                try:
                    w.cleanup()
                except Exception:
                    pass
                try:
                    view.removeItemWidget(item, c)
                except Exception:
                    pass
        for i in range(item.childCount()):
            _walk(item.child(i))

    try:
        if root is not None:
            _walk(root)
        else:
            for i in range(view.topLevelItemCount()):
                _walk(view.topLevelItem(i))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Delegate
# ---------------------------------------------------------------------------
class ImagePreviewDelegate(QStyledItemDelegate):
    """Value-column delegate: paints image rows as aspect-fit thumbnails
    (when in IMAGE mode) and defers every other row to the default
    delegate. ``view`` is the QTreeWidget; ``value_col`` is the column
    index that may hold previews (1 in Watch, 2 in Variables)."""

    def __init__(self, view, value_col: int, parent=None):
        super().__init__(parent or view)
        self._view = view
        self._col = int(value_col)
        try:
            view.header().sectionResized.connect(self._on_section_resized)
        except Exception:
            pass

    # -- live column-width tracking (relayout only; never resizes) ------
    def _on_section_resized(self, logical, _old, _new):
        if logical != self._col:
            return
        try:
            for idx in self._iter_image_indexes():
                self.sizeHintChanged.emit(idx)
        except Exception:
            pass

    def _iter_image_indexes(self):
        model = self._view.model()
        if model is None:
            return

        def walk(parent):
            for r in range(model.rowCount(parent)):
                idx0 = model.index(r, 0, parent)
                idxv = model.index(r, self._col, parent)
                if idxv.isValid() and (idxv.data(SHOW_IMAGE_ROLE)
                                       or idxv.data(SHOW_WAVEFORM_ROLE)) \
                        and idxv.data(PREVIEW_ROLE) is not None:
                    yield idxv
                if model.hasChildren(idx0):
                    yield from walk(idx0)

        yield from walk(self._view.rootIndex())

    # -- helpers --------------------------------------------------------
    def _image_pixmap(self, index):
        """The master pixmap iff this row is in IMAGE or WAVEFORM mode (both
        render an aspect-fit pixmap), else None."""
        if not (index.data(SHOW_IMAGE_ROLE) or index.data(SHOW_WAVEFORM_ROLE)):
            return None
        pm = index.data(PREVIEW_ROLE)
        if isinstance(pm, QPixmap) and not pm.isNull():
            return pm
        return None

    def _has_media_widget(self, index):
        """True iff a per-row MediaCell overlays this cell (animated GIF /
        interactive waveform). The widget renders the content, so the delegate
        must not also paint the static pixmap behind it."""
        try:
            it = self._view.itemFromIndex(index)
            return it is not None and self._view.itemWidget(it, self._col) is not None
        except Exception:
            return False

    def initStyleOption(self, option, index):
        # An image row renders a picture, not text. Blank the DisplayRole so
        # QStyledItemDelegate.paint() doesn't draw the value's repr behind it
        # -- that text used to peek out wherever the aspect-fit image didn't
        # cover the cell, e.g. during a column resize.
        super().initStyleOption(option, index)
        if self._has_media_widget(index) or self._image_pixmap(index) is not None:
            option.text = ""

    # -- editing: block the inline text editor on image-mode rows ------
    def createEditor(self, parent, option, index):
        if self._image_pixmap(index) is not None:
            return None
        return super().createEditor(parent, option, index)

    # -- aspect-fit row height: width == column width -------------------
    def sizeHint(self, option, index):
        pm = self._image_pixmap(index)
        if pm is None:
            return super().sizeHint(option, index)
        w = 0
        try:
            w = int(self._view.columnWidth(self._col))
        except Exception:
            w = 0
        if w <= 0:
            w = option.rect.width() or 128
        avail = max(1, w - 2 * _PAD)
        pw, ph = max(1, pm.width()), max(1, pm.height())
        h = int(round(avail * ph / float(pw))) + 2 * _PAD
        h = max(8, min(h, _MAX_EDGE))
        return QSize(w, h)

    # -- paint: Qt rescales the master to the cell each repaint ---------
    def paint(self, painter, option, index):
        pm = self._image_pixmap(index)
        if pm is None:
            super().paint(painter, option, index)
            return
        # A per-row media widget renders its own content, so paint only the
        # background/selection or the static master shows behind it.
        if self._has_media_widget(index):
            super().paint(painter, option, index)
            return
        # Background / selection first; the image then covers the cell.
        super().paint(painter, option, index)
        r = option.rect
        avail_w = max(1, r.width() - 2 * _PAD)
        avail_h = max(1, r.height() - 2 * _PAD)
        scaled = pm.scaled(
            avail_w, avail_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        # Top-left, so the row top lines up with the name in column 0.
        x = r.x() + _PAD
        y = r.y() + _PAD
        painter.drawPixmap(int(x), int(y), scaled)
