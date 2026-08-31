"""A geo GENERATOR whose geo INPUT is a DIFFERENT kind than its output must
still include that kind's MFn* header.

``emit_geo._generate_geo_cpp`` keyed its includes on the generator's OUTPUT kind
alone. A SINGLE (non-array) geo input is read by ``emit_attr._read_line`` as
``MFn<Kind> in_<m>`` and ``emit_geo_io.kinds_in_spec`` deliberately skips it (it
needs no ``Nd<Kind>`` struct), so an mPyNurbsCurve with a mesh input emitted
``MFnMesh in_aSrc(...)`` with no ``maya/MFnMesh.h`` -- the frag could not compile.

Structural only (no toolchain needed): assert that every ``MFn<Kind>`` the
emitted source actually names has its header in the include block.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# generator node type -> the attr its compute fills.
_GENERATORS = {
    "mPyMesh": "mesh",
    "mPyNurbsCurve": "curve",
    "mPyNurbsSurface": "surface",
}

# geo INPUT attr type -> (C++ function set, its header)
_GEO_INPUTS = {
    "mesh": ("MFnMesh", "maya/MFnMesh.h"),
    "nurbsCurve": ("MFnNurbsCurve", "maya/MFnNurbsCurve.h"),
    "nurbsSurface": ("MFnNurbsSurface", "maya/MFnNurbsSurface.h"),
}


def _generate(node_type, in_type):
    import maya.cmds as mc
    import mpynode
    from mpynode.native import compiler as codegen
    from mpynode.native.spec import spec_extractor

    mc.file(new=True, force=True)
    n = mc.createNode(node_type, name="crossKindGen")
    w = mpynode.wrap_node(n)
    w.add_input_attr("src", in_type)
    # Not lowerable -> the AI-porter PORT region is kept, which is exactly the
    # path that emits the bare `MFn<Kind> in_src` read.
    w.set_compute_expression("pass\n")
    return codegen.generate_cpp(spec_extractor.extract_spec(n), for_port=True)


class TestGeoGeneratorCrossKindIncludes(unittest.TestCase):

    def test_every_named_function_set_has_its_header(self):
        for node_type in sorted(_GENERATORS):
            for in_type, (fn, header) in sorted(_GEO_INPUTS.items()):
                with self.subTest(node_type=node_type, in_type=in_type):
                    cpp = _generate(node_type, in_type)
                    self.assertIn(
                        "%s in_aSrc(" % fn, cpp,
                        "%s: the %s input read was not emitted at all"
                        % (node_type, in_type))
                    self.assertIn(
                        "#include <%s>" % header, cpp,
                        "%s emits %s for its %s input but never includes %s"
                        % (node_type, fn, in_type, header))


if __name__ == "__main__":
    unittest.main()
