"""Media preview helpers: WAV/PCM detection, decode, waveform envelope +
render, and WAV synthesis for playback.

These back the Variables/Watch tab features: animate-GIF detection, detect a
WAV (or raw-PCM) byte stream and render it as a waveform, and synthesize a
temp .wav for click-to-play / drag-to-scrub audio.

The pure layers (sniff / decode / envelope / synth) are Maya- and Qt-free and
fully unit-tested here. ``render_waveform_pixmap`` touches Qt (QPixmap +
QPainter) so it runs under an offscreen QApplication and is skipped when Qt
is unavailable.
"""

from __future__ import annotations

import io
import os
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    from PIL import Image as _PIL_IMAGE
except Exception:  # pragma: no cover
    _PIL_IMAGE = None

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-media-test"])


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _make_wav(frame_bytes: bytes, rate: int = 22050, sampwidth: int = 1,
              nch: int = 1) -> bytes:
    """Build a real RIFF/WAVE container around raw frame bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(frame_bytes)
    return buf.getvalue()


# A 1x1 transparent GIF89a (smallest valid animated-capable GIF header).
_GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
# An ISO base-media (mp4) header: size, ``ftyp``, an isom brand, padding.
_MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00" + b"\x00" * 1500


def _real_png_bytes(w: int = 4, h: int = 3) -> bytes:
    """A PNG Qt can decode (the fixture above is a header only)."""
    from mpynode.ui.qt_wrapper import QBuffer, QByteArray, QImage

    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(0xFFFF0000)
    ba  = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba.data())


def _make_animated_gif_file():
    """Write a real multi-frame GIF to a temp file and return its path."""
    import tempfile

    frames = [_PIL_IMAGE.new("RGB", (8, 8), color=c)
              for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    fd, path = tempfile.mkstemp(suffix=".gif", prefix="mpynode_test_gif_")
    os.close(fd)
    frames[0].save(path, format="GIF", save_all=True,
                   append_images=frames[1:], duration=100, loop=0)
    return path


class TestAudioDetection(unittest.TestCase):
    def test_wav_sniff_true_for_real_wav(self):
        from mpynode.ui.widgets.image_preview import _looks_like_wav_bytes

        self.assertTrue(_looks_like_wav_bytes(_make_wav(bytes([0, 128, 255]))))

    def test_wav_sniff_false_for_non_wav(self):
        from mpynode.ui.widgets.image_preview import _looks_like_wav_bytes

        self.assertFalse(_looks_like_wav_bytes(_PNG_BYTES))
        self.assertFalse(_looks_like_wav_bytes(b"\x80" * 100))   # raw PCM
        self.assertFalse(_looks_like_wav_bytes(b"RIFF1234WEBP"))  # webp, not wav
        self.assertFalse(_looks_like_wav_bytes(b"abc"))           # too short
        self.assertFalse(_looks_like_wav_bytes("not bytes"))

    def test_audio_candidate(self):
        from mpynode.ui.widgets.image_preview import is_audio_candidate

        # a real WAV qualifies
        self.assertTrue(is_audio_candidate(_make_wav(bytes([1, 2, 3]))))
        # raw, non-image bytes (could be PCM) qualify -> manual "Show as Waveform"
        self.assertTrue(is_audio_candidate(b"\x80\x80\x81\x7f" * 10))
        # an image byte blob does NOT (it has "Show as Image" instead)
        self.assertFalse(is_audio_candidate(_PNG_BYTES))
        self.assertFalse(is_audio_candidate(_GIF_BYTES))
        # nor a video container (it gets a caption, no waveform toggle)
        self.assertFalse(is_audio_candidate(_MP4_BYTES))
        # non-bytes never
        self.assertFalse(is_audio_candidate("string"))
        self.assertFalse(is_audio_candidate(42))

    def test_gif_detection(self):
        from mpynode.ui.widgets.image_preview import is_gif_bytes

        self.assertTrue(is_gif_bytes(_GIF_BYTES))
        self.assertFalse(is_gif_bytes(_PNG_BYTES))
        self.assertFalse(is_gif_bytes("string"))

    def test_wav_is_not_an_image_kind(self):
        # a WAV routed into the image decoder yields a null pixmap, so
        # previewable_kind must see it as non-image.
        from mpynode.ui.widgets.image_preview import previewable_kind

        self.assertIsNone(previewable_kind(_make_wav(bytes([0, 128, 255]))))


@unittest.skipIf(np is None, "numpy unavailable")
class TestAudioDecode(unittest.TestCase):
    def test_decode_wav_uint8(self):
        from mpynode.ui.widgets.image_preview import decode_audio

        wav = _make_wav(bytes([0, 128, 255]), rate=8000)
        samples, rate = decode_audio(wav)
        self.assertEqual(rate, 8000)
        self.assertEqual(samples.shape[0], 3)
        # uint8 PCM centered at 128 -> [-1, 0, ~+1]
        self.assertAlmostEqual(float(samples[0]), -1.0, places=2)
        self.assertAlmostEqual(float(samples[1]), 0.0, places=2)
        self.assertGreater(float(samples[2]), 0.9)

    def test_decode_raw_pcm_uint8_default_rate(self):
        from mpynode.ui.widgets.image_preview import decode_audio

        samples, rate = decode_audio(bytes([0, 128, 255]))
        self.assertEqual(rate, 22050)  # default for headerless PCM
        self.assertEqual(samples.shape[0], 3)
        self.assertAlmostEqual(float(samples[1]), 0.0, places=2)

    def test_decode_wav_int16_stereo_mixes_to_mono(self):
        from mpynode.ui.widgets.image_preview import decode_audio

        # 2 stereo frames: L/R int16 little-endian.
        frames = np.array([[10000, -10000], [0, 0]], dtype="<i2").tobytes()
        wav = _make_wav(frames, rate=44100, sampwidth=2, nch=2)
        samples, rate = decode_audio(wav)
        self.assertEqual(rate, 44100)
        self.assertEqual(samples.shape[0], 2)         # mono mix, 2 frames
        self.assertAlmostEqual(float(samples[0]), 0.0, places=2)  # L+R cancel

    def test_waveform_envelope(self):
        from mpynode.ui.widgets.image_preview import waveform_envelope

        # ramp from -1 .. +1
        s = np.linspace(-1.0, 1.0, 1000).astype("float32")
        mins, maxs = waveform_envelope(s, 50)
        self.assertEqual(len(mins), 50)
        self.assertEqual(len(maxs), 50)
        self.assertTrue((maxs >= mins).all())
        self.assertAlmostEqual(float(mins[0]), -1.0, places=1)
        self.assertAlmostEqual(float(maxs[-1]), 1.0, places=1)

    def test_waveform_envelope_empty_is_safe(self):
        from mpynode.ui.widgets.image_preview import waveform_envelope

        mins, maxs = waveform_envelope(np.array([], dtype="float32"), 10)
        self.assertEqual(len(mins), 0)
        self.assertEqual(len(maxs), 0)


@unittest.skipIf(np is None, "numpy unavailable")
class TestWavSynthesis(unittest.TestCase):
    def test_synthesize_from_raw_pcm(self):
        from mpynode.ui.widgets.image_preview import synthesize_wav_bytes

        pcm = bytes([0, 64, 128, 192, 255])
        out = synthesize_wav_bytes(pcm, rate=22050)
        with wave.open(io.BytesIO(out), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 1)
            self.assertEqual(w.getframerate(), 22050)
            self.assertEqual(w.getnframes(), len(pcm))
            self.assertEqual(w.readframes(len(pcm)), pcm)

    def test_synthesize_passes_through_real_wav(self):
        from mpynode.ui.widgets.image_preview import synthesize_wav_bytes

        wav = _make_wav(bytes([1, 2, 3, 4]), rate=16000)
        out = synthesize_wav_bytes(wav)
        # already a container -> returned playable as-is
        self.assertEqual(bytes(out[:4]), b"RIFF")
        with wave.open(io.BytesIO(out), "rb") as w:
            self.assertEqual(w.getframerate(), 16000)


# Synthetic compressed-audio blobs: magic bytes only. The content need not
# decode; what matters is container recognition and that a compressed blob
# never falls through to the uint8 raw-PCM path.
_MP3_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64 + b"\xff\xfb\x90\x00"
_MP3_SYNC = b"\xff\xfb\x90\x00" + b"\x00" * 64
_OGG = b"OggS\x00\x02" + b"\x00" * 64
_FLAC = b"fLaC\x00\x00\x00\x22" + b"\x00" * 64
_AIFF = b"FORM\x00\x00\x00\x20AIFF" + b"\x00" * 32
_M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00" + b"\x00" * 32


class TestCompressedAudioDetection(unittest.TestCase):
    def test_container_kind_recognizes_compressed_formats(self):
        from mpynode.ui.widgets.image_preview import _audio_container_kind

        self.assertEqual(_audio_container_kind(_MP3_ID3), "MP3")
        self.assertEqual(_audio_container_kind(_MP3_SYNC), "MP3")
        self.assertEqual(_audio_container_kind(_OGG), "OGG")
        self.assertEqual(_audio_container_kind(_FLAC), "FLAC")
        self.assertEqual(_audio_container_kind(_AIFF), "AIFF")
        self.assertEqual(_audio_container_kind(_M4A), "M4A")
        # WAV is still recognized (as its own kind), raw PCM is not a container
        self.assertEqual(_audio_container_kind(_make_wav(bytes([1, 2, 3]))), "WAV")
        self.assertIsNone(_audio_container_kind(b"\x80\x80\x81" * 10))
        self.assertIsNone(_audio_container_kind("not bytes"))

    def test_compressed_kind_excludes_wav_and_pcm(self):
        from mpynode.ui.widgets.image_preview import _compressed_audio_kind

        self.assertEqual(_compressed_audio_kind(_MP3_ID3), "MP3")
        self.assertEqual(_compressed_audio_kind(_OGG), "OGG")
        # WAV and raw PCM decode natively -> not "compressed" (no QAudioDecoder)
        self.assertIsNone(_compressed_audio_kind(_make_wav(bytes([1, 2, 3]))))
        self.assertIsNone(_compressed_audio_kind(b"\x80\x80\x81" * 10))

    def test_compressed_audio_is_a_candidate(self):
        from mpynode.ui.widgets.image_preview import is_audio_candidate

        self.assertTrue(is_audio_candidate(_MP3_ID3))
        self.assertTrue(is_audio_candidate(_OGG))

    def test_playable_file_uses_real_extension(self):
        from mpynode.ui.widgets.image_preview import _playable_audio_file

        # a compressed blob plays back verbatim with its real extension
        sfx, payload = _playable_audio_file(_MP3_ID3)
        self.assertEqual(sfx, ".mp3")
        self.assertEqual(payload, _MP3_ID3)
        sfx, payload = _playable_audio_file(_OGG)
        self.assertEqual(sfx, ".ogg")
        # WAV verbatim as .wav
        wav = _make_wav(bytes([1, 2, 3]))
        sfx, payload = _playable_audio_file(wav)
        self.assertEqual(sfx, ".wav")
        self.assertEqual(payload, wav)
        # raw PCM wrapped into a .wav container
        sfx, _ = _playable_audio_file(b"\x80\x80\x81" * 4)
        self.assertEqual(sfx, ".wav")

    def test_caption_labels_the_container(self):
        from mpynode.ui.widgets.image_preview import _wave_caption

        self.assertTrue(_wave_caption(_MP3_ID3).startswith("MP3"))
        self.assertTrue(_wave_caption(_make_wav(bytes([1, 2, 3]))).startswith("WAV"))


@unittest.skipIf(np is None, "numpy unavailable")
class TestCompressedAudioDecode(unittest.TestCase):
    def test_compressed_blob_never_falls_through_to_raw_pcm(self):
        # the ouch/ugh.mp3 bug: an MP3 read as uint8 PCM yields exactly
        # len(bytes) samples of noise. With or without QAudioDecoder the
        # result must be a float32 array whose length differs from the
        # compressed byte count.
        from mpynode.ui.widgets.image_preview import decode_audio

        for blob in (_MP3_ID3, _OGG, _FLAC):
            samples, _rate = decode_audio(blob)
            self.assertEqual(samples.dtype, np.dtype("float32"))
            self.assertNotEqual(samples.size, len(blob))


@unittest.skipIf(np is None, "numpy unavailable")
@unittest.skipIf(_QAPP is None, "Qt unavailable")
class TestWaveformRender(unittest.TestCase):
    def test_render_waveform_pixmap_non_null(self):
        from mpynode.ui.widgets.image_preview import render_waveform_pixmap

        wav = _make_wav(bytes(list(range(256)) * 4), rate=22050)
        pm = render_waveform_pixmap(wav, 200, 60)
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())
        self.assertEqual(pm.width(), 200)
        self.assertEqual(pm.height(), 60)

    def test_render_waveform_pixmap_raw_pcm(self):
        from mpynode.ui.widgets.image_preview import render_waveform_pixmap

        pcm = bytes(list(range(256)) * 8)
        pm = render_waveform_pixmap(pcm, 128, 32)
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())


@unittest.skipIf(np is None, "numpy unavailable")
@unittest.skipIf(_QAPP is None, "Qt unavailable")
def _drain_qt(trees):
    """Delete created trees (and their item widgets / movies) deterministically
    so no Qt object leaks into the rest of the discover run (a leaked QMovie
    timer / orphaned QBuffer can crash PySide6 at GC / interpreter shutdown).
    Uses shiboken's immediate delete rather than deleteLater + processEvents:
    QApplication.processEvents() is unreliable in headless mayapy on Qt6 (the
    first call after standalone.initialize() can spin / block indefinitely)."""
    from mpynode.ui.widgets.image_preview import cleanup_media_widgets
    try:
        from shiboken6 import delete as _qt_delete
    except Exception:
        try:
            from shiboken2 import delete as _qt_delete
        except Exception:
            _qt_delete = None
    for t in trees:
        try:
            cleanup_media_widgets(t)
            t.clear()
            t.setParent(None)
            if _qt_delete is not None:
                _qt_delete(t)
            else:
                t.deleteLater()
        except Exception:
            pass


class TestViewModeWiring(unittest.TestCase):
    """attach_value / set_waveform_view view-mode plumbing on a real tree item
    (Qt only -- no Maya, no audio device)."""

    def setUp(self):
        self._trees = []

    def tearDown(self):
        _drain_qt(self._trees)

    def _item(self):
        from mpynode.ui.qt_wrapper import QTreeWidget, QTreeWidgetItem

        tree = QTreeWidget()
        tree.setColumnCount(2)
        item = QTreeWidgetItem(tree)
        self._trees.append(tree)
        return tree, item

    def test_wav_auto_defaults_to_waveform_when_pref_on(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_render_waveform", True)
        try:
            tree, item = self._item()
            ip.attach_value(item, 1, _make_wav(bytes([0, 128, 255] * 50)), "wav")
            self.assertTrue(ip.is_audio_item(item, 1))
            self.assertTrue(ip.is_showing_waveform(item, 1))
            self.assertIsNotNone(item.data(1, ip.PREVIEW_ROLE))
        finally:
            preferences.set_pref("variables_render_waveform", True)

    def test_raw_pcm_defaults_to_source_but_is_audio(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._item()
        ip.attach_value(item, 1, b"\x80\x81\x7f" * 40, "pcm")
        self.assertTrue(ip.is_audio_item(item, 1))
        self.assertFalse(ip.is_showing_waveform(item, 1))  # manual opt-in

    def test_manual_waveform_toggle_roundtrip(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._item()
        ip.attach_value(item, 1, b"\x80\x90\x70" * 40, "pcm")
        self.assertTrue(ip.toggle_waveform_view(item, 1))   # -> waveform
        self.assertTrue(ip.is_showing_waveform(item, 1))
        self.assertFalse(ip.toggle_waveform_view(item, 1))  # -> source
        self.assertFalse(ip.is_showing_waveform(item, 1))

    def test_image_bytes_are_not_audio(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._item()
        ip.attach_value(item, 1, _GIF_BYTES, "gif")
        self.assertTrue(ip.is_previewable_item(item, 1))
        self.assertFalse(ip.is_audio_item(item, 1))

    def test_image_bytes_default_to_the_picture(self):
        # The magic number is not ambiguous: a PNG blob (say, a persistent
        # variable loaded from an .mpn) shows as the picture, the way a PIL
        # image does. It used to default to SOURCE -- a byte dump.
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._item()
        png = _real_png_bytes()
        self.assertEqual(ip.previewable_kind(png), "bytes")
        ip.attach_value(item, 1, png, "b'...'")
        self.assertTrue(ip.is_showing_image(item, 1))
        pm = item.data(1, ip.PREVIEW_ROLE)
        self.assertIsNotNone(pm)
        self.assertFalse(pm.isNull())
        # The toggle still goes back to source and is honoured.
        self.assertFalse(ip.toggle_value_mode(item, 1))
        self.assertFalse(ip.is_showing_image(item, 1))

    def test_undecodable_image_bytes_fall_back_to_source(self):
        # A header with nothing behind it: previewable by signature, but Qt
        # cannot decode it, so the honest view is the bytes.
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._item()
        ip.attach_value(item, 1, _PNG_BYTES, "b'...'")
        self.assertTrue(ip.is_previewable_item(item, 1))
        self.assertFalse(ip.is_showing_image(item, 1))

    def test_video_bytes_show_a_caption_not_a_dump(self):
        from mpynode.ui.widgets import image_preview as ip

        self.assertEqual(ip._video_container_kind(_MP4_BYTES), "mp4")
        self.assertEqual(ip._video_container_kind(
            b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 8), "mov")
        self.assertEqual(ip._video_container_kind(
            b"\x1a\x45\xdf\xa3" + b"\x00" * 12), "webm")
        self.assertIsNone(ip._video_container_kind(_PNG_BYTES))
        # An audio-only M4A brand is audio, not video.
        self.assertIsNone(ip._video_container_kind(
            b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 8))
        tree, item = self._item()
        ip.attach_value(item, 1, _MP4_BYTES, repr(_MP4_BYTES))
        self.assertTrue(item.text(1).startswith("mp4 video \u00b7 "))
        self.assertIn("KB", item.text(1))
        self.assertFalse(ip.is_previewable_item(item, 1))
        self.assertFalse(ip.is_audio_item(item, 1))
        self.assertIn("no inline player", item.toolTip(1))

    def test_legacy_pcm_str_manual_waveform_toggle(self):
        # legacy bytes-as-str raw PCM behaves like raw-PCM bytes.
        from mpynode.ui.widgets import image_preview as ip

        pcm_str = (bytes([128] * 40 + list(range(256)) * 4 + [128] * 40)
                   .decode("latin-1"))
        tree, item = self._item()
        ip.attach_value(item, 1, pcm_str, "pcm")
        self.assertTrue(ip.is_audio_item(item, 1))
        self.assertFalse(ip.is_showing_waveform(item, 1))    # manual opt-in
        self.assertTrue(ip.toggle_waveform_view(item, 1))    # -> waveform
        self.assertTrue(ip.is_showing_waveform(item, 1))
        self.assertFalse(ip.toggle_waveform_view(item, 1))   # -> source

    def test_wav_as_str_auto_defaults_to_waveform_when_pref_on(self):
        # a legacy WAV stored as a bytes-as-str auto-renders just like WAV bytes.
        from mpynode.ui import preferences
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_render_waveform", True)
        try:
            wav_str = _make_wav(bytes([0, 128, 255] * 50)).decode("latin-1")
            tree, item = self._item()
            ip.attach_value(item, 1, wav_str, "wav")
            self.assertTrue(ip.is_audio_item(item, 1))
            self.assertTrue(ip.is_showing_waveform(item, 1))
        finally:
            preferences.set_pref("variables_render_waveform", True)


@unittest.skipIf(np is None, "numpy unavailable")
@unittest.skipIf(_QAPP is None, "Qt unavailable")
class TestMediaWidgetInstall(unittest.TestCase):
    """refresh_media_widget installs/removes a per-row MediaCell on a real
    QTreeWidget (Qt only)."""

    def setUp(self):
        self._trees = []

    def tearDown(self):
        _drain_qt(self._trees)

    def _tree_item(self):
        from mpynode.ui.qt_wrapper import QTreeWidget, QTreeWidgetItem

        tree = QTreeWidget()
        tree.setColumnCount(2)
        self._trees.append(tree)
        return tree, QTreeWidgetItem(tree)

    def test_waveform_row_gets_media_cell(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._tree_item()
        ip.attach_value(item, 1, b"\x80\x90\x70\x60" * 40, "pcm")
        ip.set_waveform_view(item, 1, True)
        ip.refresh_media_widget(tree, item, 1, ip.WaveformPlayer(tree))
        w = tree.itemWidget(item, 1)
        self.assertIsInstance(w, ip.MediaCell)
        self.assertEqual(w._mode, "waveform")

    def test_widget_removed_when_back_to_source(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._tree_item()
        ip.attach_value(item, 1, b"\x80\x90\x70\x60" * 40, "pcm")
        ip.set_waveform_view(item, 1, True)
        ip.refresh_media_widget(tree, item, 1, ip.WaveformPlayer(tree))
        self.assertIsNotNone(tree.itemWidget(item, 1))
        ip.set_waveform_view(item, 1, False)
        ip.refresh_media_widget(tree, item, 1, None)
        self.assertIsNone(tree.itemWidget(item, 1))

    def test_gif_image_mode_animates_when_pref_on(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_animate_gif", True)
        try:
            tree, item = self._tree_item()
            ip.attach_value(item, 1, _GIF_BYTES, "gif")
            ip.set_image_view(item, 1, True)   # opt the gif into IMAGE view
            ip.refresh_media_widget(tree, item, 1, None)
            w = tree.itemWidget(item, 1)
            self.assertIsInstance(w, ip.MediaCell)
            self.assertEqual(w._mode, "movie")
        finally:
            preferences.set_pref("variables_animate_gif", True)

    def test_gif_no_movie_when_animate_pref_off(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_animate_gif", False)
        try:
            tree, item = self._tree_item()
            ip.attach_value(item, 1, _GIF_BYTES, "gif")
            ip.set_image_view(item, 1, True)
            ip.refresh_media_widget(tree, item, 1, None)
            self.assertIsNone(tree.itemWidget(item, 1))  # static -> delegate
        finally:
            preferences.set_pref("variables_animate_gif", True)

    def test_install_is_idempotent_same_bytes(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._tree_item()
        ip.attach_value(item, 1, b"\x80\x90\x70\x60" * 40, "pcm")
        ip.set_waveform_view(item, 1, True)
        player = ip.WaveformPlayer(tree)
        ip.refresh_media_widget(tree, item, 1, player)
        w1 = tree.itemWidget(item, 1)
        ip.refresh_media_widget(tree, item, 1, player)
        w2 = tree.itemWidget(item, 1)
        self.assertIs(w1, w2)  # not rebuilt -> no flicker / GIF restart

    def test_media_mode_for_plain_value_is_none(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._tree_item()
        ip.attach_value(item, 1, 42, repr(42))  # not media
        self.assertIsNone(ip._media_mode_for(item, 1))


class TestDelegateTextSuppression(unittest.TestCase):
    """A media-widget row (animated GIF / interactive waveform) must NOT also
    paint the value's repr text behind the overlay -- resizing the column used
    to reveal the class repr (e.g. '<PIL.GifImagePlugin.GifImageFile ...>')
    peeking out where the aspect-fit widget didn't cover the cell."""

    def setUp(self):
        self._trees = []

    def tearDown(self):
        _drain_qt(self._trees)

    def _delegate_and_index(self):
        from mpynode.ui import preferences
        from mpynode.ui.qt_wrapper import QTreeWidget, QTreeWidgetItem
        from mpynode.ui.widgets import image_preview as ip

        tree = QTreeWidget()
        tree.setColumnCount(2)
        self._trees.append(tree)
        item = QTreeWidgetItem(tree)
        item.setText(1, "<PIL.GifImagePlugin.GifImageFile ...>")  # the repr
        ip.attach_value(item, 1, _GIF_BYTES, "gif")
        ip.set_image_view(item, 1, True)
        preferences.set_pref("variables_animate_gif", True)
        ip.refresh_media_widget(tree, item, 1, None)   # installs MediaCell
        self.assertIsNotNone(tree.itemWidget(item, 1))  # guard: overlay present
        delegate = ip.ImagePreviewDelegate(tree, 1)
        index = tree.indexFromItem(item, 1)
        return delegate, index

    def test_media_row_blanks_display_text(self):
        try:
            from PySide6.QtWidgets import QStyleOptionViewItem
        except Exception:
            from PySide2.QtWidgets import QStyleOptionViewItem

        delegate, index = self._delegate_and_index()
        opt = QStyleOptionViewItem()
        delegate.initStyleOption(opt, index)
        self.assertEqual(
            opt.text, "",
            "media row still carries DisplayRole text: %r" % (opt.text,))

    def test_static_image_row_blanks_display_text(self):
        # a static image is delegate-painted with no MediaCell overlay, so its
        # repr text must be blanked too, else it peeks on a column resize the
        # way the GIF did.
        try:
            from PySide6.QtWidgets import QStyleOptionViewItem
        except Exception:
            from PySide2.QtWidgets import QStyleOptionViewItem
        from mpynode.ui.qt_wrapper import QPixmap, Qt, QTreeWidget, QTreeWidgetItem
        from mpynode.ui.widgets import image_preview as ip

        tree = QTreeWidget()
        tree.setColumnCount(2)
        self._trees.append(tree)
        item = QTreeWidgetItem(tree)
        item.setText(1, "<PIL.JpegImagePlugin.JpegImageFile ...>")  # the repr
        pm = QPixmap(32, 24)
        pm.fill(Qt.red)
        item.setData(1, ip.PREVIEW_ROLE, pm)        # static master pixmap
        item.setData(1, ip.SHOW_IMAGE_ROLE, True)   # IMAGE view, delegate-painted
        self.assertIsNone(tree.itemWidget(item, 1))   # static -> no overlay widget
        delegate = ip.ImagePreviewDelegate(tree, 1)
        index = tree.indexFromItem(item, 1)
        self.assertIsNotNone(delegate._image_pixmap(index))  # guard: pixmap present
        opt = QStyleOptionViewItem()
        delegate.initStyleOption(opt, index)
        self.assertEqual(
            opt.text, "",
            "static image row still carries DisplayRole text: %r" % (opt.text,))


# ---------------------------------------------------------------------------
# Adversarial-review remediation: playback wiring, leaks, decode correctness
# ---------------------------------------------------------------------------
def _wave_temps():
    """Set of leftover synthesized temp .wav files in the temp dir."""
    import glob
    import tempfile

    return set(glob.glob(os.path.join(tempfile.gettempdir(),
                                      "mpynode_wave_*.wav")))


class _FakePlayer:
    """Stand-in for the QMediaPlayer make_audio_player returns, so the player
    lifecycle can be exercised with no QtMultimedia / audio device."""

    def __init__(self):
        self.stopped = 0
        self.deleted = 0
        self.played = 0
        self.position = None

    def setPosition(self, ms):
        self.position = int(ms)

    def play(self):
        self.played += 1

    def stop(self):
        self.stopped += 1

    def deleteLater(self):
        self.deleted += 1


def _pack_int24_le(samples):
    """Pack signed ints into little-endian 24-bit frames for a 24-bit WAV."""
    out = bytearray()
    for s in samples:
        s = int(s) & 0xFFFFFF
        out += bytes((s & 0xFF, (s >> 8) & 0xFF, (s >> 16) & 0xFF))
    return bytes(out)


class TestPlaybackImportAndPath(unittest.TestCase):
    """Regression guard for the missing `import os` that made click-to-play a
    silent no-op + leaked a temp .wav on every click."""

    def test_module_imports_os(self):
        from mpynode.ui.widgets import image_preview as ip

        self.assertTrue(
            hasattr(ip, "os"),
            "image_preview must import os (WaveformPlayer uses os.fdopen/remove)")

    def test_play_builds_player_and_writes_temp(self):
        from mpynode.ui import qt_wrapper
        from mpynode.ui.widgets import image_preview as ip

        if not qt_wrapper.HAS_QT_MULTIMEDIA:
            self.skipTest("QtMultimedia unavailable")
        wp = ip.WaveformPlayer(None)
        try:
            wp.play(_make_wav(bytes([0, 64, 128, 192, 255]) * 50), 22050, 0.0)
            self.assertIsNotNone(wp._player)        # os path reached
            self.assertIsNotNone(wp._tmp_path)
            self.assertTrue(os.path.exists(wp._tmp_path))
        finally:
            wp.dispose()


class TestPlaybackGracefulDegradation(unittest.TestCase):
    """Playback degrades to render-only (no crash, no leak) when QtMultimedia
    is absent OR a player can't be constructed (no audio backend)."""

    def test_make_audio_player_none_when_multimedia_absent(self):
        from mpynode.ui import qt_wrapper

        orig = qt_wrapper.HAS_QT_MULTIMEDIA
        qt_wrapper.HAS_QT_MULTIMEDIA = False
        try:
            self.assertIsNone(qt_wrapper.make_audio_player("/tmp/none.wav"))
        finally:
            qt_wrapper.HAS_QT_MULTIMEDIA = orig

    def test_make_audio_player_none_when_construction_fails(self):
        from mpynode.ui import qt_wrapper

        if not qt_wrapper.HAS_QT_MULTIMEDIA:
            self.skipTest("QtMultimedia unavailable")

        def _boom(*a, **k):
            raise RuntimeError("no audio backend")

        orig = qt_wrapper.QMediaPlayer
        qt_wrapper.QMediaPlayer = _boom
        try:
            self.assertIsNone(qt_wrapper.make_audio_player("/tmp/none.wav"))
        finally:
            qt_wrapper.QMediaPlayer = orig

    def test_make_audio_player_releases_half_built_player_on_failure(self):
        # when QAudioOutput()/setSource raises after the player object exists
        # (the real no-backend case), the half-built Qt-parented player must
        # be deleteLater'd, not leaked under the tab.
        from mpynode.ui import qt_wrapper

        if not qt_wrapper.HAS_QT_MULTIMEDIA:
            self.skipTest("QtMultimedia unavailable")

        deleted = []

        class _FakeQMP:
            def __init__(self, parent=None):
                self._parent = parent

            def deleteLater(self):
                deleted.append(1)

        class _FakeQUrl:
            @staticmethod
            def fromLocalFile(p):
                raise RuntimeError("url fail after player built")

        orig_qmp = qt_wrapper.QMediaPlayer
        orig_url = qt_wrapper.QUrl
        qt_wrapper.QMediaPlayer = _FakeQMP
        qt_wrapper.QUrl = _FakeQUrl
        try:
            self.assertIsNone(qt_wrapper.make_audio_player("/tmp/none.wav"))
            self.assertEqual(len(deleted), 1)   # half-built player released
        finally:
            qt_wrapper.QMediaPlayer = orig_qmp
            qt_wrapper.QUrl = orig_url

    def test_play_noop_and_no_temp_leak_when_backend_fails(self):
        from mpynode.ui import qt_wrapper
        from mpynode.ui.widgets import image_preview as ip

        if not qt_wrapper.HAS_QT_MULTIMEDIA:
            self.skipTest("QtMultimedia unavailable")

        def _boom(*a, **k):
            raise RuntimeError("no audio backend")

        before = _wave_temps()
        orig = qt_wrapper.QMediaPlayer
        qt_wrapper.QMediaPlayer = _boom
        wp = ip.WaveformPlayer(None)
        try:
            wp.play(_make_wav(bytes([0, 128, 255]) * 50), 22050, 0.0)  # no raise
            self.assertIsNone(wp._player)
            self.assertIsNone(wp._tmp_path)
            self.assertEqual(_wave_temps() - before, set())   # no leaked temp
        finally:
            qt_wrapper.QMediaPlayer = orig
            wp.dispose()


class TestPlayerLifecycle(unittest.TestCase):
    """Superseded players are stopped AND released; dispose frees player+temp.
    Uses a fake player so no QtMultimedia / audio device is needed (but the
    real os/tempfile path runs, so it also guards the missing-import bug)."""

    def _played_wp(self, value):
        from mpynode.ui import qt_wrapper
        from mpynode.ui.widgets import image_preview as ip

        made = []

        def _fake(path, parent=None):
            p = _FakePlayer()
            made.append((p, path))
            return p

        orig = qt_wrapper.make_audio_player
        qt_wrapper.make_audio_player = _fake
        self.addCleanup(setattr, qt_wrapper, "make_audio_player", orig)
        wp = ip.WaveformPlayer(None)
        wp.play(value, 22050, 0.0)
        return wp, made

    def test_stop_player_releases_and_nulls(self):
        wp, made = self._played_wp(_make_wav(bytes([0, 128, 255]) * 40))
        self.assertEqual(len(made), 1)            # os path reached, player built
        player = made[0][0]
        self.assertIsNotNone(wp._player)
        wp._stop_player()
        self.assertGreaterEqual(player.stopped, 1)
        self.assertGreaterEqual(player.deleted, 1)   # deleteLater'd, not orphaned
        self.assertIsNone(wp._player)
        wp.dispose()

    def test_signature_change_releases_old_player(self):
        wp, made = self._played_wp(_make_wav(bytes([0, 128, 255]) * 40))
        old = made[0][0]
        wp.play(_make_wav(bytes([10, 90, 200]) * 40), 22050, 0.0)  # new sig
        self.assertEqual(len(made), 2)
        self.assertGreaterEqual(old.deleted, 1)      # superseded -> released
        self.assertIsNot(wp._player, old)
        wp.dispose()

    def test_dispose_releases_player_and_temp(self):
        wp, made = self._played_wp(_make_wav(bytes([0, 128, 255]) * 40))
        player = made[0][0]
        tmp = wp._tmp_path
        self.assertTrue(tmp and os.path.exists(tmp))
        wp.dispose()
        self.assertGreaterEqual(player.stopped, 1)
        self.assertIsNone(wp._player)
        self.assertFalse(os.path.exists(tmp))        # temp removed


@unittest.skipIf(_QAPP is None, "Qt unavailable")
class TestMediaCleanupHelper(unittest.TestCase):
    """cleanup_media_widgets stops + removes per-row MediaCell overlays before a
    tree clear / row removal, so animated-GIF QMovie timers aren't orphaned on
    widgets that QTreeWidget.clear()/removeChild leave alive on the viewport."""

    def setUp(self):
        self._trees = []

    def tearDown(self):
        _drain_qt(self._trees)

    def _movie_row(self):
        from mpynode.ui import preferences
        from mpynode.ui.qt_wrapper import QTreeWidget, QTreeWidgetItem
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_animate_gif", True)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        self._trees.append(tree)
        item = QTreeWidgetItem(tree)
        ip.attach_value(item, 1, _GIF_BYTES, "gif")
        ip.set_image_view(item, 1, True)
        ip.refresh_media_widget(tree, item, 1, None)
        return tree, item

    def test_helper_exists(self):
        from mpynode.ui.widgets import image_preview as ip

        self.assertTrue(hasattr(ip, "cleanup_media_widgets"))

    def test_helper_stops_movie_and_removes_widget(self):
        from mpynode.ui.widgets import image_preview as ip

        tree, item = self._movie_row()
        cell = tree.itemWidget(item, 1)
        self.assertIsInstance(cell, ip.MediaCell)
        self.assertEqual(cell._mode, "movie")
        self.assertIsNotNone(cell._movie)             # running
        ip.cleanup_media_widgets(tree)
        self.assertIsNone(cell._movie)                # stopped via cleanup()
        self.assertIsNone(tree.itemWidget(item, 1))   # widget removed

    def test_helper_walks_subtree_root(self):
        from mpynode.ui.qt_wrapper import QTreeWidgetItem
        from mpynode.ui.widgets import image_preview as ip

        tree, parent = self._movie_row()              # top-level item
        child = QTreeWidgetItem(parent)
        ip.attach_value(child, 1, _GIF_BYTES, "gif")
        ip.set_image_view(child, 1, True)
        ip.refresh_media_widget(tree, child, 1, None)
        ccell = tree.itemWidget(child, 1)
        self.assertIsInstance(ccell, ip.MediaCell)
        ip.cleanup_media_widgets(tree, parent)        # root-scoped walk
        self.assertIsNone(ccell._movie)
        self.assertIsNone(tree.itemWidget(child, 1))


class TestValueSigInterior(unittest.TestCase):
    """_value_sig must detect interior-only byte changes (same len + head/tail)
    so a live cell doesn't show a stale waveform / play stale audio."""

    def test_detects_interior_change(self):
        from mpynode.ui.widgets.image_preview import _value_sig

        head = b"\x00" * 16
        tail = b"\xff" * 16
        a = head + (b"\x01" * 100) + tail
        b = head + (b"\x02" * 100) + tail   # same len, same head/tail
        self.assertNotEqual(_value_sig(a), _value_sig(b))

    def test_stable_for_same_bytes(self):
        from mpynode.ui.widgets.image_preview import _value_sig

        v = b"\x10\x20\x30" * 50
        self.assertEqual(_value_sig(v), _value_sig(bytes(v)))


@unittest.skipIf(np is None, "numpy unavailable")
class TestDecodeBitDepths(unittest.TestCase):
    """decode_audio handles 24-bit WAVs (sampwidth==3) with sane amplitude
    rather than reinterpreting them as raw uint8 garbage."""

    def test_decode_24bit_wav_sane_amplitude(self):
        from mpynode.ui.widgets.image_preview import decode_audio

        frames = _pack_int24_le([0x7FFFFF, -0x800000, 0, 0x400000])
        wav = _make_wav(frames, rate=22050, sampwidth=3, nch=1)
        samples, rate = decode_audio(wav)
        self.assertEqual(rate, 22050)
        self.assertGreater(samples.size, 0)
        self.assertLessEqual(float(samples.max()), 1.0 + 1e-6)
        self.assertGreaterEqual(float(samples.min()), -1.0 - 1e-6)
        # +/- full scale ~ +/-1.0 (NOT the >1 uint8 garbage the old branch gave)
        self.assertAlmostEqual(float(samples.max()), 1.0, places=2)
        self.assertAlmostEqual(float(samples.min()), -1.0, places=2)

    def test_decode_16bit_still_correct(self):
        import struct

        from mpynode.ui.widgets.image_preview import decode_audio

        frames = struct.pack("<4h", 0, 32767, -32768, 16384)
        wav = _make_wav(frames, rate=8000, sampwidth=2, nch=1)
        samples, rate = decode_audio(wav)
        self.assertEqual(rate, 8000)
        self.assertAlmostEqual(float(samples.max()), 1.0, places=2)
        self.assertAlmostEqual(float(samples.min()), -1.0, places=2)


@unittest.skipIf(_PIL_IMAGE is None, "PIL unavailable")
class TestAnimatedGifDetection(unittest.TestCase):
    """A PIL Image from Image.open('x.gif') is an animated-GIF source too, not
    just raw GIF bytes -- it must take the QMovie animation path."""

    def test_is_animated_gif_value_bytes(self):
        from mpynode.ui.widgets.image_preview import is_animated_gif_value

        self.assertTrue(is_animated_gif_value(_GIF_BYTES))

    def test_is_animated_gif_value_pil(self):
        from mpynode.ui.widgets.image_preview import is_animated_gif_value

        path = _make_animated_gif_file()
        # Image.open is lazy and holds the file handle; Windows refuses to
        # remove an open file, so close before unlinking.
        img = _PIL_IMAGE.open(path)
        try:
            self.assertTrue(is_animated_gif_value(img))
        finally:
            img.close()
            os.remove(path)

    def test_is_animated_gif_value_false_for_static(self):
        from mpynode.ui.widgets.image_preview import is_animated_gif_value

        self.assertFalse(is_animated_gif_value(_PNG_BYTES))
        self.assertFalse(is_animated_gif_value("not an image"))
        self.assertFalse(is_animated_gif_value(_PIL_IMAGE.new("RGB", (4, 4))))

    def test_gif_movie_bytes_from_pil(self):
        from mpynode.ui.widgets.image_preview import gif_movie_bytes

        path = _make_animated_gif_file()
        # Image.open is lazy and holds the file handle; Windows refuses to
        # remove an open file, so close before unlinking.
        img = _PIL_IMAGE.open(path)
        try:
            data = gif_movie_bytes(img)
            self.assertIsNotNone(data)
            self.assertIn(bytes(data[:6]), (b"GIF87a", b"GIF89a"))
        finally:
            img.close()
            os.remove(path)

    def test_gif_movie_bytes_passthrough_bytes(self):
        from mpynode.ui.widgets.image_preview import gif_movie_bytes

        self.assertEqual(bytes(gif_movie_bytes(_GIF_BYTES)), bytes(_GIF_BYTES))

    def test_gif_movie_bytes_none_for_non_gif(self):
        from mpynode.ui.widgets.image_preview import gif_movie_bytes

        self.assertIsNone(gif_movie_bytes(_PNG_BYTES))
        self.assertIsNone(gif_movie_bytes("x"))


@unittest.skipIf(_QAPP is None or _PIL_IMAGE is None, "Qt/PIL unavailable")
class TestPilGifMovie(unittest.TestCase):
    """A PIL animated GIF value installs an animating MediaCell (movie mode)."""

    def setUp(self):
        self._trees = []

    def tearDown(self):
        _drain_qt(self._trees)

    def test_pil_animated_gif_installs_movie(self):
        from mpynode.ui import preferences
        from mpynode.ui.qt_wrapper import QTreeWidget, QTreeWidgetItem
        from mpynode.ui.widgets import image_preview as ip

        preferences.set_pref("variables_animate_gif", True)
        path = _make_animated_gif_file()
        # Image.open is lazy and holds the file handle; Windows refuses to
        # remove an open file, so close before unlinking.
        img = _PIL_IMAGE.open(path)
        try:
            tree = QTreeWidget()
            tree.setColumnCount(2)
            self._trees.append(tree)
            item = QTreeWidgetItem(tree)
            ip.attach_value(item, 1, img, "<gif>")     # PIL -> image view default
            self.assertEqual(ip._media_mode_for(item, 1), "movie")
            ip.refresh_media_widget(tree, item, 1, None)
            w = tree.itemWidget(item, 1)
            self.assertIsInstance(w, ip.MediaCell)
            self.assertEqual(w._mode, "movie")
        finally:
            img.close()
            os.remove(path)


class TestWatchMediaCap(unittest.TestCase):
    """The Watch size cap must NOT elide previewable media (images/audio) to a
    '<too large>' string below a larger media ceiling -- else the gif/waveform
    can never reach the render path in the Watch tab."""

    def test_small_value_unchanged(self):
        from mpynode._common.instrumentation import cap_watch_value

        v = b"\x00" * 100
        self.assertEqual(cap_watch_value(v), v)

    def test_large_non_media_capped(self):
        from mpynode._common.instrumentation import cap_watch_value, watch_max_bytes

        big = b"\x01" * (watch_max_bytes() + 1024)   # > cap, not image/wav
        out = cap_watch_value(big)
        self.assertIsInstance(out, str)
        self.assertIn("too large", out)

    def test_large_image_bytes_survive_media_ceiling(self):
        from mpynode._common.instrumentation import cap_watch_value, watch_max_bytes

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (watch_max_bytes() + 50000)
        out = cap_watch_value(png)
        self.assertIs(out, png)   # media, under media ceiling -> not capped

    def test_huge_image_bytes_still_capped(self):
        from mpynode._common.instrumentation import (
            cap_watch_value, watch_max_media_bytes)

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (watch_max_media_bytes() + 1024)
        out = cap_watch_value(png)
        self.assertIsInstance(out, str)

    def test_is_previewable_media(self):
        from mpynode._common.instrumentation import _is_previewable_media

        self.assertTrue(_is_previewable_media(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20))
        self.assertTrue(_is_previewable_media(
            b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 20))
        self.assertFalse(_is_previewable_media(b"\x01" * 100))
        self.assertFalse(_is_previewable_media("a string"))


class TestLegacyPcmStr(unittest.TestCase):
    """Legacy Python-2 'bytes-as-str' raw PCM (e.g. the shipped ``ouch.sample``,
    which loads back in Py3 as a latin-1 str) must be treated as audio: it is an
    audio candidate AND decodes -- not shown as an inert string. Plain text
    strings must NOT be mistaken for audio."""

    def _pcm(self):
        return bytes([128] * 50 + list(range(256)) * 10 + [128] * 50)

    def test_as_audio_bytes_coerces_binary_str(self):
        from mpynode.ui.widgets.image_preview import _as_audio_bytes

        pcm = self._pcm()
        self.assertEqual(_as_audio_bytes(pcm), pcm)                    # bytes
        self.assertEqual(_as_audio_bytes(pcm.decode("latin-1")), pcm)  # str->bytes
        self.assertIsNone(_as_audio_bytes("plain text label"))         # text
        self.assertIsNone(_as_audio_bytes("/Users/x/Desktop/clip.gif"))
        self.assertIsNone(_as_audio_bytes(42))

    def test_audio_candidate_for_binary_str(self):
        from mpynode.ui.widgets.image_preview import is_audio_candidate

        self.assertTrue(is_audio_candidate(self._pcm().decode("latin-1")))
        self.assertFalse(is_audio_candidate("just a name"))

    def test_accented_text_is_not_audio(self):
        # accented text stays predominantly printable ASCII, so latin-1-high
        # chars must not make it look like audio.
        from mpynode.ui.widgets.image_preview import (
            _as_audio_bytes, is_audio_candidate)

        for word in ("café", "résumé", "naïve",
                     "Zürich", "/Users/x/résumé.png",
                     "5°C", "jalapeño", "é"):
            self.assertIsNone(_as_audio_bytes(word),
                              "accented text wrongly coerced: %r" % word)
            self.assertFalse(is_audio_candidate(word),
                             "accented text wrongly audio: %r" % word)

    def test_binary_str_needs_size_and_low_printable(self):
        # a short blob is never audio, and a large printable str is text.
        from mpynode.ui.widgets.image_preview import _looks_like_binary_str

        self.assertFalse(_looks_like_binary_str("\x80\x81\x82"))   # too short
        self.assertTrue(_looks_like_binary_str("\x80" * 64))       # large binary
        self.assertFalse(_looks_like_binary_str("a" * 64))         # large text

    @unittest.skipIf(np is None, "numpy unavailable")
    def test_decode_binary_str_matches_bytes(self):
        from mpynode.ui.widgets.image_preview import decode_audio

        pcm = self._pcm()
        s_samples, s_rate = decode_audio(pcm.decode("latin-1"))
        b_samples, b_rate = decode_audio(pcm)
        self.assertEqual(s_rate, b_rate)
        self.assertEqual(s_samples.shape, b_samples.shape)
        self.assertGreater(s_samples.size, 0)
        self.assertTrue((s_samples == b_samples).all())

    def test_synthesize_wav_from_binary_str(self):
        # a legacy PCM str must wrap to the same playable WAV as the bytes
        # case; the bytes(value) fallback would TypeError on a str.
        from mpynode.ui.widgets.image_preview import synthesize_wav_bytes

        pcm = self._pcm()
        out = synthesize_wav_bytes(pcm.decode("latin-1"), rate=22050)
        self.assertEqual(bytes(out[:4]), b"RIFF")
        with wave.open(io.BytesIO(out), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 1)
            self.assertEqual(w.getnframes(), len(pcm))
            self.assertEqual(w.readframes(len(pcm)), pcm)

    def test_value_sig_binary_str_matches_bytes(self):
        # the live-reconcile signature must match across the str/bytes forms
        # of the same content, else the cell rebuilds every poll.
        from mpynode.ui.widgets.image_preview import _value_sig

        pcm = self._pcm()
        self.assertEqual(_value_sig(pcm.decode("latin-1")), _value_sig(pcm))

    def test_wave_caption_binary_str(self):
        from mpynode.ui.widgets.image_preview import _wave_caption

        cap = _wave_caption(self._pcm().decode("latin-1"))
        self.assertIn("PCM", cap)
        self.assertIn("%d bytes" % len(self._pcm()), cap)


@unittest.skipIf(_QAPP is None or _PIL_IMAGE is None, "Qt/PIL unavailable")
class TestMovieFrameScaling(unittest.TestCase):
    """An animated GIF must render EVERY frame sharp + the same size.
    QMovie.setScaledSize is nearest-neighbour (fast) scaling -> pixelated.
    We keep the movie at native size and smooth-scale each frame onto the
    label ourselves, matching the static-image delegate's SmoothTransformation."""

    def setUp(self):
        self._cells = []

    def tearDown(self):
        try:
            from shiboken6 import delete as _d
        except Exception:
            try:
                from shiboken2 import delete as _d
            except Exception:
                _d = None
        for c in self._cells:
            try:
                if _d is not None:
                    _d(c)
            except Exception:
                pass

    def _big_gif_bytes(self):
        frames = []
        for k in range(4):
            im = _PIL_IMAGE.new("RGB", (80, 80), (30, 60, 90))
            sq = _PIL_IMAGE.new("RGB", (16, 16), (240, 200, 40))
            im.paste(sq, (8 + k * 12, 30))
            frames.append(im)
        buf = io.BytesIO()
        frames[0].save(buf, format="GIF", save_all=True,
                       append_images=frames[1:], duration=120, loop=0,
                       optimize=True, disposal=1)
        return buf.getvalue()

    def test_frames_smooth_scaled_to_label_not_fast_scaled(self):
        from mpynode.ui.widgets.image_preview import MediaCell

        cell = MediaCell("movie")
        self._cells.append(cell)
        cell.resize(40, 40)
        cell.set_movie_bytes(self._big_gif_bytes())
        mv = cell._movie
        self.assertIsNotNone(mv)
        # setScaledSize is nearest-neighbour and pixelates, so the movie must
        # not be scaled. Each frame is scaled with SmoothTransformation and
        # painted onto the label instead.
        self.assertTrue(mv.scaledSize().isEmpty(),
                        "movie should not be fast-scaled via setScaledSize")
        sizes = []
        for i in range(mv.frameCount()):
            mv.jumpToFrame(i)
            cell._on_movie_frame()
            pm = cell.pixmap()
            self.assertTrue(pm is not None and not pm.isNull(),
                            "frame %d not rendered to the label" % i)
            sizes.append((pm.width(), pm.height()))
        # every displayed frame is one consistent size, fitted into the cell
        self.assertEqual(len(set(sizes)), 1,
                         "frames differ in size: %r" % (sizes,))
        self.assertLessEqual(max(sizes[0]), 40)


if __name__ == "__main__":
    unittest.main()
