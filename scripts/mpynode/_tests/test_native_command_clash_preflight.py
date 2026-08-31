"""Controller-level command-name clash pre-flight.

Maya registers a given command name exactly once, so two node types that both
declare ``@maya_command def add_targets`` cannot live in one plugin. The bundler
has always refused this -- but it reads the name out of GENERATED C++, so it can
only refuse AFTER every node has been ported. A 44-node mega run spent 83 minutes
porting before dying at assembly.

The spec already carries the FINAL command names (``creates=True`` is uniquified
by ``resolve_create_command_names`` back at extraction), so ``compile_plugin``
can answer the same question up front, for free. These tests pin that it does --
and, just as importantly, that it does not answer it for nodes the portability
gate was going to drop anyway, which would reject builds that succeed today.

No test here reaches codegen: the clash cases return AT the pre-flight, and the
non-clash cases are forced unportable so they drop at the gate immediately after
it. Gated on a working native toolchain, since that pre-flight runs first.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


_CLASH_SRC = '''
@maya_command
def add_targets(self, count: int = 1):
    """A PLAIN @maya_command -- its name is the function name, verbatim."""
    return count
'''

_OTHER_SRC = '''
@maya_command
def load_shapes(self, count: int = 1):
    """A different plain command name, so nothing collides."""
    return count
'''


class TestCommandClashPreflight(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.native.toolchain import toolchain
        from mpynode.native.toolchain import compile_controller as cc

        if not toolchain.check_toolchain(cc._MAYA_DEFAULT).get("ok"):
            self.skipTest("no native toolchain on this host")

    def _make_pair(self, src_a, src_b, portable):
        """Two nodes of two DIFFERENT Classes -> two native types.

        Different Classes matter: two instances of ONE Class collapse to a single
        representative, which would hide a clash rather than test it.

        ``portable`` is forced either way rather than left to extraction, because
        it is the exact field the pre-flight filters on. Forced True is safe: a
        clash returns at the pre-flight, so nothing is ever codegen'd.
        """
        from mpynode import MPyNode
        from mpynode._common.io.user_classes import synthesize, dotted_path
        from mpynode.native.spec import spec_extractor

        specs = []
        for cls, name, src in (("ClashProbeOne", "ccClashA", src_a),
                               ("ClashProbeTwo", "ccClashB", src_b)):
            synthesize(cls, "mPyNode")
            node = MPyNode.create(name=name)
            node.set_compute_expression("out = 1")
            node.set_methods_source(src)
            node.set_py_class(dotted_path(cls))
            specs.append(spec_extractor.extract_spec(node.get_name()))

        # Two distinct native types is the premise of the whole test.
        self.assertNotEqual(specs[0]["suggested"]["node_type_name"],
                            specs[1]["suggested"]["node_type_name"])
        for s in specs:
            s["portability"] = ({"portable": True, "blockers": []} if portable
                                else {"portable": False,
                                      "blockers": ["test-forced"]})
        return specs

    def _compile(self, specs):
        from mpynode.native.toolchain import compile_controller as cc

        events = []
        res = cc.compile_plugin(
            specs, "clashProbePlug", tempfile.mkdtemp(prefix="clashprobe_"),
            strict=False, verify=False, reuse_cache=False,
            complete_fn=lambda *a, **k: "",
            progress_cb=lambda ev: events.append(ev))
        return res, events

    def _clash_events(self, events):
        return [e for e in events
                if e.get("stage") == "preflight" and e.get("status") == "fail"
                and "command name" in (e.get("detail") or "")]

    def test_the_fixture_really_produces_the_same_command_name(self):
        """Guard the premise: if extraction stopped naming plain commands after
        the function, every assertion below would pass for the wrong reason."""
        specs = self._make_pair(_CLASH_SRC, _CLASH_SRC, portable=True)
        for spec in specs:
            names = [c.get("name") for c in (spec.get("commands") or [])]
            self.assertIn("add_targets", names)

    def test_a_clash_aborts_before_any_port(self):
        specs = self._make_pair(_CLASH_SRC, _CLASH_SRC, portable=True)
        res, events = self._compile(specs)

        self.assertFalse(res["ok"])
        blob = " ".join(str(e) for e in (res.get("errors") or []))
        self.assertIn("add_targets", blob)
        self.assertIn("same command name", blob)
        # Both owners are named, so the user knows which two to reconcile.
        for spec in specs:
            self.assertIn(spec["suggested"]["node_type_name"], blob)

        # It failed at the PRE-FLIGHT, not at assembly: no node was ever ported.
        self.assertTrue(self._clash_events(events),
                        "expected a preflight clash event")
        self.assertFalse([e for e in events if e.get("stage") == "port"],
                         "no node may be ported once a clash is known")

    def test_distinct_command_names_pass_the_gate(self):
        """The converse -- otherwise the test above would pass even if the gate
        rejected every multi-node build."""
        specs = self._make_pair(_CLASH_SRC, _OTHER_SRC, portable=False)
        res, events = self._compile(specs)

        self.assertFalse(self._clash_events(events))
        blob = " ".join(str(e) for e in (res.get("errors") or []))
        self.assertNotIn("same command name", blob)
        # It got PAST the clash gate and reached the ordinary portability drop.
        reasons = " ".join(r.get("build_reason", "") or "" for r in res["nodes"])
        self.assertIn("test-forced", reasons)

    def test_an_unportable_clash_is_not_the_preflights_business(self):
        """A node the portability gate drops emits no registerCommand, so the
        bundler never counted it. The pre-flight must not be stricter than the
        failure it is front-running, or it rejects builds that pass today."""
        specs = self._make_pair(_CLASH_SRC, _CLASH_SRC, portable=False)
        res, events = self._compile(specs)

        self.assertFalse(self._clash_events(events),
                         "an unportable node must not trip the clash gate")
        blob = " ".join(str(e) for e in (res.get("errors") or []))
        self.assertNotIn("same command name", blob)
        # Both dropped for the ordinary reason, exactly as before the gate.
        reasons = " ".join(r.get("build_reason", "") or "" for r in res["nodes"])
        self.assertIn("test-forced", reasons)


if __name__ == "__main__":
    unittest.main()
