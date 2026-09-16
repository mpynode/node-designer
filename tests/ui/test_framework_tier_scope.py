"""The Framework tab is TIER-SCOPED, and this locks the reason why.

`self` is not one object in this product. Init / Compute / Viewport get a
SelfProxy; the API tab (setup / demo / @maya_command bodies, and the Methods
module it absorbed) gets the real WRAPPER. The two surfaces are DISJOINT, so a
panel that lists both while you edit one is listing things that raise.

The panel used to show all of them on every tab: 13 authoring methods that
AttributeError in a compute, and four VP2-only handles that AttributeError
outside the Viewport tier. These tests MEASURE the reachability the scope table
claims, so the table cannot drift back into lying.
"""
from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init

standalone_init()
ensure_plugins_loaded()


def _compute_probe(node, names):
    """Run ``getattr(self, n)`` for each name INSIDE the node's compute and
    return {name: True if it resolved}. The only honest way to ask what a tier
    can reach is to ask from inside that tier.

    The result comes back through USER STORAGE (``self.probeResult = ...``,
    SelfProxy Tier 4), read on the wrapper side with ``get_variables()``."""
    import json

    node.set_compute_expression(
        "import json\n"
        "_r = {}\n"
        "for _n in %r:\n"
        "    try:\n"
        "        getattr(self, _n)\n"
        "        _r[_n] = True\n"
        "    except Exception:\n"
        "        _r[_n] = False\n"
        "self.probeResult = json.dumps(_r)\n"
        "self.outColor = (0.0, 0.0, 0.0)\n"
        "self.outAlpha = 1.0\n" % (list(names),))
    mc.dgdirty(node.get_name() + ".outColor")
    mc.getAttr(node.get_name() + ".outColor")
    raw = (node.get_variables() or {}).get("probeResult")
    if not raw:
        raise AssertionError(
            "compute probe did not run -- no probeResult stored (names=%r)"
            % (list(names),))
    return json.loads(raw)


class TestSurfacesAreDisjoint(unittest.TestCase):
    """The premise of the whole feature: wrapper and SelfProxy do not overlap."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.node = MPyFile.create(name="tierScope#")

    def test_blessed_methods_do_not_resolve_on_the_wrapper(self):
        # If this ever passes, self.read_texture() becomes legal in the API tab
        # and the Methods group should be shown there too.
        for name in ("read_texture", "sample_texture"):
            self.assertFalse(
                hasattr(self.node, name),
                "%s now resolves on the wrapper -- the API tab could show the "
                "Methods group; revisit framework_scope_for()" % name)

    def test_slots_do_not_resolve_on_the_wrapper(self):
        for name in ("time", "shader"):
            self.assertFalse(
                hasattr(self.node, name),
                "%s now resolves on the wrapper; revisit the API tier scope"
                % name)

    def test_authoring_methods_do_resolve_on_the_wrapper(self):
        for name in ("has_osl_expression", "get_file_name",
                     "set_viewport_expression"):
            self.assertTrue(hasattr(self.node, name),
                            "%s must be callable from the API tab" % name)


class TestComputeTierReach(unittest.TestCase):
    """What a Compute expression can actually name."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.node = MPyFile.create(name="tierReach#")

    def test_blessed_methods_and_time_reachable(self):
        got = _compute_probe(self.node, ["read_texture", "sample_texture",
                                         "time", "fileName"])
        self.assertTrue(got.get("read_texture"),   got)
        self.assertTrue(got.get("sample_texture"), got)
        self.assertTrue(got.get("time"),           got)
        self.assertTrue(got.get("fileName"),       got)

    def test_viewport_only_slots_are_NOT_reachable(self):
        # The four the panel must hide outside the Viewport tab.
        got = _compute_probe(self.node, ["shader", "mappings",
                                         "texture_manager", "state_manager"])
        for name, ok in got.items():
            self.assertFalse(ok, "%s resolved in Compute -- it is declared "
                                 "VIEWPORT_ONLY_SLOTS" % name)

    def test_authoring_methods_are_NOT_reachable(self):
        got = _compute_probe(self.node, ["has_osl_expression",
                                         "set_file_name", "reseed_defaults"])
        for name, ok in got.items():
            self.assertFalse(ok, "%s resolved in Compute -- authoring methods "
                                 "are wrapper-only" % name)


class TestScopeTable(unittest.TestCase):
    """framework_scope_for() must encode exactly the measured reality above."""

    def _scope(self, tier):
        from mpynode.ui.widgets.plug_tree_walker import framework_scope_for

        return framework_scope_for(tier)

    def test_expression_tiers_never_show_authoring(self):
        for tier in ("Init", "Compute", "Viewport", "OSL"):
            self.assertFalse(self._scope(tier)["authoring"],
                             "%s must not list Authoring Methods" % tier)

    def test_api_tier_shows_only_authoring(self):
        s = self._scope("API")
        self.assertTrue(s["authoring"])
        self.assertFalse(s["methods"], "Methods raise on the wrapper")
        self.assertFalse(s["slots"], "Slots raise on the wrapper")
        self.assertFalse(s["draw"])

    def test_init_reaches_nothing_and_says_so(self):
        # Init resolves plugs only -- no blessed methods, no slots (measured in
        # TestInitTierReach below).
        s = self._scope("Init")
        self.assertFalse(s["methods"])
        self.assertFalse(s["slots"])
        self.assertTrue(s["note"], "an empty panel must explain itself")

    def test_osl_reaches_nothing_and_says_so(self):
        s = self._scope("OSL")
        self.assertFalse(any((s["methods"], s["slots"], s["authoring"],
                              s["draw"])))
        self.assertIn("shader language", s["note"])

    def test_compute_and_viewport_show_the_expression_surface(self):
        for tier in ("Compute", "Viewport"):
            s = self._scope(tier)
            self.assertTrue(s["methods"], tier)
            self.assertTrue(s["slots"], tier)

    def test_unknown_tier_falls_back_to_compute(self):
        # A caller that cannot name the tier gets a useful panel, not an empty
        # one.
        self.assertEqual(self._scope(None), self._scope("Compute"))
        self.assertEqual(self._scope(""), self._scope("Compute"))


class TestInitTierReach(unittest.TestCase):
    """Init is NOT Compute: its `self` resolves plugs and nothing else."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile

        self.node = MPyFile.create(name="tierInit#")

    def test_init_sees_plugs_but_not_methods_or_slots(self):
        # The probe runs in INIT; the compute only ferries the result out (an
        # Init global is reachable by bare name from the compute, the same way
        # the shipped templates call their Init helpers).
        self.node.set_init_expression(
            "initProbe = {}\n"
            "for _n in ('fileName', 'read_texture', 'time'):\n"
            "    try:\n"
            "        getattr(self, _n)\n"
            "        initProbe[_n] = True\n"
            "    except Exception:\n"
            "        initProbe[_n] = False\n")
        self.node.set_compute_expression(
            "import json\n"
            "self.probeResult = json.dumps(initProbe)\n"
            "self.outColor = (0.0, 0.0, 0.0)\n"
            "self.outAlpha = 1.0\n")
        mc.dgdirty(self.node.get_name() + ".outColor")
        mc.getAttr(self.node.get_name() + ".outColor")
        import json
        raw = (self.node.get_variables() or {}).get("probeResult")
        self.assertTrue(raw, "init probe did not reach the compute")
        got = json.loads(raw)
        self.assertTrue(got["fileName"], "Init resolves plugs")
        self.assertFalse(got["read_texture"],
                         "blessed methods are not bound during Init")
        self.assertFalse(got["time"], "slots are not bound during Init")


if __name__ == "__main__":
    unittest.main()
