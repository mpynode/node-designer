"""No SHIPPED C++ may name a variable after a Windows SAL annotation macro.

``sal.h`` (Windows SDK, pulled in transitively by every Maya/CRT header) defines
~423 OBJECT-LIKE macros whose names begin with a double underscore: ``__out``,
``__in``, ``__inout``, ``__range``, ``__success`` and friends. One of those used
as an identifier is not a style question, it is a preprocessor collision --

    MPoint* __out = &_cv[0];   ->   MPoint* [SA_annotation] = &_cv[0];

which MSVC reports as ``C2059: syntax error: '='``, then ``C2337: '__i':
attribute not found`` on every later ``__out[__i]``, plus a bogus ``C4467:
usage of ATL attributes is deprecated``. clang and gcc have no ``sal.h``, so the
same file compiles clean on macOS and Linux.

MEASURED on Windows 2026-08-31 (Maya 2025, VS 2022 toolset 14.40): the
``helixCurve`` optimizer winner declared ``MPoint* __out`` for a
contiguous-write fast path. It passed the optimizer's own compile gate (clang on
the macOS host), benchmarked faster, was promoted, and shipped -- then broke the
combined ``mPyMega`` build 32 translation units in. Nothing in the suite looked.

``optimizer_knowledge._NONPORTABLE`` now rejects such a candidate at generation
time. This is the other half: a gate over what is ALREADY COMMITTED, because a
source can also acquire the name by hand edit, by the porter, or from a cached
port that predates that rule. On Windows it checks against the REAL ``sal.h`` of
the installed SDK, so it is authoritative rather than a guess; elsewhere it
falls back to the same family regex the optimizer gate uses.
"""

from __future__ import annotations

import os
import re
import unittest

from tests import _paths

_ROOT = _paths.ROOT

# Where generated C++ is committed. plug-ins/ ships hand-written glue too -- the
# rule is a Windows fact, not a codegen one, so it applies there as well.
_SCAN_ROOTS = ("templates", "plug-ins", "scripts")

_IDENT_RE = re.compile(r"\b__[A-Za-z_][A-Za-z0-9_]*")

# Comment/string stripping: a SAL name NAMED in a comment (or in a string) is
# fine and is in fact how the fix documents itself. Mirrors
# optimizer_knowledge._code_only's intent, kept local so this file stands alone.
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')

_SAL_DEFINE_RE = re.compile(r"^\s*#define\s+(__[A-Za-z_][A-Za-z0-9_]*)", re.M)


def _code_only(src):
    return _STRING_RE.sub('""', _COMMENT_RE.sub(" ", src))


def _sal_names_from_sdk():
    """Every ``__``-prefixed macro the installed SDK's sal.h/specstrings.h
    defines, or ``None`` when there is no SDK to read (i.e. not Windows).

    Uses the SDK the compiler would actually use: %WindowsSdkDir% +
    %WindowsSDKVersion% when a developer shell exported them, else the newest
    versioned include dir under the default Windows Kits root.
    """
    roots = []
    sdk_dir = os.environ.get("WindowsSdkDir")
    ver = (os.environ.get("WindowsSDKVersion") or "").strip("\\/")
    if sdk_dir and ver:
        roots.append(os.path.join(sdk_dir, "Include", ver, "shared"))
    base = os.path.join(os.environ.get("ProgramFiles(x86)",
                                       r"C:\Program Files (x86)"),
                        "Windows Kits", "10", "include")
    if os.path.isdir(base):
        for name in sorted(os.listdir(base), reverse=True):
            roots.append(os.path.join(base, name, "shared"))

    for shared in roots:
        names = set()
        for header in ("sal.h", "specstrings.h"):
            path = os.path.join(shared, header)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    names.update(_SAL_DEFINE_RE.findall(fh.read()))
            except OSError:
                continue
        if names:
            return names
    return None


def _fallback_rule():
    """The optimizer gate's own SAL regex -- one source of truth for the
    families, so the two halves cannot drift apart."""
    import sys
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    from mpynode.native.ai import optimizer_knowledge as ok

    for rx, label in ok._NONPORTABLE:
        if "SAL" in label:
            return rx
    raise AssertionError(
        "optimizer_knowledge._NONPORTABLE lost its SAL rule -- the generation-"
        "time half of this gate is gone")


def _cpp_files():
    for top in _SCAN_ROOTS:
        base = os.path.join(_ROOT, top)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith((".cpp", ".h", ".hpp")):
                    yield os.path.join(dirpath, fn)


class TestNoSalMacroNamesInShippedCpp(unittest.TestCase):

    def test_the_scan_actually_sees_files(self):
        """Non-vacuity: an empty walk would make the real assertion pass."""
        self.assertGreater(len(list(_cpp_files())), 50)

    def test_no_committed_source_uses_a_sal_macro_name(self):
        sal = _sal_names_from_sdk()
        if sal is not None:
            def offenders(code):
                return sorted({m for m in _IDENT_RE.findall(code) if m in sal})
            how = "the installed SDK's sal.h (%d macros)" % len(sal)
        else:
            rx = _fallback_rule()
            def offenders(code):
                # The rule is all non-capturing groups, so findall yields whole
                # matches; finditer would be equivalent.
                return sorted({m.group(0) for m in rx.finditer(code)})
            how = "the optimizer gate's SAL family regex (no Windows SDK here)"

        bad = []
        for path in _cpp_files():
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    code = _code_only(fh.read())
            except OSError:
                continue
            hits = offenders(code)
            if hits:
                bad.append("%s: %s" % (os.path.relpath(path, _ROOT),
                                       ", ".join(hits)))
        self.assertEqual(
            bad, [],
            "shipped C++ names a variable after a Windows SAL macro, checked "
            "against %s. MSVC expands it into an attribute and fails with "
            "C2059/C2337 while clang compiles it clean, so this breaks ONLY on "
            "Windows. Rename the variable -- __i / __L0 / __s0 style temps are "
            "fine:\n  %s" % (how, "\n  ".join(bad)))

    def test_the_generation_time_half_still_exists(self):
        """This gate only catches what is already committed. The optimizer must
        still refuse to PRODUCE such a candidate."""
        rx = _fallback_rule()
        self.assertTrue(rx.search("MPoint* __out = &p[0];"))
        # ...and must not fire on the transpiler's own conventional temps.
        for ok_name in ("__i", "__L0", "__s0", "__o", "__n", "__a", "__mmA0"):
            self.assertFalse(rx.search("double %s = 0.0;" % ok_name), ok_name)


if __name__ == "__main__":
    unittest.main()
