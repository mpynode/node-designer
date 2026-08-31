"""OSL output tab/source, managed output, deterministic + AI Compute->OSL convert, LLM osl tool

Consolidated from: test_osl_managed_output.py, test_osl_source.py, test_osl_convert.py, test_osl_ai_convert.py, test_osl_convert_action.py, test_osl_tab.py, test_osl_tool.py.
"""

from __future__ import annotations

# ===================== from test_osl_managed_output.py =====================
import os
import tempfile
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__osl_managed_output():
    standalone_init()
    ensure_plugins_loaded()


_OSL_SRC__osl_managed_output = (
    "shader mpyMgd(output color outColor = color(0))\n"
    "{ outColor = color(1); }\n"
)


class TestManagedShaderOutputsConstant(unittest.TestCase):
    def test_osl_in_constant(self):
        from mpynode._common.osl.osl_registry import MANAGED_SHADER_OUTPUTS
        self.assertIn("osl", MANAGED_SHADER_OUTPUTS)


class TestOslIsManagedOutput(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        # createNode (NOT the wrapper create()) proves osl is on the TYPE.
        self.node = mc.createNode("mPyFile", name="oslMgd#")

    def test_fresh_node_has_osl_without_authoring(self):
        # No set_osl_expression call -> osl must already exist (static attr).
        self.assertTrue(mc.attributeQuery("osl", node=self.node, exists=True))

    def test_osl_default_is_empty(self):
        self.assertEqual(mc.getAttr(self.node + ".osl") or "", "")

    def test_osl_classified_output_in_walker(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree
        rows = {r.short_name: r for r in walk_plug_tree(self.node)}
        self.assertIn("osl", rows, "osl must be surfaced by the plug walker")
        self.assertEqual(
            rows["osl"].direction, "OUTPUT",
            "osl must classify as OUTPUT (managed shader output)",
        )
        self.assertFalse(
            rows["osl"].is_user_added,
            "osl must NOT be a user-added (deletable) attr",
        )

    def test_osl_hidden_from_maya_attribute_editor(self):
        # osl is writable, so Maya's auto-AE would render it as an editable text
        # field unless flagged hidden -- it is a wire/tab artifact, not an
        # artist control. It stays visible to the Designer walker and settable.
        self.assertTrue(
            mc.attributeQuery("osl", node=self.node, hidden=True),
            "osl must be hidden from Maya's Attribute Editor",
        )

    def test_osl_is_not_deletable(self):
        # A static type attribute cannot be removed via deleteAttr.
        try:
            mc.deleteAttr(self.node + ".osl")
        except Exception:
            pass
        self.assertTrue(
            mc.attributeQuery("osl", node=self.node, exists=True),
            "static osl output must survive a deleteAttr attempt",
        )

    def test_osl_not_in_outColor_affects(self):
        # string-in-affects-color breaks Maya 2026's VP2 fragment binding.
        affected = set(mc.affects("outColor", self.node) or [])
        self.assertNotIn("osl", affected)

    def test_essential_inputs_still_affect_outColor(self):
        # Guard: registering osl must not disturb the existing affects graph.
        affected = set(mc.affects("outColor", self.node) or [])
        for req in ("uCoord", "vCoord", "fileName", "colorSpace"):
            self.assertIn(req, affected)

    def test_osl_round_trips_via_mixin(self):
        from mpynode.wrappers.mpy_file import MPyFile
        w = MPyFile(self.node)
        self.assertTrue(w.set_osl_expression(_OSL_SRC__osl_managed_output))
        self.assertEqual(w.get_osl_expression(), _OSL_SRC__osl_managed_output)

    def test_osl_is_connectable_source(self):
        mc.setAttr(self.node + ".osl", _OSL_SRC__osl_managed_output, type="string")
        sink = mc.createNode("script", name="oslSink#") + ".before"
        mc.connectAttr(self.node + ".osl", sink, force=True)
        self.assertTrue(mc.isConnected(self.node + ".osl", sink))
        self.assertEqual(mc.getAttr(sink), _OSL_SRC__osl_managed_output)


class TestOslMaRoundTrip(unittest.TestCase):
    def test_ma_round_trip(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        w = MPyFile.create(name="oslRt#", seed_defaults=False, as_texture=False)
        w.set_osl_expression(_OSL_SRC__osl_managed_output)
        name = w.get_name()
        path = os.path.join(tempfile.mkdtemp(), "osl_mgd_rt.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        mc.file(path, open=True, force=True)
        self.assertTrue(mc.attributeQuery("osl", node=name, exists=True))
        self.assertEqual(mc.getAttr(name + ".osl"), _OSL_SRC__osl_managed_output)


class TestOslExcludedFromCompiledPort(unittest.TestCase):
    def test_output_map_excludes_osl(self):
        """get_output_attr_map drives the compiled spec; osl must never be in
        it (it is render-authoring metadata, not a user output)."""
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        w = MPyFile.create(name="oslMap#", seed_defaults=False,
                           as_texture=False)
        w.set_osl_expression(_OSL_SRC__osl_managed_output)
        self.assertNotIn("osl", w.get_output_attr_map() or {})
        self.assertNotIn("osl", w.get_input_attr_map() or {})

    def test_spec_excludes_osl(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.native.spec import spec_extractor
        w = MPyFile.create(name="oslPort#", seed_defaults=False,
                           as_texture=False)
        w.add_input_attr("tIn", "float")
        w.set_compute_expression(
            "self.outColor = [0.5, 0.5, 0.5]\nself.outAlpha = 1.0\n"
        )
        w.set_osl_expression(_OSL_SRC__osl_managed_output)
        spec = spec_extractor.extract_spec(w.get_name())
        self.assertNotIn("osl", spec.get("outputs", {}),
                         "osl (render-authoring) must not be a compiled output")
        self.assertNotIn("osl", spec.get("inputs", {}))


# ===================== from test_osl_source.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__osl_source():
    standalone_init()
    ensure_plugins_loaded()


# A minimal but VALID OSL surface shader -- one float param so OSLSceneModel has
# something to introspect into a param_* attr (the compile-success signal).
_OSL_SRC__osl_source = (
    "shader mpyTest(\n"
    "    float gain = 1.0,\n"
    "    output color outColor = color(0.0))\n"
    "{\n"
    "    outColor = color(gain, gain, gain);\n"
    "}\n"
)


class TestOslSourceMixin(unittest.TestCase):
    """C1 + C2: round-trip + connectable string output."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        # as_texture=False keeps it a bare DG node (no place2dTexture noise).
        self.f = MPyFile.create(
            name="oslSrc#", seed_defaults=False, as_texture=False
        )

    def test_has_is_false_before_set(self):
        self.assertFalse(self.f.has_osl_expression())
        # Pure-string getter never raises even with no plug yet.
        self.assertEqual(self.f.get_osl_expression(), "")

    def test_set_get_round_trip(self):
        self.assertTrue(self.f.set_osl_expression(_OSL_SRC__osl_source))
        self.assertEqual(self.f.get_osl_expression(), _OSL_SRC__osl_source)
        self.assertTrue(self.f.has_osl_expression())

    def test_clear(self):
        self.f.set_osl_expression(_OSL_SRC__osl_source)
        self.f.clear_osl_expression()
        self.assertEqual(self.f.get_osl_expression(), "")
        self.assertFalse(self.f.has_osl_expression())

    def test_plug_is_a_connectable_string_source(self):
        """The whole point of an OUTPUT (vs an internal kInternal plug): osl
        must be wireable as a connection SOURCE into another node's string
        input. Use a stock node's string attr as the stand-in sink so this
        holds with or without MtoA."""
        self.f.set_osl_expression(_OSL_SRC__osl_source)
        src = self.f.get_name() + ".osl"
        # 'script' node has a writable string attr 'before' -- a neutral sink.
        sink = mc.createNode("script", name="oslSink#") + ".before"
        mc.connectAttr(src, sink, force=True)
        self.assertTrue(mc.isConnected(src, sink))
        # And the value flows across the wire.
        self.assertEqual(mc.getAttr(sink), _OSL_SRC__osl_source)

    def test_osl_attr_persists_in_ascii(self):
        """A storable string attr must survive a .ma save/load round-trip so the
        authored OSL is not lost (it is the canonical artifact in Option A)."""
        import tempfile, os
        self.f.set_osl_expression(_OSL_SRC__osl_source)
        path = os.path.join(tempfile.mkdtemp(), "osl_rt.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        mc.file(path, open=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        reopened = MPyFile("oslSrc1")
        self.assertEqual(reopened.get_osl_expression(), _OSL_SRC__osl_source)


class TestApplyOslToArnold(unittest.TestCase):
    """C3: compile the node's OSL into a live aiOslShader (MtoA-gated)."""

    def setUp(self):
        mc.file(new=True, force=True)
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
        except Exception as exc:
            self.skipTest("MtoA unavailable: %s" % exc)
        try:
            import mtoa.osl  # noqa: F401
        except Exception as exc:
            self.skipTest("mtoa.osl unavailable: %s" % exc)
        from mpynode.wrappers.mpy_file import MPyFile
        self.f = MPyFile.create(
            name="oslApply#", seed_defaults=False, as_texture=False
        )
        self.f.set_osl_expression(_OSL_SRC__osl_source)

    def test_apply_creates_compiled_and_connected_shader(self):
        from mpynode._common.osl.osl_targets import apply_osl_to_arnold
        node = self.f.get_name()
        osl = apply_osl_to_arnold(node)
        self.assertIsNotNone(osl, "apply_osl_to_arnold returned None with MtoA")
        # .code carries the source Arnold actually compiles.
        self.assertEqual(mc.getAttr(osl + ".code"), _OSL_SRC__osl_source)
        # Compile must have materialized at least one param_* attr.
        params = mc.listAttr(osl, userDefined=True) or []
        self.assertTrue(params, "no params -> OSL did not compile")
        # The connectable output is wired into the shader's codeCache.
        self.assertTrue(
            mc.isConnected(node + ".osl", osl + ".codeCache"),
            "node.osl was not wired into aiOslShader.codeCache",
        )

    def test_apply_returns_none_for_empty_osl(self):
        from mpynode._common.osl.osl_targets import apply_osl_to_arnold
        self.f.clear_osl_expression()
        self.assertIsNone(apply_osl_to_arnold(self.f.get_name()))


class TestValidateOslViaArnold(unittest.TestCase):
    """validate_osl_via_arnold(osl) -> (ok, error): the compile-validate the AI
    fallback uses to gate / self-repair its translated OSL. Compiles a throwaway
    aiOslShader and reads the param-materialization success signal, then deletes
    the temp node. Returns (True, "") when MtoA is absent (can't validate -> the
    structural gate is the only acceptance test)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _require_mtoa(self):
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
            import mtoa.osl  # noqa: F401
        except Exception as exc:
            self.skipTest("MtoA unavailable: %s" % exc)

    def test_empty_source_is_invalid_without_mtoa(self):
        # Pure: empty/whitespace is rejected before any MtoA touch.
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        ok, err = validate_osl_via_arnold("   ")
        self.assertFalse(ok)
        self.assertTrue(err)

    def test_valid_osl_compiles_clean(self):
        self._require_mtoa()
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        before = set(mc.ls(type="aiOslShader") or [])
        ok, err = validate_osl_via_arnold(_OSL_SRC__osl_source)
        self.assertTrue(ok, "valid OSL reported invalid: %r" % err)
        self.assertEqual(err, "")
        # No temp validation node is left behind.
        after = set(mc.ls(type="aiOslShader") or [])
        self.assertEqual(before, after, "validation leaked an aiOslShader node")

    def test_garbage_osl_reports_error(self):
        self._require_mtoa()
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold
        ok, err = validate_osl_via_arnold(
            "shader broken( output color outColor = color(0)) "
            "{ this is not valid osl ###; }"
        )
        self.assertFalse(ok, "garbage OSL reported valid")
        self.assertTrue(err, "no error message for invalid OSL")
        # And it still cleans up.
        self.assertFalse(mc.ls(type="aiOslShader") or [],
                         "validation leaked a node on failure")


class TestCLevelDiagnosticCapture(unittest.TestCase):
    """oslc writes its diagnostics at the C level (Arnold's logger, not
    ``sys.stderr``), so only a dup2 of the real file descriptors catches them --
    a Python-level redirect sees nothing. The capture must also be
    fail-soft: never swallow the body's exception, always restore fd 1 / 2."""

    def test_captures_fd_level_writes(self):
        from mpynode._common.osl import osl_targets

        with osl_targets._capture_c_output() as captured:
            os.write(2, b"c-level-stderr\n")
            os.write(1, b"c-level-stdout\n")
        text = "".join(captured)
        self.assertIn("c-level-stderr", text)
        self.assertIn("c-level-stdout", text)

    def test_restores_the_real_descriptors(self):
        from mpynode._common.osl import osl_targets

        before = [os.fstat(fd)[:2] for fd in (1, 2)]
        with osl_targets._capture_c_output():
            self.assertNotEqual([os.fstat(fd)[:2] for fd in (1, 2)], before,
                                "fds were not actually redirected")
        self.assertEqual([os.fstat(fd)[:2] for fd in (1, 2)], before)

    def test_body_exception_propagates_and_text_is_kept(self):
        from mpynode._common.osl import osl_targets

        before = [os.fstat(fd)[:2] for fd in (1, 2)]
        captured = None
        with self.assertRaises(ValueError):
            with osl_targets._capture_c_output() as cap:
                captured = cap
                os.write(2, b"partial-diagnostic\n")
                raise ValueError("boom")
        self.assertIn("partial-diagnostic", "".join(captured))
        self.assertEqual([os.fstat(fd)[:2] for fd in (1, 2)], before,
                         "fds must be restored even when the body raises")

    def test_degrades_to_a_no_op_when_the_redirect_cannot_be_installed(self):
        """A capture that cannot be installed must still run the body (and
        leave the fds alone) -- a missing diagnostic is never a crash."""
        from mpynode._common.osl import osl_targets

        before = [os.fstat(fd)[:2] for fd in (1, 2)]
        orig = os.dup

        def _boom(_fd):
            raise OSError("no descriptors for you")

        os.dup = _boom
        try:
            ran = []
            with osl_targets._capture_c_output() as captured:
                ran.append(True)
        finally:
            os.dup = orig
        self.assertTrue(ran, "body did not run")
        self.assertEqual("".join(captured), "")
        self.assertEqual([os.fstat(fd)[:2] for fd in (1, 2)], before)


class TestValidateSurfacesOslcDiagnostic(unittest.TestCase):
    """The AI self-repair prompt is fed ONLY by validate_osl_via_arnold's error
    string, so it has to carry the actual oslc compiler diagnostic -- not just
    ``str(exc)`` / the generic "no shader params materialized"."""

    def setUp(self):
        mc.file(new=True, force=True)
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
            import mtoa.osl  # noqa: F401
        except Exception as exc:
            self.skipTest("MtoA unavailable: %s" % exc)

    def test_garbage_osl_error_carries_the_compiler_message(self):
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold

        ok, err = validate_osl_via_arnold(
            "shader broken( output color outColor = color(0)) "
            "{ this is not valid osl ###; }"
        )
        self.assertFalse(ok)
        self.assertIn("[osl]", err,
                      "error must carry the oslc diagnostic, got %r" % err)
        self.assertIn("error:", err,
                      "error must carry the oslc diagnostic, got %r" % err)
        self.assertNotIn("no shader params materialized", err)


class TestAiConvertWithRealArnoldValidation(unittest.TestCase):
    """Integration: the AI self-repair loop (osl_ai_convert) closed with the REAL
    Arnold compile-validator (osl_targets.validate_osl_via_arnold). The LLM is
    faked (returns broken OSL first, then good), but the rejection that drives the
    repair is a GENUINE oslc diagnostic from Arnold -- proving the loop converges
    on real compiler feedback, not just a stubbed validator."""

    def setUp(self):
        mc.file(new=True, force=True)
        try:
            if not mc.pluginInfo("mtoa", q=True, loaded=True):
                mc.loadPlugin("mtoa")
            import mtoa.osl  # noqa: F401
        except Exception as exc:
            self.skipTest("MtoA unavailable: %s" % exc)

    def test_real_validator_drives_one_self_repair(self):
        from mpynode._common.osl.osl_ai_convert import ai_convert_compute_to_osl
        from mpynode._common.osl.osl_targets import validate_osl_via_arnold

        broken = (
            "shader oslAi( output color outColor = color(0)) "
            "{ this is not valid osl ###; }"
        )
        good = _OSL_SRC__osl_source  # the known-valid golden shader
        calls = []

        def fake_complete(system, user):
            calls.append((system, user))
            return broken if len(calls) == 1 else good

        out = ai_convert_compute_to_osl(
            "u, v = self.uvCoord\nself.outColor = (u, v, 0.0)\n",
            "", "oslAi", fake_complete, validate_fn=validate_osl_via_arnold)

        self.assertEqual(out.strip(), good.strip())
        self.assertEqual(len(calls), 2, "real validator should reject #1, accept #2")
        # The repair prompt carried the real validator's rejection -- and that
        # rejection IS the oslc diagnostic: Arnold logs it at the C level (never
        # as a Python exception), so it only reaches the model because
        # validate_osl_via_arnold fd-captures the compile.
        repair_user = calls[1][1]
        self.assertIn("REJECTED", repair_user)
        self.assertIn("[osl]", repair_user)
        self.assertIn("error:", repair_user)


# ===================== from test_osl_convert.py =====================
import importlib.util
import os
import unittest


def _load_scanline_defs():
    """Import the demo's single-source-of-truth module by path (it lives outside
    the test PYTHONPATH and imports only os/re, so this is safe headless)."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "data", "scanline_defs.py")
    spec = importlib.util.spec_from_file_location("_scanline_defs_fixture", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _load_scanline_defs()


class TestConverterApi(unittest.TestCase):
    def test_module_exposes_public_api(self):
        from mpynode._common.osl import osl_convert as oc
        self.assertTrue(callable(oc.convert_compute_to_osl))
        self.assertTrue(callable(oc.extract_simple_consts))
        self.assertTrue(issubclass(oc.UnsupportedComputeError, Exception))


class TestExtractConsts(unittest.TestCase):
    def test_pulls_numeric_module_consts_from_init(self):
        from mpynode._common.osl import osl_convert as oc
        consts = oc.extract_simple_consts(S.INIT_SRC)
        self.assertEqual(consts.get("NUM_BANDS"), S.NUM_BANDS)
        self.assertEqual(consts.get("SPEED"), S.SPEED)
        self.assertEqual(consts.get("TWO_PI"), S.TWO_PI)

    def test_ignores_imports_and_functions(self):
        from mpynode._common.osl import osl_convert as oc
        consts = oc.extract_simple_consts(S.INIT_SRC)
        # _grid / _scanline_rows etc. are functions, not numeric consts.
        self.assertNotIn("_grid", consts)
        self.assertNotIn("np", consts)


class TestKeystoneReproducesGoldenTwin(unittest.TestCase):
    """The whole point: derive the existing Arnold OSL twin from the Compute."""

    def test_reproduces_arnold_osl_src_byte_for_byte(self):
        from mpynode._common.osl import osl_convert as oc
        consts = oc.extract_simple_consts(S.INIT_SRC)
        osl = oc.convert_compute_to_osl(
            S.COMPUTE_SRC, consts=consts, shader_name="scanline_overtime"
        )
        self.assertEqual(osl, S.ARNOLD_OSL_SRC)


class TestStructure(unittest.TestCase):
    def setUp(self):
        from mpynode._common.osl import osl_convert as oc
        self.oc = oc
        self.osl = oc.convert_compute_to_osl(
            S.COMPUTE_SRC,
            consts=oc.extract_simple_consts(S.INIT_SRC),
            shader_name="scanline_overtime",
        )

    def test_shader_skeleton_and_output(self):
        self.assertIn("shader scanline_overtime(", self.osl)
        self.assertIn("output color outColor = color(0))", self.osl)

    def test_declares_filename_and_tin_params(self):
        self.assertIn('string filename = ""', self.osl)
        self.assertIn("float tIn = 0.0", self.osl)

    def test_maps_python_math_and_self_reads(self):
        self.assertIn("sin(", self.osl)
        self.assertNotIn("math.sin", self.osl)
        self.assertNotIn("self.tIn", self.osl)
        self.assertIn("tIn * SPEED", self.osl)

    def test_image_sample_idiom_collapses_to_texture(self):
        self.assertIn("texture(filename, u, 1.0 - v)", self.osl)
        self.assertIn("color grid", self.osl)
        # the manual pixel indexing must NOT survive into OSL
        self.assertNotIn("shape", self.osl)
        self.assertNotIn("[py", self.osl)

    def test_output_collapses_to_color_times_scalar(self):
        self.assertIn("outColor = grid * scan;", self.osl)


class TestNotVacuous(unittest.TestCase):
    """Mutate inputs; the output MUST change accordingly (it is not a lookup)."""

    def test_constants_flow_through(self):
        from mpynode._common.osl import osl_convert as oc
        osl = oc.convert_compute_to_osl(
            S.COMPUTE_SRC,
            consts={"NUM_BANDS": 3.0, "SPEED": 0.25, "TWO_PI": 6.0},
            shader_name="scanline_overtime",
        )
        self.assertIn("float NUM_BANDS = 3.0;", osl)
        self.assertIn("float SPEED = 0.25;", osl)
        self.assertIn("float TWO_PI = 6.0;", osl)
        self.assertNotIn("12.0", osl)

    def test_look_math_flows_through(self):
        from mpynode._common.osl import osl_convert as oc
        mutated = S.COMPUTE_SRC.replace(
            "scan = 0.4 + 0.6 * s", "scan = 0.3 + 0.7 * s"
        )
        osl = oc.convert_compute_to_osl(
            mutated,
            consts=oc.extract_simple_consts(S.INIT_SRC),
            shader_name="scanline_overtime",
        )
        self.assertIn("0.3 + 0.7 * s", osl)
        self.assertNotIn("0.4 + 0.6 * s", osl)

    def test_input_name_flows_through(self):
        from mpynode._common.osl import osl_convert as oc
        mutated = S.COMPUTE_SRC.replace("self.tIn", "self.frame")
        osl = oc.convert_compute_to_osl(
            mutated,
            consts=oc.extract_simple_consts(S.INIT_SRC),
            shader_name="scanline_overtime",
        )
        self.assertIn("float frame = 0.0", osl)
        self.assertIn("frame * SPEED", osl)
        self.assertNotIn("tIn", osl)


class TestUnsupportedFallsBack(unittest.TestCase):
    def test_loop_raises_with_assistant_hint(self):
        from mpynode._common.osl import osl_convert as oc
        with self.assertRaises(oc.UnsupportedComputeError) as ctx:
            oc.convert_compute_to_osl(
                "for i in range(3):\n    self.outColor = (0.0, 0.0, 0.0)\n",
                consts={},
                shader_name="x",
            )
        self.assertIn("assistant", str(ctx.exception).lower())

    def test_numpy_array_op_raises(self):
        from mpynode._common.osl import osl_convert as oc
        with self.assertRaises(oc.UnsupportedComputeError):
            oc.convert_compute_to_osl(
                "self.outColor = np.zeros(3)\n", consts={}, shader_name="x"
            )

    def test_unknown_free_name_raises(self):
        from mpynode._common.osl import osl_convert as oc
        with self.assertRaises(oc.UnsupportedComputeError):
            oc.convert_compute_to_osl(
                "s = mystery * 2.0\nself.outColor = (s, s, s)\n",
                consts={},
                shader_name="x",
            )


class TestNeverEmitsInvalidOrWrongOsl(unittest.TestCase):
    """Adversarial-review regressions: the converter must RAISE (-> AI fallback)
    rather than silently emit invalid or numerically-wrong OSL. The cardinal sin
    of the deterministic arm is producing OSL a user would trust but a renderer
    rejects (or, worse, accepts with the wrong value)."""

    def _convert(self, body):
        from mpynode._common.osl import osl_convert as oc
        src = "%s\nself.outColor = (s, s, s)\n" % body
        return oc.convert_compute_to_osl(src, consts={}, shader_name="x")

    def test_non_osl_binary_operators_raise(self):
        from mpynode._common.osl.osl_convert import UnsupportedComputeError
        # //, **, %, ^, &, |, <<, >> have no valid OSL float equivalent here
        # ('//' is even an OSL line comment -> dangling statement).
        for op in ("a // 2.0", "a ** 2.0", "a % 2.0", "a ^ 2.0",
                   "a & 2.0", "a | 2.0", "a << 2.0", "a >> 2.0"):
            with self.assertRaises(UnsupportedComputeError, msg=op):
                self._convert("a = 7.0\ns = %s" % op)

    def test_bitwise_unary_invert_raises(self):
        from mpynode._common.osl.osl_convert import UnsupportedComputeError
        with self.assertRaises(UnsupportedComputeError):
            self._convert("a = 7.0\ns = ~a")

    def test_unary_minus_still_supported(self):
        # -x is valid OSL; must NOT be collateral damage of the operator guard.
        osl = self._convert("a = 7.0\ns = -a")
        self.assertIn("float s = -a;", osl)

    def test_plus_minus_times_divide_still_supported(self):
        osl = self._convert("a = 7.0\ns = a + 1.0 - 2.0 * a / 3.0")
        self.assertIn("a + 1.0 - 2.0 * a / 3.0", osl)

    def test_non_numeric_inline_literals_raise(self):
        from mpynode._common.osl.osl_convert import UnsupportedComputeError
        for body in ("s = None", "s = True", "s = 'hi'", "s = f'{1}'"):
            with self.assertRaises(UnsupportedComputeError, msg=body):
                self._convert(body)

    def test_integer_division_is_not_silently_wrong(self):
        # Python `1 / 2` == 0.5; OSL int division `1 / 2` == 0. The converter
        # must NOT emit bare-int division -- this locks the float-coercion
        # behaviour, which keeps the look-math faithful.
        osl = self._convert("s = 1 / 2")
        self.assertNotIn("float s = 1 / 2;", osl)
        self.assertIn("float s = 1.0 / 2.0;", osl)

    def test_integer_literals_emit_as_float(self):
        osl = self._convert("s = 3 + 4")
        self.assertIn("3.0 + 4.0", osl)
        self.assertNotIn("3 + 4", osl)


class TestAssessTractability(unittest.TestCase):
    """assess_osl_tractability distinguishes 'unsupported by the deterministic
    grammar but AI could translate it' (e.g. the colour-management pipeline)
    from 'structurally IMPOSSIBLE in OSL' (e.g. compositeTexture: a runtime
    ARRAY of textures + integer dimension outputs). The intractable case must
    be refused fast with an actionable reason, never sent to a doomed AI round."""

    def _assess(self, *a, **k):
        from mpynode._common.osl import osl_convert as oc
        return oc.assess_osl_tractability(*a, **k)

    # -- tractable: the canonical single-texture look-math -------------------
    def test_single_texture_lookmath_is_tractable(self):
        ok, reason = self._assess(_COMPUTE, _INIT)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_writes_only_color_outputs_is_tractable(self):
        ok, reason = self._assess(
            "u, v = self.uvCoord\nself.outColor = (u, v, 0.0)\nself.outAlpha = 1.0\n")
        self.assertTrue(ok)

    # -- intractable via SOURCE: writes a non-colour self output ------------
    def test_non_color_self_output_is_intractable(self):
        # compositeTexture writes self.maxWidth / self.maxHeight (int outputs).
        ok, reason = self._assess(
            "img = _composite_image(self)\n"
            "self.outColor = (1.0, 0.0, 1.0)\n"
            "self.maxWidth = 0\nself.maxHeight = 0\n")
        self.assertFalse(ok)
        self.assertIn("maxWidth", reason)

    # -- intractable via ATTR METADATA: an array input --------------------
    def test_array_input_attr_is_intractable(self):
        ok, reason = self._assess(
            "self.outColor = (0.0, 0.0, 0.0)\n",
            input_attrs={"filePaths": {"attr_type": "string", "is_array": True}})
        self.assertFalse(ok)
        self.assertIn("filePaths", reason)
        self.assertIn("array", reason.lower())

    def test_scalar_inputs_are_tractable(self):
        ok, reason = self._assess(
            "self.outColor = (self.tIn, 0.0, 0.0)\n",
            input_attrs={"tIn": {"attr_type": "float", "is_array": False}})
        self.assertTrue(ok)

    # -- intractable via ATTR METADATA: an extra typed output ---------------
    def test_extra_output_attr_is_intractable(self):
        ok, reason = self._assess(
            "self.outColor = (0.0, 0.0, 0.0)\n",
            output_attrs={"maxWidth": {"attr_type": "int", "is_array": False}})
        self.assertFalse(ok)
        self.assertIn("maxWidth", reason)

    def test_bad_compute_source_is_treated_tractable(self):
        # A syntax error is a look-math problem the deterministic arm reports;
        # tractability must not raise on unparseable source (defensive).
        ok, reason = self._assess("this is (not python")
        self.assertTrue(ok)


# ===================== from test_osl_ai_convert.py =====================
import unittest

from mpynode._common.osl.osl_ai_convert import (
    ai_convert_compute_to_osl,
    build_osl_prompt,
    OslAiConvertError,
)

_GOOD_OSL = (
    "shader mpyfile_shader(\n"
    "    string filename = \"\",\n"
    "    float tIn = 0.0,\n"
    "    output color outColor = color(0))\n"
    "{\n"
    "    color grid = texture(filename, u, 1.0 - v);\n"
    "    outColor = grid;\n"
    "}\n"
)

_COMPUTE = (
    "linear = _load_linear_pixels(self.fileName, int(self.colorSpace),\n"
    "    bool(self.preFilter), int(self.preFilterKernel), float(self.preFilterRadius))\n"
    "u, v = self.uvCoord\n"
    "r, g, b, a = _sample(linear, float(u), float(v), 0, 0, (0.0, 0.0, 0.0))\n"
    "self.outColor = (r, g, b)\nself.outAlpha = a\n"
)
_INIT = "NUM_BANDS = 12.0\ndef _load_linear_pixels(*a): pass\n"


class _RecordingComplete:
    """A fake complete_fn that records each (system, user) call and returns
    canned outputs in order."""

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = []

    def __call__(self, system, user):
        self.calls.append((system, user))
        return self._outputs[len(self.calls) - 1]


class TestBuildPrompt(unittest.TestCase):
    def test_prompt_includes_compute_and_shader_name(self):
        system, user = build_osl_prompt(_COMPUTE, _INIT, "myShader")
        self.assertIn("OSL", system)
        self.assertIn("Open Shading Language", system)
        self.assertIn("myShader", user)
        self.assertIn("_load_linear_pixels", user)  # the compute look-math
        self.assertIn("NUM_BANDS", user)            # init context

    def test_prompt_carries_prior_error_on_repair(self):
        _, user0 = build_osl_prompt(_COMPUTE, _INIT, "s")
        self.assertNotIn("rejected", user0.lower())
        _, user1 = build_osl_prompt(_COMPUTE, _INIT, "s",
                                    prior_error="syntax error at line 3")
        self.assertIn("syntax error at line 3", user1)

    def test_system_prompt_forbids_tools_and_is_one_shot(self):
        # Reinforces --strict-mcp-config at the prompt level (belt & braces, and
        # helps API providers that never had tools): the model must emit the
        # shader directly, never try to search/read files.
        system, _ = build_osl_prompt(_COMPUTE, _INIT, "s")
        low = system.lower()
        self.assertIn("no tools", low)
        self.assertTrue("do not" in low or "never" in low)


class TestAiConvert(unittest.TestCase):
    def test_returns_osl_on_first_try_no_validator(self):
        cf = _RecordingComplete([_GOOD_OSL])
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf)
        self.assertEqual(out.strip(), _GOOD_OSL.strip())
        self.assertEqual(len(cf.calls), 1)

    def test_strips_markdown_fences(self):
        fenced = "```osl\n" + _GOOD_OSL + "```\n"
        cf = _RecordingComplete([fenced])
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf)
        self.assertNotIn("```", out)
        self.assertTrue(out.strip().startswith("shader"))

    def test_streams_attempt_and_rejection_markers_to_log(self):
        # "the log does not say much": the AI loop must announce each attempt and
        # WHY an attempt was rejected, so the activity strip shows real progress.
        cf = _RecordingComplete(["I cannot help with that.", _GOOD_OSL])
        logs = []
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "s", cf,
                                        log_cb=logs.append)
        self.assertEqual(out.strip(), _GOOD_OSL.strip())
        blob = "\n".join(logs).lower()
        self.assertIn("attempt 1", blob)
        self.assertIn("attempt 2", blob)
        self.assertIn("rejected", blob)

    def test_structural_failure_triggers_one_repair(self):
        # First output is junk (no shader/outColor); second is good.
        cf = _RecordingComplete(["I cannot help with that.", _GOOD_OSL])
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf)
        self.assertEqual(out.strip(), _GOOD_OSL.strip())
        self.assertEqual(len(cf.calls), 2)
        # the repair prompt must carry an error describing the structural problem
        self.assertTrue(any("rejected" in u.lower() or "shader" in u.lower()
                            for (_, u) in cf.calls[1:]))

    def test_validator_failure_triggers_repair_with_compiler_error(self):
        calls = []

        def validate_fn(osl):
            calls.append(osl)
            if len(calls) == 1:
                return False, "error: undeclared identifier 'foo' at line 6"
            return True, ""

        cf = _RecordingComplete([_GOOD_OSL, _GOOD_OSL])
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf,
                                        validate_fn=validate_fn)
        self.assertEqual(out.strip(), _GOOD_OSL.strip())
        self.assertEqual(len(cf.calls), 2)
        # the repair prompt carried the compiler error verbatim
        self.assertIn("undeclared identifier 'foo'", cf.calls[1][1])

    def test_gives_up_after_repair_budget_exhausted(self):
        def validate_fn(osl):
            return False, "persistent compile error"

        cf = _RecordingComplete([_GOOD_OSL, _GOOD_OSL, _GOOD_OSL])
        with self.assertRaises(OslAiConvertError) as ctx:
            ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf,
                                      validate_fn=validate_fn)
        # default budget = 1 repair => 2 total attempts
        self.assertEqual(len(cf.calls), 2)
        self.assertIn("persistent compile error", str(ctx.exception))

    def test_validator_ok_returns_immediately(self):
        def validate_fn(osl):
            return True, ""

        cf = _RecordingComplete([_GOOD_OSL])
        out = ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf,
                                        validate_fn=validate_fn)
        self.assertEqual(out.strip(), _GOOD_OSL.strip())
        self.assertEqual(len(cf.calls), 1)

    def test_empty_completion_is_unsupported(self):
        cf = _RecordingComplete(["", "   "])
        with self.assertRaises(OslAiConvertError):
            ai_convert_compute_to_osl(_COMPUTE, _INIT, "mpyfile_shader", cf)
        self.assertEqual(len(cf.calls), 2)  # tried, repaired, gave up

    def test_complete_fn_exception_propagates_as_convert_error(self):
        def boom(system, user):
            raise RuntimeError("network down")

        with self.assertRaises(OslAiConvertError) as ctx:
            ai_convert_compute_to_osl(_COMPUTE, _INIT, "s", boom)
        self.assertIn("network down", str(ctx.exception))


# ===================== from test_osl_convert_action.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init

import importlib.util
import os


def _scanline_srcs():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "data", "scanline_defs.py")
    spec = importlib.util.spec_from_file_location("_scanline_defs_action", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.INIT_SRC, mod.COMPUTE_SRC, mod.ARNOLD_OSL_SRC


def _setUpModule__osl_convert_action():
    standalone_init()
    ensure_plugins_loaded()


class TestConvertCapabilityGate(unittest.TestCase):
    def test_mpyfile_has_convert_capability(self):
        from mpynode.wrappers.mpy_file import MPyFile
        self.assertTrue(hasattr(MPyFile, "convert_compute_to_osl"))

    def test_plain_mpynode_lacks_convert_capability(self):
        from mpynode.wrappers._mpy_node import MPyNode
        self.assertFalse(hasattr(MPyNode, "convert_compute_to_osl"))


class TestConvertOnLiveNode(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        self.f = MPyFile.create(
            name="oslConv#", seed_defaults=False, as_texture=False
        )
        self.init_src, self.compute_src, self.golden = _scanline_srcs()

    def test_convert_populates_osl_from_node_tiers(self):
        self.f.set_init_expression(self.init_src)
        self.f.set_compute_expression(self.compute_src)
        osl = self.f.convert_compute_to_osl()
        # round-trips onto the connectable osl output
        self.assertEqual(self.f.get_osl_expression(), osl)
        # genuinely transpiled the look (idiom + math), not echoed
        self.assertIn("texture(filename, u, 1.0 - v)", osl)
        self.assertIn("outColor = grid * scan;", osl)
        self.assertIn("0.5 + 0.5 * sin(", osl)
        # shader is named for this node (valid OSL identifier)
        self.assertIn("shader %s(" % self.f.get_name(), osl)

    def test_unsupported_compute_raises_and_preserves_osl(self):
        from mpynode._common.osl.osl_convert import UnsupportedComputeError
        sentinel = "// hand-authored, keep me\n"
        self.f.set_osl_expression(sentinel)
        self.f.set_compute_expression(
            "for i in range(3):\n    self.outColor = (0.0, 0.0, 0.0)\n"
        )
        with self.assertRaises(UnsupportedComputeError):
            self.f.convert_compute_to_osl()
        # failed conversion must not clobber the existing osl
        self.assertEqual(self.f.get_osl_expression(), sentinel)


_AI_OSL = (
    "shader oslConv(\n"
    "    string filename = \"\",\n"
    "    output color outColor = color(0))\n"
    "{\n"
    "    outColor = texture(filename, u, 1.0 - v);\n"
    "}\n"
)


class TestConvertViaAiCapabilityGate(unittest.TestCase):
    def test_mpyfile_has_ai_convert_capability(self):
        from mpynode.wrappers.mpy_file import MPyFile
        self.assertTrue(hasattr(MPyFile, "convert_compute_to_osl_ai"))

    def test_plain_mpynode_lacks_ai_convert_capability(self):
        from mpynode.wrappers._mpy_node import MPyNode
        self.assertFalse(hasattr(MPyNode, "convert_compute_to_osl_ai"))


class TestConvertViaAiOnLiveNode(unittest.TestCase):
    """The AI arm on a live node, with the LLM transport INJECTED (no network):
    it gathers the node's Compute/Init, runs the AI core, and persists the
    translated OSL onto the connectable osl output."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        self.f = MPyFile.create(
            name="oslConv#", seed_defaults=False, as_texture=False
        )
        # A compute the DETERMINISTIC arm can't handle (full colour pipeline).
        self.f.set_compute_expression(
            "linear = _load_linear_pixels(self.fileName, int(self.colorSpace),\n"
            "    bool(self.preFilter), int(self.preFilterKernel), "
            "float(self.preFilterRadius))\n"
            "u, v = self.uvCoord\n"
            "self.outColor = (u, v, 0.0)\nself.outAlpha = 1.0\n"
        )

    def test_ai_convert_persists_translated_osl(self):
        seen = {}

        def fake_complete(system, user):
            seen["system"], seen["user"] = system, user
            return _AI_OSL

        osl = self.f.convert_compute_to_osl_ai(complete_fn=fake_complete)
        self.assertEqual(self.f.get_osl_expression(), osl)
        self.assertIn("texture(filename", osl)
        # the prompt actually carried this node's compute look-math
        self.assertIn("_load_linear_pixels", seen["user"])

    def test_ai_convert_failure_preserves_existing_osl(self):
        from mpynode._common.osl.osl_ai_convert import OslAiConvertError
        sentinel = "// hand-authored, keep me\n"
        self.f.set_osl_expression(sentinel)

        def fake_complete(system, user):
            return "I'm sorry, I can't do that."  # never structurally valid

        with self.assertRaises(OslAiConvertError):
            self.f.convert_compute_to_osl_ai(complete_fn=fake_complete)
        self.assertEqual(self.f.get_osl_expression(), sentinel)

    def test_ai_convert_refuses_intractable_compute_without_llm(self):
        # compositeTexture-shaped compute (writes non-colour self.maxWidth): the
        # AI arm must refuse FAST with an actionable reason and NEVER call the
        # LLM -- no more 6-minute flail on a structurally impossible translation.
        from mpynode._common.osl.osl_ai_convert import OslAiConvertError
        called = {"n": 0}

        def fake_complete(system, user):
            called["n"] += 1
            return _AI_OSL

        self.f.set_compute_expression(
            "u, v = self.uvCoord\n"
            "self.outColor = (u, v, 0.0)\n"
            "self.maxWidth = 0\nself.maxHeight = 0\n")
        with self.assertRaises(OslAiConvertError) as ctx:
            self.f.convert_compute_to_osl_ai(complete_fn=fake_complete)
        self.assertEqual(called["n"], 0)          # LLM never invoked
        self.assertIn("maxWidth", str(ctx.exception))


# ===================== from test_osl_tab.py =====================
import inspect
import unittest


class TestOslTabGatingSource(unittest.TestCase):
    """Source-level checks (no Qt instantiation needed)."""

    def setUp(self):
        from mpynode.ui.widgets import script_tab_content as stc
        self.stc = stc
        self.init_src = inspect.getsource(stc.NDScriptTabContent.__init__)

    def test_osl_tab_added_gated_by_capability(self):
        # The tab is created only behind the hasattr gate.
        self.assertIn('hasattr(py_node, "set_osl_expression")', self.init_src)
        self.assertIn('NDOslEditor(', self.init_src)
        # The editor is hosted (under the Translate button) then added as "OSL".
        self.assertIn('addTab(osl_tab, "OSL")', self.init_src)

    def test_imports_osl_editor(self):
        mod_src = inspect.getsource(self.stc)
        self.assertIn(
            "from mpynode.ui.widgets.osl_editor import NDOslEditor", mod_src
        )

    def test_osl_editor_in_save_dirty_refresh(self):
        for meth in ("hasUnsavedChanges", "markSaved", "refresh"):
            src = inspect.getsource(
                getattr(self.stc.NDScriptTabContent, meth)
            )
            self.assertIn(
                "_osl_editor", src,
                f"{meth} must include the OSL editor in the aggregate",
            )


class TestOslEditorShape(unittest.TestCase):
    def test_editor_contract(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        for meth in ("getMPyNode", "getText", "setText", "hasUnsavedChanges",
                     "markSaved", "refresh"):
            self.assertTrue(
                hasattr(NDOslEditor, meth), f"NDOslEditor missing {meth}"
            )
        self.assertTrue(hasattr(NDOslEditor, "dirtyStateChanged"))

    def test_markSaved_persists_via_set_osl_expression(self):
        src = inspect.getsource(
            __import__("mpynode.ui.widgets.osl_editor",
                       fromlist=["NDOslEditor"]).NDOslEditor.markSaved
        )
        self.assertIn("set_osl_expression", src)

    def test_refresh_pulls_via_get_osl_expression(self):
        src = inspect.getsource(
            __import__("mpynode.ui.widgets.osl_editor",
                       fromlist=["NDOslEditor"]).NDOslEditor.refresh
        )
        self.assertIn("get_osl_expression", src)


class TestOslConvertButton(unittest.TestCase):
    """The 'Translate Compute -> OSL' affordance (deterministic converter)."""

    def test_tab_hosts_convert_button_gated_by_capability(self):
        from mpynode.ui.widgets import script_tab_content as stc
        src = inspect.getsource(stc.NDScriptTabContent.__init__)
        self.assertIn('hasattr(py_node, "convert_compute_to_osl")', src)
        self.assertIn("Translate Compute", src)
        # The button routes through _on_osl_translate_clicked, which resets the
        # activity strip and then triggers the (capability-gated) conversion.
        self.assertIn("_on_osl_translate_clicked", src)
        handler = inspect.getsource(
            stc.NDScriptTabContent._on_osl_translate_clicked
        )
        self.assertIn("convertFromCompute", handler)

    def test_osl_editor_convert_method_uses_capability(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        self.assertTrue(hasattr(NDOslEditor, "convertFromCompute"))
        src = inspect.getsource(NDOslEditor.convertFromCompute)
        self.assertIn("convert_compute_to_osl", src)


class TestOslConvertAiFallback(unittest.TestCase):
    """The AI fallback arm of the Translate button: when the deterministic
    converter raises UnsupportedComputeError, the button auto-falls-back to a
    one-shot AI translation, run OFF the main thread (no Maya freeze), pre-flighted
    for a provider, compile-validated, and marshalled back to the main thread to
    persist. GUI/threading is verified at the source level (no Qt/Maya here)."""

    def _src(self, meth):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        return inspect.getsource(getattr(NDOslEditor, meth))

    def test_convert_catches_unsupported_and_falls_back(self):
        src = self._src("convertFromCompute")
        self.assertIn("UnsupportedComputeError", src)
        self.assertIn("_convert_via_ai", src)

    def test_ai_fallback_preflights_provider(self):
        src = self._src("_convert_via_ai")
        self.assertIn("check_provider", src)
        # capability-gated like the deterministic arm
        self.assertIn("convert_compute_to_osl_ai", src)

    def test_ai_fallback_runs_off_main_thread(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        # Some method must spawn a worker thread (the AI call blocks on network).
        whole = inspect.getsource(NDOslEditor)
        self.assertIn("threading", whole)
        self.assertIn("Thread(", whole)

    def test_ai_fallback_marshals_back_to_main_thread(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        whole = inspect.getsource(NDOslEditor)
        # Maya API (persist + compile-validate) must run on the main thread.
        self.assertIn("executeInMainThreadWithResult", whole)

    def test_ai_fallback_uses_core_and_compile_validator(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        whole = inspect.getsource(NDOslEditor)
        self.assertIn("ai_convert_compute_to_osl", whole)
        self.assertIn("validate_osl_via_arnold", whole)

    def test_busy_signal_exists(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        self.assertTrue(hasattr(NDOslEditor, "convertBusyChanged"))

    def test_marshal_failure_never_reruns_finish_on_worker_thread(self):
        """The worker MUST NOT re-run _finish_ai_convert (which touches Qt +
        writes the Maya scene) off the main thread when the marshal itself fails
        (e.g. the tab is torn down during a slow LLM call). The maya.utils import
        is guarded SEPARATELY from the marshal call; a real marshal failure logs
        and resets the busy latch instead of re-invoking the finish inline."""
        src = self._src("_run_ai_convert")
        self.assertIn("import maya.utils", src)
        # a genuine marshal failure logs + clears the latch (no off-thread re-run)
        self.assertIn("marshal", src.lower())
        self.assertIn("_ai_busy = False", src)

    def test_button_reflects_busy_state(self):
        from mpynode.ui.widgets import script_tab_content as stc
        src = inspect.getsource(stc.NDScriptTabContent.__init__)
        self.assertIn("convertBusyChanged", src)


class TestOslCapabilityGate(unittest.TestCase):
    """The gate itself: mPyFile is OSL-capable, plain mPyNode is not."""

    def test_mpyfile_wrapper_is_osl_capable(self):
        from mpynode.wrappers.mpy_file import MPyFile
        self.assertTrue(hasattr(MPyFile, "set_osl_expression"))
        self.assertTrue(hasattr(MPyFile, "get_osl_expression"))

    def test_plain_mpynode_wrapper_is_not_osl_capable(self):
        from mpynode.wrappers._mpy_node import MPyNode
        self.assertFalse(hasattr(MPyNode, "set_osl_expression"))


# ===================== from test_osl_tool.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__osl_tool():
    standalone_init()
    ensure_plugins_loaded()


_OSL_SRC__osl_tool = (
    "shader mpyTool(\n"
    "    float gain = 1.0,\n"
    "    output color outColor = color(0.0))\n"
    "{ outColor = color(gain); }\n"
)


class TestSetOslExpressionTool(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.llm import tools as T
        self.T = T

    def test_tool_is_registered(self):
        self.assertIn("set_osl_expression", self.T.VALID_TOOLS)
        schema = next(s for s in self.T.TOOL_SCHEMAS
                      if s["name"] == "set_osl_expression")
        self.assertIn("source", schema["input_schema"]["properties"])

    def test_dispatch_sets_osl_on_mpyfile(self):
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="oslTool#", seed_defaults=False,
                           as_texture=False)
        ctx = self.T.ToolContext(working_node=f.get_name())
        res = self.T.dispatch("set_osl_expression",
                              {"source": _OSL_SRC__osl_tool}, ctx)
        self.assertNotIn("error", res, "dispatch errored: %r" % res)
        self.assertEqual(f.get_osl_expression(), _OSL_SRC__osl_tool)

    def test_dispatch_accepts_osl_that_is_not_valid_python(self):
        """OSL braces are a SyntaxError in Python -- the tool must NOT run it
        through the Python syntax checker (regression guard)."""
        from mpynode.wrappers.mpy_file import MPyFile
        f = MPyFile.create(name="oslTool#", seed_defaults=False,
                           as_texture=False)
        ctx = self.T.ToolContext(working_node=f.get_name())
        # Leading brace etc. -- definitely not parseable as Python.
        res = self.T.dispatch("set_osl_expression",
                              {"source": _OSL_SRC__osl_tool}, ctx)
        self.assertNotIn("error", res)

    def test_dispatch_rejected_on_non_osl_node(self):
        """A node without an OSL output (plain mPyNode) must get a clear error,
        not a stack trace -- the tool is gated by capability."""
        node = mc.createNode("mPyNode", name="plainTool#")
        ctx = self.T.ToolContext(working_node=node)
        res = self.T.dispatch("set_osl_expression",
                              {"source": _OSL_SRC__osl_tool}, ctx)
        self.assertIn("error", res)
        self.assertIn("osl", res["error"].lower())

    def test_tool_summary(self):
        self.assertEqual(
            self.T.tool_summary("set_osl_expression", {}),
            "set_osl_expression",
        )


def setUpModule():
    _setUpModule__osl_managed_output()
    _setUpModule__osl_source()
    _setUpModule__osl_convert_action()
    _setUpModule__osl_tool()


if __name__ == "__main__":
    import unittest
    unittest.main()
