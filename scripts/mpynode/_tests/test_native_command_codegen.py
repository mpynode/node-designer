"""Native @maya_command codegen + command-clash detector + maya_command marker

Consolidated from: test_command_codegen.py, test_command_clash.py, test_maya_command.py.
"""

from __future__ import annotations

# ===================== from test_command_codegen.py =====================
import unittest

from ._setup import standalone_init


def _setUpModule__command_codegen():
    standalone_init()


def _cmd(name, func_name=None, params=None, undoable=True):
    return {
        "name": name,
        "func_name": func_name or name,
        "undoable": undoable,
        "params": params or [],
        "body_src": "",
        "lineno": 1,
    }


_CTX = {
    "node_type_name": "meshRegion",
    "node_cls": "MeshRegionLoc",
    "mesh_plug": "inMesh",
    "region_attr": "regionFaces",
}


class TestCmdClassName(unittest.TestCase):
    def test_pascal_case_with_suffix(self):
        from mpynode.native.compiler.kernels import command_codegen as cc

        self.assertEqual(cc.cmd_class_name("createMeshRegion"),
                         "CreateMeshRegionCmd")
        self.assertEqual(cc.cmd_class_name("setMeshRegion"),
                         "SetMeshRegionCmd")

    def test_sanitizes_non_identifier_chars(self):
        from mpynode.native.compiler.kernels import command_codegen as cc

        # never emit an invalid C++ identifier
        name = cc.cmd_class_name("do-a thing!")
        self.assertTrue(name.isidentifier(), name)
        self.assertTrue(name.endswith("Cmd"))


class TestClassify(unittest.TestCase):
    def test_recognises_the_two_mesh_region_commands(self):
        from mpynode.native.compiler.kernels import command_codegen as cc

        self.assertEqual(cc.classify_command(_cmd("createMeshRegion")),
                         "create_mesh_region")
        self.assertEqual(cc.classify_command(_cmd("setMeshRegion")),
                         "set_mesh_region")

    def test_unknown_command_is_none(self):
        from mpynode.native.compiler.kernels import command_codegen as cc

        self.assertIsNone(cc.classify_command(_cmd("frobnicate")))


class TestEmitCommands(unittest.TestCase):
    def _emit(self, commands):
        from mpynode.native.compiler.kernels import command_codegen as cc

        return cc.emit_commands(commands, _CTX)

    def test_no_commands_is_inert(self):
        out = self._emit([])
        self.assertEqual(out["classes"], "")
        self.assertEqual(out["register"], [])
        self.assertEqual(out["deregister"], [])
        self.assertFalse(out["needs_region_attr"])

    def test_emits_class_for_each_recognised_command(self):
        out = self._emit([_cmd("createMeshRegion"), _cmd("setMeshRegion")])
        self.assertIn("class CreateMeshRegionCmd : public MPxCommand",
                      out["classes"])
        self.assertIn("class SetMeshRegionCmd : public MPxCommand",
                      out["classes"])
        self.assertEqual(sorted(out["supported"]),
                         ["createMeshRegion", "setMeshRegion"])
        self.assertEqual(out["unsupported"], [])

    def test_register_lines_use_newSyntax_creator(self):
        out = self._emit([_cmd("createMeshRegion")])
        joined = "\n".join(out["register"])
        self.assertIn('registerCommand("createMeshRegion", '
                      'CreateMeshRegionCmd::creator, '
                      'CreateMeshRegionCmd::newSyntax)', joined)

    def test_deregister_lines_match_command_names(self):
        out = self._emit([_cmd("createMeshRegion"), _cmd("setMeshRegion")])
        joined = "\n".join(out["deregister"])
        self.assertIn('deregisterCommand("createMeshRegion")', joined)
        self.assertIn('deregisterCommand("setMeshRegion")', joined)

    def test_register_does_not_match_main_node_regex(self):
        # The bundler detects the main class via register(Node|Transform)(
        # "name", X::id ...). Command registration must NOT collide with it.
        import re

        out = self._emit([_cmd("createMeshRegion")])
        node_re = re.compile(
            r'register(?:Node|Transform)\s*\(\s*"[^"]+"\s*,\s*(\w+)::id')
        for line in out["register"] + out["deregister"]:
            self.assertIsNone(node_re.search(line), line)

    def test_unknown_command_reported_not_emitted(self):
        out = self._emit([_cmd("frobnicate"), _cmd("setMeshRegion")])
        self.assertEqual(out["unsupported"], ["frobnicate"])
        self.assertEqual(out["supported"], ["setMeshRegion"])
        self.assertNotIn("Frobnicate", out["classes"])
        self.assertIn("SetMeshRegionCmd", out["classes"])

    def test_set_region_uses_indices_multiuse_syntax(self):
        out = self._emit([_cmd("setMeshRegion")])
        cls = out["classes"]
        self.assertIn("static MSyntax newSyntax()", cls)
        self.assertIn('addFlag("-i", "-indices"', cls)
        self.assertIn('makeFlagMultiUse("-i")', cls)

    def test_set_region_is_undoable_and_writes_region_attr(self):
        out = self._emit([_cmd("setMeshRegion")])
        cls = out["classes"]
        self.assertIn("isUndoable() const override { return true; }", cls)
        self.assertIn("regionFaces", cls)
        self.assertIn("MStatus undoIt() override", cls)

    def test_create_region_creates_node_and_connects_mesh(self):
        out = self._emit([_cmd("createMeshRegion")])
        cls = out["classes"]
        self.assertIn('createNode("meshRegion"', cls)
        self.assertIn("inMesh", cls)
        self.assertIn("worldMesh", cls)
        # optional -indices at create time (shares setMeshRegion's flag)
        self.assertIn('makeFlagMultiUse("-i")', cls)

    def test_create_region_builds_node_in_doIt_not_redoIt(self):
        # MDagModifier/MDGModifier ACCUMULATE ops, so a createNode/connect
        # issued in redoIt() duplicates the node on undo-then-redo. Author
        # once in doIt(); redoIt() only replays _dagMod.doIt()/_dgMod.doIt().
        out = self._emit([_cmd("createMeshRegion")])
        cls = out["classes"]
        i_do = cls.index("MStatus doIt(")
        i_redo = cls.index("MStatus redoIt()")
        i_undo = cls.index("MStatus undoIt()")
        do_body = cls[i_do:i_redo]
        redo_body = cls[i_redo:i_undo]
        self.assertIn("createNode(", do_body)       # node authored in doIt
        self.assertNotIn("createNode(", redo_body)  # NOT re-issued on redo
        self.assertNotIn(".connect(", redo_body)    # connect not re-issued
        self.assertIn("_dagMod.doIt()", redo_body)

    def test_needs_region_attr_when_mesh_region_command_present(self):
        out = self._emit([_cmd("setMeshRegion")])
        self.assertTrue(out["needs_region_attr"])
        out2 = self._emit([_cmd("frobnicate")])
        self.assertFalse(out2["needs_region_attr"])

    def test_includes_command_headers(self):
        out = self._emit([_cmd("createMeshRegion")])
        incs = " ".join(out["includes"])
        self.assertIn("MPxCommand.h", incs)
        self.assertIn("MArgDatabase.h", incs)
        self.assertIn("MSyntax.h", incs)

    def test_includes_are_self_contained(self):
        # Templates use MFn::k* enums, std::vector and size_t, so the include
        # set must stand alone: a command node with no mesh input never pulls
        # in the locator's STL/mesh headers.
        out = self._emit([_cmd("createMeshRegion")])
        incs = out["includes"]
        self.assertIn("maya/MFn.h", incs)
        # bare STL headers: the templates use std::vector<int> and size_t.
        self.assertIn("vector", incs)
        self.assertIn("cstddef", incs)

    def test_create_region_connects_selected_instance(self):
        # a shape selected on instance N must connect worldMesh[N], not
        # worldMesh[0]: MDagPath.instanceNumber() feeds
        # elementByLogicalIndex.
        out = self._emit([_cmd("createMeshRegion")])
        cls = out["classes"]
        self.assertIn("instanceNumber()", cls)
        self.assertIn("elementByLogicalIndex(_meshInst)", cls)
        self.assertNotIn("elementByLogicalIndex(0)", cls)

    def test_resolve_iterates_all_child_shapes(self):
        # search every child shape for one of OUR type, not just the first
        # (extendToShape).
        out = self._emit([_cmd("setMeshRegion")])
        cls = out["classes"]
        i0 = cls.index("static MObject _resolveOurNode")
        i1 = cls.index("class ", i0)  # the first command class after the helpers
        body = cls[i0:i1]
        self.assertIn("childCount()", body)
        self.assertIn(".child(", body)


def _loc_spec_with_commands(commands):
    """A minimal portable MPxLocatorNode spec carrying a mesh input + the given
    statically-detected ``commands`` list."""
    return {
        "schema_version": 1, "source_node": "meshRegion1",
        "mpy_type": "mPyLocator",
        "suggested": {"node_type_name": "meshRegion", "class_name": "MeshRegion",
                      "type_id": "0x00070abc", "mpx_base": "MPxLocatorNode",
                      "note": "", "heaviness": "hard"},
        "inputs": {"inMesh": {"type": "mesh", "is_array": False}},
        "outputs": {},
        "variables": {}, "compute": "self.polygons = None\n", "init": "",
        "affects": "all", "portability": {"portable": True, "blockers": []},
        "commands": commands,
    }


class TestLocatorCommandWiring(unittest.TestCase):
    """``_generate_locator_cpp`` must weave companion commands into the node:
    classes in the scaffold head, register/deregister in the plugin hooks, and
    (for mesh-region commands) a settable ``regionFaces`` int-array attr."""

    def _gen(self, commands):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(_loc_spec_with_commands(commands))

    def test_command_classes_emitted_in_scaffold(self):
        cpp = self._gen([_cmd("createMeshRegion"), _cmd("setMeshRegion")])
        self.assertIn("class CreateMeshRegionCmd : public MPxCommand", cpp)
        self.assertIn("class SetMeshRegionCmd : public MPxCommand", cpp)
        # inside the plugin scaffold guard (not in the probe / common region)
        scaffold = cpp.index("#ifndef MPYNODE_PROBE  // ===== plugin scaffold")
        endif = cpp.index("#endif  // !MPYNODE_PROBE")
        pos = cpp.index("class CreateMeshRegionCmd")
        self.assertTrue(scaffold < pos < endif)

    def test_register_and_deregister_in_plugin_hooks(self):
        cpp = self._gen([_cmd("createMeshRegion"), _cmd("setMeshRegion")])
        self.assertIn('registerCommand("createMeshRegion"', cpp)
        self.assertIn('registerCommand("setMeshRegion"', cpp)
        self.assertIn('deregisterCommand("createMeshRegion")', cpp)
        self.assertIn('deregisterCommand("setMeshRegion")', cpp)
        # registration lives inside initializePlugin (before its closing brace)
        init = cpp.index("MStatus initializePlugin(MObject obj)")
        uninit = cpp.index("MStatus uninitializePlugin(MObject obj)")
        self.assertLess(init, cpp.index('registerCommand("createMeshRegion"'))
        self.assertLess(cpp.index('registerCommand("createMeshRegion"'), uninit)
        self.assertLess(uninit,
                        cpp.index('deregisterCommand("createMeshRegion")'))

    def test_region_attr_declared_when_mesh_region_command_present(self):
        cpp = self._gen([_cmd("setMeshRegion")])
        self.assertIn("regionFaces", cpp)
        self.assertIn("MFnData::kIntArray", cpp)

    def test_region_attr_affects_appearance(self):
        # setMeshRegion writes regionFaces; the attr must mark the draw dirty
        # so VP2 refreshes, complementing isAlwaysDirty.
        cpp = self._gen([_cmd("setMeshRegion")])
        self.assertIn("setAffectsAppearance(true)", cpp)

    def test_probe_reads_faceids(self):
        # the probe must accept a face region, else the probe-vs-Python parity
        # check never exercises the region draw.
        cpp = self._gen([_cmd("setMeshRegion")])
        self.assertIn('else if (k == "FACEIDS")', cpp)

    def test_command_headers_added(self):
        cpp = self._gen([_cmd("createMeshRegion")])
        self.assertIn("maya/MPxCommand.h", cpp)
        self.assertIn("maya/MArgDatabase.h", cpp)

    def test_no_commands_leaves_locator_clean(self):
        # a locator spec with no commands must gain no command machinery:
        # protects existing locators from a byte change.
        cpp = self._gen([])
        self.assertNotIn("MPxCommand", cpp)
        self.assertNotIn("registerCommand", cpp)
        self.assertNotIn("regionFaces", cpp)

    def test_missing_commands_key_is_safe(self):
        from mpynode.native import compiler as codegen
        spec = _loc_spec_with_commands([])
        del spec["commands"]  # nodes built before the Methods feature
        cpp = codegen._generate_locator_cpp(spec)
        self.assertNotIn("registerCommand", cpp)


class TestDeterministicRegionDraw(unittest.TestCase):
    """A node carrying the mesh-region commands is, by definition, a region
    drawer -- the direct (no-AI, for_port=False) compile path must emit a
    DETERMINISTIC region-draw computeBuffers (extract_region of the settable
    faceIds) so meshRegion is a reproducible NO-LLM compile target, not a PORT
    stub. The AI port path (for_port=True) is unchanged."""

    def _gen(self, for_port):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(
            _loc_spec_with_commands([_cmd("setMeshRegion")]),
            for_port=for_port)

    def test_direct_compile_emits_deterministic_region_draw(self):
        cpp = self._gen(for_port=False)
        self.assertIn("extract_region(inMesh, faceIds, true)", cpp)
        self.assertIn("DrawPoly& _pg = data.emitPoly();", cpp)
        self.assertNotIn("TODO: translate the Python draw expression", cpp)

    def test_ai_port_path_unchanged_for_region_node(self):
        # for_port=True keeps the porter stub; no determinism is forced onto
        # the AI flow.
        cpp = self._gen(for_port=True)
        self.assertNotIn("RegionBuffer _rb = extract_region(inMesh, faceIds",
                         cpp)


_TWEEN_COMPUTE = '''\
hovered = bool(self.hovered)
now = float(_wallclock.time())
h_cur, h_e = tween(now, float(getattr(self, "hv_start", 0.0)),
                   float(getattr(self, "hv_from", 0.0)),
                   float(getattr(self, "hv_to", 0.0)), 0.35)
if hovered != bool(getattr(self, "hv_prev", False)):
    self.hv_start = now
    self.hv_from = h_cur
    self.hv_to = 1.0 if hovered else 0.0
    self.hv_prev = hovered
    h_e = 0.0
self.draw = None
'''


def _loc_spec_with_tween(compute=None):
    """Shaped like the shipped meshRegions: a hover-driven locator whose tween
    state is implicit (never declared in spec["variables"])."""
    spec = _loc_spec_with_commands([])
    spec["inputs"] = {"offset": {"type": "float", "is_array": False}}
    spec["compute"] = _TWEEN_COMPUTE if compute is None else compute
    spec["needs_hover"] = True
    return spec


class TestImplicitStoredVarsAreDiscovered(unittest.TestCase):
    """Cross-frame tween state written as `self.X = ...` and read back as
    `getattr(self, "X", <literal>)` is never DECLARED, so it never reached
    spec["variables"] -- the emitted tween struct came out empty
    (`char _unused;`) and the porter, told writes were local no-ops, folded
    every read to its seed. h_cur was then identically 0, which makes
    hoverOffset / hoverColor / hoverDur mathematically unreachable.

    Only the PAIRED form is promoted: the getattr default is the sole source of
    both the C++ type and the seed."""

    def _vars(self, src):
        from mpynode.native.compiler import emit_locator
        return emit_locator._loc_implicit_stored_vars(src)

    def test_the_hover_tween_state_is_found(self):
        got = self._vars(_TWEEN_COMPUTE)
        self.assertEqual(sorted(got), ["hv_from", "hv_prev", "hv_start",
                                       "hv_to"])

    def test_seed_and_kind_come_from_the_getattr_default(self):
        got = self._vars(_TWEEN_COMPUTE)
        self.assertEqual(got["hv_start"], {"kind": "float", "value": 0.0})
        self.assertEqual(got["hv_prev"], {"kind": "bool", "value": False})

    def test_bool_is_not_mistaken_for_int(self):
        # isinstance(True, int) is True in Python -- order matters
        self.assertEqual(
            self._vars('x = getattr(self, "f", False)\nself.f = True\n')
            ["f"]["kind"], "bool")

    def test_int_default_stays_int(self):
        self.assertEqual(
            self._vars('x = getattr(self, "n", 3)\nself.n = 4\n')
            ["n"]["kind"], "int")

    def test_a_write_with_no_getattr_read_is_not_promoted(self):
        # no default -> no type and no seed; promoting it would invent both
        self.assertEqual(self._vars("self.scratch = 1.0\n"), {})

    def test_a_getattr_read_with_no_write_is_not_promoted(self):
        # never mutated -> not cross-frame state, just a constant
        self.assertEqual(self._vars('x = getattr(self, "k", 1.0)\n'), {})

    def test_framework_slots_are_never_promoted(self):
        # self.auto_refresh already routes to data.autoRefresh -- a stored-var
        # twin would fight it. Three of the four shipped locators WRITE it.
        self.assertEqual(
            self._vars('x = getattr(self, "auto_refresh", False)\n'
                       'self.auto_refresh = True\n'), {})

    def test_a_non_literal_default_is_skipped(self):
        self.assertEqual(
            self._vars('x = getattr(self, "d", {})\nself.d = {}\n'), {})

    def test_unparseable_compute_is_survived(self):
        self.assertEqual(self._vars("this is not python ((("), {})

    def test_discovery_order_is_deterministic(self):
        # struct field order is .cpp bytes; it must not depend on set ordering
        a = self._vars(_TWEEN_COMPUTE)
        b = self._vars(_TWEEN_COMPUTE)
        self.assertEqual(list(a), list(b))
        self.assertEqual(list(a), sorted(a))


class TestStoredVarRoundTripIsEmitted(unittest.TestCase):
    """With the vars discovered, the machinery that was already in the emitter
    (Inputs.sv_*, the g_tween seed, the write-back after PORT_END) must fire."""

    def _gen(self):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(_loc_spec_with_tween(),
                                             for_port=True)

    def test_the_tween_struct_is_no_longer_empty(self):
        cpp = self._gen()
        self.assertNotIn("char _unused;  // no stored vars", cpp)
        self.assertIn("double hv_start = 0.0;", cpp)
        self.assertIn("bool hv_prev = false;", cpp)

    def test_inputs_carry_the_stored_var_conduits(self):
        cpp = self._gen()
        for n in ("hv_start", "hv_from", "hv_to", "hv_prev"):
            self.assertIn("sv_%s" % n, cpp)

    def test_the_seed_and_the_commit_both_emit(self):
        cpp = self._gen()
        self.assertIn("inp.sv_hv_start = _tw.hv_start;", cpp)
        self.assertIn("_tw.hv_start = data->sv_hv_start;", cpp)
        self.assertIn("data.sv_hv_start = hv_start;", cpp)

    def test_the_locals_are_seeded_from_the_conduit_not_a_constant(self):
        # the whole defect was reads collapsing to a hard-coded 0.0
        self.assertIn("double hv_start = inp.sv_hv_start;", self._gen())

    def test_a_hover_locator_with_no_state_is_unchanged(self):
        # control: hover alone must not start inventing stored vars
        from mpynode.native import compiler as codegen
        cpp = codegen._generate_locator_cpp(
            _loc_spec_with_tween("self.draw = None\n"), for_port=True)
        self.assertIn("char _unused;  // no stored vars", cpp)
        self.assertNotIn("sv_hv_start", cpp)


class TestPorterIsToldWritesPersist(unittest.TestCase):
    """Third teller. The guide used to say stored-var writes were LOCAL ONLY
    'cross-frame persistence is intentionally not modeled' -- which is what
    produced the folded constants. The emitter DOES persist them, so the guide
    has to agree or the next port re-folds them."""

    def test_the_guide_no_longer_calls_the_writes_no_ops(self):
        import inspect
        from mpynode.native.ai import prompt
        src = inspect.getsource(prompt)
        self.assertNotIn("the writes harmlessly no-op", src)
        self.assertNotIn("cross-frame persistence is intentionally not modeled",
                         src)

    def test_the_guide_says_the_writes_persist(self):
        import inspect
        from mpynode.native.ai import prompt
        src = inspect.getsource(prompt)
        self.assertIn("PERSIST across frames", src)


def _loc_spec_every_input():
    """A locator spec carrying one input of every kind the emitter handles."""
    spec = _loc_spec_with_commands([])
    spec["inputs"] = {
        "inMesh": {"type": "mesh", "is_array": False},
        "offset": {"type": "float", "is_array": False},
        "steps": {"type": "int", "is_array": False},
        "enabled": {"type": "bool", "is_array": False},
        "mode": {"type": "enum", "is_array": False,
                 "enum_names": ["a", "b"]},
        "regionTag": {"type": "string", "is_array": False},
        "tint": {"type": "color", "is_array": False},
    }
    return spec


class TestEveryInputMarksTheDrawDirty(unittest.TestCase):
    """A locator has NO DG output, so Maya only re-runs prepareForDraw when the
    render item is marked dirty. A runtime-added input attr is not something
    Maya recognises as draw-affecting, so without setAffectsAppearance changing
    it leaves the gizmo frozen until an unrelated refresh -- which is exactly
    what the interpreted node's setDependentsDirty override exists to prevent
    (_api2/mpy_locator.py). The string and colour branches already did this;
    the numeric, enum and mesh branches did not, so `offset` looked inert while
    `selectOffset` appeared to work (selecting forces a repaint by itself)."""

    def _gen(self):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(_loc_spec_every_input())

    def _create_block(self, cpp, attr):
        """The emitted lines from this attr's create() up to its addAttribute."""
        start = cpp.index('"%s", "%s"' % (attr, attr))
        end = cpp.index("addAttribute(", start)
        return cpp[start:end]

    def test_float_input_affects_appearance(self):
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(self._gen(), "offset"))

    def test_int_input_affects_appearance(self):
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(self._gen(), "steps"))

    def test_bool_input_affects_appearance(self):
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(self._gen(), "enabled"))

    def test_enum_input_affects_appearance(self):
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(self._gen(), "mode"))

    def test_mesh_input_affects_appearance(self):
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(self._gen(), "inMesh"))

    def test_string_and_color_inputs_still_affect_appearance(self):
        # these two already worked -- guard against the fix regressing them
        cpp = self._gen()
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(cpp, "regionTag"))
        self.assertIn("setAffectsAppearance(true)",
                      self._create_block(cpp, "tint"))

    def test_every_declared_input_is_covered(self):
        # the point is the CLASS of bug, not the five attrs above: no input may
        # be left without a draw-dirty signal.
        cpp = self._gen()
        for attr in ("inMesh", "offset", "steps", "enabled", "mode",
                     "regionTag", "tint"):
            self.assertIn("setAffectsAppearance(true)",
                          self._create_block(cpp, attr),
                          "%s does not mark the draw dirty" % attr)


class TestComponentTagsReachTheDraw(unittest.TestCase):
    """Component tags must travel INTO the compute with the mesh input.

    They live on the mesh DATA (MFnGeometryData), not on MFnMesh, so a compute
    that only sees a RegionMesh cannot resolve a named region -- the porter then
    reports it unportable and falls back to an empty face list, which draws
    NOTHING. The reader prologue holds the data MObject, so it reads the tag
    table there and the compute does a pure lookup."""

    def _gen(self, for_port=True):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(
            _loc_spec_with_commands([_cmd("setMeshRegion")]),
            for_port=for_port)

    def test_region_mesh_carries_a_tag_table(self):
        cpp = self._gen()
        self.assertIn("std::vector<std::string>       tagNames;", cpp)
        self.assertIn("std::vector<std::vector<int> > tagIds;", cpp)

    def test_tag_indices_lookup_helper_exists(self):
        cpp = self._gen()
        self.assertIn("static std::vector<int> tag_indices(const RegionMesh& mesh,",
                      cpp)
        # both a std::string and an MString key, since the tag name may arrive
        # from either a C++ literal or a string plug read.
        self.assertIn("const std::string& name)", cpp)
        self.assertIn("const MString& name)", cpp)

    def test_reader_populates_the_tag_table_from_the_mesh_data(self):
        cpp = self._gen()
        self.assertIn("MFnGeometryData _gd(_mo, &_gs);", cpp)
        self.assertIn("_gd.componentTags(_tn);", cpp)
        self.assertIn("_gd.componentTagContents(_tn[_t], &_cs);", cpp)
        self.assertIn("MFnSingleIndexedComponent _sic(_comp, &_cs);", cpp)
        self.assertIn("inp.inMesh.tagNames.push_back(", cpp)
        self.assertIn("inp.inMesh.tagIds.push_back(_tv);", cpp)

    def test_tags_are_read_before_the_input_is_marked_present(self):
        # present=true is the connected flag the compute branches on; the table
        # must already be filled by then or a first-frame draw sees no tags.
        cpp = self._gen()
        self.assertLess(cpp.index("inp.inMesh.tagIds.push_back(_tv);"),
                        cpp.index("inp.inMesh.present = true;"))

    def test_component_tag_headers_are_included(self):
        cpp = self._gen()
        self.assertIn("maya/MFnGeometryData.h", cpp)
        self.assertIn("maya/MFnSingleIndexedComponent.h", cpp)
        self.assertIn("maya/MStringArray.h", cpp)

    def test_scaffold_tells_the_porter_the_lookup_is_portable(self):
        cpp = self._gen(for_port=True)
        self.assertIn("tag_indices(inMesh, name)", cpp)
        self.assertIn("do NOT report those as unportable scene queries", cpp)

    def test_porter_guide_tells_the_same_story(self):
        # third teller: the emitted scaffold, the in-scope comment and the
        # porter guide must agree, or the porter emits ND_PORT_INCOMPLETE for a
        # lookup that is right there in front of it.
        from mpynode.native.ai import prompt

        src = prompt.__doc__ or ""
        import inspect
        src = inspect.getsource(prompt)
        self.assertIn("tag_indices(M, tagName)", src)
        self.assertIn("tag_indices_from_mesh_data", src)
        self.assertIn("never emit ND_PORT_INCOMPLETE for it", src)


class TestBundlerCarriesCommands(unittest.TestCase):
    """When a meshRegion node is merged into a (multi-node) plugin, the bundler
    must namespace-wrap the command classes (so two nodes don't collide) AND
    carry registerCommand/deregisterCommand into the per-node register hook
    (which gets a ``using namespace nd_<node>;`` so the class resolves)."""

    def _frag(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import bundler
        cpp = codegen._generate_locator_cpp(_loc_spec_with_commands(
            [_cmd("createMeshRegion"), _cmd("setMeshRegion")]))
        return bundler.transform_node_cpp(cpp, "meshRegion",
                                          lambda k: "0x00070abc")

    def test_command_class_wrapped_in_node_namespace(self):
        frag, info = self._frag()
        ns = info["ns"]
        i_ns = frag.index("namespace %s {" % ns)
        i_end = frag.index("}  // namespace %s" % ns)
        self.assertTrue(i_ns < frag.index("class CreateMeshRegionCmd") < i_end)
        self.assertTrue(i_ns < frag.index("_writeRegionFaces") < i_end)

    def test_register_carried_into_hook_with_using_namespace(self):
        frag, info = self._frag()
        ns = info["ns"]
        i_end = frag.index("}  // namespace %s" % ns)
        i_hook = frag.index("register_%s" % info["class"])
        i_reg = frag.index('registerCommand("createMeshRegion"')
        self.assertGreater(i_reg, i_end)     # outside the class namespace
        self.assertGreater(i_reg, i_hook)    # inside the register hook
        self.assertIn("using namespace %s;" % ns, frag[i_hook:])

    def test_deregister_carried(self):
        frag, _ = self._frag()
        self.assertIn('deregisterCommand("createMeshRegion")', frag)
        self.assertIn('deregisterCommand("setMeshRegion")', frag)


# ===================== from test_command_clash.py =====================
import unittest

from ._setup import standalone_init


def _setUpModule__command_clash():
    standalone_init()


class TestCommandNamesIn(unittest.TestCase):
    def test_finds_register_command_names(self):
        from mpynode.native.compiler import bundler

        src = (
            'MStatus initializePlugin(MObject obj){\n'
            '    MFnPlugin plugin(obj);\n'
            '    plugin.registerCommand("createMeshRegion", C::creator, C::newSyntax);\n'
            '    plugin.registerCommand( "setMeshRegion" , D::creator);\n'
            '    return plugin.registerNode("foo", Foo::id, Foo::creator, Foo::initialize);\n'
            '}\n')
        self.assertEqual(sorted(bundler.command_names_in(src)),
                         ["createMeshRegion", "setMeshRegion"])

    def test_no_commands_returns_empty(self):
        from mpynode.native.compiler import bundler

        self.assertEqual(bundler.command_names_in("int main(){}"), [])


class TestFindCommandClashes(unittest.TestCase):
    def test_clash_across_two_nodes(self):
        from mpynode.native.compiler import bundler

        a = 'plugin.registerCommand("doThing", A::creator);'
        b = 'plugin.registerCommand("doThing", B::creator);'
        clashes = bundler.find_command_clashes([("nodeA", a), ("nodeB", b)])
        self.assertIn("doThing", clashes)
        self.assertEqual(sorted(clashes["doThing"]), ["nodeA", "nodeB"])

    def test_no_clash_when_unique(self):
        from mpynode.native.compiler import bundler

        a = 'plugin.registerCommand("alpha", A::creator);'
        b = 'plugin.registerCommand("beta", B::creator);'
        self.assertEqual(bundler.find_command_clashes(
            [("nodeA", a), ("nodeB", b)]), {})

    def test_duplicate_within_one_node_is_a_clash(self):
        from mpynode.native.compiler import bundler

        a = ('plugin.registerCommand("dup", A::creator);'
             'plugin.registerCommand("dup", A::creator);')
        clashes = bundler.find_command_clashes([("nodeA", a)])
        self.assertIn("dup", clashes)

    def test_deregister_line_is_not_counted_as_a_register(self):
        # Every emitted command has BOTH lines, so if the register regex
        # substring-matches deregisterCommand a single node self-clashes.
        from mpynode.native.compiler import bundler

        self.assertEqual(
            bundler.command_names_in('plugin.deregisterCommand("foo");'), [])

    def test_real_emit_output_single_node_no_self_clash(self):
        # real command_codegen output, one node with two distinct commands:
        # must NOT report a clash.
        from mpynode.native.compiler import bundler
        from mpynode.native.compiler.kernels import command_codegen

        ctx = {"node_type_name": "meshRegion", "node_cls": "MeshRegionLoc",
               "mesh_plug": "inMesh", "region_attr": "regionFaces"}
        out = command_codegen.emit_commands(
            [{"name": "createMeshRegion", "func_name": "c", "undoable": True,
              "params": [], "body_src": "", "lineno": 1},
             {"name": "setMeshRegion", "func_name": "s", "undoable": True,
              "params": [], "body_src": "", "lineno": 2}], ctx)
        node_cpp = (out["classes"] + "\n"
                    + "\n".join(out["register"]) + "\n"
                    + "\n".join(out["deregister"]))
        self.assertEqual(
            bundler.find_command_clashes([("meshRegion", node_cpp)]), {})
        self.assertEqual(sorted(bundler.command_names_in(node_cpp)),
                         ["createMeshRegion", "setMeshRegion"])

    # F8 hardening regression tests.
    def test_deregister_does_not_double_count_at_clash_level(self):
        # register + deregister of the SAME name in one node is not a clash.
        from mpynode.native.compiler import bundler

        src = ('plugin.registerCommand("solo", A::creator);\n'
               'plugin.deregisterCommand("solo");\n')
        self.assertEqual(bundler.find_command_clashes([("nodeA", src)]), {})

    def test_token_boundary_alnum_before_is_not_a_match(self):
        # `xregisterCommand("x")` (alnum before) must NOT match; but
        # `plugin.registerCommand("x")` (preceded by '.') MUST match.
        from mpynode.native.compiler import bundler

        self.assertEqual(
            bundler.command_names_in('xregisterCommand("ghost");'), [])
        self.assertEqual(
            bundler.command_names_in('plugin.registerCommand("real");'),
            ["real"])


class TestCommentAndStringStripping(unittest.TestCase):
    """F7: registerCommand calls inside // /* */ comments or "..."/'...' literals
    must not be counted (they are false positives that would reject real builds
    in strict mode)."""

    def test_line_comment_hides_register(self):
        from mpynode.native.compiler import bundler

        src = ('// plugin.registerCommand("ghost");\n'
               'plugin.registerCommand("real", A::creator);\n')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_block_comment_hides_register(self):
        from mpynode.native.compiler import bundler

        src = ('/* registerCommand("ghost") */ '
               'plugin.registerCommand("real");\n')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_multi_line_block_comment_hides_register(self):
        from mpynode.native.compiler import bundler

        src = (
            '/*\n'
            ' * plugin.registerCommand("ghost1");\n'
            ' * plugin.registerCommand("ghost2");\n'
            ' */\n'
            'plugin.registerCommand("real", A::creator);\n')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_string_literal_that_closes_mid_pattern(self):
        # the string literal closes BEFORE the real registerCommand call, so
        # a naive regex also matches the `registerCommand(` inside the string.
        from mpynode.native.compiler import bundler

        src = ('const char* s = "x registerCommand("; '
               'plugin.registerCommand("real", R::creator);\n')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_escaped_quote_in_string_does_not_desync_scanner(self):
        from mpynode.native.compiler import bundler

        src = ('const char* s = "he said \\"registerCommand(\\\"ghost\\\")\\" "; '
               'plugin.registerCommand("real", R::creator);\n')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_unterminated_block_comment_does_not_raise(self):
        from mpynode.native.compiler import bundler

        src = ('plugin.registerCommand("real", R::creator);\n'
               '/* unterminated registerCommand("ghost") ...')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_unterminated_string_does_not_raise(self):
        from mpynode.native.compiler import bundler

        src = ('plugin.registerCommand("real", R::creator);\n'
               'const char* s = "unterminated registerCommand(')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_line_comment_before_deregister_only(self):
        # a deregister-only line preceded by a comment returns no names.
        from mpynode.native.compiler import bundler

        src = ('// plugin.registerCommand("ghost");\n'
               'plugin.deregisterCommand("solo");\n')
        self.assertEqual(bundler.command_names_in(src), [])


class TestRawStringLiterals(unittest.TestCase):
    """C++11 raw strings ``R"delim( ... )delim"`` (commonly emitted by an AI
    command body for embedded shader/JSON/regex text) contain unescaped ``"``
    that desync a naive ``"..."`` scanner: it would mis-close the literal and
    either LEAK a ghost ``registerCommand`` from the body (false clash ->
    spurious strict-assemble rejection) or SWALLOW a following real call
    (missed clash -> silent runtime duplicate). The scanner must treat a raw
    string as one opaque token."""

    def test_raw_string_body_does_not_leak_ghost(self):
        # The exact desync probe: an unescaped " inside the raw body.
        from mpynode.native.compiler import bundler

        src = ('auto s = R"(a "b registerCommand("ghost2") c)"; '
               'plugin.registerCommand("real");')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_raw_string_with_custom_delimiter(self):
        # A )" sequence inside the body is NOT the closer; )xy" is.
        from mpynode.native.compiler import bundler

        src = ('auto s = R"xy(a )" b registerCommand("ghost") )xy"; '
               'plugin.registerCommand("real");')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_prefixed_raw_string(self):
        # Encoding-prefixed raw strings (LR"/u8R"/uR"/UR") are also opaque.
        from mpynode.native.compiler import bundler

        for pre in ("L", "u8", "u", "U"):
            src = ('auto s = %sR"(registerCommand("ghost"))"; '
                   'plugin.registerCommand("real");' % pre)
            self.assertEqual(bundler.command_names_in(src), ["real"],
                             "prefix %r raw string leaked" % pre)

    def test_unterminated_raw_string_does_not_raise(self):
        from mpynode.native.compiler import bundler

        src = ('plugin.registerCommand("real");\n'
               'auto s = R"(unterminated registerCommand("ghost") ...')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_identifier_ending_in_R_is_not_a_raw_string(self):
        # ``fooR"..."`` -> ``fooR`` identifier + a NORMAL string, so the
        # embedded \"-escaped quotes apply and the real call is still found.
        from mpynode.native.compiler import bundler

        src = ('int fooR = 0; const char* s = fooR"reg"; '
               'plugin.registerCommand("real");')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_u8_nonraw_string_still_handled_as_normal_string(self):
        # u8"..." (no R) is a NORMAL string -> escapes apply, ghost hidden.
        from mpynode.native.compiler import bundler

        src = ('const char* s = u8"x registerCommand(\\"ghost\\")"; '
               'plugin.registerCommand("real");')
        self.assertEqual(bundler.command_names_in(src), ["real"])

    def test_real_call_inside_raw_string_is_only_a_literal(self):
        # A registerCommand call that lives ENTIRELY inside a raw string is a
        # literal, not a real registration -> not counted.
        from mpynode.native.compiler import bundler

        src = 'const char* k = R"(plugin.registerCommand("ghost", X::c);)";'
        self.assertEqual(bundler.command_names_in(src), [])


# ===================== from test_maya_command.py =====================
import unittest


class TestMayaCommandDecorator(unittest.TestCase):
    def test_bare_decorator_marks_function(self):
        from mpynode._common.methods.maya_command import maya_command

        @maya_command
        def foo(self, x):
            return x + 1

        self.assertEqual(foo.__maya_command__["name"], "foo")
        self.assertTrue(foo.__maya_command__["undoable"])
        # Still a normal callable (no-op at runtime).
        self.assertEqual(foo(None, 41), 42)

    def test_parameterized_decorator_overrides_name_and_undoable(self):
        from mpynode._common.methods.maya_command import maya_command

        @maya_command(name="createMeshRegion", undoable=False)
        def builder(self):
            return "ok"

        self.assertEqual(builder.__maya_command__["name"], "createMeshRegion")
        self.assertFalse(builder.__maya_command__["undoable"])
        self.assertEqual(builder(None), "ok")

    def test_empty_parens_defaults(self):
        from mpynode._common.methods.maya_command import maya_command

        @maya_command()
        def bar(self):
            return 1

        self.assertEqual(bar.__maya_command__["name"], "bar")
        self.assertTrue(bar.__maya_command__["undoable"])


class TestDetectCommands(unittest.TestCase):
    def test_detects_only_flagged_top_level_defs(self):
        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "def helper(self, n):\n"
            "    return n * 2\n"
            "\n"
            "@maya_command\n"
            "def setRegion(self, indices):\n"
            "    self.region = indices\n"
            "\n"
            "@maya_command(name='createMeshRegion', undoable=False)\n"
            "def make(self, indices=None):\n"
            "    return indices\n"
        )
        cmds = detect_commands(src)
        names = sorted(c["name"] for c in cmds)
        self.assertEqual(names, ["createMeshRegion", "setRegion"])

    def test_command_fields(self):
        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "@maya_command(name='setMeshRegion', undoable=True)\n"
            "def set_region_ids(self, indices=None):\n"
            "    self.region_ids = indices\n"
        )
        (c,) = detect_commands(src)
        self.assertEqual(c["name"], "setMeshRegion")
        self.assertEqual(c["func_name"], "set_region_ids")
        self.assertTrue(c["undoable"])
        self.assertEqual(c["params"], ["indices"])  # 'self' excluded
        self.assertIn("def set_region_ids", c["body_src"])
        self.assertIn("@maya_command", c["body_src"])  # decorator preserved

    def test_non_maya_decorator_is_not_a_command(self):
        from mpynode._common.methods.maya_command import detect_commands

        src = ("import functools\n"
               "@functools.lru_cache\n"
               "def cached(self):\n"
               "    return 1\n")
        self.assertEqual(detect_commands(src), [])

    def test_syntax_error_source_returns_empty(self):
        from mpynode._common.methods.maya_command import detect_commands

        self.assertEqual(detect_commands("def broken(:\n  pass\n"), [])

    def test_empty_source(self):
        from mpynode._common.methods.maya_command import detect_commands

        self.assertEqual(detect_commands(""), [])

    def test_duplicate_command_names_helper(self):
        from mpynode._common.methods.maya_command import (
            detect_commands,
            duplicate_command_names,
        )

        src = (
            "@maya_command\n"
            "def a(self):\n    pass\n"
            "@maya_command(name='a')\n"
            "def b(self):\n    pass\n"
        )
        cmds = detect_commands(src)
        self.assertEqual(duplicate_command_names(cmds), ["a"])

    def test_async_def_with_maya_command_is_skipped_and_warns(self):
        # MPxCommand.doIt is sync, so an async def can't be registered.
        # Detection ignores it AND warns: a silent skip would let the source
        # parse "fine" while the command never appears at runtime.
        import warnings

        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "from mpynode._common.methods.maya_command import maya_command\n"
            "\n"
            "@maya_command\n"
            "async def doIt(self):\n"
            "    return 1\n"
            "\n"
            "@maya_command\n"
            "def sync_cmd(self):\n"
            "    return 2\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cmds = detect_commands(src)
        self.assertEqual([c["func_name"] for c in cmds], ["sync_cmd"])
        msgs = [str(w.message) for w in caught
                if issubclass(w.category, UserWarning)]
        self.assertTrue(any("async" in m and "doIt" in m for m in msgs),
                        "expected UserWarning about async doIt; got: %r" % msgs)

    def test_aliased_decorator_warns_and_is_not_detected(self):
        # `import maya_command as mc` leaves a bare Name 'mc', which static
        # detection can't see. Returning [] is correct, but it MUST warn:
        # the silent drop is the trap.
        import warnings

        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "from mpynode._common.methods.maya_command import maya_command as mc\n"
            "\n"
            "@mc\n"
            "def setRegion(self, i):\n"
            "    pass\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cmds = detect_commands(src)
        self.assertEqual(cmds, [])
        msgs = [str(w.message) for w in caught
                if issubclass(w.category, UserWarning)]
        self.assertTrue(
            any("aliased" in m and "setRegion" in m for m in msgs),
            "expected UserWarning about aliased decorator on setRegion; got: %r"
            % msgs,
        )

    def test_attribute_form_via_module_alias_is_detected_no_warn(self):
        # `@m.maya_command` is the attribute form; the detector matches on
        # attr=='maya_command', so it is detected with no alias warning.
        import warnings

        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "import mpynode._common.methods.maya_command as m\n"
            "\n"
            "@m.maya_command\n"
            "def f(self):\n"
            "    pass\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cmds = detect_commands(src)
        self.assertEqual([c["func_name"] for c in cmds], ["f"])
        msgs = [str(w.message) for w in caught
                if issubclass(w.category, UserWarning)]
        self.assertFalse(
            any("aliased" in m for m in msgs),
            "did not expect aliased-decorator warning; got: %r" % msgs,
        )

    def test_non_literal_name_warns_and_falls_back_to_def_name(self):
        # `@maya_command(name=PREFIX+'X')` is not an ast.Constant str, so
        # detection warns and falls back to the def name; the command still
        # registers under something the warning names.
        import warnings

        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "PREFIX = 'cmd'\n"
            "@maya_command(name=PREFIX + 'X')\n"
            "def builder(self):\n"
            "    return 1\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            (c,) = detect_commands(src)
        self.assertEqual(c["name"], "builder")  # fallback to def name
        self.assertEqual(c["func_name"], "builder")
        msgs = [str(w.message) for w in caught
                if issubclass(w.category, UserWarning)]
        self.assertTrue(
            any("name=" in m and "builder" in m for m in msgs),
            "expected UserWarning about non-literal name=; got: %r" % msgs,
        )

    def test_non_literal_undoable_warns_and_defaults_true(self):
        # `@maya_command(undoable=SOME_FLAG)` is not an ast.Constant bool, so
        # warn and fall back to the documented default True. Flipping an
        # intended non-undoable to True silently would be a footgun.
        import warnings

        from mpynode._common.methods.maya_command import detect_commands

        src = (
            "SOME_FLAG = False\n"
            "@maya_command(undoable=SOME_FLAG)\n"
            "def runner(self):\n"
            "    return 1\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            (c,) = detect_commands(src)
        self.assertEqual(c["name"], "runner")
        self.assertTrue(c["undoable"])  # defaulted to True
        msgs = [str(w.message) for w in caught
                if issubclass(w.category, UserWarning)]
        self.assertTrue(
            any("undoable" in m for m in msgs),
            "expected UserWarning about non-literal undoable=; got: %r" % msgs,
        )


def setUpModule():
    _setUpModule__command_codegen()
    _setUpModule__command_clash()


if __name__ == "__main__":
    import unittest
    unittest.main()
