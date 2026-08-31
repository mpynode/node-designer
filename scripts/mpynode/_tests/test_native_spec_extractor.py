""".mpn -> native spec adapter + spec_extractor capture-only-when-non-empty contracts

Consolidated from: test_mpn_spec_adapter.py, test_metadata_spec_and_controller.py, test_locator_default_capture.py, test_preset_attr_capture.py, test_spec_capture_named_presets.py.
"""

from __future__ import annotations

# ===================== from test_mpn_spec_adapter.py =====================
import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__mpn_spec_adapter():
    standalone_init()


class TestAdapterPure(unittest.TestCase):
    """Pure-function behavior -- no live node needed."""

    def _payload(self, **over):
        p = {
            "native_type": "mPyNode",
            "node_name": "foo",
            "expression": "out = x",
            "input_attrs": {"x": {"attr_type": "float"}},
            "output_attrs": {"out": {"attr_type": "float"}},
            "stored_vars": {"k": 3},
        }
        p.update(over)
        return p

    def test_basic_shape(self):
        from mpynode.native.spec import spec_extractor as sx
        from mpynode.native.spec import mpn_spec_adapter as adapter

        spec = adapter.spec_from_mpn_payload(self._payload())
        self.assertEqual(spec["schema_version"], sx.SCHEMA_VERSION)
        self.assertEqual(spec["source_node"], "foo")
        self.assertEqual(spec["mpy_type"], "mPyNode")
        self.assertEqual(spec["suggested"]["node_type_name"], sx._sanitize_ident("foo"))
        self.assertEqual(spec["suggested"]["type_id"], sx.suggest_type_id("foo"))
        self.assertEqual(spec["suggested"]["mpx_base"], "MPxNode")
        self.assertEqual(spec["inputs"]["x"], sx.normalize_attr({"attr_type": "float"}))
        self.assertEqual(spec["outputs"]["out"], sx.normalize_attr({"attr_type": "float"}))
        self.assertEqual(spec["variables"]["k"], sx._summarize_var(3))
        self.assertEqual(spec["compute"], "out = x")
        self.assertEqual(spec["init"], "")
        self.assertEqual(spec["affects"], "all")
        self.assertIn("portability", spec)  # ALWAYS present

    def test_optional_keys_omitted_when_empty(self):
        from mpynode.native.spec import mpn_spec_adapter as adapter

        spec = adapter.spec_from_mpn_payload(self._payload())
        for k in ("methods", "commands", "metadata",
                  "external_helpers", "external_helper_units", "needs_hover"):
            self.assertNotIn(k, spec)
        # No live classification, and no spurious reads_image_file.
        self.assertNotIn("classification", spec["suggested"])
        self.assertNotIn("reads_image_file", spec["suggested"])

    def test_methods_and_metadata_added_when_present(self):
        from mpynode.native.spec import mpn_spec_adapter as adapter
        from mpynode._common.methods import maya_command
        from mpynode._common.lifecycle import metadata_registry as md

        methods_src = (
            "from mpynode import maya_command\n"
            "@maya_command\n"
            "def do_thing(self):\n"
            "    return 1\n"
        )
        meta = {"authors": ["me"], "version": "1.0"}
        spec = adapter.spec_from_mpn_payload(
            self._payload(methods_source=methods_src, metadata=meta))
        self.assertEqual(spec["methods"], methods_src)
        self.assertEqual(spec["commands"], maya_command.detect_commands(methods_src))
        self.assertEqual(spec["metadata"], md.coerce(meta))

    def test_assess_portability_uses_raw_maps(self):
        """A python-typed input must register as a blocker -- proving the RAW
        attr map (attr_type=...) reaches assess_portability, not normalize_attr's
        output (which renames the key to 'type')."""
        from mpynode.native.spec import mpn_spec_adapter as adapter

        spec = adapter.spec_from_mpn_payload(
            self._payload(input_attrs={"p": {"attr_type": "python"}}))
        self.assertFalse(spec["portability"]["portable"])
        self.assertTrue(any("python" in b for b in spec["portability"]["blockers"]))

    def test_locator_needs_hover_reproduced(self):
        from mpynode.native.spec import mpn_spec_adapter as adapter

        loc = adapter.spec_from_mpn_payload({
            "native_type": "mPyLocator", "node_name": "L",
            "expression": "if self.hovered:\n    pass\n"})
        self.assertTrue(loc.get("needs_hover"))
        # The hover flag is locator-gated (matches extract_spec).
        non = adapter.spec_from_mpn_payload({
            "native_type": "mPyNode", "node_name": "N",
            "expression": "if self.hovered:\n    pass\n"})
        self.assertNotIn("needs_hover", non)

    def test_adapter_module_has_no_maya_import(self):
        import ast

        from mpynode.native.spec import mpn_spec_adapter as adapter

        tree = ast.parse(inspect.getsource(adapter))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        offenders = [m for m in imported if (m or "").split(".")[0] == "maya"]
        self.assertEqual(offenders, [], "adapter must not import maya")


class TestAdapterEquivalence(unittest.TestCase):
    """The primary anchor: a file-sourced spec must equal the live extract_spec
    spec for a plain mPyNode (no documented deltas apply)."""

    def setUp(self):
        ensure_plugins_loaded()

    def test_equivalence_against_extract_spec(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.native.spec import spec_extractor as sx
        from mpynode.native.spec import mpn_spec_adapter as adapter
        from mpynode._common.io import mpn_io
        from mpynode._common.storedvars.stored_vars_api import set_variable

        n = MPyNode.create(name="equiv_node")
        nm = n.get_name()
        n.add_input_attr("amount", "float", False)
        n.add_output_attr("result", "float", False)
        n.set_compute_expression("result = amount * 2")
        n.set_init_expression("self.k = 1\n")
        set_variable(nm, "scale", 3, persistent=True)

        live = sx.extract_spec(nm)
        payload = mpn_io.serialize_node(n)
        from_file = adapter.spec_from_mpn_payload(payload)
        self.assertEqual(from_file, live)

    def test_equivalence_mpyfile_presets_against_extract_spec(self):
        # #48 (D3): the .mpn adapter reproduces the mPyFile texture PRESET
        # interface via a transient node, so a file-sourced mPyFile spec must
        # equal the live one -- else the port_cache key splits in two.
        import maya.cmds as cmds
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.native.spec import spec_extractor as sx
        from mpynode.native.spec import mpn_spec_adapter as adapter
        from mpynode._common.io import mpn_io

        cmds.file(new=True, force=True)
        f = MPyFile.create(name="equivTex#", seed_defaults=True, as_texture=False)
        f.add_input_attr("gain", "float")
        f.set_compute_expression(
            "u, v = self.uvCoord\n"
            "self.outColor = (u * self.gain, v * self.gain, 0.0)\n"
            "self.outAlpha = 1.0\n")

        live = sx.extract_spec(f.get_name())
        payload = mpn_io.serialize_node(f)
        from_file = adapter.spec_from_mpn_payload(payload)
        # The texture interface must be present + identical (types + membership).
        self.assertEqual(from_file["inputs"], live["inputs"])
        self.assertEqual(from_file["outputs"], live["outputs"])
        self.assertEqual(from_file["inputs"]["uvCoord"]["type"], "float2")
        self.assertEqual(from_file["outputs"]["outColor"]["type"], "color")
        self.assertEqual(from_file["outputs"]["outAlpha"]["type"], "float")


# ===================== from test_metadata_spec_and_controller.py =====================
import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__metadata_spec_and_controller():
    standalone_init()
    ensure_plugins_loaded()


class TestSpecCapturesMetadata(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_metadata_in_spec_when_set(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="specMetaSrc")
        n.add_input_attr("a", "float")
        n.add_output_attr("b", "float")
        n.set_compute_expression("self.b = a")
        n.set_metadata({"license": "(c) 2026 Acme", "version": "1.4"})
        spec = spec_extractor.extract_spec(n.get_name())
        self.assertIn("metadata", spec)
        self.assertEqual(spec["metadata"]["license"], "(c) 2026 Acme")
        self.assertEqual(spec["metadata"]["version"], "1.4")

    def test_no_metadata_means_no_key(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="plainSpecMeta")
        n.add_input_attr("a", "float")
        n.add_output_attr("b", "float")
        n.set_compute_expression("self.b = a")
        spec = spec_extractor.extract_spec(n.get_name())
        self.assertNotIn("metadata", spec)


class TestControllerDefaultsMerge(unittest.TestCase):
    """The pure merge step the controller applies before codegen."""

    def test_empty_node_field_falls_back_to_default(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = [{"suggested": {}, "metadata": {"version": "9.9"}}]
        cc._merge_metadata_defaults_into_specs(
            specs, {"license": "(c) Global", "version": "1.0"})
        m = specs[0]["metadata"]
        self.assertEqual(m["version"], "9.9")        # node wins
        self.assertEqual(m["license"], "(c) Global")  # filled from default

    def test_defaults_applied_to_node_without_metadata(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = [{"suggested": {}}]
        cc._merge_metadata_defaults_into_specs(specs, {"license": "(c) Global"})
        self.assertEqual(specs[0]["metadata"]["license"], "(c) Global")

    def test_no_node_meta_and_no_defaults_leaves_spec_clean(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = [{"suggested": {}}]
        cc._merge_metadata_defaults_into_specs(specs, {})
        # cache-stable: no metadata key added when nothing to embed
        self.assertNotIn("metadata", specs[0])


# ===================== from test_locator_default_capture.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__locator_default_capture():
    standalone_init()


class TestNeedsHoverDetection(unittest.TestCase):
    """Pure: detect the hover/auto-refresh markers in a draw expression."""

    def test_detects_self_hovered(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertTrue(se.detect_needs_hover("scale = 1.0 if self.hovered else 0.5"))

    def test_detects_precise_hover_and_auto_refresh(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertTrue(se.detect_needs_hover("self.precise_hover = True"))
        self.assertTrue(se.detect_needs_hover("self.auto_refresh = True"))

    def test_no_markers_is_false(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertFalse(se.detect_needs_hover(
            "import numpy as np\n"
            "self.draw = DrawCurve(np.zeros((3, 3)))\n"))

    def test_marker_only_in_comment_or_string_is_false(self):
        from mpynode.native.spec import spec_extractor as se
        # _self_attr_refs skips comments/strings, so a stray mention doesn't count.
        self.assertFalse(se.detect_needs_hover("# self.hovered would be nice\n"
                                               "x = 'self.hovered'\n"))


class TestPortabilityCommentStripping(unittest.TestCase):
    """Pure: assess_portability must scan real CODE only, not comments/strings.

    A non-portable TOKEN that appears only inside a ``# comment`` or a string
    literal must NOT flip portable=False. This is the spine bug: the init comment
    ``# Init tab -- runs once per file open (not per compute()).`` matched the
    bare-``open(`` blocker and hard-rejected an otherwise pure-numpy node. A
    genuine call in real code must still be blocked.
    """

    def _assess(self, compute, init=""):
        from mpynode.native.spec import spec_extractor as se
        return se.assess_portability(compute, init, {}, {}, {})

    def test_open_in_comment_is_not_a_blocker(self):
        # The exact spine init comment that trips the false positive today.
        init = ("# Init tab -- runs once per file open (not per compute()).\n"
                "import numpy as np\n")
        res = self._assess("out = 1.0", init)
        self.assertTrue(res["portable"], res["blockers"])
        self.assertNotIn("file I/O via open() (not portable)", res["blockers"])

    def test_open_in_string_is_not_a_blocker(self):
        res = self._assess("msg = 'remember to open() the file'\nout = 1.0")
        self.assertTrue(res["portable"], res["blockers"])

    def test_real_open_call_is_still_DETECTED(self):
        # Guard: a genuine open() in code must still be SEEN. It no longer
        # blocks -- valid Python is never refused -- but it must reach the
        # porter as a stated gap, which is what `unported` carries.
        res = self._assess("f = open('x.txt')\nout = 1.0")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertTrue(any("open()" in u for u in res["unported"]),
                        res["unported"])

    def test_blendshape_target_read_at_a_RUNTIME_index_is_DETECTED(self):
        # The gate detects by CAPABILITY, not by attribute name. nd_lower
        # rewrites a geometry-multi read only at a LITERAL index, so a runtime
        # index cannot lower -- reported as a gap (naming bake_deltas), not a
        # refusal.
        res = self._assess(
            "mesh = self.outputGeometry[0]\n"
            "base = mesh.getPoints()\n"
            "for i in range(4):\n"
            "    tgt = self.targetGeometry[i]\n"
            "mesh.setPoints(base)\n")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertTrue(any("targetGeometry" in u for u in res["unported"]),
                        res["unported"])

    def test_blendshape_target_read_at_a_LITERAL_index_is_allowed(self):
        # The same attribute at a constant index lowers today, so blocking it
        # would be a nominal rejection of working code.
        res = self._assess(
            "mesh = self.outputGeometry[0]\n"
            "base = mesh.getPoints()\n"
            "tgt = self.targetGeometry[0]\n"
            "mesh.setPoints(base)\n")
        self.assertTrue(res["portable"], res["blockers"])

    def test_targetgeometry_in_comment_is_not_flagged(self):
        # Guard: the word in a comment must not raise a phantom gap.
        res = self._assess("# reads self.targetGeometry someday\nout = 1.0")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertEqual([], res["unported"])

    def test_cmds_in_comment_ok_but_real_cmds_is_flagged(self):
        ok = self._assess("# cmds.polyCube() would be handy here\nout = 1.0")
        self.assertTrue(ok["portable"], ok["blockers"])
        self.assertEqual([], ok["unported"])
        # A real cmds. call is still detected, with adjacency (cmds.foo() no
        # space) preserved by the stripper so the scene-access regex fires.
        bad = self._assess("import maya.cmds as cmds\ncmds.polyCube()\nout = 1.0")
        self.assertTrue(bad["portable"], bad["blockers"])
        self.assertTrue(any("maya.cmds" in u for u in bad["unported"]),
                        bad["unported"])

    def test_hard_blocker_lib_in_string_is_ignored(self):
        # "import torch" as a data string must not drag in the torch gap.
        res = self._assess("doc = 'import torch to train'\nout = 1.0")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertEqual([], res["unported"])

    def _rng_warned(self, compute, init=""):
        return any("RNG" in w for w in self._assess(compute, init)["warnings"])

    def test_rng_in_a_comment_does_not_gate_the_parity_skip(self):
        # spec_uses_rng gates verify.py's pointwise-parity SKIP. It used to scan
        # RAW text while assess_portability scanned stripped code, so a WHY
        # comment naming np.random -- on a node with no RNG at all -- silently
        # turned parity checking OFF and printed a false skip reason.
        from mpynode.native.spec import spec_extractor as se

        compute = (
            "# deterministic hash noise -- deliberately NOT np.random, so the\n"
            "# compiled node stays bit-identical to Python.\n"
            "h = (np.arange(self.n) * 2654435761) % 4294967296\n"
            "self.out = (h / 4294967296.0).sum()\n")
        self.assertFalse(se.spec_uses_rng({"compute": compute, "init": ""}))
        self.assertFalse(self._rng_warned(compute))

    def test_rng_in_a_string_does_not_gate_the_parity_skip(self):
        from mpynode.native.spec import spec_extractor as se

        compute = ("msg = 'np.random.random is not used here'\n"
                   "self.out = float(self.a) + 1.0\n")
        self.assertFalse(se.spec_uses_rng({"compute": compute, "init": ""}))
        self.assertFalse(self._rng_warned(compute))

    def test_rng_in_REAL_code_is_still_DETECTED(self):
        # Guard on the other side: the skip must still fire for genuine RNG,
        # including when a comment sits on the same line as the call.
        from mpynode.native.spec import spec_extractor as se

        for compute in ("self.out = float(np.random.random())",
                        "rng = np.random.RandomState(12345)\nself.out = rng.rand()",
                        "self.out = float(np.random.random())  # seeded per compute",
                        "x = random.gauss(0, 1)\nself.out = x"):
            self.assertTrue(se.spec_uses_rng({"compute": compute, "init": ""}),
                            compute)

    def test_spec_uses_rng_and_assess_portability_never_diverge(self):
        # The two callers share uses_rng and MUST share its input, or the compile
        # log (parity skipped) and the manifest (no RNG warning) contradict.
        from mpynode.native.spec import spec_extractor as se

        for compute, init in (
                ("# mentions np.random only\nself.out = self.a", ""),
                ("self.out = self.a", "# np.random in the init comment\n"),
                ("doc = 'random.uniform'\nself.out = self.a", ""),
                ("self.out = float(np.random.random())", "import numpy as np"),
                ("x = random.uniform(0.0, 1.0)\nself.out = x", "import random")):
            self.assertEqual(
                se.spec_uses_rng({"compute": compute, "init": init}),
                self._rng_warned(compute, init),
                "detector/warning disagree for: %r" % compute)


class TestUnloweredFileIoIsReportedAsAGap(unittest.TestCase):
    """File I/O with no C++ kernel is REPORTED, not refused.

    It never blocks: valid Python is never turned away, and "we have not written
    that port" is the AI porter's problem to attempt. What the analyser owes is
    an honest statement of the gap, which is ``unported`` -- carried into the
    porter's prompt alongside the instruction to mark anything it cannot do
    (prompt._UNPORTED_RULE) and checked afterwards against the spliced body
    (prompt.scan_ported_body). So the discriminating assertion is no longer
    "portable is False" but "the gap was SEEN": a construct that silently
    produced no entry would reach the porter with no warning at all.
    """

    def _assess(self, compute, init="", allow_file_read=False):
        from mpynode.native.spec import spec_extractor as se
        return se.assess_portability(compute, init, {}, {}, {},
                                     allow_file_read=allow_file_read)

    def _gap(self, compute, needle, init=""):
        """Detected as a gap -- and NOT as a refusal."""
        res = self._assess(compute, init)
        self.assertTrue(res["portable"],
                        "%r must not be refused: %r" % (compute, res["blockers"]))
        self.assertTrue(any(needle in u for u in res["unported"]),
                        "%r -> %r" % (compute, res["unported"]))
        # Mirrored into warnings so existing readers render it unchanged.
        self.assertTrue(any(needle in w for w in res["warnings"]),
                        "%r -> %r" % (compute, res["warnings"]))

    def _no_gap(self, compute, init=""):
        """Lowers deterministically: no refusal AND nothing to tell the porter."""
        res = self._assess(compute, init)
        self.assertTrue(res["portable"], "%r -> %r" % (compute, res["blockers"]))
        self.assertEqual([], res["unported"], "%r -> %r" % (compute,
                                                            res["unported"]))

    def test_unlowerable_numpy_reads_are_flagged(self):
        # np.load is the interesting one: it is BINARY and would be easy to
        # lower, except it carries no dtype -- the compiled element type would
        # be a guess. The rest have no C++ reader at all.
        for src in ("import numpy as np\npts = np.load(self.path)\n",
                    "import numpy as np\npts = np.loadtxt(self.path)\n",
                    "import numpy as np\npts = np.genfromtxt(self.path)\n",
                    "import numpy as np\nm = np.memmap(self.path)\n"):
            self._gap(src, "numpy file I/O")

    def test_unlowerable_numpy_writes_are_flagged(self):
        for src in ("import numpy as np\nnp.savez(self.path, a=a)\n",
                    "import numpy as np\nnp.savetxt(self.path, a)\n"):
            self._gap(src, "numpy file I/O")

    def test_lowered_io_forms_raise_no_gap(self):
        # These three carry an explicit dtype (np.fromfile) or write verbatim
        # (np.save/.tofile), so py_to_cpp lowers them onto the nd_io kernel.
        # Flagging them would put a false gap in a working node's prompt.
        for src in ("import numpy as np\npts = np.fromfile(self.path, "
                    "dtype=np.float64)\n",
                    "import numpy as np\nnp.save(self.path, a)\n",
                    "import numpy as np\na.tofile(self.path)\n"):
            self._no_gap(src)

    def test_ndio_calls_raise_no_gap(self):
        # The sanctioned surface. Both halves exist (mpynode/ndio.py and
        # kernels/nd_io_cpp.py), so there is no gap to report.
        for src in ("from mpynode import ndio\n"
                    "pts = ndio.read(self.path, 'points')\n",
                    "from mpynode import ndio\n"
                    "n = ndio.read_raw(self.path, dtype=np.float64)\n",
                    "from mpynode import ndio\n"
                    "ndio.write(self.outPath, points=pts)\n",
                    "from mpynode import ndio\n"
                    "ndio.write_raw(self.outPath, pts)\n"):
            self._no_gap(src)

    def test_nonstandard_numpy_alias_is_resolved(self):
        # `import numpy as N` evades a \bnp\.load spelling; the alias pass
        # catches the ambiguous short names.
        self._gap("import numpy as N\npts = N.load(self.path)\n", "alias 'N'")

    def test_pathlib_read_write_is_flagged(self):
        for call in ("read_text", "read_bytes", "write_text", "write_bytes"):
            self._gap("t = Path(self.path).%s()\n" % call, "pathlib")

    def test_pickle_is_flagged(self):
        self._gap("import pickle\nd = pickle.loads(buf)\n", "pickle")

    def test_json_is_flagged(self):
        # Not file I/O per se, but the same missing lowering: json.loads returns
        # a dict, and the type lattice has no dict kind.
        self._gap("import json\nd = json.loads(self.blob)\n", "json")

    def test_texture_carve_out_does_not_silence_them(self):
        # allow_file_read sanctions an MImage read -- it must NOT make these
        # look handled. The carve-out exists because MImage::readFromFile is a
        # real kernel; np.load has none either way.
        res = self._assess("import numpy as np\npts = np.load(self.path)\n",
                           allow_file_read=True)
        self.assertTrue(any("numpy file I/O" in u for u in res["unported"]),
                        res["unported"])

    def test_mentions_in_comments_and_strings_raise_no_gap(self):
        # Same stripper contract as before: a mention is not a call. Now it
        # matters MORE -- a phantom entry would put a false gap in the prompt.
        for src in ("# one day: np.load(self.path)\nout = 1.0",
                    "doc = 'call np.loadtxt here'\nout = 1.0",
                    "# pickle.loads(buf) is forbidden\nout = 1.0",
                    "# json.loads(x)\nout = 1.0"):
            self._no_gap(src)

    def test_ordinary_numpy_math_is_untouched(self):
        # The regression that matters: normal vectorized code must stay clean.
        # np.random is a WARNING (verify-skip gate), never a gap.
        res = self._assess("import numpy as np\n"
                           "a = np.zeros((4, 3))\n"
                           "b = np.linspace(0.0, 1.0, 4)\n"
                           "c = np.random.rand(4)\n"
                           "out = float(np.dot(b, b))\n")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertEqual([], res["unported"])

    def test_similarly_named_user_calls_are_not_caught(self):
        # `self.load_cache()` / a var named `save` must not trip the numpy rule.
        self._no_gap("v = self.load_cache()\nsave = 1.0\nout = save\n")


class TestClosestPointMeshQueryIsClassified(unittest.TestCase):
    """A closest-point mesh query is SEEN, and its flag is set.

    It used to be classified nowhere: the voxelize template's whole algorithm is
    an MMeshIntersector sweep, yet its portability report named only the image
    read, so the porter was told nothing about the query. It is a real gap (no
    deterministic lowering) but an unusual one -- the C++ API is the identical
    class -- so the contract is BOTH halves: reported as a gap like everything
    else, AND flagged, because the flag is what emits the header the porter is
    forbidden to add.
    """

    def _assess(self, compute, init=""):
        from mpynode.native.spec import spec_extractor as se
        return se.assess_portability(compute, init, {}, {}, {})

    def test_mmeshintersector_is_reported_and_flagged(self):
        res = self._assess("import maya.api.OpenMaya as om\n"
                           "isect = om.MMeshIntersector()\n"
                           "isect.create(self.inMesh.to_mobject())\n")
        self.assertTrue(res["portable"], res["blockers"])
        self.assertTrue(res["uses_mesh_intersector"])
        self.assertTrue(any("closest-point mesh query" in u
                            for u in res["unported"]), res["unported"])
        # Mirrored into warnings, so every existing reader renders it unchanged.
        self.assertTrue(any("closest-point mesh query" in w
                            for w in res["warnings"]), res["warnings"])

    def test_reason_names_the_cpp_api_not_a_dead_end(self):
        # The gap text IS the porter's prompt for this construct: it has to carry
        # the 1:1 mapping, or the port can only be guessed at.
        res = self._assess("isect = om.MMeshIntersector()\n")
        gap = next(u for u in res["unported"] if "closest-point" in u)
        for needle in ("MMeshIntersector::create", "getClosestPoint",
                       "MPointOnMesh", "MMeshIntersector.h"):
            self.assertIn(needle, gap)

    def test_query_and_result_class_are_detected_on_their_own(self):
        # The construct can appear without the class name (MFnMesh's own query),
        # and the result class without the query (a helper that only unpacks it).
        for src in ("r = self.mesh.fn.getClosestPoint(om.MPoint(0, 0, 0))\n",
                    "def f(hit):\n    return isinstance(hit, om.MPointOnMesh)\n"):
            res = self._assess(src)
            self.assertTrue(res["uses_mesh_intersector"], src)

    def test_detected_in_INIT_as_well_as_compute(self):
        # The shipped voxelize template does its whole query inside an INIT
        # helper (_vox_closest); a compute-only scan would miss it entirely.
        res = self._assess("samples = _vox_closest(src.to_mobject(), grid)\n",
                           init="isect = om.MMeshIntersector()\n"
                                "r = isect.getClosestPoint(p)\n")
        self.assertTrue(res["uses_mesh_intersector"])

    def test_mentions_in_comments_and_strings_are_not_detected(self):
        # Same stripper contract as the file-I/O scans: a mention is not a call.
        # A phantom flag would emit a header (and re-key the port cache) for a
        # node that never queries anything.
        for src in ("# one day: om.MMeshIntersector()\nout = 1.0",
                    "doc = 'call getClosestPoint(p) here'\nout = 1.0"):
            res = self._assess(src)
            self.assertFalse(res["uses_mesh_intersector"], src)
            self.assertEqual([], res["unported"], src)

    def test_ordinary_mesh_math_is_untouched(self):
        # The regression that matters: a plain mesh node must not be flagged --
        # the flag changes generated C++, so a false positive is a false rebuild.
        res = self._assess("import numpy as np\n"
                           "pts = np.asarray(self.inMesh.points)\n"
                           "self.outMesh = Mesh(points=pts * 2.0)\n")
        self.assertFalse(res["uses_mesh_intersector"])
        self.assertEqual([], res["unported"], res["unported"])


class TestShouldCaptureDefault(unittest.TestCase):
    """Pure: which normalized input entries get a live-value default capture."""

    def test_scalar_without_default_wants_capture(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertTrue(se._input_wants_default_capture(
            {"type": "float", "is_array": False}))
        self.assertTrue(se._input_wants_default_capture(
            {"type": "enum", "is_array": False}))

    def test_already_defaulted_is_skipped(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertFalse(se._input_wants_default_capture(
            {"type": "float", "is_array": False, "default_value": 1.0}))

    def test_array_and_non_scalar_skipped(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertFalse(se._input_wants_default_capture(
            {"type": "float", "is_array": True}))
        self.assertFalse(se._input_wants_default_capture(
            {"type": "vector", "is_array": False}))
        self.assertFalse(se._input_wants_default_capture(
            {"type": "mesh", "is_array": False}))


class TestLocatorSpecCaptureIntegration(unittest.TestCase):
    """Real mPyLocator -> extract_spec captures the live default + needs_hover."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def _make_locator(self, name, draw_src):
        from mpynode.wrappers.mpy_locator import MPyLocator
        loc = MPyLocator.create(name=name)
        loc.add_input_attr("wire_width", "float")
        loc.set_compute_expression(draw_src)
        return loc

    def test_live_scalar_value_becomes_baked_default(self):
        from mpynode.native.spec import spec_extractor as se
        loc = self._make_locator(
            "capA",
            "w = self.wire_width\n"
            "import numpy as np\nself.lines = {'starts': np.zeros((1,3))}\n")
        mc.setAttr(loc.get_name() + ".wire_width", 2.0)
        spec = se.extract_spec(loc.get_name())
        self.assertAlmostEqual(
            spec["inputs"]["wire_width"].get("default_value"), 2.0,
            msg="live unconnected scalar value must be captured as the default")

    def test_connected_input_is_not_captured(self):
        from mpynode.native.spec import spec_extractor as se
        loc = self._make_locator(
            "capB",
            "w = self.wire_width\nself.lines = None\n")
        # Drive wire_width from another node -> default is irrelevant, skip.
        src = mc.createNode("addDoubleLinear")
        mc.connectAttr(src + ".output", loc.get_name() + ".wire_width")
        spec = se.extract_spec(loc.get_name())
        self.assertNotIn("default_value", spec["inputs"]["wire_width"],
                         "a connected/driven input must not capture a default")

    def test_needs_hover_set_when_draw_uses_hovered(self):
        from mpynode.native.spec import spec_extractor as se
        loc = self._make_locator(
            "capC",
            "s = 1.0 if self.hovered else 0.5\nself.lines = None\n")
        spec = se.extract_spec(loc.get_name())
        self.assertTrue(spec.get("needs_hover"))

    def test_needs_hover_absent_when_draw_has_no_hover(self):
        from mpynode.native.spec import spec_extractor as se
        loc = self._make_locator(
            "capD",
            "import numpy as np\nself.lines = {'starts': np.zeros((1,3))}\n")
        spec = se.extract_spec(loc.get_name())
        self.assertFalse(spec.get("needs_hover"))


# ===================== from test_preset_attr_capture.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__preset_attr_capture():
    standalone_init()
    ensure_plugins_loaded()


class TestNewAttrTypes(unittest.TestCase):
    """float2 + color are portable native types with C++ codegen hints."""

    def test_float2_is_portable(self):
        from mpynode.native.spec import spec_extractor as se
        n = se.normalize_attr({"attr_type": "float2"})
        self.assertEqual(n["type"], "float2")
        self.assertTrue(n["portable"])
        self.assertIsNotNone(n["cpp"])

    def test_color_is_portable(self):
        from mpynode.native.spec import spec_extractor as se
        n = se.normalize_attr({"attr_type": "color"})
        self.assertEqual(n["type"], "color")
        self.assertTrue(n["portable"])
        self.assertIsNotNone(n["cpp"])

    def test_quaternion_is_portable(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertIn("quaternion", se._NORM_TYPE)
        n = se.normalize_attr({"attr_type": "quaternion"})
        self.assertEqual(n["type"], "quaternion")
        self.assertTrue(n["portable"])
        self.assertIsNotNone(n["cpp"])


def _codegen_spec(inputs, outputs, compute="self.outColor = (0.0,0.0,0.0)"):
    """Minimal compute-family spec dict for codegen-only tests (no Maya node)."""
    from mpynode.native.spec import spec_extractor as se
    return {
        "suggested": {"node_type_name": "presetCgNode", "class_name": "PresetCgNode",
                      "type_id": "0x00070abc", "mpx_base": "MPxNode"},
        "compute": compute,
        "init": "",
        "inputs": {n: se.normalize_attr(m) for n, m in inputs.items()},
        "outputs": {n: se.normalize_attr(m) for n, m in outputs.items()},
        "variables": {},
        "portability": {"portable": True, "blockers": [], "warnings": []},
    }


class TestFloat2Codegen(unittest.TestCase):
    def test_float2_input_create_and_read(self):
        from mpynode.native import compiler as codegen
        spec = _codegen_spec({"uvCoord": {"attr_type": "float2"}},
                             {"outVal": {"attr_type": "float"}},
                             compute="u, v = self.uvCoord\nself.outVal = u + v")
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Two float children + a float2 compound parent.
        self.assertIn("asFloat2()", cpp)
        self.assertIn("uvCoord", cpp)
        # The read exposes in_<member> indexable as [0]/[1].
        self.assertIn("in_aUvCoord", cpp)


class TestColorCodegen(unittest.TestCase):
    def test_color_output_create_and_write(self):
        from mpynode.native import compiler as codegen
        spec = _codegen_spec({"uIn": {"attr_type": "float"}},
                             {"outColor": {"attr_type": "color"}},
                             compute="self.outColor = (self.uIn, 0.0, 0.0)")
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("createColor", cpp)
        # A `color` output written from a tuple literal lowers DETERMINISTICALLY
        # (nd_lower color writer -> set3Float), so there is NO AI PORT region.
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        self.assertIn("set3Float", cpp)

    def test_color_input_read(self):
        from mpynode.native import compiler as codegen
        spec = _codegen_spec({"borderColor": {"attr_type": "color"}},
                             {"outVal": {"attr_type": "float"}},
                             compute="self.outVal = self.borderColor[0]")
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("asFloat3()", cpp)
        self.assertIn("in_aBorderColor", cpp)


class TestQuaternionCodegen2(unittest.TestCase):
    def test_quaternion_input_read(self):
        from mpynode.native import compiler as codegen
        spec = _codegen_spec({"qIn": {"attr_type": "quaternion"}},
                             {"outVal": {"attr_type": "float"}},
                             compute="self.outVal = self.qIn[0] + self.qIn[3]")
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Generic compound: children read via MFnCompoundAttribute child handles.
        self.assertIn("MFnCompoundAttribute", cpp)
        self.assertIn("in_aQIn", cpp)
        self.assertIn("qInX", cpp)
        self.assertIn("qInW", cpp)

    def test_quaternion_output_write(self):
        from mpynode.native import compiler as codegen
        spec = _codegen_spec({"uIn": {"attr_type": "float"}},
                             {"qOut": {"attr_type": "quaternion"}},
                             compute="self.qOut = (0.0, 0.0, 0.0, 1.0)")
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Output compound seeds the identity default via child handles.
        self.assertIn("MFnCompoundAttribute", cpp)
        self.assertIn("setDouble", cpp)


class TestPresetCapture(unittest.TestCase):
    """extract_spec on an mPyFile captures the preset attrs its compute uses."""

    def _scanline_mpyfile(self):
        from mpynode.wrappers.mpy_file import MPyFile
        import maya.cmds as cmds
        cmds.file(new=True, force=True)
        f = MPyFile.create(name="presetCapTex#", seed_defaults=True,
                           as_texture=False)
        f.add_input_attr("tIn", "float")  # a user attr (merges with presets)
        f.set_compute_expression(
            "from PIL import Image\n"
            "img = Image.open(self.fileName)\n"
            "arr = np.asarray(img).astype('float32') / 255.0\n"
            "u, v = self.uvCoord\n"
            "px = int(u) % max(1, arr.shape[1])\n"
            "py = int(v) % max(1, arr.shape[0])\n"
            "rgb = arr[py, px, :3]\n"
            "scan = 0.5 + 0.5 * float((self.tIn % 2.0) > 1.0)\n"
            "self.outColor = (float(rgb[0]) * scan, float(rgb[1]) * scan, "
            "float(rgb[2]) * scan)\n"
            "self.outAlpha = 1.0\n")
        return f

    def test_captures_referenced_presets(self):
        from mpynode.native.spec import spec_extractor
        f = self._scanline_mpyfile()
        spec = spec_extractor.extract_spec(f.get_name())
        ins, outs = spec["inputs"], spec["outputs"]
        # Inputs: fileName (string), uvCoord (float2), + user tIn (float).
        self.assertIn("fileName", ins)
        self.assertEqual(ins["fileName"]["type"], "string")
        self.assertIn("uvCoord", ins)
        self.assertEqual(ins["uvCoord"]["type"], "float2")
        self.assertIn("tIn", ins)  # user attr survives
        # Outputs: outColor (color), outAlpha (float).
        self.assertIn("outColor", outs)
        self.assertEqual(outs["outColor"]["type"], "color")
        self.assertIn("outAlpha", outs)
        self.assertEqual(outs["outAlpha"]["type"], "float")

    def test_does_not_capture_unreferenced_presets(self):
        from mpynode.native.spec import spec_extractor
        f = self._scanline_mpyfile()
        spec = spec_extractor.extract_spec(f.get_name())
        # colorSpace / wrapModeU / preFilter are presets the compute never
        # references -> not dragged into the port.
        for unref in ("colorSpace", "wrapModeU", "preFilter", "mipmapMode"):
            self.assertNotIn(unref, spec["inputs"], unref)

    def test_injected_slots_not_captured(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_file import MPyFile
        import maya.cmds as cmds
        cmds.file(new=True, force=True)
        f = MPyFile.create(name="slotTex#", as_texture=False)
        # self.time is an injected API slot, NOT a DG attr -> must be skipped.
        f.set_compute_expression(
            "self.outColor = (self.time, 0.0, 0.0)\nself.outAlpha = 1.0")
        spec = spec_extractor.extract_spec(f.get_name())
        self.assertNotIn("time", spec["inputs"])
        self.assertNotIn("time", spec["outputs"])

    def test_reads_image_and_classification_present(self):
        from mpynode.native.spec import spec_extractor
        f = self._scanline_mpyfile()
        spec = spec_extractor.extract_spec(f.get_name())
        self.assertTrue(spec["suggested"].get("reads_image_file"))
        self.assertIn("texture/2d", spec["suggested"].get("classification", ""))
        self.assertTrue(spec["portability"]["portable"],
                        spec["portability"].get("blockers"))


class TestTextureInterfaceGuidance(unittest.TestCase):
    """The porter guide must teach float2 (uvCoord -> in_[0]/[1]) + color
    (outColor -> set3Float) handling when the spec carries those types."""

    def test_guidance_present_for_float2_and_color(self):
        from mpynode.native.ai import translation_knowledge as tk
        from mpynode.native.spec import spec_extractor as se
        spec = {
            "compute": "u, v = self.uvCoord\nself.outColor = (u, v, 0.0)",
            "init": "",
            "suggested": {},
            "inputs": {"uvCoord": se.normalize_attr({"attr_type": "float2"})},
            "outputs": {"outColor": se.normalize_attr({"attr_type": "color"})},
        }
        guide = tk.guide_for_spec(spec)
        self.assertIn("set3Float", guide)
        self.assertIn("uvCoord", guide.replace("in_<name>", "uvCoord") + " uvCoord")

    def test_guidance_absent_without_those_types(self):
        from mpynode.native.ai import translation_knowledge as tk
        from mpynode.native.spec import spec_extractor as se
        spec = {
            "compute": "self.b = self.a * 2", "init": "", "suggested": {},
            "inputs": {"a": se.normalize_attr({"attr_type": "float"})},
            "outputs": {"b": se.normalize_attr({"attr_type": "float"})},
        }
        guide = tk.guide_for_spec(spec)
        self.assertNotIn("TEXTURE INTERFACE ATTRS", guide)


class TestPresetCaptureGated(unittest.TestCase):
    """A plain mpynode is NOT preset-captured -> spec unchanged (cache stable)."""

    def test_plain_mpynode_has_no_phantom_presets(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds
        cmds.file(new=True, force=True)
        w = MPyNode.create(name="plainNode#")
        w.add_input_attr("a", "float")
        w.add_output_attr("b", "float")
        w.set_compute_expression("self.b = self.a * 2.0")
        spec = spec_extractor.extract_spec(w.get_name())
        self.assertEqual(set(spec["inputs"].keys()), {"a"})
        self.assertEqual(set(spec["outputs"].keys()), {"b"})


class TestPresetCaptureIgnoresCommentsAndStrings(unittest.TestCase):
    """Review finding #2: self.<name> in a COMMENT or STRING literal must NOT be
    captured (it would bloat the spec + the port-cache key). Only real code
    references count."""

    def test_preset_in_comment_or_string_not_captured(self):
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_file import MPyFile
        import maya.cmds as cmds
        cmds.file(new=True, force=True)
        f = MPyFile.create(name="commentTex#", seed_defaults=True,
                           as_texture=False)
        f.set_compute_expression(
            "# TODO: also honour self.wrapModeU and self.colorSpace later\n"
            "note = 'remember to set self.borderColor first'\n"
            "u, v = self.uvCoord\n"
            "self.outColor = (u, v, 0.0)\n"
            "self.outAlpha = 1.0\n")
        spec = spec_extractor.extract_spec(f.get_name())
        # Real code refs captured:
        self.assertIn("uvCoord", spec["inputs"])
        self.assertIn("outColor", spec["outputs"])
        # Comment/string-only refs NOT captured:
        for ghost in ("wrapModeU", "colorSpace", "borderColor"):
            self.assertNotIn(ghost, spec["inputs"], ghost)


class TestEnumLabelEscaping(unittest.TestCase):
    """Review finding #1: enum field labels (Maya/OCIO-supplied for captured
    presets -- the user can't sanitize them) must be C-string-escaped and honor
    explicit `Label=index` forms, or the generated C++ won't compile / mis-maps."""

    def _enum_spec(self, names):
        from mpynode.native.spec import spec_extractor as se
        return {
            "suggested": {"node_type_name": "enumCg", "class_name": "EnumCg",
                          "type_id": "0x00070abd", "mpx_base": "MPxNode"},
            "compute": "self.o = float(self.cs)", "init": "",
            "inputs": {"cs": se.normalize_attr(
                {"attr_type": "enum", "enum_names": names})},
            "outputs": {"o": se.normalize_attr({"attr_type": "float"})},
            "variables": {},
            "portability": {"portable": True, "blockers": [], "warnings": []},
        }

    def test_quote_and_backslash_escaped(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._enum_spec(['a "b" c', 'd\\e']),
                                   for_port=True)
        self.assertIn(r'\"b\"', cpp)              # quote escaped
        self.assertNotIn('"a "b" c"', cpp)        # not emitted raw
        self.assertIn(r'd\\e', cpp)               # backslash escaped

    def test_explicit_index_form_parsed(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._enum_spec(["Off=0", "On=5"]),
                                   for_port=True)
        # The '=5' must become the addField index, not part of the label.
        self.assertIn('addField("On", 5)', cpp)
        self.assertNotIn('On=5', cpp)

    def test_plain_enum_unchanged(self):
        # Backward-compat: no special chars / no '=' -> sequential, raw label.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._enum_spec(["Wrap", "Clamp", "Mirror"]),
                                   for_port=True)
        self.assertIn('addField("Wrap", 0)', cpp)
        self.assertIn('addField("Clamp", 1)', cpp)
        self.assertIn('addField("Mirror", 2)', cpp)


class TestVerifySkipsTextureTypes(unittest.TestCase):
    """Review finding #3 (updated by #1b): float2/uvCoord is the ONLY texture
    type the generic parity harness still can't drive (add_input_attr has no
    float2 kind), so a node carrying one must SKIP cleanly with an honest reason
    -- NOT raise. color (float3 usedAsColor) and quaternion (compound-4) are now
    rebuildable + driveable, so they no longer gate the check."""

    def test_verify_skips_float2_without_touching_maya(self):
        from mpynode.native.toolchain import verify as cc

        class _BoomCmds:
            def __getattr__(self, _n):
                def _f(*a, **k):
                    raise AssertionError(
                        "verify must NOT touch Maya for a float2 node")
                return _f

        spec = {
            "suggested": {"node_type_name": "texProc", "mpx_base": "MPxNode"},
            "compute": "u, v = self.uvCoord\nself.outColor = (u, v, 0.0)",
            "init": "",
            "inputs": {"uvCoord": {"type": "float2"}},
            "outputs": {"outColor": {"type": "color"}},
        }
        res = cc._verify_one(_BoomCmds(), "/x.bundle", spec)
        self.assertFalse(res["ran"])
        self.assertIsNone(res["pass"])
        self.assertIn("float2", res["reason"].lower())


# ===================== from test_spec_capture_named_presets.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__spec_capture_named_presets():
    standalone_init()
    ensure_plugins_loaded()


VIEWPORT_ONLY = ("filterMode", "maxAnisotropy", "mipmapMode",
                 "mipLODBias", "minLOD", "maxLOD")


class TestCaptureNamedPresets(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_file import MPyFile
        self.node = MPyFile.create(name="presetCap#", seed_defaults=False,
                                   as_texture=False).get_name()

    def test_captures_all_viewport_presets_with_real_types(self):
        from mpynode.native.spec import spec_extractor as SE
        got = SE.capture_named_presets(self.node, VIEWPORT_ONLY)
        for nm in VIEWPORT_ONLY:
            self.assertIn(nm, got, "viewport preset %r not captured" % nm)
        # Real types (not coerced): the enums must be enums (with field names),
        # the numeric ones int/float -- matching the Python node's attrs.
        self.assertEqual(got["filterMode"]["type"], "enum")
        self.assertEqual(got["mipmapMode"]["type"], "enum")
        self.assertEqual(got["maxAnisotropy"]["type"], "int")
        self.assertEqual(got["minLOD"]["type"], "int")
        self.assertEqual(got["maxLOD"]["type"], "int")
        self.assertEqual(got["mipLODBias"]["type"], "float")
        self.assertEqual(
            got["filterMode"].get("enum_names"),
            ["Point", "Linear", "Anisotropic"])
        self.assertEqual(got["mipmapMode"].get("enum_names"), ["None", "Auto"])

    def test_entries_are_portable_codegen_ready(self):
        from mpynode.native.spec import spec_extractor as SE
        got = SE.capture_named_presets(self.node, VIEWPORT_ONLY)
        for nm, entry in got.items():
            self.assertTrue(entry.get("portable"),
                            "%s must be portable for codegen" % nm)

    def test_skips_nonexistent_and_internal(self):
        from mpynode.native.spec import spec_extractor as SE
        got = SE.capture_named_presets(
            self.node, ("filterMode", "doesNotExist", "_inputAttrs"))
        self.assertIn("filterMode", got)
        self.assertNotIn("doesNotExist", got)
        self.assertNotIn("_inputAttrs", got)

    def test_merge_shape_matches_spec_inputs(self):
        """The returned entries must drop into spec['inputs'] verbatim (same shape
        normalize_attr produces) so a setdefault-merge is sound."""
        from mpynode.native.spec import spec_extractor as SE
        spec = SE.extract_spec(self.node)
        got = SE.capture_named_presets(self.node, VIEWPORT_ONLY)
        for nm, entry in got.items():
            spec["inputs"].setdefault(nm, entry)
        # the merged inputs are still all dicts with a 'type'
        for nm in VIEWPORT_ONLY:
            self.assertIn("type", spec["inputs"][nm])


def setUpModule():
    _setUpModule__mpn_spec_adapter()
    _setUpModule__metadata_spec_and_controller()
    _setUpModule__locator_default_capture()
    _setUpModule__preset_attr_capture()
    _setUpModule__spec_capture_named_presets()


if __name__ == "__main__":
    import unittest
    unittest.main()
