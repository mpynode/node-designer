"""Real-clang parity for the native `hex` attr transcode.

A `hex` attr stores a space-separated lowercase UTF-8 hex byte string but the
expression sees/produces plain text. codegen emits a C++ transcode core
(`codegen._HEX_CORE_CPP`, Maya-free std::string functions) that MUST match the
interpreter codec in mpynode/_api2/helpers.py byte-for-byte, so a node runs
identically whether interpreted or compiled.

This test compiles that core with real clang++ (no Maya) and diffs its output
against the Python codec across ASCII / multibyte-UTF-8 / emoji / empty /
whitespace / malformed / round-trip vectors. It is the native-change norm for
this codebase (mirrors test_file_texture_parity.py). Skips when clang++ is
absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests import _paths

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = _paths.ROOT
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


# --- Python reference codec (mirrors _api2/helpers.py hex branches) ----------
# encode: helpers.py _write_value_to_handle hex branch
# decode: helpers.py get_attr hex branch --
#         bytes.fromhex(raw.replace(" ","")).decode("utf-8","replace"). The C++
#         core returns the re-encoded UTF-8 bytes of that DECODED TEXT, so the
#         reference is text.encode("utf-8").hex(). Ill-formed UTF-8 must match
#         CPython's "replace" handler byte-for-byte (one U+FFFD per maximal
#         ill-formed subpart); valid UTF-8 round-trips to the same bytes.
def py_encode(b: bytes) -> str:
    return " ".join("%02x" % x for x in b)


def py_decode_hex(raw: str) -> str:
    """Lowercase contiguous hex of the decoded TEXT (matches the harness dump).

    empty / all-whitespace -> "";  any parse failure (non-hex / odd length) ->
    the raw input unchanged (mirrors the interpreter's `except: return raw`).
    """
    if not raw.strip():
        return ""
    try:
        text = bytes.fromhex(raw.replace(" ", "")).decode("utf-8", "replace")
    except Exception:
        return raw.encode("utf-8").hex()
    return text.encode("utf-8").hex()


# Byte payloads for the ENCODE direction.
_ENC_VECTORS = [
    b"",
    b"Hi",
    b"DRAG ME AROUND!",
    "DRAG ME AROUND!\nX: 1.50\nY: -2.00\nZ: 0.00".encode("utf-8"),
    "héllo".encode("utf-8"),              # multibyte (é)
    "日本語".encode("utf-8"),      # CJK (日本語)
    "\U0001f389".encode("utf-8"),              # 4-byte emoji (🎉)
    b" ",                                        # a single literal space byte
    bytes(range(256)),                           # every byte value incl NUL
]

# Input strings for the DECODE direction.
_DEC_VECTORS = [
    "",                                          # empty -> ""
    "   ",                                        # all-whitespace -> ""
    "48 69",                                      # canonical -> "Hi"
    "4869",                                        # contiguous -> "Hi"
    "48   69",                                     # extra spaces -> "Hi"
    "48\t69",                                      # tab between pairs -> "Hi"
    "c3 a9",                                       # é bytes
    "e6 97 a5 e6 9c ac e8 aa 9e",                 # 日本語 bytes
    "f0 9f 8e 89",                                # 🎉 bytes
    "4 8",                                          # space removed -> "48" -> "H"
    "zz",                                          # non-hex -> raw fallback
    "abc",                                         # odd length -> raw fallback
    py_encode("DRAG ME AROUND!\nX: 1.50".encode("utf-8")),   # round-trip
    # ill-formed UTF-8 that still parses as hex: re-encoded exactly like
    # CPython's .decode("utf-8","replace"), one U+FFFD per maximal subpart.
    # Codec-written values are always valid UTF-8, but an out-of-band raw
    # byte string must still match the interpreter.
    "ff",                                          # bad lead byte -> U+FFFD
    "80",                                          # stray continuation -> U+FFFD
    "c3 28",                                       # 2-byte lead, bad cont -> FFFD '('
    "e0 80",                                       # E0 needs A0..BF -> FFFD FFFD
    "ed a0 80",                                    # UTF-16 surrogate D800 -> 3x FFFD
    "f0 28 8c 28",                                 # F0 needs 90..BF -> FFFD '(' FFFD '('
    "f4 90 80 80",                                 # > U+10FFFF -> 4x FFFD
    "c0 80",                                       # overlong NUL -> FFFD FFFD
    "e1 80 41",                                    # valid prefix, ASCII breaks -> FFFD 'A'
    "f0 90 80",                                    # truncated 4-byte tail -> 1x FFFD
    "41 00 42",                                    # interior NUL is valid UTF-8 -> "A\0B"
    # valid-path coverage for every multibyte lead subrange (must pass through):
    "e0 a0 80",                                    # E0 A0..BF -> U+0800 (3-byte)
    "ed 80 80",                                    # ED 80..9F -> U+D000 (non-surrogate)
    "ee 80 80",                                    # EE..EF -> U+E000 (3-byte)
    "f1 80 80 80",                                 # F1..F3 -> U+40000 (4-byte)
    "c2",                                          # lone 2-byte lead at end -> 1x FFFD
    bytes(range(256)).hex(),                       # every byte, contiguous, no spaces
]


def _cpp_byte_literal(b: bytes) -> str:
    r"""Every byte as a \xNN escape (safe: a following \ or " stops the greedy
    \x, and we never emit a literal hex-digit char after an escape)."""
    return "".join("\\x%02x" % x for x in b)


def _harness_src(core_cpp: str) -> str:
    lines = [
        "#include <string>",
        "#include <cstddef>",
        "#include <cstdio>",
        core_cpp,
        "static void put_bytes(int idx, const std::string& s) {",
        '    printf("%d:", idx);',
        "    for (std::size_t i = 0; i < s.size(); ++i)",
        '        printf("%02x", (unsigned char)s[i]);',
        '    printf("\\n");',
        "}",
        "static void put_str(int idx, const std::string& s) {",
        '    printf("%d:%s\\n", idx, s.c_str());',
        "}",
        "int main() {",
    ]
    idx = 0
    for b in _ENC_VECTORS:
        lines.append('    { std::string in("%s", %d); put_str(%d, nd_hex_encode_str(in)); }'
                     % (_cpp_byte_literal(b), len(b), idx))
        idx += 1
    for s in _DEC_VECTORS:
        sb = s.encode("utf-8")
        lines.append('    { std::string in("%s", %d); put_bytes(%d, nd_hex_decode_str(in)); }'
                     % (_cpp_byte_literal(sb), len(sb), idx))
        idx += 1
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines)


@unittest.skipUnless(shutil.which("clang++"), "clang++ not available")
class TestHexTranscodeParity(unittest.TestCase):
    def test_cpp_core_matches_python_codec(self):
        from mpynode.native import compiler as codegen

        core = codegen._HEX_CORE_CPP
        d    = tempfile.mkdtemp(prefix="ndhex_")
        cpp  = os.path.join(d, "harness.cpp")
        exe  = os.path.join(d, "harness")
        with open(cpp, "w") as fh:
            fh.write(_harness_src(core))

        r = subprocess.run(["clang++", "-std=c++17", "-O2", "-o", exe, cpp],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0,
                         "harness compile failed:\n" + r.stderr)

        run = subprocess.run([exe], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0,
                         "harness run failed:\n" + run.stderr)

        got = {}
        for line in run.stdout.splitlines():
            k, _, v = line.partition(":")
            got[int(k)] = v

        expected = {}
        idx      = 0
        for b in _ENC_VECTORS:
            expected[idx] = py_encode(b)
            idx += 1
        for s in _DEC_VECTORS:
            expected[idx] = py_decode_hex(s)
            idx += 1

        self.assertEqual(len(got), len(expected),
                         "harness emitted %d lines, expected %d" % (len(got), len(expected)))
        for i in sorted(expected):
            self.assertEqual(
                got.get(i), expected[i],
                "vector %d mismatch: C++ %r != Python %r" % (i, got.get(i), expected[i]))


if __name__ == "__main__":
    unittest.main()
