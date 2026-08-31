# tests/ui/test_watch_media_sniff.py  (pure -- no setUpModule)
"""The two magic-byte sniffs must accept the same audio containers.

There are deliberately two: ``ui.image_preview._audio_container_kind`` (Qt
side, decides whether a cell renders as a waveform) and
``_common.instrumentation.watch._is_previewable_media`` (headless, decides
whether the value clears the generic size cap and reaches the renderer at all).
The second cannot import the first -- compute runs without Qt.

The duplication is fine; the DRIFT is the defect. The headless sniff knew only
WAVE, so an 80 KB mp3 was over the 64 KB generic cap, never earned the 2 MB
media cap, and was elided to "<bytes too large to display>" -- while a wav of
the same size rendered. These tests pin the two lists together.
"""
import unittest

from mpynode._common.instrumentation import watch as _iw


# One minimal, correctly-signed header per container. Padded past the 12-byte
# minimum both sniffs require.
_PAD = b"\x00" * 32

HEADERS = {
    "WAV":  b"RIFF\x24\x00\x00\x00WAVEfmt " + _PAD,
    "MP3-ID3":   b"ID3\x03\x00\x00\x00\x00\x00\x00" + _PAD,
    "MP3-SYNC":  b"\xff\xfb\x90\x00" + _PAD,
    "OGG":  b"OggS\x00\x02\x00\x00\x00\x00\x00\x00" + _PAD,
    "FLAC": b"fLaC\x00\x00\x00\x22\x00\x00\x00\x00" + _PAD,
    "AIFF": b"FORM\x00\x00\x00\x2eAIFF" + _PAD,
    "M4A":  b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00" + _PAD,
}


class TestHeadlessSniffAcceptsEveryAudioContainer(unittest.TestCase):

    def test_every_container_is_previewable_media(self):
        missed = [k for k, blob in HEADERS.items()
                  if not _iw._is_previewable_media(blob)]
        self.assertEqual(
            missed, [],
            "these audio containers do NOT earn the media size ceiling, so a "
            "clip larger than watch_max_value_kb is elided to a "
            "'<too large to display>' string before the waveform renderer "
            "ever sees the bytes: %r" % (missed,))

    def test_the_two_sniffs_agree(self):
        """The Qt-side sniff is the source of truth for what can render."""
        try:
            from mpynode.ui.widgets import image_preview as _ip
        except Exception as exc:            # noqa: BLE001
            self.skipTest("image_preview needs Qt: %r" % (exc,))
        disagree = []
        for kind, blob in HEADERS.items():
            renders = _ip._audio_container_kind(blob) is not None
            previewable = _iw._is_previewable_media(blob)
            if renders != previewable:
                disagree.append("%s: image_preview=%s watch=%s"
                                % (kind, renders, previewable))
        self.assertEqual(
            disagree, [],
            "the Qt sniff and the headless sniff disagree. They are separate "
            "on purpose (compute is Qt-free) but must accept the SAME "
            "containers, or a value renders in one panel and is elided in the "
            "other:\n  " + "\n  ".join(disagree))


class TestTheCapIsWhatWasActuallyBroken(unittest.TestCase):
    """Non-vacuity: prove the sniff is what decides, at a real size."""

    def test_an_mp3_over_the_generic_cap_survives_capping(self):
        # 80 KB: over the 64 KB generic default, under the 2 MB media default.
        blob = HEADERS["MP3-ID3"] + b"\x00" * (80 * 1024)
        capped = _iw.cap_watch_value(blob, max_bytes=64 * 1024)
        self.assertIsInstance(
            capped, (bytes, bytearray),
            "an mp3 past the generic cap was elided to %r instead of being "
            "handed to the waveform renderer" % (capped,))

    def test_a_non_media_blob_of_the_same_size_is_still_elided(self):
        """The cap must still do its job -- this is not 'disable the cap'."""
        blob = b"\x00" * (80 * 1024)
        capped = _iw.cap_watch_value(blob, max_bytes=64 * 1024)
        self.assertIsInstance(
            capped, str,
            "the size cap no longer elides a large NON-media value; the media "
            "exemption has been widened into a blanket bypass")


if __name__ == "__main__":
    unittest.main()
