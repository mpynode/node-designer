"""The mPyBlendShape ``self.morphs`` object surface (Stages 1 + 2).

Three layers, all Maya-standalone only (no compiler needed):

  * ``TestMorphKernels``   -- the Maya-free math in ``_common/methods/morph_blend``
  * ``TestMorphInterface`` -- the blessed METHOD / PROPERTY registry contract, and
    the cross-module invariants a drift would silently break
  * ``TestMorphDesugar``   -- ``nd_lower._rewrite_morph_reads``: every recognised
    form rewrites to the exact blessed call, every other form honest-rejects
  * ``TestMorphStackLive`` -- the object on a REAL node: authoring names + search,
    the compute surface, and interpreted/compiled agreement of the deform

The load-bearing idea is that ``MorphStack`` is a Python-side affordance the
transpiler never sees -- the codegen rewrites it into blessed method calls that
transpile the SAME numpy kernel the interpreted object runs. So the tests that
matter most are the ones pinning those two halves together: the desugar targets
(``TestMorphDesugar``) and the reads ORDER (``TestMorphInterface``), because a
drift in either produces a node that runs and silently deforms wrong.
"""
from __future__ import annotations

import unittest

import numpy as np

from tests import _setup


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


# ===========================================================================
# 1. the Maya-free kernels
# ===========================================================================
class TestMorphKernels(unittest.TestCase):
    def setUp(self):
        from mpynode._common.methods import morph_blend
        self.mb   = morph_blend
        self.base = np.zeros((5, 3))
        self.ofs  = np.array([0, 2, 3], dtype=np.int64)
        self.comp = np.array([0, 1, 4], dtype=np.int64)
        self.dlt  = np.array([1., 0., 0., 0., 2., 0., 0., 0., 3.])

    def test_accumulate_scales_each_target_by_its_weight(self):
        d = self.mb.accumulate_deltas(
            self.base, np.array([1.0, 0.0]), self.ofs, self.comp, self.dlt)
        self.assertTrue(np.allclose(d[0], [1., 0., 0.]))
        self.assertTrue(np.allclose(d[1], [0., 2., 0.]))
        self.assertTrue(np.allclose(d[4], [0., 0., 0.]))

    def test_targets_ADD_rather_than_overwrite(self):
        d = self.mb.accumulate_deltas(
            self.base, np.array([1.0, 1.0]), self.ofs, self.comp, self.dlt)
        self.assertTrue(np.allclose(d[4], [0., 0., 3.]))
        self.assertTrue(np.allclose(d[0], [1., 0., 0.]))

    def test_a_weight_past_the_table_is_a_noop_not_an_OOB(self):
        # compiled, nd::at1_ref does NO bounds checking, so an unclamped read
        # is a silent heap write, not an IndexError.
        d = self.mb.accumulate_deltas(
            self.base, np.array([0.0, 0.0, 1.0, 1.0]),
            self.ofs, self.comp, self.dlt)
        self.assertTrue(np.allclose(d, 0.0))

    def test_a_vertex_id_past_the_mesh_is_clamped_away(self):
        comp = np.array([0, 99, 4], dtype=np.int64)
        d = self.mb.accumulate_deltas(
            self.base, np.array([1.0, 0.0]), self.ofs, comp, self.dlt)
        self.assertTrue(np.allclose(d[0], [1., 0., 0.]))
        self.assertEqual(d.shape, (5, 3))

    def test_empty_corrective_tables_leave_weights_untouched(self):
        w   = np.array([0.25, 0.75])
        z   = np.zeros(0, dtype=np.int64)
        got = self.mb.resolve_weights(w, z, np.zeros(0), z, z)
        self.assertTrue(np.allclose(got, w))

    def test_inbetween_is_a_triangular_hat_peaking_at_the_knot(self):
        # target 1 is an in-between of target 0 at knot 0.5
        ibase = np.array([-1, 0], dtype=np.int64)
        iknot = np.array([0.0, 0.5])
        z     = np.zeros(0, dtype=np.int64)
        cofs  = np.zeros(0, dtype=np.int64)

        def hat(driver):
            return self.mb.resolve_weights(
                np.array([driver, 0.0]), ibase, iknot, cofs, z)[1]

        self.assertAlmostEqual(hat(0.0),  0.0)
        self.assertAlmostEqual(hat(0.5),  1.0)     # peaks exactly on the knot
        self.assertAlmostEqual(hat(1.0),  0.0)
        self.assertAlmostEqual(hat(0.25), 0.5)
        self.assertAlmostEqual(hat(0.75), 0.5)

    def test_inbetween_ADDS_to_its_OWN_channel(self):
        # The driven hat is ADDED to whatever is keyed on the in-between's own
        # channel -- it does not replace it. Every weight[] element is an
        # aliased, settable rig channel (and is listed as one in the Attribute
        # Editor), so a value keyed there has to reach the deform.
        ibase = np.array([-1, 0], dtype=np.int64)
        iknot = np.array([0.0, 0.5])
        z     = np.zeros(0, dtype=np.int64)
        a     = self.mb.resolve_weights(np.array([0.5, 0.0]), ibase, iknot, z, z)
        b     = self.mb.resolve_weights(np.array([0.5, 0.9]), ibase, iknot, z, z)
        self.assertAlmostEqual(a[1], 1.0)   # hat alone, at the knot
        self.assertAlmostEqual(b[1], 1.9)   # hat + the hand-keyed 0.9
        self.assertAlmostEqual(b[0], a[0])  # the MAIN is untouched

    def test_inbetween_own_channel_alone_drives_it_with_the_main_at_rest(self):
        # Drivers down, corrective dialled by hand: the channel is the only
        # contribution, so it passes straight through.
        ibase = np.array([-1, 0], dtype=np.int64)
        iknot = np.array([0.0, 0.5])
        z     = np.zeros(0, dtype=np.int64)
        got   = self.mb.resolve_weights(np.array([0.0, 0.7]), ibase, iknot, z, z)
        self.assertAlmostEqual(got[1], 0.7)

    def test_combo_is_the_product_of_its_drivers(self):
        # target 2 is a combo of targets 0 and 1
        z    = np.zeros(0, dtype=np.int64)
        cofs = np.array([0, 0, 0, 2], dtype=np.int64)
        cdrv = np.array([0, 1], dtype=np.int64)
        got = self.mb.resolve_weights(
            np.array([0.5, 0.4, 0.0]), z, np.zeros(0), cofs, cdrv)
        self.assertAlmostEqual(got[2], 0.2)

    def test_combo_ADDS_the_product_to_its_OWN_channel(self):
        # Same rule as the in-between: driven product PLUS the hand-keyed value.
        z    = np.zeros(0, dtype=np.int64)
        cofs = np.array([0, 0, 0, 2], dtype=np.int64)
        cdrv = np.array([0, 1], dtype=np.int64)
        got = self.mb.resolve_weights(
            np.array([0.5, 0.4, 0.25]), z, np.zeros(0), cofs, cdrv)
        self.assertAlmostEqual(got[2], 0.45)
        # ...and the drivers themselves stay exactly as keyed.
        self.assertAlmostEqual(got[0], 0.5)
        self.assertAlmostEqual(got[1], 0.4)

    def test_apply_morphs_equals_resolve_plus_accumulate(self):
        z = np.zeros(0, dtype=np.int64)
        w = np.array([0.3, 0.7])
        got = self.mb.apply_morphs(self.base, 0.5, w, z, np.zeros(0), z, z,
                                   self.ofs, self.comp, self.dlt)
        eff = self.mb.resolve_weights(w, z, np.zeros(0), z, z)
        want = self.base + 0.5 * self.mb.accumulate_deltas(
            self.base, eff, self.ofs, self.comp, self.dlt)
        self.assertTrue(np.array_equal(got, want))


# ===========================================================================
# 2. registry contract + cross-module invariants
# ===========================================================================
class TestMorphInterface(unittest.TestCase):
    def setUp(self):
        from mpynode._common.interface import morph_method_interface as mmi
        self.mmi     = mmi
        self.by_name = {m.name: m for m in mmi.INTERNAL_API_METHODS}

    def test_registered_for_mPyBlendShape(self):
        from mpynode._common.interface import method_registry
        names = {m.name for m in method_registry.methods_for_type("mPyBlendShape")}
        self.assertTrue(
            {"morph_weights", "morph_deltas", "morph_apply",
             "blend_targets"}.issubset(names))

    def test_morphs_property_is_registered(self):
        from mpynode._common.interface import method_registry
        props = method_registry.properties_for_type("mPyBlendShape")
        self.assertEqual([p.name for p in props], ["morphs"])

    def test_properties_for_an_unknown_type_are_empty(self):
        from mpynode._common.interface import method_registry
        self.assertEqual(method_registry.properties_for_type("mPyMesh"), ())
        self.assertEqual(method_registry.properties_for_type(None), ())

    def test_reads_ORDER_matches_each_free_fn_trailing_params(self):
        """The reads tuple binds POSITIONALLY to the free fn's trailing params.

        A reordering here would compile clean and silently feed (say) interKnot
        where comboOffset belongs, so this is pinned rather than trusted.
        """
        import ast
        import inspect
        from mpynode._common.methods import morph_blend

        src = inspect.getsource(morph_blend)
        params = {n.name: [a.arg for a in n.args.args]
                  for n in ast.parse(src).body
                  if isinstance(n, ast.FunctionDef)}
        W = self.mmi.WEIGHT_READS
        D = self.mmi.DELTA_READS
        L = self.mmi.LIVE_READS
        # (method, free fn, LEADING user args, the exact reads tuple expected)
        for method, fn, n_user, want in (
                ("morph_weights", "resolve_weights", 0, W),
                ("morph_deltas", "accumulate_deltas_live", 2, D + L),
                ("morph_apply", "apply_morphs_live", 2, W + D + L),
                ("blend_targets", "blend_targets_live", 1, W + D + L)):
            spec = self.by_name[method]
            self.assertEqual(
                spec.lower.free_fn.rsplit(":", 1)[-1], fn,
                "%s lowers to the wrong free fn -- a delta method pointed at a "
                "non-live kernel is a compiled node that ignores its connected "
                "targets" % method)
            trailing = params[fn][n_user:]
            self.assertEqual(
                len(trailing), len(spec.reads),
                "%s: %d trailing params vs %d declared reads"
                % (method, len(trailing), len(spec.reads)))
            # The COUNT and the kernel ORDER are what bind; pin the exact tuple
            # so a silent swap is caught.
            self.assertEqual(spec.reads, want,
                             "%s: declared reads changed" % method)

    def _wrapper_tables(self):
        """Every table attr the wrapper actually declares on the node."""
        from mpynode.wrappers import mpy_blend_shape as w
        known = {w.WEIGHT_ATTR}
        known |= {a for a, _k in w.DELTA_ATTRS}
        known |= {a for a, _k in w.CORRECTIVE_ATTRS}
        known |= {a for a, _k in w.SLOT_ATTRS}
        return known

    def test_every_declared_read_is_a_real_wrapper_table_attr(self):
        known = self._wrapper_tables()
        for m in self.mmi.INTERNAL_API_METHODS:
            for r in m.reads:
                if r in self.mmi.LIVE_READS:
                    continue        # codegen-bound -- see the test below
                self.assertIn(r, known,
                              "%s reads %r which no table declares" % (m.name, r))

    def test_the_live_reads_are_NOT_plugs(self):
        """The live tables are built by CODEGEN, never read from the node.

        They are the one read surface with nothing behind it on the node: the
        emitter reads targetGeometry / originalGeometry -- Maya calls no
        transpiled kernel can make -- and hands the result across. A real plug of
        the same name would be dead weight the emitter overwrites anyway, while
        reading like configuration a user could set.
        """
        known = self._wrapper_tables()
        for r in self.mmi.LIVE_READS:
            self.assertNotIn(r, known, "%r became a real plug" % r)

    def test_LIVE_CPP_VARS_covers_exactly_LIVE_READS(self):
        """The emitting half and the binding half key off one table.

        emit_deformer DECLARES these C++ vectors and nd_lower BINDS them under
        the read names. A name in one and not the other does not fail loudly --
        the lowering just declines, try_lower_deform swallows it, and the node
        ships as an AI port with the live path silently absent.
        """
        self.assertEqual(tuple(self.mmi.LIVE_CPP_VARS), self.mmi.LIVE_READS)
        for _dt, var in self.mmi.LIVE_CPP_VARS.values():
            self.assertTrue(var.startswith("mpyLive"), var)

    def test_WEIGHT_PLUG_matches_the_wrapper_attr_name(self):
        """The desugar rewrites self.morphs.weights -> self.<WEIGHT_PLUG>.
        If that drifts from the wrapper's actual attr the rewrite targets a plug
        that does not exist."""
        from mpynode.wrappers.mpy_blend_shape import WEIGHT_ATTR
        self.assertEqual(self.mmi.WEIGHT_PLUG, WEIGHT_ATTR)

    def test_desugar_targets_are_all_registered_methods(self):
        from mpynode.native.compiler import nd_lower
        targets = {m for m, _lo, _hi in nd_lower._MORPH_CALLS.values()}
        targets.add("morph_weights")            # .resolved
        self.assertTrue(targets.issubset(set(self.by_name)),
                        "desugar targets %r not in the registry" % targets)

    def test_property_name_collision_is_fatal(self):
        from mpynode._common.interface.api_methods import (
            PropertySpec, validate_properties)
        p = PropertySpec("envelope", "sig", "doc", "m:f")
        with self.assertRaises(ValueError):
            validate_properties([p], {"envelope"})
        q = PropertySpec("morph_apply", "sig", "doc", "m:f")
        with self.assertRaises(ValueError):
            validate_properties([q], set(), ("morph_apply",))


# ===========================================================================
# 3. the desugar
# ===========================================================================
class TestMorphDesugar(unittest.TestCase):
    def _rw(self, src):
        from mpynode.native.compiler import nd_lower
        return nd_lower._rewrite_morph_reads(src).strip()

    def test_recognised_forms_rewrite_to_the_exact_blessed_call(self):
        for src, want in (
            ("x = self.morphs.apply(b, e)", "x = self.morph_apply(b, e)"),
            ("x = self.morphs.apply(b)", "x = self.morph_apply(b, 1.0)"),
            ("x = self.morphs.deltas(b, w)", "x = self.morph_deltas(b, w)"),
            ("x = self.morphs.deltas(b)",
             "x = self.morph_deltas(b, self.morph_weights())"),
            ("x = self.morphs.resolved", "x = self.morph_weights()"),
            ("x = self.morphs.weights", "x = self.weight"),
            ("x = len(self.morphs)", "x = self.weight.shape[0]"),
            ("x = self.morphs[2].weight", "x = self.weight[2]"),
        ):
            self.assertEqual(self._rw(src + "\n"), want, src)

    def test_arguments_are_emitted_EXACTLY_ONCE(self):
        """apply() has its own kernel precisely so the base expression is not
        duplicated -- base is typically mesh.getPoints(), and evaluating it
        twice per deform would be a real cost, not a cosmetic one."""
        got = self._rw("x = self.morphs.apply(mesh_pts, e)\n")
        self.assertEqual(got.count("mesh_pts"), 1, got)

    def test_nested_uses_rewrite_too(self):
        got = self._rw("x = self.morphs.deltas(b, self.morphs.resolved)\n")
        self.assertEqual(got, "x = self.morph_deltas(b, self.morph_weights())")

    def test_source_without_morphs_is_returned_untouched(self):
        src = "x = self.weight\ny = self.envelope\n"
        from mpynode.native.compiler import nd_lower
        self.assertIs(nd_lower._rewrite_morph_reads(src), src)

    def test_unrecognised_forms_honest_reject(self):
        from mpynode.native.compiler.errors import UnsupportedSpec
        for label, src in (
            # A LITERAL name key compiles (Stage 3, see TestMorphSlots); a key
            # whose value is not provably constant must still reject.
            ("branch-assigned key",
             "k = 'browUp'\nif x > 0:\n    k = 'jawOpen'\n"
             "y = self.morphs[k].weight\n"),
            ("runtime index", "i = 1\nx = self.morphs[i].weight\n"),
            ("negative index", "x = self.morphs[-1].weight\n"),
            ("unknown member", "x = self.morphs.magnitudes\n"),
            ("unknown call", "x = self.morphs.prune(1e-5)\n"),
            ("bare reference", "x = self.morphs\n"),
            ("iteration", "for m in self.morphs:\n    x = m\n"),
            ("slice", "x = self.morphs[0:2]\n"),
            ("keyword arg", "x = self.morphs.apply(b, envelope=1.0)\n"),
            ("too many args", "x = self.morphs.apply(a, b, c)\n"),
            ("too few args", "x = self.morphs.deltas()\n"),
        ):
            with self.assertRaises(UnsupportedSpec, msg=label):
                self._rw(src)

    def test_reject_message_names_the_recognised_surface(self):
        from mpynode.native.compiler.errors import UnsupportedSpec
        try:
            self._rw("x = self.morphs.magnitudes\n")
            self.fail("expected UnsupportedSpec")
        except UnsupportedSpec as e:
            self.assertIn(".resolved", str(e))
            self.assertIn(".apply(", str(e))

    def test_a_string_index_rejects_in_py_to_cpp_too(self):
        """Independent of the morph desugar: a str used as an index used to emit
        `(int64_t)(std::string(...))`, which is not valid C++ -- it passed the
        transpiler and died later in the compiler."""
        from mpynode.native.compiler import py_to_cpp
        from mpynode.native.compiler.errors import UnsupportedSpec
        from mpynode.native.compiler.py_to_cpp import array_t
        env = {"self.arr": array_t("double", 1)}
        with self.assertRaises(UnsupportedSpec):
            py_to_cpp.transpile_compute_block(
                "self.out = float(self.arr['browUp'])\n", env,
                {"self.out": lambda v: ["    X(%s);" % v.code]})


# ===========================================================================
# 4. the object on a live node
# ===========================================================================
class TestMorphStackLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        mc.file(new=True, force=True)
        cls.base = mc.polySphere(name="msBase", sx=6, sy=5, ch=False)[0]
        for nm, v, off in (("browUp", 0, (0, .5, 0)),
                           ("mouthOpen", 4, (0, -.3, .2)),
                           ("browUp50", 0, (.1, .3, 0)),
                           ("browUp_mouthOpen", 2, (0, 0, .5))):
            d = mc.duplicate(cls.base, name=nm)[0]
            mc.move(off[0], off[1], off[2], "%s.vtx[%d]" % (d, v), relative=True)
        cls.bs = MPyBlendShape.create(mesh=cls.base, name="msBS")
        for nm in ("browUp", "mouthOpen", "browUp50", "browUp_mouthOpen"):
            cls.bs.add_target(nm)
        cls.bs.rebuild()
        cls.node = cls.bs.get_name()

    # ----- rebuild now declares ALL eight tables -----
    def test_rebuild_declares_the_corrective_tables_unconditionally(self):
        """morph_weights declares them as implicit reads, and an unbound read is
        a COMPILE-time reject -- so a node without them could not compile."""
        import maya.cmds as mc
        for attr in ("targetOffset", "targetComponents", "targetDeltas",
                     "interBase", "interKnot", "comboOffset", "comboDriver"):
            self.assertTrue(mc.objExists("%s.%s" % (self.node, attr)), attr)

    # ----- authoring surface (names DO resolve here) -----
    def test_authoring_stack_carries_names(self):
        self.assertEqual(self.bs.morphs.names,
                         ["browUp", "mouthOpen", "browUp50", "browUp_mouthOpen"])

    def test_lookup_by_name(self):
        self.assertEqual(self.bs.morphs["mouthOpen"].index, 1)

    def test_unknown_name_raises_KeyError_listing_what_exists(self):
        with self.assertRaises(KeyError) as cm:
            self.bs.morphs["noSuchTarget"]
        self.assertIn("browUp", str(cm.exception))

    def test_find_substring_and_glob(self):
        m = self.bs.morphs
        self.assertEqual([x.name for x in m.find("brow*")],
                         ["browUp", "browUp50", "browUp_mouthOpen"])
        self.assertEqual([x.name for x in m.find("_")], ["browUp_mouthOpen"])
        self.assertEqual([x.name for x in m.find("MOUTH")],
                         ["mouthOpen", "browUp_mouthOpen"])

    def test_index_of_and_contains(self):
        m = self.bs.morphs
        self.assertEqual(m.index_of("browUp50"), 2)
        self.assertEqual(m.index_of("nope"), -1)
        self.assertIn("browUp", m)
        self.assertNotIn("nope", m)

    def test_len_and_iteration(self):
        m = self.bs.morphs
        self.assertEqual(len(m), 4)
        self.assertEqual([x.index for x in m], [0, 1, 2, 3])

    def test_get_never_raises(self):
        self.assertIsNone(self.bs.morphs.get("nope"))
        self.assertEqual(self.bs.morphs.get(99, "fallback"), "fallback")

    # ----- Morph value semantics -----
    def test_a_target_is_sparse(self):
        m = self.bs.morphs["browUp"]
        self.assertEqual(m.size,             1)
        self.assertEqual(m.indices.tolist(), [0])
        self.assertEqual(m.offsets.shape,    (1, 3))

    def test_addition_takes_the_sparse_index_UNION(self):
        m = self.bs.morphs
        s = m["browUp"] + m["mouthOpen"]
        self.assertEqual(sorted(s.indices.tolist()), [0, 4])
        # sized by the DISTINCT touched vertices, not by the highest vertex id
        self.assertEqual(s.offsets.shape[0], 2)

    def test_self_subtraction_is_zero(self):
        self.assertTrue((self.bs.morphs["browUp"]
                         - self.bs.morphs["browUp"]).is_zero())

    def test_scalar_multiply_scales_offsets(self):
        m = self.bs.morphs["browUp"]
        self.assertTrue(np.allclose((m * 3).offsets, m.offsets * 3))

    def test_dense_expands_to_the_full_vertex_count(self):
        m = self.bs.morphs["browUp"]
        d = m.dense(26)
        self.assertEqual(d.shape, (26, 3))
        self.assertTrue(np.allclose(d[0], m.offsets[0]))
        self.assertTrue(np.allclose(d[1], 0.0))

    def test_prune_drops_near_zero_offsets(self):
        from mpynode._api2.morph import Morph
        m = Morph("t", [[1.0, 0, 0], [1e-12, 0, 0]], [3, 7])
        self.assertEqual(m.prune(1e-7).indices.tolist(), [3])

    # ----- compute surface: ALIASES must not resolve -----
    def test_a_compute_stack_has_no_aliases(self):
        """``names`` is the ALIAS list, and aliases are unreadable on the EM
        worker thread. A name KEY still works there, but through the slot table
        (see TestMorphSlots) -- never through this."""
        from mpynode._api2.morph import MorphStack

        class _P:
            weight = [0.0, 0.0]
        s = MorphStack.from_proxy(_P())
        self.assertEqual(s.names, [])
        with self.assertRaises(KeyError) as cm:
            s["browUp"]
        # No compute source reachable on a bare stub, so no slot declares it.
        self.assertIn("browUp", str(cm.exception))

    # ----- the deform itself -----
    def test_object_apply_matches_the_blessed_methods(self):
        import maya.cmds as mc
        import maya.api.OpenMaya as om2

        shape = mc.listRelatives(self.base, shapes=True, ni=True)[0]

        def pts():
            sel = om2.MSelectionList()
            sel.add(shape)
            fn = om2.MFnMesh(sel.getDependNode(0))
            return np.array([[p.x, p.y, p.z]
                             for p in fn.getPoints(om2.MSpace.kObject)])

        mc.setAttr(self.node + ".browUp", 0.4)
        mc.setAttr(self.node + ".mouthOpen", 0.7)

        forms = {
            "methods": ("mesh = self.outputGeometry[0]\n"
                        "base = mesh.getPoints()\n"
                        "mesh.setPoints(base + float(self.envelope) * "
                        "self.morph_deltas(base, self.morph_weights()))\n"),
            "apply": ("mesh = self.outputGeometry[0]\n"
                      "base = mesh.getPoints()\n"
                      "mesh.setPoints(self.morphs.apply(base, self.envelope))\n"),
            "two-step": ("mesh = self.outputGeometry[0]\n"
                         "base = mesh.getPoints()\n"
                         "w = self.morphs.resolved\n"
                         "d = self.morphs.deltas(base, w)\n"
                         "mesh.setPoints(base + float(self.envelope) * d)\n"),
        }
        got = {}
        for label, src in forms.items():
            mc.setAttr(self.node + "._computeSource", src, type="string")
            mc.dgdirty(self.node)
            got[label] = pts()

        for label in ("apply", "two-step"):
            self.assertTrue(
                np.allclose(got[label], got["methods"], atol=1e-9),
                "%s diverges from the blessed-method form (maxerr %.3e)"
                % (label, float(np.abs(got[label] - got["methods"]).max())))

    def test_every_object_form_lowers_to_pure_cpp(self):
        import maya.cmds as mc
        from mpynode.native.compiler import nd_lower
        from mpynode.native.compiler.emit_attr import _members
        from mpynode.native.spec.spec_extractor import extract_spec

        for src in (
            ("mesh = self.outputGeometry[0]\n"
             "base = mesh.getPoints()\n"
             "mesh.setPoints(self.morphs.apply(base, self.envelope))\n"),
            ("mesh = self.outputGeometry[0]\n"
             "base = mesh.getPoints()\n"
             "w = self.morphs.resolved\n"
             "mesh.setPoints(base + float(self.envelope) * "
             "self.morphs.deltas(base, w))\n"),
        ):
            mc.setAttr(self.node + "._computeSource", src, type="string")
            spec = extract_spec(self.node)
            self.assertEqual((spec["portability"].get("blockers") or []), [])
            ins  = [m for m in _members(spec) if m["kind"] == "inputs"]
            body = nd_lower.try_lower_deform(ins, spec, "MPxDeformerNode")
            self.assertIsNotNone(body, "did not lower:\n%s" % src)
            text = "\n".join(body)
            # the object is ERASED and nothing name-derived is baked in
            self.assertNotIn("MorphStack", text)
            self.assertNotIn("browUp",     text)
            self.assertNotIn("mouthOpen",  text)

    def test_an_unsupported_object_form_is_reported_to_the_porter(self):
        """The gate must run the REAL desugar on the RAW source.

        ``assess_portability`` scans ``_strip_comments_strings`` output, which
        blanks a string literal INCLUDING its quotes -- ``self.morphs[      ]``
        does not parse, so an AST gate fed that text silently passes everything.

        The refusal text is now carried to the AI porter as ``unported`` rather
        than aborting the build. That text names the whole recognised MorphStack
        surface, which is what keeps the original guarantee alive: the reason
        this form was refused was the risk of a member lowering to something
        other than what MorphStack does interpreted, and the porter can only
        avoid that if it is told the correct forms.
        """
        import maya.cmds as mc
        from mpynode.native.spec.spec_extractor import extract_spec

        mc.setAttr(self.node + "._computeSource",
                   "mesh = self.outputGeometry[0]\n"
                   "base = mesh.getPoints()\n"
                   "x = self.morphs['browUp'].size\n"
                   "mesh.setPoints(base)\n", type="string")
        rep = extract_spec(self.node)["portability"]
        self.assertTrue(rep["portable"], repr(rep["blockers"]))
        self.assertTrue(any("morphs" in u for u in rep["unported"]),
                        repr(rep["unported"]))
        # Each refusal names the supported form for ITS branch: here the
        # indexed-target one, where only .weight is reachable. That
        # specificity is the point, it is what the porter reads.
        self.assertTrue(any(".weight" in u for u in rep["unported"]),
                        "the supported form must travel with the gap: %r"
                        % rep["unported"])


# ===========================================================================
# 5. Stage 3 -- NAME keys, folded to a per-rig slot
# ===========================================================================
class TestMorphSlotFold(unittest.TestCase):
    """The const-fold and unroll that turn a name into a compile-time slot.

    The dangerous case is a name that LOOKS constant but is not: a string local
    is a real runtime value (``str_t`` is a kind in the lattice), so folding one
    that a branch reassigns would silently drive the wrong shape. Every negative
    here is that failure mode in a different spelling.
    """

    def _d(self, body):
        from mpynode.native.compiler.nd_lower import _desugar_morphs
        return _desugar_morphs("mesh = self.outputGeometry[0]\n"
                               "base = mesh.getPoints()\n" + body +
                               "mesh.setPoints(base)\n")

    def _rejects(self, body, needle=None):
        from mpynode.native.compiler.errors import UnsupportedSpec
        with self.assertRaises(UnsupportedSpec) as cm:
            self._d(body)
        if needle:
            self.assertIn(needle, str(cm.exception))

    # ----- recognised spellings -----
    def test_literal_key_folds_to_slot_zero(self):
        out, slots = self._d("x = self.morphs['browUp'].weight\n")
        self.assertEqual(slots, ("browUp",))
        self.assertIn("self.morph_weight_at(0)", out)

    def test_distinct_names_get_distinct_slots_in_source_order(self):
        _out, slots = self._d(
            "x = self.morphs['b'].weight + self.morphs['a'].weight\n")
        self.assertEqual(slots, ("b", "a"))

    def test_the_same_name_twice_shares_one_slot(self):
        out, slots = self._d("x = self.morphs['b'].weight\n"
                             "y = self.morphs['b'].weight\n")
        self.assertEqual(slots, ("b",))
        self.assertEqual(out.count("self.morph_weight_at(0)"), 2)

    def test_3a_scalar_constant_folds(self):
        out, slots = self._d("JAW = 'jawOpen'\n"
                             "x = self.morphs[JAW].weight\n")
        self.assertEqual(slots, ("jawOpen",))
        self.assertIn("self.morph_weight_at(0)", out)

    def test_3a_consumed_constant_is_dropped_from_the_output(self):
        """It must not reach py_to_cpp at all -- that is what lets a name key
        compile with no new string type in the shared transpiler."""
        out, _slots = self._d("JAW = 'jawOpen'\n"
                              "x = self.morphs[JAW].weight\n")
        self.assertNotIn("JAW", out)

    def test_a_constant_still_read_elsewhere_is_kept(self):
        out, _slots = self._d("JAW = 'jawOpen'\n"
                              "x = self.morphs[JAW].weight\n"
                              "y = JAW\n")
        self.assertIn("JAW = 'jawOpen'", out)

    def test_3b_constant_tuple_loop_unrolls(self):
        out, slots = self._d("NAMES = ('a', 'b')\n"
                             "t = 0.0\n"
                             "for n in NAMES:\n"
                             "    t = t + self.morphs[n].weight\n")
        self.assertEqual(slots, ("a", "b"))
        self.assertIn("self.morph_weight_at(0)", out)
        self.assertIn("self.morph_weight_at(1)", out)
        self.assertNotIn("for n in", out)

    def test_3b_inline_tuple_literal_unrolls(self):
        _out, slots = self._d("t = 0.0\n"
                              "for n in ('a', 'b', 'c'):\n"
                              "    t = t + self.morphs[n].weight\n")
        self.assertEqual(slots, ("a", "b", "c"))

    def test_constant_tuple_element_by_int_literal(self):
        _out, slots = self._d("NAMES = ('a', 'b')\n"
                              "x = self.morphs[NAMES[1]].weight\n")
        self.assertEqual(slots, ("b",))

    def test_3c_range_loop_indexing_a_constant_list(self):
        _out, slots = self._d("NAMES = ('a', 'b')\n"
                              "t = 0.0\n"
                              "for i in range(len(NAMES)):\n"
                              "    t = t + self.morphs[NAMES[i]].weight\n")
        self.assertEqual(slots, ("a", "b"))

    def test_an_ordinary_range_loop_is_NOT_unrolled(self):
        """``for i in range(n)`` already lowers to a real C++ loop. Unrolling it
        would change codegen that works today, so the 3c gate must not fire."""
        out, _slots = self._d("x = self.morphs['a'].weight\n"
                              "t = 0.0\n"
                              "for i in range(4):\n"
                              "    t = t + float(self.weight[i])\n")
        self.assertIn("for i in range(4)", out)

    def test_an_int_index_still_reads_the_weight_multi_directly(self):
        out, slots = self._d("x = self.morphs[2].weight\n")
        self.assertEqual(slots, ())
        self.assertIn("self.weight[2]", out)

    # ----- the unsound cases MUST reject -----
    def test_a_branch_reassigned_key_rejects(self):
        self._rejects("k = 'a'\n"
                      "if float(self.envelope) > 0.5:\n"
                      "    k = 'b'\n"
                      "x = self.morphs[k].weight\n",
                      "not a provable constant")

    def test_a_key_assigned_inside_a_block_rejects(self):
        self._rejects("if float(self.envelope) > 0.5:\n"
                      "    k = 'a'\n"
                      "x = self.morphs[k].weight\n",
                      "not a provable constant")

    def test_a_mutated_sequence_rejects(self):
        self._rejects("NAMES = ['a', 'b']\n"
                      "NAMES[0] = 'c'\n"
                      "x = self.morphs[NAMES[0]].weight\n")

    def test_an_appended_sequence_rejects(self):
        self._rejects("NAMES = ['a']\n"
                      "NAMES.append('b')\n"
                      "for n in NAMES:\n"
                      "    x = self.morphs[n].weight\n")

    def test_break_in_an_unrolled_loop_rejects(self):
        self._rejects("NAMES = ('a', 'b')\n"
                      "for n in NAMES:\n"
                      "    x = self.morphs[n].weight\n"
                      "    break\n", "break/continue")

    def test_for_else_rejects(self):
        self._rejects("NAMES = ('a', 'b')\n"
                      "for n in NAMES:\n"
                      "    x = self.morphs[n].weight\n"
                      "else:\n"
                      "    x = 0.0\n", "for/else")

    def test_only_weight_is_reachable_from_an_indexed_target(self):
        self._rejects("x = self.morphs['a'].size\n", "Only .weight")

    def test_unroll_blowup_is_capped_loudly(self):
        names = ", ".join("'n%d'" % i for i in range(300))
        self._rejects("NAMES = (%s)\n"
                      "t = 0.0\n"
                      "for n in NAMES:\n"
                      "    t = t + self.morphs[n].weight\n" % names,
                      "more than")

    # ----- the ordering is single-sourced -----
    def test_morph_slot_names_agrees_with_the_desugar(self):
        from mpynode.native.compiler.nd_lower import morph_slot_names
        src = ("mesh = self.outputGeometry[0]\n"
               "base = mesh.getPoints()\n"
               "NAMES = ('a', 'b')\n"
               "x = self.morphs['z'].weight\n"
               "for n in NAMES:\n"
               "    x = x + self.morphs[n].weight\n"
               "mesh.setPoints(base)\n")
        from mpynode.native.compiler.nd_lower import _desugar_morphs
        self.assertEqual(morph_slot_names(src), _desugar_morphs(src)[1])
        self.assertEqual(morph_slot_names(src), ("z", "a", "b"))

    def test_slot_names_survives_a_source_the_compiler_would_reject(self):
        """The interpreted node resolves names through this ordering and may use
        authoring-only members, so collection must not inherit the rejects."""
        from mpynode.native.compiler.nd_lower import morph_slot_names
        src = ("x = self.morphs['browUp'].weight\n"
               "y = self.morphs.prune(1e-5)\n")     # no compiled form
        self.assertEqual(morph_slot_names(src), ("browUp",))

    def test_slot_names_is_empty_for_unparseable_source(self):
        from mpynode.native.compiler.nd_lower import morph_slot_names
        self.assertEqual(morph_slot_names("self.morphs[ this is not python"), ())


class TestMorphSlots(unittest.TestCase):
    """``shapeSlot`` on a real node: the per-rig half of the name indirection."""

    @classmethod
    def setUpClass(cls):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        mc.file(new=True, force=True)
        cls.base = mc.polySphere(name="slotBase", sx=6, sy=5, ch=False)[0]
        for i, nm in enumerate(("browUp", "mouthOpen", "jawOpen")):
            d = mc.duplicate(cls.base, name=nm)[0]
            mc.move(0, .4 + .1 * i, 0, "%s.vtx[%d]" % (d, i), relative=True)
        cls.bs = MPyBlendShape.create(mesh=cls.base, name="slotBS")
        for nm in ("browUp", "mouthOpen", "jawOpen"):
            cls.bs.add_target(nm)
        cls.node = cls.bs.get_name()
        cls.SRC = ("mesh = self.outputGeometry[0]\n"
                   "base = mesh.getPoints()\n"
                   "j = float(self.morphs['jawOpen'].weight)\n"
                   "b = float(self.morphs['browUp'].weight)\n"
                   "d = self.morphs.deltas(base, self.morphs.resolved)\n"
                   "mesh.setPoints(base + float(self.envelope) * d "
                   "* (1.0 + 0.0 * (j + b)))\n")
        mc.setAttr(cls.node + "._computeSource", cls.SRC, type="string")
        cls.bs.rebuild()

    def test_rebuild_declares_shapeSlot_unconditionally(self):
        """morph_weight_at names it an implicit read, and an unbound read is a
        compile-time reject."""
        import maya.cmds as mc
        self.assertTrue(mc.objExists("%s.shapeSlot" % self.node))

    def test_slot_names_come_from_the_compiler(self):
        self.assertEqual(self.bs.compute_slot_names(), ["jawOpen", "browUp"])

    def test_shapeSlot_maps_each_slot_to_this_rigs_weight_index(self):
        # jawOpen is weight[2] here, browUp is weight[0]
        self.assertEqual(self.bs._read_multi("shapeSlot", int), [2, 0])

    def test_a_name_this_rig_lacks_writes_minus_one(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        other = mc.polySphere(name="lonelyBase", sx=4, sy=3, ch=False)[0]
        bs2   = MPyBlendShape.create(mesh=other, name="lonelyBS")
        mc.setAttr(bs2.get_name() + "._computeSource", self.SRC, type="string")
        bs2.rebuild()
        self.assertEqual(bs2._read_multi("shapeSlot", int), [-1, -1])

    def test_interpreted_name_lookup_goes_through_shapeSlot(self):
        import maya.cmds as mc
        for a in ("gotJaw", "gotBrow", "gotMissing"):
            if not mc.objExists("%s.%s" % (self.node, a)):
                self.bs.add_output_attr(a, "double")
        mc.setAttr(self.node + ".browUp", 0.25)
        mc.setAttr(self.node + ".jawOpen", 0.5)
        mc.setAttr(self.node + "._computeSource",
                   "mesh = self.outputGeometry[0]\n"
                   "base = mesh.getPoints()\n"
                   "self.gotJaw = float(self.morphs['jawOpen'].weight)\n"
                   "self.gotBrow = float(self.morphs['browUp'].weight)\n"
                   "self.gotMissing = float(self.morphs['nope'].weight)\n"
                   "mesh.setPoints(base)\n", type="string")
        self.bs.rebuild()
        mc.dgdirty(self.node)
        mc.getAttr(self.node + ".outputGeometry[0]")
        # weight[] is a FLOAT multi, so compare at float32 precision.
        self.assertAlmostEqual(mc.getAttr(self.node + ".gotJaw"), 0.5, places=6)
        self.assertAlmostEqual(mc.getAttr(self.node + ".gotBrow"), 0.25, places=6)
        # a name this rig has no target for reads AT REST, matching the
        # compiled weight_at_slot; that is what lets one bundle serve any rig.
        self.assertAlmostEqual(mc.getAttr(self.node + ".gotMissing"), 0.0)
        mc.setAttr(self.node + "._computeSource", self.SRC, type="string")
        self.bs.rebuild()

    def test_the_compute_lowers_and_bakes_no_name(self):
        import maya.cmds as mc
        from mpynode.native.compiler import nd_lower
        from mpynode.native.compiler.emit_attr import _members
        from mpynode.native.spec.spec_extractor import extract_spec

        mc.setAttr(self.node + "._computeSource", self.SRC, type="string")
        spec = extract_spec(self.node)
        self.assertEqual(spec["portability"].get("blockers") or [], [])
        ins  = [m for m in _members(spec) if m["kind"] == "inputs"]
        body = nd_lower.try_lower_deform(ins, spec, "MPxDeformerNode")
        self.assertIsNotNone(body)
        text = "\n".join(body)
        for nm in ("jawOpen", "browUp", "mouthOpen"):
            self.assertNotIn(nm, text)
        self.assertIn("shapeSlot", text)

    def test_the_fingerprint_moves_when_the_computes_names_change(self):
        """shapeSlot is derived from the COMPUTE, and editing it touches no
        alias and no table length -- so an alias-only key would call the stale
        table fresh and the node would drive the previous shape."""
        import maya.cmds as mc
        mc.setAttr(self.node + "._computeSource", self.SRC, type="string")
        self.bs.rebuild()
        before = self.bs.alias_fingerprint
        self.assertFalse(self.bs.tables_stale())
        mc.setAttr(self.node + "._computeSource",
                   self.SRC.replace("'browUp'", "'mouthOpen'"), type="string")
        self.assertNotEqual(self.bs.alias_fingerprint, before)
        self.assertTrue(self.bs.tables_stale())
        self.bs.rebuild()
        self.assertFalse(self.bs.tables_stale())
        self.assertEqual(self.bs._read_multi("shapeSlot", int), [2, 1])
        mc.setAttr(self.node + "._computeSource", self.SRC, type="string")
        self.bs.rebuild()


if __name__ == "__main__":
    unittest.main()
