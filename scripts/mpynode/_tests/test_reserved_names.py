"""Reserved-name resolver: per-type coverage, runtime parity, fail-open.

The parity suite is the drift guard. The framework's ``compute_locals`` seeds
are built inside ``compute()`` from a live datablock, so they cannot be read
back without Maya AND a real evaluation; the reserved set therefore declares
them as wrapper class tuples. These tests AST-parse the REAL seed dicts out of
``_api1`` / ``_api2`` and fail the moment the declaration stops matching.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ast
import sys
import unittest

import maya.standalone
maya.standalone.initialize()

from mpynode._common.interface import reserved_names


# .../scripts/mpynode/_common/interface/reserved_names.py -> .../scripts
_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(reserved_names.__file__)))))


# node type -> (source file relative to scripts/, seed variable names)
_SEED_SITES = {
    "mPyMesh": ("mpynode/_api2/mpy_mesh.py", ("_compute_locals",)),
    "mPyNurbsCurve": ("mpynode/_api2/mpy_nurbs_curve.py",
                      ("_compute_locals",)),
    "mPyNurbsSurface": ("mpynode/_api2/mpy_nurbs_surface.py",
                        ("_compute_locals",)),
    "mPyLocator": ("mpynode/_api2/mpy_locator.py", ("_compute_locals",)),
    "mPyTransform": ("mpynode/_api1/mpy_transform.py", ("compute_locals",)),
    "mPyIkSolver": ("mpynode/_api1/helpers.py", ("ik_compute_locals",)),
    "mPyFile": ("mpynode/_api2/mpy_file.py",
                ("preset_locals", "viewport_locals")),
    "mPyConstraint": ("mpynode/_api2/mpy_constraint.py",
                      ("preset_internals", "merged_locals")),
}


# node type -> source file carrying the ``output_scratch_keys=`` call. A real
# plug WINS on read for these seeded slots, so a same-named user attr COEXISTS
# instead of being shadowed -- not reserved. Same runtime-underivability as the
# seed dicts above, hence a declared tuple plus this drift guard.
_SCRATCH_SITES = {
    "mPyMesh": "mpynode/_api2/mpy_mesh.py",
    "mPyNurbsCurve": "mpynode/_api2/mpy_nurbs_curve.py",
    "mPyNurbsSurface": "mpynode/_api2/mpy_nurbs_surface.py",
    "mPyLocator": "mpynode/_api2/mpy_locator.py",
}


class _SeedKeyCollector(ast.NodeVisitor):
    """Collect the STRING-LITERAL keys the framework seeds into a
    compute_locals dict: dict-literal assignments, ``.update({...})`` calls
    and ``d["key"] = ...`` subscript writes. Dynamic keys (user inputs /
    outputs seeded from a loop variable) are correctly ignored -- those are
    plugs, not framework names."""

    def __init__(self, targets):
        self.targets = set(targets)
        self.keys = set()

    def _dict_keys(self, node):
        if not isinstance(node, ast.Dict):
            return
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self.keys.add(key.value)

    def visit_Assign(self, node):
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in self.targets:
                self._dict_keys(node.value)
            elif (isinstance(tgt, ast.Subscript)
                  and isinstance(tgt.value, ast.Name)
                  and tgt.value.id in self.targets
                  and isinstance(tgt.slice, ast.Constant)
                  and isinstance(tgt.slice.value, str)):
                self.keys.add(tgt.slice.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if (isinstance(node.target, ast.Name)
                and node.target.id in self.targets
                and node.value is not None):
            self._dict_keys(node.value)
        self.generic_visit(node)

    def visit_Call(self, node):
        fn = node.func
        if (isinstance(fn, ast.Attribute) and fn.attr == "update"
                and isinstance(fn.value, ast.Name)
                and fn.value.id in self.targets):
            for arg in node.args:
                self._dict_keys(arg)
        self.generic_visit(node)


class _ScratchKeyCollector(ast.NodeVisitor):
    """Collect the string-literal names passed as ``output_scratch_keys=`` and
    count the call sites (a second, un-mirrored site must not slip by)."""

    def __init__(self):
        self.keys = set()
        self.sites = 0

    def visit_keyword(self, node):
        if node.arg == "output_scratch_keys":
            self.sites += 1
            for elt in getattr(node.value, "elts", ()):
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    self.keys.add(elt.value)
        self.generic_visit(node)


def _parse(rel_path):
    path = os.path.join(_SCRIPTS, rel_path)
    with open(path, "r") as handle:
        return ast.parse(handle.read(), filename=path)


def _runtime_seed_keys(rel_path, targets):
    collector = _SeedKeyCollector(targets)
    collector.visit(_parse(rel_path))
    return collector.keys


def _runtime_scratch_keys(rel_path):
    collector = _ScratchKeyCollector()
    collector.visit(_parse(rel_path))
    return collector.keys, collector.sites


def _declared_scratch_slots(node_type):
    cls = reserved_names._wrapper_class_for_type(node_type)
    return set(getattr(cls, "COEXISTING_SCRATCH_SLOTS", ()) or ())


def _declared_slot_names(node_type):
    """Every framework slot the WRAPPER declares, reserved or not. Read from
    the class tuples, not from the resolver: the resolver subtracts the
    coexisting (output-scratch) names, and completeness of the DECLARATION is
    what the parity suite is guarding."""
    cls = reserved_names._wrapper_class_for_type(node_type)
    declared = set()
    for attr in ("INTERNAL_API_SLOTS", "RESERVED_COMPUTE_LOCALS"):
        for entry in getattr(cls, attr, ()) or ():
            declared.add(entry if isinstance(entry, str) else entry[0])
    return declared


class TestResolverPerType(unittest.TestCase):
    """Every mpy node type answers, and every answer carries a real reason."""

    def test_every_type_answers_with_reasons(self):
        for node_type in reserved_names.known_types():
            reserved = reserved_names.reserved_names_for_type(node_type)
            self.assertIsInstance(reserved, dict, node_type)
            self.assertTrue(reserved, "empty reserved set for " + node_type)
            for name, reason in reserved.items():
                self.assertIsInstance(reason, str)
                # A dialog-grade reason names the thing it is talking about.
                self.assertIn(repr(name), reason, "%s/%s" % (node_type, name))
                self.assertGreater(len(reason), len(repr(name)) + 10)

    def test_self_proxy_bridge_reserved_on_every_type(self):
        # Real attributes on SelfProxy: normal lookup finds them, so
        # __getattr__ (plug / init / storage tiers) never runs.
        for node_type in reserved_names.known_types():
            reserved = reserved_names.reserved_names_for_type(node_type)
            for name in ("get_compute_locals", "diff_storage",
                         "get_plug_proxy", "mark_compute_local_writable"):
                self.assertIn(name, reserved, node_type)

    def test_landmine3_underclaims_are_closed(self):
        # The geometry buffers once listed here (color_indices / normal_indices
        # / outMesh / outCurve / outSurface) are output-scratch: a real plug
        # wins on read, so they COEXIST and are deliberately not reserved.
        xform = reserved_names.reserved_names_for_type("mPyTransform")
        for name in ("translate", "rotate", "scale", "shear", "rotate_order"):
            self.assertIn(name, xform)

    def test_blessed_methods_and_properties_reserved(self):
        file_names = reserved_names.reserved_names_for_type("mPyFile")
        self.assertIn("read_texture", file_names)
        self.assertIn("sample_texture", file_names)
        skin = reserved_names.reserved_names_for_type("mPySkinCluster")
        for name in ("linear_blend", "dual_quaternion", "twist_swing"):
            self.assertIn(name, skin)
        # morphs is a real PropertySpec -> SelfProxy Tier 0.5.
        self.assertIn(
            "morphs",
            reserved_names.reserved_names_for_type("mPyBlendShape"))

    def test_d3_blendshape_authoring_properties_not_reserved(self):
        # D3: aliases / target_count / alias_fingerprint are wrapper @property
        # names, never bound into SelfProxy. A user input of that name works
        # today (the plug wins), so reserving them would regress it.
        bs = reserved_names.reserved_names_for_type("mPyBlendShape")
        for name in ("aliases", "target_count", "alias_fingerprint"):
            self.assertNotIn(name, bs)

    def test_reason_text_is_specific(self):
        mesh = reserved_names.reserved_names_for_type("mPyMesh")
        self.assertEqual(
            mesh["time"],
            "'time' is a framework READ slot on mPyMesh -- "
            "TimeFloat -- current frame; .fps / .asSeconds()")


class TestRuntimeParity(unittest.TestCase):
    """The declared tuples must still equal what the bridge actually seeds."""

    def test_declared_set_equals_runtime_seed(self):
        for node_type, (rel_path, targets) in sorted(_SEED_SITES.items()):
            seeded = _runtime_seed_keys(rel_path, targets)
            self.assertTrue(seeded, "no seed keys parsed from " + rel_path)
            declared = _declared_slot_names(node_type)
            missing = seeded - declared
            self.assertFalse(
                missing,
                "%s seeds %s into compute_locals but the wrapper does not "
                "declare it (add to RESERVED_COMPUTE_LOCALS)"
                % (node_type, sorted(missing)))

    def test_no_stale_declarations(self):
        # The reverse direction: a declared slot that the bridge no longer
        # seeds is dead weight and would reserve a name for no reason.
        for node_type, (rel_path, targets) in sorted(_SEED_SITES.items()):
            seeded = _runtime_seed_keys(rel_path, targets)
            stale = _declared_slot_names(node_type) - seeded
            self.assertFalse(
                stale,
                "%s declares %s but the bridge no longer seeds it"
                % (node_type, sorted(stale)))


class TestCoexistingScratchSlots(unittest.TestCase):
    """A name that COEXISTS is not reserved; a name that SHADOWS is.

    ``output_scratch_keys`` exists precisely so a user input/output of a
    buffer's name stays readable via ``self.<name>`` (a real plug wins on
    read). Reserving those names would block the configuration the mechanism
    was built to support, so the resolver subtracts them -- from the declared
    ``COEXISTING_SCRATCH_SLOTS`` tuple, which these tests keep honest against
    the REAL ``output_scratch_keys=`` call.
    """

    def test_declared_tuple_matches_the_real_output_scratch_keys(self):
        for node_type, rel_path in sorted(_SCRATCH_SITES.items()):
            passed, sites = _runtime_scratch_keys(rel_path)
            self.assertEqual(
                sites, 1,
                "%s: expected exactly 1 output_scratch_keys= call in %s, "
                "found %d" % (node_type, rel_path, sites))
            declared = _declared_scratch_slots(node_type)
            self.assertEqual(
                declared, passed,
                "%s COEXISTING_SCRATCH_SLOTS drifted from %s: "
                "under-declared %s, stale %s"
                % (node_type, rel_path,
                   sorted(passed - declared), sorted(declared - passed)))

    def test_scratch_slots_are_a_subset_of_the_seeded_slots(self):
        # A scratch key that is not seeded at all would be subtracting a name
        # the resolver never reserved -- i.e. a typo, silently doing nothing.
        for node_type, rel_path in sorted(_SCRATCH_SITES.items()):
            passed, _ = _runtime_scratch_keys(rel_path)
            orphans = passed - _declared_slot_names(node_type)
            self.assertFalse(
                orphans,
                "%s marks %s as output-scratch but declares no such slot"
                % (node_type, sorted(orphans)))

    def test_coexisting_names_are_not_reserved(self):
        for node_type in sorted(_SCRATCH_SITES):
            reserved = reserved_names.reserved_names_for_type(node_type)
            for name in sorted(_declared_scratch_slots(node_type)):
                self.assertNotIn(
                    name, reserved,
                    "%s.%s coexists with its scratch slot (the plug wins on "
                    "read) -- reserving it blocks a working configuration"
                    % (node_type, name))
                self.assertIsNone(
                    reserved_names.check_reserved_name(name,
                                                       node_type=node_type))

    def test_shadowing_slots_still_reserved(self):
        # The counter-case, one per type: a seeded slot that is NOT
        # output-scratch really does shadow a same-named plug on read.
        shadowing = {
            "mPyMesh": ("time",),
            "mPyNurbsCurve": ("time", "degree", "form", "rational"),
            "mPyNurbsSurface": ("time", "degree_u", "form_v"),
            "mPyLocator": ("time", "selected", "is_lead", "hovered",
                           "selection_color"),
        }
        for node_type, names in sorted(shadowing.items()):
            scratch = _declared_scratch_slots(node_type)
            for name in names:
                self.assertNotIn(name, scratch)  # premise of the case
                self.assertIsNotNone(
                    reserved_names.check_reserved_name(name,
                                                       node_type=node_type),
                    "%s.%s shadows on read and must stay reserved"
                    % (node_type, name))


class TestPrefixAndCheck(unittest.TestCase):
    def test_psp_prefix_reserved_without_a_type(self):
        reason = reserved_names.check_reserved_name("_psp_mobject")
        self.assertIsNotNone(reason)
        self.assertIn("_psp_", reason)

    def test_check_returns_none_for_a_free_name(self):
        self.assertIsNone(
            reserved_names.check_reserved_name("amplitude",
                                               node_type="mPyMesh"))

    def test_check_returns_reason_for_a_taken_name(self):
        reason = reserved_names.check_reserved_name("time",
                                                    node_type="mPyMesh")
        self.assertIsNotNone(reason)
        self.assertIn("time", reason)

    def test_check_with_no_type_only_sees_the_shared_surface(self):
        self.assertIsNone(reserved_names.check_reserved_name("time"))
        self.assertIsNotNone(
            reserved_names.check_reserved_name("get_compute_locals"))

    def test_empty_name(self):
        self.assertIsNone(reserved_names.check_reserved_name(""))
        self.assertIsNone(reserved_names.check_reserved_name(None))


class TestFailsOpen(unittest.TestCase):
    """LANDMINE 5: every failure path returns nothing, never raises."""

    def test_unknown_type(self):
        # A non-mpy node has none of these tiers, so there is nothing to say.
        self.assertEqual(
            reserved_names.reserved_names_for_type("polyCube"), {})
        self.assertEqual(reserved_names.reserved_names_for_type(None), {})
        self.assertIsNone(
            reserved_names.check_reserved_name("get_compute_locals",
                                               node_type="polyCube"))

    def test_missing_node(self):
        self.assertEqual(
            reserved_names.reserved_names_for_node("no_such_node_xyz"), {})
        self.assertIsNone(
            reserved_names.check_reserved_name(
                "time", node_name="no_such_node_xyz"))

    def _sabotage(self, *module_names):
        saved = {}
        for mod in module_names:
            saved[mod] = sys.modules.get(mod)
            sys.modules[mod] = None  # makes `import mod` raise ImportError
        self.addCleanup(self._restore, saved)

    @staticmethod
    def _restore(saved):
        for mod, value in saved.items():
            if value is None:
                sys.modules.pop(mod, None)
            else:
                sys.modules[mod] = value

    def test_wrapper_import_failure_is_survivable(self):
        self._sabotage("mpynode.wrappers.mpy_mesh")
        self.assertIsNone(
            reserved_names._wrapper_class_for_type("mPyMesh"))
        reserved = reserved_names.reserved_names_for_type("mPyMesh")
        self.assertIsInstance(reserved, dict)
        # The wrapper tier is gone (fail OPEN -- nothing is reserved from it)
        # but nothing raised and the type-independent tier still answers.
        self.assertNotIn("time", reserved)
        self.assertIn("get_compute_locals", reserved)

    def test_total_import_failure_returns_empty(self):
        self._sabotage(
            "mpynode.wrappers.mpy_mesh",
            "mpynode._common.compute.self_proxy",
            "mpynode._common.interface.method_registry",
        )
        self.assertEqual(
            reserved_names.reserved_names_for_type("mPyMesh"), {})
        self.assertIsNone(
            reserved_names.check_reserved_name("time",
                                               node_type="mPyMesh"))
        # The prefix rule needs no import at all and must still fire.
        self.assertIsNotNone(
            reserved_names.check_reserved_name("_psp_x", node_type="mPyMesh"))

    def test_module_scope_is_import_free(self):
        # LANDMINE 5: wrappers/_mpy_node.py imports this during plug-in
        # registration, before _common is guaranteed importable. Every
        # import must therefore live inside a function body.
        path = os.path.abspath(reserved_names.__file__).replace(".pyc", ".py")
        with open(path, "r") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            self.assertNotIsInstance(
                node, (ast.Import, ast.ImportFrom),
                "module-scope import at line %d" % node.lineno)


class _LiveNodeCase(unittest.TestCase):
    """Base for the cases that need real nodes (and therefore the plugins)."""

    @classmethod
    def setUpClass(cls):
        from ._setup import ensure_plugins_loaded

        ensure_plugins_loaded()

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    @staticmethod
    def _make(node_type):
        return reserved_names._wrapper_class_for_type(node_type).create(
            skip_selection=True)


class TestCoexistingNamesAreAddableOnLiveNodes(_LiveNodeCase):
    """The end-to-end shape of the regression: the guard must not stand
    between the user and a name the bridge deliberately lets a plug win."""

    # These three are the node's REAL geometry output plug, so Maya itself
    # refuses a dynamic attr of that name long before any guard runs. They stay
    # un-reserved; the assertion below is that the refusal is Maya's, not ours.
    _OWNED_BY_MAYA = {"outMesh", "outCurve", "outSurface"}

    def test_every_coexisting_name_can_be_added(self):
        for node_type in sorted(_SCRATCH_SITES):
            for name in sorted(_declared_scratch_slots(node_type)):
                node = self._make(node_type)
                if name in self._OWNED_BY_MAYA:
                    self.assertIsNone(
                        reserved_names.check_reserved_name(
                            name, node_type=node_type))
                    with self.assertRaises(Exception) as ctx:
                        node.add_input_attr(name, "float")
                    self.assertNotIn("reserved by the framework",
                                     str(ctx.exception))
                    continue
                node.add_input_attr(name, "float")   # must not raise
                self.assertIn(name, node.get_input_attr_map(),
                              "%s.%s was not added" % (node_type, name))

    def test_shadowing_name_still_raises_on_every_type(self):
        for node_type, name in sorted({
            "mPyMesh": "time",
            "mPyNurbsCurve": "degree",
            "mPyNurbsSurface": "degree_u",
            "mPyLocator": "selected",
        }.items()):
            node = self._make(node_type)
            with self.assertRaises(ValueError) as ctx:
                node.add_input_attr(name, "float")
            self.assertIn("reserved by the framework", str(ctx.exception))


class TestSurgeryGraceDoesNotDowngradeTheGuard(_LiveNodeCase):
    """The downgrade to a warning belongs to the surgery BLOCK, not to the
    trailing ``_SURGERY_GRACE_S`` window that follows it.

    The grace exists so ``should_defer_transient`` still covers a deferred EM
    pull after the block returns; every attr / var a surgery writes goes in
    synchronously while the depth counter is up. Letting the grace reach the
    authoring guard turned every reorder and every .mpn load into a ~2 second
    window in which a reserved name was merely warned about."""

    def test_reserved_add_warns_inside_the_block(self):
        from mpynode._common.lifecycle import scene_state

        node = self._make("mPyMesh")
        scene_state.begin_attr_surgery()
        try:
            node.add_input_attr("diff_storage", "float")  # warns, allowed
        finally:
            scene_state.end_attr_surgery()
        self.assertIn("diff_storage", node.get_input_attr_map())

    def test_reserved_add_raises_in_the_trailing_grace(self):
        from mpynode._common.lifecycle import scene_state

        node = self._make("mPyMesh")
        scene_state.begin_attr_surgery()
        scene_state.end_attr_surgery()
        # The grace is still open -- deferred transients are still suppressed.
        self.assertTrue(scene_state.in_attr_surgery())
        self.assertFalse(scene_state.in_attr_surgery_block())
        with self.assertRaises(ValueError):
            node.add_input_attr("diff_storage", "float")

    def test_reserved_stored_var_raises_in_the_trailing_grace(self):
        from mpynode._common.lifecycle import scene_state
        from mpynode._common.storedvars import stored_vars_api

        node = self._make("mPyMesh")
        scene_state.begin_attr_surgery()
        try:
            stored_vars_api.add_variable(node.get_name(), "diff_storage", 1.0)
        finally:
            scene_state.end_attr_surgery()
        self.assertTrue(scene_state.in_attr_surgery())
        with self.assertRaises(ValueError):
            stored_vars_api.add_variable(
                node.get_name(), "get_plug_proxy", 1.0)


if __name__ == "__main__":
    unittest.main()
