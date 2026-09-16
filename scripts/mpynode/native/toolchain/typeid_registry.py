"""MTypeId assignment for native MPyNode plugins -- deterministic, file-free.

Maya requires every node type registered in a process to carry a UNIQUE
``MTypeId``; a duplicate makes the *second* ``registerNode`` fail outright. And
because a ``.mb`` scene bakes the **id** (a ``.ma`` stores the type NAME), an id
that changes between rebuilds silently turns every saved instance into an
unknown node. So the two properties that actually matter are **uniqueness** and
**stability**.

An id is therefore DERIVED, not allocated::

    id = base + sha256(key) % (end - base + 1)

Same Class -> same id, on every machine, forever, with no file to read, no file
to write, and no shared mutable state to lock. A missing, unwritable or
read-only home cannot fail a compile any more -- which is the whole point,
because the previous per-user registry file made the id allocator the single
most fragile step in the build.

Three sources feed an id, most specific first:

  1. **a manual pin** -- ``type_id`` in the node's metadata, set in Node Designer's
     Node Info dialog. Round-trips with the ``.ma``/``.mpn``, so it is the escape
     hatch when a derived id ever clashes with a third-party plugin (a derived
     id is stable BY DESIGN, so such a clash would otherwise be permanent).
  2. **a pin file** -- the legacy ``typeid_registry.json``, READ if it happens to
     exist so ids already shipped keep working. Never written by a compile.
  3. **the derived id**, probed forward on the rare in-bundle hash collision.

Collisions: the pool is ~458k ids, so a hash clash inside one bundle is remote
but not impossible. When it happens the later key probes forward to the next
free id and the fact is recorded in ``collisions`` (and the build manifest) --
detected and reported, never silent.

The legacy scheme -- which this replaces -- hashed the node NAME into a 19-bit
range with no probing, which is the real numba/bspline clash and the
``node_id + 1`` matrix-id bug found in the 2026-06-07 audit. The difference is
not "hashing" but the range width plus collision detection.

The optional pin file stays human-readable::

    {
      "base": "0x00010000",
      "map": {"besselField": "0x0001a2b3", "rbfSolve": "0x00042f01"}
    }
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, Iterable, List, Optional, Tuple


# Maya's documented free/internal MTypeId range is 0x00000000-0x0007ffff. We
# derive ids by hashing, so the pool wants to be as WIDE as possible: collision
# probability is quadratic in the node count and linear in 1/span. 0x00010000
# upward gives 458752 ids (~0.3% chance of one clash across 50 nodes, and the
# clash is detected + probed, not silent). Overridable via [typeid] base/end in
# mpynode.ini -- set it if you have your own Autodesk-allocated block.
DEFAULT_BASE = 0x00010000
RANGE_END    = 0x0007FFFF

_ENV_PATH = "MPYNODE_TYPEID_REGISTRY"


def configured_base() -> int:
    from mpynode._common import bootstrap
    return bootstrap.get_int("typeid", "base", DEFAULT_BASE)


def configured_end() -> int:
    from mpynode._common import bootstrap
    return bootstrap.get_int("typeid", "end", RANGE_END)


def default_registry_path() -> str:
    """Path of the OPTIONAL pin file, overridable via ``MPYNODE_TYPEID_REGISTRY``
    or ``[paths] typeid_pins``. The file does not have to exist.

    ``ensure_home()`` rather than ``home_dir()``: it runs the one-time COPY of the
    legacy hidden ``~/.mpynode``, so a returning user's already-shipped ids are
    found here rather than abandoned. Same return value, guarded by home's
    ``_ensured`` flag so repeat calls stay cheap.
    """
    override = os.environ.get(_ENV_PATH)
    if override:
        return override
    from mpynode._common import home
    home.ensure_home()
    return home.typeid_pins_path()


def _as_int(hex_or_int) -> int:
    if isinstance(hex_or_int, int):
        return hex_or_int
    return int(str(hex_or_int), 16)


def _as_hex(value: int) -> str:
    return "0x%08x" % value


def deterministic_id(key: str, base: int | None = None,
                     end: int | None = None) -> int:
    """The id ``key`` derives to. A pure function -- no state, no I/O.

    sha256 (not ``hash()``, which is salted per process and would make ids
    differ between Maya sessions) folded into ``[base, end]``."""
    base   = configured_base() if base is None else int(base)
    end    = configured_end() if end is None else int(end)
    span   = max(1, end - base + 1)
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    return base + (int(digest, 16) % span)


class TypeIdRegistry:
    """Resolves node keys to MTypeIds for ONE build.

    An instance is the bundle's scope: it remembers what it has handed out so
    two nodes in the same plugin can never collide, and it consults the optional
    pin file exactly once. Nothing here writes to disk during a compile -- see
    ``write_pins`` for the explicit, opt-in freeze.
    """

    def __init__(self, path: str | None = None, base: int | None = None,
                 end: int | None = None):
        self._path = path
        self.base  = configured_base() if base is None else int(base)
        self.end   = configured_end() if end is None else int(end)
        self._file_pins: Optional[Dict[str, int]] = None  # lazy, read-once
        self._manual:    Dict[str, int] = {}              # metadata pins
        self._issued:    Dict[str, int] = {}              # key -> id, this run
        self._used:      Dict[int, str] = {}              # id -> key, this run
        self.sources:    Dict[str, str] = {}              # key -> how it got it
        self.collisions: List[Tuple[str, int, int]] = []  # (key, wanted, got)

    @property
    def path(self) -> str:
        """Pin-file path, resolved lazily so merely constructing a registry
        touches no home directory (headless callers construct one eagerly)."""
        if self._path is None:
            self._path = default_registry_path()
        return self._path

    # -- pin sources ---------------------------------------------------------

    def _pins(self) -> Dict[str, int]:
        """The legacy pin file, read once. Absent/unreadable/corrupt -> ``{}``:
        this file is an override, and its absence is the normal case."""
        if self._file_pins is not None:
            return self._file_pins
        pins: Dict[str, int] = {}
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            for nm, hx in (doc.get("map") or {}).items():
                try:
                    pins[str(nm)] = _as_int(hx)
                except Exception:  # noqa: BLE001 -- skip a bad entry, keep the rest
                    continue
        except Exception:  # noqa: BLE001 -- missing file is the normal case
            pins = {}
        self._file_pins = pins
        return pins

    def pin(self, name: str, value) -> Optional[int]:
        """Force ``name`` to a specific id for this build (the node-metadata
        ``type_id``). Highest precedence. Returns the parsed id, or ``None`` if
        the value is unusable or out of Maya's range -- a bad pin is ignored in
        favour of the derived id rather than failing the build."""
        if value is None or not str(value).strip():
            return None
        try:
            val = _as_int(str(value).strip())
        except Exception:  # noqa: BLE001
            return None
        if val < 0 or val > 0x0007FFFF:
            return None
        self._manual[str(name)] = val
        return val

    def seed(self, mapping: Dict[str, str]) -> None:
        """Bulk-``pin`` from an external map (e.g. a project-local pin file).
        In-memory only; existing pins win."""
        for nm, hx in (mapping or {}).items():
            if nm not in self._manual:
                self.pin(nm, hx)

    # -- resolution ----------------------------------------------------------

    def _claim(self, name: str, wanted: int, source: str) -> int:
        """Take ``wanted`` for ``name``, or the next free id after it. Probing
        wraps inside [base, end] so a value near the top of the block can't run
        off the end."""
        span  = max(1, self.end - self.base + 1)
        got   = wanted
        steps = 0
        while got in self._used and steps < span:
            got = self.base + ((got - self.base + 1) % span)
            steps += 1
        if steps >= span:
            raise RuntimeError(
                "MTypeId pool exhausted (base=%s..%s); configure a larger "
                "[typeid] base/end block in mpynode.ini."
                % (_as_hex(self.base), _as_hex(self.end)))
        if got != wanted:
            self.collisions.append((name, wanted, got))
            source = "%s+probed" % source
        self._issued[name] = got
        self._used[got]    = name
        self.sources[name] = source
        return got

    def allocate(self, name: str) -> str:
        """Return the hex MTypeId for ``name``. Idempotent within a build."""
        return self.allocate_many([name])[name]

    def allocate_many(self, names: Iterable[str]) -> Dict[str, str]:
        """Resolve several keys in one go (keeps a node + its companion classes
        -- e.g. a transform's matrix -- resolved together).

        Order within a build is the caller's, and the caller's node order is
        itself deterministic, so repeat builds of the same set agree.
        """
        out: Dict[str, str] = {}
        for nm in dict.fromkeys(names):  # de-dupe, preserve order
            if nm in self._issued:
                out[nm] = _as_hex(self._issued[nm])
                continue
            if nm in self._manual:
                out[nm] = _as_hex(self._claim(nm, self._manual[nm], "pinned"))
                continue
            file_pin = self._pins().get(nm)
            if file_pin is not None:
                out[nm] = _as_hex(self._claim(nm, file_pin, "pin-file"))
                continue
            wanted  = deterministic_id(nm, self.base, self.end)
            out[nm] = _as_hex(self._claim(nm, wanted, "derived"))
        return out

    # -- introspection -------------------------------------------------------

    def get(self, name: str) -> str:
        """The id ``name`` WOULD get, without claiming it. Pure preview -- used
        by the UI to show the derived id as a placeholder."""
        if name in self._issued:
            return _as_hex(self._issued[name])
        if name in self._manual:
            return _as_hex(self._manual[name])
        file_pin = self._pins().get(name)
        if file_pin is not None:
            return _as_hex(file_pin)
        return _as_hex(deterministic_id(name, self.base, self.end))

    def export_map(self) -> Dict[str, str]:
        """The ids actually issued this build, ready to be frozen into a pin
        file."""
        return {nm: _as_hex(val) for nm, val in sorted(self._issued.items())}

    def write_pins(self, path: str | None = None) -> str:
        """Freeze this build's ids into a pin file. EXPLICIT and opt-in -- no
        compile calls this, so the build never depends on a writable home."""
        target = path or self.path
        d      = os.path.dirname(target)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        doc = {"base": _as_hex(self.base), "map": self.export_map()}
        tmp = target + ".tmp-%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, target)  # atomic on POSIX
        return target


# Module-level convenience. Each call builds a throwaway registry: without a
# shared file there is no cross-call state to preserve, and a derived id is the
# same every time anyway.
def allocate(name: str) -> str:
    return TypeIdRegistry().allocate(name)


def allocate_many(names: Iterable[str]) -> Dict[str, str]:
    return TypeIdRegistry().allocate_many(names)
