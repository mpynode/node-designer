"""Runtime support for expressions converted from node-designer v1.

v1 made ``MPoint``, ``MVector``, ``MMatrix``, ``MQuaternion`` and
``MEulerRotation`` ambient in the expression namespace, and handed plug values
back as those objects. v2 does not: api objects are absent from the namespace
by design, and plug reads arrive as numpy or :class:`MatrixView`.

:class:`V1Vec` bridges the gap for the vector-like cases. It is a numpy
**subclass** carrying five method names, not a re-export of ``MVector`` --
every numpy operation works on it unchanged, and nothing here is seeded into
any namespace. A converted node gets one explicit ``from ... import`` line in
its Init tab, visible and removable once the maths has been tidied.

The five methods are exactly what the upstream v1 example corpus calls on such
values, established by walking every api call site in all nine scenes rather
than guessed at:

===================== ===========================================
``length()``          ``springChainNode``
``normalize()``       ``springChainNode``
``normal()``          the non-mutating variant, for symmetry
``distanceTo()``      ``unitSphereCollisionNode``
``point * matrix``    ``unitSphereCollisionNode``
``a ^ b``             cross product; v1 spelled it this way
===================== ===========================================

This lives in a real module, rather than being injected as source into Init,
for one concrete reason: **stored variables have to survive a pickle round
trip.** v1 nodes keep buffers of vectors in ``_storedVarsData``
(``springChainNode`` holds velocity and position arrays, ``unitSphereCollision``
a grid of points), and a class defined by ``exec``-ing Init source has no
importable module path, so its instances cannot be pickled. As a side benefit
the injected Init shim collapses from ~90 lines to one import.
"""
from __future__ import annotations

import numpy


def matrix_rows(m):
    """4x4 rows from anything matrix-like, or None if it is not a matrix.

    Handles the two shapes v2 actually produces: a matrix plug read is a
    ``MatrixView``, which carries ``asMatrix()``, and an api2 ``MMatrix`` is a
    flat 16-element sequence.
    """
    try:
        if hasattr(m, "asMatrix"):
            m = m.asMatrix()
    except Exception:
        pass
    try:
        flat = [float(x) for x in m]
    except Exception:
        return None
    if len(flat) != 16:
        return None
    return [flat[0:4], flat[4:8], flat[8:12], flat[12:16]]


class V1Vec(numpy.ndarray):
    """A 3-component numpy array that also answers v1's MVector/MPoint API.

    Construct with :func:`v1_vec` rather than directly; numpy subclasses want
    ``view()`` rather than ``__init__``.
    """

    def length(self):
        v = numpy.asarray(self[:3], dtype=float)
        return float(numpy.sqrt(numpy.dot(v, v)))

    def normalize(self):
        """Normalise IN PLACE and return self, as ``MVector.normalize`` does.

        The in-place part matters: ``springChainNode`` calls ``s.normalize()``
        for its side effect and then keeps using ``s``.
        """
        n = self.length()
        if n:
            self[:3] = numpy.asarray(self[:3], dtype=float) / n
        return self

    def normal(self):
        """A normalised COPY, leaving self alone -- ``MVector.normal``."""
        n = self.length()
        if not n:
            return v1_vec(0, 0, 0)
        return v1_vec(numpy.asarray(self[:3], dtype=float) / n)

    def distanceTo(self, other):
        d = (numpy.asarray(self[:3], dtype=float)
             - numpy.asarray(other, dtype=float)[:3])
        return float(numpy.sqrt(numpy.dot(d, d)))

    def __xor__(self, other):
        """v1 spelled the cross product ``a ^ b``.

        Left to numpy that is a bitwise op, which on a float array raises
        rather than quietly doing the wrong thing -- but it still stops the
        node dead, so it is worth carrying.
        """
        return v1_vec(numpy.cross(
            numpy.asarray(self[:3], dtype=float),
            numpy.asarray(other, dtype=float)[:3]))

    def __mul__(self, other):
        """``point * matrix`` is a homogeneous transform, Maya's row-vector
        convention, with ``w`` divided out.

        Anything not matrix-shaped falls straight through to numpy, so scalar
        and elementwise multiplication behave exactly as before.
        """
        rows = matrix_rows(other)
        if rows is None:
            return numpy.ndarray.__mul__(self, other)
        p = [float(self[0]), float(self[1]), float(self[2]), 1.0]
        out = [sum(p[k] * rows[k][c] for k in range(4)) for c in range(4)]
        w = out[3] or 1.0
        return v1_vec(out[0] / w, out[1] / w, out[2] / w)


def v1_vec(*args):
    """v1's ``MVector`` / ``MPoint``, as a :class:`V1Vec`.

    Accepts the scalar form, the single-sequence form and no arguments at all
    (v1 allowed ``MVector()``), pads short input with zeros, and **drops a
    fourth component**: an ``MPoint``'s ``w`` was never written to a
    three-component plug regardless.
    """
    if len(args) == 1:
        try:
            args = tuple(args[0])
        except TypeError:
            args = (args[0],)
    vals = [float(a) for a in args[:3]]
    while len(vals) < 3:
        vals.append(0.0)
    return numpy.array(vals, dtype=float).view(V1Vec)


def _is_vec_literal(value):
    """True for a flat sequence of 3 or 4 numbers -- a demoted v1 vector.

    Four is included because ``MPoint`` pickles as ``[x, y, z, w]``, and
    :func:`v1_vec` drops the ``w``.
    """
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        return False
    return all(isinstance(x, (int, float)) and not isinstance(x, bool)
               for x in value)


def coerce_stored(value, _depth=0):
    """Turn demoted v1 vectors inside a stored variable into :class:`V1Vec`.

    The importer's restricted unpickler maps v1's own classes to plain data,
    so a saved ``MVector`` arrives as ``[x, y, z]``. That is the right thing
    for reading a file without v1 installed, but it is the wrong thing to
    compute with: ``float * [0.0, 0.0, 0.0]`` raises ``TypeError: can't
    multiply sequence by non-int of type 'float'``, which is exactly how
    ``springChainNode`` failed, and a plain list has no ``distanceTo`` and no
    matrix multiply, which is how ``unitSphereCollisionNode`` failed.

    Recurses through lists, tuples and dict values so the buffers those two
    nodes keep -- lists of vectors -- are converted element by element. Depth
    is capped because a stored variable is arbitrary user data and may be
    self-referential.
    """
    if _depth > 6:
        return value
    if _is_vec_literal(value):
        return v1_vec(*value)
    if isinstance(value, list):
        return [coerce_stored(v, _depth + 1) for v in value]
    if isinstance(value, tuple):
        return tuple(coerce_stored(v, _depth + 1) for v in value)
    if isinstance(value, dict):
        return {k: coerce_stored(v, _depth + 1) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Audio: v1 pushed raw PCM at PyAudio; v2 plays files through Qt
# ---------------------------------------------------------------------------
#
# `ouchNode` -- the one upstream example that cannot be converted mechanically
# -- does this in v1:
#
#     import pyaudio, threading
#     def ouch(sample_rate, sample_data):
#         p = pyaudio.PyAudio()
#         stream = p.open(format=32, channels=1, rate=sample_rate, output=True)
#         stream.write(sample_data)      # BLOCKING, hence the thread
#         ...
#     t = threading.Thread(target=ouch, args=(int(self.sampleRate), self.sample))
#
# Three problems, none of them a syntax question. pyaudio is a third-party
# extension that is not present and cannot be assumed; `format=32` is
# `paFloat32`, so `self.sample` holds raw 32-bit float mono samples rather
# than any container format; and the blocking write forced a background
# thread, which is a bad idea in a Maya compute.
#
# Qt solves the last two for free -- QMediaPlayer is already asynchronous, so
# no thread -- but it plays FILES, so the raw samples need a header. This is
# the same shape as the v2 `Ouch` template, which materialises its audio to a
# temp file named by content hash and hands it to `make_audio_player`; the
# difference is purely that the template already stores a complete `.wav`.

_PLAYERS = {}


def wav_from_float32(raw, rate, channels=1):
    """Wrap raw 32-bit float PCM in a WAV container, as 16-bit signed.

    ``wave`` cannot write IEEE-float WAV (format 3), and a float32 payload in
    a PCM-declared header decodes as noise, so the samples are converted to
    16-bit signed -- which every Qt backend decodes. Values are clamped
    first: v1 fed these straight to the sound card, so nothing guarantees
    they sit inside [-1, 1].
    """
    import array
    import io as _io
    import wave

    data = bytes(raw)
    floats = array.array("f")
    floats.frombytes(data[:len(data) // 4 * 4])
    ints = array.array(
        "h", (int(max(-1.0, min(1.0, f)) * 32767) for f in floats))

    buf = _io.BytesIO()
    handle = wave.open(buf, "wb")
    try:
        handle.setnchannels(int(channels))
        handle.setsampwidth(2)
        handle.setframerate(int(rate))
        handle.writeframes(ints.tobytes())
    finally:
        handle.close()
    return buf.getvalue()


def play_pcm(raw, rate, channels=1):
    """Play raw float32 PCM without blocking. Returns the player, or None.

    Returns None rather than raising when Qt audio is unavailable -- there is
    no QtMultimedia in ``mayapy``, and a node that cannot make a noise should
    still compute its outputs.

    The player is cached module-side by content hash as well as returned, for
    two reasons: a QMediaPlayer that goes out of scope is garbage collected
    mid-playback and the sound cuts off, and rebuilding one per frame would
    thrash. The temp file is named by the same hash, so distinct clips get
    distinct files and a changed clip is never masked by a stale one.
    """
    import hashlib
    import os
    import tempfile

    try:
        from mpynode.ui.qt_wrapper import make_audio_player
    except Exception:
        return None

    try:
        wav = wav_from_float32(raw, rate, channels)
    except Exception:
        return None

    key = hashlib.md5(wav).hexdigest()[:12]
    player = _PLAYERS.get(key)
    if player is None:
        path = os.path.join(tempfile.gettempdir(),
                            "mpynode_v1_pcm_%s.wav" % key)
        try:
            if not os.path.isfile(path):
                with open(path, "wb") as fh:
                    fh.write(wav)
            player = make_audio_player(path)
        except Exception:
            return None
        if player is None:
            return None
        _PLAYERS[key] = player

    try:
        player.setPosition(0)     # replay from the top on a repeat trigger
        player.play()
    except Exception:
        return None
    return player
