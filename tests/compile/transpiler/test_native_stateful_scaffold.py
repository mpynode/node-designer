"""Native stateful-var scaffold: persistent ``self.<name>`` latched across evals.

An interpreted MPyNode may carry per-instance state between compute() calls -- a
latched rest length, a running accumulator, a solver carry-over -- by writing an
UNDECLARED ``self.<name>`` and reading it back on a later eval. A compiled
MPxNode::compute() is stateless per call, so codegen must give such vars a
persistent home. This suite proves the deterministic scaffold:

  * py_to_cpp lowers ``hasattr(self,'X')`` -> ``st.X_isset``, a write -> ``st.X =
    ...; st.X_isset = true;`` and a read -> ``st.X`` (member type discovered from
    the first write);
  * nd_lower emits the per-node registry preamble (a ``this``-keyed static vector,
    generalizing the spring_chain pattern) so the members survive between evals;
  * codegen ships it as PURE C++ (no AI PORT region); and, decisively,
  * the COMPILED node accumulates correctly across MANY evals with changing input
    -- the exact multi-eval behaviour a single-eval parity check cannot see.

The compile+eval test SKIPs (never fails) on a host with no C++ toolchain / Maya
devkit, matching the other native e2e suites.
"""
from __future__ import annotations

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_ACCUM_COMPUTE = (
    "if not hasattr(self, 'acc'):\n"
    "    self.acc = 0.0\n"
    "self.acc = self.acc + self.inValue\n"
    "self.out = self.acc\n"
)


def _accum_spec():
    """Build the accumulator node in-scene and extract its porter spec."""
    import maya.cmds as cmds
    from mpynode import MPyNode
    from mpynode.native.spec import spec_extractor

    cmds.file(new=True, force=True)
    w = MPyNode.create(name="accum#")
    w.add_input_attr("inValue", "double")
    w.add_output_attr("out", "double")
    w.set_compute_expression(_ACCUM_COMPUTE)
    spec = spec_extractor.extract_spec(w.get_name())
    spec["suggested"]["node_type_name"] = "accumNative"
    return spec


# ARRAY persistent state: the carry is a whole numpy array latched across evals
# (a running per-element sum). This is the #99 generalisation of the scalar case:
# the state member is an nd::Array<double>, not a POD.
_ARR_ACCUM_COMPUTE = (
    "import numpy as np\n"
    "if not hasattr(self, 'acc'):\n"
    "    self.acc = self.inArray * 0.0\n"      # zero-seed, same shape as input
    "self.acc = self.acc + self.inArray\n"
    "self.outArray = self.acc\n"
)


def _arr_accum_spec():
    """Build the ARRAY accumulator node in-scene and extract its porter spec."""
    import maya.cmds as cmds
    from mpynode import MPyNode
    from mpynode.native.spec import spec_extractor

    cmds.file(new=True, force=True)
    w = MPyNode.create(name="arracc#")
    w.add_input_attr("inArray", "double", is_array=True)
    w.add_output_attr("outArray", "double", is_array=True)
    w.set_compute_expression(_ARR_ACCUM_COMPUTE)
    spec = spec_extractor.extract_spec(w.get_name())
    spec["suggested"]["node_type_name"] = "arrAccNative"
    return spec


class TestTranspilerStatefulLowering(unittest.TestCase):
    """py_to_cpp maps the persistent-state idiom to per-node ``st.`` members."""

    def _lower(self, source, state_vars, env=None, writers=None):
        from mpynode.native.compiler import py_to_cpp
        from mpynode.native.compiler.py_to_cpp import scalar_t

        if env is None:
            env = {"self.inValue": scalar_t("double")}
        if writers is None:
            writers = {"self.out": lambda v: ["ndout_self_out = %s;" % v.code]}
        return py_to_cpp.transpile_compute_block(
            source, env, writers, state_vars=state_vars)

    def test_hasattr_read_write_lower(self):
        res, written, _ = self._lower(_ACCUM_COMPUTE, {"acc"})
        body = "\n".join(res.body_lines)
        self.assertIn("st.acc_isset", body)          # hasattr(self,'acc')
        self.assertIn("st.acc = ", body)             # write
        self.assertIn("st.acc_isset = true;", body)  # write flags set
        self.assertIn("ndout_self_out = st.acc;", body)  # read feeds the output
        # member type discovered as a scalar double from the first write.
        self.assertIn("acc", res.state_members)
        self.assertEqual(res.state_members["acc"].kind, "scalar")
        self.assertEqual(res.state_members["acc"].dtype, "double")

    def test_hasattr_on_undeclared_nonstate_rejects(self):
        # hasattr on something that is neither a state var nor declared IO cannot
        # be answered -> UnsupportedSpec (node falls back to the porter).
        from mpynode.native.compiler.errors import UnsupportedSpec

        with self.assertRaises(UnsupportedSpec):
            self._lower("self.out = 1.0 if hasattr(self, 'nope') else 0.0\n",
                        set())

    def test_array_state_lowers_to_nd_array_member(self):
        # #99: a WHOLE-array persistent carry lowers deterministically -- the
        # member type is discovered as an array (nd::Array<double>), not a POD,
        # and the per-element carry uses nd:: elementwise ops.
        from mpynode.native.compiler.py_to_cpp import array_t

        env = {"self.inArray": array_t("double")}
        writers = {"self.outArray":
                   lambda v: ["ndout_self_outArray = %s;" % v.code]}
        res, _, _ = self._lower(_ARR_ACCUM_COMPUTE, {"acc"}, env, writers)
        self.assertIn("acc", res.state_members)
        self.assertEqual(res.state_members["acc"].kind, "array")
        self.assertEqual(res.state_members["acc"].dtype, "double")
        body = "\n".join(res.body_lines)
        self.assertIn("st.acc = nd::add(st.acc, ndin_self_inArray);", body)
        self.assertIn("st.acc_isset = true;", body)

    def test_nonliftable_state_types_honest_reject(self):
        # #99 SAFETY: persistent state whose VALUE cannot be lowered to a native
        # type must HONEST-REJECT (UnsupportedSpec) so the node routes to the AI
        # porter -- NEVER silently flatten it to a scalar.
        from mpynode.native.compiler.errors import UnsupportedSpec

        cases = {
            "string": "if not hasattr(self,'s'):\n    self.s = 'hi'\n"
                      "self.out = self.inValue\n",
            "bytes":  "if not hasattr(self,'b'):\n    self.b = b'x'\n"
                      "self.out = self.inValue\n",
            "list":   "if not hasattr(self,'lst'):\n    self.lst = [1.0, 2.0]\n"
                      "self.out = self.inValue\n",
            "object": "if not hasattr(self,'node'):\n    self.node = make_it()\n"
                      "self.out = self.inValue\n",
        }
        for label, src in cases.items():
            var = {"string": "s", "bytes": "b", "list": "lst",
                   "object": "node"}[label]
            with self.assertRaises(UnsupportedSpec, msg=label):
                self._lower(src, {var})


class TestNdLowerStatePreamble(unittest.TestCase):
    """nd_lower detects the persistent var + binds the per-instance member."""

    def _lower_compute(self):
        from mpynode.native.compiler import nd_lower

        ins = [{"plug": "inValue", "member": "aInValue",
                "meta": {"type": "double", "is_array": False}}]
        outs = [{"plug": "out", "member": "aOut",
                 "meta": {"type": "double", "is_array": False}}]
        return nd_lower.lower_compute(ins, outs, _ACCUM_COMPUTE)

    def test_body_binds_the_per_instance_member(self):
        cpp = "\n".join(self._lower_compute())
        # The body BINDS the node's own member; it declares no storage of its own.
        self.assertIn("_NdState& st = _ndState;", cpp)
        self.assertIn("std::lock_guard<std::mutex> _ndStateLock(_ndStateMutex);",
                      cpp)
        # ...and NONE of the function-static registry it replaces. That shape --
        # a `this`-keyed std::vector with no mutex -- handed out
        # `&_nd_states.back()`, which dangles the moment another instance's
        # compute() push_back()s and reallocates.
        for gone in ("static std::vector<_NdState>", "_nd_states",
                     "(const void*)this", "const void* key;"):
            self.assertNotIn(gone, cpp, "registry remnant %r" % gone)

    def test_state_members_are_class_body_declarations(self):
        decls = "\n".join(self._lower_compute().state_decls)
        self.assertIn("struct _NdState {", decls)
        # Default initialisers are load-bearing: the node's `<cls>() {}` ctor
        # names no member, so an uninitialised `bool acc_isset` would be an
        # INDETERMINATE first-run test.
        self.assertIn("bool acc_isset = false;", decls)
        self.assertIn("double acc {};", decls)
        self.assertIn("_NdState _ndState;", decls)      # per-INSTANCE, not static
        self.assertIn("std::mutex _ndStateMutex;", decls)
        self.assertNotIn("static", decls)

    def test_detects_written_and_read_state_var(self):
        from mpynode.native.compiler import nd_lower

        # written+read undeclared self.<attr> -> a state var
        self.assertEqual(
            nd_lower._persistent_state_vars(
                "self._cache = self.a\nself.b = self._cache", {"a", "b"}),
            {"_cache"})
        # write-only (never read) -> NOT a state var (dead store)
        self.assertEqual(
            nd_lower._persistent_state_vars(
                "self.b = self.a\nself._dead = 1.0", {"a", "b"}),
            set())
        # read-only (never written) -> NOT a state var (orphan; rejects elsewhere)
        self.assertEqual(
            nd_lower._persistent_state_vars(
                "self.o = self.a + self._state", {"a", "o"}),
            set())


class TestAccumulatorCodegenDeterministic(unittest.TestCase):
    """The accumulator ships as PURE C++ (no AI porter) with the registry."""

    def test_no_port_region_and_registry(self):
        from mpynode.native import compiler as codegen

        spec = _accum_spec()
        self.assertTrue((spec.get("portability") or {}).get("portable"),
                        spec.get("portability"))
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)     # deterministic, no porter
        self.assertIn("struct _NdState", cpp)
        self.assertIn("st.acc", cpp)

    def test_state_is_a_class_member_not_a_static_registry(self):
        # The state must be declared in the CLASS body, so it is constructed and
        # destroyed with the node instead of living in a function-static registry
        # that is never evicted (and whose records outlive the nodes that own
        # them). Ordering is the proof: both declarations precede compute()'s
        # DEFINITION, so they can only be inside the class.
        from mpynode.native import compiler as codegen

        spec = _accum_spec()
        cls = spec["suggested"]["class_name"]
        cpp = codegen.generate_cpp(spec, for_port=True)
        defn = cpp.index("MStatus %s::compute(" % cls)
        self.assertLess(cpp.index("struct _NdState"), defn)
        self.assertLess(cpp.index("    _NdState _ndState;"), defn)
        self.assertIn("    std::mutex _ndStateMutex;", cpp)
        self.assertIn("#include <mutex>", cpp)
        self.assertNotIn("_nd_states", cpp)


def _running_maya_root():
    """Install root whose ``include/maya`` exists (None -> no devkit -> skip)."""
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


class TestAccumulatorMultiEvalCompiled(unittest.TestCase):
    """DECISIVE: the compiled node latches state across evals (not flattened)."""

    def test_compiled_accumulates_over_many_evals(self):
        from mpynode.native.toolchain import compile_controller

        if _running_maya_root() is None:
            self.skipTest("no Maya devkit headers on this host")

        import maya.cmds as cmds

        spec = _accum_spec()
        out_dir = tempfile.mkdtemp(prefix="accum_scaffold_")
        res = compile_controller.compile_plugin(
            [spec], "accumScaffoldTest", out_dir, strict=True, verify=False)
        if not res.get("ok"):
            self.skipTest("compile unavailable on this host: %s"
                          % (res.get("errors"),))

        cmds.file(new=True, force=True)
        cmds.loadPlugin(res["bundle_path"])
        n = cmds.createNode("accumNative")
        running = 0.0
        for v in (1.0, 2.0, 3.0, 10.0, -5.0, 0.25):
            cmds.setAttr(n + ".inValue", v)
            got = cmds.getAttr(n + ".out")
            running += v
            self.assertAlmostEqual(
                got, running, places=6,
                msg="compiled accumulator did NOT persist state across evals "
                    "(got %r, expected running sum %r) -- state was flattened"
                    % (got, running))


class TestStateIsPerInstanceCompiled(unittest.TestCase):
    """DECISIVE: the compiled state lives IN the node object, not in a registry.

    Two properties the function-static ``(const void*)this`` registry could not
    give. Interleaved instances keeping INDEPENDENT running sums it happened to
    get right; a node created after a stateful node is DESTROYED starting FRESH
    it did not -- nothing ever evicted a record, so a new node allocated at a
    freed address inherited the dead node's value AND its ``acc_isset``, which
    then skipped the first-run seed. Measured on the pre-fix build: 2 of 8 fresh
    nodes read 301.0 where 1.0 is correct. A per-instance member is destroyed
    with its node, so the second generation is always clean.
    """

    def _load(self):
        import maya.cmds as cmds
        from mpynode.native.toolchain import compile_controller

        if _running_maya_root() is None:
            self.skipTest("no Maya devkit headers on this host")
        spec = _accum_spec()
        spec["suggested"]["node_type_name"] = "accumPerInstNative"
        out_dir = tempfile.mkdtemp(prefix="accum_perinst_")
        res = compile_controller.compile_plugin(
            [spec], "accumPerInstTest", out_dir, strict=True, verify=False)
        if not res.get("ok"):
            self.skipTest("compile unavailable on this host: %s"
                          % (res.get("errors"),))
        cmds.file(new=True, force=True)
        cmds.loadPlugin(res["bundle_path"])
        return cmds

    def test_instances_are_independent_and_recreate_starts_fresh(self):
        cmds = self._load()

        # (a) two instances driven alternately keep separate running sums.
        a = cmds.createNode("accumPerInstNative")
        b = cmds.createNode("accumPerInstNative")
        ra = rb = 0.0
        for va, vb in ((1.0, 100.0), (2.0, 200.0), (3.0, 300.0)):
            cmds.setAttr(a + ".inValue", va)
            got_a = cmds.getAttr(a + ".out")
            cmds.setAttr(b + ".inValue", vb)
            got_b = cmds.getAttr(b + ".out")
            ra += va
            rb += vb
            self.assertAlmostEqual(got_a, ra, places=6,
                                   msg="instance A saw instance B's state")
            self.assertAlmostEqual(got_b, rb, places=6,
                                   msg="instance B saw instance A's state")

        # (b) destroy a generation of stateful nodes, then build a second one:
        # every fresh node must start from zero. flushUndo() is what actually
        # frees the MPxNodes -- cmds.delete alone parks them on the undo queue,
        # so no address is ever recycled and the leak cannot show.
        first = []
        for _ in range(8):
            n = cmds.createNode("accumPerInstNative")
            first.append(n)
            for v in (100.0, 100.0, 100.0):
                cmds.setAttr(n + ".inValue", v)
                cmds.getAttr(n + ".out")
        cmds.delete(first)
        cmds.flushUndo()

        for i in range(8):
            n = cmds.createNode("accumPerInstNative")
            cmds.setAttr(n + ".inValue", 1.0)
            self.assertAlmostEqual(
                cmds.getAttr(n + ".out"), 1.0, places=6,
                msg="fresh node %d inherited a destroyed node's state -- the "
                    "persistent state outlived the node that owned it" % i)


class TestArrayStateDeterministicAndCompiled(unittest.TestCase):
    """#99: an ARRAY persistent carry lowers DETERMINISTICALLY (no porter) and the
    compiled node accumulates the whole array across evals."""

    def test_array_accumulator_is_deterministic(self):
        from mpynode.native import compiler as codegen

        spec = _arr_accum_spec()
        self.assertTrue((spec.get("portability") or {}).get("portable"),
                        spec.get("portability"))
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)     # deterministic, no porter
        self.assertIn("struct _NdState", cpp)
        self.assertIn("nd::Array", cpp)               # array-typed state member

    def test_compiled_array_accumulates_over_many_evals(self):
        from mpynode.native.toolchain import compile_controller

        if _running_maya_root() is None:
            self.skipTest("no Maya devkit headers on this host")

        import maya.cmds as cmds

        spec = _arr_accum_spec()
        out_dir = tempfile.mkdtemp(prefix="arracc_scaffold_")
        res = compile_controller.compile_plugin(
            [spec], "arrAccScaffoldTest", out_dir, strict=True, verify=False)
        if not res.get("ok"):
            self.skipTest("compile unavailable on this host: %s"
                          % (res.get("errors"),))

        cmds.file(new=True, force=True)
        cmds.loadPlugin(res["bundle_path"])
        n = cmds.createNode("arrAccNative")
        running = [0.0, 0.0, 0.0]
        for vec in ([1.0, 2.0, 3.0], [10.0, 20.0, 30.0], [-1.0, -2.0, -3.0]):
            for i, v in enumerate(vec):
                cmds.setAttr("%s.inArray[%d]" % (n, i), v)
            got = [cmds.getAttr("%s.outArray[%d]" % (n, i)) for i in range(3)]
            running = [running[i] + vec[i] for i in range(3)]
            for i in range(3):
                self.assertAlmostEqual(
                    got[i], running[i], places=6,
                    msg="compiled ARRAY accumulator did NOT persist state across "
                        "evals (element %d: got %r expected %r) -- array state "
                        "was flattened" % (i, got[i], running[i]))


class TestNonLiftableStateRoutesToPorter(unittest.TestCase):
    """#99 SAFETY at the PIPELINE level: a persistent carry whose value is a python
    OBJECT (self.node = Solver(...)) is NOT lowered deterministically -- the
    deterministic path returns None so the node routes to the AI porter (which has
    the this-keyed-registry guidance), rather than being flattened or crashing."""

    def test_object_state_deterministic_lower_returns_none(self):
        from mpynode.native.compiler import nd_lower

        ins = [{"plug": "a", "member": "aA",
                "meta": {"type": "double", "is_array": False}}]
        outs = [{"plug": "out", "member": "aOut",
                 "meta": {"type": "double", "is_array": False}}]
        # self.node holds a helper-object instance carried across evals (the
        # dnet self.node=Solver() pattern). The transpiler cannot lower an
        # object value -> try_lower_compute returns None, never a flat scalar.
        spec = {"compute": "if not hasattr(self,'node'):\n"
                           "    self.node = make_solver(self.a)\n"
                           "self.out = self.node\n",
                "init": ""}
        self.assertIsNone(nd_lower.try_lower_compute(ins, outs, spec))


class TestPorterStatePersistenceGuidance(unittest.TestCase):
    """A PORTER node with persistent state (spine's ``defaultLength``, dnet's
    ``previous`` -- computes the porter can't lower deterministically) gets
    explicit guidance to emit a ``this``-keyed state registry instead of
    flattening it. It steers FUTURE / re-ported nodes. (The guidance was additive
    when first written; T3 then rewrote it -- records -> POINTERS -- so
    PORTER_RECIPE_VERSION went to "13" and existing port caches ARE invalidated.)
    (Fully closing spine/dnet still needs a re-port run + a GUI parity check --
    their live MFn curve queries cannot be evaluated by the headless reference.)
    """

    def test_stateful_spec_gets_registry_guidance(self):
        from mpynode.native.ai import translation_knowledge as tk

        stateful = {
            "compute": "if not hasattr(self, 'rest'):\n    self.rest = self.a\n"
                       "self.out = self.a - self.rest\n",
            "init": "",
            "inputs": {"a": {"type": "double"}},
            "outputs": {"out": {"type": "double"}},
        }
        self.assertEqual(tk._persistent_state_names(stateful), {"rest"})
        guide = tk.guide_for_spec(stateful)
        self.assertIn("PERSISTENT PER-INSTANCE STATE", guide)
        self.assertIn("(const void*)this", guide)
        self.assertIn("hasattr", guide)

    _STATEFUL = {
        "compute": "if not hasattr(self, 'rest'):\n    self.rest = self.a\n"
                   "self.out = self.a - self.rest\n",
        "init": "",
        "inputs": {"a": {"type": "double"}},
        "outputs": {"out": {"type": "double"}},
    }

    def test_guidance_registry_cannot_dangle(self):
        # The porter is spliced ONLY between the PORT markers, so it cannot
        # declare the per-instance member the deterministic path uses -- but the
        # registry it CAN write must not be the shape that hands out a pointer
        # into a reallocating vector.
        from mpynode.native.ai import translation_knowledge as tk

        guide = tk.guide_for_spec(dict(self._STATEFUL))
        # prescribed: a vector of POINTERS (only the pointer array moves).
        self.assertIn("static std::vector<NodeState*> s_states;", guide)
        self.assertIn("st = new NodeState();", guide)
        # forbidden, by name: the vector of RECORDS whose `&s_states.back()`
        # dangles as soon as another instance's compute() push_back()s.
        self.assertIn("NEVER `static std::vector<NodeState> s_states;`", guide)
        # and it says WHY it is not the per-instance member the optimizer wants.
        self.assertIn("add a class member and you may not add an #include", guide)
        self.assertIn("CONSTRAINED FALLBACK", guide)

    def test_guidance_never_claims_the_pointer_vector_is_thread_safe(self):
        """T104. Pointers fix the DANGLE and nothing else: the range-for read
        still races the push_back under the parallel EM (two instances first
        evaluating concurrently is the COMMON case, not the rare one), and the
        registry has no lock because the porter cannot add the <mutex> include.
        The guide claimed 'A vector of POINTERS is immune', which reads as
        'this shape is fine' -- so a reader has no reason to lift it."""
        from mpynode.native.ai import translation_knowledge as tk

        guide = tk.guide_for_spec(dict(self._STATEFUL))
        self.assertNotIn("A vector of POINTERS is immune", guide)
        self.assertIn("UNSYNCHRONISED", guide)

    def test_guidance_names_the_per_instance_shape_the_optimizer_lifts_to(self):
        """The two prompts must describe ONE destination. Asserted against the
        lines nd_lower ACTUALLY emits, so prose and codegen cannot drift."""
        from mpynode.native.ai import translation_knowledge as tk
        from mpynode.native.compiler import nd_lower

        guide = tk.guide_for_spec(dict(self._STATEFUL))
        for line in nd_lower._state_binding_preamble({"rest": None}):
            line = line.strip()
            if line.startswith("//"):
                continue
            self.assertIn(line, guide,
                          "the guide must name the binding the deterministic "
                          "path emits, verbatim")
        self.assertIn("_NdState _ndState;", guide)
        self.assertIn("std::mutex _ndStateMutex;", guide)

    def test_optimizer_owns_the_lift_the_porter_cannot_do(self):
        # The two prompts used to contradict each other: the optimizer forbade a
        # node-keyed static registry while this guide prescribed one. They are
        # now a handoff -- the porter is region-confined, the optimizer is not.
        from mpynode.native.ai import optimizer_agent

        task = optimizer_agent._TASK_MD
        self.assertIn("Per-instance members ONLY", task)
        self.assertIn("lifting it to a per-instance member is IN SCOPE", task)

    def test_guidance_covers_object_instance_carry(self):
        # #99: the guidance must tell the porter how to handle a persistent carry
        # that holds a PYTHON OBJECT (a cached solver/helper instance) -- store the
        # data it carries, not the object pointer (the dnet self.node=Solver case).
        from mpynode.native.ai import translation_knowledge as tk

        stateful = {
            "compute": "if not hasattr(self, 'solver'):\n"
                       "    self.solver = Solver(self.a)\n"
                       "self.out = self.solver.step(self.a)\n",
            "init": "",
            "inputs": {"a": {"type": "double"}},
            "outputs": {"out": {"type": "double"}},
        }
        guide = tk.guide_for_spec(stateful)
        self.assertIn("PERSISTENT PER-INSTANCE STATE", guide)
        self.assertIn("PYTHON OBJECT", guide)
        self.assertIn("Never store a Python-object pointer", guide)

    def test_stateless_spec_has_no_state_guidance(self):
        from mpynode.native.ai import translation_knowledge as tk

        stateless = {"compute": "self.out = self.a * 2.0", "init": "",
                     "inputs": {"a": {"type": "double"}},
                     "outputs": {"out": {"type": "double"}}}
        self.assertEqual(tk._persistent_state_names(stateless), set())
        self.assertNotIn("PERSISTENT PER-INSTANCE STATE",
                         tk.guide_for_spec(stateless))


class TestMultiEvalVerifyCatchesFlattening(unittest.TestCase):
    """SAFETY NET (#95): the parity verify drives a persistent instance over MANY
    evals with changing inputs, so a stateful node whose state was FLATTENED (the
    spine-class bug) diverges from the interpreted original and is REJECTED -- it
    is never silently shipped. Proven both directions on the scalar accumulator:
    the correct (scaffolded) build PASSES; a hand-flattened build FAILS.

    NOTE: this covers the class of stateful nodes the HEADLESS harness can drive.
    A stateful node that reads geometry via LIVE MFn queries (spine's
    findParamFromLength / getPointAtParam) cannot be parity-checked headlessly at
    all -- the interpreted reference returns 0 elements on a synthesized standalone
    curve -- so verify honestly SKIPs it (ran=False), and its parity must be
    confirmed in a GUI Maya session. That limitation is inherent to the reference,
    not to this scaffold.
    """

    def _compile(self, type_name, flatten):
        """Compile the accumulator under *type_name*; if *flatten*, drop the state
        carry from the generated C++ + rebuild. Returns (spec, bundle_path).

        A DISTINCT type name per build lets the correct and flattened plugins be
        loaded side by side (reloading a same-named plugin over a live one in one
        Maya session is unreliable)."""
        import glob
        import subprocess

        from mpynode.native.toolchain import compile_controller

        if _running_maya_root() is None:
            self.skipTest("no Maya devkit headers on this host")
        spec = _accum_spec()
        spec["suggested"]["node_type_name"] = type_name
        out_dir = tempfile.mkdtemp(prefix="accstate_")
        res = compile_controller.compile_plugin(
            [spec], "accStateTest_" + type_name, out_dir, strict=True,
            verify=False)
        if not res.get("ok"):
            self.skipTest("compile unavailable on this host: %s"
                          % (res.get("errors"),))
        if flatten:
            hit = False
            for p in glob.glob(os.path.join(out_dir, "**", "*.cpp"),
                               recursive=True):
                with open(p) as fh:
                    s = fh.read()
                if "st.acc = (st.acc + ndin_self_inValue);" in s:
                    with open(p, "w") as fh:
                        fh.write(
                            s.replace("st.acc = (st.acc + ndin_self_inValue);",
                                      "st.acc = (ndin_self_inValue);"))
                    hit = True
            self.assertTrue(hit, "did not find the state-carry line to flatten")
            rb = subprocess.run(
                ["bash", os.path.join(out_dir, "build", "build.sh")],
                cwd=out_dir, capture_output=True, text=True)
            if rb.returncode != 0:
                self.skipTest("rebuild unavailable: %s" % (rb.stderr or "")[-200:])
        return spec, res["bundle_path"]

    def test_correct_passes_flattened_fails(self):
        import maya.cmds as cmds
        from mpynode.native.toolchain import verify

        # (a) the correct (scaffolded) build accumulates -> parity PASS.
        spec_ok, bundle_ok = self._compile("accStateOkNative", flatten=False)
        # (b) a hand-flattened build drops the state carry -> parity FAIL (mirrors
        # the porter dropping persistent state: out = inValue each eval).
        spec_bad, bundle_bad = self._compile("accStateFlatNative", flatten=True)

        cmds.file(new=True, force=True)
        cmds.loadPlugin(bundle_ok)
        cmds.loadPlugin(bundle_bad)

        ok = verify._verify_one(cmds, bundle_ok, spec_ok)
        self.assertTrue(ok.get("ran"))
        self.assertTrue(ok.get("pass"),
                        "correct stateful build should verify PASS, got %r" % ok)

        bad = verify._verify_one(cmds, bundle_bad, spec_bad)
        self.assertTrue(bad.get("ran"))
        self.assertFalse(
            bad.get("pass"),
            "multi-eval verify must REJECT a flattened stateful port, got %r"
            % bad)


if __name__ == "__main__":
    unittest.main()
