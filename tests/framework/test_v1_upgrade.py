"""Upgrading a v1 node that arrived through a scene open, in place.

Companion to ``test_v1_import``, which covers reading a ``.ma`` as text. This
module covers the other path: v2 registers the same node TYPE name as v1, so
Maya builds a v2 ``mPyNode`` and replays v1's ``setAttr`` calls at it, and the
node has to be converted where it sits.

Every case here corresponds to something that actually went wrong when a real
upstream scene (``quaternionSpineNode.ma``) was opened, and the theme is one
mistake made twice: **v1 and v2 share a plug NAME while disagreeing about what
goes in it.** The payload therefore survives the open looking perfectly intact
and is read by v2 as nothing at all, which is much harder to notice than a
plug that failed to load.

  * ``_inputAttrs`` / ``_outputAttrs`` -- v1 wrote base64+pickle of
    ``{name: [type]}``, v2 writes plain JSON of
    ``{name: {attr_type, is_array, order}}``. Symptom: the attributes were
    present on the Maya node (``addAttr`` is type-agnostic, so they loaded)
    but Node Designer's Attributes tab listed none of them, and
    ``self.<attr>`` did not resolve.
  * ``_storedVarNames`` -- v1 pickled a list, v2 comma-joins a string. v2
    gates persistence on membership of that list, so every stored variable
    read back as absent.

The second one also had an ordering component, pinned by
``TestTheCallbackOrdering`` below, which is the only test here that can catch
it: the store hydrates ``_storedVarsData`` and then deliberately CLEARS the
plug, so an upgrade sequenced after that finds the v1 payload already gone.
"""

from __future__ import annotations

import base64
import json
import pickle
import unittest

import maya.cmds as mc

from mpynode._common.io import v1_upgrade as U
from mpynode.wrappers._mpy_node import MPyNode
from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _v1_blob(obj):
    """v1's ``_dumpPickle``: base64 of a pickle, no compression anywhere."""
    return base64.encodebytes(pickle.dumps(obj, protocol=2)).decode()


_TYPE_FLAGS = {
    "float":  {"attributeType": "double"},
    "int":    {"attributeType": "long"},
    "bool":   {"attributeType": "bool"},
    "enum":   {"attributeType": "enum", "enumName": "0:1"},
    "matrix": {"dataType": "matrix"},
    "vector": {"attributeType": "double3"},
}


def _add_plug(node, name, typ, is_array=False, out=False):
    """Add the physical attribute the way the ``.ma``'s addAttr line would."""
    kw = dict(_TYPE_FLAGS.get(typ, {"attributeType": "double"}))
    if is_array:
        kw["multi"] = True
    mc.addAttr(node, longName=name, **kw)
    if typ == "vector":
        for ax in "XYZ":
            mc.addAttr(node, longName=name + ax, attributeType="double",
                       parent=name)


def _make_v1_node(inputs=None, outputs=None, stored=None,
                  expression="outValue = inValue * 2", arrays=(), name=None):
    """A v2 node carrying a v1 payload -- what a v1 scene open produces.

    Deliberately built by writing v1-format blobs onto a freshly created v2
    node rather than by opening a fixture scene: the real fixtures are 10 MB
    and live in another repository, and this reproduces the state that matters.
    """
    inputs  = {"inValue": "float"} if inputs is None else inputs
    outputs = {"outValue": "float"} if outputs is None else outputs

    node = MPyNode.create(name=name or "v1upgrade")._name
    for attr, typ in inputs.items():
        _add_plug(node, attr, typ, is_array=attr in arrays)
    for attr, typ in outputs.items():
        _add_plug(node, attr, typ, is_array=attr in arrays, out=True)

    mc.setAttr(node + "." + U.LEGACY_PLUG, expression, type="string")
    mc.setAttr(node + "._inputAttrs",
               _v1_blob({k: [v] for k, v in inputs.items()}), type="string")
    mc.setAttr(node + "._outputAttrs",
               _v1_blob({k: [v] for k, v in outputs.items()}), type="string")
    if stored:
        mc.setAttr(node + "._storedVarsData", _v1_blob(dict(stored)),
                   type="string")
        mc.setAttr(node + "._storedVarNames", _v1_blob(sorted(stored)),
                   type="string")
    return node


class _Base(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)


class TestThePendingGate(_Base):
    """The sweep runs on every open, so the gate has to be exact and
    idempotent. It needs no marker attribute: a non-empty legacy
    ``expression`` with an empty ``_computeSource`` is a state no v2-authored
    node can be in, because v2 never writes ``expression`` at all."""

    def test_a_v1_payload_is_pending(self):
        self.assertTrue(U.is_pending(_make_v1_node()))

    def test_a_node_authored_in_v2_is_not_pending(self):
        n = MPyNode.create(name="native")
        n.set_compute_expression("pass")
        self.assertFalse(U.is_pending(n._name))

    def test_an_upgraded_node_is_no_longer_pending(self):
        node = _make_v1_node()
        U.upgrade_node(node)
        self.assertFalse(U.is_pending(node))

    def test_the_sweep_is_idempotent(self):
        node = _make_v1_node()
        first, _ = U.upgrade_scene()
        second, _ = U.upgrade_scene()
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [], "a second sweep re-converted the node")
        self.assertEqual(U.find_pending([node]), [])


class TestTheAttributeRegistry(_Base):
    """The reported bug: plugs on the node, nothing in the Attributes tab.

    Asserted through ``get_input_attr_map`` / ``get_output_attr_map`` -- the
    Attributes tab's own source of truth -- rather than by reading the plug
    back, because reading the plug is exactly the check that passed while the
    feature was broken.
    """

    def test_v2_can_read_the_inputs_after_an_upgrade(self):
        node = _make_v1_node(inputs={"a": "float", "m": "matrix"},
                             outputs={"out": "vector"},
                             expression="out = [a, a, a]")
        U.upgrade_node(node)
        self.assertEqual(sorted(MPyNode(node).get_input_attr_map()), ["a", "m"])

    def test_v2_can_read_the_outputs_after_an_upgrade(self):
        node = _make_v1_node(inputs={"a": "float"},
                             outputs={"out": "vector", "flag": "bool"},
                             expression="out = [a, a, a]\nflag = True")
        U.upgrade_node(node)
        self.assertEqual(sorted(MPyNode(node).get_output_attr_map()),
                         ["flag", "out"])

    def test_v2_reads_nothing_before_the_upgrade(self):
        # Pins the bug itself: the v1 blob is present and undamaged, and v2
        # still sees an empty node. Without this the fix looks unnecessary.
        node = _make_v1_node(inputs={"a": "float"})
        self.assertTrue(mc.getAttr(node + "._inputAttrs").strip())
        self.assertEqual(MPyNode(node).get_input_attr_map(), {})

    def test_the_registry_is_json_not_a_pickle_blob(self):
        node = _make_v1_node(inputs={"a": "float"})
        U.upgrade_node(node)
        table = json.loads(mc.getAttr(node + "._inputAttrs"))
        self.assertEqual(table["a"]["attr_type"], "float")

    def test_is_array_comes_from_the_live_plug(self):
        # v1's schema cannot express it: a multi is stored as ['matrix'] just
        # like a single. The plug is the only witness.
        node = _make_v1_node(inputs={"single": "matrix", "many": "matrix"},
                             outputs={"out": "float"},
                             arrays=("many",), expression="out = 1.0")
        U.upgrade_node(node)
        table = MPyNode(node).get_input_attr_map()
        self.assertTrue(table["many"]["is_array"])
        self.assertFalse(table["single"]["is_array"])

    def test_order_follows_the_v1_table(self):
        node = _make_v1_node(inputs={"first": "float", "second": "float"},
                             outputs={"out": "float"},
                             expression="out = first + second")
        U.upgrade_node(node)
        table = MPyNode(node).get_input_attr_map()
        self.assertLess(table["first"]["order"], table["second"]["order"])

    def test_a_declared_plug_that_is_not_on_the_node_is_reported(self):
        node = _make_v1_node(inputs={"a": "float"})
        # v1's _loadPickle swallowed errors, so a table can outlive its plugs.
        mc.setAttr(node + "._inputAttrs",
                   _v1_blob({"a": ["float"], "ghost": ["float"]}),
                   type="string")
        report = U.upgrade_node(node)
        self.assertEqual(report["missing_plugs"], ["ghost"])
        self.assertNotIn("ghost", MPyNode(node).get_input_attr_map())


class TestStoredVariables(_Base):
    """``_storedVarsData`` is base64+pickle on both sides, so the VALUES
    survive -- but ``_storedVarNames`` is a comma-joined string in v2 where v1
    pickled a list, and v2 gates persistence on that list."""

    def test_a_v1_stored_variable_survives_the_upgrade(self):
        node = _make_v1_node(stored={"defaultLength": 12.0})
        U.upgrade_node(node)
        self.assertEqual(MPyNode(node).get_variables(),
                         {"defaultLength": 12.0})

    def test_the_names_plug_is_rewritten_in_v2_format(self):
        node = _make_v1_node(stored={"defaultLength": 12.0})
        U.upgrade_node(node)
        self.assertEqual(MPyNode(node).get_variable_names(), ["defaultLength"])

    def test_v2_reads_no_names_from_the_v1_blob(self):
        # The blob has no commas, so v2's split yields one garbage "name" --
        # which is worse than nothing, because it shows up in the UI.
        node = _make_v1_node(stored={"defaultLength": 12.0})
        self.assertNotIn("defaultLength", MPyNode(node).get_variable_names())

    def test_a_node_with_no_stored_vars_is_fine(self):
        node   = _make_v1_node()
        report = U.upgrade_node(node)
        self.assertEqual(report["stored_vars"], {})
        self.assertNotIn("stored_var_error", report)


class TestTheExpression(_Base):

    def test_the_compute_is_selfified(self):
        node = _make_v1_node()
        U.upgrade_node(node)
        compute = MPyNode(node).get_compute_expression()
        self.assertIn("self.outValue", compute)
        self.assertIn("self.inValue", compute)

    def test_imports_and_defs_land_in_init(self):
        node = _make_v1_node(
            expression="import math\n\ndef f(x):\n    return x\n"
                       "\noutValue = f(inValue)")
        U.upgrade_node(node)
        w = MPyNode(node)
        self.assertIn("import math", w.get_init_expression())
        self.assertIn("def f", w.get_init_expression())
        self.assertNotIn("def f", w.get_compute_expression())

    def test_enum_labels_are_invented_and_applied_to_the_plug(self):
        # v1 stored ['enum'] and no labels at all; v2 rejects a label-less
        # enum. The plug already exists, so this is a relabel, not an add.
        node = _make_v1_node(inputs={"mode": "enum"},
                             outputs={"out": "float"},
                             expression="out = 1.0 if mode == 2 else 0.0")
        report = U.upgrade_node(node)
        self.assertEqual(report["synthesized_enums"]["mode"], ["0", "1", "2"])
        self.assertEqual(
            mc.attributeQuery("mode", node=node, listEnum=True),
            ["0:1:2"])

    def test_the_legacy_payload_is_kept_by_default(self):
        # An audit trail costs one hidden string; the gate is _computeSource
        # being empty, so idempotence does not depend on clearing it.
        node = _make_v1_node()
        U.upgrade_node(node)
        self.assertTrue(mc.getAttr(node + "." + U.LEGACY_PLUG).strip())

    def test_clear_legacy_empties_the_carrier(self):
        node = _make_v1_node()
        U.upgrade_node(node, clear_legacy=True)
        self.assertEqual(mc.getAttr(node + "." + U.LEGACY_PLUG).strip(), "")


class TestTheReport(_Base):
    """A silent 90% conversion is worse than a noisy one, so the report is
    part of the deliverable and gets asserted like one."""

    def test_the_summary_names_what_the_user_must_act_on(self):
        node = _make_v1_node(inputs={"mode": "enum", "m": "matrix"},
                             outputs={"out": "float"},
                             # om.-qualified: a real api2 call, so it is
                             # reported rather than rewritten.
                             expression="out = om.MVector(m)[0] if mode else 0.0")
        line = U.summarize(*U.upgrade_scene())[0]
        self.assertIn(node,         line)
        self.assertIn("registered", line)
        self.assertIn("mode",       line)  # invented enum labels
        self.assertIn("MVector",    line)  # v1 api objects
        # The api-object note no longer claims the maths is broken: the two
        # mismatches that actually broke a converted node are auto-fixed, so
        # what is left is a performance / C++-lowering remark.
        self.assertIn("still constructs", line)
        self.assertIn("lowers to C++", line)

    def test_the_summary_reports_the_auto_fixes(self):
        node = _make_v1_node(
            inputs={"m": "matrix"}, outputs={"out": "vector"},
            expression="out = om.MTransformationMatrix(m).translation(0)")
        line = U.summarize(*U.upgrade_scene())[0]
        self.assertIn("auto-fixed 1 MatrixView call", line)
        self.assertIn("asTransformationMatrix", line)
        self.assertIn("4-component writes to out", line)
        self.assertIn("_v1_vec3", line)

    def test_a_failure_is_reported_and_never_raised(self):
        node = _make_v1_node(expression="def (:")   # unparseable
        reports, failures = U.upgrade_scene()
        self.assertEqual(reports, [])
        self.assertEqual([n for n, _ in failures], [node])
        self.assertIn("could NOT upgrade", U.summarize(reports, failures)[0])


class TestTheCallbackOrdering(unittest.TestCase):
    """The upgrade MUST be sequenced before the stored-var hydration.

    ``stored_var_store.load_and_clear_all`` reads ``_storedVarsData`` into an
    in-memory cache and then CLEARS the plug, on the grounds that the cache is
    authoritative for the rest of the session. An upgrade placed after it
    therefore reads an empty plug and drops every stored variable -- silently,
    because the values are simply not there to convert. The upgrade also
    cannot fall back to the cache, since hydration keys off ``_storedVarNames``
    in v2's format.

    This is a source-order assertion because there is no way to observe the
    ordering from the outside: both orderings produce a node that looks
    correct apart from its missing variables.
    """

    def _source(self):
        import inspect

        from mpynode._common.lifecycle import scene_callbacks

        return inspect.getsource(scene_callbacks)

    def _assert_upgrade_precedes_hydration(self, func_name):
        import inspect

        from mpynode._common.lifecycle import scene_callbacks

        src     = inspect.getsource(getattr(scene_callbacks, func_name))
        up      = src.find("_upgrade_v1_nodes()")
        hydrate = src.find("load_and_clear_all()")
        self.assertNotEqual(up, -1, "%s no longer sweeps v1 nodes" % func_name)
        self.assertNotEqual(hydrate, -1,
                            "%s no longer hydrates stored vars" % func_name)
        self.assertLess(up, hydrate,
                        "%s hydrates stored vars BEFORE upgrading v1 nodes, "
                        "which clears the v1 payload and loses every stored "
                        "variable" % func_name)

    def test_scene_open_upgrades_before_hydrating(self):
        self._assert_upgrade_precedes_hydration("_on_scene_opened")

    def test_after_import_upgrades_before_hydrating(self):
        self._assert_upgrade_precedes_hydration("_on_after_import")

    def test_reference_deliberately_does_not_upgrade(self):
        # A referenced node's plugs are locked, so the rewrite could not be
        # written; the edit would not belong to this scene either.
        import inspect

        from mpynode._common.lifecycle import scene_callbacks

        src = inspect.getsource(scene_callbacks._on_after_reference)
        self.assertNotIn("_upgrade_v1_nodes", src)


class TestTheLegacyPlugNameIsReserved(unittest.TestCase):
    """``expression`` was a free name until the v1 carrier plug claimed it on
    every mpy type, so a user attribute of that name now collides with a real
    plug."""

    def test_expression_is_refused_with_a_reason(self):
        from mpynode._common.interface import reserved_names

        reason = reserved_names.check_reserved_name("expression",
                                                    node_type="mPyNode")
        self.assertTrue(reason)
        self.assertIn("v1", reason)

    def test_an_ordinary_name_is_still_free(self):
        from mpynode._common.interface import reserved_names

        self.assertIsNone(
            reserved_names.check_reserved_name("myThing", node_type="mPyNode"))


if __name__ == "__main__":
    unittest.main()


def _make_v1_owned_node(name="v1owned"):
    """A node shaped like one served by v1's OWN plug-in.

    The distinguishing feature is a NEGATIVE: no ``_computeSource`` plug,
    because v1 does not declare one anywhere in its source tree. Built on a
    plain ``network`` node rather than an ``mPyNode``, since a real v2
    ``mPyNode`` always has ``_computeSource`` and so cannot reproduce the
    state -- which is the point of using it as the gate.
    """
    node = mc.createNode("network", name=name)
    for plug in ("expression", "_inputAttrs", "_outputAttrs",
                 "_storedVarNames", "_storedVarsData"):
        mc.addAttr(node, longName=plug, dataType="string")
    mc.setAttr(node + ".expression", "outputTranslate = inputCurve * 2",
               type="string")
    mc.setAttr(node + "._inputAttrs", _v1_blob({"inputCurve": ["nurbsCurve"]}),
               type="string")
    mc.setAttr(node + "._outputAttrs",
               _v1_blob({"outputTranslate": ["vector"]}), type="string")
    return node


class TestStandingDownWhenV1OwnsTheNode(_Base):
    """The sweep must not touch a node v1 is serving.

    v1 and v2 register the same node TYPE name, so whichever plug-in loads
    first wins -- and every v1 scene contains
    ``requires -nodeType "mPyNode" "mpynode_plugin.py"``, which loads v1 by
    name. When v1 wins, v2's registration fails and the scene's nodes are v1
    nodes running v1's compute. Converting one is destructive rather than
    merely useless: rewriting ``_inputAttrs`` into v2's JSON leaves v1 unable
    to build its expression locals, and its compute dies with
    ``NameError: name 'inputCurve' is not defined``.

    Observed for real, which is why these tests exist: a v1 scene opened
    correctly under v1, then the Designer was launched (installing v2's scene
    callbacks), and the next open of that scene broke the node.
    """

    def test_a_v1_owned_node_is_not_pending(self):
        self.assertFalse(U.is_pending(_make_v1_owned_node()))

    def test_the_gate_is_plug_EXISTENCE_not_emptiness(self):
        # The bug in one line: `_get` returns "" for both "absent" and
        # "empty", so the original gate could not tell the two cases apart.
        node = _make_v1_owned_node()
        self.assertEqual(U._get(node, "_computeSource"), "")
        self.assertFalse(U._has_plug(node, "_computeSource"))
        # ...whereas a v2 node has the plug, empty.
        v2 = _make_v1_node()
        self.assertTrue(U._has_plug(v2, "_computeSource"))
        self.assertEqual(U._get(v2, "_computeSource"), "")
        self.assertTrue(U.is_pending(v2))

    def test_the_sweep_leaves_a_v1_owned_node_byte_identical(self):
        node = _make_v1_owned_node()
        plugs = ("expression", "_inputAttrs", "_outputAttrs",
                 "_storedVarNames", "_storedVarsData")
        before = {p: mc.getAttr(node + "." + p) for p in plugs}
        reports, failures = U.upgrade_scene([node])
        self.assertEqual((reports, failures), ([], []))
        after = {p: mc.getAttr(node + "." + p) for p in plugs}
        self.assertEqual(before, after)

    def test_find_foreign_names_it(self):
        node = _make_v1_owned_node()
        self.assertEqual(U.find_foreign([node]), [node])

    def test_find_foreign_ignores_a_v2_owned_node(self):
        self.assertEqual(U.find_foreign([_make_v1_node()]), [])

    def test_find_foreign_ignores_a_node_with_no_v1_payload(self):
        node = mc.createNode("network", name="innocent")
        self.assertEqual(U.find_foreign([node]), [])


class TestTheConflictWarning(_Base):
    """Silence is the worst outcome here: v2's plug-in loads, its node type
    does not register, every Designer panel reads an empty node, and nothing
    says why. So the stand-down is announced -- once."""

    def setUp(self):
        super().setUp()
        from mpynode._common.lifecycle import scene_callbacks

        self._sc                            = scene_callbacks
        self._saved                         = scene_callbacks._V1_CONFLICT_WARNED
        scene_callbacks._V1_CONFLICT_WARNED = False
        self.addCleanup(setattr, scene_callbacks, "_V1_CONFLICT_WARNED",
                        self._saved)

    def _sweep(self, nodes):
        import io
        from contextlib import redirect_stderr

        buf = io.StringIO()
        with redirect_stderr(buf):
            self._sc._upgrade_v1_nodes(nodes)
        return buf.getvalue()

    def test_it_fires_and_explains_the_collision(self):
        node = _make_v1_owned_node()
        out  = self._sweep([node])
        self.assertIn("STANDING DOWN", out)
        self.assertIn(node, out)
        self.assertIn("mpynode_plugin.py", out)   # what to move
        self.assertIn("mpylib", out)

    def test_it_fires_only_once_per_session(self):
        node = _make_v1_owned_node()
        self.assertIn("STANDING DOWN", self._sweep([node]))
        self.assertNotIn("STANDING DOWN", self._sweep([node]))

    def test_a_healthy_v2_scene_says_nothing_about_a_conflict(self):
        out = self._sweep([_make_v1_node()])
        self.assertNotIn("STANDING DOWN", out)
        self.assertIn("upgraded v1 node", out)
