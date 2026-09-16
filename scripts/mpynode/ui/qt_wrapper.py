"""Qt import shim that works on both Maya 2024 (PySide2) and Maya 2026 (PySide6).

Usage::

 from mpynode.ui.qt_wrapper import (
 QWidget, QTabWidget, QTreeWidget, QTreeWidgetItem,
 QVBoxLayout, QHBoxLayout, Qt,...
 )

If Qt is not available (e.g. Maya 2026 mayapy without PySide6 installed),
the imports raise ``ImportError``. UI tests should be Qt-guarded:

 try:
 from mpynode.ui.qt_wrapper import QWidget
 except ImportError:
 unittest.skipTest("Qt unavailable")
"""

from __future__ import annotations

# Pyrefly false positives: PySide6 / PySide2 don't exist in the system Python
# but DO in mayapy (PySide6 in Maya 2026, PySide2 in 2024). Suppress missing-import
# warnings + unused-import hints (the noqa: F401 below handles flake8).
# pyrefly: ignore [missing-import,unused-import]

# Try PySide6 first (Maya 2026+), fall back to PySide2 (Maya 2022-2025).
try:
    # pyrefly: ignore [missing-import,unused-import]
    from PySide6.QtCore import (  # noqa: F401
        QBuffer,
        QByteArray,
        QEvent,
        QObject,
        QRect,
        QRegularExpression,
        QSize,
        Qt,
        QTimer,
        QUrl,
        Signal,
        Slot,
    )

    # pyrefly: ignore [missing-import,unused-import]
    from PySide6.QtGui import (  # noqa: F401
        # Qt 6 moved QAction/QShortcut/QActionGroup from QtWidgets to
        # QtGui; the PySide2 fallback below imports QAction from QtWidgets.
        QAction,
        QBrush,
        QColor,
        QDesktopServices,
        QFont,
        QFontMetrics,
        QIcon,
        QImage,
        QImageReader,
        QKeySequence,
        QMovie,
        QPainter,
        QPalette,
        QPixmap,
        QShortcut,
        QSyntaxHighlighter,
        QTextBlockFormat,
        QTextCharFormat,
        QTextCursor,
        QTextFormat,
        QTextFrameFormat,
        QTextLength,
        QTextTable,
        QTextTableFormat,
    )

    # pyrefly: ignore [missing-import,unused-import]
    from PySide6.QtWidgets import (  # noqa: F401
        QAbstractItemView,
        QButtonGroup,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSplitter,
        QSplitterHandle,
        QStackedLayout,
        QStackedWidget,
        QStyle,
        QStyledItemDelegate,
        QStyleOptionViewItem,
        QTabBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextBrowser,
        QTextEdit,
        QToolBar,
        QToolTip,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_BINDING = "PySide6"

    # pyrefly: ignore [missing-import,unused-import]
    from shiboken6 import wrapInstance  # noqa: F401
except ImportError:
    try:
        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtCore import (  # noqa: F401
            QBuffer,
            QByteArray,
            QEvent,
            QObject,
            QRect,
            QRegularExpression,
            QSize,
            Qt,
            QTimer,
            QUrl,
            Signal,
            Slot,
        )

        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtGui import (  # noqa: F401
            QBrush,
            QColor,
            QDesktopServices,
            QFont,
            QFontMetrics,
            QIcon,
            QImage,
            QImageReader,
            QKeySequence,
            QMovie,
            QPainter,
            QPalette,
            QPixmap,
            QSyntaxHighlighter,
            QTextBlockFormat,
            QTextCharFormat,
            QTextCursor,
            QTextFormat,
            QTextFrameFormat,
            QTextLength,
            QTextTable,
            QTextTableFormat,
        )

        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtWidgets import (  # noqa: F401
            # PySide2 (Qt 5) keeps QAction and QShortcut in QtWidgets, not QtGui.
            QAbstractItemView,
            QAction,
            QButtonGroup,
            QCheckBox,
            QColorDialog,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QHeaderView,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QRadioButton,
            QScrollArea,
            QShortcut,
            QSplitter,
            QSplitterHandle,
            QStackedLayout,
            QStackedWidget,
            QStyle,
            QStyledItemDelegate,
            QStyleOptionViewItem,
            QTabBar,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QTextBrowser,
            QTextEdit,
            QToolBar,
            QToolTip,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )

        QT_BINDING = "PySide2"

        # pyrefly: ignore [missing-import,unused-import]
        from shiboken2 import wrapInstance  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Neither PySide6 nor PySide2 is available; the Node Designer UI "
            "cannot be imported. (mPyNode + plugin functionality still works "
            "without the UI; this only affects the Node Designer window.)"
        ) from exc


# ---------------------------------------------------------------------------
# Optional QtMultimedia (video previews). Ships with both Maya PySide bundles
# but may be absent in a trimmed env, so callers check HAS_QT_MULTIMEDIA.
# ---------------------------------------------------------------------------

HAS_QT_MULTIMEDIA = False
QMediaPlayer      = None
QVideoWidget      = None
QAudioOutput      = None
QMediaContent     = None

if QT_BINDING == "PySide6":
    try:
        # pyrefly: ignore [missing-import,unused-import]
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer  # noqa: F401
        # pyrefly: ignore [missing-import,unused-import]
        from PySide6.QtMultimediaWidgets import QVideoWidget  # noqa: F401
        HAS_QT_MULTIMEDIA = True
    except ImportError:
        pass
else:
    try:
        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtMultimedia import QMediaContent, QMediaPlayer  # noqa: F401
        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtMultimediaWidgets import QVideoWidget  # noqa: F401
        HAS_QT_MULTIMEDIA = True
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Optional QAudioDecoder (compressed-audio -> raw PCM, for the waveform view of
# MP3/OGG/FLAC/AIFF/M4A blobs the stdlib ``wave`` module can't parse). Decoding
# is platform-backend + codec dependent (macOS AVFoundation / Win Media
# Foundation / Linux gstreamer), so callers ALWAYS treat a None/empty result as
# "no waveform available" and fall back to a blank strip -- never to
# reinterpreting the compressed bytes as PCM noise. QMediaPlayer can still PLAY
# the same blob even when QAudioDecoder can't hand back samples.
# ---------------------------------------------------------------------------

HAS_QT_AUDIO_DECODER = False
QAudioDecoder        = None
QAudioFormat         = None

if QT_BINDING == "PySide6":
    try:
        # pyrefly: ignore [missing-import,unused-import]
        from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat  # noqa: F401
        HAS_QT_AUDIO_DECODER = True
    except ImportError:
        pass
else:
    try:
        # pyrefly: ignore [missing-import,unused-import]
        from PySide2.QtMultimedia import QAudioDecoder, QAudioFormat  # noqa: F401
        HAS_QT_AUDIO_DECODER = True
    except ImportError:
        pass


def _q_audio_sample_format(fmt):
    """(sample_format_str, channels, rate) for a QAudioBuffer's QAudioFormat,
    spanning the Qt5 (sampleType + sampleSize) and Qt6 (sampleFormat) APIs.
    ``sample_format_str`` is one of "uint8"/"int16"/"int32"/"float32" or None
    when it can't be classified."""
    ch, rate = 1, 0
    try:
        ch = int(fmt.channelCount())
    except Exception:
        ch = 1
    try:
        rate = int(fmt.sampleRate())
    except Exception:
        rate = 0

    # Qt6: QAudioFormat.SampleFormat enum (accessible scoped or unscoped).
    def _q6(name):
        v = getattr(QAudioFormat, name, None)
        if v is None:
            sfc = getattr(QAudioFormat, "SampleFormat", None)
            v   = getattr(sfc, name, None) if sfc is not None else None
        return v

    try:
        sf = fmt.sampleFormat()
        for name, tag in (("UInt8", "uint8"), ("Int16", "int16"),
                          ("Int32", "int32"), ("Float", "float32")):
            ref = _q6(name)
            if ref is not None and sf == ref:
                return tag, ch, rate
    except Exception:
        pass

    # Qt5: sampleType (SignedInt / UnSignedInt / Float) + sampleSize (bits).
    try:
        size = int(fmt.sampleSize())
        st   = fmt.sampleType()
        if getattr(QAudioFormat, "Float", None) is not None and st == QAudioFormat.Float:
            return "float32", ch, rate
        if size == 8:
            return "uint8", ch, rate
        if size == 16:
            return "int16", ch, rate
        if size == 32:
            return "int32", ch, rate
    except Exception:
        pass
    return None, ch, rate


def _q_audio_buffer_bytes(buf):
    """Raw interleaved PCM bytes out of a QAudioBuffer, spanning the several
    shapes PySide can hand back (bytes / memoryview / sized shiboken voidptr).
    Returns b"" if none of them work."""
    n = 0
    try:
        n = int(buf.byteCount())
    except Exception:
        n = 0
    for meth in ("constData", "data"):
        fn = getattr(buf, meth, None)
        if fn is None:
            continue
        try:
            d = fn()
        except Exception:
            continue
        if d is None:
            continue
        if isinstance(d, (bytes, bytearray)):
            return bytes(d)
        try:
            return memoryview(d).tobytes()
        except Exception:
            pass
        try:
            if n > 0 and hasattr(d, "setsize"):
                d.setsize(n)
            return bytes(d)
        except Exception:
            continue
    return b""


def decode_audio_bytes_to_pcm(data, suffix, timeout_ms=8000):
    """Decode compressed/uncompressed audio ``data`` to interleaved PCM via
    QtMultimedia's QAudioDecoder.

    ``data`` is written to a temp file with ``suffix`` (QAudioDecoder decodes
    from a file across both Qt5/Qt6), a bounded local event loop pumps the
    async decode, and the result is ``(pcm_bytes, sample_format, channels,
    rate)`` -- or ``(None, None, 0, 0)`` when the decoder is unavailable OR
    decoding fails (missing codec / bad data / timeout). Safe on the main
    thread; never raises."""
    if not HAS_QT_AUDIO_DECODER:
        return None, None, 0, 0
    import os as _os
    import tempfile as _tf

    if QT_BINDING == "PySide6":
        from PySide6.QtCore import QEventLoop
        from PySide6.QtCore import QTimer as _QTimer
        from PySide6.QtCore import QUrl as _QUrl
    else:
        from PySide2.QtCore import QEventLoop
        from PySide2.QtCore import QTimer as _QTimer
        from PySide2.QtCore import QUrl as _QUrl

    path = None
    try:
        fd, path = _tf.mkstemp(suffix=suffix or "", prefix="mpynode_dec_")
        with _os.fdopen(fd, "wb") as fh:
            fh.write(bytes(data))
    except Exception:
        if path is not None:
            try:
                _os.remove(path)
            except Exception:
                pass
        return None, None, 0, 0

    chunks  = []
    fmt_box = {"sf": None, "ch": 1, "rate": 0}
    dec     = None
    try:
        dec  = QAudioDecoder()
        loop = QEventLoop()

        def _read_ready():
            try:
                while dec.bufferAvailable():
                    buf = dec.read()
                    if fmt_box["sf"] is None:
                        try:
                            sf, ch, rate = _q_audio_sample_format(buf.format())
                            fmt_box["sf"], fmt_box["ch"], fmt_box["rate"] = (
                                sf, ch, rate)
                        except Exception:
                            pass
                    raw = _q_audio_buffer_bytes(buf)
                    if raw:
                        chunks.append(raw)
            except Exception:
                pass

        def _quit(*_a):
            try:
                loop.quit()
            except Exception:
                pass

        dec.bufferReady.connect(_read_ready)
        try:
            dec.finished.connect(_quit)
        except Exception:
            pass
        for sig_name in ("errorOccurred", "error"):  # Qt6 / Qt5
            sig = getattr(dec, sig_name, None)
            if sig is not None:
                try:
                    sig.connect(_quit)
                except Exception:
                    pass

        if QT_BINDING == "PySide6":
            dec.setSource(_QUrl.fromLocalFile(path))
        else:
            dec.setSourceFilename(path)
        dec.start()

        timer = _QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(_quit)
        timer.start(int(timeout_ms))
        (loop.exec if hasattr(loop, "exec") else loop.exec_)()
        try:
            timer.stop()
        except Exception:
            pass
        # Drain any buffers delivered right before finished/quit.
        try:
            _read_ready()
        except Exception:
            pass
        try:
            dec.stop()
        except Exception:
            pass
    except Exception:
        chunks = []
    finally:
        if dec is not None:
            try:
                dec.deleteLater()
            except Exception:
                pass
        if path is not None:
            try:
                _os.remove(path)
            except Exception:
                pass

    if not chunks or fmt_box["sf"] is None:
        return None, None, 0, 0
    return (b"".join(chunks), fmt_box["sf"],
            int(fmt_box["ch"] or 1), int(fmt_box["rate"] or 0))


def start_video_preview(path, video_widget):
    """Play ``path`` (looping, muted) into ``video_widget`` and return the
    QMediaPlayer (the caller must keep a ref so it isn't GC'd), or None if
    QtMultimedia is unavailable. Hides the PySide2/PySide6 API split."""
    if not HAS_QT_MULTIMEDIA:
        return None
    player = QMediaPlayer()
    player.setVideoOutput(video_widget)
    url = QUrl.fromLocalFile(path)
    if QT_BINDING == "PySide6":
        audio = QAudioOutput()
        audio.setMuted(True)
        audio.setParent(player)  # Qt parent-owns it (GC-safe)
        player.setAudioOutput(audio)
        player.setLoops(QMediaPlayer.Infinite)
        player.setSource(url)
    else:
        player.setMuted(True)
        player.setMedia(QMediaContent(url))

        # Qt5 has no setLoops: restart on EndOfMedia.
        def _loop(status, p=player):
            if status == QMediaPlayer.EndOfMedia:
                p.setPosition(0)
                p.play()

        player.mediaStatusChanged.connect(_loop)
    player.play()
    return player


def make_audio_player(path, parent=None):
    """Build an UN-muted QMediaPlayer for a local audio file and return it (or
    None if QtMultimedia is unavailable). The caller keeps the ref and drives
    play() / setPosition(ms) / stop() directly (those are identical across
    PySide2/PySide6). Hides the Qt5/Qt6 source-setting + audio-output split.

    Unlike :func:`start_video_preview` this does NOT mute or loop -- it is for
    the Variables/Watch tab click-to-play / drag-to-scrub waveform audio.

    Returns None when QtMultimedia is unavailable OR a player cannot be
    constructed (e.g. no platform audio backend / device), so callers degrade
    to render-only (waveform shown, no playback) rather than penalize the user.
    """
    if not HAS_QT_MULTIMEDIA:
        return None
    player = None
    try:
        player = QMediaPlayer(parent)
        url    = QUrl.fromLocalFile(path)
        if QT_BINDING == "PySide6":
            audio = QAudioOutput()
            audio.setParent(player)  # Qt parent-owns it (GC-safe)
            player.setAudioOutput(audio)
            player.setSource(url)
        else:
            player.setMedia(QMediaContent(url))
            try:
                player.setVolume(100)
            except Exception:
                pass
        return player
    except Exception:
        # A backend failure surfaces AFTER construction, and the player is
        # already parented to a live tab widget, so dropping the Python ref
        # would leak it under the tab. Release it before degrading to None.
        if player is not None:
            try:
                player.deleteLater()
            except Exception:
                pass
        return None


# ---------------------------------------------------------------------------
# Maya main window helper
# ---------------------------------------------------------------------------


def maya_main_window():
    """Return Maya's main window as a QWidget (or None if unavailable).

    Use as the ``parent=`` for any standalone window so the QWidget hierarchy
    keeps the window alive (without a parent, ``NDMainWindow().show()``
    would be GC'd as soon as the temporary goes out of scope).
    """
    try:
        import maya.OpenMayaUI as omui
    except ImportError:
        return None
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    try:
        return wrapInstance(int(ptr), QWidget)
    except Exception:
        return None
