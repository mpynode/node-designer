"""A multi-node plug-in must not leave orphan node types behind when its load
goes wrong.

The generated ``plugin_main.cpp`` used to register members in order and return
on the first failure. MEASURED with the shipped mPyMega (2026-09-28): with the
standalone NURBS Wave plug-in loaded first, its command clashed at the 4th
member, the load failed, and the three members registered before it stayed
registered with no plug-in behind them -- ``createNode procrustesTags`` then
crashed Maya.

The entry point is now a table walked with a session pre-check (node type
name, MTypeId, command), skip-or-fail per member, undo of a half-registered
member, and an unload that touches only what this load registered. These
tests pin that shape on the generated text; the real load behaviour was
verified by building a bundle and loading it beside a standalone plug-in that
owns one of its nodes (see the commit that added this file).
"""

from __future__ import annotations

import os
import tempfile
import unittest

from tests.compile.pipeline.test_native_compile_layout import _node_src


def _infos():
    return [
        {"node_name": "fooNode", "class": "FooNode", "ns": "nd_fooNode",
         "register": "register_FooNode", "deregister": "deregister_FooNode",
         "type_names": ["fooNode"], "type_ids": ["0x00081000"], "commands": []},
        {"node_name": "barNode", "class": "BarNode", "ns": "nd_barNode",
         "register": "register_BarNode", "deregister": "deregister_BarNode",
         "type_names": ["barNode"], "type_ids": ["0x00081001", "0x00081002"],
         "commands": ["barCmd", "barReset"]},
    ]


class TestEveryMemberIsCheckedBeforeItRegisters(unittest.TestCase):

    def setUp(self):
        from mpynode.native.compiler import bundler

        self.cpp = bundler.make_plugin_main(_infos(), "duo")

    def test_the_pre_check_runs_before_the_hook(self):
        self.assertLess(self.cpp.index("ndConflict(m)"), self.cpp.index("m.reg(plugin)"))

    def test_it_asks_the_session_all_three_questions(self):
        # Node type names, MTypeIds and command names are each ONE global space
        # per Maya session; a clash on any of them is what broke the load.
        self.assertIn("MNodeClass byName{MString(*t)};", self.cpp)
        self.assertIn("MNodeClass byId{MTypeId(*i)};", self.cpp)
        self.assertIn('whatIs', self.cpp)

    def test_a_conflicting_member_is_skipped_by_default(self):
        self.assertIn("#define ND_BUNDLE_STRICT 0", self.cpp)
        self.assertIn("(another loaded plug-in provides it)", self.cpp)
        self.assertIn("++skipped;", self.cpp)

    def test_a_half_registered_member_is_undone(self):
        # The hook is not atomic: node registered, then a command refused. Its
        # own deregister must run before anything else happens.
        fail = self.cpp.index("if (!st) {")
        self.assertLess(fail, self.cpp.index("m.dereg(plugin);"))
        self.assertLess(self.cpp.index("m.dereg(plugin);"), self.cpp.index("failed to register"))

    def test_unload_touches_only_what_this_load_registered(self):
        self.assertIn("bool g_live[kCount] = {};", self.cpp)
        self.assertIn("if (!g_live[j]) continue;", self.cpp)
        self.assertIn("for (int j = kCount - 1; j >= 0; --j)", self.cpp)  # reverse
        self.assertIn("g_live[i] = true;", self.cpp)

    def test_nothing_registered_is_a_failed_load(self):
        self.assertIn("if (skipped == kCount)", self.cpp)
        self.assertIn("could be registered", self.cpp)


class TestStrictLoad(unittest.TestCase):

    def test_strict_undoes_every_earlier_member_and_fails(self):
        from mpynode.native.compiler import bundler

        cpp = bundler.make_plugin_main(_infos(), "duo", strict_load=True)
        self.assertIn("#define ND_BUNDLE_STRICT 1", cpp)
        self.assertIn("ndUnloadAll(plugin);\n            return MS::kFailure;", cpp)
        self.assertIn("ndUnloadAll(plugin);\n            return st;", cpp)

    def test_strictness_can_still_be_chosen_at_compile_time(self):
        from mpynode.native.compiler import bundler

        cpp = bundler.make_plugin_main(_infos(), "duo")
        # A plain `cl /D ND_BUNDLE_STRICT=1` on the generated tree flips it.
        self.assertIn("#ifndef ND_BUNDLE_STRICT", cpp)


class TestTheTableCarriesWhatThePreCheckReads(unittest.TestCase):

    def setUp(self):
        from mpynode.native.compiler import bundler

        self.cpp = bundler.make_plugin_main(_infos(), "duo", vendor="Acme", version="2.3")

    def test_names_ids_and_commands_per_member(self):
        self.assertIn('const char* const kTypes_0[] = {"fooNode", nullptr};', self.cpp)
        self.assertIn("const unsigned    kIds_0[]   = {0x00081000u, 0u};", self.cpp)
        self.assertIn("const char* const kCmds_0[]  = {nullptr};", self.cpp)
        self.assertIn("const unsigned    kIds_1[]   = {0x00081001u, 0x00081002u, 0u};", self.cpp)
        self.assertIn('const char* const kCmds_1[]  = {"barCmd", "barReset", nullptr};', self.cpp)
        self.assertIn('{"barNode", kTypes_1, kIds_1, kCmds_1, register_BarNode, deregister_BarNode},',
                      self.cpp)

    def test_hooks_are_declared_once_each(self):
        self.assertEqual(self.cpp.count("MStatus register_FooNode(MFnPlugin&);"), 1)
        self.assertEqual(self.cpp.count("MStatus deregister_BarNode(MFnPlugin&);"), 1)

    def test_vendor_and_version_reach_the_plugin(self):
        self.assertIn('MFnPlugin plugin(obj, "Acme", "2.3", "Any");', self.cpp)

    def test_an_int_id_and_a_quote_in_a_name_are_handled(self):
        from mpynode.native.compiler import bundler

        infos = _infos()
        infos[0]["type_ids"] = [0x81000]
        infos[0]["commands"] = ['say"hi']
        cpp = bundler.make_plugin_main(infos, "duo")
        self.assertIn("{0x00081000u, 0u}", cpp)
        self.assertIn('{"say\\"hi", nullptr}', cpp)


class TestFragmentInfoRecoversAMember(unittest.TestCase):
    """The shipped All Templates Plugin's entry point is regenerated from its
    fragments, so a fragment must give back exactly what the transform knew."""

    def _fragment(self):
        from mpynode.native.compiler import bundler

        src = _node_src("fooNode", "FooNode", "0x00081000", with_block=False)
        frag, info = bundler.transform_node_cpp(src, "fooNode", lambda k: "0x00081000")
        return frag, info

    def test_the_transform_records_the_members_claims(self):
        _frag, info = self._fragment()
        self.assertEqual(info["type_names"], ["fooNode"])
        self.assertEqual(info["type_ids"], ["0x00081000"])
        self.assertEqual(info["commands"], [])

    def test_a_fragment_reads_back_to_the_same_info(self):
        frag, info = self._fragment()
        from mpynode.native.compiler import bundler

        back = bundler.fragment_info(frag)
        for key in ("node_name", "class", "ns", "register", "deregister",
                    "type_names", "type_ids", "commands"):
            self.assertEqual(back[key], info[key], key)

    def test_a_single_node_source_is_not_a_fragment(self):
        from mpynode.native.compiler import bundler

        with self.assertRaises(ValueError):
            bundler.fragment_info(_node_src("fooNode", "FooNode", "0x00081000",
                                            with_block=False))

    def test_the_registered_name_comes_from_the_hook_not_the_file(self):
        from mpynode.native.compiler import bundler

        frag, _info = self._fragment()
        # A comment mentioning another registerNode before the hook must not win.
        frag = "// registerNode(\"decoy\", ...)\n" + frag
        self.assertEqual(bundler.fragment_info(frag)["node_name"], "fooNode")


class TestAssembleEmitsTheTable(unittest.TestCase):

    def test_a_generated_tree_carries_the_pre_check(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import typeid_registry

        d = tempfile.mkdtemp(prefix="pm_assemble_")
        paths = []
        for node, cls, tid in (("fooNode", "FooNode", "0x00081000"),
                               ("barNode", "BarNode", "0x00081001")):
            p = os.path.join(d, node + ".cpp")
            with open(p, "w") as fh:
                fh.write(_node_src(node, cls, tid, with_block=False))
            paths.append((node, p))
        reg = typeid_registry.TypeIdRegistry(path=os.path.join(d, "no-pins.json"))
        rep = bundler.assemble(paths, "duo", os.path.join(d, "out"),
                               compile_now=False, registry=reg,
                               vendor="Acme", version="0.1", strict_load=True)
        self.assertTrue(rep["nodes"], rep)
        with open(os.path.join(d, "out", "build", "source", "plugin_main.cpp")) as fh:
            cpp = fh.read()
        self.assertIn("#define ND_BUNDLE_STRICT 1", cpp)
        self.assertIn('MFnPlugin plugin(obj, "Acme", "0.1", "Any");', cpp)
        self.assertIn('kTypes_0[] = {"fooNode", nullptr};', cpp)
        self.assertIn("ndConflict", cpp)


if __name__ == "__main__":
    unittest.main()
