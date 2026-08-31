"""Companion command plugin generator -- Phase 2, Slice 2.

A native compile turns an mPyNode's *compute* into C++ but cannot translate an
arbitrary ``@maya_command`` body (host orchestration: ``createNode`` /
``connectAttr`` / numpy / ...). Instead of dropping those commands, the compiler
emits a COMPANION: a standalone Python plugin shipped beside the ``.bundle`` that
re-exposes the methods as real ``maya.cmds.<name>()`` commands, dispatched through
the SAME interpreted machinery the live node uses (``build_methods_namespace`` +
``invoke_command``) but bound to the COMPILED node type.

These tests pin both the generated TEXT (pure) and the runtime BEHAVIOUR
(functional: the generated plugin is loaded into the running mayapy and driven via
``maya.cmds``). The interpreted ``mPyNode`` type stands in for "the compiled type"
-- at the ``cmds`` level (``createNode`` + plug get/set) it is faithful, and it
needs no clang. A real-clang end-to-end confirmation lives in a separate spike.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest

import maya.cmds as mc

from mpynode._common.methods.maya_command import detect_commands as _detect

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A factory + an instance command. read_name returns the bound node's name, so
# an instance command can prove it bound the SELECTED node; mk creates a node,
# so a factory command can prove it created the COMPILED type.
_METHODS = '''import maya.cmds as mc


@maya_command("companionMk")
def mk(cls):
    return cls.create(name="madeByCompanion#")


@maya_command("companionReadName")
def read_name(self):
    return self.get_name()
'''


class TestGenerateText(unittest.TestCase):
    """Pure text-emission contract (no plugin load)."""

    def _gen(self, methods=_METHODS, node_type="zzCompiledType", plugin="zzPlug"):
        from mpynode.native.compiler.command_companion import generate_companion_plugin

        return generate_companion_plugin(plugin, node_type, methods)

    def test_no_commands_returns_empty(self):
        self.assertEqual(self._gen(methods="# nothing here\nx = 1\n"), "")

    def test_emits_api2_plugin_scaffold(self):
        src = self._gen()
        self.assertIn("maya_useNewAPI", src)
        self.assertIn("def initializePlugin", src)
        self.assertIn("def uninitializePlugin", src)
        # binds to the COMPILED type name, not a hard-coded mpy type.
        self.assertIn("zzCompiledType", src)

    def test_emits_both_command_names(self):
        src = self._gen()
        self.assertIn("companionMk", src)
        self.assertIn("companionReadName", src)

    def test_reuses_interpreted_dispatch(self):
        # the companion routes through the shared runtime, not its own copy.
        src = self._gen()
        self.assertIn("build_methods_namespace", src)
        self.assertIn("invoke_command", src)

    def test_generated_source_is_valid_python(self):
        compile(self._gen(), "<companion>", "exec")

    def test_summary_classifies_kind(self):
        from mpynode.native.compiler.command_companion import companion_command_summary

        summ = {c["name"]: c for c in companion_command_summary(_METHODS)}
        self.assertEqual(summ["companionMk"]["kind"], "factory")
        self.assertEqual(summ["companionReadName"]["kind"], "instance")


class TestGenerateGuards(unittest.TestCase):
    """Defects the adversarial review confirmed: the generator must fail loudly
    at COMPILE time rather than emit a silently-broken/un-loadable plugin."""

    def _gen(self, methods, node_type="zzT", plugin="zzP"):
        from mpynode.native.compiler.command_companion import generate_companion_plugin

        return generate_companion_plugin(plugin, node_type, methods)

    def test_duplicate_command_name_rejected(self):
        # Two defs, SAME @maya_command name -> registerCommand collides at load.
        src = ('@maya_command("dup")\ndef alpha(cls):\n    return cls\n\n\n'
               '@maya_command("dup")\ndef beta(cls):\n    return cls\n')
        with self.assertRaises(ValueError):
            self._gen(src)

    def test_duplicate_def_name_rejected(self):
        # Two defs sharing the python def name -> colliding _Cmd_ classes.
        src = ('@maya_command("a")\ndef run(cls):\n    return cls\n\n\n'
               '@maya_command("b")\ndef run(self):\n    return self\n')
        with self.assertRaises(ValueError):
            self._gen(src)

    def test_invalid_command_name_rejected(self):
        for bad in ('@maya_command("bad-name")\ndef f(cls):\n    return cls\n',
                    '@maya_command("has space")\ndef g(cls):\n    return cls\n',
                    '@maya_command("")\ndef h(cls):\n    return cls\n'):
            with self.assertRaises(ValueError):
                self._gen(bad)

    def test_initializeplugin_rolls_back_on_failure(self):
        # the generated initializePlugin guards registration with try/except,
        # so a mid-loop failure can't leak half-registered commands.
        src = self._gen(_METHODS)
        init = src[src.index("def initializePlugin"):]
        self.assertIn("try", init)
        self.assertIn("except", init)
        # uninitialize must tolerate a never-registered command.
        uninit = src[src.index("def uninitializePlugin"):]
        self.assertIn("except", uninit)


class TestEmitCompanions(unittest.TestCase):
    """``emit_companions`` no longer WRITES anything: every @maya_command now
    compiles into the node's own bundle as an MPxCommand, so a compile yields
    exactly one artifact. What survives here is its clash gate -- it is the only
    check that sees command names across ALL nodes in one build."""

    def setUp(self):
        import tempfile

        self.out = tempfile.mkdtemp(prefix="emit_companions_")
        self.addCleanup(self._rm)

    def _rm(self):
        import shutil

        shutil.rmtree(self.out, ignore_errors=True)

    def _emit(self, nodes):
        from mpynode.native.compiler.command_companion import emit_companions

        return emit_companions(nodes, "myPlug", self.out)

    def _spec(self, base, methods):
        return {"suggested": {"mpx_base": base},
                "methods": methods,
                "commands": _detect(methods)}

    def test_factory_node_writes_no_companion_file(self):
        # a compile produces exactly ONE artifact: the commands move into the
        # node's own bundle as MPxCommands. Check nothing is written here and
        # that they are emitted there.
        from mpynode.native.compiler.kernels import command_dispatch

        spec = self._spec("MPxNode", _METHODS)
        recs = self._emit([("madeType", spec)])
        self.assertEqual(recs, [])
        self.assertEqual(os.listdir(self.out), [])

        out = command_dispatch.dispatch_for_spec(spec, "madeType")
        self.assertEqual(set(out["supported"]),
                         {"companionMk", "companionReadName"})
        for name in ("companionMk", "companionReadName"):
            self.assertIn('plugin.registerCommand("%s"' % name,
                          "\n".join(out["register"]))

    def test_node_without_commands_writes_nothing(self):
        spec = {"suggested": {"mpx_base": "MPxNode"}}
        recs = self._emit([("plainType", spec)])
        self.assertEqual(recs, [])
        self.assertEqual(os.listdir(self.out), [])

    def test_native_mesh_region_command_excluded_from_companion(self):
        # createMeshRegion on a locator compiles to C++ -> NOT in the companion.
        methods = ('@maya_command("createMeshRegion")\n'
                   'def cmr(cls):\n    return cls.create()\n')
        spec = self._spec("MPxLocatorNode", methods)
        recs = self._emit([("loc", spec)])
        self.assertEqual(recs, [], "native mesh-region must not ship as companion")

    def test_locator_mixes_native_and_dispatch_in_one_bundle(self):
        # createMeshRegion keeps its hand-written native template; customThing
        # has none and goes through the generic dispatch emitter. Both land in
        # the same bundle and neither ships as a companion.
        from mpynode.native.compiler.kernels import (command_codegen,
                                                     command_dispatch)

        methods = ('@maya_command("createMeshRegion")\n'
                   'def cmr(cls):\n    return cls.create()\n\n\n'
                   '@maya_command("customThing")\n'
                   'def custom(self):\n    return self.get_name()\n')
        spec = self._spec("MPxLocatorNode", methods)
        recs = self._emit([("loc", spec)])
        self.assertEqual(recs, [])
        self.assertEqual(os.listdir(self.out), [])

        cmds = spec["commands"]
        native = [c["name"] for c in cmds
                  if command_codegen.classify_command(c) is not None]
        self.assertEqual(native, ["createMeshRegion"])
        # The locator emitter passes the natively-handled names as exclude= so
        # the two emitters cannot both register the same command name.
        out = command_dispatch.dispatch_for_spec(spec, "loc",
                                                 exclude=tuple(native))
        self.assertEqual(out["supported"], ["customThing"])

    def test_cross_node_command_name_clash_raises(self):
        a = self._spec("MPxNode",
                       '@maya_command("dup")\ndef a(cls):\n    return cls\n')
        b = self._spec("MPxNode",
                       '@maya_command("dup")\ndef b(cls):\n    return cls\n')
        with self.assertRaises(ValueError):
            self._emit([("A", a), ("B", b)])

    def test_companion_clashes_with_native_command_name_raises(self):
        # a locator compiles createMeshRegion natively into the .bundle; a
        # different node's COMPANION command of the same name registers the
        # same global Maya command at load. The bundler's clash gate can't see
        # companions and emit_companions' gate couldn't see native names, so
        # this slipped through.
        loc = self._spec("MPxLocatorNode",
                         '@maya_command("createMeshRegion")\n'
                         'def cmr(cls):\n    return cls.create()\n')
        other = self._spec("MPxNode",
                           '@maya_command("createMeshRegion")\n'
                           'def cmr2(self):\n    return self.get_name()\n')
        with self.assertRaises(ValueError):
            self._emit([("loc", loc), ("other", other)])

    def test_cross_node_clash_writes_no_files(self):
        # all-or-nothing, mirroring the bundler's native gate: a clash on the
        # second node must not orphan the first node's companion .py on disk.
        a = self._spec("MPxNode",
                       '@maya_command("dup")\ndef a(cls):\n    return cls\n')
        b = self._spec("MPxNode",
                       '@maya_command("dup")\ndef b(cls):\n    return cls\n')
        with self.assertRaises(ValueError):
            self._emit([("A", a), ("B", b)])
        self.assertEqual(os.listdir(self.out), [],
                         "a clash must leave NO orphaned companion files")


class TestControllerWiring(unittest.TestCase):
    """compile_plugin must leave NO sibling .py beside the bundle while still
    reporting the bundled commands per node. Mocks the toolchain/cache/assemble
    so a command-bearing node reaches that step with NO LLM and NO real clang
    (cache-hit path)."""

    def setUp(self):
        import tempfile

        self.out = tempfile.mkdtemp(prefix="ctrl_companion_")
        self.addCleanup(self._rm)

    def _rm(self):
        import shutil

        shutil.rmtree(self.out, ignore_errors=True)

    def _spec(self):
        return {
            "schema_version": 1, "source_node": "addNode1", "mpy_type": "mPyNode",
            "suggested": {"node_type_name": "addNode1", "class_name": "AddNode1",
                          "type_id": "0x00070140", "mpx_base": "MPxNode"},
            "inputs": {"a": {"type": "float", "is_array": False}},
            "outputs": {"b": {"type": "float", "is_array": False}},
            "variables": {}, "compute": "b = a\n", "init": "",
            "affects": "all", "portability": {"portable": True, "blockers": []},
            "methods": _METHODS, "commands": _detect(_METHODS),
        }

    def test_compile_plugin_writes_no_companion_and_reports_commands(self):
        import unittest.mock as mock
        from mpynode.native.toolchain import compile_controller as cc

        cached_cpp = os.path.join(self.out, "_cached.cpp")
        with open(cached_cpp, "w") as fh:
            fh.write("// dummy cached cpp\n")

        def fake_assemble(asm_nodes, plugin_name, out_dir, **kw):
            bundle = os.path.join(out_dir, plugin_name + ".bundle")
            with open(bundle, "w") as fh:
                fh.write("x")
            return {"ok": True, "bundle": bundle, "dropped": [],
                    "shared_helpers": [],
                    "nodes": [{"name": tn, "id": "0x70140", "status": "compiled"}
                              for (tn, _c) in asm_nodes]}

        with mock.patch.object(cc.toolchain, "check_toolchain",
                               return_value={"ok": True}), \
                mock.patch.object(cc.port_cache, "get_path",
                                  return_value=cached_cpp), \
                mock.patch.object(cc.bundler, "assemble",
                                  side_effect=fake_assemble):
            result = cc.compile_plugin(
                [self._spec()], "addPlug", self.out, verify=False, strict=False,
                complete_fn=lambda *a, **k: "")

        self.assertTrue(result["ok"], result.get("errors"))
        companion = os.path.join(self.out, "addNode1_commands.py")
        self.assertFalse(os.path.isfile(companion),
                         "a compile must produce ONE artifact, no sibling .py")
        self.assertNotIn("companions", result)
        # the per-node row still carries the command summary for the dialog
        # report, derived from the spec rather than a written file.
        self.assertIn("commands", result["nodes"][0])
        names = {c["name"] for c in result["nodes"][0]["commands"]}
        self.assertIn("companionMk", names)

    def _plain_spec(self):
        return {
            "schema_version": 1, "source_node": "plainNode",
            "mpy_type": "mPyNode",
            "suggested": {"node_type_name": "plainNode",
                          "class_name": "PlainNode",
                          "type_id": "0x00070141", "mpx_base": "MPxNode"},
            "inputs": {"a": {"type": "float", "is_array": False}},
            "outputs": {"b": {"type": "float", "is_array": False}},
            "variables": {}, "compute": "b = a\n", "init": "",
            "affects": "all", "portability": {"portable": True, "blockers": []},
        }

    def test_dropped_command_node_writes_no_companion(self):
        # with strict=False a command-bearing node can fail while a sibling
        # links (ok=True). Its type is not in the bundle, so a companion
        # targeting it would fail at call time: skip dropped types.
        import unittest.mock as mock
        from mpynode.native.toolchain import compile_controller as cc

        cached_cpp = os.path.join(self.out, "_cached2.cpp")
        with open(cached_cpp, "w") as fh:
            fh.write("// dummy\n")

        def fake_assemble(asm_nodes, plugin_name, out_dir, **kw):
            bundle = os.path.join(out_dir, plugin_name + ".bundle")
            with open(bundle, "w") as fh:
                fh.write("x")
            nodes = []
            for (tn, _c) in asm_nodes:
                st = "compile-failed" if tn == "addNode1" else "compiled"
                nodes.append({"name": tn, "id": "0x70140", "status": st})
            return {"ok": True, "bundle": bundle, "dropped": ["addNode1"],
                    "shared_helpers": [], "nodes": nodes}

        with mock.patch.object(cc.toolchain, "check_toolchain",
                               return_value={"ok": True}), \
                mock.patch.object(cc.port_cache, "get_path",
                                  return_value=cached_cpp), \
                mock.patch.object(cc.bundler, "assemble",
                                  side_effect=fake_assemble):
            result = cc.compile_plugin(
                [self._spec(), self._plain_spec()], "addPlug", self.out,
                verify=False, strict=False, complete_fn=lambda *a, **k: "")

        self.assertTrue(result["ok"], result.get("errors"))
        self.assertFalse(
            os.path.isfile(os.path.join(self.out, "addNode1_commands.py")),
            "a dropped node must not get a broken companion")
        self.assertNotIn("companions", result)


class _CompanionPluginFixture:
    """Generate a companion plugin into a temp dir, load it, and guarantee
    unload + temp cleanup. ``node_type`` stands in for the compiled type."""

    _counter = 0

    def _load_companion(self, methods, node_type="mPyNode"):
        from mpynode.native.compiler.command_companion import generate_companion_plugin

        _CompanionPluginFixture._counter += 1
        plugin = "zzCompanion%d" % _CompanionPluginFixture._counter
        src = generate_companion_plugin(plugin, node_type, methods)
        tmpdir = tempfile.mkdtemp(prefix="mpyn_companion_")
        path = os.path.join(tmpdir, plugin + ".py")
        with open(path, "w") as fh:
            fh.write(src)
        mc.loadPlugin(path, quiet=True)
        self.addCleanup(self._unload, plugin, path, tmpdir)
        return plugin

    def _unload(self, plugin, path, tmpdir):
        try:
            mc.unloadPlugin(plugin)
        except Exception:
            pass
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except Exception:
            pass


class TestCompanionRuntime(_CompanionPluginFixture, unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_factory_command_creates_the_compiled_type(self):
        self._load_companion(_METHODS, node_type="mPyNode")
        before = set(mc.ls(type="mPyNode"))
        mc.companionMk()
        after = set(mc.ls(type="mPyNode"))
        self.assertEqual(len(after - before), 1,
                         "factory companion must create exactly one node")

    def test_factory_returns_the_created_node_name(self):
        self._load_companion(_METHODS, node_type="mPyNode")
        result = mc.companionMk()
        # cmds returns the command's setResult; the created node must exist.
        name = result[0] if isinstance(result, (list, tuple)) else result
        self.assertTrue(name and mc.objExists(name), repr(result))

    def test_instance_command_binds_the_selected_node(self):
        self._load_companion(_METHODS, node_type="mPyNode")
        host = mc.createNode("mPyNode", name="theSelectedHost")
        mc.select(host)
        result = mc.companionReadName()
        name = result[0] if isinstance(result, (list, tuple)) else result
        self.assertEqual(name, host)

    def test_instance_command_accepts_explicit_object_arg(self):
        self._load_companion(_METHODS, node_type="mPyNode")
        host = mc.createNode("mPyNode", name="theArgHost")
        mc.select(clear=True)
        result = mc.companionReadName(host)
        name = result[0] if isinstance(result, (list, tuple)) else result
        self.assertEqual(name, host)

    def test_instance_command_errors_with_no_target(self):
        self._load_companion(_METHODS, node_type="mPyNode")
        mc.select(clear=True)
        with self.assertRaises(Exception):
            mc.companionReadName()

    def test_static_command_runs_without_a_target(self):
        # a @staticmethod command needs no node and must run with an EMPTY
        # selection; the live node runs it fine via call_command.
        methods = ('@staticmethod\n@maya_command("companionStaticPing")\n'
                   'def ping():\n    return 42\n')
        self._load_companion(methods, node_type="mPyNode")
        mc.select(clear=True)
        res = mc.companionStaticPing()
        val = res[0] if isinstance(res, (list, tuple)) else res
        self.assertEqual(val, 42)

    def test_numpy_scalar_result_marshals_numeric_not_string(self):
        methods = ('import numpy as np\n\n\n'
                   '@maya_command("companionNpInt")\n'
                   'def npint(self):\n    return np.int64(7)\n\n\n'
                   '@maya_command("companionNpBool")\n'
                   'def npbool(self):\n    return np.bool_(False)\n')
        self._load_companion(methods, node_type="mPyNode")
        host = mc.createNode("mPyNode", name="npHost")
        mc.select(host)
        r_int = mc.companionNpInt()
        r_int = r_int[0] if isinstance(r_int, (list, tuple)) else r_int
        self.assertEqual(r_int, 7)
        self.assertNotIsInstance(r_int, str)

        mc.select(host)
        r_bool = mc.companionNpBool()
        r_bool = r_bool[0] if isinstance(r_bool, (list, tuple)) else r_bool
        # The bug stringified np.bool_(False) -> "False", which is TRUTHY.
        self.assertNotEqual(r_bool, "False")
        self.assertFalse(bool(r_bool))


if __name__ == "__main__":
    unittest.main()
