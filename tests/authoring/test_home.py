"""The central per-user data home (``mpynode._common.home``).

Everything MPyNode writes for a user (preferences, port cache, type-id registry,
default compiled output) lives under ONE directory -- ``~/.mpynode`` by default,
overridable with ``MPYNODE_HOME``.

These tests drive a throwaway home (``$HOME`` on unix, ``%USERPROFILE%`` on
Windows -- ``expanduser("~")`` reads a different variable on each) so nothing
touches the real home."""

from __future__ import annotations

import os
import tempfile
import unittest


class _FakeHome:
    """Context manager: point ``$HOME`` at a fresh temp dir and clear
    ``MPYNODE_HOME`` so home resolution exercises the DEFAULT path.
    Restores both on exit."""

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="mpynode-home-test-")
        for k in ("HOME", "MPYNODE_HOME", "USERPROFILE"):
            self._saved[k] = os.environ.get(k)
        os.environ["HOME"] = self.dir
        # ntpath.expanduser reads USERPROFILE and IGNORES HOME, so setting only
        # HOME left every test in this file resolving against the REAL home on
        # Windows. MEASURED 2026-08-14: home_dir() returned
        # C:\Users\<user>\mpynode instead of the temp dir, failing 8 tests here
        # and never exercising the throwaway home at all. posixpath.expanduser
        # ignores USERPROFILE, so setting both keeps ONE path for both.
        os.environ["USERPROFILE"] = self.dir
        os.environ.pop("MPYNODE_HOME", None)
        from mpynode._common import home
        home._reset_for_tests()
        return self.dir

    def __exit__(self, *exc):
        from mpynode._common import home
        home._reset_for_tests()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestHomeDir(unittest.TestCase):
    def test_default_is_dot_mpynode(self):
        from mpynode._common import home
        with _FakeHome() as h:
            got = home.home_dir()
            self.assertEqual(got, os.path.join(h, ".mpynode"))

    def test_env_override_wins(self):
        from mpynode._common import home
        with _FakeHome():
            os.environ["MPYNODE_HOME"] = "/tmp/custom-mpy-home"
            try:
                self.assertEqual(home.home_dir(), "/tmp/custom-mpy-home")
            finally:
                os.environ.pop("MPYNODE_HOME", None)

    def test_home_dir_is_pure_no_side_effects(self):
        from mpynode._common import home
        with _FakeHome() as h:
            home.home_dir()
            # Merely asking for the path must not create it.
            self.assertFalse(os.path.exists(os.path.join(h, ".mpynode")))


class TestEnsureHome(unittest.TestCase):
    def test_creates_home(self):
        from mpynode._common import home
        with _FakeHome() as h:
            d = home.ensure_home()
            self.assertEqual(d, os.path.join(h, ".mpynode"))
            self.assertTrue(os.path.isdir(d))


class TestSitesUseHome(unittest.TestCase):
    """Every default per-user path lands under the ``~/.mpynode`` home -- never
    the retired visible ``~/mpynode`` -- while each site keeps its own explicit
    env override."""

    _OLD_VISIBLE = os.sep + "mpynode" + os.sep

    def test_port_cache_default_under_home(self):
        from mpynode.native.toolchain import port_cache
        with _FakeHome() as h:
            saved = os.environ.pop("MPYNODE_PORT_CACHE", None)
            try:
                d = port_cache.cache_dir()
            finally:
                if saved is not None:
                    os.environ["MPYNODE_PORT_CACHE"] = saved
            self.assertEqual(d, os.path.join(h, ".mpynode", "port_cache"))
            self.assertNotIn(self._OLD_VISIBLE, d)

    def test_typeid_registry_default_under_home(self):
        from mpynode.native.toolchain import typeid_registry
        with _FakeHome() as h:
            saved = os.environ.pop("MPYNODE_TYPEID_REGISTRY", None)
            try:
                p = typeid_registry.default_registry_path()
            finally:
                if saved is not None:
                    os.environ["MPYNODE_TYPEID_REGISTRY"] = saved
            self.assertEqual(
                p, os.path.join(h, ".mpynode", "typeid_registry.json"))
            self.assertNotIn(self._OLD_VISIBLE, p)

    def test_compile_dialog_default_out_dir_under_home(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        class _F:
            _scene_nodes = [("metaClay1", "mPyMesh")]

        with _FakeHome() as h:
            out = CompileDialog._default_out_dir(_F())
            self.assertTrue(
                out.startswith(os.path.join(h, ".mpynode", "compiled")))
            self.assertNotIn(self._OLD_VISIBLE, out)

    def test_trust_store_default_under_home(self):
        from mpynode._common.io import trust
        with _FakeHome() as h:
            saved = os.environ.pop("MPYNODE_TRUST_STORE", None)
            try:
                p = trust._store_path()
            finally:
                if saved is not None:
                    os.environ["MPYNODE_TRUST_STORE"] = saved
            self.assertEqual(p, os.path.join(h, ".mpynode", "trusted.json"))
            self.assertNotIn(self._OLD_VISIBLE, p)

    def test_preferences_default_under_home(self):
        from mpynode._common import home
        with _FakeHome() as h:
            saved = os.environ.pop("MPYNODE_PREFS", None)
            try:
                p = home.preferences_path()
            finally:
                if saved is not None:
                    os.environ["MPYNODE_PREFS"] = saved
            self.assertEqual(p, os.path.join(h, ".mpynode", "preferences.json"))
            self.assertNotIn(self._OLD_VISIBLE, p)

    def test_designer_triggers_ensure_home(self):
        import inspect
        from mpynode.ui import mpynode_designer
        src = inspect.getsource(mpynode_designer.NDMainWindow.__init__)
        self.assertIn("ensure_home", src)


class TestPortCachePrecedence(unittest.TestCase):
    """``port_cache_dir()`` is the ONE location with FOUR levels::

        MPYNODE_PORT_CACHE -> the preference -> [paths] port_cache -> default

    The preference sits above the ini (a per-user choice is more specific than
    an install-wide one) and below env (so tests / CI / harness scripts keep
    overriding everything). The other five resolvers are untouched.
    """

    def _pref(self, value):
        """Patch the port-cache PREFERENCE, without touching a prefs file."""
        from unittest import mock
        from mpynode.ui import preferences

        return mock.patch.object(
            preferences, "port_cache_dir_pref", lambda: value)

    def _no_env(self):
        from unittest import mock

        env = dict(os.environ)
        env.pop("MPYNODE_PORT_CACHE", None)
        return mock.patch.dict(os.environ, env, clear=True)

    def test_env_beats_the_preference(self):
        from unittest import mock
        from mpynode._common import home

        with _FakeHome():
            with mock.patch.dict(os.environ,
                                 {"MPYNODE_PORT_CACHE": os.sep + "from_env"}):
                with self._pref(os.sep + "from_pref"):
                    self.assertEqual(home.port_cache_dir(),
                                     os.sep + "from_env")

    def test_the_preference_beats_the_default(self):
        from mpynode._common import home

        with _FakeHome():
            with self._no_env(), self._pref(os.sep + "from_pref"):
                self.assertEqual(home.port_cache_dir(), os.sep + "from_pref")

    def test_a_blank_preference_falls_through_to_the_default(self):
        from mpynode._common import home

        with _FakeHome() as h:
            with self._no_env(), self._pref(""):
                self.assertEqual(home.port_cache_dir(),
                                 os.path.join(h, ".mpynode", "port_cache"))

    def test_an_unimportable_ui_never_breaks_resolution(self):
        """home.py must stay usable where the UI package cannot be imported --
        the import is function-local AND guarded for exactly this."""
        import sys
        from unittest import mock
        from mpynode._common import home

        with _FakeHome() as h:
            with self._no_env(), mock.patch.dict(
                    sys.modules, {"mpynode.ui.preferences": None}):
                self.assertEqual(home.port_cache_dir(),
                                 os.path.join(h, ".mpynode", "port_cache"))

    def test_the_other_locations_did_not_gain_the_preference_level(self):
        """Only the cache is overridable. home carries trusted.json and the
        type-id pins, so it stays ini-only."""
        from mpynode._common import home

        with _FakeHome() as h:
            with self._no_env(), self._pref(os.sep + "from_pref"):
                self.assertEqual(home.home_dir(),
                                 os.path.join(h, ".mpynode"))
                self.assertEqual(home.trust_store_path(),
                                 os.path.join(h, ".mpynode", "trusted.json"))
                self.assertEqual(home.compiled_dir(),
                                 os.path.join(h, ".mpynode", "compiled"))


class TestDefaultsAreOSNative(unittest.TestCase):
    """No platform inherits another's layout: every default hangs off
    ``expanduser("~")``, which reads USERPROFILE on Windows and HOME on
    POSIX."""

    def test_default_home_is_under_the_real_user_home(self):
        from mpynode._common import home

        with _FakeHome() as h:
            self.assertEqual(home.home_dir(), os.path.join(h, ".mpynode"))

    def test_no_foreign_separator_or_drive_in_the_default(self):
        from mpynode._common import home

        with _FakeHome():
            d = home.home_dir()
            if os.name == "nt":
                # Must not look like a POSIX absolute path.
                self.assertFalse(d.startswith("/"), d)
            else:
                # Must not carry a drive letter or a UNC prefix.
                self.assertFalse(
                    len(d) >= 2 and d[0].isalpha() and d[1] == ":", d)
                self.assertFalse(d.startswith("\\\\"), d)


if __name__ == "__main__":
    unittest.main()
