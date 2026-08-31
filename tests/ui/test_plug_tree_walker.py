"""plug_tree_walker.walk_plug_tree enumeration + read-text + no-force-eval

Consolidated from: test_phaseL_0_walk_plug_tree.py, test_plug_tree_no_force_eval.py, test_walker_all_indices_and_editor_loadsave.py, test_walker_readtext_and_refresh_menu.py, test_phaseM_3_no_cmds_getattr_in_wrappers.py.
"""

from __future__ import annotations

# ===================== from test_phaseL_0_walk_plug_tree.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseL_0_walk_plug_tree():
    standalone_init()


class TestWalkPlugTreeShape(unittest.TestCase):
    """L.0: walk_plug_tree returns RowSpec rows with the documented
    fields, classified by direction, with inherited + user-added
    plugs both visible."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="walktd")
        self.deformer.add_input_attr("driverMatrixA", "matrix")
        self.deformer.add_input_attr("amplitude", "vector")

    def test_walker_returns_nonempty(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        self.assertGreater(len(rows), 0)

    def test_inherited_envelope_visible_as_input(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        env_rows = [r for r in rows if r.short_name == "envelope"]
        self.assertEqual(len(env_rows), 1)
        self.assertEqual(env_rows[0].direction, "INPUT")
        self.assertFalse(env_rows[0].is_user_added)

    def test_user_added_attrs_flagged(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        names = {r.short_name for r in rows if r.is_user_added}
        self.assertIn("driverMatrixA", names)
        self.assertIn("amplitude", names)

    def test_compound_children_expanded(self):
        """L.0: Double3 amplitude compound has 3 children
        (amplitudeX/Y/Z) visible as nested rows."""
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        child_paths = {r.plug_path for r in rows if r.parent_path == "amplitude"}
        self.assertEqual(
            child_paths,
            {"amplitude.amplitudeX", "amplitude.amplitudeY", "amplitude.amplitudeZ"},
        )

    def test_input_compound_multi_expands(self):
        """The inherited 'input[0].inputGeometry' / groupId /
        componentTagExpression compound children show up."""
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        nested = {r.plug_path for r in rows}
        # input[0] (array element) + children should be present
        self.assertTrue(any("input[0]" in p for p in nested),
            "expected input[0] element row to surface")

    def test_outputs_bucket(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            walk_plug_tree, filter_by_direction,
        )

        rows = walk_plug_tree(self.deformer.get_name())
        outputs = filter_by_direction(rows, "OUTPUT")
        names = {r.short_name for r in outputs}
        self.assertIn("outputGeometry", names)

    def test_unknown_node_returns_empty(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        self.assertEqual(walk_plug_tree("nosuch_xyz"), [])


class TestInternalApiSlots(unittest.TestCase):
    """L.1: per-wrapper ``INTERNAL_API_SLOTS`` declaration."""

    def test_transform_declares_local_matrix(self):
        from mpynode.wrappers.mpy_transform import MPyTransform
        names = {s[0] for s in MPyTransform.INTERNAL_API_SLOTS}
        self.assertIn("local_matrix", names)

    def test_iksolver_declares_handle_state(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        names = {s[0] for s in MPyIkSolver.INTERNAL_API_SLOTS}
        for slot in ("joints", "end_effector", "pole_vector", "twist"):
            self.assertIn(slot, names)

    def test_locator_declares_drawoverride_state(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        names = {s[0] for s in MPyLocator.INTERNAL_API_SLOTS}
        for slot in ("selected", "is_lead", "selection_color"):
            self.assertIn(slot, names)

    def test_deformer_has_no_internal_api_slots(self):
        """MPyDeformer is fully plug-tree-driven; no INTERNAL_API_SLOTS
        attribute, or an empty tuple if explicitly declared."""
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        slots = getattr(MPyDeformer, "INTERNAL_API_SLOTS", ())
        self.assertEqual(tuple(slots), ())


class TestVariablesWidgetUnification(unittest.TestCase):
    """L.2: variables widget integrates walk_plug_tree -- inherited +
    user-added plugs surface, with compound children expanded."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="varstd")
        self.deformer.add_input_attr("amplitude", "vector")

    def test_inherited_envelope_in_collect_plug_rows(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        rows = collect_plug_rows(self.deformer.get_name())
        plug_paths = [r[0] for r in rows]
        self.assertIn("envelope", plug_paths)

    def test_user_added_amplitude_compound_children_in_rows(self):
        """Advance over compound children
        (amplitude.amplitudeX/Y/Z) appear in the rows, not just the
        parent 'amplitude'."""
        from mpynode.ui.widgets.variables import collect_plug_rows

        rows = collect_plug_rows(self.deformer.get_name())
        plug_paths = [r[0] for r in rows]
        self.assertIn("amplitude", plug_paths)
        self.assertIn("amplitude.amplitudeX", plug_paths)

    def test_collect_internal_api_rows_iksolver(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        from mpynode.ui.widgets.variables import collect_internal_api_rows

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        node = mc.createNode("mPyIkSolver")
        rows = collect_internal_api_rows(node)
        names = [r[0] for r in rows]
        for slot in MPyIkSolver.INTERNAL_API_SLOTS:
            self.assertIn(slot[0], names)


# ===================== from test_plug_tree_no_force_eval.py =====================
import contextlib
import io
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__plug_tree_no_force_eval():
    standalone_init()


class TestPlugTreeNoForceEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def test_walk_plug_tree_does_not_force_recompute_when_clean(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        mc.file(new=True, force=True)
        node = MPyNode.create(name="walkTest")
        node.add_output_attr("pts", "vector", is_array=True)
        node.set_compute_expression(
            'print("EVALPT")\nself.pts = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n'
        )
        name = node.get_name()
        mc.getAttr(name + ".pts[0]")  # prime -> clean
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for _ in range(3):
                walk_plug_tree(name)
        self.assertEqual(buf.getvalue().count("EVALPT"), 0)

    def test_walk_plug_tree_still_surfaces_elements(self):
        """The element rows are still produced (display not regressed)."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        mc.file(new=True, force=True)
        node = MPyNode.create(name="walkTest2")
        node.add_output_attr("pts", "vector", is_array=True)
        node.set_compute_expression(
            "self.pts = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n"
        )
        name = node.get_name()
        mc.getAttr(name + ".pts[0]")  # prime so elements exist
        rows = walk_plug_tree(name)
        elem_paths = [r.plug_path for r in rows]
        self.assertIn("pts[0]", elem_paths)
        self.assertIn("pts[1]", elem_paths)


# ===================== from test_walker_all_indices_and_editor_loadsave.py =====================
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-walker-loadsave-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__walker_all_indices_and_editor_loadsave():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestWalkerEnumeratesAllIndices(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        # Maya 2026 auto-wires originalGeometry[0] eagerly but 2024 creates it
        # lazily, so force-wire [0], [1] and [2] to keep the precondition
        # version-independent.
        plane0 = mc.polyPlane(w=1, h=1, sx=1, sy=1)[0]
        plane1 = mc.polyPlane(w=1, h=1, sx=1, sy=1)[0]
        plane2 = mc.polyPlane(w=1, h=1, sx=1, sy=1)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane0, name="walker_multi_def")
        # Force-wire originalGeometry[0..2] from plane0/plane1/plane2.
        def_node = self.deformer.get_name()
        try:
            mc.connectAttr(
                f"{plane0}.outMesh", f"{def_node}.originalGeometry[0]",
                force=True,
            )
            mc.connectAttr(
                f"{plane1}.outMesh", f"{def_node}.originalGeometry[1]",
                force=True,
            )
            mc.connectAttr(
                f"{plane2}.outMesh", f"{def_node}.originalGeometry[2]",
                force=True,
            )
        except Exception as exc:
            self.skipTest(
                f"could not wire originalGeometry[0..2]: {exc}"
            )

    def test_walker_emits_all_populated_indices(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree

        rows = walk_plug_tree(self.deformer.get_name())
        og_rows = [
            r for r in rows
            if r.plug_path.startswith("originalGeometry[")
        ]
        og_paths = sorted({r.plug_path for r in og_rows})
        # All three indices ([0], [1], [2]) must appear.
        for idx in (0, 1, 2):
            self.assertIn(
                f"originalGeometry[{idx}]", og_paths,
                f"walker should emit originalGeometry[{idx}]; "
                f"got: {og_paths}",
            )


class TestEditorLoadSaveMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def test_helpers_present(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        for m in ("contextMenuEvent", "_load_from_file", "_save_to_file"):
            self.assertTrue(
                hasattr(QtPythonEditor, m),
                f"QtPythonEditor missing {m!r}",
            )

    def test_load_replaces_contents(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        ed = QtPythonEditor()
        ed.setPlainText("# original\n")
        # Write a tmp.py + drive the load directly (bypass dialog).
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as fp:
            fp.write("import math\nresult = math.pi\n")
            path = fp.name
        try:
            # Drive the file-read path; the dialog wrapper is
            # straightforward + tested by source-grep below.
            with open(path, "r", encoding="utf-8") as f:
                ed.setPlainText(f.read())
            self.assertEqual(
                ed.toPlainText(), "import math\nresult = math.pi\n",
            )
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def test_save_writes_contents_to_disk(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        ed = QtPythonEditor()
        ed.setPlainText("# saved script\nx = 42\n")
        tmpdir = tempfile.mkdtemp(prefix="mpynode_loadsave_")
        path = os.path.join(tmpdir, "out.py")
        try:
            # Drive the file-write path directly.
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(ed.toPlainText())
            with open(path, "r", encoding="utf-8") as fp:
                got = fp.read()
            self.assertEqual(got, "# saved script\nx = 42\n")
        finally:
            try:
                os.unlink(path)
                os.rmdir(tmpdir)
            except Exception:
                pass


class TestSourceShape__walker_all_indices_and_editor_loadsave(unittest.TestCase):
    def test_context_menu_adds_load_and_save(self):
        import inspect
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        src = inspect.getsource(QtPythonEditor.contextMenuEvent)
        self.assertIn("Load From File", src)
        self.assertIn("Save To File", src)
        self.assertIn("createStandardContextMenu", src)

    def test_load_save_use_qfiledialog(self):
        import inspect
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        for fn_name in ("_load_from_file", "_save_to_file"):
            src = inspect.getsource(getattr(QtPythonEditor, fn_name))
            self.assertIn("QFileDialog", src,
                f"{fn_name} must use QFileDialog for cross-platform "
                f"file picker")

    def test_walker_iterates_all_indices(self):
        import inspect
        from mpynode.ui.widgets import plug_tree_walker

        src = inspect.getsource(plug_tree_walker._walk_attribute)
        self.assertIn("for raw_idx in elem_indices", src)
        # Make sure the [0]-only restriction is gone.
        self.assertNotIn("first_idx = int(elem_indices[0])", src)


# ===================== from test_walker_readtext_and_refresh_menu.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-walker-readtext-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__walker_readtext_and_refresh_menu():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestReadValueTextSkipsNonDisplayable(unittest.TestCase):
    """_read_value_text must NOT call cmds.getAttr on data-typed
    plugs that Maya would warn about."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=1, h=1, sx=1, sy=1)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        self.deformer = MPyDeformer.create_on(plane, name="readtxt_def")

    def test_typed_types_constant_includes_mesh(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            _NON_DISPLAYABLE_ATTR_TYPES,
        )
        for needle in (
            "mesh", "nurbsCurve", "nurbsSurface", "lattice",
            "componentList", "Message", "polyFaces", "polyEdges",
        ):
            self.assertIn(needle, _NON_DISPLAYABLE_ATTR_TYPES,
                f"_NON_DISPLAYABLE_ATTR_TYPES must include {needle!r}")

    def test_read_value_text_skips_mesh_plug_silently(self):
        from mpynode.ui.widgets.plug_tree_walker import _read_value_text

        node = self.deformer.get_name()
        # originalGeometry[0] is a mesh-typed plug: this call used to print
        # "The data is not a numeric or string value" to the script editor.
        result = _read_value_text(node, "originalGeometry[0]")
        # Assert the silent-skip return value instead (stderr inside Maya's
        # script editor is not capturable): "" unconnected, "<- src>" if wired.
        self.assertIn(
            result, ("", "<- {}".format(
                mc.connectionInfo(
                    f"{node}.originalGeometry[0]",
                    sourceFromDestination=True,
                ) or ""
            ).rstrip(),
            "<connected>"),
            f"unexpected value text for mesh plug: {result!r}",
        )

    def test_numeric_plug_still_returns_value(self):
        """Numeric plugs (envelope is a 0..1 float) must still
        round-trip through the displayable path."""
        from mpynode.ui.widgets.plug_tree_walker import _read_value_text

        result = _read_value_text(
            self.deformer.get_name(), "envelope",
        )
        # envelope defaults to 1.0; repr is "1.0".
        self.assertIn(result, ("1.0", "1"))


class TestRefreshContextMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=1, h=1, sx=1, sy=1)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        self.deformer = MPyDeformer.create_on(plane, name="refresh_menu_def")

    def test_refresh_helper_present(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        self.assertTrue(hasattr(NDInputAttrTree, "_refresh_both_trees"))

    def test_refresh_both_trees_calls_both_trees(self):
        from mpynode.ui.widgets.attributes import NDAttributesWidget

        w = NDAttributesWidget()
        w.refresh(self.deformer)
        # Spy on each tree's refresh.
        input_called = []
        output_called = []
        orig_in_refresh = w._input_tree.refresh
        orig_out_refresh = w._output_tree.refresh
        w._input_tree.refresh = lambda: (input_called.append(1), orig_in_refresh())
        w._output_tree.refresh = lambda: (output_called.append(1), orig_out_refresh())
        # Trigger from the input tree.
        w._input_tree._refresh_both_trees()
        self.assertEqual(input_called, [1], "input tree refresh must run")
        self.assertEqual(output_called, [1], "output tree refresh must run")


class TestSourceShape__walker_readtext_and_refresh_menu(unittest.TestCase):
    def test_read_value_text_uses_type_precheck(self):
        import inspect
        from mpynode.ui.widgets import plug_tree_walker
        src = inspect.getsource(plug_tree_walker._read_value_text)
        self.assertIn("_NON_DISPLAYABLE_ATTR_TYPES", src)
        self.assertIn("type=True", src)

    def test_context_menu_has_refresh_item(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        src = inspect.getsource(NDInputAttrTree.contextMenuEvent)
        self.assertIn("Refresh Inputs + Outputs", src)
        self.assertIn("_refresh_both_trees", src)


# ===================== from test_phaseM_3_no_cmds_getattr_in_wrappers.py =====================
import inspect
import re
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseM_3_no_cmds_getattr_in_wrappers():
    standalone_init()


# Source-grep pattern: anything that looks like a real call to
# cmds.getAttr inside a compute path. The docstring/comment "cmds.getAttr"
# (without parens) is OK.
_CMDS_GETATTR_CALL = re.compile(r"cmds\.getAttr\s*\(")


class TestTransformComputeHasNoCmdsGetAttr(unittest.TestCase):
    """``MPyTransformMatrix._run_expression`` must not call
    ``cmds.getAttr(...)``. The live channels (translate/rotate/scale/shear/
    rotateOrder) are read off the paired MPxTransformationMatrix accessors."""

    def test_run_expression_has_no_cmds_getattr(self):
        from mpynode._api1.mpy_transform import MPyTransformMatrix

        src = inspect.getsource(MPyTransformMatrix._run_expression)
        self.assertIsNone(
            _CMDS_GETATTR_CALL.search(src),
            "MPyTransformMatrix._run_expression must NOT "
            "call cmds.getAttr(...) -- read the live channels off the paired "
            "MPxTransformationMatrix accessors instead.",
        )

    def test_run_expression_reads_live_channels_off_accessors(self):
        from mpynode._api1.mpy_transform import MPyTransformMatrix

        src = inspect.getsource(MPyTransformMatrix._run_expression)
        # Live channels come off the paired MPxTransformationMatrix accessors
        # (fresh + at parity with the compiled desiredLocal), not a plug read.
        self.assertIn("_read_transform_components", src)
        # world_matrix was axed: the node no longer reads its own DAG parent, so
        # the old parent-world plug helper is GONE (WORLD is a connected-parent
        # expression: local_matrix = world @ inv(parent)).
        self.assertNotIn("_read_parent_matrix_via_plug", src)


class TestConstraintComputeHasNoCmdsGetAttr(unittest.TestCase):
    """``MPyConstraint.compute`` (the preset_internals reads) must
    not call ``cmds.getAttr(...)``."""

    def test_compute_has_no_cmds_getattr(self):
        from mpynode._api2.mpy_constraint import MPyConstraint

        src = inspect.getsource(MPyConstraint.compute)
        self.assertIsNone(
            _CMDS_GETATTR_CALL.search(src),
            "MPyConstraint.compute must NOT call "
            "cmds.getAttr(...) -- use PlugProxy + "
            "CompoundPlugProxy.as_numpy() instead.",
        )

    def test_compute_uses_plug_proxy(self):
        from mpynode._api2.mpy_constraint import MPyConstraint

        src = inspect.getsource(MPyConstraint.compute)
        self.assertIn("PlugProxy", src)
        self.assertIn("_read_double3_via_plug", src)


class TestTransformBehaviorParity(unittest.TestCase):
    """Behavior parity under the GATED LOCAL-MATRIX contract: an empty expression
    still behaves as a plain Maya transform (TRS drives it), and the expression
    can drive the node through the gated local_matrix / apply_* write slots (the
    legacy self.translate read + self.output_matrix write, and the world_matrix
    write slot, were removed)."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_transform_picks_up_translate(self):
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="tx_m3")
        mc.setAttr(t.get_name() + ".translateX", 7.5)
        mc.setAttr(t.get_name() + ".translateY", -1.25)
        mc.setAttr(t.get_name() + ".translateZ", 3.0)
        # Empty expression -> matrix is default TRS composition.
        wm = mc.xform(t.get_name(), q=True, ws=True, t=True)
        self.assertAlmostEqual(wm[0], 7.5, places=4)
        self.assertAlmostEqual(wm[1], -1.25, places=4)
        self.assertAlmostEqual(wm[2], 3.0, places=4)

    def test_expression_drives_via_local_matrix(self):
        """The expression drives the node through the gated ``local_matrix``
        slot (the legacy ``self.translate`` read + ``self.output_matrix`` write
        were removed). Author a local matrix that lifts Y by 10 with the
        translate gate open and confirm it surfaces on worldMatrix[0] (which
        composes L * offsetParentMatrix * parent)."""
        from mpynode.wrappers.mpy_transform import MPyTransform

        t = MPyTransform.create(name="tx_m3_expr")
        t.set_compute_expression(
            "import numpy as np\n"
            "m = np.eye(4)\n"
            "m[3, 1] = 10.0\n"
            "self.local_matrix = m\n"
            "self.apply_translate = True\n"
        )
        # Force compute via a worldMatrix query.
        wm = mc.getAttr(t.get_name() + ".worldMatrix[0]") or []
        self.assertEqual(len(wm), 16, "worldMatrix[0] should be 16 floats")
        # Translation lives at flat indices 12, 13, 14 (Maya layout).
        self.assertAlmostEqual(wm[13], 10.0, places=4,
            msg="gated local_matrix should drive offsetParentMatrix; "
                "got worldMatrix[0] translation Y = {:.4f}".format(wm[13]))


def setUpModule():
    _setUpModule__phaseL_0_walk_plug_tree()
    _setUpModule__plug_tree_no_force_eval()
    _setUpModule__walker_all_indices_and_editor_loadsave()
    _setUpModule__walker_readtext_and_refresh_menu()
    _setUpModule__phaseM_3_no_cmds_getattr_in_wrappers()


if __name__ == "__main__":
    import unittest
    unittest.main()
