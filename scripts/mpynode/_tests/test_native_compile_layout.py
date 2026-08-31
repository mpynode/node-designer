"""Compile OUTPUT-FOLDER layout: a clean, self-explanatory folder.

Only the importable ``<plugin>.bundle`` (and any ``*_commands.py`` companion
plugins, emitted by the controller) sit at the top level; ALL source, build
scripts, README and the manifest live under ``build/`` -- with the C++ source
(``<node>.cpp`` / ``plugin_main.cpp`` / ``shared_helpers.cpp``) nested one level
deeper in ``build/source/``. The build scripts therefore read their inputs from
``$HERE/source/`` and write the rebuilt bundle back up to ``$HERE/../`` (the top
level), so a hand rebuild lands the bundle exactly where the programmatic build
did.

These assert the bundler's file placement with ``compile_now=False`` (no compiler
needed): the source/scripts are written regardless of whether the link runs.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from mpynode.native.compiler import bundler
from mpynode.native.toolchain import toolchain
from mpynode.native.toolchain import typeid_registry

# Reuse the minimal, valid single-node .cpp fixture (registerNode +
# initializePlugin/uninitializePlugin + MTypeId) the dedup suite already ships.
from mpynode._tests.test_native_helper_dedup import _node_src


def _reg(d):
    return typeid_registry.TypeIdRegistry(path=os.path.join(d, "reg.json"))


def _broken_node_src(node_name, cls, tid):
    """A node that TRANSFORMS fine (has registerNode + init/uninit) but does NOT
    compile (garbage in the compute body) -- to exercise the best-effort drop."""
    return (
        "#include <maya/MPxNode.h>\n"
        "#include <maya/MFnPlugin.h>\n"
        "class %s : public MPxNode {\n"
        "public:\n"
        "    static void* creator() { return new %s(); }\n"
        "    static MStatus initialize() { return MS::kSuccess; }\n"
        "    MStatus compute(const MPlug& plug, MDataBlock& data) override {\n"
        "        this is definitely not valid c++ @@@ ;\n"
        "        return MS::kSuccess;\n"
        "    }\n"
        "    static MTypeId id;\n"
        "};\n"
        "MTypeId %s::id(%s);\n"
        "MStatus initializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj, \"x\", \"1.0\", \"Any\");\n"
        "    return plugin.registerNode(\"%s\", %s::id, %s::creator, "
        "%s::initialize);\n"
        "}\n"
        "MStatus uninitializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj);\n"
        "    return plugin.deregisterNode(%s::id);\n"
        "}\n"
        % (cls, cls, cls, tid, node_name, cls, cls, cls, cls))


class TestCompileOutputLayout(unittest.TestCase):
    def _write_node(self, d, node, cls, tid):
        p = os.path.join(d, node + ".cpp")
        with open(p, "w") as fh:
            fh.write(_node_src(node, cls, tid, with_block=False))
        return p

    def _assemble(self, nodes, plugin, d):
        out = os.path.join(d, "out")
        report = bundler.assemble(nodes, plugin, out, strict=True,
                                  registry=_reg(d), compile_now=False)
        self.assertTrue(report.get("ok"), report)
        return out

    # ---- single-node -----------------------------------------------------
    def test_single_node_clean_top_level(self):
        d = tempfile.mkdtemp(prefix="layout_single_")
        p = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        out = self._assemble([("fooNode", p)], "solo", d)

        # Source is nested in build/source; scripts + README sit in build/.
        self.assertTrue(os.path.isfile(
            os.path.join(out, "build", "source", "fooNode.cpp")))
        for f in ("build.sh", "build.bat", "README.txt"):
            self.assertTrue(os.path.isfile(os.path.join(out, "build", f)), f)

        # Nothing spills to the top level (no bundle: compile_now=False).
        self.assertFalse(os.path.exists(os.path.join(out, "fooNode.cpp")))
        self.assertFalse(os.path.exists(os.path.join(out, "build.sh")))
        self.assertEqual(set(os.listdir(out)), {"build"})

    def test_single_build_sh_paths(self):
        d = tempfile.mkdtemp(prefix="layout_ssh_")
        p = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        out = self._assemble([("fooNode", p)], "solo", d)
        with open(os.path.join(out, "build", "build.sh")) as fh:
            sh = fh.read()
        self.assertIn("$HERE/source/fooNode.cpp", sh)      # input from source/
        self.assertIn('-o "$HERE/../solo.bundle"', sh)     # bundle to top level

    # ---- multi-node ------------------------------------------------------
    def test_multi_node_clean_top_level(self):
        d = tempfile.mkdtemp(prefix="layout_multi_")
        p1 = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        p2 = self._write_node(d, "barNode", "BarNode", "0x00081001")
        out = self._assemble([("fooNode", p1), ("barNode", p2)], "duo", d)

        src = os.path.join(out, "build", "source")
        for f in ("fooNode.cpp", "barNode.cpp", "plugin_main.cpp"):
            self.assertTrue(os.path.isfile(os.path.join(src, f)), f)
        for f in ("build.sh", "build.bat", "README.txt"):
            self.assertTrue(os.path.isfile(os.path.join(out, "build", f)), f)
        self.assertEqual(set(os.listdir(out)), {"build"})

    def test_multi_build_sh_paths(self):
        d = tempfile.mkdtemp(prefix="layout_msh_")
        p1 = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        p2 = self._write_node(d, "barNode", "BarNode", "0x00081001")
        out = self._assemble([("fooNode", p1), ("barNode", p2)], "duo", d)
        with open(os.path.join(out, "build", "build.sh")) as fh:
            sh = fh.read()
        self.assertIn("$HERE/source/", sh)                 # inputs from source/
        self.assertIn('-o "$HERE/../duo.bundle"', sh)      # bundle to top level

    # ---- a DROPPED node must not orphan its fragment in source/ ----------
    def test_dropped_node_fragment_not_left_in_source(self):
        # Real-compiler integration: a best-effort multi-node build where one
        # node won't compile. The dropped node's fragment must NOT linger in
        # source/ -- source/ is exactly the bundle's source.
        d = tempfile.mkdtemp(prefix="layout_drop_")
        good = self._write_node(d, "goodNode", "GoodNode", "0x00081000")
        bad = os.path.join(d, "badNode.cpp")
        with open(bad, "w") as fh:
            fh.write(_broken_node_src("badNode", "BadNode", "0x00081001"))
        out = os.path.join(d, "out")
        report = bundler.assemble(
            [("goodNode", good), ("badNode", bad)], "duo", out,
            strict=False, registry=_reg(d), compile_now=True)
        # Skip when this host has no C++ toolchain: then even the good node never
        # reaches the compile step (badNode wouldn't be in 'dropped').
        if not report.get("ok") and "badNode" not in (report.get("dropped") or []):
            self.skipTest("no compiler on this host: %s" % report.get("reason"))
        self.assertIn("badNode", report.get("dropped") or [])
        src = bundler.source_dir_for(out)
        self.assertTrue(os.path.isfile(os.path.join(src, "goodNode.cpp")))
        self.assertFalse(os.path.exists(os.path.join(src, "badNode.cpp")),
                         "dropped node's fragment must be removed from source/")
        # The good node still linked into the bundle at the top level.
        self.assertTrue(report.get("ok"))
        # Platform extension, not a hardcoded ".bundle": the artifact is
        # duo.mll on Windows and duo.so on Linux, so this asserted a file that
        # could never exist there (measured 2026-08-14).
        self.assertTrue(os.path.isfile(
            os.path.join(out, "duo" + toolchain.plugin_ext())))

    # ---- layout helpers are the single source of truth -------------------
    def test_layout_helpers(self):
        self.assertEqual(bundler.build_dir_for("/x/out"),
                         os.path.join("/x/out", "build"))
        self.assertEqual(bundler.source_dir_for("/x/out"),
                         os.path.join("/x/out", "build", "source"))


class TestWindowsBuildScriptFpFlags(unittest.TestCase):
    """Item 1: the generated Windows rebuild scripts must carry the SAME parity
    flags as the in-process compile (_MSVC_CXXFLAGS): /O2 AND an explicit
    /fp:precise, never /fp:fast. A user who hand-runs build.bat must reproduce a
    binary numerically identical to the shipped one; a script missing /O2 (slower)
    or /fp:precise (implicit-default drift) would silently diverge."""

    def test_combined_build_bat_has_o2_and_fp_precise(self):
        bat = bundler.make_build_bat("duo", ["fooNode.cpp", "barNode.cpp"])
        self.assertIn("/O2", bat)
        self.assertIn("/fp:precise", bat)
        self.assertNotIn("/fp:fast", bat)

    def test_single_build_bat_has_o2_and_fp_precise(self):
        bat = bundler.make_single_build_bat("solo", "fooNode.cpp", ["OpenMaya"])
        self.assertIn("/O2", bat)
        self.assertIn("/fp:precise", bat)
        self.assertNotIn("/fp:fast", bat)


class TestCleanWorkingSubdirs(unittest.TestCase):
    """The controller's post-build scratch sweep: drop a built node's
    build/<type>/, keep a dropped node's for debugging, and MIGRATE away any
    pre-reorg top-level out_dir/<type>/ for every node -- never the bundle."""

    def test_sweep_migrates_toplevel_keeps_dropped_buildsubdir(self):
        from mpynode.native.toolchain import compile_controller as cc

        d = tempfile.mkdtemp(prefix="cleanws_")
        # pre-reorg top-level scratch for a built + a dropped node (migration)
        for tn in ("fooBuilt", "barDropped"):
            os.makedirs(os.path.join(d, tn))
        # new-layout scratch under build/ for both
        os.makedirs(os.path.join(d, "build", "fooBuilt"))
        os.makedirs(os.path.join(d, "build", "barDropped"))
        # the importable artifacts must survive
        open(os.path.join(d, "P.bundle"), "w").close()
        open(os.path.join(d, "foo_commands.py"), "w").close()

        rows = [{"type_name": "fooBuilt", "build_status": "compiled"},
                {"type_name": "barDropped", "build_status": "dropped"}]
        cc._clean_working_subdirs(d, rows)

        # top-level scratch swept for BOTH (migration).
        self.assertFalse(os.path.exists(os.path.join(d, "fooBuilt")))
        self.assertFalse(os.path.exists(os.path.join(d, "barDropped")))
        # build/<type>: built removed, dropped kept.
        self.assertFalse(os.path.exists(os.path.join(d, "build", "fooBuilt")))
        self.assertTrue(os.path.exists(os.path.join(d, "build", "barDropped")))
        # bundle + companion untouched.
        self.assertTrue(os.path.exists(os.path.join(d, "P.bundle")))
        self.assertTrue(os.path.exists(os.path.join(d, "foo_commands.py")))


if __name__ == "__main__":
    unittest.main()
