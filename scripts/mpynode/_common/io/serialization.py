"""JSON encode/decode for ``_inputAttrs`` / ``_outputAttrs`` /
``_storedVarsData`` plug values.

The format is a single JSON object on the plug.

For attr maps:
 {
 "myInputAttr": {"attr_type": "float", "is_array": false},
 "myOutputAttr": {"attr_type": "vector", "is_array": true}
 }

For stored vars:
 base64-encoded pickle bytes (varies by user expression)

This module is API-agnostic (pure Python) and is imported by both the
API 1 plugin (mPyIkSolver/Field/Emitter) and the API 2 plugin (everything
else). No Maya imports at module-import time.
"""

from __future__ import annotations

import base64
import json
import lzma
import pickle
import threading
import zlib
from collections import OrderedDict
from typing import Any

from mpynode._common.io import trust, value_codec


class InvalidAttrMapError(ValueError):
    """Raised when a plug value can't be parsed as a valid attr map."""


# ---- Attr map (string plug -> dict of {name: {attr_type, is_array}}) ----


def encode_attr_map(data: dict[str, dict[str, Any]]) -> str:
    """Compact JSON encoding for ``_inputAttrs`` / ``_outputAttrs``.

    ``sort_keys=True`` for deterministic output (helps diffing.ma files
    across reloads).
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def decode_attr_map(plug_value: str) -> dict[str, dict[str, Any]]:
    """Parse a JSON attr-map string. Returns ``{}`` for empty/None."""
    if not plug_value or plug_value == "None":
        return {}
    try:
        parsed = json.loads(plug_value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidAttrMapError(
            f"attr map plug value is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise InvalidAttrMapError(
            f"attr map must decode to a dict; got {type(parsed).__name__}"
        )
    # Light validation: each entry must be a dict with at least ``attr_type``.
    for name, entry in parsed.items():
        if not isinstance(entry, dict):
            raise InvalidAttrMapError(
                f"attr map entry {name!r} must be a dict; got {type(entry).__name__}"
            )
        if "attr_type" not in entry:
            raise InvalidAttrMapError(
                f"attr map entry {name!r} missing required key 'attr_type'"
            )
    return parsed


# ---- Stored vars (string plug -> arbitrary pickled Python objects) ----


def _compress(raw: bytes, compression: str) -> tuple[bytes, str]:
    if compression == "lzma":
        return lzma.compress(raw), "lzma"
    if compression == "none":
        return raw, "none"
    return zlib.compress(raw, 6), "zlib"


def _decompress(blob: bytes, codec) -> bytes:
    if codec == "zlib":
        return zlib.decompress(blob)
    if codec == "lzma":
        return lzma.decompress(blob)
    return blob  # "none"/None (legacy uncompressed)


def _encode_keyed(
    vars_dict: dict[str, Any], compression: str
) -> tuple[str, list[str]]:
    """Hybrid keyed encode (format ``"keyed2"``, protocol 8).

    Each value is encoded INDEPENDENTLY (per-value isolation): first via the
    version-safe, pickle-free :mod:`value_codec` (numpy / primitives /
    containers -> ``{"enc": "safe", ...}``); anything it can't represent falls
    back to pickle (``{"enc": "pickle", ...}``). The whole ``{name: entry}``
    container is then JSON-encoded (NOT pickled -- the old format pickled the
    outer container too, an extra RCE sink), compressed, and base64'd.

    The wrapper carries ``has_pickle`` so callers can cheaply tell whether
    opening the file needs a trust decision without decompressing. Values that
    can be neither safe-encoded nor pickled are dropped and returned in
    ``dropped``.
    """
    inner:   dict[str, dict] = {}
    dropped: list[str] = []
    has_pickle = False
    for key, value in vars_dict.items():
        try:
            inner[key] = {"enc": "safe", "data": value_codec.encode_value(value)}
            continue
        except value_codec.UnsupportedValue:
            pass
        except Exception:
            # value_codec hit an unexpected error -- still try pickle before
            # giving up on the value.
            pass
        try:
            payload_b64 = base64.b64encode(
                pickle.dumps(value, protocol=5)
            ).decode("ascii")
            inner[key] = {"enc": "pickle", "b64": payload_b64}
            has_pickle = True
        except Exception:
            dropped.append(key)
    raw = json.dumps(inner, separators=(",", ":")).encode("utf-8")
    blob, codec = _compress(raw, compression)
    payload = {
        "protocol":   8,
        "format":     "keyed2",
        "codec":      codec,
        "has_pickle": has_pickle,
        "data_b64":   base64.b64encode(blob).decode("ascii"),
    }
    return json.dumps(payload, separators=(",", ":")), dropped


def encode_stored_vars(vars_dict: dict[str, Any], compression: str = "zlib") -> str:
    """Encode a stored-vars dict to the keyed blob string (see
    :func:`_encode_keyed`). ``compression``: ``"zlib"`` (default, fast),
    ``"lzma"`` (max), or ``"none"``. Unpicklable values are dropped."""
    return _encode_keyed(vars_dict, compression)[0]


def encode_stored_vars_resilient(
    vars_dict: dict[str, Any], compression: str = "zlib"
) -> tuple[str, list[str]]:
    """Like :func:`encode_stored_vars` but also returns the list of keys
    that were dropped because their value couldn't be pickled (so the
    caller can warn). Per-value isolation is inherent to the keyed
    format, so this is just :func:`_encode_keyed`."""
    return _encode_keyed(vars_dict, compression)


def blob_has_pickle(plug_value: str) -> bool:
    """True if decoding ``plug_value`` would require unpickling (possibly
    untrusted) data.

    SECURITY: the wrapper's ``has_pickle`` flag lives in the ``.ma`` file and is
    therefore attacker-controllable -- it is NOT trusted for this decision. For
    the ``keyed2`` format we DECOMPRESS the inner (plain JSON, cheap; this runs
    once per node at open, never on the compute hot path) and scan for a real
    ``enc == "pickle"`` entry. Any decode failure fails SAFE (treated as
    pickle, i.e. requires a trust decision). The OLD ``keyed`` / legacy
    single-blob formats are always pickle. Empty / non-stored-vars -> False.

    Callers (the scene open/import hook, ``.mpn`` load) use this to decide
    whether a file even needs a trust prompt -- a file whose stored vars are all
    safe-codec never prompts.
    """
    if not plug_value or plug_value == "None":
        return False
    try:
        wrapper = json.loads(plug_value)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(wrapper, dict) or "data_b64" not in wrapper:
        return False
    if wrapper.get("format") != "keyed2":
        return True  # old "keyed" / legacy single-blob == pickle
    # keyed2: ignore the self-declared flag; scan the actual inner for pickle.
    try:
        raw   = _decompress(base64.b64decode(wrapper["data_b64"]), wrapper.get("codec"))
        inner = json.loads(raw.decode("utf-8"))
    except Exception:
        return True  # can't verify -> assume pickle (fail safe)
    if not isinstance(inner, dict):
        return True
    for entry in inner.values():
        if isinstance(entry, dict) and entry.get("enc") == "pickle":
            return True
    return False


def _decode_keyed2(
    raw: bytes, trusted: bool | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Decode the JSON ``{name: entry}`` inner of the new ``keyed2`` format.

    ``safe`` values always decode (pickle-free). ``pickle`` values decode ONLY
    when trusted; otherwise they are recorded in ``failures`` and NEVER
    unpickled (no code execution). The inner is plain JSON, so even when
    untrusted we can still enumerate keys and load the safe values + name
    exactly which pickle values were refused.

    ``trusted`` defaults to the per-scene flag (:func:`trust.pickle_trusted`);
    callers loading an out-of-band file (e.g. ``.mpn`` import) pass an explicit,
    per-file resolution so the decision isn't tied to the ambient scene state.
    """
    try:
        inner = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}, {}
    if not isinstance(inner, dict):
        return {}, {}
    out:      dict[str, Any] = {}
    failures: dict[str, str] = {}
    trusted = trust.pickle_trusted() if trusted is None else bool(trusted)
    for key, entry in inner.items():
        if not isinstance(entry, dict):
            failures[key] = "malformed entry"
            continue
        enc = entry.get("enc")
        if enc == "safe":
            try:
                out[key] = value_codec.decode_value(entry.get("data"))
            except Exception as exc:
                failures[key] = "{}: {}".format(type(exc).__name__, exc)
        elif enc == "pickle":
            if not trusted:
                failures[key] = "refused: scene not trusted (pickle value)"
                continue
            try:
                out[key] = pickle.loads(base64.b64decode(entry.get("b64", "")))
            except Exception as exc:
                failures[key] = "{}: {}".format(type(exc).__name__, exc)
        else:
            failures[key] = "unknown encoding %r" % (enc,)
    return out, failures


def _decode_legacy_pickle(
    raw: bytes, kind: str, trusted: bool | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Decode an OLD all-pickle blob (the ``keyed`` outer-container form, or the
    legacy single-blob form). Both unpickle attacker-controllable bytes, so the
    WHOLE decode is gated on trust -- and because the container itself is pickle,
    when untrusted we cannot even enumerate keys, so we refuse wholesale.

    ``trusted`` defaults to the per-scene flag; an explicit value scopes the
    decision to a single out-of-band file load (see :func:`_decode_keyed2`).
    """
    if not (trust.pickle_trusted() if trusted is None else bool(trusted)):
        return {}, {"<%s>" % kind: "refused: scene not trusted (legacy pickle blob)"}
    try:
        decoded = pickle.loads(raw)
    except Exception as exc:
        return {}, {"<%s>" % kind: "{}: {}".format(type(exc).__name__, exc)}
    if not isinstance(decoded, dict):
        return {}, {}
    if kind == "keyed":
        # outer is {name: pickled-bytes}; unpickle each value independently
        out:      dict[str, Any] = {}
        failures: dict[str, str] = {}
        for key, blob in decoded.items():
            try:
                out[key] = pickle.loads(blob)
            except Exception as exc:
                failures[key] = "{}: {}".format(type(exc).__name__, exc)
        return out, failures
    return decoded, {}


def _decode_detailed(
    plug_value: str, trusted: bool | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Decode a stored-vars blob -> ``(values, failures)``.

    Dispatches by wrapper format:
      * ``keyed2`` (current): safe values always; pickle values trust-gated.
      * ``keyed`` (old): all-pickle, trust-gated wholesale.
      * legacy single-blob (protocol 5/6): one pickle, trust-gated.

    Pickle is NEVER run untrusted -- the gate (the per-scene flag, or an
    explicit per-file ``trusted`` for out-of-band loads) is the security
    boundary, not a restricted unpickler, so a trusted file keeps full
    arbitrary-object support.
    """
    if not plug_value or plug_value == "None":
        return {}, {}
    try:
        wrapper = json.loads(plug_value)
    except (json.JSONDecodeError, TypeError):
        return {}, {}
    if not isinstance(wrapper, dict) or "data_b64" not in wrapper:
        return {}, {}
    try:
        raw = _decompress(base64.b64decode(wrapper["data_b64"]), wrapper.get("codec"))
    except Exception:
        return {}, {}
    fmt = wrapper.get("format")
    if fmt == "keyed2":
        return _decode_keyed2(raw, trusted=trusted)
    if fmt == "keyed":
        return _decode_legacy_pickle(raw, "keyed", trusted=trusted)
    return _decode_legacy_pickle(raw, "legacy", trusted=trusted)


def decode_stored_vars(plug_value: str, trusted: bool | None = None) -> dict[str, Any]:
    """Decode to a values dict (partial -- failed/unimportable values are
    silently skipped). Use :func:`decode_stored_vars_detailed` when you
    need to report what failed. Returns ``{}`` for empty/None.

    ``trusted`` (default: the per-scene flag) lets an out-of-band file load
    pass an explicit, per-file pickle-trust decision."""
    return _decode_detailed(plug_value, trusted=trusted)[0]


def decode_stored_vars_detailed(
    plug_value: str, trusted: bool | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Like :func:`decode_stored_vars` but also returns ``{name: reason}``
    for any value that couldn't be reconstructed (graceful partial load)."""
    return _decode_detailed(plug_value, trusted=trusted)


# ---- Content-addressed decode cache (compute hot path) ----
#
# On the compute hot path the blob string is IDENTICAL frame to frame whenever
# the stored vars didn't change, so re-unpickling it every frame is pure waste
# proportional to the data size (an embedded image would be rebuilt each frame).
# ``decode_cached`` memoizes by blob-string CONTENT.
#
# Content-addressing makes it self-coherent: any writer that changes the stored
# vars writes a different blob string, so the next decode is a natural miss. No
# explicit invalidation is needed; the scene-change clear is memory hygiene.
#
# READ-ONLY CONTRACT: ``decode_cached`` is only for callers that treat the
# result as read-only (compute paths copy into SelfProxy/new_stored first).
# Mutating callers (``stored_vars_api`` add/set/remove) must keep using
# ``decode_stored_vars``. It hands out a SHALLOW COPY, so mutating the CONTAINER
# is safe, but in-place mutation of a stored-var VALUE (already a non-persisting
# anti-pattern) leaks across frames -- reassign ``self.x = ...`` instead.
#
# Bounded by total cached blob bytes with LRU eviction, so a few large blobs
# can't blow up memory; eviction only costs a re-decode. Thread-safe, since
# compute runs on EM worker threads.

_DECODE_CACHE: "OrderedDict[str, dict]" = OrderedDict()
_DECODE_CACHE_BYTES     = 0
_DECODE_CACHE_MAX_BYTES = 128 * 1024 * 1024  # 128 MB of blob strings
_DECODE_CACHE_LOCK      = threading.Lock()


def decode_cached(plug_value: str) -> dict[str, Any]:
    """Cached, read-only-contract variant of :func:`decode_stored_vars`
    for the compute hot path. Returns a shallow copy of the decoded
    dict (see module note). Empty/None -> ``{}`` (never cached)."""
    if not plug_value or plug_value == "None":
        return {}
    with _DECODE_CACHE_LOCK:
        hit = _DECODE_CACHE.get(plug_value)
        if hit is not None:
            _DECODE_CACHE.move_to_end(plug_value)
            return dict(hit)
    # Miss: decode outside the lock (the expensive part), then insert.
    decoded = decode_stored_vars(plug_value)
    nbytes  = len(plug_value)
    with _DECODE_CACHE_LOCK:
        if plug_value not in _DECODE_CACHE:
            _DECODE_CACHE[plug_value] = decoded
            global _DECODE_CACHE_BYTES
            _DECODE_CACHE_BYTES += nbytes
        _DECODE_CACHE.move_to_end(plug_value)
        # Evict LRU until under the byte budget (keep at least the
        # entry we just added).
        while (
            _DECODE_CACHE_BYTES > _DECODE_CACHE_MAX_BYTES
            and len(_DECODE_CACHE) > 1
        ):
            old_key, _old_val = _DECODE_CACHE.popitem(last=False)
            _DECODE_CACHE_BYTES -= len(old_key)
    return dict(decoded)


def clear_stored_var_decode_cache() -> None:
    """Drop the entire decode cache (memory hygiene on scene change)."""
    global _DECODE_CACHE_BYTES
    with _DECODE_CACHE_LOCK:
        _DECODE_CACHE.clear()
        _DECODE_CACHE_BYTES = 0


def _stored_var_decode_cache_info() -> tuple:
    """(entry_count, total_blob_bytes) -- for tests/diagnostics."""
    with _DECODE_CACHE_LOCK:
        return (len(_DECODE_CACHE), _DECODE_CACHE_BYTES)

