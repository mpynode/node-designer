"""Bundling nodes that are ALREADY compiled into one plug-in -- the planner
(``bundle_plan``), the bundler changes it relies on, and the CLI.

Text only: nothing here runs a compiler. What the compiled result does is
covered by ``test_native_bundle_build`` (skipped without a toolchain) and was
verified by hand on a 5-node bundle -- a plain node, a curve generator, a
transform with a companion matrix class, a deformer and a hover locator --
loaded in Maya 2025 alone and beside a standalone plug-in owning one of them.

Two of the bundler changes are load-bearing for correctness, not features:

* ISOLATION. A ported node carries its whole inlined runtime at file scope,
  before the point where the transform used to open the node namespace, so
  every member of a bundle shared ONE copy of each inline function and the
  linker silently kept whichever it saw first. MEASURED with two real versions
  of ``nd_runtime.h``: ``nd::det`` threw for one node in one link order.
  Every global run is now wrapped in the node's namespace.
* IDS ARE KEPT. Each node keeps the id it shipped with; a duplicate is refused
  rather than probed forward, because a probed id would depend on what else is
  in the bundle and ``.mb`` scenes store ids. The bundler used to overwrite a
  pinned id silently (0x00050000 became 0x00013315 in a probe).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock


def _src(node, cls, tid, commands=(), runtime=True, trailing="", companion=None,
         global_only=""):
    """A standalone node source shaped like a ported one: an inlined
    "runtime" between two includes, then the class, then the entry points."""
    rt = ("#ifndef ND_RT\n#define ND_RT\n"
          "namespace nd { inline int det() { return 1; } }\n"
          "static double _clock() { using namespace std::chrono; return 0.0; }\n"
          "#endif\n") if runtime else ""
    comp = ""
    if companion:
        ccls, ctid = companion
        comp = ("class %s { public: static MTypeId id; };\nMTypeId %s::id(%s);\n"
                % (ccls, ccls, ctid))
    regs = "".join(
        '    MStatus _c%d = plugin.registerCommand("%s", %s::creator, %s::newSyntax); '
        'if (!_c%d) return _c%d;\n' % (i, c, cls, cls, i, i)
        for i, c in enumerate(commands))
    deregs = "".join('    plugin.deregisterCommand("%s");\n' % c for c in commands)
    return (
        "// build: abcdef123456\n"
        "#include <maya/MPxNode.h>\n"
        "#include <chrono>\n"
        + rt + global_only +
        "#include <maya/MFnPlugin.h>\n"
        "class %s : public MPxNode {\n"
        "public:\n"
        "    static void* creator() { return new %s(); }\n"
        "    static MStatus initialize() { return MS::kSuccess; }\n"
        "    static MTypeId id;\n"
        "};\n"
        "MTypeId %s::id(%s);\n"
        "%s"
        "MStatus initializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj, \"x\", \"1.0\", \"Any\");\n"
        "    MStatus _st = plugin.registerNode(\"%s\", %s::id, %s::creator, %s::initialize);\n"
        "    if (!_st) return _st;\n"
        "%s"
        "    return MS::kSuccess;\n"
        "}\n"
        "MStatus uninitializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj);\n"
        "%s"
        "    return plugin.deregisterNode(%s::id);\n"
        "}\n"
        "%s"
        % (cls, cls, cls, tid, comp, node, cls, cls, cls, regs, deregs, cls, trailing))


def _write(d, name, text):
    p = os.path.abspath(os.path.join(d, name))  # abspath: one separator style
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def _fragment(node, cls, tid, version=2, **kw):
    """A fragment as the transform emits it (v2), or with the stamp stripped
    and the preamble un-isolated (v1, the shape shipped in the mega tree)."""
    from mpynode.native.compiler import bundler

    frag, _info = bundler.transform_node_cpp(_src(node, cls, tid, **kw), node,
                                             lambda key: tid)
    if version >= 2:
        return frag
    lines = [ln for ln in frag.splitlines()
             if ln != bundler.FRAGMENT_STAMP
             and ln not in ("namespace nd_%s {" % node, "}  // namespace nd_%s" % node)]
    # put the ONE body namespace back, and name the hooks after the CLASS as
    # the old transform did (register_<Cls>), which is what E5 is about
    text    = "\n".join(lines)
    body_at = text.index("class %s" % cls)
    text = (text[:body_at] + "namespace nd_%s {\n" % node + text[body_at:]
            .replace("MStatus register_", "}  // namespace nd_%s\n\nMStatus register_"
                     % node, 1))
    return text.replace("register_nd_%s" % node, "register_%s" % cls)


def _devkit(d):
    """A fake Maya root that passes the devkit check."""
    os.makedirs(os.path.join(d, "maya", "include", "maya"), exist_ok=True)
    return os.path.join(d, "maya")


class TestResolveInputs(unittest.TestCase):

    def setUp(self):
        from mpynode.native.toolchain import bundle_plan

        self.bp = bundle_plan
        self.d  = tempfile.mkdtemp(prefix="bundle_in_")
        self.a  = _write(self.d, "plug/build/source/aNode.cpp", "// a")
        self.b  = _write(self.d, "plug/build/source/bNode.cpp", "// b")
        _write(self.d, "plug/build/source/plugin_main.cpp", "// main")
        _write(self.d, "plug/build/source/shared_helpers.cpp", "// shared")

    def test_a_folder_gives_its_node_sources_and_skips_the_bundles_own_files(self):
        self.assertEqual(self.bp.resolve_inputs([os.path.join(self.d, "plug")]),
                         [self.a, self.b])

    def test_a_selector_picks_nodes_by_file_stem(self):
        self.assertEqual(self.bp.resolve_inputs([os.path.join(self.d, "plug") + "::bNode"]),
                         [self.b])

    def test_a_selector_naming_an_absent_node_is_an_error(self):
        with self.assertRaises(self.bp.InputError):
            self.bp.resolve_inputs([os.path.join(self.d, "plug") + "::cNode"])

    def test_a_list_file_and_a_duplicate(self):
        lst = _write(self.d, "list.txt", "%s\n# comment\n%s\n%s\n" % (self.a, self.b, self.a))
        self.assertEqual(self.bp.resolve_inputs(["@" + lst]), [self.a, self.b])

    def test_a_missing_input_is_an_error(self):
        with self.assertRaises(self.bp.InputError):
            self.bp.resolve_inputs([os.path.join(self.d, "nope.cpp")])


class TestScanTellsWhatAnInputIs(unittest.TestCase):

    def setUp(self):
        from mpynode.native.toolchain import bundle_plan

        self.bp = bundle_plan
        self.d  = tempfile.mkdtemp(prefix="bundle_scan_")

    def test_identity_comes_from_the_registered_name_not_the_file(self):
        p = _write(self.d, "whatever.cpp", _src("fooNode", "FooNode", "0x00081000",
                                                commands=("fooCmd",),
                                                companion=("FooMatrix", "0x00081001")))
        m = self.bp.scan(p)
        self.assertEqual((m.kind, m.node, m.cls), ("standalone", "fooNode", "FooNode"))
        self.assertEqual(m.ids, {"fooNode": "0x00081000", "fooNode#FooMatrix": "0x00081001"})
        self.assertEqual(m.commands, ["fooCmd"])
        self.assertEqual(m.build_stamp, "abcdef123456")

    def test_the_scratch_layout_is_recognised(self):
        p = _write(self.d, "build/fooNode/fooNode.cpp", _src("fooNode", "FooNode", "0x00070001"))
        self.assertEqual(self.bp.scan(p).kind, "scratch")

    def test_a_fragment_and_its_version(self):
        v2 = _write(self.d, "v2.cpp", _fragment("barNode", "BarNode", "0x00081002"))
        v1 = _write(self.d, "v1.cpp", _fragment("bazNode", "BazNode", "0x00081003", version=1))
        m2, m1 = self.bp.scan(v2), self.bp.scan(v1)
        self.assertEqual((m2.kind, m2.fragment_version, m2.node), ("fragment", 2, "barNode"))
        self.assertEqual((m1.kind, m1.fragment_version, m1.node), ("fragment", 1, "bazNode"))
        self.assertEqual(m2.hook, "register_nd_barNode")

    def test_the_bundles_own_files_are_refused(self):
        p = _write(self.d, "plugin_main.cpp", "// anything")
        self.assertEqual(self.bp.scan(p).kind, "refused")

    def test_a_plug_in_that_registers_no_node_is_refused(self):
        text = _src("fooNode", "FooNode", "0x00081000").replace(
            'plugin.registerNode("fooNode", FooNode::id, FooNode::creator, FooNode::initialize)',
            'plugin.registerShape("fooNode", FooNode::id, FooNode::creator, FooNode::initialize, 0, 0)')
        m = self.bp.scan(_write(self.d, "shape.cpp", text))
        self.assertEqual(m.kind, "refused")
        self.assertIn("registers no node type", m.reason)

    def test_code_after_uninitializeplugin_is_refused_not_dropped(self):
        p = _write(self.d, "tail.cpp", _src("fooNode", "FooNode", "0x00081000",
                                            trailing="int stray() { return 1; }\n"))
        m = self.bp.scan(p)
        self.assertEqual(m.kind, "refused")
        self.assertIn("after uninitializePlugin", m.reason)

    def test_something_else_entirely_is_refused(self):
        m = self.bp.scan(_write(self.d, "x.cpp", "int main() { return 0; }\n"))
        self.assertEqual(m.kind, "refused")

    def test_the_sibling_manifest_is_read(self):
        p = _write(self.d, "plug/build/source/fooNode.cpp", _src("fooNode", "FooNode", "0x00081000"))
        _write(self.d, "plug/build/manifest.json", json.dumps({
            "plugin_name": "plug", "porter_recipe_version": "36",
            "nodes": [{"type_name": "fooNode", "type_id": "0x00081000"}]}))
        m = self.bp.scan(p)
        self.assertEqual((m.manifest_id, m.recipe, m.source_plugin), ("0x00081000", "36", "plug"))


class TestEachNodeKeepsTheIdItShippedWith(unittest.TestCase):

    def setUp(self):
        from mpynode.native.toolchain import bundle_plan

        self.bp = bundle_plan
        self.d  = tempfile.mkdtemp(prefix="bundle_ids_")

    def _member(self, tid, name="fooNode", cls="FooNode", manifest=None, scratch=False, **kw):
        rel = "build/%s/%s.cpp" % (name, name) if scratch else "build/source/%s.cpp" % name
        p   = _write(self.d, rel, _src(name, cls, tid, **kw))
        if manifest:
            _write(self.d, "build/manifest.json", json.dumps({
                "plugin_name": "p", "nodes": [{"type_name": name, "type_id": manifest}]}))
        return self.bp.scan(p)

    def test_a_real_literal_is_kept_even_outside_the_testing_block(self):
        m = self._member("0x00123456")
        self.bp.resolve_ids([m])
        self.assertEqual(m.resolved["fooNode"], "0x00123456")
        self.assertEqual(m.id_source["fooNode"], "literal")

    def test_a_placeholder_gives_way_to_the_manifest(self):
        from mpynode.native.spec.spec_extractor import suggest_type_id

        m = self._member(suggest_type_id("fooNode"), manifest="0x00013315", scratch=True)
        self.bp.resolve_ids([m])
        self.assertEqual((m.resolved["fooNode"], m.id_source["fooNode"]),
                         ("0x00013315", "manifest"))

    def test_a_placeholder_with_nothing_else_derives(self):
        from mpynode.native.spec.spec_extractor import suggest_type_id
        from mpynode.native.toolchain import typeid_registry

        m = self._member(suggest_type_id("fooNode"), scratch=True)
        self.bp.resolve_ids([m])
        self.assertEqual(m.id_source["fooNode"], "derived")
        self.assertEqual(m.resolved["fooNode"],
                         "0x%08x" % typeid_registry.deterministic_id("fooNode"))

    def test_a_companion_placeholder_is_placeholder_plus_one(self):
        from mpynode.native.spec.spec_extractor import suggest_type_id

        ph = int(suggest_type_id("fooNode"), 16)
        m  = self._member("0x00081000", companion=("FooMatrix", "0x%08x" % (ph + 1)))
        self.bp.resolve_ids([m])
        self.assertEqual(m.id_source["fooNode#FooMatrix"], "derived")
        self.assertEqual(m.id_source["fooNode"], "literal")

    def test_a_pin_wins(self):
        m = self._member("0x00081000")
        self.bp.resolve_ids([m], pins={"fooNode": "0x00090000"})
        self.assertEqual((m.resolved["fooNode"], m.id_source["fooNode"]),
                         ("0x00090000", "pinned"))

    def test_a_fragments_id_is_baked_in_so_a_pin_is_refused(self):
        p    = _write(self.d, "f.cpp", _fragment("barNode", "BarNode", "0x00081002"))
        m    = self.bp.scan(p)
        errs = self.bp.resolve_ids([m], pins={"barNode": "0x00090000"})
        self.assertEqual([c for c, _ in errs], ["E4"])
        self.assertEqual(m.resolved["barNode"], "0x00081002")


class TestPreflightRefusesEveryBadCombination(unittest.TestCase):

    MAYA = None

    def setUp(self):
        from mpynode.native.toolchain import bundle_plan

        self.bp   = bundle_plan
        self.d    = tempfile.mkdtemp(prefix="bundle_pf_")
        self.maya = _devkit(self.d)

    def _scan(self, rel, text):
        return self.bp.scan(_write(self.d, rel, text))

    def _codes(self, members, **kw):
        plan = self.bp.preflight(members, maya=self.maya, **kw)
        return sorted({c for c, _m in plan.errors}), plan

    def test_a_clean_set_passes(self):
        codes, plan = self._codes([
            self._scan("a/build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000")),
            self._scan("b/build/source/bNode.cpp", _src("bNode", "BNode", "0x00081001"))])
        self.assertEqual(codes, [])
        self.assertEqual([m.node for m in plan.members], ["aNode", "bNode"])

    def test_E1_the_same_node_from_two_different_sources(self):
        codes, _ = self._codes([
            self._scan("a/aNode.cpp", _src("aNode", "ANode", "0x00081000")),
            self._scan("b/aNode.cpp", _src("aNode", "ANode", "0x00081000", commands=("x",)))])
        self.assertEqual(codes, ["E1"])

    def test_byte_identical_duplicates_are_merged_not_refused(self):
        text = _src("aNode", "ANode", "0x00081000")
        codes, plan = self._codes([self._scan("a/aNode.cpp", text),
                                   self._scan("b/aNode.cpp", text)])
        self.assertEqual(codes, [])
        self.assertEqual(len(plan.members), 1)
        self.assertTrue(any("identical" in w for w in plan.warnings))

    def test_E2_names_that_collide_once_sanitised(self):
        codes, _ = self._codes([
            self._scan("a/x.cpp", _src("a-node", "ANode", "0x00081000")),
            self._scan("b/y.cpp", _src("a_node", "BNode", "0x00081001"))])
        self.assertEqual(codes, ["E2"])

    def test_E3_a_command_registered_twice(self):
        codes, _ = self._codes([
            self._scan("a/a.cpp", _src("aNode", "ANode", "0x00081000", commands=("doIt",))),
            self._scan("b/b.cpp", _src("bNode", "BNode", "0x00081001", commands=("doIt",)))])
        self.assertEqual(codes, ["E3"])

    def test_E4_two_members_on_one_id_are_refused_not_probed(self):
        codes, _ = self._codes([
            self._scan("a/a.cpp", _src("aNode", "ANode", "0x00081000")),
            self._scan("b/b.cpp", _src("bNode", "BNode", "0x00081000"))])
        self.assertEqual(codes, ["E4"])

    def test_E5_legacy_fragments_whose_classes_share_a_name(self):
        codes, _ = self._codes([
            self._scan("a/a.cpp", _fragment("aNode", "Node", "0x00081000", version=1)),
            self._scan("b/b.cpp", _fragment("bNode", "Node", "0x00081001", version=1))])
        self.assertEqual(codes, ["E5"])

    def test_E6_and_E7(self):
        frag = _fragment("aNode", "ANode", "0x00081000") + \
            "\n// shared helper prototypes (defined in shared_helpers.cpp)\n"
        codes, _ = self._codes([self._scan("plugin_main.cpp", "// x"),
                                self._scan("f.cpp", frag)])
        self.assertEqual(codes, ["E6", "E7"])

    def test_E8_members_that_disagree_on_global_only_code(self):
        a = _src("aNode", "ANode", "0x00081000", global_only='extern "C" int hook() { return 1; }\n')
        b = _src("bNode", "BNode", "0x00081001", global_only='extern "C" int hook() { return 2; }\n')
        codes, _ = self._codes([self._scan("a/a.cpp", a), self._scan("b/b.cpp", b)])
        self.assertEqual(codes, ["E8"])

    def test_E9_a_qt_member_with_no_qt_headers(self):
        from mpynode.native.toolchain import toolchain

        text = _src("aNode", "ANode", "0x00081000").replace(
            "#include <maya/MFnPlugin.h>", "#include <QtGui/QCursor>\n#include <maya/MFnPlugin.h>")
        with mock.patch.object(toolchain, "qt_include_problem", return_value="no Qt here"):
            codes, plan = self._codes([self._scan("a/a.cpp", text)])
        self.assertEqual(codes, ["E9"])
        self.assertTrue(plan.needs_qt)

    def test_E10_linux(self):
        from mpynode.native.toolchain import toolchain

        with mock.patch.object(toolchain, "is_linux", return_value=True):
            codes, _ = self._codes([self._scan("a/a.cpp", _src("aNode", "ANode", "0x00081000"))])
        self.assertEqual(codes, ["E10"])

    def test_exclude_drops_a_member_with_a_warning(self):
        codes, plan = self._codes([
            self._scan("a/a.cpp", _src("aNode", "ANode", "0x00081000")),
            self._scan("b/b.cpp", _src("bNode", "BNode", "0x00081001"))], exclude=["bNode"])
        self.assertEqual(codes, [])
        self.assertEqual([m.node for m in plan.members], ["aNode"])
        self.assertTrue(any("excluded bNode" in w for w in plan.warnings))

    def test_a_command_bearing_member_warns_about_its_own_plugin(self):
        self._scan("p/build/manifest.json", json.dumps({"plugin_name": "solo", "nodes": [
            {"type_name": "aNode", "type_id": "0x00081000"}]}))
        m = self._scan("p/build/source/aNode.cpp", _src("aNode", "ANode", "0x00081000", commands=("aCmd",)))
        _codes, plan = self._codes([m])
        self.assertTrue(any("beside its own plug-in 'solo'" in w for w in plan.warnings))


class TestIsolationGivesEachNodeItsOwnRuntime(unittest.TestCase):

    def _frag(self, **kw):
        from mpynode.native.compiler import bundler

        return bundler.transform_node_cpp(_src("fooNode", "FooNode", "0x00081000", **kw),
                                          "fooNode", lambda k: "0x00081000")

    def test_the_runtime_sits_inside_the_node_namespace(self):
        frag, _ = self._frag()
        self.assertLess(frag.index("namespace nd_fooNode {"), frag.index("namespace nd {"))
        # reopened: once around the runtime run, once around the body
        self.assertGreaterEqual(frag.count("namespace nd_fooNode {"), 2)

    def test_directives_stay_outside(self):
        frag, _ = self._frag()
        for ln in frag.splitlines():
            if ln.startswith("#"):
                self.assertNotIn("namespace", ln)
        # the include guard's #endif is not swallowed into a namespace block
        self.assertIn("#endif", frag)

    def test_the_fragment_is_stamped_and_hooks_are_named_after_the_namespace(self):
        from mpynode.native.compiler import bundler

        frag, info = self._frag()
        self.assertTrue(frag.startswith(bundler.FRAGMENT_STAMP + "\n"))
        self.assertEqual((info["register"], info["deregister"]),
                         ("register_nd_fooNode", "deregister_nd_fooNode"))
        self.assertEqual(info["version"], 2)

    def test_a_using_directive_does_not_keep_a_run_out(self):
        # every hover locator has `using namespace std::chrono;` in a clock helper
        frag, info = self._frag()
        self.assertEqual(info["unwrapped_runs"], [])
        self.assertLess(frag.index("namespace nd_fooNode {"), frag.index("_clock()"))

    def test_a_std_specialisation_stays_at_global_scope(self):
        frag, info = self._frag(global_only="namespace std { template<> struct hash<int> {}; }\n")
        self.assertEqual(len(info["unwrapped_runs"]), 1)
        at = frag.index("namespace std {")
        # not wrapped: the nearest enclosing open before it has been closed
        self.assertEqual(frag.count("namespace nd_fooNode {", 0, at),
                         frag.count("}  // namespace nd_fooNode", 0, at))


class TestALegacyFragmentIsUpgradedOnTheWayIn(unittest.TestCase):

    def test_v1_gets_isolated_and_stamped(self):
        from mpynode.native.compiler import bundler

        v1 = _fragment("barNode", "BarNode", "0x00081002", version=1)
        self.assertNotIn(bundler.FRAGMENT_STAMP, v1)
        new, info = bundler.upgrade_fragment(v1)
        self.assertEqual(info["version"], 2)
        self.assertLess(new.index("namespace nd_barNode {"), new.index("namespace nd {"))
        self.assertEqual(bundler.fragment_info(new)["type_id_map"], {"barNode": "0x00081002"})

    def test_v2_is_returned_unchanged(self):
        from mpynode.native.compiler import bundler

        v2 = _fragment("barNode", "BarNode", "0x00081002")
        self.assertEqual(bundler.upgrade_fragment(v2)[0], v2)

    def test_a_fragment_needing_the_shared_unit_is_refused(self):
        from mpynode.native.compiler import bundler

        v1 = _fragment("barNode", "BarNode", "0x00081002", version=1)
        v1 = v1.replace("#include <maya/MFnPlugin.h>",
                        "#include <maya/MFnPlugin.h>\n// shared helper prototypes (defined in shared_helpers.cpp)\nint helper(int);")
        with self.assertRaises(ValueError):
            bundler.upgrade_fragment(v1)


class TestAssemblePassesFragmentsThrough(unittest.TestCase):

    def setUp(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import typeid_registry

        self.bundler = bundler
        self.d       = tempfile.mkdtemp(prefix="bundle_asm_")
        self.reg     = typeid_registry.TypeIdRegistry(path=os.path.join(self.d, "none.json"))

    def test_a_fragment_keeps_its_literal_id_and_joins_plugin_main(self):
        a = _write(self.d, "aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        f = _write(self.d, "barNode.cpp", _fragment("barNode", "BarNode", "0x00081002", version=1))
        rep = self.bundler.assemble([("aNode", a), ("barNode", f)], "duo",
                                    os.path.join(self.d, "out"), compile_now=False,
                                    registry=self.reg)
        self.assertTrue(rep["ok"], rep)
        by = {r["name"]: r for r in rep["nodes"]}
        self.assertEqual(by["barNode"]["id"], "0x00081002")
        self.assertEqual(by["barNode"]["status"], "generated")
        with open(os.path.join(self.d, "out", "build", "source", "plugin_main.cpp")) as fh:
            pm = fh.read()
        self.assertIn("register_nd_aNode", pm)
        # the legacy fragment's own hook name is kept: it is in its text
        self.assertIn("register_BarNode", pm)
        self.assertIn("0x00081002u", pm)
        with open(os.path.join(self.d, "out", "build", "source", "barNode.cpp")) as fh:
            self.assertTrue(fh.read().startswith(self.bundler.FRAGMENT_STAMP))

    def test_a_lone_fragment_takes_the_multi_node_path(self):
        f = _write(self.d, "barNode.cpp", _fragment("barNode", "BarNode", "0x00081002"))
        rep = self.bundler.assemble([("barNode", f)], "solo", os.path.join(self.d, "out1"),
                                    compile_now=False, registry=self.reg)
        self.assertTrue(rep["ok"], rep)
        self.assertTrue(os.path.isfile(os.path.join(self.d, "out1", "build", "source",
                                                    "plugin_main.cpp")))

    def test_two_fragments_on_one_id_is_an_error_not_a_silent_move(self):
        f1 = _write(self.d, "aNode.cpp", _fragment("aNode", "ANode", "0x00081002"))
        f2 = _write(self.d, "bNode.cpp", _fragment("bNode", "BNode", "0x00081002"))
        rep = self.bundler.assemble([("aNode", f1), ("bNode", f2)], "duo",
                                    os.path.join(self.d, "out2"), compile_now=False,
                                    registry=self.reg, strict=False)
        self.assertIn("bNode", rep["dropped"])
        self.assertIn("already held", rep["nodes"][1]["reason"])

    def test_a_transform_failure_is_reported_as_dropped(self):
        a   = _write(self.d, "aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        bad = _write(self.d, "bad.cpp", "int x;\n")
        rep = self.bundler.assemble([("aNode", a), ("bad", bad)], "duo",
                                    os.path.join(self.d, "out3"), compile_now=False,
                                    registry=self.reg, strict=False)
        self.assertEqual(rep["dropped"], ["bad"])


class TestRegistryLiteralClaims(unittest.TestCase):

    def test_claim_keeps_exactly_the_value(self):
        from mpynode.native.toolchain import typeid_registry

        reg = typeid_registry.TypeIdRegistry(path="/nonexistent.json")
        reg.claim_literal("fooNode", "0x00123456")
        self.assertEqual(reg.allocate_many(["fooNode"]), {"fooNode": "0x00123456"})
        self.assertEqual(reg.sources["fooNode"], "literal")

    def test_a_second_owner_is_an_error(self):
        from mpynode.native.toolchain import typeid_registry

        reg = typeid_registry.TypeIdRegistry(path="/nonexistent.json")
        reg.claim_literal("fooNode", "0x00123456")
        with self.assertRaises(ValueError):
            reg.claim_literal("barNode", "0x00123456")

    def test_pin_admits_the_full_range_only_when_asked(self):
        from mpynode.native.toolchain import typeid_registry

        reg = typeid_registry.TypeIdRegistry(path="/nonexistent.json")
        self.assertIsNone(reg.pin("a", "0x00123456"))
        self.assertEqual(reg.pin("a", "0x00123456", any_range=True), 0x123456)


class TestTheSweepLeavesHandWrittenScriptsAlone(unittest.TestCase):

    def test_only_generated_files_are_swept(self):
        from mpynode.native.compiler import bundler

        d    = tempfile.mkdtemp(prefix="bundle_sweep_")
        mine = _write(d, "build.bat", "@echo off\nREM my wrapper\n")
        gen  = _write(d, "build.sh", bundler.make_build_sh("p", ["a.cpp"]))
        bundler._clean_stale_intermediates(d)
        self.assertTrue(os.path.exists(mine))
        self.assertFalse(os.path.exists(gen))


class TestOutputFolderGuard(unittest.TestCase):

    def test_new_empty_and_bundler_written_are_fine_a_strangers_is_not(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import bundle_plan

        d = tempfile.mkdtemp(prefix="bundle_out_")
        self.assertIsNone(bundle_plan.out_dir_problem(os.path.join(d, "new")))
        self.assertIsNone(bundle_plan.out_dir_problem(d))
        _write(d, "build/README.txt", bundler.make_readme("p", ["a.cpp"], single=False,
                                                          bundle_name="p.mll"))
        self.assertIsNone(bundle_plan.out_dir_problem(d))
        other = tempfile.mkdtemp(prefix="bundle_other_")
        _write(other, "notes.txt", "mine")
        self.assertIn("not written by the bundler", bundle_plan.out_dir_problem(other))


class TestBuildWritesAManifestARefreshCanReadBack(unittest.TestCase):

    def test_generated_tree_and_manifest(self):
        from mpynode.native.toolchain import bundle_plan

        d    = tempfile.mkdtemp(prefix="bundle_build_")
        maya = _devkit(d)
        a    = _write(d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000", commands=("aCmd",)))
        f    = _write(d, "in/barNode.cpp", _fragment("barNode", "BarNode", "0x00081002", version=1))
        plan = bundle_plan.preflight([bundle_plan.scan(a), bundle_plan.scan(f)], maya=maya)
        self.assertTrue(plan.ok, plan.errors)
        out = os.path.join(d, "out")
        rep = bundle_plan.build(plan, "duo", out, maya=maya, compile_now=False,
                                vendor="Acme", strict_load=True)
        self.assertTrue(rep["ok"], rep)
        man = bundle_plan.read_manifest(out)
        self.assertEqual(man["plugin_name"], "duo")
        self.assertEqual(man["vendor"], "Acme")
        self.assertTrue(man["strict_load"])
        self.assertTrue(man["version"].startswith("1.0+"))
        rows = {r["type_name"]: r for r in man["nodes"]}
        self.assertEqual(rows["aNode"]["type_id"], "0x00081000")
        self.assertEqual(rows["aNode"]["commands"], ["aCmd"])
        self.assertEqual(rows["barNode"]["build_status"], "generated")
        self.assertEqual([r["path"] for r in man["bundled_from"]], [a, f])
        paths, back = bundle_plan.refresh_inputs(out)
        self.assertEqual((paths, back["plugin_name"]), ([a, f], "duo"))
        with open(os.path.join(out, "build", "source", "plugin_main.cpp")) as fh:
            self.assertIn("#define ND_BUNDLE_STRICT 1", fh.read())

    def test_refused_plans_do_not_build(self):
        from mpynode.native.toolchain import bundle_plan

        d    = tempfile.mkdtemp(prefix="bundle_refused_")
        maya = _devkit(d)
        a    = _write(d, "a/a.cpp", _src("aNode", "ANode", "0x00081000"))
        b    = _write(d, "b/b.cpp", _src("bNode", "BNode", "0x00081000"))
        plan = bundle_plan.preflight([bundle_plan.scan(a), bundle_plan.scan(b)], maya=maya)
        with self.assertRaises(bundle_plan.BundleRefused) as cm:
            bundle_plan.build(plan, "duo", os.path.join(d, "out"), maya=maya, compile_now=False)
        self.assertEqual(cm.exception.codes, ["E4"])
        self.assertFalse(os.path.exists(os.path.join(d, "out")))


class TestTheCli(unittest.TestCase):

    def setUp(self):
        from mpynode.native import bundle

        self.cli  = bundle
        self.d    = tempfile.mkdtemp(prefix="bundle_cli_")
        self.maya = _devkit(self.d)
        self.a    = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b    = _write(self.d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def _run(self, *argv):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cli.main(list(argv))
        return rc, buf.getvalue()

    def test_usage_errors_exit_3(self):
        self.assertEqual(self._run()[0], 3)
        self.assertEqual(self._run("bad name", self.a, "--maya", self.maya)[0], 3)
        self.assertEqual(self._run("--check")[0], 3)
        self.assertEqual(self._run("p", self.a, "--maya", self.maya, "--pin", "nonsense")[0], 3)
        self.assertEqual(self._run("p", self.a, "--maya", "2099")[0], 3)

    def test_check_passes_a_clean_set_and_refuses_a_bad_one(self):
        rc, out = self._run("--check", self.a, self.b, "--maya", self.maya)
        self.assertEqual(rc, 0, out)
        self.assertIn("pre-flight: ok, 2 member(s)", out)
        dup = _write(self.d, "dup/aNode.cpp", _src("aNode", "ANode", "0x00081001"))
        rc, out = self._run("--check", self.a, dup, "--maya", self.maya)
        self.assertEqual(rc, 2)
        self.assertIn("E1", out)

    def test_check_json(self):
        rc, out = self._run("--check", self.a, "--maya", self.maya, "--json")
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual([m["node"] for m in doc["members"]], ["aNode"])

    def test_no_compile_writes_a_rebuildable_tree(self):
        out_dir = os.path.join(self.d, "out")
        rc, out = self._run("duo", self.a, self.b, "--maya", self.maya, "--out", out_dir,
                            "--no-compile")
        self.assertEqual(rc, 0, out)
        for f in ("build/build.bat", "build/build.sh", "build/manifest.json",
                  "build/source/aNode.cpp", "build/source/bNode.cpp",
                  "build/source/plugin_main.cpp"):
            self.assertTrue(os.path.isfile(os.path.join(out_dir, f)), f)
        self.assertIn("generated:", out)

    def test_a_foreign_output_folder_is_refused(self):
        out_dir = os.path.join(self.d, "taken")
        _write(out_dir, "keep.txt", "not yours")
        rc, out = self._run("duo", self.a, self.b, "--maya", self.maya, "--out", out_dir,
                            "--no-compile")
        self.assertEqual(rc, 2)
        self.assertIn("E11", out)
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "keep.txt")))

    def test_refresh_rebuilds_the_recorded_set(self):
        out_dir = os.path.join(self.d, "out")
        self.assertEqual(self._run("duo", self.a, self.b, "--maya", self.maya, "--out",
                                   out_dir, "--no-compile")[0], 0)
        rc, out = self._run("--refresh", out_dir, "--no-compile")
        self.assertEqual(rc, 0, out)
        self.assertIn("aNode", out)
        self.assertIn("bNode", out)


if __name__ == "__main__":
    unittest.main()
