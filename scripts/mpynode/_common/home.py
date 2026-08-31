"""Central per-user MPyNode data home.

Everything MPyNode writes for a user -- preferences, the port cache, the global
type-id registry, and default compiled-plugin output -- lives under ONE VISIBLE
directory so nothing is hidden from a first-time user::

    ~/mpynode/                 (the default -- NOT hidden, no leading dot)
      preferences.json
      typeid_registry.json
      trusted.json
      port_cache/
      compiled/<plugin>/

Each of those locations resolves independently, most specific first:

  1. its env var (``MPYNODE_HOME``, ``MPYNODE_PORT_CACHE``, ...)
  2. the install's ``mpynode.ini`` (see :mod:`mpynode._common.bootstrap`)
  3. the built-in default -- a subpath of the home

The port cache alone has a fourth level, a per-user PREFERENCE, slotted between
1 and 2 -- see :func:`port_cache_dir`. Every default here is OS-native by
construction: ``expanduser("~")`` yields ``C:\\Users\\<user>`` on Windows,
``/Users/<user>`` on macOS and ``/home/<user>`` on Linux, so no platform ever
inherits another's layout.

So a studio can relocate just the compile output, or the whole home, by editing
ONE file that ships next to the code, while env vars keep overriding everything
for tests and one-off harness runs.

Historically this lived in the HIDDEN ``~/.mpynode``; on first use of the DEFAULT
home we COPY that legacy dir across (never move) so a returning user keeps their
type-id pins -- ``.mb`` scenes bake those MTypeIds -- while the old hidden dir
stays put as a backup.

Maya-/Qt-free and import-cheap so every writer (``ui.preferences``,
``toolchain.port_cache``, ``toolchain.typeid_registry``, the compile dialog) can
share it.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Optional

from mpynode._common import bootstrap

HOME_ENV = "MPYNODE_HOME"

_DEFAULT_DIRNAME = "mpynode"
_LEGACY_DIRNAME = ".mpynode"

# One-time guard so ensure_home()'s migration + makedirs run at most once per
# process (path resolution stays cheap thereafter).
_ensured = False


def _default_home() -> str:
    return os.path.join(os.path.expanduser("~"), _DEFAULT_DIRNAME)


def legacy_home_dir() -> str:
    """The old HIDDEN home (``~/.mpynode``) we migrate away from."""
    return os.path.join(os.path.expanduser("~"), _LEGACY_DIRNAME)


def home_dir() -> str:
    """The MPyNode data home: ``MPYNODE_HOME``, else ``[paths] home`` from the
    install's ``mpynode.ini``, else the visible ``~/mpynode``. A PURE path -- no
    filesystem side effects."""
    return (os.environ.get(HOME_ENV)
            or bootstrap.path("home")
            or _default_home())


def _under_home(option: str, env: str, *leaf: str) -> str:
    """Resolve one configurable location: its env var, else the matching
    ``[paths]`` entry, else ``<home>/<leaf>``. The three-level order is the same
    for every location, so it lives here once."""
    return (os.environ.get(env)
            or bootstrap.path(option)
            or os.path.join(home_dir(), *leaf))


def preferences_path() -> str:
    """Node Designer's ``preferences.json``."""
    return _under_home("preferences", "MPYNODE_PREFS", "preferences.json")


def trust_store_path() -> str:
    """The pickle-trust store consulted on scene open/import (a SECURITY
    control, not a compile artifact -- see ``_common.io.trust``)."""
    return _under_home("trust_store", "MPYNODE_TRUST_STORE", "trusted.json")


def typeid_pins_path() -> str:
    """Optional MTypeId pin table. Ids are derived deterministically from the
    node's Class, so this file is a pure OVERRIDE -- absent is the normal case
    and never blocks a compile (see ``toolchain.typeid_registry``)."""
    return _under_home("typeid_pins", "MPYNODE_TYPEID_REGISTRY",
                       "typeid_registry.json")


def port_cache_dir() -> str:
    """Where the AI porter's translated C++ is cached.

    The ONE location with a user-facing preference (Preferences -> Locations),
    so it resolves FOUR deep rather than three::

        MPYNODE_PORT_CACHE  ->  the preference  ->  [paths] port_cache  ->  default

    The preference sits ABOVE the ini because a per-user choice is more specific
    than an install-wide one -- a studio's ini is the fallback for artists who
    have not set anything -- and BELOW env so tests, CI and harness scripts keep
    overriding everything exactly as before.

    Only the cache gets this. The other five stay ini-only: ``home`` in
    particular carries ``trusted.json`` (moving it resets pickle trust, so
    previously-trusted scenes fail closed) and ``typeid_registry.json``
    (MTypeIds baked into saved ``.mb`` scenes), and ``preferences.json`` lives
    under it -- a home field in the prefs dialog would relocate the file the
    dialog just wrote itself into.

    The import is function-local and guarded: ``ui.preferences`` imports THIS
    module at module scope for ``PREFS_PATH``, so importing it back at module
    scope would be circular, and path resolution must keep working even where
    the UI package cannot be imported at all."""
    env = os.environ.get("MPYNODE_PORT_CACHE")
    if env:
        return env
    try:
        from mpynode.ui import preferences

        pref = preferences.port_cache_dir_pref()
    except Exception:  # noqa: BLE001 -- never let the UI break path resolution
        pref = ""
    if pref:
        return pref
    return _under_home("port_cache", "MPYNODE_PORT_CACHE", "port_cache")


def compiled_dir() -> str:
    """Default parent folder for compiled plugin output."""
    return _under_home("compiled", "MPYNODE_COMPILED", "compiled")


def migrate_legacy_home() -> Optional[str]:
    """One-time COPY of the legacy hidden ``~/.mpynode`` into the new visible
    ``~/mpynode``. Returns the new path if it copied, else ``None``.

    Only ever touches the DEFAULT home: an explicit ``MPYNODE_HOME`` override
    manages its own directory (and keeps tests isolated). Never overwrites an
    existing new home, and COPIES (leaving the old dir as a backup) so the
    type-id registry -- baked into saved scenes as MTypeIds -- survives verbatim.
    Best-effort: any copy failure returns ``None`` and leaves the legacy dir the
    single source of truth (no half state to reason about).
    """
    if os.environ.get(HOME_ENV):
        return None
    new = _default_home()
    old = legacy_home_dir()
    if os.path.isdir(new):
        return None          # already have a home -> never clobber it
    if not os.path.isdir(old):
        return None          # fresh install -> nothing to migrate
    try:
        shutil.copytree(old, new)
    except Exception:
        return None
    return new


def ensure_home() -> str:
    """Return the home dir, running the one-time legacy migration + ``makedirs``
    on first call (guarded so repeated calls are cheap). Call this at real
    entry points (plugin/designer startup, a headless compile) so a returning
    user's data is migrated before the first read/allocate."""
    global _ensured
    d = home_dir()
    if _ensured:
        return d
    migrate_legacy_home()
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as exc:  # noqa: BLE001
        # Still return the path (callers that only READ must keep working), but
        # SAY SO. Swallowing this silently is how an unwritable home surfaced as
        # an unrelated failure deep inside a build, at the first write, instead
        # of here where the cause is obvious and the remedy is one line.
        sys.stderr.write(
            "[mpynode.home] cannot create the MPyNode home %r: %s\n"
            "  Anything MPyNode writes there will fail. Point it somewhere\n"
            "  writable via the MPYNODE_HOME env var, or set [paths] home in\n"
            "  %s\n"
            % (d, exc, bootstrap.config_path() or bootstrap._package_config()))
    _ensured = True
    return d


def _reset_for_tests() -> None:
    """Clear the one-time guard so tests can re-exercise ensure_home()/migration
    with a fresh ``$HOME``/``MPYNODE_HOME``."""
    global _ensured
    _ensured = False
