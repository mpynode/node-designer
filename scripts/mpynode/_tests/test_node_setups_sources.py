# scripts/mpynode/_tests/test_node_setups_sources.py  (pure -- no setUpModule)
import ast
import os
import unittest
from mpynode._common import node_setups as ns
from mpynode._common.methods.methods_registry import build_methods_namespace

SETUP_TYPES = ["mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface", "mPyFile",
               "mPyDeformer", "mPySkinCluster", "mPyBlendShape", "mPyIkSolver"]


class TestAuthoredSetupSources(unittest.TestCase):
    def test_each_source_exists_and_gates(self):
        for t in SETUP_TYPES:
            src = ns.setup_source_for_type(t)
            self.assertIsNotNone(src, "missing setup source for %s" % t)
            self.assertIsNotNone(ns.find_setup(src), "%s not a self-first def" % t)

    def test_each_source_execs_to_callable_setup(self):
        for t in SETUP_TYPES:
            obj = build_methods_namespace(ns.setup_source_for_type(t)).get("setup")
            self.assertTrue(callable(obj) or isinstance(obj, classmethod),
                            "%s setup did not exec to a callable" % t)


class TestSkinClusterWireJointsVendoring(unittest.TestCase):
    """mPySkinCluster's setup carries a hand-copied ``_wire_joints`` instead of
    importing ``MPySkinCluster._wire_joints``: the setup body is a create command
    and ships as embedded Python inside a compiled ``.mll``, which must run on a
    machine that has Maya but NOT mpynode. So the copy is deliberate and these
    two tests are the only thing keeping it honest.
    """

    def _wire_joints(self, src):
        """(arg names, AST dump of the body sans docstring) for the first
        ``_wire_joints`` def in ``src``, or None."""
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.FunctionDef) and node.name == "_wire_joints":
                body = node.body
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                return ([a.arg for a in node.args.args],
                        ast.dump(ast.Module(body=body, type_ignores=[])))
        return None

    def test_vendored_copy_matches_the_wrapper(self):
        # Resolve the wrapper through the SAME tree the setup source came from,
        # so a stale installed mpynode can't make this compare two repos.
        root = ns.find_setups_root()
        self.assertIsNotNone(root, "could not locate node_setups/")
        wrapper_path = os.path.join(root, os.pardir, os.pardir, "wrappers",
                                    "mpy_skin_cluster.py")
        with open(wrapper_path) as fh:
            ref = self._wire_joints(fh.read())
        copy = self._wire_joints(ns.setup_source_for_type("mPySkinCluster"))
        self.assertIsNotNone(ref, "MPySkinCluster._wire_joints not found")
        self.assertIsNotNone(copy,
                             "node_setups/mPySkinCluster.py lost _wire_joints")
        self.assertEqual(
            ref, copy,
            "node_setups/mPySkinCluster.py::_wire_joints has drifted from "
            "MPySkinCluster._wire_joints -- re-copy the body. Do NOT fix this "
            "by importing the wrapper: the setup ships as embedded Python in a "
            "compiled .mll and must run without mpynode installed.")

    def test_the_setup_imports_no_mpynode(self):
        # AST, not a substring scan: the file NAMES mpynode in its comments.
        tree = ast.parse(ns.setup_source_for_type("mPySkinCluster"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
        offenders = [m for m in modules
                     if m == "mpynode" or m.startswith("mpynode.")]
        self.assertEqual(
            offenders, [],
            "the mPySkinCluster setup ships inside a compiled .mll and must "
            "import nothing from mpynode; found %r" % (offenders,))


if __name__ == "__main__":
    unittest.main()
