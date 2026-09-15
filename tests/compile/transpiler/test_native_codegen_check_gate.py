"""Fail-LOUD gate for unsupported locator INPUT attrs (mesh-plug bug follow-up).

The user hit "compiled meshRegion has no input mesh plug". The mesh plug itself
is generated correctly; the real, durable hazard is that codegen's locator path
SILENTLY drops any input it can't represent: ``_loc_scalar_inputs`` only keeps
float/int/bool/enum and ``_loc_mesh_inputs`` only keeps mesh, so a vector / euler
/ string / array / second-mesh input vanishes with NO error -- the compiled node
just lacks that plug. ``_check`` for the locator base only validated portability
and never asserted the inputs survived (its comment even claimed "user INPUT
attrs are not yet wired into the draw", which is stale).

This gate mirrors the iksolver ``_IK_INPUT_OK`` gate: it raises ``UnsupportedSpec``
for any locator input whose type the draw cannot represent, for arrays (no array
read path), and for more than one mesh (only ``meshes[0]`` drives the region
draw) -- turning a silent missing-plug into the exact actionable error.

Plus: ``port_cache.PORTER_RECIPE_VERSION`` is bumped so any stale pre-mesh-support
cached ``.cpp`` (which would still key-match and serve a plug-less node) is
invalidated on the next compile.
"""
from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _loc_spec(inputs):
    """A minimal portable MPxLocatorNode spec carrying ``inputs``."""
    return {
        "schema_version": 1, "source_node": "loc1", "mpy_type": "mPyLocator",
        "suggested": {"node_type_name": "loc1", "class_name": "Loc1",
                      "type_id": "0x00070123", "mpx_base": "MPxLocatorNode",
                      "note": "", "heaviness": "hard"},
        "inputs": inputs, "outputs": {},
        "variables": {}, "compute": "self.polygons = None\n", "init": "",
        "affects": "all", "portability": {"portable": True, "blockers": []},
    }


def _geo_spec(inputs):
    """A minimal portable mPyMesh geometry-generator spec carrying ``inputs``."""
    return {
        "schema_version": 1, "source_node": "geo1", "mpy_type": "mPyMesh",
        "suggested": {"node_type_name": "geo1", "class_name": "Geo1",
                      "type_id": "0x00070124", "mpx_base": "MPxNode",
                      "note": "", "heaviness": "hard"},
        "inputs": inputs, "outputs": {},
        "variables": {}, "compute": "self.outMesh = None\n", "init": "",
        "affects": "all", "portability": {"portable": True, "blockers": []},
    }


class TestLocatorInputGate(unittest.TestCase):

    def test_accepts_mesh_and_scalars(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({
            "wire_width": {"type": "float", "is_array": False},
            "count": {"type": "int", "is_array": False},
            "show": {"type": "bool", "is_array": False},
            "mode": {"type": "enum", "is_array": False, "enum_names": ["a", "b"]},
            "inMesh": {"type": "mesh", "is_array": False},
        })
        codegen._check(spec)  # must NOT raise

    def test_accepts_vector_input(self):
        # vector/euler ride the shared findPlug readers into the Inputs POD.
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"dir": {"type": "vector", "is_array": False}})
        codegen._check(spec)  # must NOT raise

    def test_accepts_euler_input(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"rot": {"type": "euler", "is_array": False}})
        codegen._check(spec)  # must NOT raise

    def test_accepts_every_supported_input_type(self):
        """The contract: EVERY non-excluded attr type is a legal locator INPUT,
        scalar AND array. Only python/message are excluded."""
        from mpynode.native import compiler as codegen
        for t in sorted(codegen._SUPPORTED):
            for arr in (False, True):
                md = {"type": t, "is_array": arr}
                if t == "enum":
                    md["enum_names"] = ["a", "b"]
                codegen._check(_loc_spec({"p": md}))  # must NOT raise

    def test_still_rejects_excluded_types(self):
        from mpynode.native import compiler as codegen
        for t in ("python", "message"):
            with self.assertRaises(codegen.UnsupportedSpec):
                codegen._check(_loc_spec({"p": {"type": t, "is_array": False}}))

    def test_accepts_string_input(self):
        # A scalar string INPUT on a locator is supported (animated_text): the
        # codegen emits a kString attr + asString() read into an in_<name> local.
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"label": {"type": "string", "is_array": False}})
        codegen._check(spec)  # must NOT raise

    def test_accepts_array_scalar_input(self):
        # dense std::vector<T> read off the array plug (_read_plug_array_*).
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"widths": {"type": "float", "is_array": True}})
        codegen._check(spec)  # must NOT raise

    def test_accepts_array_mesh_input(self):
        # std::vector<NdMesh> read off the array plug (geo_plug_array_input_lines).
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"inMeshes": {"type": "mesh", "is_array": True}})
        codegen._check(spec)  # must NOT raise

    def test_accepts_more_than_one_mesh(self):
        # every mesh is marshalled into the POD; meshes[0] drives the region draw.
        from mpynode.native import compiler as codegen
        spec = _loc_spec({
            "inMesh": {"type": "mesh", "is_array": False},
            "floorMesh": {"type": "mesh", "is_array": False},
        })
        codegen._check(spec)  # must NOT raise

    def test_error_message_names_the_bad_plug_and_type(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"dir": {"type": "nosuchtype", "is_array": False}})
        try:
            codegen._check(spec)
            self.fail("expected UnsupportedSpec")
        except codegen.UnsupportedSpec as exc:
            msg = str(exc)
            self.assertIn("dir", msg)
            self.assertIn("nosuchtype", msg)


def _cmd(name):
    return {"name": name, "func_name": name, "undoable": True,
            "params": [], "body_src": "", "lineno": 1}


class TestRegionCommandGate(unittest.TestCase):
    """Companion mesh-region commands must be validated by ``_check``:
    an unrecognised command, or a region command with no mesh input to connect
    into / draw, is a SILENT no-op today -- fail LOUD instead (mirrors the
    iksolver/locator input-gate convention)."""

    def test_region_command_without_mesh_input_raises(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({})  # NO mesh input
        spec["commands"] = [_cmd("setMeshRegion")]
        with self.assertRaises(codegen.UnsupportedSpec):
            codegen._check(spec)

    def test_region_command_without_mesh_message_names_command_and_mesh(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({})
        spec["commands"] = [_cmd("setMeshRegion")]
        try:
            codegen._check(spec)
            self.fail("expected UnsupportedSpec")
        except codegen.UnsupportedSpec as exc:
            msg = str(exc)
            self.assertIn("setMeshRegion", msg)
            self.assertIn("mesh", msg)

    def test_region_command_with_mesh_input_ok(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"inMesh": {"type": "mesh", "is_array": False}})
        spec["commands"] = [_cmd("createMeshRegion"), _cmd("setMeshRegion")]
        codegen._check(spec)  # must NOT raise

    def test_unsupported_command_routes_to_companion_not_raise(self):
        # A command with no deterministic native template is not a compile
        # error: it ships as a companion Python plugin, so _check passes it.
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"inMesh": {"type": "mesh", "is_array": False}})
        spec["commands"] = [_cmd("frobnicate")]
        codegen._check(spec)  # must NOT raise (frobnicate -> companion)

    def test_no_commands_key_is_unaffected(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"inMesh": {"type": "mesh", "is_array": False}})
        codegen._check(spec)  # no 'commands' key -> must NOT raise


class TestNonLocatorCommandGate(unittest.TestCase):
    """Companion @maya_command commands now ship as a sibling Python plugin
    (native/command_companion), so a command on ANY node base is supported --
    it is routed to the companion, never silently dropped and never a compile
    error. ``_check`` must therefore PASS a command-bearing non-locator spec
    (the controller writes the companion after assemble)."""

    def _nonloc_spec(self, base, commands, outputs=None):
        return {
            "schema_version": 1, "source_node": "n1", "mpy_type": "mPyNode",
            "suggested": {"node_type_name": "n1", "class_name": "N1",
                          "type_id": "0x00070130", "mpx_base": base,
                          "note": "", "heaviness": "soft"},
            "inputs": {"a": {"type": "float", "is_array": False}},
            "outputs": {"b": {"type": "float", "is_array": False}}
            if outputs is None else outputs,
            "variables": {}, "compute": "b = a\n", "init": "",
            "affects": "all", "portability": {"portable": True, "blockers": []},
            "commands": commands,
        }

    def test_nonlocator_with_command_routes_to_companion(self):
        from mpynode.native import compiler as codegen
        spec = self._nonloc_spec("MPxNode", [_cmd("anyCommand")])
        codegen._check(spec)  # must NOT raise (-> companion)

    def test_nonlocator_deformer_with_command_routes_to_companion(self):
        # A deformer drives inherited geometry and has no user outputs, but
        # its command must still route to the companion.
        from mpynode.native import compiler as codegen
        spec = self._nonloc_spec("MPxDeformerNode", [_cmd("anyCommand")],
                                 outputs={})
        codegen._check(spec)  # must NOT raise (-> companion)

    def test_nonlocator_without_commands_unaffected(self):
        from mpynode.native import compiler as codegen
        spec = self._nonloc_spec("MPxNode", [])
        codegen._check(spec)  # no commands -> must NOT raise

    def test_locator_with_commands_still_supported(self):
        # Regression anchor: the locator path STILL accepts the region commands.
        from mpynode.native import compiler as codegen
        spec = _loc_spec({"inMesh": {"type": "mesh", "is_array": False}})
        spec["commands"] = [_cmd("createMeshRegion"), _cmd("setMeshRegion")]
        codegen._check(spec)  # must NOT raise


class TestGeoGeneratorInputGate(unittest.TestCase):
    """Geometry generators (mPyMesh/mPyNurbsCurve/mPyNurbsSurface) read array
    inputs into ``std::vector<T> in_<member>`` via ``_array_read_lines`` (the same
    machinery as the generic MPxNode). Every element type in ``_ARRAY_OK`` --
    now including string/hex/color/quaternion -- is representable; only genuinely
    non-array element types (geo, python) still fail the gate LOUD. Scalar inputs
    (incl. scalar hex) always pass."""

    def test_accepts_scalar_inputs(self):
        from mpynode.native import compiler as codegen
        spec = _geo_spec({
            "resolution": {"type": "int", "is_array": False},
            "isoValue": {"type": "double", "is_array": False},
            "label": {"type": "hex", "is_array": False},   # scalar hex is fine
        })
        codegen._check(spec)  # must NOT raise

    def test_accepts_allowed_array_inputs(self):
        # The SDF DMC generator's real array inputs -- all in _ARRAY_OK.
        from mpynode.native import compiler as codegen
        spec = _geo_spec({
            "shapeMatrix": {"type": "matrix", "is_array": True},
            "shapeType": {"type": "int", "is_array": True},
            "additive": {"type": "bool", "is_array": True},
            "smoothing": {"type": "double", "is_array": True},
            "halfExtents": {"type": "vector", "is_array": True},
        })
        codegen._check(spec)  # must NOT raise

    def test_accepts_string_hex_color_quaternion_arrays(self):
        # These joined _ARRAY_OK: geo generators read them through the same
        # _array_read_lines machinery, so the gate must allow them.
        from mpynode.native import compiler as codegen
        for t in ("string", "hex", "color", "quaternion"):
            spec = _geo_spec({"vals": {"type": t, "is_array": True}})
            codegen._check(spec)  # must NOT raise

    def test_accepts_array_of_geometry(self):
        # geometry is not in _ARRAY_OK, which drives the numeric _CPP array
        # path, but a geo array has its own codegen: std::vector<Nd<Kind>>
        # via emit_geo_io.geo_array_input_lines.
        from mpynode.native import compiler as codegen
        for t in ("mesh", "nurbsCurve", "nurbsSurface"):
            spec = _geo_spec({"geos": {"type": t, "is_array": True}})
            codegen._check(spec)  # must NOT raise


class TestPorterRecipeVersionBumped(unittest.TestCase):
    """A recipe-version bump invalidates any stale pre-mesh-support cache entry
    that would otherwise serve a plug-less compiled node on a cache HIT."""

    def test_recipe_version_is_past_v1(self):
        from mpynode.native.toolchain import port_cache
        self.assertNotEqual(port_cache.PORTER_RECIPE_VERSION, "1",
                            "bump PORTER_RECIPE_VERSION so stale pre-mesh cache "
                            "entries miss and rebuild")


class TestGeoScalarOutputGate(unittest.TestCase):
    """Scalar OUTPUT attrs on a geometry GENERATOR (Mesh Maze's int
    ``solutionSteps`` was the first). Until 2026-09-14 ``emit_geo`` read the
    spec's INPUTS only and silently dropped every output: ``_check`` does not
    reject them for the geometry families, so the node compiled with the plug
    simply missing, the porter honestly wrote ND_PORT_INCOMPLETE and the authored
    test died on ``No object matches name: meshMaze1.solutionSteps``. Same shape
    as the locator input gate above: represent it fully, or fail LOUD."""

    _INT_OUT = {"solutionSteps": {"type": "int", "is_array": False,
                                  "default_value": 0}}

    def _spec(self, outputs, inputs=None):
        spec = _geo_spec(inputs or {"start": {"type": "int", "is_array": False}})
        spec["outputs"] = outputs
        return spec

    def test_scalar_output_is_declared_created_wired_and_handled(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(self._INT_OUT), for_port=True)
        for needle in (
            "static MObject aSolutionSteps;",
            "MObject Geo1::aSolutionSteps;",
            'aSolutionSteps = nAttr.create("solutionSteps", "solutionSteps", '
            "MFnNumericData::kInt, 0);",
            "addAttribute(aSolutionSteps);",
            "attributeAffects(aStart, aSolutionSteps);",
            "MDataHandle h_aSolutionSteps = data.outputValue(aSolutionSteps);",
            "h_aSolutionSteps.setInt(<int>)",       # the porter's setter hint
            "h_aSolutionSteps.setClean();",
        ):
            self.assertIn(needle, cpp, needle)

    def test_compute_gate_also_answers_the_scalar_plug(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(self._INT_OUT))
        self.assertIn("if (plug != aOutMesh && plug != aSolutionSteps) "
                      "return MS::kUnknownParameter;", cpp)

    def test_handle_is_declared_before_the_port_region_and_cleaned_after(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler.spec_model import PORT_BEGIN, PORT_END
        cpp = codegen.generate_cpp(self._spec(self._INT_OUT), for_port=True)
        i_handle = cpp.index("MDataHandle h_aSolutionSteps")
        i_begin, i_end = cpp.index(PORT_BEGIN), cpp.index(PORT_END)
        i_clean = cpp.index("h_aSolutionSteps.setClean();")
        self.assertLess(i_handle, i_begin, "handle must exist before the ported body")
        self.assertLess(i_end, i_clean, "setClean must follow the ported body")

    def test_no_outputs_emits_no_output_machinery(self):
        # The 36 generators without a scalar output must stay byte-identical;
        # this pins the no-output shape the freshness suite then measures.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec({}))
        self.assertNotIn("MDataHandle h_", cpp)
        self.assertNotIn("scalar output handles", cpp)
        self.assertIn("if (plug != aOutMesh) return MS::kUnknownParameter;", cpp)
        self.assertEqual(cpp.count("attributeAffects("), 1)   # aStart -> aOutMesh

    def test_compound_hex_and_array_outputs_are_rejected_loudly(self):
        from mpynode.native import compiler as codegen
        for plug, meta in (("tint", {"type": "color", "is_array": False}),
                           ("blob", {"type": "hex", "is_array": False}),
                           ("many", {"type": "double", "is_array": True})):
            with self.assertRaises(codegen.UnsupportedSpec) as cm:
                codegen.generate_cpp(self._spec({plug: meta}))
            self.assertIn(plug, str(cm.exception), plug)

    def test_geo_prompt_names_the_scalar_outputs(self):
        from mpynode.native.ai import prompt
        plain = prompt._geo_system("mesh")
        self.assertNotIn("scalar OUTPUT", plain)
        rich = prompt._geo_system(
            "mesh", [("solutionSteps", "h_aSolutionSteps.setInt(<int>)")])
        self.assertIn("- self.solutionSteps -> h_aSolutionSteps.setInt(<int>)", rich)
        self.assertIn("never emit ND_PORT_INCOMPLETE", rich)


class TestColorInputDefault(unittest.TestCase):
    """A colour INPUT's recorded default must reach the compiled node.

    ``nAttr.createColor`` takes no default and ``_create_lines`` never set one,
    so every compiled colour input came up black where the Python node carried
    its ``default_value``. Mesh Maze's authored test asserts on exactly those
    defaults and read (0,0,0) off the compiled node while the Python passed;
    Voxelize's defaultColor and Mesh Regions' six colours were wrong the same
    way (measured 2026-09-14). Emitted only for a non-zero default, so a node
    without one stays byte-identical -- the same silent-drop shape as the gates
    above, caught by a test that happened to assert on a default."""

    def test_non_zero_default_is_set_with_float_literals(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(_geo_spec(
            {"wallColor": {"type": "color", "is_array": False,
                           "default_value": [0.2, 0.55, 0.2]}}))
        self.assertIn('aWallColor = nAttr.createColor("wallColor", "wallColor");', cpp)
        self.assertIn("nAttr.setDefault(0.2f, 0.55f, 0.2f);", cpp)

    def test_zero_or_absent_default_emits_nothing_extra(self):
        from mpynode.native import compiler as codegen
        for meta in ({"type": "color", "is_array": False},
                     {"type": "color", "is_array": False, "default_value": [0, 0, 0]},
                     {"type": "color", "is_array": False, "default_value": "junk"}):
            cpp = codegen.generate_cpp(_geo_spec({"tint": meta}))
            self.assertNotIn("setDefault(", cpp, repr(meta))

    def test_default_follows_createColor_before_the_flags(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(_geo_spec(
            {"tint": {"type": "color", "is_array": False,
                      "default_value": [1.0, 0.9, 0.1]}}))
        i_create = cpp.index('nAttr.createColor("tint", "tint");')
        i_default = cpp.index("nAttr.setDefault(1.0f, 0.9f, 0.1f);")
        i_flag = cpp.index("nAttr.setStorable(true);", i_create)
        self.assertLess(i_create, i_default)
        self.assertLess(i_default, i_flag,
                        "setDefault must apply to the attr just created, before "
                        "the flag lines that follow it")

    def test_color_output_gets_no_default(self):
        # An output is computed every evaluation; a default is meaningless there
        # and must not be emitted even when the spec records one.
        from mpynode.native import compiler as codegen
        spec = {
            "schema_version": 1, "source_node": "n1", "mpy_type": "mPyNode",
            "suggested": {"node_type_name": "n1", "class_name": "N1",
                          "type_id": "0x00070125", "mpx_base": "MPxNode",
                          "note": "", "heaviness": "hard"},
            "inputs": {"k": {"type": "double", "is_array": False}},
            "outputs": {"tint": {"type": "color", "is_array": False,
                                 "default_value": [1.0, 0.0, 0.0]}},
            "variables": {}, "compute": "self.tint = (self.k, 0.0, 0.0)\n",
            "init": "", "affects": "all",
            "portability": {"portable": True, "blockers": []},
        }
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn('nAttr.createColor("tint", "tint");', cpp)
        self.assertNotIn("setDefault(", cpp)


class TestGeoQuaternionInclude(unittest.TestCase):
    """A quaternion input on a geometry generator is read through MQuaternion;
    the geometry include list never carried its header (the generic scaffold
    gets it from emit_attr._INCLUDES), so the node failed to compile with C2027
    'use of undefined type MQuaternion'. Compiled-surface audit, 2026-09-14."""

    def test_quaternion_input_pulls_in_the_header(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(_geo_spec(
            {"q": {"type": "quaternion", "is_array": False}}))
        self.assertIn("#include <maya/MQuaternion.h>", cpp)

    def test_generator_without_quaternion_is_unchanged(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(_geo_spec(
            {"start": {"type": "int", "is_array": False}}))
        self.assertNotIn("MQuaternion.h", cpp)


class TestDefaultValueContract(unittest.TestCase):
    """Which attr types honour a recorded ``default_value`` is a PARITY
    contract: the compiled node must do exactly what the interpreted node does
    (``wrappers._mpy_node.add_input_attr``), measured on a live node 2026-09-14:

        honoured : float double int bool enum angle(RADIANS) color(inputs)
        ignored  : vector euler float2 quaternion string time

    Honouring a default the Python side ignores would make the two nodes
    disagree on a fresh scene -- exactly what ``time`` did (compiled 2.0 vs
    Python 0.0). The 'ignored' set is a framework gap the .mpn can still record
    a value into; until add_input_attr applies them, codegen must not either.
    Update BOTH sides together if that contract ever changes."""

    HONOURED = {
        "float": (1.5, "1.5"), "double": (2.5, "2.5"), "int": (7, ", 7);"),
        "bool": (True, "true"), "enum": (1, '"p", 1);'),
        "angle": (0.5, "kAngle, 0.5);"),
        "color": ([0.2, 0.55, 0.2], "setDefault(0.2f, 0.55f, 0.2f);"),
    }
    # distinctive literals that must NOT appear anywhere in initialize()
    IGNORED = {
        "vector": ([1.25, 2.5, 3.75], ("1.25", "3.75")),
        "euler": ([0.11, 0.22, 0.33], ("0.11", "0.22", "0.33")),
        "float2": ([0.125, 0.875], ("0.125", "0.875")),
        "quaternion": ([0.11, 0.22, 0.33, 0.44], ("0.11", "0.22", "0.44")),
        "string": ("zzhelloqq", ("zzhelloqq",)),
        "time": (2.75, ("2.75",)),
    }

    def _init_block(self, t, dv):
        from mpynode.native import compiler as codegen
        meta = {"type": t, "is_array": False, "default_value": dv}
        if t == "enum":
            meta["enum_names"] = ["a", "b", "c"]
        cpp = codegen.generate_cpp(_geo_spec({"p": meta}))
        return cpp[cpp.index("::initialize() {"):cpp.index("    addAttribute(")]

    def test_honoured_types_emit_the_recorded_default(self):
        for t, (dv, lit) in self.HONOURED.items():
            self.assertIn(lit, self._init_block(t, dv), "%s must honour %r" % (t, dv))

    def test_ignored_types_emit_no_default(self):
        for t, (dv, lits) in self.IGNORED.items():
            blk = self._init_block(t, dv)
            for lit in lits:
                self.assertNotIn(lit, blk,
                                 "%s: the interpreted node ignores default_value; "
                                 "codegen must not honour it (%s found)" % (t, lit))

    def test_the_two_sets_cover_every_supported_type(self):
        from mpynode.native import compiler as codegen
        covered = set(self.HONOURED) | set(self.IGNORED)
        no_default_concept = {"matrix", "hex", "mesh", "nurbsCurve", "nurbsSurface"}
        self.assertEqual(set(codegen._SUPPORTED) - no_default_concept, covered,
                         "a supported type is missing from the default contract")


if __name__ == "__main__":
    unittest.main()
