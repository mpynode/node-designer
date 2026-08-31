"""Loading blend-shape targets from files instead of scene meshes.

Covers the reader (``_common/io/shape_files``), the three wrapper entry points
(``add_target_from_offsets`` / ``load_target`` / ``load_shapes``) and the
factory commands seeded onto every mPyBlendShape.

The fixtures are written here rather than read from a corpus so the suite stays
hermetic, but they mirror the two real container shapes exactly: a ``.npz``
stores nested records as flat ``index_3/offsets`` keys, its ``.json`` twin
stores them as real nested objects. Both must decode to the same thing -- that
parity is the reader's whole job.

The load path is deliberately NOT a second implementation. A file's offsets are
RAW ``target - base``, which is exactly what a connected target mesh yields, and
``bake_deltas`` stores both the same way -- verbatim, correctives included. Two
tests pin that (``...is_stored_raw`` and its combo twin), because the bake used
to subtract each corrective's drivers back out of it on the theory that a
corrective sculpt is an absolute pose. It is not: a corrective is sculpted as
the correction itself, so the subtraction removed something that was never
there.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import numpy as np

from tests import _setup
from mpynode.wrappers.mpy_blend_shape import WEIGHT_ATTR


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


def _write_pair(directory, stem, records):
    """``records`` as both containers. Returns ``(npz_path, json_path)``."""
    flat, nested = {}, {}
    for k, rec in enumerate(records):
        flat["index_%d/name" % k] = rec["name"]
        flat["index_%d/indices" % k] = np.asarray(rec["indices"], dtype=np.int64)
        flat["index_%d/offsets" % k] = np.asarray(rec["offsets"],
                                                  dtype=np.float64)
        nested["index_%d" % k] = {
            "name": rec["name"],
            "indices": [int(i) for i in rec["indices"]],
            "offsets": [[float(x) for x in row] for row in rec["offsets"]],
        }
    npz = os.path.join(directory, stem + ".npz")
    jsn = os.path.join(directory, stem + ".json")
    np.savez(npz, **flat)
    with open(jsn, "w") as fh:
        json.dump(nested, fh)
    return npz, jsn


def _write_mesh_pair(directory, stem, name, points, counts, indices):
    npz = os.path.join(directory, stem + ".npz")
    jsn = os.path.join(directory, stem + ".json")
    np.savez(npz, name=name, points=np.asarray(points, dtype=np.float64),
             counts=np.asarray(counts, dtype=np.int64),
             indices=np.asarray(indices, dtype=np.int64))
    with open(jsn, "w") as fh:
        json.dump({"name": name,
                   "points": [[float(x) for x in p] for p in points],
                   "counts": [int(c) for c in counts],
                   "indices": [int(i) for i in indices]}, fh)
    return npz, jsn


class _TmpDir(unittest.TestCase):
    """Per-class scratch directory for the generated fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mpy_bs_loaders_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestShapeFileReaders(_TmpDir):
    RECORDS = [
        {"name": "browUp", "indices": [0, 2], "offsets": [[1, 0, 0], [0, 1, 0]]},
        {"name": "empty", "indices": [], "offsets": []},
        {"name": "mouthOpen", "indices": [1], "offsets": [[0, 0, 3]]},
    ]

    def test_npz_and_json_decode_identically(self):
        from mpynode._common.io import shape_files

        npz, jsn = _write_pair(self.tmp, "pair", self.RECORDS)
        a, b = shape_files.read_shapes(npz), shape_files.read_shapes(jsn)
        self.assertEqual([r["name"] for r in a], [r["name"] for r in b])
        for ra, rb in zip(a, b):
            np.testing.assert_array_equal(ra["indices"], rb["indices"])
            np.testing.assert_allclose(ra["offsets"], rb["offsets"])

    def test_an_empty_record_keeps_its_slot(self):
        """It still owns a weight index and an alias. Dropping it would shift
        every later target -- 88 of the 297 in the reference set are empty."""
        from mpynode._common.io import shape_files

        npz, _ = _write_pair(self.tmp, "withempty", self.RECORDS)
        recs = shape_files.read_shapes(npz)
        self.assertEqual([r["name"] for r in recs],
                         ["browUp", "empty", "mouthOpen"])
        self.assertEqual(recs[1]["indices"].size, 0)
        self.assertEqual(recs[1]["offsets"].shape, (0, 3))

    def test_records_are_ordered_numerically_not_lexicographically(self):
        """``index_10`` sorts after ``index_9``. String ordering would permute
        the stack and re-point every alias onto someone else's deltas."""
        from mpynode._common.io import shape_files

        many = [{"name": "s%d" % i, "indices": [i], "offsets": [[i, 0, 0]]}
                for i in range(12)]
        npz, jsn = _write_pair(self.tmp, "twelve", many)
        for path in (npz, jsn):
            got = [r["name"] for r in shape_files.read_shapes(path)]
            self.assertEqual(got, ["s%d" % i for i in range(12)], path)

    def test_mesh_files_read_in_both_containers(self):
        from mpynode._common.io import shape_files

        pts = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
        npz, jsn = _write_mesh_pair(self.tmp, "quad", "quadMesh", pts, [4],
                                    [0, 1, 2, 3])
        for path in (npz, jsn):
            doc = shape_files.read_mesh(path)
            self.assertEqual(doc["name"], "quadMesh", path)
            self.assertEqual(doc["points"].shape, (4, 3), path)
            np.testing.assert_array_equal(doc["counts"], [4])
            np.testing.assert_array_equal(doc["indices"], [0, 1, 2, 3])

    def test_the_wrong_kind_of_file_is_diagnosed_not_half_read(self):
        from mpynode._common.io import shape_files

        shapes_npz, _ = _write_pair(self.tmp, "kinds", self.RECORDS)
        mesh_npz, _ = _write_mesh_pair(self.tmp, "kindmesh", "m",
                                       [[0, 0, 0]], [1], [0])
        with self.assertRaises(ValueError) as cm:
            shape_files.read_mesh(shapes_npz)
        self.assertIn("expected a MESH file", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            shape_files.read_shapes(mesh_npz)
        self.assertIn("expected a SHAPES file", str(cm.exception))

    def test_an_unknown_extension_is_refused(self):
        from mpynode._common.io import shape_files

        with self.assertRaises(ValueError):
            shape_files.load_document(os.path.join(self.tmp, "x.obj"))

    def test_dense_offsets_drops_out_of_range_ids(self):
        """Clamping would pile a stray delta onto vertex 0."""
        from mpynode._common.io import shape_files

        rec = {"indices": np.array([0, 9]),
               "offsets": np.array([[1.0, 0, 0], [5.0, 0, 0]])}
        dense = shape_files.dense_offsets(rec, 3)
        self.assertEqual(dense.shape, (3, 3))
        np.testing.assert_allclose(dense[0], [1.0, 0, 0])
        self.assertAlmostEqual(float(np.abs(dense[1:]).max()), 0.0)


def _base_rig(node_name, verts=None):
    """A fresh scene with one mPyBlendShape on a small grid, and its points."""
    import maya.cmds as mc
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    mc.file(new=True, force=True)
    base = mc.polyPlane(name=node_name + "Base", sx=1, sy=1, ch=False)[0]
    bs = MPyBlendShape.create(mesh=base, name=node_name)
    return bs, base, bs._base_points()


class TestLoadShapes(_TmpDir):
    def test_every_record_becomes_an_aliased_target(self):
        bs, _base, pts = _base_rig("loadAllBS")
        n = pts.shape[0]
        recs = [{"name": "up", "indices": [0], "offsets": [[0, 1, 0]]},
                {"name": "flat", "indices": [], "offsets": []},
                {"name": "side", "indices": [n - 1], "offsets": [[2, 0, 0]]}]
        npz, _ = _write_pair(self.tmp, "all", recs)

        out = bs.load_shapes(npz)
        self.assertEqual(out["loaded"], 3)
        self.assertEqual(bs.target_names, ["up", "flat", "side"])
        # The empty one occupies its index: offsets[1] == offsets[2].
        ofs = bs._read_multi("targetOffset", int)
        self.assertEqual(len(ofs), 4)
        self.assertEqual(ofs[1], ofs[2])

    def test_weights_are_keyable_so_the_channel_box_lists_them(self):
        import maya.cmds as mc

        bs, _base, _pts = _base_rig("loadKeyBS")
        npz, _ = _write_pair(self.tmp, "key",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        bs.load_shapes(npz)
        self.assertIn(
            "up", mc.listAttr(bs.get_name(), multi=True, keyable=True) or [])
        # The check above is NOT sufficient on its own -- it reports the alias
        # whether or not the parent attribute is keyable, which is exactly how
        # the weights stayed invisible in a real channel box while every gate
        # read green. attributeQuery reads the ATTRIBUTE DEFINITION, which is
        # what Maya actually descends on.
        self.assertTrue(
            mc.attributeQuery(WEIGHT_ATTR, node=bs.get_name(), keyable=True),
            "the weight ATTRIBUTE must be keyable or the channel box lists "
            "nothing, however keyable the individual elements are")

    def test_no_target_geometry_connection_is_made(self):
        """The point of loading from a file: nothing has to stay in the scene."""
        import maya.cmds as mc

        bs, _base, _pts = _base_rig("loadNoConnBS")
        npz, _ = _write_pair(self.tmp, "noconn",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        bs.load_shapes(npz)
        self.assertEqual(
            mc.listConnections("%s.targetGeometry" % bs.get_name(),
                               s=True, d=False) or [], [])

    def test_an_inbetween_offset_is_stored_raw(self):
        """browUp50's stored delta is EXACTLY what the file carried.

        A loaded corrective must behave identically to a sculpted one, and
        neither is reduced: the sculpt already IS the correction. The bake used
        to store ``3.0 - 0.50 * 4.0 == 1.0`` here, which is a shape the artist
        never made.
        """
        bs, _base, pts = _base_rig("loadInterBS")
        main = [[0.0, 4.0, 0.0]]
        inter = [[0.0, 3.0, 0.0]]
        npz, _ = _write_pair(self.tmp, "inter", [
            {"name": "browUp", "indices": [0], "offsets": main},
            {"name": "browUp50", "indices": [0], "offsets": inter}])

        out = bs.load_shapes(npz)
        self.assertEqual(out["inter"], 1)
        ofs = bs._read_multi("targetOffset", int)
        deltas = bs._read_multi("targetDeltas", float)
        stored = deltas[3 * ofs[1]:3 * ofs[2]]
        np.testing.assert_allclose(stored, [0.0, 3.0, 0.0], atol=1e-9)

    def test_a_combo_offset_is_stored_raw(self):
        bs, _base, pts = _base_rig("loadComboBS")
        npz, _ = _write_pair(self.tmp, "combo", [
            {"name": "browUp", "indices": [0], "offsets": [[0.0, 2.0, 0.0]]},
            {"name": "mouthOpen", "indices": [0], "offsets": [[0.0, 0.0, 3.0]]},
            {"name": "browUp_mouthOpen", "indices": [0],
             "offsets": [[1.0, 2.0, 3.0]]}])

        out = bs.load_shapes(npz)
        self.assertEqual(out["combo"], 1)
        ofs = bs._read_multi("targetOffset", int)
        deltas = bs._read_multi("targetDeltas", float)
        stored = deltas[3 * ofs[2]:3 * ofs[3]]
        np.testing.assert_allclose(stored, [1.0, 2.0, 3.0], atol=1e-9)

    def test_a_later_rebuild_does_not_wipe_file_loaded_targets(self):
        """They have no mesh in the scene, so a rebuild that only trusted
        connections would bake them all empty."""
        bs, _base, _pts = _base_rig("loadRebuildBS")
        npz, _ = _write_pair(self.tmp, "rebuild",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        bs.load_shapes(npz)
        before = bs._read_multi("targetDeltas", float)

        bs.rebuild()

        self.assertEqual(bs._read_multi("targetDeltas", float), before)
        self.assertFalse(bs.tables_stale())

    def test_loading_twice_appends_rather_than_replacing(self):
        bs, _base, _pts = _base_rig("loadTwiceBS")
        one, _ = _write_pair(self.tmp, "one",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        two, _ = _write_pair(self.tmp, "two",
                             [{"name": "side", "indices": [1],
                               "offsets": [[1, 0, 0]]}])
        bs.load_shapes(one)
        bs.load_shapes(two)
        self.assertEqual(bs.target_names, ["up", "side"])
        self.assertEqual(len(bs._read_multi("targetComponents", int)), 2)


class TestLoadTarget(_TmpDir):
    def test_a_mesh_form_npz_becomes_one_target(self):
        bs, _base, pts = _base_rig("oneNpzBS")
        moved = pts + np.array([0.0, 5.0, 0.0])
        npz, jsn = _write_mesh_pair(self.tmp, "pushed", "pushedUp", moved,
                                    [4], [0, 1, 2, 3])

        idx = bs.load_target(npz)

        self.assertEqual(idx, 0)
        self.assertEqual(bs.target_names, ["pushedUp"])
        # Every vertex moved by exactly (0, 5, 0).
        deltas = np.asarray(bs._read_multi("targetDeltas", float)).reshape(-1, 3)
        self.assertEqual(deltas.shape[0], pts.shape[0])
        np.testing.assert_allclose(deltas, np.tile([0.0, 5.0, 0.0],
                                                   (pts.shape[0], 1)))

    def test_the_json_twin_gives_the_same_target(self):
        bs, _base, pts = _base_rig("oneJsonBS")
        moved = pts + np.array([0.0, 5.0, 0.0])
        _npz, jsn = _write_mesh_pair(self.tmp, "pushedj", "pushedUp", moved,
                                     [4], [0, 1, 2, 3])
        bs.load_target(jsn)
        deltas = np.asarray(bs._read_multi("targetDeltas", float)).reshape(-1, 3)
        np.testing.assert_allclose(deltas, np.tile([0.0, 5.0, 0.0],
                                                   (pts.shape[0], 1)))

    def test_an_explicit_name_wins_over_the_file_name(self):
        bs, _base, pts = _base_rig("oneNameBS")
        npz, _ = _write_mesh_pair(self.tmp, "named", "fromFile", pts, [4],
                                  [0, 1, 2, 3])
        bs.load_target(npz, name="chosen")
        self.assertEqual(bs.target_names, ["chosen"])

    def test_a_scene_file_is_imported_read_and_removed_again(self):
        import maya.cmds as mc

        bs, base, pts = _base_rig("oneMaBS")
        dup = mc.duplicate(base, name="sculpted")[0]
        mc.setAttr(dup + ".translateY", 3.0)
        mc.makeIdentity(dup, apply=True, t=True)
        mc.select(dup)
        path = mc.file(os.path.join(self.tmp, "sculpted.ma"), force=True,
                       type="mayaAscii", exportSelected=True)
        mc.delete(dup)

        idx = bs.load_target(path, name="fromMa")

        self.assertEqual(idx, 0)
        self.assertEqual(bs.target_names, ["fromMa"])
        deltas = np.asarray(bs._read_multi("targetDeltas", float)).reshape(-1, 3)
        np.testing.assert_allclose(deltas, np.tile([0.0, 3.0, 0.0],
                                                   (pts.shape[0], 1)), atol=1e-6)
        # Nothing left behind: no node, no namespace.
        self.assertFalse(mc.objExists("sculpted"))
        self.assertFalse(mc.namespace(exists="mPyLoadTarget"))

    def test_a_missing_file_is_refused(self):
        bs, _base, _pts = _base_rig("oneMissingBS")
        with self.assertRaises(ValueError):
            bs.load_target(os.path.join(self.tmp, "nope.npz"))


class TestAddTargetFromOffsets(_TmpDir):
    def test_a_sparse_morph_object_can_be_added_directly(self):
        """The arithmetic surface in _api2.morph produces Morphs; this is what
        the module docstring's corrective example ends in."""
        from mpynode._api2.morph import Morph

        bs, _base, _pts = _base_rig("morphAddBS")
        m = Morph(name="corrective", offsets=[[0.0, 7.0, 0.0]], indices=[2])

        idx = bs.add_target_from_offsets(m)

        self.assertEqual(idx, 0)
        self.assertEqual(bs.target_names, ["corrective"])
        self.assertEqual(bs._read_multi("targetComponents", int), [2])
        np.testing.assert_allclose(bs._read_multi("targetDeltas", float),
                                   [0.0, 7.0, 0.0])

    def test_dense_offsets_must_match_the_vertex_count(self):
        bs, _base, _pts = _base_rig("denseBadBS")
        with self.assertRaises(ValueError) as cm:
            bs.add_target_from_offsets(np.zeros((2, 3)), name="bad")
        self.assertIn("dense offsets", str(cm.exception))

    def test_an_out_of_range_vertex_id_is_refused(self):
        bs, _base, pts = _base_rig("sparseBadBS")
        with self.assertRaises(ValueError) as cm:
            bs.add_target_from_offsets([[0.0, 1.0, 0.0]],
                                       indices=[pts.shape[0] + 5], name="bad")
        self.assertIn("outside the base mesh", str(cm.exception))


class TestLoaderErrors(_TmpDir):
    def test_loading_onto_a_node_with_no_geometry_is_an_error(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        mc.file(new=True, force=True)
        bs = MPyBlendShape.create(name="bareBS")
        npz, _ = _write_pair(self.tmp, "bare",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        for call in (lambda: bs.load_shapes(npz),
                     lambda: bs.add_target_from_offsets([[0, 1, 0]],
                                                        indices=[0], name="x")):
            with self.assertRaises(ValueError) as cm:
                call()
            self.assertIn("no geometry attached", str(cm.exception))

    def test_a_file_for_different_geometry_is_an_error(self):
        bs, _base, pts = _base_rig("wrongGeoBS")
        npz, _ = _write_pair(self.tmp, "wrong",
                             [{"name": "up", "indices": [pts.shape[0] + 100],
                               "offsets": [[0, 1, 0]]}])
        with self.assertRaises(ValueError) as cm:
            bs.load_shapes(npz)
        self.assertIn("not for this geometry", str(cm.exception))

    def test_a_failed_load_claims_no_weight_indices(self):
        """Validation runs over the WHOLE file first: a half-applied load would
        leave aliases for shapes the node does not have."""
        import maya.cmds as mc

        bs, _base, pts = _base_rig("atomicBS")
        npz, _ = _write_pair(self.tmp, "atomic", [
            {"name": "good", "indices": [0], "offsets": [[0, 1, 0]]},
            {"name": "bad", "indices": [pts.shape[0] + 100],
             "offsets": [[0, 1, 0]]}])
        with self.assertRaises(ValueError):
            bs.load_shapes(npz)
        self.assertEqual(
            mc.getAttr("%s.weight" % bs.get_name(), multiIndices=True) or [], [])
        self.assertEqual(bs.target_names, [])

    def test_a_mesh_with_the_wrong_vertex_count_is_an_error(self):
        bs, _base, _pts = _base_rig("wrongCountBS")
        npz, _ = _write_mesh_pair(self.tmp, "tiny", "tiny", [[0, 0, 0]], [1],
                                  [0])
        with self.assertRaises(ValueError) as cm:
            bs.load_target(npz)
        self.assertIn("vertices", str(cm.exception))


class TestFactoryCommands(_TmpDir):
    """The mPyBlendShape command TEMPLATES the type offers.

    These three are PLAIN commands, so ``merge_type_default`` deliberately does
    not write them onto the node -- naming them is the user's call, and two node
    types shipping one plain command name is refused at mega-compile. They are
    offered as copy-out templates instead. The behaviour tests below paste them
    in, which is exactly what the Script tab's copy action does.
    """

    NAMES = {"add_targets", "load_target", "load_shapes"}

    def _seeded(self, node_name):
        """A node with the setup merged AND the templates pasted in.

        ``create()`` alone never populates methods source -- the node-creation
        command does it via ``_seed_setup_source``, which is this same call. The
        templates are then appended the way a user copies them out of the
        Commands group.
        """
        from mpynode._common import node_setups
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        bs, base, pts = _base_rig(node_name)
        MPyBlendShape._populate_methods_source(bs)
        pasted = "\n\n".join(
            t.source for t in
            node_setups.command_templates_for_type("mPyBlendShape"))
        cur = bs.get_methods_source() or ""
        bs.set_methods_source((cur + "\n\n" + pasted) if cur.strip() else pasted)
        return bs, base, pts

    def test_the_type_default_carries_all_three(self):
        from mpynode._common import node_setups
        from mpynode._common.methods.maya_command import detect_commands

        src = node_setups.setup_source_for_type("mPyBlendShape")
        self.assertLessEqual(self.NAMES,
                             {c["name"] for c in detect_commands(src)})
        # The setup hook must survive alongside them.
        self.assertIsNotNone(node_setups.find_setup(src))

    def test_no_command_can_reach_an_mpynode_import(self):
        """A command body ships as embedded Python inside the compiled .mll, so
        an mpynode import there raises ModuleNotFoundError wherever the package
        is not installed -- and fails the compile here. The setup's own import
        is invisible only because setup is undecorated; these three must reach
        nothing, which is why they go through ``self``."""
        from mpynode._common import node_setups
        from mpynode._common.methods.maya_command import detect_commands
        from mpynode.native.compiler.kernels import command_dispatch as cd

        src = node_setups.setup_source_for_type("mPyBlendShape")
        self.assertEqual(
            cd.reachable_mpynode_imports(src, detect_commands(src)), [])

    def test_every_command_resolves_to_msyntax_flags(self):
        from mpynode._common import node_setups
        from mpynode._common.methods.maya_command import detect_commands
        from mpynode.native.compiler.kernels import command_dispatch as cd

        src = node_setups.setup_source_for_type("mPyBlendShape")
        for cmd in detect_commands(src):
            if cmd["name"] not in self.NAMES:
                continue
            flags = {f["long"]: f["type"] for f in cd.flag_spec_for(cmd)}
            self.assertTrue(flags, cmd["name"])

    def test_the_compiled_contract_names_the_blend_shape_members(self):
        """A compiled node cannot rebuild its tables (no _computeSource plug),
        so the proxy has to say WHY instead of raising AttributeError."""
        from mpynode.native.compiler.kernels import command_dispatch as cd

        for member in ("add_target", "add_target_from_offsets", "load_target",
                       "load_shapes", "rebuild"):
            self.assertIn(member, cd.COMPILED_UNSUPPORTED)

    def test_a_created_node_carries_none_of_them_but_is_offered_all_three(self):
        """The split: a fresh node gets the setup, NOT the plain commands.

        mPyBlendShape is the only type where that leaves an empty command list,
        because its seed is entirely plain commands (its setup is deliberately
        undecorated -- a create-command body may reach no mpynode import, and
        that setup constructs the wrapper)."""
        from mpynode._common import node_setups
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        bs, _base, _pts = _base_rig("seedCmdBS")
        MPyBlendShape._populate_methods_source(bs)
        self.assertFalse(self.NAMES & {c["name"] for c in bs.list_commands()})
        # ...but the setup hook DID merge, and all three are on offer.
        self.assertIsNotNone(
            node_setups.find_setup(bs.get_methods_source() or ""))
        self.assertEqual(
            self.NAMES,
            {t.name for t in
             node_setups.command_templates_for_type("mPyBlendShape")})

    def test_a_pasted_template_registers_under_its_pinned_name(self):
        """The templates pin ``name=`` so the Maya command name survives the
        ``_cmd`` suffix the def needs to avoid shadowing the wrapper method."""
        bs, _base, _pts = self._seeded("pastedCmdBS")
        got = {c["name"]: c["func_name"] for c in bs.list_commands()}
        self.assertLessEqual(self.NAMES, set(got))
        self.assertEqual(got["load_target"], "load_target_cmd")
        self.assertEqual(got["load_shapes"], "load_shapes_cmd")

    def test_a_create_command_type_still_auto_merges(self):
        """The other side of the split: a ``creates=True`` factory is NOT a
        template -- it merges, so ``cmds.<nodeType>()`` works with no pasting."""
        from mpynode._common import node_setups
        from mpynode._common.methods.maya_command import detect_commands

        for ntype in ("mPyDeformer", "mPyMesh", "mPySkinCluster",
                      "mPyIkSolver", "mPyNurbsCurve", "mPyNurbsSurface"):
            merged = node_setups.merge_type_default("", ntype)
            names = {c["name"] for c in detect_commands(merged) if c["creates"]}
            self.assertTrue(names, "%s lost its create command" % ntype)
            self.assertEqual(
                [], node_setups.command_templates_for_type(ntype),
                "%s should offer no plain-command templates" % ntype)

    def test_add_targets_takes_the_selection_and_aliases_each_mesh(self):
        import maya.cmds as mc

        bs, base, _pts = self._seeded("addSelBS")
        smile = mc.duplicate(base, name="smile")[0]
        frown = mc.duplicate(base, name="frown")[0]
        mc.move(0.0, 1.0, 0.0, smile + ".vtx[0]", relative=True)
        mc.move(0.0, -1.0, 0.0, frown + ".vtx[1]", relative=True)
        mc.select([smile, frown])

        out = bs.call_command("add_targets")

        self.assertEqual(out, ["smile", "frown"])
        self.assertEqual(bs.target_names, ["smile", "frown"])
        # Wired AND baked -- wiring alone deforms nothing.
        self.assertTrue(bs._read_multi("targetComponents", int))
        self.assertLessEqual(
            {"smile", "frown"},
            set(mc.listAttr(bs.get_name(), multi=True, keyable=True) or []))

    def test_add_targets_never_makes_the_node_its_own_target(self):
        import maya.cmds as mc

        bs, base, _pts = self._seeded("addSelfBS")
        dup = mc.duplicate(base, name="shape1")[0]
        mc.select([dup, bs.get_name()])
        self.assertEqual(bs.call_command("add_targets"), ["shape1"])

    def test_add_targets_with_no_meshes_selected_says_so(self):
        import maya.cmds as mc

        bs, _base, _pts = self._seeded("addNoneBS")
        mc.select(clear=True)
        with self.assertRaises(ValueError) as cm:
            bs.call_command("add_targets")
        self.assertIn("select one or more MESHES", str(cm.exception))

    def test_add_targets_accepts_an_explicit_list(self):
        import maya.cmds as mc

        bs, base, _pts = self._seeded("addListBS")
        dup = mc.duplicate(base, name="explicit")[0]
        mc.select(clear=True)
        self.assertEqual(bs.call_command("add_targets", meshes=[dup]),
                         ["explicit"])

    def test_load_shapes_runs_as_a_command(self):
        bs, _base, _pts = self._seeded("cmdLoadShapesBS")
        npz, _ = _write_pair(self.tmp, "cmdshapes",
                             [{"name": "up", "indices": [0],
                               "offsets": [[0, 1, 0]]}])
        out = bs.call_command("load_shapes", npz)
        self.assertEqual(out["loaded"], 1)
        self.assertEqual(bs.target_names, ["up"])

    def test_load_target_runs_as_a_command(self):
        bs, _base, pts = self._seeded("cmdLoadTargetBS")
        npz, _ = _write_mesh_pair(self.tmp, "cmdmesh", "shifted",
                                  pts + np.array([0.0, 2.0, 0.0]), [4],
                                  [0, 1, 2, 3])
        self.assertEqual(bs.call_command("load_target", npz), 0)
        self.assertEqual(bs.target_names, ["shifted"])
        self.assertEqual(bs.call_command("load_target", npz, "renamed"), 1)
        self.assertEqual(bs.target_names, ["shifted", "renamed"])


if __name__ == "__main__":
    unittest.main()
