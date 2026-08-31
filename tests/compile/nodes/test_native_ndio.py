"""nd_io -- array file IO that survives compilation.

Three layers are covered, because a break in any one of them is silent:

  1. the PYTHON half (mpynode.ndio) -- format sniffing, degrade-to-empty, cache
  2. the TRANSPILER -- which spellings lower, and which must REJECT
  3. the CODEGEN WIRING -- kernel/members/includes emitted iff the source uses IO

The degrade-to-empty rule gets its own tests in layers 1 and 2 because it is the
contract that keeps interpreted and compiled agreeing on a MISSING file. If one
half raised and the other returned empty, parity would hold on the happy path
and diverge exactly when something went wrong.
"""

from __future__ import annotations

import os
import struct
import tempfile
import unittest

import numpy as np

from tests import _setup


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="ndio_test_")

    def path(self, name):
        return os.path.join(self._dir, name)


# ---------------------------------------------------------------------------
# 1. the Python half
# ---------------------------------------------------------------------------
class TestNdioPython(_Tmp):

    def test_ndio_container_round_trips_many_named_arrays(self):
        from mpynode import ndio

        p = self.path("bundle.ndio")
        pts = np.arange(24, dtype=np.float64).reshape(4, 2, 3)
        cnt = np.array([4, 4, 3], dtype=np.int64)
        self.assertTrue(ndio.write(p, points=pts, counts=cnt))
        self.assertEqual(ndio.keys(p), ["counts", "points"])
        got = ndio.read(p, "points")
        self.assertEqual(got.shape, (4, 2, 3))
        self.assertTrue(np.array_equal(got, pts))
        self.assertTrue(np.array_equal(ndio.read(p, "counts", dtype=np.int64),
                                       cnt))

    def test_npy_is_sniffed_and_read_as_the_sole_array(self):
        from mpynode import ndio

        p = self.path("a.npy")
        a = np.linspace(0.0, 1.0, 12).reshape(4, 3)
        np.save(p, a)
        self.assertTrue(np.array_equal(ndio.read(p), a))

    def test_json_object_of_number_arrays_is_read(self):
        from mpynode import ndio

        p = self.path("m.json")
        with open(p, "w") as fh:
            fh.write('{"points": [[0,0,0],[1,2,3]], "counts": [3, 3]}')
        self.assertEqual(ndio.read(p, "points").shape, (2, 3))
        self.assertTrue(np.array_equal(ndio.read(p, "counts", dtype=np.int64),
                                       np.array([3, 3])))

    def test_raw_needs_an_explicit_dtype(self):
        from mpynode import ndio

        p = self.path("b.raw")
        a = np.arange(6, dtype=np.float64)
        self.assertTrue(ndio.write_raw(p, a))
        self.assertTrue(np.array_equal(ndio.read_raw(p, np.float64), a))

    def test_missing_malformed_and_absent_key_all_degrade_to_empty(self):
        # THE parity contract: never raise, always a well-formed empty array.
        from mpynode import ndio

        garbage = self.path("garbage.bin")
        with open(garbage, "wb") as fh:
            fh.write(b"\x00\x01not a format at all\xff")
        good = self.path("g.ndio")
        ndio.write(good, points=np.zeros((2, 3)))

        for path, key in ((self.path("nope.ndio"), "points"),
                          (garbage, "points"),
                          ("", "points"),
                          (good, "no_such_key")):
            arr = ndio.read(path, key)
            self.assertEqual(arr.size, 0, "%r/%r should be empty" % (path, key))
            self.assertIsInstance(arr, np.ndarray)

    def test_a_rewrite_under_the_same_name_is_picked_up(self):
        # The cache keys on path+mtime+size; a same-name rewrite must NOT be
        # served stale. Nanosecond mtime is what makes this hold for a fast
        # same-size rewrite.
        from mpynode import ndio

        p = self.path("c.ndio")
        ndio.write(p, points=np.ones((2, 3)))
        first = ndio.read(p, "points").copy()
        ndio.write(p, points=np.full((2, 3), 7.0))
        second = ndio.read(p, "points")
        self.assertTrue(np.array_equal(first, np.ones((2, 3))))
        self.assertTrue(np.array_equal(second, np.full((2, 3), 7.0)))

    def test_repeat_reads_do_not_re_parse(self):
        from mpynode import ndio

        p = self.path("d.ndio")
        ndio.write(p, points=np.zeros((3, 3)))
        ndio.read(p, "points")
        calls = []
        real = ndio._slurp

        def counting(path):
            calls.append(path)
            return real(path)

        ndio._slurp = counting
        try:
            for _ in range(5):
                ndio.read(p, "points")
        finally:
            ndio._slurp = real
        self.assertEqual(calls, [], "a warm cache must not touch the disk")

    def test_frame_path_substitutes_the_first_hash_run(self):
        # The C++ twin (nd_io_frame_path) must agree EXACTLY. A divergence here
        # would not be a slightly different number -- it would have the compiled
        # node open a DIFFERENT FILE than the interpreted one.
        from mpynode import ndio

        self.assertEqual(ndio.frame_path("mesh.####.json", 7), "mesh.0007.json")
        self.assertEqual(ndio.frame_path("mesh.#.json", 7), "mesh.7.json")
        self.assertEqual(ndio.frame_path("mesh.########.json", 7),
                         "mesh.00000007.json")
        # The FIRST run only; a second run is left alone.
        self.assertEqual(ndio.frame_path("a####b####c", 7), "a0007b####c")

    def test_frame_path_edges_match_the_cpp_padding_rule(self):
        from mpynode import ndio

        # No '#' -> unchanged, so a plain filename still works as a template.
        self.assertEqual(ndio.frame_path("mesh.json", 7), "mesh.json")
        self.assertEqual(ndio.frame_path("", 7), "")
        self.assertEqual(ndio.frame_path(None, 7), "")
        # `frame` arrives from a time/double plug: truncate toward zero, and
        # keep the sign inside the pad width (snprintf "%0*lld" does the same).
        self.assertEqual(ndio.frame_path("f.####.x", 7.9), "f.0007.x")
        self.assertEqual(ndio.frame_path("f.####.x", -7), "f.-007.x")
        self.assertEqual(ndio.frame_path("f.####.x", -7.9), "f.-007.x")
        # Wider than the pad -> NOT truncated. Silently dropping digits would
        # read the wrong frame instead of failing.
        self.assertEqual(ndio.frame_path("f.##.x", 12345), "f.12345.x")

    def test_frame_path_cpp_twin_uses_the_same_formatting_primitive(self):
        # A cross-implementation differential lives outside this suite (it needs
        # a compiler); pin the primitive so an edit to one half that changes the
        # padding rule is visible here.
        from mpynode.native.compiler.kernels import nd_io_cpp as k

        self.assertIn("static std::string nd_io_frame_path(", k.NDIO_CPP)
        self.assertIn('"%0*lld"', k.NDIO_CPP)
        self.assertIn("(long long)frame", k.NDIO_CPP)

    def test_container_layout_is_what_the_cpp_kernel_expects(self):
        # The C++ half parses these bytes by hand; pin the header so a change
        # to one implementation cannot silently desync the other.
        from mpynode import ndio

        p = self.path("layout.ndio")
        ndio.write(p, points=np.zeros((2, 3), dtype=np.float64))
        raw = open(p, "rb").read()
        self.assertEqual(raw[:5], b"NDIO\x01")
        self.assertEqual(struct.unpack_from("<I", raw, 5)[0], 1)
        namelen = struct.unpack_from("<H", raw, 9)[0]
        self.assertEqual(raw[11:11 + namelen], b"points")


# ---------------------------------------------------------------------------
# 2. the transpiler
# ---------------------------------------------------------------------------
class TestNdioLowering(unittest.TestCase):
    """Reject-or-lower. A spelling either produces the right C++ or raises --
    never a plausible-looking call to something that does not exist."""

    def _lower(self, body):
        from mpynode.native.compiler.py_to_cpp import (transpile_function,
                                                       str_t, scalar_t)
        src = "def f(path, t):\n" + "".join(
            "    %s\n" % ln for ln in body.strip().splitlines())
        r = transpile_function(src, {"path": str_t(), "t": scalar_t("double")})
        return "\n".join(list(r.decl_lines) + list(r.body_lines))

    def _rejects(self, body, needle=None):
        from mpynode.native.compiler.errors import UnsupportedSpec
        with self.assertRaises(UnsupportedSpec) as cm:
            self._lower(body)
        if needle:
            self.assertIn(needle, str(cm.exception))

    # -- reads --------------------------------------------------------------
    def test_ndio_read_named_lowers_to_the_cached_reader(self):
        cpp = self._lower("pts = ndio.read(path, 'points')\nreturn pts")
        self.assertIn("nd_io_read_named<double>(_ndioCache, _ndioMutex, path, "
                      'std::string("points"))', cpp)

    def test_dtype_keyword_selects_the_element_type(self):
        cpp = self._lower("a = ndio.read(path, 'i', dtype=np.int64)\nreturn a")
        self.assertIn("nd_io_read_named<int64_t>", cpp)

    def test_read_without_a_name_asks_for_the_sole_array(self):
        cpp = self._lower("pts = ndio.read(path)\nreturn pts")
        self.assertIn('std::string("")', cpp)

    def test_read_raw_and_fromfile_agree(self):
        a = self._lower("b = ndio.read_raw(path, dtype=np.float64)\nreturn b")
        b = self._lower("b = np.fromfile(path, dtype=np.float64)\nreturn b")
        self.assertIn("nd_io_read_raw<double>(_ndioCache, _ndioMutex, path, "
                      "'f', 8)", a)
        self.assertEqual(a, b)

    def test_raw_descriptor_matches_numpys_actual_byte_layout(self):
        # THE regression: the descriptor used to be keyed on the PROMOTED dtype,
        # so every float spelling emitted ('f', 8) and every int spelling
        # ('i', 8). np.fromfile(p, dtype=np.float32) then walked a 4-byte file
        # in 8-byte strides -- an 8-element float32 file read back as 4 elements
        # of garbage (2 512 8192 131072). The emitted pair describes the FILE,
        # so it must equal whatever numpy actually wrote.
        for spelling, dt in (("np.float64", np.float64),
                             ("np.float32", np.float32),
                             ("np.int64", np.int64), ("np.int32", np.int32),
                             ("np.int16", np.int16), ("np.int8", np.int8),
                             ("np.uint8", np.uint8), ("np.uint16", np.uint16),
                             ("np.uint32", np.uint32)):
            cpp = self._lower("b = np.fromfile(path, dtype=%s)\nreturn b"
                              % spelling)
            want = np.dtype(dt)
            self.assertIn("'%s', %d)" % (want.kind, want.itemsize), cpp,
                          "%s emitted the wrong raw byte layout" % spelling)

    def test_raw_bool_is_one_byte_per_element(self):
        # np.bool_.itemsize is 1, so a bool file is one byte per element; the
        # old descriptor said 8. The kind letter is 'i' rather than numpy's 'b'
        # because nd_io_elem_f treats any non-'f'/'u' kind as a signed integer
        # of the given size, which reads a 0/1 byte correctly.
        self.assertEqual(np.dtype(bool).itemsize, 1)
        cpp = self._lower("b = np.fromfile(path, dtype=np.bool_)\nreturn b")
        self.assertIn("'i', 1)", cpp)

    def test_string_dtype_spelling_lowers_like_the_dotted_one(self):
        # ndio.py:28 advertises dtype="int32" in its own docstring, but _canon
        # returns None for a string constant -- it is not a dotted name -- so a
        # designer following the docs used to fall silently off the
        # deterministic path onto the AI porter.
        a = self._lower('b = np.fromfile(path, dtype="int32")\nreturn b')
        b = self._lower("b = np.fromfile(path, dtype=np.int32)\nreturn b")
        self.assertEqual(a, b)
        self.assertIn("'i', 4)", a)

    def test_a_read_composes_with_ordinary_array_math(self):
        cpp = self._lower("pts = ndio.read(path, 'p')\nreturn pts * 2.0")
        self.assertIn("nd_io_read_named", cpp)
        self.assertIn("nd::mul", cpp)

    def test_a_runtime_index_slices_one_frame_out_of_a_stack(self):
        cpp = self._lower("f = ndio.read(path, 'p')\n"
                          "i = int(t) % f.shape[0]\n"
                          "return f[i]")
        self.assertIn("nd::slice(", cpp)

    # -- frame -> filename ----------------------------------------------------
    def test_frame_path_lowers_and_feeds_a_read(self):
        # A file-per-frame sequence needs the frame formatted INTO the path, and
        # str() / % / f-strings are all outside the lowerable surface -- so this
        # one substitution lives in the kernel next to the reader.
        cpp = self._lower("p = ndio.frame_path(path, t)\n"
                          "return ndio.read(p, 'points')")
        self.assertIn("nd_io_frame_path(path, (double)(t))", cpp)
        self.assertIn("nd_io_read_named<double>(_ndioCache, _ndioMutex, p, "
                      'std::string("points"))', cpp)

    def test_frame_path_rejects_a_bad_template_or_frame(self):
        base = "p = ndio.frame_path(%s)\nreturn ndio.read(p, 'x')"
        self._rejects(base % "3.0, t", "must be a string")
        self._rejects(base % "path, path", "must be a number")
        self._rejects(base % "path")
        self._rejects(base % "path, t, t", "ndio.frame_path(template, frame)")

    # -- writes -------------------------------------------------------------
    def test_ndio_write_emits_one_writer_per_named_array(self):
        cpp = self._lower("a = np.zeros((2, 3))\n"
                          "ndio.write(path, points=a, counts=a)\n"
                          "return a")
        self.assertIn("NdIoWriter", cpp)
        self.assertIn('nd_io_writer_add(ndio_w_2, std::string("points")', cpp)
        self.assertIn('nd_io_writer_add(ndio_w_2, std::string("counts")', cpp)
        self.assertIn("nd_io_writer_finish", cpp)

    def test_np_save_replicates_numpys_npy_suffix_rule(self):
        # np.save("/tmp/x", a) writes /tmp/x.npy. If the compiled node wrote
        # /tmp/x instead, a downstream reader would find nothing.
        cpp = self._lower("a = np.zeros((2, 3))\n"
                          "np.save(path, a)\nreturn a")
        self.assertIn("nd_io_write_npy(nd_io_npy_path(path)", cpp)

    def test_tofile_writes_the_path_verbatim(self):
        cpp = self._lower("a = np.zeros((2, 3))\n"
                          "a.tofile(path)\nreturn a")
        self.assertIn("nd_io_write_raw(path", cpp)
        self.assertNotIn("nd_io_npy_path", cpp)

    def test_a_bare_write_statement_is_actually_emitted(self):
        # A bare call statement is normally rejected; a write must survive as a
        # statement or the file would never be written.
        cpp = self._lower("a = np.zeros((2, 3))\n"
                          "a.tofile(path)\nreturn a")
        self.assertIn("(void)(nd_io_write_raw(path", cpp)

    # -- rejects ------------------------------------------------------------
    def test_np_load_is_rejected_because_it_names_no_dtype(self):
        self._rejects("return np.load(path)")

    def test_a_raw_read_without_a_dtype_is_rejected(self):
        self._rejects("return ndio.read_raw(path)", "explicit dtype")
        self._rejects("return np.fromfile(path)", "explicit dtype")

    def test_ndio_keys_is_rejected_as_a_list(self):
        self._rejects("return ndio.keys(path)", "list")

    def test_a_non_string_path_is_rejected(self):
        self._rejects("return ndio.read(3.0, 'x')", "must be a string")

    def test_write_needs_arrays_and_they_must_be_arrays(self):
        self._rejects("ndio.write(path)\nreturn np.zeros(1)",
                      "no arrays")
        self._rejects("ndio.write(path, a=1.0)\nreturn np.zeros(1)",
                      "not an array")

    def test_unlowered_fromfile_options_are_rejected_not_ignored(self):
        # Silently dropping count= would read the WHOLE file instead of 3
        # elements -- a wrong answer, not a missing feature.
        for kw in ("count=3", "sep=','", "offset=8"):
            self._rejects("return np.fromfile(path, dtype=np.float64, %s)" % kw)


# ---------------------------------------------------------------------------
# 3. codegen wiring
# ---------------------------------------------------------------------------
class TestNdioCodegenWiring(unittest.TestCase):

    def test_detector_matches_every_lowered_spelling(self):
        from mpynode.native.compiler.kernels import nd_io_cpp as k

        for src in ("pts = ndio.read(self.p, 'x')",
                    "a = ndio.read_raw(self.p, dtype=np.float64)",
                    "ndio.write(self.p, points=a)",
                    "ndio.write_raw(self.p, a)",
                    "b = np.fromfile(self.p, dtype=np.float64)",
                    "np.save(self.p, a)",
                    "a.tofile(self.p)",
                    "q = ndio.frame_path(self.p, self.frame)"):
            self.assertTrue(k.spec_uses_ndio({"compute": src, "init": ""}),
                            "missed %r -- a miss is a link error" % src)

    def test_detector_ignores_ordinary_computes(self):
        from mpynode.native.compiler.kernels import nd_io_cpp as k

        for src in ("out = np.zeros((4, 3)) * 2.0",
                    "v = self.load_cache()",
                    "out = np.dot(a, b)"):
            self.assertFalse(k.spec_uses_ndio({"compute": src, "init": ""}), src)

    def test_reject_unlowered_io_fires_only_when_io_did_not_lower(self):
        from mpynode.native.compiler.kernels import nd_io_cpp as k
        from mpynode.native.compiler.errors import UnsupportedSpec

        io_spec = {"compute": "pts = ndio.read(self.p, 'x')", "init": ""}
        plain = {"compute": "out = 1.0", "init": ""}
        # lowered -> fine; no IO -> fine; IO + not lowered -> refuse
        k.reject_unlowered_io(io_spec, ["some c++"], "node")
        k.reject_unlowered_io(plain, None, "node")
        with self.assertRaises(UnsupportedSpec) as cm:
            k.reject_unlowered_io(io_spec, None, "node")
        self.assertIn("did not lower", str(cm.exception))

    def test_kernel_and_members_are_emitted_only_for_an_io_node(self):
        # A non-IO node's translation unit must be byte-identical to before,
        # which is what keeps the port cache valid.
        from mpynode.native.compiler.kernels import nd_io_cpp as k

        self.assertIn("_ndioCache", k.NDIO_MEMBERS)
        self.assertIn("_ndioMutex", k.NDIO_MEMBERS)
        self.assertIn("ND_IO_KERNEL_INCLUDED", k.NDIO_CPP)
        for h in ("mutex", "fstream", "sys/stat.h"):
            self.assertIn(h, k.NDIO_INCLUDES)


if __name__ == "__main__":
    unittest.main()
