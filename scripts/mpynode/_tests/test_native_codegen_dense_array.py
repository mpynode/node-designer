"""Native codegen: DENSE gap-filled array INPUT reads + the ``sparse`` opt-out.

Mirrors the interpreted read change (``_api2.helpers.read_user_inputs_dict`` now
returns a dense ``max_logical+1`` array, gaps filled with the attribute default).
The generated C++ array read now does the same by default: scatter existing
elements to their logical index (``elementIndex()``), growing the vector to
``max_logical+1`` with gaps pre-filled by the per-type default (matrix=identity,
vector/euler=zero, numeric=addAttr dv). A per-input ``sparse=True`` flag keeps
the legacy compact (physical, connection-order) read.

Universal scope: dense is the DEFAULT for every node family (both the generic
compute() path and the deformer deform() path). The inherited skinCluster
joint-matrix reader (``_matrix_array_read``) is intentionally NOT covered -- it
is a Maya-native multi with no user meta / sparse flag.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _member(attr_type, *, member="myarr", sparse=False, default_value=None):
    meta = {"type": attr_type, "is_array": True}
    if sparse:
        meta["sparse"] = True
    if default_value is not None:
        meta["default_value"] = default_value
    return {"plug": member, "member": member, "kind": "inputs", "meta": meta}


class TestArrayGapDefaultCpp(unittest.TestCase):
    """Per-type C++ gap-fill literal mirrors _api2.helpers.array_gap_default."""

    def _d(self, attr_type, **kw):
        from mpynode.native import compiler as codegen

        return codegen._array_gap_default_cpp(
            dict(type=attr_type, **kw)
        )

    def test_matrix_is_identity(self):
        self.assertEqual(self._d("matrix"), "MMatrix()")

    def test_vector_and_euler_are_zero(self):
        self.assertEqual(self._d("vector"), "MVector()")
        self.assertEqual(self._d("euler"), "MVector()")

    def test_numeric_uses_addattr_dv(self):
        self.assertEqual(self._d("float", default_value=5.0), "5.0")
        self.assertEqual(self._d("int", default_value=7), "7")

    def test_numeric_fallbacks_to_zero(self):
        self.assertEqual(self._d("float"), "0.0")
        self.assertEqual(self._d("int"), "0")

    def test_bool_enum_time(self):
        self.assertEqual(self._d("bool"), "false")
        self.assertEqual(self._d("enum"), "0")
        self.assertEqual(self._d("time"), "0.0")

    def test_angle_radians_default(self):
        # angle dv is recorded (radians); fallback zero.
        self.assertEqual(self._d("angle"), "0.0")


class TestArrayReadLinesDense(unittest.TestCase):
    """_array_read_lines emits a dense logical-index read by default."""

    def _cpp(self, *a, **kw):
        from mpynode.native import compiler as codegen

        return "\n".join(codegen._array_read_lines(*a, **kw))

    def test_float_dense_default(self):
        cpp = self._cpp(_member("float"))
        self.assertIn("_arr.elementIndex()", cpp)
        self.assertIn("in_myarr.resize(_li + 1, 0.0)", cpp)
        self.assertIn("in_myarr[_li] = eh.asFloat();", cpp)
        self.assertNotIn("push_back", cpp)

    def test_float_dense_custom_dv(self):
        cpp = self._cpp(_member("float", default_value=5.0))
        self.assertIn("in_myarr.resize(_li + 1, 5.0)", cpp)

    def test_matrix_dense_identity_gap(self):
        cpp = self._cpp(_member("matrix"))
        self.assertIn("in_myarr.resize(_li + 1, MMatrix())", cpp)
        self.assertIn("in_myarr[_li] = eh.asMatrix();", cpp)

    def test_vector_dense_zero_gap(self):
        cpp = self._cpp(_member("vector"))
        self.assertIn("in_myarr.resize(_li + 1, MVector())", cpp)

    def test_sparse_keeps_compact(self):
        cpp = self._cpp(_member("float", sparse=True))
        self.assertIn("in_myarr.push_back(eh.asFloat());", cpp)
        self.assertNotIn("elementIndex", cpp)
        self.assertNotIn("resize", cpp)

    def test_deform_src_block_is_dense_too(self):
        cpp = self._cpp(_member("float"), src="block")
        self.assertIn("block.inputArrayValue(myarr)", cpp)
        self.assertIn("_arr.elementIndex()", cpp)


class TestNormalizeAttrPropagatesSparse(unittest.TestCase):
    """The single spec chokepoint must carry sparse through to codegen."""

    def test_sparse_true_survives(self):
        from mpynode.native.spec import spec_extractor

        out = spec_extractor.normalize_attr(
            {"attr_type": "float", "is_array": True, "sparse": True}
        )
        self.assertIs(out.get("sparse"), True)

    def test_dense_has_no_sparse_key(self):
        from mpynode.native.spec import spec_extractor

        out = spec_extractor.normalize_attr(
            {"attr_type": "float", "is_array": True}
        )
        self.assertNotIn("sparse", out)


class TestGenerateCppEndToEnd(unittest.TestCase):
    """Through extract_spec -> generate_cpp: dense by default, compact if sparse."""

    def _spec(self, *, sparse=False):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="denseSrc#")
        w.add_input_attr("arr", "float", is_array=True, sparse=sparse)
        w.add_output_attr("o", "float")
        w.set_compute_expression("self.o = float(self.arr[0])")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "denseTestNode"
        return spec

    def test_dense_array_input_generates_logical_read(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("_arr.elementIndex()", cpp)
        self.assertIn(".resize(_li + 1,", cpp)

    def test_sparse_array_input_generates_compact_read(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self._spec(sparse=True), for_port=True)
        self.assertIn("push_back(eh.asFloat());", cpp)
        self.assertNotIn("elementIndex", cpp)


if __name__ == "__main__":
    unittest.main()
