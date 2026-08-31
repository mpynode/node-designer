"""Per-node-type *tier starter* registry.

Maps a native node type + a source tier to the working starter code that tier
should be seeded with on a Designer virgin-create. The empty-tier seeder in
:mod:`mpynode._base.commands` consults this BEFORE falling back to the generic
commented header, so a registered type gets runnable default code while every
unregistered type behaves exactly as before (header-only / blank).

Design notes:
 * One source of truth. mPyFile's starters point at the SAME
   ``_defaults.file_defaults`` constants the wrapper ``create()`` seeds, so the
   plain-left-click path and the programmatic path can never drift.
 * Additive + guarded. The consulting seeder only writes EMPTY tiers, so a
   populated tier (a merged setup source, a wrapper-``create()`` seed, or any
   user text) is never clobbered.
 * Scope. This is the Designer "headers" create behavior; the wrapper API /
   ``.mpn`` import paths never invoke the seeder, matching existing scoping.
"""
from __future__ import annotations

# Canonical tier identifiers (match the source tiers the seeder walks).
TIER_INIT = "init"
TIER_COMPUTE = "compute"
TIER_VIEWPORT = "viewport"
TIER_OSL = "osl"
TIER_METHODS = "methods"


def _build_registry() -> dict:
    """Assemble the registry lazily so importing this module never forces the
    per-type default modules to import (and their transitive deps) unless a
    lookup actually happens for that type."""
    from mpynode._defaults import file_defaults, skin_cluster_defaults

    return {
        "mPyFile": {
            TIER_INIT: file_defaults.DEFAULT_INIT_SOURCE,
            TIER_COMPUTE: file_defaults.DEFAULT_COMPUTE_SOURCE,
            TIER_VIEWPORT: file_defaults.DEFAULT_VIEWPORT_SOURCE,
        },
        "mPySkinCluster": {
            TIER_INIT: skin_cluster_defaults.DEFAULT_INIT_SOURCE,
            TIER_COMPUTE: skin_cluster_defaults.DEFAULT_COMPUTE_SOURCE,
        },
    }


def registered_types() -> tuple:
    """Native types that ship at least one tier starter."""
    return tuple(_build_registry().keys())


def starter_source(native_type: str, tier: str) -> str | None:
    """Return the starter source for ``(native_type, tier)`` or ``None`` if the
    type declares no starter for that tier. ``native_type`` is matched exactly
    (case-sensitive), mirroring the node-setups convention."""
    return _build_registry().get(native_type, {}).get(tier)
