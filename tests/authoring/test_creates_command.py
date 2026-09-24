# tests/authoring/test_creates_command.py  (pure -- no setUpModule)
"""@maya_command(creates=True): the setup-as-create-command surface.

Covers the four pieces that make a self-first ``setup`` double as a
blendShape-style create command: the marker, the name resolution, the
compile-time proxy-safety gate, and the generated dispatcher's classification.
"""
import ast
import contextlib
import inspect
import io
import unittest
import warnings

from mpynode._common.methods.maya_command import (
    detect_commands, maya_command, resolve_create_command_names,
    _is_instance_def,
)
from mpynode._common.methods.outline_model import build_outline
from mpynode._common import node_setups
from mpynode.native.compiler.kernels import command_dispatch as cd


CREATES_SRC = (
    "@maya_command('patchRelax', creates=True)\n"
    "def setup(self, selection=None, *args, **kwargs):\n"
    "    return self.get_name()\n"
)

UNNAMED_SRC = (
    "@maya_command(creates=True)\n"
    "def setup(self, *args, **kwargs):\n"
    "    return self.get_name()\n"
)


class TestCreatesMarker(unittest.TestCase):
    def test_runtime_records_creates_and_stays_a_noop(self):
        @maya_command("thing", creates=True)
        def fn(self):
            return 7
        self.assertTrue(fn.__maya_command__["creates"])
        self.assertEqual(fn(None), 7)

    def test_bare_marker_defaults_creates_false(self):
        @maya_command
        def fn(self):
            return 1
        self.assertFalse(fn.__maya_command__["creates"])

    def test_detected_on_a_self_first_def(self):
        c = detect_commands(CREATES_SRC)[0]
        self.assertTrue(c["creates"])
        self.assertFalse(c["is_factory"])
        self.assertFalse(c["is_static"])
        self.assertEqual(c["func_name"], "setup")
        self.assertTrue(c["name_explicit"])

    def test_ignored_and_warned_on_a_factory(self):
        src = ("@maya_command('mk', creates=True)\n"
               "def mk(cls):\n"
               "    return 1\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            c = detect_commands(src)[0]
        self.assertFalse(c["creates"])
        self.assertTrue(c["is_factory"])
        self.assertTrue(any("creates" in str(w.message) for w in caught))

    def test_ignored_and_warned_on_a_staticmethod(self):
        src = ("@maya_command('st', creates=True)\n"
               "@staticmethod\n"
               "def st():\n"
               "    return 1\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            c = detect_commands(src)[0]
        self.assertFalse(c["creates"])
        self.assertTrue(any("creates" in str(w.message) for w in caught))

    def test_non_literal_creates_warns_and_defaults_false(self):
        src = ("FLAG = True\n"
               "@maya_command('dyn', creates=FLAG)\n"
               "def dyn(self):\n"
               "    return 1\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            c = detect_commands(src)[0]
        self.assertFalse(c["creates"])
        self.assertTrue(any("creates" in str(w.message) for w in caught))

    def test_decorating_setup_does_not_break_find_setup(self):
        """The gate rejects only @classmethod/@staticmethod, so a decorated
        setup is still the setup hook -- this is what lets one def be both."""
        self.assertIsNotNone(node_setups.find_setup(CREATES_SRC))
        fn = ast.parse(CREATES_SRC).body[0]
        self.assertTrue(_is_instance_def(fn))


class TestCreateCommandNameResolution(unittest.TestCase):
    def test_unnamed_takes_the_node_type_name(self):
        cmds = resolve_create_command_names(
            detect_commands(UNNAMED_SRC), "sineRipple")
        self.assertEqual(cmds[0]["name"], "sineRipple")

    def test_explicit_literal_is_never_overwritten(self):
        cmds = resolve_create_command_names(
            detect_commands(CREATES_SRC), "somethingElse")
        self.assertEqual(cmds[0]["name"], "patchRelax")

    def test_non_creates_commands_are_untouched(self):
        src = ("@maya_command\n"
               "def poke(self):\n"
               "    return 1\n")
        cmds = resolve_create_command_names(detect_commands(src), "someType")
        self.assertEqual(cmds[0]["name"], "poke")

    def test_missing_type_name_is_a_noop(self):
        cmds = resolve_create_command_names(detect_commands(UNNAMED_SRC), "")
        self.assertEqual(cmds[0]["name"], "setup")


class TestProxySafetyGate(unittest.TestCase):
    def _cmd(self, body):
        src = "@maya_command(creates=True)\ndef setup(self, selection=None):\n" + body
        return resolve_create_command_names(detect_commands(src), "someNode")[0]

    def test_clean_setup_has_no_blockers(self):
        c = self._cmd("    return self.get_name()\n")
        self.assertEqual(cd.create_command_blockers(c), [])

    def test_native_type_and_call_command_are_allowed(self):
        c = self._cmd("    return self.NATIVE_TYPE + self.call_command('x')\n")
        self.assertEqual(cd.create_command_blockers(c), [])

    def test_stored_variable_access_is_blocked(self):
        c        = self._cmd("    self.set_variable('p', [1], persistent=True)\n")
        blockers = cd.create_command_blockers(c)
        self.assertTrue(blockers)
        self.assertIn("set_variable", blockers[0])

    def test_wrapper_instance_construction_is_blocked(self):
        c = self._cmd(
            "    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape\n"
            "    MPyBlendShape(self.get_name()).rebuild()\n")
        blockers = cd.create_command_blockers(c)
        self.assertTrue(blockers)
        self.assertIn("MPyBlendShape", blockers[0])

    def test_wrapper_staticmethod_is_allowed(self):
        """Measured: MPySkinCluster._wire_joints is pure maya.cmds against real
        compiled attributes. Blocking the IMPORT would wrongly reject the whole
        skinCluster create command."""
        c = self._cmd(
            "    from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster\n"
            "    MPySkinCluster._wire_joints(self.get_name(), ['j1'])\n")
        self.assertEqual(cd.create_command_blockers(c), [])

    def test_registry_wrap_is_blocked(self):
        c = self._cmd(
            "    from mpynode._node_registry import wrap_node\n"
            "    wrap_node(self.get_name(), 'mPyNode')\n")
        blockers = cd.create_command_blockers(c)
        self.assertTrue(blockers)
        self.assertIn("wrap_node", blockers[0])

    def test_access_in_a_swallowing_try_is_allowed(self):
        """Mesh Regions' legacy migration: on a compiled node the proxy raises
        RuntimeError at the lookup, the handler swallows it, the setup goes on."""
        c = self._cmd(
            "    try:\n"
            "        legacy = (self.get_variables() or {}).get('regions')\n"
            "    except Exception:\n"
            "        legacy = None\n"
            "    try:\n"
            "        self.remove_variable('regions')\n"
            "    except (KeyError, RuntimeError):\n"
            "        pass\n")
        self.assertEqual(cd.create_command_blockers(c), [])

    def test_bare_except_and_base_exception_guard_too(self):
        for handler in ("except:", "except BaseException:", "except builtins.RuntimeError:"):
            c = self._cmd("    try:\n        self.get_variables()\n    %s\n        pass\n" % handler)
            self.assertEqual(cd.create_command_blockers(c), [], handler)

    def test_a_handler_that_misses_runtime_error_still_blocks(self):
        c        = self._cmd("    try:\n        self.get_variables()\n    except KeyError:\n        pass\n")
        blockers = cd.create_command_blockers(c)
        self.assertTrue(blockers)
        self.assertIn("get_variables", blockers[0])

    def test_a_handler_that_reraises_still_blocks(self):
        c = self._cmd("    try:\n        self.get_variables()\n"
                      "    except RuntimeError:\n        raise ValueError('no')\n")
        self.assertTrue(cd.create_command_blockers(c))

    def test_access_outside_the_try_body_still_blocks(self):
        for body in ("    try:\n        pass\n    except Exception:\n        self.get_variables()\n",
                     "    try:\n        pass\n    except Exception:\n        pass\n"
                     "    finally:\n        self.get_variables()\n",
                     "    try:\n        pass\n    except Exception:\n        pass\n"
                     "    else:\n        self.get_variables()\n"):
            self.assertTrue(cd.create_command_blockers(self._cmd(body)), body)

    def test_a_deferred_call_defined_in_the_try_still_blocks(self):
        c = self._cmd("    try:\n        later = lambda: self.get_variables()\n"
                      "    except Exception:\n        pass\n    later()\n")
        self.assertTrue(cd.create_command_blockers(c))

    def test_a_blocked_command_fails_the_emit(self):
        c   = self._cmd("    self.set_variable('p', 1)\n")
        out = cd.emit_dispatch_commands([c], "someNode", "")
        self.assertTrue(out["errors"])
        self.assertEqual(out["classes"], "")


class TestGeneratedDispatch(unittest.TestCase):
    def test_kind_is_creates(self):
        cmds = resolve_create_command_names(detect_commands(UNNAMED_SRC), "myType")
        src  = cd.python_module_source("myType", UNNAMED_SRC, cmds)
        self.assertIn("'myType': 'creates'", src.replace('"', "'"))

    def test_plain_instance_command_keeps_its_kind(self):
        src_py = "@maya_command\ndef poke(self):\n    return 1\n"
        cmds   = detect_commands(src_py)
        src    = cd.python_module_source("myType", src_py, cmds)
        self.assertIn("'poke': 'instance'", src.replace('"', "'"))

    def test_create_command_widens_its_object_arity(self):
        """A create command takes many objects (the geometry); an instance
        command still takes exactly one."""
        both = "@maya_command\ndef poke(self):\n    return 1\n" + UNNAMED_SRC
        cmds = resolve_create_command_names(detect_commands(both), "myType")
        out  = cd.emit_dispatch_commands(cmds, "myType", both)
        self.assertEqual(out["errors"], [])
        self.assertIn("kSelectionList, 0, 255)", out["classes"])
        self.assertIn("kSelectionList, 0, 1)", out["classes"])

    def test_setup_star_args_do_not_fail_the_flag_spec(self):
        """*args/**kwargs is a hard CommandSpecError for a normal command; on a
        create command it is the setup hook's tail and must be tolerated."""
        cmds = resolve_create_command_names(detect_commands(UNNAMED_SRC), "myType")
        out  = cd.emit_dispatch_commands(cmds, "myType", UNNAMED_SRC)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["supported"], ["myType"])

    def test_selection_is_not_exposed_as_a_flag(self):
        cmds  = resolve_create_command_names(detect_commands(CREATES_SRC), "myType")
        flags = cd.flag_spec_for(cmds[0])
        self.assertEqual([f["param"] for f in flags], [])


class TestOutlineRouting(unittest.TestCase):
    def test_creates_setup_stays_in_the_setup_group(self):
        """It must NOT move to Commands: the Script tab's command runner does
        not pass selection=, so the setup would adopt nothing."""
        items  = build_outline(CREATES_SRC)
        groups = {}
        for it in items:
            groups.setdefault(it.kind, []).append(it)
        self.assertIn("Setup", groups)
        self.assertNotIn("Commands", groups)
        row = groups["Setup"][0]
        self.assertEqual(row.run_kind, "setup")
        self.assertEqual(row.command_name, "patchRelax")

    def test_unnamed_creates_setup_reports_no_command_name(self):
        """The outline has source only -- it cannot know the compiled type, and
        must not report the un-resolved fallback ("setup") as a command name."""
        row = [it for it in build_outline(UNNAMED_SRC) if it.kind == "Setup"][0]
        self.assertIsNone(row.command_name)

    def test_an_ordinary_command_still_lands_in_commands(self):
        src = ("@maya_command\n"
               "def poke(self):\n"
               "    return 1\n"
               "def setup(self, selection=None):\n"
               "    return selection\n")
        kinds = {it.kind: it for it in build_outline(src)}
        self.assertIn("Commands", kinds)
        self.assertIn("Setup", kinds)
        self.assertIsNone(kinds["Setup"].command_name)


class TestTypeDefaultsCarryCreateCommands(unittest.TestCase):
    """The per-type default setups are the ONLY setup 21 templates ever get, so
    their decorator is what gives those nodes a create command at all."""

    DECORATED = ["mPyDeformer", "mPySkinCluster", "mPyMesh", "mPyIkSolver",
                 "mPyNurbsCurve", "mPyNurbsSurface"]

    def test_each_declares_an_unnamed_create_command(self):
        for t in self.DECORATED:
            src = node_setups.setup_source_for_type(t)
            self.assertIsNotNone(src, "missing setup source for %s" % t)
            cre = [c for c in detect_commands(src) if c.get("creates")]
            self.assertEqual(len(cre), 1, "%s: expected one create command" % t)
            self.assertEqual(cre[0]["func_name"], "setup")
            self.assertFalse(cre[0]["name_explicit"],
                             "%s: a name literal in a SHARED setup would give "
                             "every node of the type the same command name" % t)

    def test_each_is_proxy_safe(self):
        for t in self.DECORATED:
            src = node_setups.setup_source_for_type(t)
            cre = resolve_create_command_names(
                detect_commands(src), t + "Thing")[0]
            self.assertEqual(cd.create_command_blockers(cre), [],
                             "%s setup is not compiled-safe" % t)

    def test_signature_keeps_selection_in_kwargs(self):
        """These bodies read kwargs.get("selection"). A named selection=
        parameter would swallow the dispatcher's snapshot and the body would
        fall back to the live selection -- which createNode just clobbered."""
        for t in self.DECORATED:
            src   = node_setups.setup_source_for_type(t)
            fn    = node_setups.find_setup(src)
            named = [a.arg for a in fn.args.args]
            self.assertEqual(named, ["self"], "%s changed its signature" % t)
            self.assertIsNotNone(fn.args.kwarg, "%s lost **kwargs" % t)


class TestMergeTypeDefault(unittest.TestCase):
    def test_appends_when_there_is_no_setup(self):
        out = node_setups.merge_type_default("def other():\n    pass\n",
                                             "mPyDeformer")
        self.assertIn("def other()", out)
        self.assertIsNotNone(node_setups.find_setup(out))

    def test_authored_setup_wins(self):
        src = "def setup(self, selection=None):\n    return 'mine'\n"
        self.assertEqual(node_setups.merge_type_default(src, "mPyDeformer"), src)

    def test_type_without_a_default_is_a_noop(self):
        self.assertEqual(node_setups.merge_type_default("x = 1\n", "mPyNode"),
                         "x = 1\n")


class TestPayloadRowSizeCheck(unittest.TestCase):
    """The base64 payload ships as the initialiser of a ``static const char[]``,
    which dodges both MSVC string-literal caps -- but NOT the 65535-character
    cap on a single source LINE. What binds is the chunk width, never the
    payload size, and blowing it produces an MSVC-only C2026 nobody sees on
    clang."""

    def test_each_base64_character_costs_four_source_characters(self):
        """The arithmetic the cap is reasoned about: one ``'x',`` per char."""
        self.assertEqual(cd._b64_array_body("hi", indent="").splitlines(),
                         ["'a','G','k','=',"])

    def test_a_payload_far_past_the_cap_still_emits(self):
        """60 KB of source is 80000 base64 characters -- past the line cap many
        times over. Built in memory; the array form has no payload ceiling."""
        rows = cd._b64_array_body("x" * 60000).splitlines()
        self.assertGreater(len(rows), 1)
        self.assertLess(max(len(r) for r in rows), cd.MSVC_SOURCE_LINE_MAX)

    def test_the_shipped_chunk_width_cannot_reach_the_cap(self):
        self.assertLess(cd._B64_LINE_WIDTH * 4, cd.MSVC_SOURCE_LINE_MAX)

    def test_an_over_long_row_raises(self):
        """``_B64_LINE_WIDTH`` is bound as a def-time default of ``_b64_lines``,
        so patching the module attribute would not widen a row and no payload
        size can either -- ``indent`` is the one lever that grows the same
        ``len(row)`` the guard measures, and it needs no fixture on disk."""
        indent = " " * cd.MSVC_SOURCE_LINE_MAX
        with self.assertRaises(AssertionError) as ctx:
            cd._b64_array_body("hi", indent=indent)
        msg = str(ctx.exception)
        self.assertIn(str(len(indent) + 16),        msg)
        self.assertIn(str(cd.MSVC_SOURCE_LINE_MAX), msg)
        self.assertIn("_B64_LINE_WIDTH",            msg)

    def test_the_guard_is_a_raise_not_an_assert(self):
        """``python -O`` strips every ``assert`` statement. A guard on what the
        compiler can physically consume must survive that, so it is written as
        an explicit ``raise AssertionError``."""
        tree = ast.parse(inspect.getsource(cd._b64_array_body))
        self.assertEqual(
            [n for n in ast.walk(tree) if isinstance(n, ast.Assert)], [],
            "an `assert` here would vanish under python -O")
        raises = [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]
        self.assertEqual(len(raises), 1)
        exc = raises[0].exc
        self.assertIsInstance(exc, ast.Call)
        self.assertEqual(exc.func.id, "AssertionError")


class TestReachableMpynodeImportIsFatal(unittest.TestCase):
    """A bundle ships its commands, and what they use, as embedded Python and is
    loaded on machines that have Maya but NOT mpynode, where a shipped ``import
    mpynode`` raises ModuleNotFoundError the first time the command runs.

    That used to be a stderr WARNING ("Not fatal -- the command still
    compiles") and 13 templates broke straight through it, so a payload-bearing
    node now FAILS the compile. A node that ships NO payload (command-less, or
    every command natively lowered) is a different case -- nothing embeds the
    source, so the artifact is correct -- and is REPORTED as LATENT instead."""

    POKE = ("@maya_command('pokeIt')\n"
            "def poke(self):\n"
            "    return self.get_name()\n")

    def _reach(self, src):
        return cd.reachable_mpynode_imports(src, detect_commands(src))

    def test_clean_source_reports_nothing(self):
        src = "import maya.cmds as mc\n\n\n" + self.POKE
        self.assertEqual(self._reach(src), [])

    def test_module_scope_import_is_reported(self):
        """It execs before any command is even looked up, so reachability does
        not enter into it."""
        src = ("from mpynode._common.methods.maya_command import maya_test\n\n\n"
               + self.POKE)
        lines = self._reach(src)
        self.assertEqual(len(lines), 1)
        self.assertIn("module scope", lines[0])
        self.assertIn("L1", lines[0])

    def test_import_inside_the_command_body_is_reported(self):
        src = ("@maya_command('pokeIt')\n"
               "def poke(self):\n"
               "    from mpynode._common.methods.setup_helpers import _meshes\n"
               "    return _meshes(None)\n")
        lines = self._reach(src)
        self.assertEqual(len(lines), 1)
        self.assertIn("in def poke", lines[0])

    def test_import_in_a_helper_the_command_reaches_is_reported(self):
        src = ("def _grab():\n"
               "    import mpynode\n"
               "    return mpynode\n\n\n"
               "@maya_command('pokeIt')\n"
               "def poke(self):\n"
               "    return _grab()\n")
        lines = self._reach(src)
        self.assertEqual(len(lines), 1)
        self.assertIn("_grab <- poke", lines[0])

    def test_an_unreachable_def_is_not_reported(self):
        """No command can call it, so it never runs in a bundle."""
        src = ("def _orphan():\n"
               "    import mpynode\n"
               "    return mpynode\n\n\n" + self.POKE)
        self.assertEqual(self._reach(src), [])

    def test_unparsable_source_reports_nothing(self):
        self.assertEqual(cd.reachable_mpynode_imports("def (:\n", []), [])

    def test_emit_FAILS_the_compile_when_the_payload_carries_the_import(self):
        """The command SHIPS as embedded Python, so the import is a real defect
        in the artifact -- not something to note and carry on past."""
        from mpynode.native.compiler.errors import UnsupportedSpec

        src = ("from mpynode._common.methods.setup_helpers import _meshes\n\n\n"
               "@maya_command('pokeIt')\n"
               "def poke(self):\n"
               "    return _meshes(None)\n")
        cmds = detect_commands(src)
        with self.assertRaises(UnsupportedSpec) as ctx:
            cd.emit_dispatch_commands(cmds, "pokeType", src)
        msg = str(ctx.exception)
        self.assertIn("pokeType", msg)
        self.assertIn("setup_helpers import _meshes", msg)
        self.assertIn("module scope", msg)

    def test_a_module_scope_import_no_command_uses_does_not_ship(self):
        """The payload carries only the commands and what they use, so an
        import only a demo or test needs is not in the bundle at all."""
        src = ("from mpynode._common.methods.maya_command import maya_test\n\n\n"
               + self.POKE)
        out = cd.emit_dispatch_commands(detect_commands(src), "pokeType", src)
        self.assertEqual(out["supported"], ["pokeIt"])
        self.assertNotIn("maya_test", cd.command_payload_source(src))

    def test_the_failure_names_every_reachable_import_at_once(self):
        from mpynode.native.compiler.errors import UnsupportedSpec

        src = ("import mpynode\n\n\n"
               "def _grab():\n"
               "    from mpynode._common.methods import setup_helpers\n"
               "    return mpynode, setup_helpers\n\n\n"
               "@maya_command('pokeIt')\n"
               "def poke(self):\n"
               "    return _grab()\n")
        with self.assertRaises(UnsupportedSpec) as ctx:
            cd.emit_dispatch_commands(detect_commands(src), "pokeType", src)
        msg = str(ctx.exception)
        self.assertIn("module scope", msg)
        self.assertIn("_grab <- poke", msg)

    def test_a_clean_node_emits_no_warning(self):
        src = "import maya.cmds as mc\n\n\n" + self.POKE
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = cd.emit_dispatch_commands(detect_commands(src), "pokeType",
                                            src)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(out["supported"], ["pokeIt"])

    def test_a_command_less_node_reports_the_LATENT_import_and_compiles(self):
        """THE LATENT CASE. No command -> no payload -> nothing embeds the
        source, so the artifact is fine and failing would be a false alarm. But
        it stops being latent the day this node acquires one @maya_command, with
        no edit to the import, so the compiler must not be blind to it."""
        spec = {"commands": [], "methods": "import mpynode\n\n\nX = 1\n"}
        err  = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = cd.dispatch_for_spec(spec, "quietType")
        text = err.getvalue()
        self.assertIn("LATENT",       text)
        self.assertIn("quietType",    text)
        self.assertIn("module scope", text)
        self.assertEqual(out, dict(cd.EMPTY))

    def test_a_command_less_CLEAN_node_reports_nothing(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cd.dispatch_for_spec({"commands": [], "methods": "X = 1\n"},
                                 "quietType")
        self.assertEqual(err.getvalue(), "")

    def test_an_all_native_node_reports_the_LATENT_import_and_compiles(self):
        """Same rule from the other side: the shipped mPyMesh setup lowers to
        pure C++, so no payload is emitted and the import never ships."""
        src  = "import mpynode\n" + node_setups.setup_source_for_type("mPyMesh")
        cmds = resolve_create_command_names(detect_commands(src), "mPyMesh")
        err  = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = cd.emit_dispatch_commands(cmds, "mPyMesh", src,
                                            mpx_base="MPxNode")
        self.assertEqual(out["native"], ["mPyMesh"],
                         "fixture must still lower -- otherwise this asserts "
                         "nothing about the no-payload path")
        self.assertIn("LATENT", err.getvalue())


class TestNativeLoweringSelectsTheCreatedNode(unittest.TestCase):
    """A natively lowered create command must leave the same node SELECTED as
    the Python form of the very same command.

    The compiled PYTHON-PAYLOAD form reaches ``cmds.createNode(<type>)`` through
    ``_CompiledProxy.create()`` and then runs the body verbatim -- and every
    ``cmds.createNode`` in that body reselects what it makes, so the selection
    the command leaves behind is the LAST DAG node the BODY created, not the
    mPyNode. A modifier create touches no selection at all, so the lowered form
    has to say so explicitly or the two compiled forms of one command disagree.
    """

    # mPyMesh's body creates the transform (n0) then the mesh shape (n1).
    SELECT = "MGlobal::select(_o_n1, MGlobal::kReplaceList);"

    def _emit(self):
        """The SHIPPED mPyMesh setup, run through the real emitter."""
        src  = node_setups.setup_source_for_type("mPyMesh")
        cmds = resolve_create_command_names(detect_commands(src), "mPyMesh")
        out = cd.emit_dispatch_commands(cmds, "mPyMesh", src,
                                        mpx_base="MPxNode")
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["native"], ["mPyMesh"],
                         "the shipped mPyMesh setup must still lower to C++")
        return out["classes"]

    def test_the_lowered_create_selects_the_bodys_last_dag_node(self):
        cpp = self._emit()
        self.assertIn('_o_n1 = _dagMod.createNode("mesh"', cpp,
                      "_o_n1 is the LAST node the mPyMesh body creates")
        self.assertIn(self.SELECT, cpp)
        self.assertNotIn("MGlobal::select(_self", cpp,
                         "the body's creates reselect over the mPyNode")

    def test_the_select_fires_after_the_body_built(self):
        """Selecting before buildBody() leaves the WRONG node selected (and a
        failed body would leave a selection the Python form never makes)."""
        cpp = self._emit()
        self.assertLess(cpp.index("st = buildBody();"), cpp.index(self.SELECT))

    def test_the_select_is_replayed_on_redo(self):
        """doIt and redoIt both have to leave the same selection behind."""
        self.assertEqual(self._emit().count(self.SELECT), 2)

    def test_undo_restores_the_selection_the_command_replaced(self):
        """Maya's own createNode undo puts back what was selected before it;
        replacing the selection and never restoring it does not."""
        cpp = self._emit()
        self.assertEqual(2, cpp.count("MGlobal::getActiveSelectionList(_priorSel);"),
                         "snapshot once per do and once per redo")
        restore = "MGlobal::setActiveSelectionList(_priorSel, MGlobal::kReplaceList);"
        self.assertIn(restore, cpp)
        self.assertLess(cpp.index("_nodeMod.undoIt();"), cpp.index(restore),
                        "restore after the modifiers are rolled back")
        self.assertIn("MSelectionList _priorSel;", cpp)

    def test_the_snapshot_precedes_the_select_it_pairs_with(self):
        cpp = self._emit()
        self.assertLess(cpp.index("MGlobal::getActiveSelectionList(_priorSel);"),
                        cpp.index(self.SELECT))


class TestNativeLoweringRefusesUnmodelledCreates(unittest.TestCase):
    """``createNode``'s TYPE is the one wildcard the recognised grammar still
    admits, and for two whole classes of it the emitted C++ is NOT the twin of
    the body it replaces. Both were measured against Maya 2026 (an
    ``MDagModifier`` is the only create the lowering emits):

      * a DG type -- ``MDagModifier::createNode("decomposeMatrix", ...)`` comes
        back ``kInvalidParameter``, so the compiled command FAILS outright where
        the ``cmds.createNode`` it replaced succeeded;
      * a SHAPE type with no ``parent`` -- ``cmds.createNode("mesh", name=X)``
        names the SHAPE X, while ``MDagModifier::createNode("mesh", kNullObj)``
        hands back the AUTO-CREATED TRANSFORM, so the rename lands on the
        transform and the local binds to it. A later ``sets()`` on that local
        then shades the TRANSFORM -- wrong, and silently so, because
        ``MFnSet::addMember`` accepts it without error.

    Refusing costs nothing: the command keeps the Python payload it has today.
    """

    HEAD = ("@maya_command(creates=True)\n"
            "def setup(self, *args, **kwargs):\n"
            "    from maya import cmds as mc\n"
            "    name = self.get_name()\n")

    def _plan(self, body):
        cmds = resolve_create_command_names(
            detect_commands(self.HEAD + body), "mPyThing")
        self.assertEqual(len(cmds), 1)
        return cd.native_plan_for(cmds[0], cd.flag_spec_for(cmds[0]))

    def _shape_under_a_transform(self, shape_type):
        return ('    xf = mc.createNode("transform", name=name + "Render")\n'
                '    sh = mc.createNode("%s", name=name + "RenderShape",\n'
                "                       parent=xf)\n"
                '    mc.sets(sh, edit=True, forceElement="initialShadingGroup")\n'
                "    return name\n" % shape_type)

    def test_every_shape_type_the_shipped_corpus_creates_still_lowers(self):
        """The four types the six shipped lowered bodies build. A refusal here
        would silently hand the whole corpus back to the Python payload."""
        for shape_type in ("mesh", "nurbsCurve", "nurbsSurface"):
            plan = self._plan(self._shape_under_a_transform(shape_type))
            self.assertIsNotNone(plan, shape_type)
            self.assertEqual([c["type"] for c in plan["creates"]],
                             ["transform", shape_type])

    def test_a_dg_node_type_is_refused(self):
        """MDagModifier::createNode rejects a non-DAG type, so this body would
        compile to a command that always errors."""
        self.assertIsNone(self._plan(
            '    dm = mc.createNode("decomposeMatrix", name=name + "_decomp")\n'
            '    mc.connectAttr(name + ".outMatrix", dm + ".inputMatrix",\n'
            "                   force=True)\n"
            "    return name\n"))

    def test_a_shape_with_no_parent_is_refused(self):
        """The rename would land on the auto-created transform, and the local
        -- here the connect destination -- would bind to it."""
        self.assertIsNone(self._plan(
            '    sh = mc.createNode("mesh", name=name + "RenderShape")\n'
            '    mc.connectAttr(name + ".outMesh", sh + ".inMesh", force=True)\n'
            "    return name\n"))

    def test_a_parentless_shape_feeding_sets_is_refused(self):
        """The SILENT case: MFnSet::addMember on the auto-created transform
        succeeds, so the mis-lowering shades the wrong object with no error."""
        self.assertIsNone(self._plan(
            '    sh = mc.createNode("mesh", name=name + "RenderShape")\n'
            '    mc.sets(sh, edit=True, forceElement="initialShadingGroup")\n'
            "    return name\n"))

    def test_a_shape_parented_under_a_shape_is_refused(self):
        """The mirror of the parentless-shape case, on the PARENT side.
        Measured against Maya 2026: ``cmds.createNode("mesh", parent=<mesh>)``
        only WARNS ("Cannot place non-transform node in the underworld of a
        shape") and re-homes the new shape under a fresh transform, while
        ``MDagModifier::createNode("mesh", <mesh MObject>)`` raises
        ``parent is not a transform type`` -- so the compiled command would
        FAIL outright where the body it replaced succeeded."""
        self.assertIsNone(self._plan(
            '    xf = mc.createNode("transform", name=name + "Render")\n'
            '    sh = mc.createNode("mesh", name=name + "RenderShape",\n'
            "                       parent=xf)\n"
            '    sh2 = mc.createNode("mesh", name=name + "RenderShape2",\n'
            "                        parent=sh)\n"
            '    mc.sets(sh2, edit=True, forceElement="initialShadingGroup")\n'
            "    return name\n"))

    def test_an_unverified_type_is_refused_rather_than_assumed(self):
        """A type nothing measured is a MISS, not a guess that it is a DAG
        node -- the grammar's stated rule is that it admits no wildcard."""
        self.assertIsNone(self._plan(
            '    x = mc.createNode("someUserPlugInType", name=name + "X")\n'
            '    mc.connectAttr(name + ".outMesh", x + ".inMesh", force=True)\n'
            "    return name\n"))


if __name__ == "__main__":
    unittest.main()
