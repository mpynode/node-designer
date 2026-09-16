"""Native porter/bundler followed-import helper hoist + dedup (scalar + non-scalar)

Consolidated from: test_import_follower.py, test_shared_helpers.py, test_nonscalar_helpers.py.
"""

from __future__ import annotations

# ===================== from test_import_follower.py =====================
import importlib
import os
import sys
import tempfile
import unittest

from mpynode.native.ai import import_follower as ifol

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__import_follower():
    # Needed only by the extract_spec integration test; the pure follower tests
    # ignore it. Cheap + idempotent under the shared harness.
    standalone_init()
    ensure_plugins_loaded()


class _TempModules(unittest.TestCase):
    """Base: a temp dir on sys.path to drop helper modules into."""

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="ifol_")
        sys.path.insert(0, self._dir)
        importlib.invalidate_caches()
        self._written = []

    def tearDown(self):
        try:
            sys.path.remove(self._dir)
        except ValueError:
            pass
        for name in self._written:
            sys.modules.pop(name, None)
        importlib.invalidate_caches()

    def _write(self, modname, src):
        path = os.path.join(self._dir, modname + ".py")
        with open(path, "w") as f:
            f.write(src)
        self._written.append(modname)
        return path

    def _write_package(self, pkgname, modules):
        """Create ``pkgname/`` with ``modules`` = {submodule|'__init__': src}."""
        pdir = os.path.join(self._dir, pkgname)
        os.makedirs(pdir, exist_ok=True)
        for mod, src in modules.items():
            with open(os.path.join(pdir, mod + ".py"), "w") as f:
                f.write(src)
        self._written.append(pkgname)
        return pdir


class TestCollectHelperSources(_TempModules):
    def test_follows_from_import_and_same_module_transitive(self):
        self._write(
            "geomath1",
            "def _norm(x):\n    return x * x\n\n"
            "def curvature(a, b):\n    return _norm(a) + b\n",
        )
        compute = (
            "from geomath1 import curvature\n"
            "self.out = curvature(self.a, self.b)\n"
        )
        res   = ifol.collect_helper_sources(compute, "")
        names = {s["name"] for s in res["sources"]}
        self.assertIn("curvature", names)
        self.assertIn("_norm", names)  # same-module transitive helper
        rendered = ifol.render_for_prompt(res)
        self.assertIn("def curvature", rendered)
        self.assertIn("def _norm", rendered)

    def test_follows_module_attribute_access(self):
        self._write("geomath2", "def curv(a):\n    return a + 1\n")
        compute = "import geomath2 as g\nself.out = g.curv(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        names   = {s["name"] for s in res["sources"]}
        self.assertIn("curv", names)

    def test_follows_class_definition(self):
        self._write(
            "geomath3",
            "class Solver:\n    def run(self, x):\n        return x\n",
        )
        compute = "from geomath3 import Solver\nself.out = Solver().run(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        self.assertIn("Solver", {s["name"] for s in res["sources"]})
        self.assertIn("class Solver", ifol.render_for_prompt(res))

    def test_cross_module_transitive(self):
        self._write("geocore4", "def helper(x):\n    return x - 1\n")
        self._write(
            "geomath4",
            "from geocore4 import helper\n\n"
            "def curvature(a):\n    return helper(a) * 2\n",
        )
        compute = "from geomath4 import curvature\nself.out = curvature(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        names   = {(s["module"], s["name"]) for s in res["sources"]}
        self.assertIn(("geomath4", "curvature"), names)
        self.assertIn(("geocore4", "helper"), names)  # followed across modules

    def test_skips_numpy_and_stdlib(self):
        compute = (
            "import numpy as np\n"
            "import math\n"
            "self.out = float(np.sum(self.pts)) + math.sqrt(self.a)\n"
        )
        res  = ifol.collect_helper_sources(compute, "")
        mods = {s["module"] for s in res["sources"]}
        self.assertNotIn("numpy", mods)  # handled by translation_knowledge
        self.assertNotIn("math", mods)   # stdlib / C builtin
        self.assertEqual(res["sources"], [])

    def test_unresolvable_import_degrades(self):
        compute = "from totally_missing_xyz import foo\nself.out = foo(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")  # must not raise
        self.assertEqual(res["sources"], [])

    def test_syntax_error_source_degrades(self):
        res = ifol.collect_helper_sources("def (:::\n bad python", "")
        self.assertEqual(res["sources"], [])  # no crash

    def test_render_empty_when_no_helpers(self):
        res = ifol.collect_helper_sources("self.out = self.a * 2.0", "")
        self.assertEqual(ifol.render_for_prompt(res), "")

    def test_does_not_execute_module_code(self):
        # The follower must locate + read source statically; it must NEVER run
        # the module (no import), so a module-level side effect must NOT fire.
        sentinel = os.path.join(self._dir, "SENTINEL_EXECUTED")
        self._write(
            "sideeffect5",
            "open(%r, 'w').write('x')\n\n"
            "def f(a):\n    return a\n" % sentinel,
        )
        compute = "from sideeffect5 import f\nself.out = f(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        self.assertIn("f", {s["name"] for s in res["sources"]})  # source found
        self.assertFalse(
            os.path.exists(sentinel),
            "module-level code executed -- follower must be static (no import)",
        )

    def test_package_submodule_followed_without_executing_init(self):
        # R1: following `from pkg.sub import f` must NOT execute pkg/__init__.py
        # (find_spec on a dotted name imports the parent; we must resolve it
        # statically). Helper must still be followed.
        sentinel = os.path.join(self._dir, "pkgX", "INIT_RAN")
        self._write_package(
            "pkgX",
            {"__init__": "open(%r, 'w').write('ran')\n" % sentinel,
             "leaf": "def curvature(a):\n    return a * 2\n"},
        )
        compute = "from pkgX.leaf import curvature\nself.out = curvature(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        self.assertIn(
            ("pkgX.leaf", "curvature"),
            {(s["module"], s["name"]) for s in res["sources"]},
        )
        self.assertFalse(
            os.path.exists(sentinel),
            "package __init__ executed -- R1 (no import/exec) violated",
        )

    def test_bare_dotted_import_followed(self):
        # R5: `import pkg.sub` (no alias) + `pkg.sub.f()` must resolve the helper
        # through the multi-level attribute chain.
        self._write_package(
            "pkgY",
            {"__init__": "", "sub": "def helper(a):\n    return a + 7\n"},
        )
        compute = "import pkgY.sub\nself.out = pkgY.sub.helper(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        self.assertIn(
            ("pkgY.sub", "helper"),
            {(s["module"], s["name"]) for s in res["sources"]},
        )

    def test_decorator_included_in_source(self):
        # R5: a decorated helper's source must keep its decorator (its behavior
        # depends on it); get_source_segment drops decorators.
        self._write(
            "decomod",
            "def memo(fn):\n    return fn\n\n@memo\ndef curvature(a):\n    return a * 2\n",
        )
        compute = "from decomod import curvature\nself.out = curvature(self.a)\n"
        res     = ifol.collect_helper_sources(compute, "")
        curv    = [s for s in res["sources"] if s["name"] == "curvature"]
        self.assertTrue(curv)
        self.assertIn("@memo", curv[0]["source"])

    def test_param_shadowing_excludes_unrelated_def(self):
        # R5: a parameter named like a top-level def must NOT pull that def in.
        self._write(
            "shadowmod",
            "def scale(x):\n    return x * 100\n\n"
            "def curvature(scale, b):\n    return scale * b\n",
        )
        compute = (
            "from shadowmod import curvature\n"
            "self.out = curvature(self.a, self.b)\n"
        )
        res   = ifol.collect_helper_sources(compute, "")
        names = {s["name"] for s in res["sources"]}
        self.assertIn("curvature", names)
        self.assertNotIn("scale", names)  # 'scale' is a param here, not the def

    def test_helper_defined_in_init_is_not_external(self):
        # A helper DEFINED in Init (not imported) is already handed to the porter
        # via the Init block -- the follower shouldn't duplicate it as external.
        init    = "def localhelp(x):\n    return x + 1\n"
        compute = "self.out = localhelp(self.a)\n"
        res     = ifol.collect_helper_sources(compute, init)
        self.assertEqual(res["sources"], [])


class TestPorterPromptIntegration(unittest.TestCase):
    """build_prompt injects the followed helpers as reference, and is byte-for-
    byte unchanged when there are none."""

    def _spec(self, **over):
        spec = {
            "mpy_type":    "mPyNode",
            "source_node": "n",
            "suggested":   {"mpx_base": "MPxNode"},
            "compute":     "self.out = self.a",
            "init":        "",
            "inputs":      {},
            "outputs":     {},
        }
        spec.update(over)
        return spec

    def test_build_prompt_includes_external_helpers(self):
        from mpynode.native.ai import porter

        spec = self._spec(
            compute          = "self.out = foo(self.a)",
            init             = "from m import foo",
            external_helpers = "# --- from module 'm' ---\ndef foo(a):\n    return a + 1",
        )
        _system, user = porter.build_prompt(spec, "// PORT_BEGIN\n// PORT_END\n")
        self.assertIn("External helper modules", user)
        self.assertIn("def foo", user)

    def test_build_prompt_unchanged_when_no_helpers(self):
        from mpynode.native.ai import porter

        skeleton = "// PORT_BEGIN\n// PORT_END\n"
        # No external_helpers key at all -> must match the absent-key prompt
        # exactly, and never mention the helper block.
        spec_absent = self._spec()
        spec_empty  = self._spec(external_helpers="")
        _s1, u_absent = porter.build_prompt(spec_absent, skeleton)
        _s2, u_empty = porter.build_prompt(spec_empty, skeleton)
        self.assertNotIn("External helper modules", u_absent)
        self.assertEqual(u_absent, u_empty)  # empty string == absent key


class TestExtractSpecFollowsImports(_TempModules):
    """extract_spec populates spec['external_helpers'] from followed imports."""

    def test_extract_spec_populates_external_helpers(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode

        self._write("geoextract9", "def curv(a):\n    return a + 1\n")
        n = MPyNode.create(name="follow_node#")
        n.add_input_attr("a", "float")
        n.add_output_attr("out", "float")
        n.set_init_expression("from geoextract9 import curv")
        n.set_compute_expression("self.out = curv(self.a)")

        spec = spec_extractor.extract_spec(n.get_name())
        self.assertIn("external_helpers", spec)
        self.assertIn("def curv", spec["external_helpers"])

    def test_extract_spec_external_helpers_empty_for_plain_node(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode

        n = MPyNode.create(name="plain_node#")
        n.add_input_attr("a", "float")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = self.a * 2.0")

        spec = spec_extractor.extract_spec(n.get_name())
        # No followable helpers -> the key is OMITTED entirely, so the spec (and
        # therefore the port_cache key) is byte-identical to the pre-feature
        # spec: existing cached ports are NOT invalidated on upgrade.
        self.assertNotIn("external_helpers", spec)


# ===================== from test_shared_helpers.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest

from tests._setup import standalone_init


def _setUpModule__shared_helpers():
    standalone_init()


# A marked shared-helper block as codegen will emit it (file scope).
_BLOCK = (
    "// === MPYNODE SHARED HELPER BEGIN name=mpyh_abc123def0 "
    "proto=double mpyh_abc123def0(double x, double k) ===\n"
    "double mpyh_abc123def0(double x, double k) {\n"
    "    return x * k + 1.0;\n"
    "}\n"
    "// === MPYNODE SHARED HELPER END name=mpyh_abc123def0 ===\n"
)


def _node_src(node_name, cls, type_id, *, with_block=True):
    block = ("\n" + _BLOCK + "\n") if with_block else "\n"
    # The call site exists only when the node actually carries the helper.
    call = ("        double r = mpyh_abc123def0(1.0, 2.0);\n        (void)r;\n"
            if with_block else "")
    return (
        "#include <maya/MPxNode.h>\n"
        "#include <maya/MFnPlugin.h>\n"
        "#include <cmath>\n"
        "%s"
        "class %s : public MPxNode {\n"
        "public:\n"
        "    static void* creator() { return new %s(); }\n"
        "    static MStatus initialize() { return MS::kSuccess; }\n"
        "    MStatus compute(const MPlug& plug, MDataBlock& data) override {\n"
        "%s"
        "        return MS::kSuccess;\n"
        "    }\n"
        "    static MTypeId id;\n"
        "};\n"
        "MTypeId %s::id(%s);\n"
        "\n"
        "MStatus initializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj, \"x\", \"1.0\", \"Any\");\n"
        "    return plugin.registerNode(\"%s\", %s::id, %s::creator, %s::initialize);\n"
        "}\n"
        "MStatus uninitializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj);\n"
        "    return plugin.deregisterNode(%s::id);\n"
        "}\n"
        % (block, cls, cls, call, cls, type_id, node_name, cls, cls, cls, cls)
    )


def _id_for(_key):
    return "0x00081234"


class TestTransformExtractsSharedHelper(unittest.TestCase):
    def test_block_def_hoisted_proto_left_behind(self):
        from mpynode.native.compiler import bundler

        src = _node_src("fooNode", "FooNode", "0x00081000")
        frag, info = bundler.transform_node_cpp(src, "fooNode", _id_for)

        # The DEFINITION must be gone from the node fragment (it moves to the
        # shared unit) ...
        self.assertNotIn("return x * k + 1.0;", frag,
                         "helper body must be hoisted out of the node fragment")
        # ... replaced by a prototype declaration at GLOBAL scope so the call
        # inside namespace nd_fooNode resolves to the shared definition.
        self.assertIn("double mpyh_abc123def0(double x, double k);", frag)
        # The call site survives.
        self.assertIn("mpyh_abc123def0(1.0, 2.0)", frag)
        # The marker comments must not leak into the fragment.
        self.assertNotIn("MPYNODE SHARED HELPER", frag)
        # The block is reported for the assembler to collect.
        sh = info.get("shared_helpers") or []
        self.assertEqual(len(sh), 1)
        self.assertEqual(sh[0]["name"], "mpyh_abc123def0")
        self.assertIn("return x * k + 1.0;", sh[0]["code"])
        self.assertEqual(sh[0]["proto"], "double mpyh_abc123def0(double x, double k)")

    def test_proto_is_global_scope_before_namespace(self):
        from mpynode.native.compiler import bundler

        src = _node_src("fooNode", "FooNode", "0x00081000")
        frag, _info = bundler.transform_node_cpp(src, "fooNode", _id_for)
        proto_at = frag.index("double mpyh_abc123def0(double x, double k);")
        ns_at    = frag.index("namespace nd_fooNode")
        self.assertLess(proto_at, ns_at,
                        "proto decl must precede the node namespace (global scope)")


class TestTransformBackwardCompatible(unittest.TestCase):
    def test_no_block_means_no_change(self):
        from mpynode.native.compiler import bundler

        src = _node_src("fooNode", "FooNode", "0x00081000", with_block=False)
        frag, info = bundler.transform_node_cpp(src, "fooNode", _id_for)
        # No shared-helper artifacts at all.
        self.assertEqual(info.get("shared_helpers") or [], [])
        self.assertNotIn("MPYNODE SHARED HELPER", frag)
        self.assertNotIn("mpyh_", frag)
        # Structure intact: still namespace-wrapped + register hook generated.
        self.assertIn("namespace nd_fooNode", frag)
        self.assertIn("register_FooNode", frag)


class TestAssembleDedup(unittest.TestCase):
    def test_two_nodes_one_shared_unit(self):
        from mpynode.native.toolchain import typeid_registry
        from mpynode.native.compiler import bundler

        d  = tempfile.mkdtemp(prefix="shared_asm_")
        p1 = os.path.join(d, "fooNode.cpp")
        p2 = os.path.join(d, "barNode.cpp")
        with open(p1, "w") as fh:
            fh.write(_node_src("fooNode", "FooNode", "0x00081000"))
        with open(p2, "w") as fh:
            fh.write(_node_src("barNode", "BarNode", "0x00081001"))

        out = os.path.join(d, "out")
        reg = typeid_registry.TypeIdRegistry(path=os.path.join(d, "reg.json"))
        report = bundler.assemble(
            [("fooNode", p1), ("barNode", p2)], "twoShare", out,
            strict=True, registry=reg, compile_now=False)

        # A single shared unit holds the helper definition exactly once.
        shared = os.path.join(out, "build", "source", "shared_helpers.cpp")
        self.assertTrue(os.path.isfile(shared),
                        "assemble must emit shared_helpers.cpp")
        with open(shared) as fh:
            shared_text = fh.read()
        self.assertEqual(shared_text.count("double mpyh_abc123def0(double x, double k) {"), 1,
                         "the helper must be DEFINED exactly once (deduped)")

        # build.sh must compile the shared unit too.
        with open(os.path.join(out, "build", "build.sh")) as fh:
            build = fh.read()
        self.assertIn("shared_helpers.cpp", build)

        # Neither node fragment may still DEFINE the helper. (assemble now emits
        # the clean, re-buildable ``<node>.cpp`` -- not the old ``frag_<node>``.)
        for nm in ("fooNode", "barNode"):
            with open(os.path.join(out, "build", "source", "%s.cpp" % nm)) as fh:
                frag = fh.read()
            self.assertNotIn("return x * k + 1.0;", frag,
                             "%s frag must not embed the helper body" % nm)
            self.assertIn("double mpyh_abc123def0(double x, double k);", frag)

    def test_no_shared_unit_when_no_blocks(self):
        from mpynode.native.toolchain import typeid_registry
        from mpynode.native.compiler import bundler

        d  = tempfile.mkdtemp(prefix="shared_asm_none_")
        p1 = os.path.join(d, "plainNode.cpp")
        with open(p1, "w") as fh:
            fh.write(_node_src("plainNode", "PlainNode", "0x00081000",
                               with_block=False))
        out = os.path.join(d, "out")
        reg = typeid_registry.TypeIdRegistry(path=os.path.join(d, "reg.json"))
        bundler.assemble([("plainNode", p1)], "plain", out,
                         strict=True, registry=reg, compile_now=False)
        # No marked blocks anywhere -> no shared unit is emitted (additive).
        self.assertFalse(os.path.isfile(os.path.join(out, "build", "source", "shared_helpers.cpp")),
                         "no shared unit should exist when no node has a block")
        with open(os.path.join(out, "build", "build.sh")) as fh:
            self.assertNotIn("shared_helpers.cpp", fh.read())


class TestPorterScalarProto(unittest.TestCase):
    def _u(self, name, source, module="m"):
        return {"module": module, "name": name, "source": source}

    def test_simple_scalar_proto(self):
        from mpynode.native.ai import porter

        name, proto = porter._derive_scalar_proto(
            self._u("scaled", "def scaled(x, k):\n    return x * k + 1.0\n"))
        self.assertTrue(name.startswith("mpyh_"))
        self.assertEqual(proto, "double %s(double x, double k)" % name)

    def test_name_is_deterministic_and_source_sensitive(self):
        from mpynode.native.ai import porter

        a = porter._derive_scalar_proto(
            self._u("scaled", "def scaled(x, k):\n    return x * k + 1.0\n"))
        b = porter._derive_scalar_proto(
            self._u("scaled", "def scaled(x, k):\n    return x * k + 1.0\n"))
        c = porter._derive_scalar_proto(
            self._u("scaled", "def scaled(x, k):\n    return x * k + 2.0\n"))
        self.assertEqual(a[0], b[0])     # same source -> same name
        self.assertNotEqual(a[0], c[0])  # different source -> different name

    def test_no_arg_helper(self):
        from mpynode.native.ai import porter
        name, proto = porter._derive_scalar_proto(
            self._u("k", "def k():\n    return 3.0\n"))
        self.assertEqual(proto, "double %s()" % name)

    def test_class_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertIsNone(porter._derive_scalar_proto(
            self._u("S", "class S:\n    pass\n")))

    def test_varargs_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertIsNone(porter._derive_scalar_proto(
            self._u("f", "def f(*a):\n    return 0\n")))

    def test_defaults_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertIsNone(porter._derive_scalar_proto(
            self._u("f", "def f(x, k=1.0):\n    return x\n")))


class TestShareableHelperUnits(unittest.TestCase):
    def test_units_from_spec(self):
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k + 1.0\n"}]}
        units = porter._shareable_helper_units(spec)
        self.assertEqual(len(units),         1)
        self.assertEqual(units[0]["sym"],    "scaled")
        self.assertEqual(units[0]["module"], "m")
        self.assertTrue(units[0]["name"].startswith("mpyh_"))

    def test_any_unshareable_falls_back_to_empty(self):
        # If ANY followed helper can't be a scalar free function, the whole node
        # keeps the (current, robust) INLINE path -- no partial sharing.
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k\n"},
            {"module": "m", "name": "f", "source": "def f(*a):\n    return 0\n"}]}
        self.assertEqual(porter._shareable_helper_units(spec), [])

    def test_no_helpers_is_empty(self):
        from mpynode.native.ai import porter
        self.assertEqual(porter._shareable_helper_units({}), [])


class TestPorterSharedPromptAndInject(unittest.TestCase):
    def _spec(self, **over):
        spec = {"mpy_type": "mPyNode", "source_node": "n",
                "suggested":        {"mpx_base": "MPxNode"},
                "compute":          "self.out = scaled(self.a, self.k)",
                "init":             "from m import scaled",
                "external_helpers": "# --- from module 'm' ---\n"
                                    "def scaled(x, k):\n    return x * k + 1.0",
                "inputs": {}, "outputs": {}}
        spec.update(over)
        return spec

    def test_shared_mode_instructs_call_not_inline(self):
        from mpynode.native.ai import porter
        protos = [("m.scaled", "double mpyh_abc(double x, double k)")]
        _s, user = porter.build_prompt(
            self._spec(), "// PORT_BEGIN\n// PORT_END\n", shared_protos=protos)
        self.assertIn("mpyh_abc", user)
        self.assertIn("double mpyh_abc(double x, double k)", user)
        # In shared mode the LLM is told to CALL, not to port the source inline.
        self.assertNotIn("port these into the C++ alongside", user)

    def test_default_mode_unchanged(self):
        from mpynode.native.ai import porter
        _s, user = porter.build_prompt(self._spec(), "// PORT_BEGIN\n// PORT_END\n")
        # Without shared_protos the behavior is exactly the inline path.
        self.assertIn("External helper modules", user)

    def test_inject_blocks_after_includes_before_body(self):
        from mpynode.native.ai import porter
        sk = "#include <a.h>\n#include <b.h>\n\nclass X {};\n"
        blk = porter._marked_block(
            "mpyh_x", "double mpyh_x(double a)",
            "double mpyh_x(double a) { return a; }")
        out = porter._inject_helper_blocks(sk, [blk])
        self.assertGreater(out.index("MPYNODE SHARED HELPER"),
                           out.index("#include <b.h>"))
        self.assertLess(out.index("MPYNODE SHARED HELPER"), out.index("class X"))


class TestScalarSafety(unittest.TestCase):
    """A followed helper is shared ONLY if it is provably scalar-double. Anything
    that touches a parameter non-scalarly (subscript/attr/iterate/len/sum/...),
    returns a container, or uses a C++-keyword parameter name must fall back to
    the (correct) INLINE path -- otherwise we'd regress helpers the inline path
    handled fine. Erring toward inline is the safe direction."""

    def _proto(self, name, source):
        from mpynode.native.ai import porter
        return porter._derive_scalar_proto(
            {"module": "m", "name": name, "source": source})

    def test_pure_arithmetic_is_shareable(self):
        self.assertIsNotNone(self._proto(
            "scaled", "def scaled(x, k):\n    return x * k + 1.0\n"))

    def test_math_call_on_scalar_is_shareable(self):
        self.assertIsNotNone(self._proto(
            "f", "import math\ndef f(x):\n    return math.sqrt(x) + 1.0\n"))

    def test_two_arg_minmax_is_shareable(self):
        self.assertIsNotNone(self._proto(
            "clamp", "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n"))

    def test_subscripted_param_not_shareable(self):
        self.assertIsNone(self._proto("f", "def f(p):\n    return p[0]\n"))

    def test_attribute_param_not_shareable(self):
        self.assertIsNone(self._proto("f", "def f(p):\n    return p.x\n"))

    def test_iterated_param_not_shareable(self):
        self.assertIsNone(self._proto(
            "f", "def f(p):\n    s = 0.0\n    for v in p:\n        s += v\n    return s\n"))

    def test_len_sum_param_not_shareable(self):
        self.assertIsNone(self._proto(
            "centroid", "def centroid(pts):\n    return sum(pts) / len(pts)\n"))

    def test_single_arg_min_is_iterable_not_shareable(self):
        self.assertIsNone(self._proto("f", "def f(p):\n    return min(p)\n"))

    def test_return_container_not_shareable(self):
        self.assertIsNone(self._proto("f", "def f(x):\n    return [x, x * 2.0]\n"))

    def test_comprehension_over_param_not_shareable(self):
        self.assertIsNone(self._proto(
            "f", "def f(p):\n    return sum(v * v for v in p)\n"))

    def test_cpp_keyword_param_not_shareable(self):
        self.assertIsNone(self._proto("f", "def f(new, max):\n    return new + max\n"))
        self.assertIsNone(self._proto("g", "def g(int):\n    return int + 1.0\n"))

    def test_units_skips_node_with_any_unshareable_helper(self):
        # A vector helper like centroid is now NON-scalar shareable, so the
        # disqualifier must be genuinely untypeable -- here, one that CALLS a
        # parameter as a function.
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k\n"},
            {"module": "m", "name": "apply_fn",
             "source": "def apply_fn(g, x):\n    return g(x)\n"}]}
        self.assertEqual(porter._shareable_helper_units(spec), [])


class TestSharedUnitForwardDecls(unittest.TestCase):
    """A helper that calls a sibling helper must compile regardless of emission
    order -- the shared unit forward-declares every helper before defining any."""

    def test_protos_precede_defs(self):
        from mpynode.native.compiler import bundler
        blocks = [
            {"name": "mpyh_A", "proto": "double mpyh_A(double x)",
             "code": "double mpyh_A(double x) { return mpyh_B(x) + 1.0; }"},
            {"name": "mpyh_B", "proto": "double mpyh_B(double x)",
             "code": "double mpyh_B(double x) { return x * 2.0; }"},
        ]
        cpp = bundler.make_shared_helpers_cpp(blocks)
        # both prototypes appear, before the first definition body.
        self.assertIn("double mpyh_A(double x);", cpp)
        self.assertIn("double mpyh_B(double x);", cpp)
        self.assertLess(cpp.index("double mpyh_B(double x);"),
                        cpp.index("return mpyh_B(x) + 1.0;"))

    def test_sibling_calling_unit_compiles(self):
        # The real bug: A defined before B but A calls B. With forward decls the
        # shared unit must compile. Uses clang directly (no Maya needed).
        import shutil
        import subprocess
        import tempfile
        from mpynode.native.toolchain import toolchain
        from mpynode.native.compiler import bundler

        cxx = shutil.which(toolchain.default_compiler()) or shutil.which("clang++")
        if not cxx:
            self.skipTest("no C++ compiler available")
        blocks = [
            {"name": "mpyh_A", "proto": "double mpyh_A(double x)",
             "code": "double mpyh_A(double x) { return mpyh_B(x) + 1.0; }"},
            {"name": "mpyh_B", "proto": "double mpyh_B(double x)",
             "code": "double mpyh_B(double x) { return x * 2.0; }"},
        ]
        d   = tempfile.mkdtemp(prefix="shared_compile_")
        src = os.path.join(d, "shared_helpers.cpp")
        with open(src, "w") as fh:
            fh.write(bundler.make_shared_helpers_cpp(blocks))
        obj = os.path.join(d, "shared_helpers.o")
        proc = subprocess.run([cxx, "-std=c++17", "-c", src, "-o", obj],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         "shared unit with sibling call must compile; stderr:\n%s"
                         % proc.stderr)


class TestPorterBundlerRoundTrip(unittest.TestCase):
    """A porter-emitted marked block must be cleanly extractable by the bundler
    -- they are the two halves of the same contract."""

    def test_roundtrip(self):
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler
        name, proto = porter._derive_scalar_proto(
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k + 1.0\n"})
        code = "%s { return x * k + 1.0; }" % proto
        blk  = porter._marked_block(name, proto, code)
        _t, blocks = bundler._extract_shared_helpers("pre\n" + blk + "post\n")
        self.assertEqual(len(blocks),        1)
        self.assertEqual(blocks[0]["name"],  name)
        self.assertEqual(blocks[0]["proto"], proto)
        self.assertIn("return x * k + 1.0;", blocks[0]["code"])


# ===================== from test_nonscalar_helpers.py =====================
import ast
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__nonscalar_helpers():
    standalone_init()


def _fn(src, name):
    """Parse ``src`` and return the top-level FunctionDef named ``name``."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError("no def %r in source" % name)


# ---------------------------------------------------------------------------
# (1) _nonscalar_shareable -- the relaxed twin of _scalar_safe
# ---------------------------------------------------------------------------


class TestNonScalarShareable(unittest.TestCase):
    def test_subscripted_param_is_nonscalar_shareable(self):
        from mpynode.native.ai import porter
        self.assertTrue(porter._nonscalar_shareable(
            _fn("def vdot(a, b):\n    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]\n",
                "vdot")))

    def test_len_sum_param_is_nonscalar_shareable(self):
        from mpynode.native.ai import porter
        self.assertTrue(porter._nonscalar_shareable(
            _fn("def centroid(pts):\n    return sum(pts) / len(pts)\n",
                "centroid")))

    def test_iterated_param_is_nonscalar_shareable(self):
        from mpynode.native.ai import porter
        self.assertTrue(porter._nonscalar_shareable(
            _fn("def f(p):\n    s = 0.0\n    for v in p:\n        s += v\n    return s\n",
                "f")))

    def test_np_call_on_param_is_nonscalar_shareable(self):
        from mpynode.native.ai import porter
        self.assertTrue(porter._nonscalar_shareable(
            _fn("import numpy as np\ndef f(a, b):\n    return np.dot(a, b)\n", "f")))

    def test_varargs_still_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(*a):\n    return 0\n", "f")))

    def test_defaults_still_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(a, k=1.0):\n    return a[0]\n", "f")))

    def test_cpp_keyword_param_still_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(new, a):\n    return a[0]\n", "f")))

    def test_calling_a_param_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(g, x):\n    return g(x)\n", "f")))

    def test_dict_return_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(p):\n    return {0: p[0]}\n", "f")))

    def test_set_return_not_shareable(self):
        from mpynode.native.ai import porter
        self.assertFalse(porter._nonscalar_shareable(
            _fn("def f(p):\n    return {p[0], p[1]}\n", "f")))


# ---------------------------------------------------------------------------
# (2) _parse_helper_proto -- pull the LLM-chosen signature off the PROTO: line
# ---------------------------------------------------------------------------


class TestParseHelperProto(unittest.TestCase):
    def test_parses_proto_and_body(self):
        from mpynode.native.ai import porter
        proto, code = porter._parse_helper_proto(
            "PROTO: double mpyh_x(const MVector& a, const MVector& b)\n"
            "double mpyh_x(const MVector& a, const MVector& b) {\n"
            "    return a.x*b.x + a.y*b.y + a.z*b.z;\n}\n")
        self.assertEqual(proto, "double mpyh_x(const MVector& a, const MVector& b)")
        self.assertIn("a.x*b.x", code)
        self.assertNotIn("PROTO:", code)

    def test_strips_fences(self):
        from mpynode.native.ai import porter
        proto, code = porter._parse_helper_proto(
            "```cpp\n"
            "PROTO: double mpyh_y(const MVector& a)\n"
            "double mpyh_y(const MVector& a) { return a.x; }\n"
            "```")
        self.assertEqual(proto, "double mpyh_y(const MVector& a)")
        self.assertIn("return a.x;", code)

    def test_proto_is_derived_from_definition_not_the_proto_line(self):
        # The stored proto comes from the DEFINITION's signature, so a PROTO line
        # that disagrees with the def can never produce a mismatched forward decl.
        from mpynode.native.ai import porter
        proto, code = porter._parse_helper_proto(
            "PROTO: int wrong(double x)\n"                       # bogus hint line
            "double mpyh_z(const MVector& a) { return a.x; }\n")  # real def
        self.assertEqual(proto, "double mpyh_z(const MVector& a)")  # from the def

    def test_missing_proto_line_raises(self):
        from mpynode.native.ai import porter
        with self.assertRaises(porter._HelperProtoError):
            porter._parse_helper_proto("double f(int x) { return x; }")

    def test_proto_line_without_body_raises(self):
        from mpynode.native.ai import porter
        with self.assertRaises(porter._HelperProtoError):
            porter._parse_helper_proto("PROTO: double f(double x)\n")


# ---------------------------------------------------------------------------
# (3) _shareable_helper_units -- scalar vs nonscalar vs inline tagging
# ---------------------------------------------------------------------------


class TestShareableUnitsTagging(unittest.TestCase):
    def test_scalar_unit_tagged_scalar_with_fixed_proto(self):
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k + 1.0\n"}]}
        units = porter._shareable_helper_units(spec)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["kind"], "scalar")
        self.assertEqual(units[0]["proto"],
                         "double %s(double x, double k)" % units[0]["name"])

    def test_nonscalar_unit_tagged_nonscalar_proto_deferred(self):
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "vdot",
             "source": "def vdot(a, b):\n    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]\n"}]}
        units = porter._shareable_helper_units(spec)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["kind"], "nonscalar")
        self.assertIsNone(units[0]["proto"])           # chosen later by the LLM
        self.assertTrue(units[0]["name"].startswith("mpyh_"))
        self.assertEqual(units[0]["sym"], "vdot")

    def test_mixed_scalar_and_nonscalar_both_shareable(self):
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k + 1.0\n"},
            {"module": "m", "name": "vdot",
             "source": "def vdot(a, b):\n    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]\n"}]}
        units = porter._shareable_helper_units(spec)
        kinds = sorted(u["kind"] for u in units)
        self.assertEqual(kinds, ["nonscalar", "scalar"])

    def test_genuinely_unshareable_helper_forces_inline(self):
        # A dict-returning helper can't be typed -> the WHOLE node keeps inline.
        from mpynode.native.ai import porter
        spec = {"external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k\n"},
            {"module": "m", "name": "bag",
             "source": "def bag(p):\n    return {0: p[0]}\n"}]}
        self.assertEqual(porter._shareable_helper_units(spec), [])


# ---------------------------------------------------------------------------
# (4) _translate_helper -- nonscalar PROTO contract + translate-once memo
# ---------------------------------------------------------------------------


class TestTranslateHelperNonScalar(unittest.TestCase):
    def _unit(self):
        from mpynode.native.ai import porter
        src  = "def vdot(a, b):\n    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]\n"
        name = porter._helper_symbol("m", "vdot", src)
        return {"module": "m", "sym": "vdot", "source": src,
                "name": name, "proto": None, "kind": "nonscalar"}

    def test_nonscalar_prompt_and_parsed_proto(self):
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        u    = self._unit()
        seen = {}

        def spy(system, user):
            seen["system"] = system
            seen["user"]   = user
            return ("PROTO: double %s(const MVector& a, const MVector& b)\n"
                    "double %s(const MVector& a, const MVector& b) "
                    "{ return a.x*b.x+a.y*b.y+a.z*b.z; }" % (u["name"], u["name"]))

        r = porter._translate_helper(u, spy, [])
        self.assertEqual(seen["system"], porter._SYSTEM_HELPER)
        self.assertIn("PROTO:", seen["user"])   # nonscalar output contract
        self.assertIn(u["name"], seen["user"])  # the fixed name is given
        self.assertEqual(
            r["proto"], "double %s(const MVector& a, const MVector& b)" % u["name"])
        self.assertIn("a.x*b.x", r["code"])

    def test_translate_once_memoizes_chosen_proto(self):
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        u     = self._unit()
        calls = {"n": 0}

        def spy(system, user):
            calls["n"] += 1
            # a DIFFERENT proto on a 2nd call -> the memo must prevent it.
            sig = ("double %s(const MVector& a, const MVector& b)" % u["name"]
                   if calls["n"] == 1
                   else "double %s(double a, double b)" % u["name"])
            return "PROTO: %s\n%s { return 0.0; }" % (sig, sig)

        r1 = porter._translate_helper(u, spy, [])
        r2 = porter._translate_helper(u, spy, [])
        self.assertEqual(calls["n"], 1, "helper must be translated exactly once")
        self.assertEqual(r1["proto"], r2["proto"])
        self.assertIn("const MVector&", r1["proto"])

    def test_bad_translation_raises_sentinel(self):
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        u = self._unit()
        # No PROTO: line at all -> sentinel so the node falls back to inline.
        with self.assertRaises(porter._HelperProtoError):
            porter._translate_helper(
                u, lambda s, usr: "double f(double x){return x;}", [])

    def test_proto_must_use_the_fixed_name(self):
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        u = self._unit()
        # Right shape, WRONG name -> sentinel (call site would not link).
        with self.assertRaises(porter._HelperProtoError):
            porter._translate_helper(
                u, lambda s, usr: ("PROTO: double wrongName(const MVector& a)\n"
                                   "double wrongName(const MVector& a){return a.x;}"),
                [])


# ---------------------------------------------------------------------------
# (5) Regression anchors: SCALAR + NO-HELPER paths stay byte-identical
# ---------------------------------------------------------------------------


class TestScalarPathUnchanged(unittest.TestCase):
    def test_scalar_translate_prompt_is_the_fixed_signature_contract(self):
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        src = "def scaled(x, k):\n    return x * k + 1.0\n"
        name, proto = porter._derive_scalar_proto(
            {"module": "m", "name": "scaled", "source": src})
        unit = {"module": "m", "sym": "scaled", "source": src,
                "name": name, "proto": proto, "kind": "scalar"}
        seen = {}

        def spy(system, user):
            seen["system"] = system
            seen["user"]   = user
            return "%s { return x * k + 1.0; }" % proto

        r = porter._translate_helper(unit, spy, [proto])
        self.assertEqual(seen["system"], porter._SYSTEM_HELPER)
        self.assertIn("EXACTLY this name and signature", seen["user"])
        self.assertNotIn("PROTO:", seen["user"])  # scalar never asks for PROTO
        self.assertEqual(r["proto"], proto)       # fixed, not LLM-chosen

    def test_legacy_unit_without_kind_is_scalar(self):
        # A unit dict lacking a 'kind' key (older callers) must behave as scalar.
        from mpynode.native.ai import porter
        porter.reset_helper_memo()
        src = "def scaled(x, k):\n    return x * k + 1.0\n"
        name, proto = porter._derive_scalar_proto(
            {"module": "m", "name": "scaled", "source": src})
        unit = {"module": "m", "sym": "scaled", "source": src,
                "name": name, "proto": proto}     # NO 'kind'
        seen = {}

        def spy(system, user):
            seen["user"] = user
            return "%s { return x * k + 1.0; }" % proto

        porter._translate_helper(unit, spy, [proto])
        self.assertIn("EXACTLY this name and signature", seen["user"])
        self.assertNotIn("PROTO:", seen["user"])


# ---------------------------------------------------------------------------
# (6) Inline fallback control flow -- a shared node that won't compile retries
#     once on the robust inline path; the bundled cpp then has NO marked block.
# ---------------------------------------------------------------------------


def _port_spec():
    return {
        "mpy_type": "mPyNode", "source_node": "n",
        "suggested": {"class_name": "FooNode", "node_type_name": "fooNode",
                      "type_id": "0x00081234", "mpx_base": "MPxNode"},
        "inputs":  {"a": {"type": "float"}, "k": {"type": "float"}},
        "outputs": {"out": {"type": "float"}},
        "compute": "self.out = scaled(self.a, self.k)",
        "init":    "from m import scaled",
        "external_helpers": ("# --- from module 'm' ---\n"
                             "def scaled(x, k):\n    return x * k + 1.0"),
        "external_helper_units": [
            {"module": "m", "name": "scaled",
             "source": "def scaled(x, k):\n    return x * k + 1.0\n"}],
        "portability": {"portable": True, "blockers": []},
    }


class TestInlineFallbackControlFlow(unittest.TestCase):
    def setUp(self):
        import tempfile
        from mpynode.native.ai import porter
        self.porter = porter
        self.tmp    = tempfile.mkdtemp(prefix="nonscalar_fallback_")
        porter.reset_helper_memo()
        self._real_compile = porter.compile_cpp

    def tearDown(self):
        self.porter.compile_cpp = self._real_compile

    def test_shared_compile_failure_falls_back_to_inline(self):
        porter = self.porter

        # Fake compiler: a cpp that still carries the shared helper symbol is the
        # shared attempt -> "fails"; the inline retry (no mpyh_) -> "succeeds".
        def fake_compile(cpp_path, spec, out_dir, maya=None, compiler=None,
                         log_cb=None):
            with open(cpp_path) as fh:
                cpp = fh.read()
            ok = "mpyh_" not in cpp and "MPYNODE SHARED HELPER" not in cpp
            return ok, "log", (os.path.join(out_dir, "x.bundle") if ok else None)

        porter.compile_cpp = fake_compile

        def complete_fn(system, user):
            # Helper translate + both port modes: a trivial valid body. The shared
            # cpp still contains the injected marked block (mpyh_) regardless.
            return "h_aOut.setFloat(0.0f);"

        res = porter.port_node(_port_spec(), self.tmp, complete_fn=complete_fn,
                               max_fix_rounds=0)
        self.assertTrue(res["ok"], "inline fallback must recover the failed shared port")
        with open(res["cpp"]) as fh:
            final = fh.read()
        self.assertNotIn("MPYNODE SHARED HELPER", final,
                         "fallback cpp must be the inline path (no marked block)")
        self.assertNotIn("mpyh_", final)

    def test_no_helper_node_never_takes_fallback(self):
        # A node with no followed helpers must compile via the normal path with
        # shared_protos=None -- the fallback branch must not fire.
        porter = self.porter
        calls  = {"n": 0}

        def fake_compile(cpp_path, spec, out_dir, maya=None, compiler=None,
                         log_cb=None):
            calls["n"] += 1
            return True, "ok", os.path.join(out_dir, "x.bundle")

        porter.compile_cpp = fake_compile
        spec               = _port_spec()
        spec.pop("external_helpers")
        spec.pop("external_helper_units")
        res = porter.port_node(spec, self.tmp,
                               complete_fn=lambda s, u: "h_aOut.setFloat(0.0f);",
                               max_fix_rounds=0)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["n"], 1, "no-helper node compiles once, no retry")


# ---------------------------------------------------------------------------
# (7) Performance: optimizer flags in the toolchain argv builders
# ---------------------------------------------------------------------------


class TestOptimizerFlags(unittest.TestCase):
    def test_unix_one_shot_has_o3_ffp_contract_off(self):
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_to_plugin_cmd(
            "clang++", "foo.cpp", "/out/foo.bundle",
            include_dir="/M/include", lib_dir="/M/lib", libs=["OpenMaya"],
            os_name="darwin", arch="arm64")
        self.assertIn("-O3", got)
        self.assertIn("-ffp-contract=off", got)
        self.assertNotIn("-O2", got)

    def test_unix_object_has_o3_ffp_contract_off(self):
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_object_cmd(
            "clang++", "/x/frag.cpp", "/x/frag.o",
            include_dir="/M/include", frag=True, os_name="darwin", arch="arm64")
        self.assertIn("-O3", got)
        self.assertIn("-ffp-contract=off", got)
        self.assertNotIn("-O2", got)

    def test_linux_object_has_o3_ffp_contract_off(self):
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_object_cmd(
            "g++", "/x/frag.cpp", "/x/frag.o",
            include_dir="/M/include", frag=True, os_name="linux")
        self.assertIn("-O3", got)
        self.assertIn("-ffp-contract=off", got)
        self.assertNotIn("-O2", got)

    def test_msvc_one_shot_has_O2(self):
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_to_plugin_cmd(
            "cl", r"C:\src\foo.cpp", r"C:\out\foo.mll",
            include_dir=r"C:\M\include", lib_dir=r"C:\M\lib", libs=["OpenMaya"],
            os_name="win32")
        self.assertIn("/O2", got)

    def test_msvc_object_has_O2(self):
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_object_cmd(
            "cl", r"C:\x\frag.cpp", r"C:\x\frag.obj",
            include_dir=r"C:\M\include", frag=True, os_name="win32")
        self.assertIn("/O2", got)

    def test_no_ffast_math_anywhere(self):
        # -O2 must NOT bring -ffast-math/-Ofast (that breaks IEEE parity).
        from mpynode.native.toolchain import toolchain as tc
        got = tc.compile_to_plugin_cmd(
            "clang++", "foo.cpp", "/out/foo.bundle",
            include_dir="/M/include", lib_dir="/M/lib", libs=["OpenMaya"],
            os_name="darwin", arch="arm64")
        self.assertNotIn("-ffast-math", got)
        self.assertNotIn("-Ofast", got)


# ---------------------------------------------------------------------------
# (8) Shared C++ unit can host MVector/MMatrix helpers (typed signatures)
# ---------------------------------------------------------------------------


class TestSharedUnitVectorIncludes(unittest.TestCase):
    def test_typed_helper_pulls_full_maya_superset(self):
        # Any Maya-typed block -> the FULL Maya math header superset, so a helper
        # that compiled in its (broad-include) node skeleton ALSO compiles here.
        from mpynode.native.compiler import bundler
        blocks = [{
            "name":  "mpyh_v",
            "proto": "double mpyh_v(const MVector& a, const MVector& b)",
            "code": ("double mpyh_v(const MVector& a, const MVector& b) "
                     "{ return a.x*b.x+a.y*b.y+a.z*b.z; }")}]
        cpp = bundler.make_shared_helpers_cpp(blocks)
        for hdr in ("maya/MVector.h", "maya/MMatrix.h", "maya/MPoint.h",
                    "maya/MEulerRotation.h", "maya/MQuaternion.h"):
            self.assertIn(hdr, cpp)
        self.assertIn("<cmath>", cpp)             # scalar base still present

    def test_meulerrotation_helper_pulls_its_header(self):
        # Regression for the hard-abort bug: a helper that compiles standalone
        # (the node skeleton includes MEulerRotation.h) must also get the header
        # in the shared unit, or the whole bundle link aborts.
        from mpynode.native.compiler import bundler
        blocks = [{
            "name":  "mpyh_e",
            "proto": "MEulerRotation mpyh_e(const MEulerRotation& r)",
            "code": "MEulerRotation mpyh_e(const MEulerRotation& r) { return r; }"}]
        cpp = bundler.make_shared_helpers_cpp(blocks)
        self.assertIn("maya/MEulerRotation.h", cpp)

    def test_scalar_only_unit_has_no_maya_headers(self):
        # A scalar-only shared unit stays byte-identical to before: no Maya
        # headers (so it compiles with a bare compiler, no Maya include path).
        from mpynode.native.compiler import bundler
        blocks = [{
            "name": "mpyh_s", "proto": "double mpyh_s(double x)",
            "code": "double mpyh_s(double x) { return x * 2.0; }"}]
        cpp = bundler.make_shared_helpers_cpp(blocks)
        self.assertNotIn("maya/", cpp)

    def test_identifier_named_like_maya_type_does_not_pull_headers(self):
        # Word-boundary token match: a scalar helper with a local 'MAX' must NOT
        # drag in Maya headers (which would break its bare-compiler build).
        from mpynode.native.compiler import bundler
        blocks = [{
            "name": "mpyh_c", "proto": "double mpyh_c(double x)",
            "code": "double mpyh_c(double x) { double MAX = 9.0; return x<MAX?x:MAX; }"}]
        cpp = bundler.make_shared_helpers_cpp(blocks)
        self.assertNotIn("maya/", cpp)


# ---------------------------------------------------------------------------
# (9) Performance + type-mapping guidance reaches BOTH prompt paths
# ---------------------------------------------------------------------------


class TestPerfGuidanceReach(unittest.TestCase):
    def test_core_has_perf_and_type_mapping(self):
        from mpynode.native.ai import translation_knowledge as tk
        self.assertIn("PERFORMANCE", tk.CORE)
        self.assertIn("const&", tk.CORE)
        self.assertIn("reserve()", tk.CORE)
        self.assertIn("-ffast-math", tk.CORE)           # the determinism guard
        self.assertIn("std::vector<MVector>", tk.CORE)  # canonical type table

    def test_system_helper_has_type_mapping_perf_and_proto_contract(self):
        from mpynode.native.ai import porter
        self.assertIn("const MVector&", porter._SYSTEM_HELPER)
        self.assertIn("std::vector<double>", porter._SYSTEM_HELPER)
        self.assertIn("PROTO:", porter._SYSTEM_HELPER)  # nonscalar output contract
        self.assertIn("const&", porter._SYSTEM_HELPER)  # perf bullet


def setUpModule():
    _setUpModule__import_follower()
    _setUpModule__shared_helpers()
    _setUpModule__nonscalar_helpers()


if __name__ == "__main__":
    import unittest
    unittest.main()
