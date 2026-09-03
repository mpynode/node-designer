"""Importing a v1 (``node-designer``) node out of a ``.ma``.

Every fixture here is synthetic and small. The real corpus -- the nine scenes
in the upstream ``examples/`` folder -- is 10 MB and lives in another
repository, so the cases it exposed are reproduced as minimal `.ma` fragments
instead. Each of the parsing tests below corresponds to something a real file
actually did and an earlier draft of the importer got wrong.
"""

from __future__ import annotations

import base64
import io
import os
import pickle
import tempfile
import unittest

from mpynode._common.io import v1_import as V


def _b64(obj, protocol=pickle.HIGHEST_PROTOCOL):
    """base64 with the line breaks removed -- a MEL string literal cannot
    carry a raw newline, and the importer strips whitespace anyway."""
    raw = base64.encodebytes(pickle.dumps(obj, protocol=protocol)).decode()
    return "".join(raw.split())


def _ma(expression="", inputs=None, outputs=None, stored=None, wrap=False,
        name="v1node"):
    """A minimal .ma carrying one v1 mPyNode."""
    L = ['//Maya ASCII 2024 scene', 'requires maya "2024";',
         'createNode transform -name "someOtherNode";',
         'createNode mPyNode -name "%s";' % name,
         '\trename -uuid "AAAA-BBBB";']

    def setattr_str(plug, payload):
        if wrap:
            L.append('\tsetAttr ".%s" -type "string" (' % plug)
            chunk = 40
            bits = [payload[i:i + chunk] for i in range(0, len(payload), chunk)]
            for k, bit in enumerate(bits):
                L.append('\t\t%s"%s"' % ("" if k == 0 else "+ ", bit))
        else:
            L.append('\tsetAttr ".%s" -type "string" "%s";' % (plug, payload))

    if expression:
        setattr_str("expression", expression.replace("\n", chr(92) + "n"))
    if inputs is not None:
        setattr_str("_inputAttrs", _b64({k: [v] for k, v in inputs.items()}).strip())
    if outputs is not None:
        setattr_str("_outputAttrs", _b64({k: [v] for k, v in outputs.items()}).strip())
    if stored is not None:
        setattr_str("_storedVarsData", _b64(stored).strip())
    L.append('createNode lambert -name "trailing";')
    return "\n".join(L) + "\n"


def _write(text):
    fd, path = tempfile.mkstemp(suffix=".ma")
    os.close(fd)
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class TestReadingTheFile(unittest.TestCase):

    def _read(self, **kw):
        path = _write(_ma(**kw))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return V.read_v1_ma(path)

    def test_only_mpynodes_are_picked_up(self):
        nodes = self._read(expression="x = 1", inputs={"a": "float"})
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "v1node")

    def test_attrs_and_stored_vars_decode(self):
        n = self._read(expression="out = a",
                       inputs={"a": "float", "m": "matrix"},
                       outputs={"out": "vector"},
                       stored={"count": 7})[0]
        self.assertEqual(n.inputs, {"a": "float", "m": "matrix"})
        self.assertEqual(n.outputs, {"out": "vector"})
        self.assertEqual(n.stored_vars, {"count": 7})

    def test_the_payload_is_the_LAST_string_on_the_line(self):
        # `setAttr "._inputAttrs" -type "string" "<b64>"` has three quoted
        # runs. Taking the first yielded the plug name plus everything after
        # it, and every real file failed to decode.
        n = self._read(expression="out = a", inputs={"a": "float"},
                       outputs={"out": "float"})[0]
        self.assertEqual(n.inputs, {"a": "float"})

    def test_a_wrapped_multi_line_payload(self):
        # Maya splits any long string across `( "..." + "..." )`. Real files do
        # this for both the expression AND the pickle plugs once they are big
        # enough -- four of the nine upstream examples.
        n = self._read(expression="out = a\nout = out + 1",
                       inputs={"a": "float"}, outputs={"out": "float"},
                       stored={"k": list(range(40))}, wrap=True)[0]
        self.assertEqual(n.inputs, {"a": "float"})
        self.assertEqual(n.stored_vars["k"], list(range(40)))
        self.assertIn("out = a", n.expression)

    def test_a_continuation_run_ends_without_a_closing_paren_line(self):
        # Maya writes the final fragment and the ");" together, so the next
        # setAttr follows immediately. A parser waiting for a lone ")" ate the
        # rest of the node.
        n = self._read(expression="out = a", inputs={"a": "float"},
                       outputs={"out": "float"}, stored={"z": 1}, wrap=True)[0]
        self.assertEqual(n.stored_vars, {"z": 1})

    def test_mixed_pickle_protocols_in_one_node(self):
        # quaternionSpineNode.ma really is like this: written across the
        # Python 2 -> 3 migration, protocol 2 on one plug and 4 on another.
        path = _write(_ma(expression="out = a", inputs={"a": "float"},
                          outputs={"out": "float"})
                      .replace(_b64({"a": ["float"]}).strip(),
                               _b64({"a": ["float"]}, protocol=2).strip()))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertEqual(V.read_v1_ma(path)[0].inputs, {"a": "float"})

    def test_silently_empty_attrs_are_an_error(self):
        # v1's _loadPickle ends in a bare `except: pass`, so corrupt data reads
        # as empty. An expression with no attributes is far likelier to be that
        # than a genuinely attribute-less node.
        path = _write(_ma(expression="out = 1"))
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with self.assertRaises(V.V1ImportError):
            V.read_v1_ma(path)


class TestTheUnpickler(unittest.TestCase):
    """v1 stored vars can hold v1's OWN classes -- unitSphereCollisionNode.ma
    stores a list of ``mpylib._mpynode._openmaya.MPoint``. Requiring v1 on
    sys.path to read them would defeat the whole file-based approach."""

    def test_a_v1_class_demotes_to_plain_numbers(self):
        payload = (b'cmpylib._mpynode._openmaya' + bytes([10])
                   + b'MPoint' + bytes([10])
                   + b'(F1.0' + bytes([10]) + b'F2.0' + bytes([10])
                   + b'F3.0' + bytes([10]) + b'tR.')
        got = V._unpickle_b64(base64.encodebytes(payload).decode())
        self.assertEqual(got, [1.0, 2.0, 3.0])

    def test_an_unexpected_module_is_refused(self):
        # Untrusted input: allowing an explicit set beats letting pickle import
        # whatever it is told to.
        payload = (b'cos' + bytes([10]) + b'system' + bytes([10])
                   + b"(S'echo hi'" + bytes([10]) + b'tR.')
        with self.assertRaises(V.V1ImportError):
            V._unpickle_b64(base64.encodebytes(payload).decode())


class TestExpressionConversion(unittest.TestCase):

    def test_reads_and_writes_become_self(self):
        init, comp, rep = V.split_and_selfify(
            "out = a * 2", {"a": "float"}, {"out": "float"})
        self.assertIn("self.out", comp)
        self.assertIn("self.a", comp)
        self.assertEqual(rep["rewrites"], 2)

    def test_imports_and_defs_go_to_init(self):
        init, comp, rep = V.split_and_selfify(
            "import math\n\ndef helper(x):\n    return x + 1\n\nout = helper(a)",
            {"a": "float"}, {"out": "float"})
        self.assertIn("import math", init)
        self.assertIn("def helper", init)
        self.assertNotIn("def helper", comp)
        self.assertIn("self.out", comp)

    def test_a_shadowed_input_gets_an_alias_not_a_rewrite(self):
        # v1 semantics: assigning to an input made a plain local and did NOT
        # write the plug -- but the name still STARTED as the plug value, and
        # splineNode reads `degree` before assigning to it. Leaving it bare
        # alone raised NameError.
        init, comp, rep = V.split_and_selfify(
            "d = degree + 1\ndegree = 3\nout = degree",
            {"degree": "int"}, {"out": "int"})
        self.assertEqual(rep["shadowed"], ["degree"])
        self.assertEqual(comp.splitlines()[0], "degree = self.degree")
        self.assertNotIn("self.degree + 1", comp)

    def test_an_output_is_rewritten_even_though_it_is_assigned(self):
        # Assigning an output IS the plug write; that is the point.
        _i, comp, _r = V.split_and_selfify("out = 1", {}, {"out": "float"})
        self.assertIn("self.out = 1", comp)

    def test_strings_and_comments_are_untouched(self):
        # The reason this is an AST pass and not a regex.
        src = "# a is nice\nmsg = 'a'\nout = a"
        _i, comp, _r = V.split_and_selfify(src, {"a": "float"}, {"out": "float"})
        self.assertIn("'a'", comp)
        self.assertIn("self.a", comp)
        self.assertNotIn("self.a'", comp)

    def test_a_helper_reading_a_plug_as_a_global_is_reported(self):
        # v1 helpers saw plug values because they were module-level locals. In
        # v2 helpers live in Init and cannot see self, so these need finishing.
        _i, _c, rep = V.split_and_selfify(
            "def f():\n    return a\n\nout = f()",
            {"a": "float"}, {"out": "float"})
        self.assertEqual(rep["globals_in_defs"], ["a"])

    def test_a_syntax_error_is_reported_not_swallowed(self):
        with self.assertRaises(V.V1ImportError):
            V.split_and_selfify("def (:", {}, {})


class TestEnumSynthesis(unittest.TestCase):
    """v1 stored `['enum']` and no labels at all, and v2 rejects an enum with
    no enum_names -- so the importer has to invent them."""

    def test_the_count_comes_from_what_it_is_compared_against(self):
        names = V.synth_enum_names("mode", "if mode == 2:\n    pass")
        self.assertEqual(names, ["0", "1", "2"])

    def test_a_minimum_of_two(self):
        self.assertEqual(V.synth_enum_names("mode", "x = 1"), ["0", "1"])

    def test_unparseable_source_still_yields_something_usable(self):
        self.assertEqual(V.synth_enum_names("mode", "def (:"), ["0", "1"])


class TestHandFinishReporting(unittest.TestCase):
    """v1 handed plug values as its own MPoint/MVector/MMatrix shims and made
    those names ambient; v2 hands numpy and MatrixView. Arithmetic written
    against the old model does not type-check, and no converter can guess its
    way through that -- so it is reported."""

    def _spec(self, expr, ins, outs):
        n = V.V1Node("n")
        n.expression, n.inputs, n.outputs = expr, ins, outs
        return V.convert(n)

    def test_api_object_use_is_flagged(self):
        # MMatrix has no mechanical numpy equivalent, so it is still reported
        # rather than rewritten -- unlike the vector/point holders.
        spec = self._spec("out = MMatrix()", {}, {"out": "matrix"})
        self.assertEqual(spec["api_objects"], ["MMatrix"])
        self.assertTrue(spec["needs_hand_finish"])

    def test_a_rewritten_vector_ctor_is_no_longer_flagged(self):
        # Reporting something the converter already fixed is noise. Bare
        # MVector/MPoint become numpy, so they drop out of api_objects --
        # and with nothing else left, the node stops needing hand-finishing
        # at all. That is what took splineNode to a clean evaluation.
        spec = self._spec("out = MVector(0, 0, 0)", {}, {"out": "vector"})
        self.assertEqual(spec["api_objects"], [])
        self.assertFalse(spec["needs_hand_finish"])
        self.assertEqual(spec["vec_ctor_fixes"], ["MVector"])

    def test_plain_numeric_code_is_not_flagged(self):
        spec = self._spec("out = a * 2", {"a": "float"}, {"out": "float"})
        self.assertEqual(spec["api_objects"], [])
        self.assertFalse(spec["needs_hand_finish"])

    def test_the_report_carries_what_the_user_must_act_on(self):
        spec = self._spec("out = MPoint(a, 0, 0)", {"a": "float"},
                          {"out": "vector"})
        for key in ("shadowed", "globals_in_defs", "synthesized_enums",
                    "api_objects", "needs_hand_finish", "init", "compute"):
            self.assertIn(key, spec, key)


class TestApiTypeFixes(unittest.TestCase):
    """The two v1->v2 type mismatches the converter repairs outright.

    Both were found by evaluating a real converted node rather than by reading
    v1's source, and they hide behind each other: on
    ``quaternionSpineNode.ma`` fixing the first only reveals the second, and
    the node runs clean once both are done. Four edit sites in 52 lines --
    which is why they are worth automating rather than reporting.

    Both rules key off the DECLARED attribute type, never off inferring what
    an expression evaluates to, so neither can fire on something that merely
    looks like a plug read.
    """

    def _conv(self, src, ins, outs):
        return V.split_and_selfify(src, ins, outs)

    # -- class 1: a matrix plug read is a MatrixView, not an MMatrix --------

    def test_a_qualified_matrix_ctor_on_a_plug_is_rewritten(self):
        _i, comp, rep = self._conv("out = om.MTransformationMatrix(m)",
                                   {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m.asTransformationMatrix()", comp)
        self.assertNotIn("MTransformationMatrix(", comp)
        self.assertEqual(len(rep["matrix_view_fixes"]), 1)

    def test_the_bare_ctor_form_is_rewritten_too(self):
        # v1 made MMatrix/MPoint/MVector ambient in the expression namespace,
        # and real v1 nodes use both the bare and the om.-qualified form.
        _i, comp, _r = self._conv("out = MMatrix(m)",
                                  {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m.asMatrix()", comp)

    def test_an_array_element_is_rewritten(self):
        # An element of a matrix ARRAY plug is a MatrixView just as a single
        # matrix plug is -- this is the form the spine example actually used.
        _i, comp, _r = self._conv(
            "out = om.MTransformationMatrix(m[i])",
            {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("self.m[i].asTransformationMatrix()", comp)

    def test_a_non_plug_argument_is_left_alone(self):
        # A helper returning a real MMatrix must keep its constructor.
        _i, comp, rep = self._conv(
            "out = om.MTransformationMatrix(buildMatrix(1))",
            {}, {"out": "matrix"})
        self.assertIn("om.MTransformationMatrix(buildMatrix(1))", comp)
        self.assertEqual(rep["matrix_view_fixes"], [])

    def test_a_plug_of_the_wrong_type_is_left_alone(self):
        _i, comp, rep = self._conv("out = om.MMatrix(f)",
                                   {"f": "float"}, {"out": "matrix"})
        self.assertIn("om.MMatrix(self.f)", comp)
        self.assertEqual(rep["matrix_view_fixes"], [])

    def test_a_multi_argument_ctor_is_left_alone(self):
        _i, comp, _r = self._conv("out = om.MMatrix(m, m)",
                                  {"m": "matrix"}, {"out": "matrix"})
        self.assertIn("om.MMatrix(self.m, self.m)", comp)

    # -- class 2: an MPoint has four components, a vector plug has three ----

    def test_a_computed_write_to_a_vector_plug_is_wrapped(self):
        _i, comp, rep = self._conv("out = curve.getPointAtParam(0)",
                                   {}, {"out": "vector"})
        self.assertIn("_v1_vec3(curve.getPointAtParam(0))", comp)
        self.assertEqual(rep["vec3_fixes"], ["out"])

    def test_arithmetic_is_wrapped_even_with_no_api_call_on_the_line(self):
        # The spine wrote `p0 + t0 * n`, MPoint-valued with nothing on the
        # line to infer that from. This is why the fix is a shim rather than
        # a table of api return types.
        _i, comp, _r = self._conv("out = p0 + t0 * 3",
                                  {}, {"out": "vector"})
        self.assertIn("_v1_vec3(p0 + t0 * 3)", comp)

    def test_a_three_element_display_is_not_wrapped(self):
        # Already the right shape, and by far the common case -- wrapping it
        # would be pure noise.
        _i, comp, rep = self._conv("out = [1, 2, 3]", {}, {"out": "vector"})
        self.assertIn("out = [1, 2, 3]", comp)
        self.assertNotIn("_v1_vec3", comp)
        self.assertEqual(rep["vec3_fixes"], [])

    def test_euler_and_colour_plugs_are_covered(self):
        _i, comp, rep = self._conv("a = f()\nb = g()",
                                   {}, {"a": "euler", "b": "color"})
        self.assertIn("_v1_vec3(f())", comp)
        self.assertIn("_v1_vec3(g())", comp)
        self.assertEqual(rep["vec3_fixes"], ["a", "b"])

    def test_a_non_vector_plug_is_not_wrapped(self):
        _i, comp, rep = self._conv("out = f()", {}, {"out": "float"})
        self.assertNotIn("_v1_vec3", comp)
        self.assertEqual(rep["vec3_fixes"], [])

    def test_an_array_element_write_is_wrapped(self):
        _i, comp, _r = self._conv("out[i] = f()", {}, {"out": "vector"})
        self.assertIn("_v1_vec3(f())", comp)

    # -- the shim ----------------------------------------------------------

    def test_the_shim_lands_in_init_when_needed(self):
        init, _c, _r = self._conv("out = f()", {}, {"out": "vector"})
        self.assertIn("def _v1_vec3(v):", init)

    def test_no_shim_when_nothing_needs_it(self):
        # A node that does not need it gets no mystery function to wonder at.
        init, _c, _r = self._conv("out = [1, 2, 3]", {}, {"out": "vector"})
        self.assertNotIn("_v1_vec3", init)

    def test_the_shim_truncates_four_and_passes_three_through(self):
        init, _c, _r = self._conv("out = f()", {}, {"out": "vector"})
        ns = {}
        exec(compile(init, "<init>", "exec"), ns)
        shim = ns["_v1_vec3"]
        self.assertEqual(shim([1, 2, 3, 1]), [1, 2, 3])
        self.assertEqual(shim([1, 2, 3]), [1, 2, 3])
        self.assertEqual(shim(7.5), 7.5)          # not a sequence at all

    def test_the_pass_is_idempotent(self):
        # convert() may be re-run on the same source; a double wrap would
        # still be correct but would look like a bug.
        _i, comp, _r = self._conv("out = f()", {}, {"out": "vector"})
        _i2, comp2, _r2 = self._conv(comp.replace("self.", ""), {},
                                     {"out": "vector"})
        self.assertEqual(comp2.count("_v1_vec3"), 1)


class TestDeadV1LibraryImports(unittest.TestCase):
    """``from mpylib import MVector`` cannot be satisfied under v2, and must be
    dropped rather than left to fail.

    Four of the nine upstream examples do this. Leaving the import in place is
    far worse than removing it, because Init is ALL-OR-NOTHING: the
    ModuleNotFoundError aborts the whole exec, so every other Init name --
    unrelated imports, helper defs, the ``_v1_vec3`` shim -- disappears with
    it, and Compute then reports whichever of those it reaches first. On
    gameOfLifeNode that surfaced as ``NameError: name '_v1_vec3' is not
    defined``: a trail pointing at the importer's own shim rather than at the
    dead import. After the drop the same scene reports
    ``NameError: name 'MVector' is not defined``, which is the truth.
    """

    def test_the_import_is_dropped_and_reported(self):
        init, _c, rep = V.split_and_selfify(
            "from mpylib import MVector\nout = MVector(1, 2, 3)[0]",
            {}, {"out": "float"})
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["from mpylib import MVector"])

    def test_a_plain_import_is_dropped(self):
        init, _c, rep = V.split_and_selfify(
            "import mpylib\nout = 1.0", {}, {"out": "float"})
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["import mpylib"])

    def test_a_submodule_import_is_dropped(self):
        _i, _c, rep = V.split_and_selfify(
            "from mpylib.api import openmaya\nout = 1.0",
            {}, {"out": "float"})
        self.assertEqual(rep["dead_imports"],
                         ["from mpylib.api import openmaya"])

    def test_an_unrelated_import_on_the_same_line_survives(self):
        # Collateral damage would be worse than the original problem.
        init, _c, rep = V.split_and_selfify(
            "import mpylib, math\nout = math.pi", {}, {"out": "float"})
        self.assertIn("import math", init)
        self.assertNotIn("mpylib", init)
        self.assertEqual(rep["dead_imports"], ["import mpylib"])

    def test_other_imports_are_untouched(self):
        init, _c, rep = V.split_and_selfify(
            "import random\nfrom bisect import bisect_left as bl\nout = 1.0",
            {}, {"out": "float"})
        self.assertIn("import random", init)
        self.assertIn("bisect_left as bl", init)
        self.assertEqual(rep["dead_imports"], [])

    def test_the_rest_of_init_still_executes(self):
        # The whole point. Before the drop this Init raised
        # ModuleNotFoundError and neither `helper` nor the shim existed.
        init, _c, _r = V.split_and_selfify(
            "from mpylib import MVector\nimport math\n"
            "def helper(x):\n    return x * 2\n\nout = helper(1)",
            {}, {"out": "vector"})
        ns = {}
        exec(compile(init, "<init>", "exec"), ns)
        self.assertEqual(ns["helper"](3), 6)
        self.assertIn("math", ns)
        self.assertIn("_v1_vec3", ns)

    def test_a_nested_import_is_reported_but_left_alone(self):
        # It fails when the function is CALLED, not during Init, so it does
        # not poison the namespace -- and removing it could leave an empty
        # function body. Reporting is enough.
        init, _c, rep = V.split_and_selfify(
            "def f():\n    from mpylib import MVector\n    return MVector()\n"
            "\nout = 1.0", {}, {"out": "float"})
        self.assertIn("from mpylib import MVector", init)
        self.assertEqual(rep["dead_imports"], ["mpylib"])


class TestBareVectorConstructors(unittest.TestCase):
    """v1's ambient ``MVector`` / ``MPoint``, rewritten to numpy.

    v2 does not seed api objects into the expression namespace -- an explicit
    design decision -- so a bare ``MVector(0, 0, 0)`` is simply undefined, and
    dropping the dead ``from mpylib import MVector`` (see above) exposes that
    rather than hiding it.

    Every bare call in the nine upstream examples takes scalar arguments:
    ``MVector(0, 0, 0)``, ``MVector(1, 1, 1)``, ``MVector(p[0], p[1], 0)``,
    ``MPoint(0, 0, 0, 1)``, ``MPoint(x, 0, z, 1)``. They are plain 3- and
    4-component holders, so a numpy array does the same arithmetic -- and
    numpy is what the rest of v2 hands you anyway. The shim is a visible,
    deletable function in Init, NOT a re-export of MVector.
    """

    def _conv(self, src, ins=None, outs=None):
        return V.split_and_selfify(src, ins or {}, outs or {"out": "float"})

    def test_a_bare_mvector_becomes_the_shim(self):
        _i, comp, rep = self._conv("v = MVector(0, 0, 0)\nout = v[0]")
        self.assertIn("_v1_vec(0, 0, 0)", comp)
        self.assertNotIn("MVector", comp)
        self.assertEqual(rep["vec_ctor_fixes"], ["MVector"])

    def test_a_bare_mpoint_becomes_the_shim(self):
        _i, comp, rep = self._conv("p = MPoint(x, 0, z, 1)\nout = p[0]")
        self.assertIn("_v1_vec(x, 0, z, 1)", comp)
        self.assertEqual(rep["vec_ctor_fixes"], ["MPoint"])

    def test_the_qualified_form_is_left_alone(self):
        # om.MVector is a real api2 call that works fine under v2.
        _i, comp, rep = self._conv("v = om.MVector(0, 0, 0)\nout = v[0]")
        self.assertIn("om.MVector(0, 0, 0)", comp)
        self.assertNotIn("_v1_vec(", comp)
        self.assertEqual(rep["vec_ctor_fixes"], [])

    def test_a_bare_matrix_ctor_is_not_swept_up(self):
        # Only the vector/point holders are mechanically replaceable. MMatrix
        # keeps its own reporting path rather than being guessed at.
        _i, comp, rep = self._conv("m = MMatrix()\nout = 1.0")
        self.assertIn("MMatrix()", comp)
        self.assertEqual(rep["vec_ctor_fixes"], [])

    def test_no_redundant_vec3_wrap_on_top_of_the_shim(self):
        # The shim already yields exactly three components; wrapping it in
        # _v1_vec3 as well would be pure noise.
        _i, comp, _r = self._conv("out = MVector(0, 0, 0)", {},
                                  {"out": "vector"})
        self.assertIn("self.out = _v1_vec(0, 0, 0)", comp)
        self.assertNotIn("_v1_vec3", comp)

    def test_the_shim_import_lands_in_init_only_when_needed(self):
        # One import line, not ~90 lines of injected class source: the type
        # lives in a real module so stored vectors can be pickled.
        init, _c, _r = self._conv("out = MVector(1, 2, 3)[0]")
        self.assertIn("v1_compat import v1_vec as _v1_vec", init)
        init2, _c2, _r2 = self._conv("out = 1.0")
        self.assertNotIn("_v1_vec", init2)

    def test_the_shim_semantics(self):
        from mpynode._common.io.v1_compat import v1_vec as vec
        self.assertEqual(list(vec(1, 2, 3)), [1.0, 2.0, 3.0])
        # MPoint's w is dropped -- it was never written to a 3-slot plug.
        self.assertEqual(list(vec(1, 2, 3, 1)), [1.0, 2.0, 3.0])
        # Single-sequence form, and short input padded with zeros.
        self.assertEqual(list(vec([4, 5, 6])), [4.0, 5.0, 6.0])
        self.assertEqual(list(vec()), [0.0, 0.0, 0.0])
        self.assertEqual(list(vec(7)), [7.0, 0.0, 0.0])

    def test_the_shim_result_supports_scalar_arithmetic(self):
        # The actual reason it is numpy and not a list: splineNode does
        # `self.samples[i] += self.cv[k] * w`, and `list * float` raises
        # TypeError -- which is how springChainNode still fails.
        from mpynode._common.io.v1_compat import v1_vec
        self.assertEqual(list(v1_vec(1, 2, 3) * 2.0), [2.0, 4.0, 6.0])


class TestUnitWrappedPlugReads(unittest.TestCase):
    """``self.<time/angle plug>.value`` -> the plug read itself.

    v1 set ``DEFAULT_ANGLE = MAngle`` and ``DEFAULT_TIME = MTime``, so those
    plugs came back wrapped and the number was ``.value``. v2 hands the number
    directly, and the resulting ``AttributeError: 'float' object has no
    attribute 'value'`` is completely opaque until you know that. It cost two
    scenes: gameOfLifeNode on a time plug, ouchNode on an angle plug.
    """

    def test_a_time_plug_loses_the_value_hop(self):
        _i, comp, rep = V.split_and_selfify(
            "out = frame.value * 2", {"frame": "time"}, {"out": "float"})
        self.assertIn("self.frame * 2", comp)
        self.assertEqual(rep["time_fixes"], ["frame"])

    def test_an_angle_plug_loses_it_too(self):
        _i, comp, rep = V.split_and_selfify(
            "out = angle.value", {"angle": "angle"}, {"out": "float"})
        self.assertIn("self.angle", comp)
        self.assertNotIn(".value", comp)
        self.assertEqual(rep["time_fixes"], ["angle"])

    def test_an_unrelated_dot_value_is_left_alone(self):
        # Only the declared unit-wrapped plug types, never any `.value`.
        _i, comp, rep = V.split_and_selfify(
            "out = thing.value", {}, {"out": "float"})
        self.assertIn("thing.value", comp)
        self.assertEqual(rep["time_fixes"], [])

    def test_a_float_plug_keeps_its_value_attribute(self):
        _i, comp, rep = V.split_and_selfify(
            "out = f.value", {"f": "float"}, {"out": "float"})
        self.assertIn("self.f.value", comp)
        self.assertEqual(rep["time_fixes"], [])


class TestEvalOfAPlugName(unittest.TestCase):
    """``eval('boardX')`` -- v1 introspection with a plug name inside a STRING.

    gameOfLifeNode really contains
    ``test0 = getattr(self, 'boardX') == eval('boardX')``. Under v1 the bare
    name resolved because plugs were locals in the exec namespace; an AST pass
    cannot see into a string literal, so this needs its own rule.
    """

    def test_the_string_is_rewritten(self):
        _i, comp, rep = V.split_and_selfify(
            "out = eval('n')", {"n": "int"}, {"out": "float"})
        self.assertIn("eval('self.n')", comp)
        self.assertEqual(rep["eval_fixes"], ["n"])

    def test_a_non_plug_string_is_untouched(self):
        # `self.` would be wrong here, so it is left to fail visibly.
        _i, comp, rep = V.split_and_selfify(
            "out = eval('1 + 1')", {}, {"out": "float"})
        self.assertIn("eval('1 + 1')", comp)
        self.assertEqual(rep["eval_fixes"], [])

    def test_a_dynamic_argument_is_untouched(self):
        _i, comp, rep = V.split_and_selfify(
            "out = eval(name)", {"n": "int"}, {"out": "float"})
        self.assertIn("eval(name)", comp)
        self.assertEqual(rep["eval_fixes"], [])


class TestInitHelpersAreRewrittenToo(unittest.TestCase):
    """A top-level def is partitioned into Init BEFORE any rewriting, so for a
    while a helper that built its own ``MVector`` kept a name that does not
    exist under v2. springChainNode's ``spring()`` does exactly that, twice."""

    def test_a_bare_ctor_inside_an_init_def_is_rewritten(self):
        init, _c, rep = V.split_and_selfify(
            "def helper():\n    return MVector(0, 0, 0)\n\nout = helper()[0]",
            {}, {"out": "float"})
        self.assertIn("_v1_vec(0, 0, 0)", init)
        self.assertNotIn("MVector", init)
        self.assertEqual(rep["vec_ctor_fixes"], ["MVector"])

    def test_the_shim_import_is_present_for_an_init_only_fix(self):
        init, _c, _r = V.split_and_selfify(
            "def helper():\n    return MVector(0, 0, 0)\n\nout = helper()[0]",
            {}, {"out": "float"})
        self.assertIn("v1_compat import v1_vec as _v1_vec", init)


class TestThirdPartyImportsAreReported(unittest.TestCase):
    """pyaudio is not dropped the way mpylib is -- unlike v1's own library it
    can legitimately be installed -- but it is reported, with the v2 route
    named, because otherwise the failure is a bare ModuleNotFoundError."""

    def test_pyaudio_is_reported_and_kept(self):
        init, _c, rep = V.split_and_selfify(
            "import pyaudio\nout = 1.0", {}, {"out": "float"})
        self.assertIn("import pyaudio", init)
        self.assertEqual(rep["third_party_imports"], ["pyaudio"])

    def test_the_report_names_the_v2_route(self):
        self.assertIn("play_pcm", V._V1_THIRD_PARTY["pyaudio"])

    def test_an_ordinary_import_is_not_reported(self):
        _i, _c, rep = V.split_and_selfify(
            "import math\nout = math.pi", {}, {"out": "float"})
        self.assertEqual(rep["third_party_imports"], [])


class TestV1CompatModule(unittest.TestCase):
    """``_common/io/v1_compat.py`` -- the runtime half of the conversion.

    A real module rather than injected Init source for one concrete reason:
    stored variables are PICKLED, and v1 nodes keep buffers of vectors
    (springChain velocity/position, unitSphereCollision a point grid). A class
    defined by exec-ing Init source has no importable path, so its instances
    cannot round-trip -- which is why those two scenes failed from their SAVED
    data rather than from anything in their expressions.
    """

    def setUp(self):
        from mpynode._common.io import v1_compat
        self.C = v1_compat

    def test_it_is_a_numpy_subclass_so_numpy_still_works(self):
        import numpy
        v = self.C.v1_vec(1, 2, 3)
        self.assertIsInstance(v, numpy.ndarray)
        self.assertEqual(list(v + self.C.v1_vec(1, 1, 1)), [2.0, 3.0, 4.0])
        self.assertEqual(list(2.0 * v), [2.0, 4.0, 6.0])
        self.assertEqual(list(v * self.C.v1_vec(2, 2, 2)), [2.0, 4.0, 6.0])

    def test_length_and_the_two_normalise_variants(self):
        v = self.C.v1_vec(3, 4, 0)
        self.assertEqual(v.length(), 5.0)
        # normal() copies; normalize() mutates in place and returns self,
        # which is what springChainNode relies on.
        self.assertEqual(list(v.normal()), [0.6, 0.8, 0.0])
        self.assertEqual(list(v), [3.0, 4.0, 0.0])
        self.assertEqual(list(v.normalize()), [0.6, 0.8, 0.0])
        self.assertEqual(list(v), [0.6, 0.8, 0.0])

    def test_a_zero_vector_normalises_without_dividing_by_zero(self):
        z = self.C.v1_vec(0, 0, 0)
        self.assertEqual(list(z.normalize()), [0.0, 0.0, 0.0])
        self.assertEqual(list(z.normal()), [0.0, 0.0, 0.0])

    def test_distance_and_cross(self):
        self.assertEqual(self.C.v1_vec(0, 0, 0).distanceTo(
            self.C.v1_vec(1, 2, 2)), 3.0)
        self.assertEqual(
            list(self.C.v1_vec(1, 0, 0) ^ self.C.v1_vec(0, 1, 0)),
            [0.0, 0.0, 1.0])

    def test_point_times_matrix_is_a_homogeneous_transform(self):
        translate = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5, 6, 7, 1]
        self.assertEqual(list(self.C.v1_vec(1, 2, 3) * translate),
                         [6.0, 8.0, 10.0])

    def test_a_four_component_point_drops_w(self):
        self.assertEqual(list(self.C.v1_vec(1, 2, 3, 1)), [1.0, 2.0, 3.0])

    def test_no_args_and_short_input(self):
        self.assertEqual(list(self.C.v1_vec()), [0.0, 0.0, 0.0])
        self.assertEqual(list(self.C.v1_vec(7)), [7.0, 0.0, 0.0])

    def test_matrix_rows_accepts_a_matrixview_and_refuses_other_things(self):
        class FakeView:
            def asMatrix(self):
                return list(range(16))
        self.assertEqual(self.C.matrix_rows(FakeView())[0],
                         [0.0, 1.0, 2.0, 3.0])
        self.assertIsNone(self.C.matrix_rows([1, 2, 3]))
        self.assertIsNone(self.C.matrix_rows("nope"))
        self.assertIsNone(self.C.matrix_rows(4.0))

    def test_stored_vars_are_coerced_recursively(self):
        got = self.C.coerce_stored(
            {"buf": [[1, 2, 3], [4, 5, 6, 1]], "n": 7, "s": "x"})
        self.assertEqual(list(got["buf"][0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(got["buf"][1]), [4.0, 5.0, 6.0])
        self.assertTrue(hasattr(got["buf"][0], "distanceTo"))
        self.assertEqual(got["n"], 7)
        self.assertEqual(got["s"], "x")

    def test_coercion_leaves_non_vector_lists_alone(self):
        for value in ([1, 2], [1, 2, 3, 4, 5], ["a", "b", "c"],
                      [True, False, True]):
            self.assertEqual(self.C.coerce_stored(value), value)

    def test_a_coerced_vector_survives_a_pickle_round_trip(self):
        # The whole reason this is a module. Without it springChainNode and
        # unitSphereCollisionNode compute against plain lists from their
        # saved buffers and raise on the first multiply.
        import pickle
        v = self.C.coerce_stored([1, 2, 3])
        back = pickle.loads(pickle.dumps(v))
        self.assertEqual(list(back), [1.0, 2.0, 3.0])
        self.assertEqual(back.length(), self.C.v1_vec(1, 2, 3).length())

    def test_raw_float32_pcm_gets_a_valid_wav_container(self):
        # v1 pushed these bytes straight at PyAudio with format=32
        # (paFloat32). Qt plays files, so they need a header -- and `wave`
        # cannot write IEEE float, so they become 16-bit signed.
        import array
        import io as _io
        import math
        import wave
        n = 512
        pcm = array.array(
            "f", (0.5 * math.sin(2 * math.pi * 440 * i / 22050)
                  for i in range(n))).tobytes()
        wav = self.C.wav_from_float32(pcm, 22050)
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(wav[8:12], b"WAVE")
        handle = wave.open(_io.BytesIO(wav))
        self.assertEqual(handle.getnchannels(), 1)
        self.assertEqual(handle.getsampwidth(), 2)
        self.assertEqual(handle.getframerate(), 22050)
        self.assertEqual(handle.getnframes(), n)

    def test_out_of_range_samples_are_clamped_not_wrapped(self):
        # v1 fed these to the sound card directly, so nothing guarantees they
        # sit inside [-1, 1]; overflowing int16 turns a loud clip into noise.
        import array
        import io as _io
        import wave
        pcm = array.array("f", [2.0, -2.0, 0.0]).tobytes()
        handle = wave.open(_io.BytesIO(self.C.wav_from_float32(pcm, 8000)))
        frames = array.array("h")
        frames.frombytes(handle.readframes(3))
        self.assertEqual(list(frames), [32767, -32767, 0])

    def test_play_pcm_degrades_instead_of_raising(self):
        # No QtMultimedia, no audio device, junk bytes -- a node that cannot
        # make a noise must still compute its outputs.
        self.assertIsNone(self.C.play_pcm(b"", 0))
        self.assertIsNone(self.C.play_pcm(None, 22050))
