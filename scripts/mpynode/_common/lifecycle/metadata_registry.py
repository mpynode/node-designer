"""metadata_registry -- per-node authorship / version / license metadata.

Every mPyNode type can carry a small bundle of metadata: ``authors`` (a list of
``"Name <email>"`` strings), ``version``, ``license`` and a free ``description``.
The main driver is embedding the license (+ author / version) in *compiled*
nodes, plus emitting a build-hash identifier on compile.

``license`` holds the whole legal block -- a copyright line, a copyleft notice,
a Creative Commons deed, an SPDX id, or full license text. There is deliberately
no separate ``copyright`` field: a CC0 or public-domain node has no copyright
holder to name, so that label invited the wrong content.

Storage mirrors ``MethodsSourceMixin`` / ``InitSourceMixin``: a hidden
``_metadata`` string plug holding a JSON blob, so the metadata round-trips with
the ``.ma``. The plug is created lazily (only on ``set_metadata``) so a node that
never sets metadata stays byte-identical (and cache-stable for the native
porter). ``MetadataMixin`` lives on the BASE ``MPyNode`` so every wrapper type
inherits it.

This module is otherwise pure (Qt-free at import; maya and the preferences
module are imported lazily, inside the mixin methods and ``prefs_defaults``):
``coerce`` / ``merge_metadata`` / ``is_empty`` / ``build_hash`` /
``stamp_build_hash`` / ``vendor_string`` / ``version_string`` / ``banner_lines``
are deterministic helpers used by the native codegen, the .py bake and the
preferences merge, and are unit-tested without a running Maya.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, List, Tuple

__all__ = [
    "MetadataMixin",
    "FIELDS",
    "coerce",
    "merge_metadata",
    "prefs_defaults",
    "bake_header_enabled",
    "is_empty",
    "build_hash",
    "stamp_build_hash",
    "vendor_string",
    "version_string",
    "banner_lines",
    "BUILD_HASH_PLACEHOLDER",
    "DEFAULT_VENDOR",
    "DEFAULT_VERSION",
]

_PLUG = "_metadata"

# Canonical field set. ``authors`` is a list[str]; the rest are free strings.
#
# ``type_id`` pins the compiled node's MTypeId. Normally EMPTY -- ids are derived
# from the node's Class (see toolchain.typeid_registry), which is stable by
# design and therefore makes a clash with a third-party plugin permanent. This is
# the escape hatch from that, and it lives with the node (not in the compile
# dialog) so it round-trips with the .ma/.mpn instead of being retyped per build.
FIELDS = ("authors", "version", "license", "description", "type_id")
_STR_FIELDS = ("version", "license", "description", "type_id")

# Removed field folded into ``license`` on read -- see ``coerce``.
_LEGACY_INTO_LICENSE = "copyright"

# Fields that must NOT fall back to the global defaults. An id is unique per node
# by definition, so inheriting one would hand every node the same MTypeId and
# make each build a pile of probed collisions.
_NO_DEFAULT_FIELDS = ("type_id",)

DEFAULT_VENDOR = "mpynode-native"
DEFAULT_VERSION = "1.0"

# A placeholder token substituted with the real build hash AFTER the generated
# .cpp text is assembled -- so the hash is a deterministic function of the
# (placeholder-bearing) source and can be embedded in both the banner and the
# MFnPlugin version string without a chicken-and-egg dependency.
BUILD_HASH_PLACEHOLDER = "__MPYNODE_BUILD_HASH__"


# ---- Pure helpers. ----
def coerce(meta: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize a raw metadata dict to the canonical shape.

    Missing keys become empty. ``authors`` is always a ``list[str]`` with blank
    entries dropped (a bare string is wrapped into a one-element list); the rest
    are coerced to strings. Never raises."""
    meta = dict(meta or {})
    out: Dict[str, Any] = {}

    authors = meta.get("authors", [])
    if isinstance(authors, str):
        authors = [authors]
    elif not isinstance(authors, (list, tuple)):
        authors = []
    # Drop None (an absent optional) so it can't become the literal author
    # "None"; honors the "blank entries dropped" contract.
    out["authors"] = [str(a).strip() for a in authors
                      if a is not None and str(a).strip()]

    for k in _STR_FIELDS:
        val = meta.get(k, "")
        out[k] = "" if val is None else str(val)

    # ``copyright`` was its own field until it was merged into ``license``. Fold
    # an old value in ABOVE the license text rather than dropping it on read, so
    # a node whose metadata predates the merge keeps its notice.
    legacy = meta.get(_LEGACY_INTO_LICENSE)
    if legacy is not None and str(legacy).strip():
        legacy = str(legacy).rstrip()
        out["license"] = ("%s\n%s" % (legacy, out["license"]) if out["license"]
                          else legacy)

    out["type_id"] = _canon_type_id(out["type_id"])
    return out


def _canon_type_id(raw: str) -> str:
    """Normalize a pinned MTypeId to ``0x%08x`` so ``0x1A2B3``, ``1a2b3`` and
    ``0x0001a2b3`` are one value (they key the same spec, hence the same port-
    cache entry). An unparseable or out-of-range entry is kept VERBATIM: the
    typo stays visible in the Info dialog instead of silently vanishing, and the
    allocator ignores it in favour of the derived id."""
    s = (raw or "").strip()
    if not s:
        return ""
    try:
        val = int(s, 16)
    except Exception:  # noqa: BLE001
        return s
    if val < 0 or val > 0x0007FFFF:
        return s
    return "0x%08x" % val


def is_empty(meta: Dict[str, Any] | None) -> bool:
    """True if a (coerced) metadata dict carries no information."""
    c = coerce(meta)
    return not c["authors"] and not any(c[k] for k in _STR_FIELDS)


def merge_metadata(node_meta: Dict[str, Any] | None,
                   defaults: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge per-node metadata over global defaults: a non-empty per-node field
    wins; an empty per-node field falls back to the default. Pure + total."""
    node = coerce(node_meta)
    base = coerce(defaults)
    out: Dict[str, Any] = {}
    out["authors"] = node["authors"] or base["authors"]
    for k in _STR_FIELDS:
        out[k] = node[k] if k in _NO_DEFAULT_FIELDS else (node[k] or base[k])
    return out


def prefs_defaults() -> Dict[str, Any]:
    """Read global metadata defaults from Node Designer preferences. Lazy +
    best-effort: returns ``{}`` headless or when prefs are unavailable (mirrors
    the lazy ``ui.llm.config`` import used for provider/model). Maps the prefs
    keys to the canonical metadata fields; ``authors`` is split on newlines /
    semicolons (NOT commas, so ``"Last, First"`` survives).

    Lives here rather than in the compile controller because BOTH tiers that
    emit a banner need the same defaults: a node with a blank license would
    otherwise compile with the studio default and bake a .py without it."""
    try:
        from mpynode.ui import preferences as _prefs
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    try:
        import re

        authors = _prefs.get_pref("metadata_default_authors", "") or ""
        if str(authors).strip():
            out["authors"] = [a.strip() for a in re.split(r"[;\n]", str(authors))
                              if a.strip()]
        for key, field in (("metadata_default_version", "version"),
                           ("metadata_default_license", "license")):
            val = _prefs.get_pref(key, "") or ""
            if str(val).strip():
                out[field] = str(val)
    except Exception:
        return {}
    return out


def bake_header_enabled(default: bool = True) -> bool:
    """Should the .py bake mirror this metadata into a header banner?

    Same lazy, best-effort prefs read as ``prefs_defaults``: an unreadable or
    absent preferences module returns ``default`` rather than raising, so a
    headless bake keeps working. Only the .py bake consults this -- the
    compiled tier always embeds its banner, because that is also where the
    MFnPlugin vendor/version and the build hash come from."""
    try:
        from mpynode.ui import preferences as _prefs

        return bool(_prefs.get_pref("metadata_bake_header", default))
    except Exception:  # noqa: BLE001
        return default


def build_hash(text: str) -> str:
    """Deterministic short build identifier: sha256 of ``text`` -> 12 hex."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def stamp_build_hash(text: str) -> Tuple[str, str]:
    """Replace every ``BUILD_HASH_PLACEHOLDER`` in ``text`` with the short
    sha256 of ``text`` (computed over the placeholder-bearing text, so it is a
    deterministic function of the canonical source). Returns ``(stamped, hash)``.
    """
    h = build_hash(text)
    return text.replace(BUILD_HASH_PLACEHOLDER, h), h


def vendor_string(meta: Dict[str, Any] | None,
                  default: str = DEFAULT_VENDOR) -> str:
    """Vendor for ``MFnPlugin`` registration: the joined authors, else the
    default. (Shows in Maya's Plug-in Manager.)

    ``license`` is deliberately NOT consulted, even though the old ``copyright``
    field was: that field named a party, whereas a license block leads with a
    term ("MIT License", "CC BY-SA 4.0"), which makes a poor vendor. A studio
    wanting its name here sets ``metadata_default_authors`` in preferences."""
    c = coerce(meta)
    if c["authors"]:
        return "; ".join(c["authors"])
    return default


def version_string(meta: Dict[str, Any] | None,
                   default: str = DEFAULT_VERSION) -> str:
    """Base version (without the build-hash suffix)."""
    return coerce(meta)["version"] or default


def banner_lines(meta: Dict[str, Any] | None,
                 generator: str = DEFAULT_VENDOR,
                 prefix: str = "//",
                 build: bool = True) -> List[str]:
    """A comment banner block embedding the metadata + a build token.

    Returns a list of line-comment strings, each starting with ``prefix``:
    ``//`` for the C++ tier, ``#`` for the Python bake. The defaults reproduce
    the C++ banner byte-for-byte.

    ``license`` and ``description`` keep the line breaks the author typed (see
    ``_block_lines``) and ``authors`` gets one line each, so the banner is a
    mirror of the Node Info dialog rather than a reflow of it. ``version`` is a
    single-line field in that dialog and stays collapsed.

    ``license`` is the one field emitted VERBATIM, with no ``license:`` label
    and a blank comment line fencing it off. It carries the whole legal block --
    a copyright line, a CC deed, an SPDX id, full terms -- and labelling only
    its first line reads wrong for every one of those.

    The build hash is emitted as ``BUILD_HASH_PLACEHOLDER`` -- the caller stamps
    the real digest via ``stamp_build_hash`` once the full source is assembled.
    Pass ``build=False`` where nothing stamps it (the .py bake has no compile
    step), or the placeholder reaches the file verbatim.

    The banner is ALWAYS emitted, even for empty metadata, so every compiled
    node carries a build identifier. A caller with no build line to justify that
    (again: the .py bake) has nothing left but two bars, so it gates on
    ``is_empty`` first rather than emitting an empty box."""
    c = coerce(meta)
    bar = prefix + " " + "=" * 73
    lines = [bar, "%s Generated by %s." % (prefix, generator)]
    if build:
        lines.append("%s build: %s" % (prefix, BUILD_HASH_PLACEHOLDER))
    if c["version"]:
        lines.append("%s version: %s" % (prefix, _one_line(c["version"])))
    # One labelled line per author: that is how they are typed in Node Info
    # (one per line) and how they are stored (a list), so joining them onto a
    # single line was the one place the banner stopped mirroring the dialog.
    for author in c["authors"]:
        lines.append("%s author(s): %s" % (prefix, _one_line(author)))
    # license / description are the two block fields -- a license text is
    # multi-line by nature -- so they keep the author's own line breaks. The
    # license additionally drops its label and is fenced by blank comment lines;
    # the trailing fence is emitted only when something follows it, so the block
    # never butts a bare prefix against the closing bar.
    if c["license"]:
        lines.append(prefix)
        lines.extend(_block_lines(prefix, None, c["license"]))
        if c["description"]:
            lines.append(prefix)
    if c["description"]:
        lines.extend(_block_lines(prefix, "description", c["description"]))
    lines.append(bar)
    return lines


def _block_lines(prefix: str, label: str | None, value: str) -> List[str]:
    """A field that may span lines: the label on the first, the author's own
    subsequent lines VERBATIM below it, each behind the comment ``prefix``.
    A ``label`` of None labels nothing -- every line is emitted bare, which is
    how the license block is written.

    Collapsing these to one line (what ``_one_line`` does, and what every field
    used to do) is what made a formatted licence or description come out as a
    single unreadable run -- the dialog soft-wraps it, so it looked right there
    and nowhere else.

    Keeping the breaks does NOT weaken the reason ``_one_line`` exists: every
    emitted line carries the prefix, so no value can escape its comment.
    ``splitlines`` covers \\r and \\r\\n too, which a bare ``split("\\n")``
    would leave embedded. Blank lines emit the bare prefix, so the banner never
    carries trailing whitespace."""
    out = []
    for i, raw in enumerate((value or "").splitlines() or [""]):
        head = "%s %s: " % (prefix, label) if (label and i == 0) else prefix + " "
        out.append((head + raw).rstrip())
    return out


def _one_line(s: str) -> str:
    """Collapse newlines/tabs so a value can't break out of a // comment."""
    return " ".join(str(s).split())


# ---- Mixin. ----
class MetadataMixin:
    """Adds ``set_metadata`` / ``get_metadata`` / ``has_metadata`` /
    ``clear_metadata`` to any wrapper with a ``self._name``. Persists a JSON blob
    on a hidden ``_metadata`` string plug (parity with ``_methodsSource``) so it
    round-trips with the .ma. Adds no ``__init__`` and creates the plug lazily so
    nodes that never set metadata are unchanged."""

    def set_metadata(self, meta: Dict[str, Any]) -> bool:
        """Persist ``meta`` (coerced to the canonical shape). Returns True on
        success, False (with a stderr note) if the plug write fails."""
        from maya import cmds

        payload = json.dumps(coerce(meta), sort_keys=True)
        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            cmds.addAttr(self._name, longName=_PLUG, dataType="string",
                         hidden=True)
        try:
            cmds.setAttr("%s.%s" % (self._name, _PLUG), payload, type="string")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(
                "[metadata_registry] set_metadata failed on %r: %s\n"
                % (self._name, exc))
            return False
        return True

    def get_metadata(self) -> Dict[str, Any]:
        """Return the node's metadata as a coerced dict (empty shape if unset or
        malformed). Never raises."""
        from maya import cmds

        if not cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            return coerce(None)
        try:
            raw = cmds.getAttr("%s.%s" % (self._name, _PLUG)) or ""
        except Exception:  # noqa: BLE001
            return coerce(None)
        if not raw:
            return coerce(None)
        try:
            return coerce(json.loads(raw))
        except Exception:  # noqa: BLE001
            return coerce(None)

    def has_metadata(self) -> bool:
        return not is_empty(self.get_metadata())

    def clear_metadata(self) -> None:
        from maya import cmds

        if cmds.attributeQuery(_PLUG, node=self._name, exists=True):
            try:
                cmds.setAttr("%s.%s" % (self._name, _PLUG), "", type="string")
            except Exception:  # noqa: BLE001
                pass
