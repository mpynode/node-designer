"""The ONE file that tells Node Designer where everything else lives.

Every other location MPyNode writes to -- the data home, preferences, the port
cache, the type-id pin file, compiled plugin output -- is derived from a single
``mpynode.ini`` that sits NEXT TO THE CODE, at the top of the ``mpynode``
package::

    scripts/mpynode/mpynode.ini

That path is fixed by the install itself and needs no environment to find, which
makes it the one thing that is always locatable: the code has to be importable
for anything to run at all, so the config is reachable by construction. The file
only ever POINTS at other places -- it stores no state -- so a read-only or
network install is perfectly fine (and is the expected case for a studio, where
a TD sets it once for everyone).

Resolution order for every value, most specific first:

  1. the environment variable (``MPYNODE_HOME``, ``MPYNODE_PORT_CACHE``, ...)
  2. ``mpynode.ini``
  3. the built-in default (``~/mpynode/...``)

Env stays on top so tests, CI and one-off harness scripts keep working exactly
as before; a missing or unreadable ini means every value falls through to the
built-in default, so this module is purely additive.

Format is INI (``configparser``) rather than TOML because Maya 2024 ships Python
3.10 and ``tomllib`` only landed in 3.11 -- INI is stdlib on both, takes
comments, and is the one file a human is expected to hand-edit.

Values in ``[paths]`` get ``~`` and ``$VAR`` expanded, and a RELATIVE path is
resolved against the directory holding the ini -- so a self-contained checkout
can point at ``../../.mpynode_local`` and stay portable.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

CONFIG_ENV  = "MPYNODE_CONFIG"
CONFIG_NAME = "mpynode.ini"

# Parsed once per process: the config is a static description of the install,
# and re-reading it per path lookup would put a stat() on every prefs access.
_loaded = False
_parser = None          # configparser.ConfigParser | None
_path: Optional[str] = None
_base: Optional[str] = None   # dir the ini lives in -- relative paths hang off it


def _package_config() -> str:
    """``<mpynode package>/mpynode.ini`` -- the canonical location."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        CONFIG_NAME)


def config_path() -> Optional[str]:
    """Absolute path of the ini actually in force, or ``None`` when running on
    built-in defaults. ``MPYNODE_CONFIG`` overrides the package location."""
    _load()
    return _path


def _load() -> None:
    global _loaded, _parser, _path, _base
    if _loaded:
        return
    _loaded   = True
    candidate = os.environ.get(CONFIG_ENV) or _package_config()
    if not os.path.isfile(candidate):
        return
    try:
        import configparser

        parser = configparser.ConfigParser()
        with open(candidate, "r") as fh:
            parser.read_file(fh)
    except Exception as exc:  # noqa: BLE001
        # A broken ini must never stop Node Designer from starting -- fall all
        # the way through to built-in defaults, but say so: silently ignoring it
        # is how you end up debugging a path that "should" have been redirected.
        sys.stderr.write("[mpynode.bootstrap] ignoring unreadable %s: %s\n"
                         % (candidate, exc))
        return
    _parser = parser
    _path   = os.path.abspath(candidate)
    _base   = os.path.dirname(_path)


def get(section: str, option: str, default=None):
    """Raw string value from the ini, or ``default``. Never raises."""
    _load()
    if _parser is None:
        return default
    try:
        if _parser.has_option(section, option):
            val = _parser.get(section, option)
            return val if val is not None else default
    except Exception:  # noqa: BLE001 -- interpolation errors etc.
        return default
    return default


def path(option: str, default=None) -> Optional[str]:
    """A ``[paths]`` entry, ``~``/``$VAR``-expanded and made absolute against the
    ini's own directory. Blank entries read as unset (so a value can be commented
    out by emptying it). Returns ``default`` when there is no usable value."""
    raw = get("paths", option, None)
    if raw is None or not str(raw).strip():
        return default
    return _resolve(str(raw).strip())


def _resolve(raw: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(raw))
    if not os.path.isabs(expanded) and _base:
        expanded = os.path.normpath(os.path.join(_base, expanded))
    return expanded


def get_int(section: str, option: str, default=None):
    """An int from the ini, accepting ``0x``-prefixed hex (the type-id base is
    naturally written that way). Returns ``default`` if absent or unparseable."""
    raw = get(section, option, None)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip(), 0)
    except Exception:  # noqa: BLE001
        sys.stderr.write("[mpynode.bootstrap] bad integer for [%s] %s = %r\n"
                         % (section, option, raw))
        return default


def _reset_for_tests() -> None:
    """Drop the parsed config so a test can point ``MPYNODE_CONFIG`` somewhere
    else and re-resolve."""
    global _loaded, _parser, _path, _base
    _loaded = False
    _parser = None
    _path   = None
    _base   = None
