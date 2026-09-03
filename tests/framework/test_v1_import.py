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
        spec = self._spec("out = MVector(0, 0, 0)", {}, {"out": "vector"})
        self.assertEqual(spec["api_objects"], ["MVector"])
        self.assertTrue(spec["needs_hand_finish"])

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
