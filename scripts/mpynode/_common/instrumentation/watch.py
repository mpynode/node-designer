"""Watch-variable capture / capping / (de)serialization for the
instrumentation package.

Split out of the former ``instrumentation.py`` module (behavior unchanged).
"""

from __future__ import annotations

import base64
import fnmatch
import inspect
import json
import pickle
import types

from mpynode._common.io import trust


# Expression-namespace names that are framework-injected context (NOT user
# values) and must never show up in the Watch panel's Locals.
_FRAMEWORK_LOCAL_NAMES = frozenset({"self", "node"})

#: Reserved key carrying the FRAMEWORK surface inside the watch snapshot.
#:
#: ``self`` is excluded from Locals (it's the SelfProxy, not a user value), but
#: its ``self.X`` slots -- a locator's draw, a mesh's points, a solver's joints
#: -- are exactly what a user debugging a node wants. They ride in the same
#: snapshot under this key rather than a second plug, and the Watch tab pops
#: them into their own group. Dunder-prefixed so a user variable can never
#: collide (``filter_watch_vars`` drops every ``_``-leading name).
WATCH_FRAMEWORK_KEY = "__framework__"


# ---- Watch capture ----


# Default ceiling (KiB) per watched value when the preference isn't readable.
# Anything bigger becomes a "too large" marker, so the snapshot (pickled to a
# plug and decoded every refresh) can't freeze the Watch tab on e.g. a full
# mesh-point buffer. Values under the limit keep their real type.
_WATCH_MAX_KB_DEFAULT = 64


def watch_max_bytes() -> int:
    """The per-value display ceiling in BYTES, from the user preference
    ``watch_max_value_kb`` (best-effort; falls back to the default)."""
    kb = _WATCH_MAX_KB_DEFAULT
    try:
        from mpynode.ui import preferences as _prefs

        kb = int(_prefs.get_pref("watch_max_value_kb", _WATCH_MAX_KB_DEFAULT))
    except Exception:
        kb = _WATCH_MAX_KB_DEFAULT
    return max(1, kb) * 1024


_WATCH_MAX_MEDIA_KB_DEFAULT = 2048


def watch_max_media_bytes() -> int:
    """Display ceiling in BYTES for previewable media (images / WAV audio),
    from the ``watch_max_media_kb`` preference. Larger than the generic cap so a
    gif / image / waveform reaches the render path instead of being elided to a
    "<too large>" string -- bounded so a truly huge image still caps."""
    kb = _WATCH_MAX_MEDIA_KB_DEFAULT
    try:
        from mpynode.ui import preferences as _prefs

        kb = int(_prefs.get_pref("watch_max_media_kb", _WATCH_MAX_MEDIA_KB_DEFAULT))
    except Exception:
        kb = _WATCH_MAX_MEDIA_KB_DEFAULT
    return max(1, kb) * 1024


def _is_previewable_media(value) -> bool:
    """True iff ``value`` is image/audio the Variables/Watch tabs can render (a
    PIL image, an image or audio byte blob, or a uint8 image ndarray).
    PySide-free so it is safe at compute time -- it must NOT import the Qt UI
    module (this duplicates the magic-byte sniff in ui.image_preview, which
    can't be imported here because compute runs headless). The duplication is
    unavoidable; the DRIFT is not -- ``test_watch_media_sniff`` asserts both
    sniffs accept the same containers."""
    try:
        from PIL import Image as _PILImage

        if isinstance(value, _PILImage.Image):
            return True
    except Exception:
        pass
    try:
        import numpy as _np

        if (isinstance(value, _np.ndarray) and value.dtype == _np.uint8
                and (value.ndim == 2
                     or (value.ndim == 3 and value.shape[2] in (1, 3, 4)))):
            return True
    except Exception:
        pass
    if isinstance(value, (bytes, bytearray)) and len(value) >= 12:
        head = bytes(value[:12])
        if (head.startswith(b"\x89PNG\r\n\x1a\n")
                or head.startswith(b"\xff\xd8\xff")
                or head[:6] in (b"GIF87a", b"GIF89a")
                or head[:2] == b"BM"
                or head[:4] in (b"II*\x00", b"MM\x00*")
                or (head[:4] == b"RIFF" and head[8:12] in (b"WEBP", b"WAVE"))):
            return True
        # Compressed audio. The waveform renderer decodes all of these, so they
        # must earn the media ceiling exactly as WAV does -- this list is the
        # one in ui.image_preview._audio_container_kind, and
        # test_watch_media_sniff pins the two together. Listing only WAVE here
        # sent an 80 KB mp3 through the 64 KB GENERIC cap and elided it to
        # "<bytes too large to display>" while the same-size wav rendered.
        if head[:3] == b"ID3" or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
            return True                                          # MP3
        if head[:4] == b"OggS":                                  # OGG
            return True
        if head[:4] == b"fLaC":                                  # FLAC
            return True
        if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
            return True
        if head[4:8] == b"ftyp" and head[8:12] in (b"M4A ", b"M4B ", b"M4P "):
            return True                                          # M4A/AAC
    return False


def _estimate_value_bytes(value) -> int:
    """Cheap in-memory size estimate for a watched value (bytes). Avoids
    pickling obviously-huge containers."""
    try:
        import numpy as _np

        if isinstance(value, _np.ndarray):
            return int(value.nbytes)
    except Exception:
        pass
    if isinstance(value, (bytes, bytearray, str)):
        return len(value)
    if isinstance(value, (list, tuple, set, dict)):
        n = len(value)
        if n > 50000:
            return n * 8  # clearly huge -> don't pay to pickle it
        try:
            return len(pickle.dumps(value, protocol=5))
        except Exception:
            return n * 64
    try:
        return len(pickle.dumps(value, protocol=5))
    except Exception:
        return 0


#: Modules whose objects show as a COMPACT LABEL instead of a pickled payload:
#: the API dataclasses (Mesh / UVSet / NurbsCurve / NurbsSurface / Morph /
#: MorphStack / Draw*). Each has a short __repr__ that IDENTIFIES it, while the
#: arrays behind it run to megabytes.
#:
#: Substituting up front is what makes this cheap: a 20k-point Mesh spent ~680
#: KB of pickling per compute only to become a "<too large>" string that didn't
#: even say WHICH mesh. To watch the numbers, name them -- ``pts = mesh.points``
#: is an ordinary ndarray row.
_LABEL_ONLY_MODULES = (
    "mpynode._api2.geometry",
    "mpynode._api2.morph",
    "mpynode._common.draw.draw_types",
)


class WatchLabel(str):
    """A compact stand-in for an object the snapshot deliberately does NOT carry.

    Behaves as an ordinary ``str`` everywhere (display, filtering, the media
    sniffers), but remembers what it replaced so the Watch tab's Type column can
    still say ``Mesh`` instead of ``str`` -- collapsing the VALUE should not also
    throw away the type.

    ``__reduce__`` is explicit because a ``str`` subclass with extra state does
    not round-trip through pickle by default, and this rides in the snapshot.
    """

    __slots__ = ("type_name",)

    def __new__(cls, text, type_name):
        obj           = str.__new__(cls, text)
        obj.type_name = type_name
        return obj

    def __reduce__(self):
        return (WatchLabel, (str(self), self.type_name))


def _is_label_only(value) -> bool:
    """True for an API dataclass the Watch tab shows as its repr label.

    Matches on ``__module__`` rather than importing the classes: this runs at
    COMPUTE time, so it must not drag Maya-side modules into the import graph
    (the same technique the OpenMaya drop rule in ``filter_watch_vars`` uses).
    """
    return (type(value).__module__ or "").startswith(_LABEL_ONLY_MODULES)


def cap_watch_value(value, max_bytes: int | None = None):
    """Return ``value`` unchanged when it fits within ``max_bytes`` (so its
    real type is preserved), else a compact "<too large>" marker string.

    API dataclasses (see :data:`_LABEL_ONLY_MODULES`) always collapse to their
    repr label -- they are never pickled, whatever their size.

    ``max_bytes`` defaults to the ``watch_max_value_kb`` preference."""
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    # BEFORE the size estimate: estimating cost means pickling, which is the
    # very thing that made a big geometry object expensive to display.
    if _is_label_only(value):
        cls_name = type(value).__name__
        try:
            return WatchLabel(repr(value), cls_name)
        except Exception:
            return WatchLabel("<%s>" % cls_name, cls_name)
    if max_bytes is None:
        max_bytes = watch_max_bytes()
    # Previewable media (images / WAV audio) gets a larger ceiling so it can
    # actually render in the Variables/Watch tabs instead of being elided.
    if _is_previewable_media(value):
        max_bytes = max(max_bytes, watch_max_media_bytes())
    nbytes = _estimate_value_bytes(value)
    if nbytes <= max_bytes:
        return value
    label = type(value).__name__
    try:
        import numpy as _np

        if isinstance(value, _np.ndarray):
            label = "ndarray %s %s" % (value.dtype, tuple(value.shape))
    except Exception:
        pass
    return "<%s too large to display: %.1f KB>" % (label, nbytes / 1024.0)


def filter_watch_vars(exec_locals: dict, glob_filter: str = "") -> dict:
    """Filter exec_locals down to user-visible values.

    Excludes:
      * dunder + single-underscore names
      * modules, functions, builtin functions, methods, lambdas
      * classes / type objects

    If ``glob_filter`` is provided:
      * if it contains ``*? [`` → fnmatch.fnmatchcase (e.g. ``"target_*"``)
      * else → case-sensitive substring match (e.g. ``"target"``)

    Returns a fresh dict; never mutates exec_locals.
    """
    pat       = glob_filter or ""
    has_glob  = any(c in pat for c in ("*", "?", "["))
    max_bytes = watch_max_bytes()

    out: dict = {}
    for name, value in exec_locals.items():
        if not name or name.startswith("_"):
            continue
        # Framework context, not user values: ``self`` is the SelfProxy, ``node``
        # the deformer-family write surface. Neither belongs in Watch.
        if name in _FRAMEWORK_LOCAL_NAMES:
            continue
        if isinstance(
            value,
            (
                types.ModuleType,
                types.FunctionType,
                types.BuiltinFunctionType,
                types.BuiltinMethodType,
                types.MethodType,
                types.LambdaType,
            ),
        ):
            continue
        if inspect.isclass(value):
            continue
        # Maya API objects (MFnMesh / MObject / MMatrix) are not user data:
        # serializing them is pointless and holding the reference past compute
        # is unsafe, since the underlying data may be recycled.
        mod = type(value).__module__ or ""
        if mod == "OpenMaya" or mod.startswith("OpenMaya") or mod.startswith("maya."):
            continue
        if pat:
            if has_glob:
                if not fnmatch.fnmatchcase(name, pat):
                    continue
            else:
                if pat not in name:
                    continue
        # Cap huge values: the snapshot is encoded every compute and decoded
        # every live refresh. Under the limit, the real type is kept.
        out[name] = cap_watch_value(value, max_bytes)
    return out


def collect_framework_vars(namespace: dict) -> dict:
    """The wrapper's ``self.X`` framework surface, ready for the Watch tab.

    Read off the SelfProxy already sitting in ``namespace`` -- the slots are
    seeded before exec and harvested after it, so at the snapshot point the
    values are simply in memory. Nothing is evaluated and no plug is read.

    Runs the same hygiene as :func:`filter_watch_vars` (drop privates / modules
    / functions / classes / live Maya API handles, cap oversized values), which
    matters here: mPyFile's viewport slots are live ``MShaderInstance`` /
    ``MTextureManager`` handles that must not be held past compute.

    Returns ``{}`` for any node whose proxy has no compute-locals surface.
    """
    proxy  = namespace.get("self")
    getter = getattr(proxy, "get_compute_locals", None)
    if getter is None:
        return {}
    try:
        return filter_watch_vars(getter())
    except Exception:
        return {}


# ---- Watch vars envelope: JSON around pickle+base64, since values may be
# numpy arrays, MFn* objects or custom classes. ----


def encode_watch_vars(vars_dict: dict) -> str:
    """Pickle+base64 a dict of watch values, wrapped in a JSON envelope.

    Values that don't pickle are replaced with their ``repr()`` so we
    never lose the variable from the watch list (only the live binding
    of unpicklable values).
    """
    def _safe(v):
        try:
            pickle.dumps(v)
            return v
        except Exception:
            return repr(v)

    safe: dict = {}
    for k, v in vars_dict.items():
        if isinstance(v, dict):
            # A nested surface (the framework block) is sanitised PER KEY: one
            # unpicklable slot (a live DrawItem in ``draw``) used to collapse the
            # whole block into a repr string and the Watch tab's Framework group
            # came up empty.
            safe[k] = {kk: _safe(vv) for kk, vv in v.items()}
        else:
            safe[k] = _safe(v)
    payload = {
        "protocol": 1,
        "data_b64": base64.b64encode(pickle.dumps(safe, protocol=5)).decode("ascii"),
    }
    return json.dumps(payload, separators=(",", ":"))


def decode_watch_vars(text: str) -> dict | None:
    """Inverse of encode_watch_vars. Returns None on bad/empty input."""
    if not text:
        return None
    try:
        wrapper = json.loads(text)
    except Exception:
        return None
    if not isinstance(wrapper, dict) or "data_b64" not in wrapper:
        return None
    try:
        raw = base64.b64decode(wrapper["data_b64"])
    except Exception:
        return None
    # Watch-var debug data is pickle from the (possibly untrusted) scene file.
    # Gate it on the per-scene trust resolved at open -- never unpickle an
    # untrusted scene's data (the Watch tab simply shows nothing for it).
    if not trust.pickle_trusted():
        return None
    try:
        result = pickle.loads(raw)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    return result
