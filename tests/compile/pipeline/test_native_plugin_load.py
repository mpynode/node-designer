"""``load_or_reload_native_plugin`` must load a freshly-compiled native plugin
into the CURRENT Maya session WITHOUT touching the scene, and -- crucially for
the recompile-iterate workflow -- UNLOAD an already-loaded same-named plugin
first so the new code actually takes effect (the old plain ``load-if-absent``
guard silently kept stale code).

It must also degrade gracefully when ``unloadPlugin`` fails (Maya raises if any
node instance of a type the plugin registers still exists in the scene): surface
a clear error string instead of crashing, and NEVER raise.

Tested with a fake ``cmds`` injected over the module global so the load / unload
/ reload SEQUENCE and the nodes-in-use failure path are exercised deterministically
without a real compiled bundle.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import tempfile
import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


class _FakeCmds:
    """Records calls; models pluginInfo/loadPlugin/unloadPlugin state."""

    def __init__(self, loaded=False, unload_raises=False, load_raises=False,
                 load_silently_fails=False):
        self._loaded = loaded
        self._unload_raises = unload_raises
        self._load_raises = load_raises
        # Model Maya SWALLOWING a kFailure from initializePlugin: loadPlugin
        # returns WITHOUT raising but leaves the plugin UNLOADED.
        self._load_silently_fails = load_silently_fails
        self.calls = []

    def pluginInfo(self, name, q=False, loaded=False):
        self.calls.append(("pluginInfo", name))
        return self._loaded

    def unloadPlugin(self, name):
        self.calls.append(("unloadPlugin", name))
        if self._unload_raises:
            raise RuntimeError("plugin has nodes in the scene")
        self._loaded = False

    def loadPlugin(self, path):
        self.calls.append(("loadPlugin", path))
        if self._load_raises:
            raise RuntimeError("loadPlugin boom")
        if self._load_silently_fails:
            return  # Maya logged a warning, swallowed the failure, stayed UNLOADED
        self._loaded = True

    def names(self):
        return [c[0] for c in self.calls]


class TestLoadOrReloadPlugin(unittest.TestCase):
    def _patch(self, fake):
        from mpynode._base import plugins

        self._orig = plugins.cmds
        plugins.cmds = fake
        self.addCleanup(lambda: setattr(plugins, "cmds", self._orig))

    def test_not_loaded_just_loads(self):
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=False)
        self._patch(fake)
        res = load_or_reload_native_plugin("/some/out/myPlug.bundle")
        self.assertTrue(res["loaded"])
        self.assertFalse(res["reloaded"])
        self.assertIsNone(res["error"])
        self.assertEqual(res["base"], "myPlug.bundle")
        # loadPlugin called with the FULL path; no unload when not loaded.
        self.assertIn(("loadPlugin", "/some/out/myPlug.bundle"), fake.calls)
        self.assertNotIn("unloadPlugin", fake.names())

    def test_already_loaded_unloads_then_loads_in_order(self):
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=True)
        self._patch(fake)
        res = load_or_reload_native_plugin("/some/out/myPlug.bundle")
        self.assertTrue(res["loaded"])
        self.assertTrue(res["reloaded"])
        self.assertIsNone(res["error"])
        # unloadPlugin takes the BASE name; loadPlugin the full path; in ORDER.
        self.assertIn(("unloadPlugin", "myPlug.bundle"), fake.calls)
        self.assertIn(("loadPlugin", "/some/out/myPlug.bundle"), fake.calls)
        names = fake.names()
        self.assertLess(
            names.index("unloadPlugin"),
            names.index("loadPlugin"),
            "must unload the stale plugin BEFORE loading the new one",
        )

    def test_unload_fails_nodes_in_use_surfaces_error_no_load_no_raise(self):
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=True, unload_raises=True)
        self._patch(fake)
        res = load_or_reload_native_plugin("/some/out/myPlug.bundle")
        # Did not crash; clear error; did NOT proceed to loadPlugin (old still in).
        self.assertFalse(res["loaded"])
        self.assertIsNotNone(res["error"])
        self.assertIn("myPlug.bundle", res["error"])
        self.assertNotIn("loadPlugin", fake.names())

    def test_load_failure_surfaces_error_never_raises(self):
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=False, load_raises=True)
        self._patch(fake)
        res = load_or_reload_native_plugin("/some/out/myPlug.bundle")
        self.assertFalse(res["loaded"])
        self.assertIsNotNone(res["error"])

    def test_silent_load_failure_detected_via_plugininfo(self):
        # loadPlugin SWALLOWS a kFailure raised inside initializePlugin (Maya
        # logs a warning, does NOT re-raise, leaves the plugin UNLOADED) -- the
        # dominant companion-load failure mode (a command-name clash with an
        # already-loaded plugin). The helper must re-query pluginInfo and report
        # it as an error, not a FALSE success.
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=False, load_silently_fails=True)
        self._patch(fake)
        res = load_or_reload_native_plugin("/some/out/companion.py")
        self.assertFalse(res["loaded"],
                         "a swallowed kFailure must NOT report loaded=True")
        self.assertIsNotNone(res["error"])
        self.assertIn("companion.py", res["error"])
        # It must have actually re-queried the load state after loadPlugin.
        self.assertGreaterEqual(
            fake.names().count("pluginInfo"), 1,
            "must verify the load took via pluginInfo")

    def test_never_touches_the_scene(self):
        """The helper must NOT call file(new) or any scene-clearing op."""
        from mpynode._base.plugins import load_or_reload_native_plugin

        fake = _FakeCmds(loaded=True)
        self._patch(fake)
        load_or_reload_native_plugin("/some/out/myPlug.bundle")
        self.assertNotIn("file", fake.names())


class TestValidateRegisteredTypes(unittest.TestCase):
    """#63: 'loaded' is necessary but not sufficient. validate_registered_types
    confirms the bundle actually REGISTERED the node type(s) the build manifest
    recorded, so a load that registers nothing is caught as a failure."""

    class _FakeCmds:
        def __init__(self, dep_types):
            self._dep = list(dep_types)

        def pluginInfo(self, base, query=False, dependNode=False, **kw):
            return list(self._dep)

    def _patch(self, fake):
        from mpynode._base import plugins

        orig = plugins.cmds
        plugins.cmds = fake
        self.addCleanup(lambda: setattr(plugins, "cmds", orig))

    def _bundle_with_manifest(self, tmp, type_names):
        build = os.path.join(tmp, "build")
        os.makedirs(build, exist_ok=True)
        with open(os.path.join(build, "manifest.json"), "w") as fh:
            json.dump({"nodes": [{"type_name": t} for t in type_names]}, fh)
        return os.path.join(tmp, "mPyThing.bundle")

    def test_ok_when_all_expected_types_registered(self):
        from mpynode._base.plugins import validate_registered_types

        self._patch(self._FakeCmds(["mPyThing", "mPyOther"]))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_with_manifest(tmp, ["mPyThing"])
            res = validate_registered_types(bundle)
        self.assertTrue(res["ok"])
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["expected"], ["mPyThing"])

    def test_fail_when_expected_type_missing(self):
        from mpynode._base.plugins import validate_registered_types

        self._patch(self._FakeCmds([]))  # loaded, but registered nothing
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_with_manifest(tmp, ["mPyThing"])
            res = validate_registered_types(bundle)
        self.assertFalse(res["ok"])
        self.assertEqual(res["missing"], ["mPyThing"])
        self.assertIn("mPyThing", res["error"])

    def test_ok_when_no_manifest(self):
        from mpynode._base.plugins import validate_registered_types

        self._patch(self._FakeCmds([]))
        with tempfile.TemporaryDirectory() as tmp:
            bundle = os.path.join(tmp, "mPyThing.bundle")  # no build/manifest
            res = validate_registered_types(bundle)
        self.assertTrue(res["ok"])         # nothing to validate -> do not block
        self.assertEqual(res["expected"], [])

    def test_never_raises(self):
        from mpynode._base.plugins import validate_registered_types

        class _Boom:
            def pluginInfo(self, *a, **k):
                raise RuntimeError("boom")

        self._patch(_Boom())
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_with_manifest(tmp, ["mPyThing"])
            res = validate_registered_types(bundle)
        self.assertFalse(res["ok"])
        self.assertIsNotNone(res["error"])

    def _bundle_with_status_manifest(self, tmp, rows):
        build = os.path.join(tmp, "build")
        os.makedirs(build, exist_ok=True)
        with open(os.path.join(build, "manifest.json"), "w") as fh:
            json.dump({"nodes": rows}, fh)
        return os.path.join(tmp, "mPyThing.bundle")

    def test_dropped_and_failed_nodes_not_expected(self):
        # A best-effort (strict=False) build records DROPPED / compile-failed
        # nodes in the manifest, but those never register. They must NOT be part
        # of the expected-registered set, else a legitimately-successful partial
        # build false-fails as "loaded but did not register its node type(s)".
        from mpynode._base.plugins import validate_registered_types

        self._patch(self._FakeCmds(["mPyThing"]))  # only the built node registers
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_with_status_manifest(tmp, [
                {"type_name": "mPyThing", "build_status": "compiled"},
                {"type_name": "mPyDropped", "build_status": "dropped"},
                {"type_name": "mPyBad", "build_status": "compile-failed"},
            ])
            res = validate_registered_types(bundle)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["expected"], ["mPyThing"])


if __name__ == "__main__":
    unittest.main()
