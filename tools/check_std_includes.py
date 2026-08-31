#!/usr/bin/env python3
"""Static include-isolation checker: a ``std::`` facility used with no include.

THE DEFECT CLASS. libc++ (Apple clang) leaks transitive includes generously;
the MSVC STL does not. A translation unit that says ``std::array`` while only
including ``<vector>`` is rc=0 on macOS and C2039 on Windows. The whole macOS
pipeline is blind to it, because the only compile gate IS the macOS compile.
Recall calibration against five injected defects (mutex/sstream/fstream/map/
limits): the shipped build flags catch 2/5, ``-D_LIBCPP_REMOVE_TRANSITIVE_
INCLUDES -fsyntax-only`` catches 3/5, this static name->header check catches
5/5.

HOW IT WORKS. For a given source it strips comments and string literals,
extracts every ``std::<name>`` token with its first-use line, follows local
``#include "..."`` one hop to harvest the headers those pull in, and reports a
MISS when NONE of the standard-mandated providers of that name is included, or
an ORDER problem when a provider is included only AFTER first use.

CONSERVATIVE BY CONSTRUCTION. A name absent from the table is UNMAPPED, never a
failure. And the table is deliberately GENEROUS for names that every practical
implementation makes complete through a container/string header --
``std::pair``, ``std::make_pair``, ``std::move``, ``std::forward``,
``std::swap``, ``std::size_t``. A prior verification pass refuted seven such
hits in the mega corpus; reporting them again would be crying wolf and the
checker would be ignored.

Importable as a module (``check_file`` / ``check_text`` / ``check_region`` /
``missing_headers``) and runnable as a CLI over files and directories.

Run:
    python3 tools/check_std_includes.py "templates/All Templates Plugin/build/source"
    python3 tools/check_std_includes.py --self-test
"""

from __future__ import annotations

import os
import re
import sys
from collections import namedtuple


# ---------------------------------------------------------------------------
# name -> tuple of headers, ANY of which is a standard-mandated provider.
# Sourced from the [headers] synopses in C++17, not from what libc++ leaks.
# ---------------------------------------------------------------------------

# Headers that drag in <utility>/<cstddef> on every practical implementation
# (they need pair/size_t in their own synopses). Used to keep the checker off
# the seven refuted pair/move hits in the known-clean corpus.
_UTILITY_LIKE = (
    "utility", "map", "unordered_map", "set", "unordered_set", "vector",
    "string", "algorithm", "tuple", "array", "deque", "list", "queue",
    "stack", "memory", "iterator", "functional",
)

_SIZE_T_LIKE = (
    "cstddef", "cstdint", "cstring", "cstdio", "cstdlib", "ctime",
    "vector", "string", "array", "map", "set", "algorithm", "memory",
    "iterator", "limits", "sstream", "fstream", "iostream",
)

STD_NAME_HEADERS = {
    # -- containers ---------------------------------------------------------
    "vector": ("vector",),
    "map": ("map",),
    "multimap": ("map",),
    "set": ("set",),
    "multiset": ("set",),
    "unordered_map": ("unordered_map",),
    "unordered_multimap": ("unordered_map",),
    "unordered_set": ("unordered_set",),
    "unordered_multiset": ("unordered_set",),
    "deque": ("deque",),
    "list": ("list",),
    "forward_list": ("forward_list",),
    "array": ("array",),
    "queue": ("queue",),
    "priority_queue": ("queue",),
    "stack": ("stack",),
    "bitset": ("bitset",),
    "valarray": ("valarray",),
    # -- string -------------------------------------------------------------
    "string": ("string",),
    "wstring": ("string",),
    "to_string": ("string",),
    "stod": ("string",),
    "stof": ("string",),
    "stoi": ("string",),
    "stol": ("string",),
    "stoll": ("string",),
    "stoul": ("string",),
    "stoull": ("string",),
    "string_view": ("string_view",),
    "char_traits": ("string", "iosfwd"),
    # -- memory -------------------------------------------------------------
    "shared_ptr": ("memory",),
    "unique_ptr": ("memory",),
    "weak_ptr": ("memory",),
    "make_shared": ("memory",),
    "make_unique": ("memory",),
    "allocator": ("memory",),
    "addressof": ("memory",),
    "default_delete": ("memory",),
    # -- utility / type traits ----------------------------------------------
    # GENEROUS ON PURPOSE -- see the module docstring. These are complete via
    # any container/string header on every implementation, so demanding
    # <utility> here produces false hits, not findings.
    "pair": _UTILITY_LIKE,
    "make_pair": _UTILITY_LIKE,
    "move": _UTILITY_LIKE,
    "forward": _UTILITY_LIKE,
    "swap": _UTILITY_LIKE,
    "declval": _UTILITY_LIKE,
    "get": _UTILITY_LIKE,
    "tuple": ("tuple",),
    "make_tuple": ("tuple",),
    "tie": ("tuple",),
    "initializer_list": _UTILITY_LIKE + ("initializer_list",),
    "is_same": ("type_traits",),
    "is_integral": ("type_traits",),
    "is_floating_point": ("type_traits",),
    "is_arithmetic": ("type_traits",),
    "is_pointer": ("type_traits",),
    "enable_if": ("type_traits",),
    "enable_if_t": ("type_traits",),
    "conditional": ("type_traits",),
    "conditional_t": ("type_traits",),
    "decay": ("type_traits",),
    "decay_t": ("type_traits",),
    "remove_reference": ("type_traits",),
    "remove_reference_t": ("type_traits",),
    "remove_cv": ("type_traits",),
    "underlying_type": ("type_traits",),
    "function": ("functional",),
    "bind": ("functional",),
    "hash": ("functional", "string", "unordered_map", "unordered_set"),
    "less": ("functional",),
    "greater": ("functional",),
    "plus": ("functional",),
    "ref": ("functional",),
    "cref": ("functional",),
    # -- algorithm ----------------------------------------------------------
    "sort": ("algorithm",),
    "stable_sort": ("algorithm",),
    "partial_sort": ("algorithm",),
    "nth_element": ("algorithm",),
    "lower_bound": ("algorithm",),
    "upper_bound": ("algorithm",),
    "equal_range": ("algorithm",),
    "binary_search": ("algorithm",),
    "find": ("algorithm",),
    "find_if": ("algorithm",),
    "search": ("algorithm",),
    "copy": ("algorithm",),
    "copy_n": ("algorithm",),
    "copy_if": ("algorithm",),
    "fill": ("algorithm",),
    "fill_n": ("algorithm",),
    "generate": ("algorithm",),
    "unique": ("algorithm",),
    "reverse": ("algorithm",),
    "rotate": ("algorithm",),
    "shuffle": ("algorithm",),
    "min": ("algorithm",),
    "max": ("algorithm",),
    "minmax": ("algorithm",),
    "min_element": ("algorithm",),
    "max_element": ("algorithm",),
    "minmax_element": ("algorithm",),
    "clamp": ("algorithm",),
    "push_heap": ("algorithm",),
    "pop_heap": ("algorithm",),
    "make_heap": ("algorithm",),
    "sort_heap": ("algorithm",),
    "count": ("algorithm",),
    "count_if": ("algorithm",),
    "remove": ("algorithm",),
    "remove_if": ("algorithm",),
    "transform": ("algorithm",),
    "any_of": ("algorithm",),
    "all_of": ("algorithm",),
    "none_of": ("algorithm",),
    "for_each": ("algorithm",),
    "equal": ("algorithm",),
    "lexicographical_compare": ("algorithm",),
    "includes": ("algorithm",),
    "set_union": ("algorithm",),
    "set_intersection": ("algorithm",),
    "set_difference": ("algorithm",),
    "iter_swap": ("algorithm",),
    "swap_ranges": ("algorithm",),
    # -- numeric ------------------------------------------------------------
    "accumulate": ("numeric",),
    "iota": ("numeric",),
    "inner_product": ("numeric",),
    "partial_sum": ("numeric",),
    "adjacent_difference": ("numeric",),
    "gcd": ("numeric",),
    "lcm": ("numeric",),
    # -- cmath --------------------------------------------------------------
    "fabs": ("cmath",),
    "abs": ("cmath", "cstdlib"),
    "sqrt": ("cmath",),
    "cbrt": ("cmath",),
    "pow": ("cmath",),
    "floor": ("cmath",),
    "ceil": ("cmath",),
    "round": ("cmath",),
    "lround": ("cmath",),
    "llround": ("cmath",),
    "nearbyint": ("cmath",),
    "rint": ("cmath",),
    "trunc": ("cmath",),
    "fmod": ("cmath",),
    "remainder": ("cmath",),
    "modf": ("cmath",),
    "frexp": ("cmath",),
    "ldexp": ("cmath",),
    "sin": ("cmath",),
    "cos": ("cmath",),
    "tan": ("cmath",),
    "asin": ("cmath",),
    "acos": ("cmath",),
    "atan": ("cmath",),
    "atan2": ("cmath",),
    "sinh": ("cmath",),
    "cosh": ("cmath",),
    "tanh": ("cmath",),
    "asinh": ("cmath",),
    "acosh": ("cmath",),
    "atanh": ("cmath",),
    "exp": ("cmath",),
    "exp2": ("cmath",),
    "expm1": ("cmath",),
    "log": ("cmath",),
    "log1p": ("cmath",),
    "log2": ("cmath",),
    "log10": ("cmath",),
    "hypot": ("cmath",),
    "erf": ("cmath",),
    "erfc": ("cmath",),
    "tgamma": ("cmath",),
    "lgamma": ("cmath",),
    "isnan": ("cmath",),
    "isinf": ("cmath",),
    "isfinite": ("cmath",),
    "isnormal": ("cmath",),
    "signbit": ("cmath",),
    "copysign": ("cmath",),
    "nan": ("cmath",),
    "fma": ("cmath",),
    "fmin": ("cmath",),
    "fmax": ("cmath",),
    "fdim": ("cmath",),
    # -- limits -------------------------------------------------------------
    "numeric_limits": ("limits",),
    # -- fixed-width ints / sizes -------------------------------------------
    "int8_t": ("cstdint",),
    "int16_t": ("cstdint",),
    "int32_t": ("cstdint",),
    "int64_t": ("cstdint",),
    "uint8_t": ("cstdint",),
    "uint16_t": ("cstdint",),
    "uint32_t": ("cstdint",),
    "uint64_t": ("cstdint",),
    "intmax_t": ("cstdint",),
    "uintmax_t": ("cstdint",),
    "intptr_t": ("cstdint",),
    "uintptr_t": ("cstdint",),
    "size_t": _SIZE_T_LIKE,
    "ptrdiff_t": _SIZE_T_LIKE,
    "nullptr_t": ("cstddef",),
    "byte": ("cstddef",),
    # -- cstring ------------------------------------------------------------
    "memcpy": ("cstring",),
    "memset": ("cstring",),
    "memcmp": ("cstring",),
    "memmove": ("cstring",),
    "strcmp": ("cstring",),
    "strncmp": ("cstring",),
    "strlen": ("cstring",),
    "strcpy": ("cstring",),
    "strncpy": ("cstring",),
    # -- cstdio -------------------------------------------------------------
    "snprintf": ("cstdio",),
    "sprintf": ("cstdio",),
    "printf": ("cstdio",),
    "fprintf": ("cstdio",),
    "sscanf": ("cstdio",),
    "fopen": ("cstdio",),
    "fclose": ("cstdio",),
    "fread": ("cstdio",),
    "fwrite": ("cstdio",),
    "FILE": ("cstdio",),
    # -- cstdlib ------------------------------------------------------------
    "atoi": ("cstdlib",),
    "atof": ("cstdlib",),
    "strtol": ("cstdlib",),
    "strtoll": ("cstdlib",),
    "strtod": ("cstdlib",),
    "malloc": ("cstdlib",),
    "calloc": ("cstdlib",),
    "realloc": ("cstdlib",),
    "free": ("cstdlib",),
    "qsort": ("cstdlib",),
    "exit": ("cstdlib",),
    "getenv": ("cstdlib",),
    "system": ("cstdlib",),
    "llabs": ("cstdlib",),
    "div": ("cstdlib",),
    # -- ctime --------------------------------------------------------------
    "time": ("ctime",),
    "clock": ("ctime",),
    "time_t": ("ctime",),
    "tm": ("ctime",),
    "strftime": ("ctime",),
    # -- exceptions ---------------------------------------------------------
    "runtime_error": ("stdexcept",),
    "logic_error": ("stdexcept",),
    "out_of_range": ("stdexcept",),
    "invalid_argument": ("stdexcept",),
    "length_error": ("stdexcept",),
    "range_error": ("stdexcept",),
    "domain_error": ("stdexcept",),
    "overflow_error": ("stdexcept",),
    "underflow_error": ("stdexcept",),
    "exception": ("exception", "stdexcept"),
    "bad_alloc": ("new",),
    "nothrow": ("new",),
    "terminate": ("exception",),
    # -- iostreams ----------------------------------------------------------
    "ostringstream": ("sstream",),
    "istringstream": ("sstream",),
    "stringstream": ("sstream",),
    "ofstream": ("fstream",),
    "ifstream": ("fstream",),
    "fstream": ("fstream",),
    "cout": ("iostream",),
    "cerr": ("iostream",),
    "cin": ("iostream",),
    "clog": ("iostream",),
    "endl": ("ostream", "iostream", "sstream", "fstream", "iomanip"),
    "flush": ("ostream", "iostream", "sstream", "fstream"),
    "ostream": ("ostream", "iostream", "sstream", "fstream"),
    "istream": ("istream", "iostream", "sstream", "fstream"),
    "iostream": ("istream", "ostream", "iostream", "sstream", "fstream"),
    "ios": ("ios", "iosfwd", "iostream", "sstream", "fstream"),
    "ios_base": ("ios", "iostream", "sstream", "fstream"),
    "streamsize": ("ios", "iosfwd", "iostream", "sstream", "fstream"),
    "streamoff": ("ios", "iosfwd", "iostream", "sstream", "fstream"),
    "streampos": ("ios", "iosfwd", "iostream", "sstream", "fstream"),
    "setprecision": ("iomanip",),
    "setw": ("iomanip",),
    "setfill": ("iomanip",),
    "fixed": ("ios", "iostream", "sstream", "fstream", "iomanip"),
    "scientific": ("ios", "iostream", "sstream", "fstream", "iomanip"),
    "hex": ("ios", "iostream", "sstream", "fstream", "iomanip"),
    "dec": ("ios", "iostream", "sstream", "fstream", "iomanip"),
    "oct": ("ios", "iostream", "sstream", "fstream", "iomanip"),
    # -- threading (the motivating class) -----------------------------------
    "mutex": ("mutex",),
    "recursive_mutex": ("mutex",),
    "timed_mutex": ("mutex",),
    "lock_guard": ("mutex",),
    "unique_lock": ("mutex",),
    "scoped_lock": ("mutex",),
    "lock": ("mutex",),
    "call_once": ("mutex",),
    "once_flag": ("mutex",),
    "shared_mutex": ("shared_mutex",),
    "shared_lock": ("shared_mutex",),
    "thread": ("thread",),
    "this_thread": ("thread",),
    "async": ("future",),
    "future": ("future",),
    "promise": ("future",),
    "packaged_task": ("future",),
    "launch": ("future",),
    "atomic": ("atomic",),
    "atomic_flag": ("atomic",),
    "atomic_int": ("atomic",),
    "atomic_bool": ("atomic",),
    "memory_order": ("atomic",),
    "memory_order_relaxed": ("atomic",),
    "memory_order_consume": ("atomic",),
    "memory_order_acquire": ("atomic",),
    "memory_order_release": ("atomic",),
    "memory_order_acq_rel": ("atomic",),
    "memory_order_seq_cst": ("atomic",),
    "atomic_thread_fence": ("atomic",),
    "condition_variable": ("condition_variable",),
    "condition_variable_any": ("condition_variable",),
    "cv_status": ("condition_variable",),
    # -- random -------------------------------------------------------------
    "mt19937": ("random",),
    "mt19937_64": ("random",),
    "minstd_rand": ("random",),
    "default_random_engine": ("random",),
    "random_device": ("random",),
    "uniform_real_distribution": ("random",),
    "uniform_int_distribution": ("random",),
    "normal_distribution": ("random",),
    "bernoulli_distribution": ("random",),
    "discrete_distribution": ("random",),
    "seed_seq": ("random",),
    "generate_canonical": ("random",),
    # -- chrono -------------------------------------------------------------
    "chrono": ("chrono",),
    # -- misc ---------------------------------------------------------------
    "optional": ("optional",),
    "nullopt": ("optional",),
    "variant": ("variant",),
    "visit": ("variant",),
    "any": ("any",),
    "complex": ("complex",),
    "back_inserter": ("iterator",),
    "front_inserter": ("iterator",),
    "inserter": ("iterator",),
    "begin": ("iterator",) + _UTILITY_LIKE,
    "end": ("iterator",) + _UTILITY_LIKE,
    "distance": ("iterator",),
    "advance": ("iterator",),
    "next": ("iterator",),
    "prev": ("iterator",),
    "iterator": ("iterator",),
    "iterator_traits": ("iterator",),
    "reverse_iterator": ("iterator",),
}


Finding = namedtuple("Finding", "kind path line name headers have_line")

INC_RE = re.compile(r'^\s*#\s*include\s*<([^>]+)>')
LOCAL_INC_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
STD_RE = re.compile(r'\bstd\s*::\s*([A-Za-z_][A-Za-z0-9_]*)')
_LINE_COMMENT_RE = re.compile(r'//.*$')
_STRLIT_RE = re.compile(r'"(?:\\.|[^"\\])*"')
_SOURCE_EXTS = (".cpp", ".cxx", ".cc", ".h", ".hpp", ".inl")


def strip_noise(text):
    """Blank ``/* */`` blocks, ``//`` comments and string literals, keeping
    line structure so reported line numbers stay true.

    The same shape a prior reserved-identifier lint used, which found 0 false
    hits on this corpus. Literals are blanked before comments so a ``"//"``
    inside a path string cannot swallow real code to its right."""
    out = []
    i = 0
    n = len(text or "")
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                j = n
            out.append(re.sub(r'[^\n]', ' ', text[i:j + 2]))
            i = j + 2
        else:
            j = text.find("/*", i)
            if j < 0:
                j = n
            chunk = text[i:j]
            chunk = "\n".join(
                _STRLIT_RE.sub(lambda m: " " * len(m.group(0)),
                               _LINE_COMMENT_RE.sub("", ln))
                for ln in chunk.split("\n"))
            out.append(chunk)
            i = j
    return "".join(out)


def std_names(text):
    """``{std name: first-use line}`` for ``text`` (comments/strings stripped)."""
    first = {}
    for ln, line in enumerate(strip_noise(text).split("\n"), 1):
        for m in STD_RE.finditer(line):
            first.setdefault(m.group(1), ln)
    return first


def _harvest_local(path, seen, out, search_dirs):
    """One hop through ``#include "local.h"`` so a probe that pulls
    ``nd_runtime.h`` is not false-positived on the header's own includes."""
    real = os.path.realpath(path)
    if real in seen:
        return
    seen.add(real)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return
    for line in txt.split("\n"):
        m = INC_RE.match(line)
        if m:
            out.setdefault(m.group(1), 0)   # line 0 == "via a local header"
            continue
        m = LOCAL_INC_RE.match(line)
        if m:
            for cand in _candidates(path, m.group(1), search_dirs):
                if os.path.exists(cand):
                    _harvest_local(cand, seen, out, search_dirs)
                    break


def _candidates(path, rel, search_dirs):
    yield os.path.join(os.path.dirname(path), rel)
    for d in search_dirs or ():
        yield os.path.join(d, rel)


def included_headers(text, path=None, search_dirs=()):
    """``{header: first line}`` for ``text``, following local includes one hop.

    Reads the RAW text (not the stripped one): a ``#include`` inside a comment
    is not an include, but blanking comments would also renumber nothing, so
    the cheap and correct thing is to match the directive form on raw lines and
    let the strip pass handle the ``std::`` side only."""
    includes = {}
    for ln, line in enumerate((text or "").split("\n"), 1):
        m = INC_RE.match(line)
        if m:
            includes.setdefault(m.group(1), ln)
            continue
        m = LOCAL_INC_RE.match(line)
        if m and path:
            for cand in _candidates(path, m.group(1), search_dirs):
                if os.path.exists(cand):
                    _harvest_local(cand, set(), includes, search_dirs)
                    break
    return includes


def _findings(uses, includes, path, check_order):
    misses = []
    for name, use_ln in sorted(uses.items(), key=lambda kv: (kv[1], kv[0])):
        headers = STD_NAME_HEADERS.get(name)
        if headers is None:
            continue                       # UNMAPPED is never a failure
        present = [(h, includes[h]) for h in headers if h in includes]
        if not present:
            misses.append(Finding("miss", path, use_ln, name, headers, None))
        elif check_order and min(l for _, l in present) > use_ln:
            h, l = min(present, key=lambda hl: hl[1])
            misses.append(Finding("order", path, use_ln, name, (h,), l))
    return misses


def check_text(text, path=None, search_dirs=(), extra_headers=(),
               check_order=True):
    """Findings for one source given as text. ``extra_headers`` are treated as
    already included (for a fragment whose includes live elsewhere)."""
    includes = included_headers(text, path=path, search_dirs=search_dirs)
    for h in extra_headers or ():
        includes.setdefault(h, 0)
    return _findings(std_names(text), includes, path, check_order)


def check_file(path, search_dirs=()):
    """Findings for one file on disk."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return check_text(fh.read(), path=path, search_dirs=search_dirs)


def check_region(region_text, file_text, path=None, search_dirs=()):
    """Findings for a REGION of a file, resolved against the WHOLE file's
    includes.

    This is the AI path's shape: the model authors only the text between the
    PORT markers, while the ``#include`` block belongs to codegen. Line numbers
    are region-relative. Order is not checked -- the region always sits below
    the include block."""
    includes = included_headers(file_text, path=path, search_dirs=search_dirs)
    return _findings(std_names(region_text), includes, path, False)


def missing_headers(findings):
    """The ordered, de-duplicated headers that would satisfy ``findings``.

    The FIRST provider of each name is chosen, which is the standard's own
    home for it (``abs`` -> ``<cmath>``, not ``<cstdlib>``). Deterministic:
    findings arrive sorted by first-use line."""
    out = []
    for f in findings:
        if f.kind != "miss":
            continue
        h = f.headers[0]
        if h not in out:
            out.append(h)
    return out


def format_finding(f):
    if f.kind == "order":
        return ("ORDER line %-6d std::%-26s <%s> only included at line %s"
                % (f.line, f.name, f.headers[0], f.have_line))
    return ("MISS  line %-6d std::%-26s needs one of <%s>"
            % (f.line, f.name, "> <".join(f.headers)))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def iter_sources(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in sorted(dirs)
                           if d not in ("_snapshots", ".mpynode_local",
                                        "CompilerIdCXX", "__pycache__")]
                for fn in sorted(files):
                    if fn.endswith(_SOURCE_EXTS):
                        yield os.path.join(root, fn)
        else:
            yield p


def _self_test():
    """Inject the five calibration defects into COPIES in /tmp and prove 5/5.

    Never touches a repo source: the base text is synthesized here, and the
    copies are written under /tmp. Also asserts the refuted pair/move shape
    stays SILENT, because a checker that cries wolf gets switched off."""
    import tempfile

    base = ("#include <vector>\n"
            "#include <cmath>\n"
            "#include <string>\n"
            "#include <map>\n"
            "void f() { std::vector<double> v; v.push_back(std::sqrt(2.0)); }\n")
    cases = [
        ("mutex", "std::mutex g_m; std::lock_guard<std::mutex> lk(g_m);"),
        ("sstream", "std::ostringstream oss; oss << 1;"),
        ("fstream", "std::ifstream fh(\"x\");"),
        ("array", "std::array<double,3> a{};"),
        ("limits", "double d = std::numeric_limits<double>::max();"),
    ]
    tmp = tempfile.mkdtemp(prefix="check_std_includes_")
    caught = 0
    for header, stmt in cases:
        path = os.path.join(tmp, "inj_%s.cpp" % header)
        with open(path, "w") as fh:
            fh.write(base + "void g() { %s }\n" % stmt)
        found = check_file(path)
        hit = header in missing_headers(found)
        caught += 1 if hit else 0
        print("  %-8s -> %s%s" % (
            header, "CAUGHT" if hit else "MISSED",
            "" if hit else "   (%s)" % [f.name for f in found]))

    clean = os.path.join(tmp, "clean_pair.cpp")
    with open(clean, "w") as fh:
        fh.write(base + "void h() { std::map<int,int> m; "
                        "m.insert(std::make_pair(1,2)); "
                        "std::string s = std::move(std::string(\"a\")); }\n")
    quiet = check_file(clean)
    print("  %-8s -> %s" % ("pair/move",
                            "SILENT" if not quiet else
                            "CRIED WOLF %s" % [f.name for f in quiet]))
    print("self-test: %d/%d injected defects caught, %d false hits"
          % (caught, len(cases), len(quiet)))
    return 0 if (caught == len(cases) and not quiet) else 1


def main(argv):
    args = list(argv[1:])
    if "--self-test" in args:
        return _self_test()
    search_dirs, paths = [], []
    for a in args:
        if a.startswith("-I"):
            search_dirs.append(a[2:])
        else:
            paths.append(a)
    if not paths:
        print("usage: check_std_includes.py [-I<dir>] <file.cpp|dir> ...")
        print("       check_std_includes.py --self-test")
        return 2
    files = list(iter_sources(paths))
    total = 0
    for path in files:
        found = check_file(path, search_dirs=search_dirs)
        if not found:
            continue
        print("=" * 72)
        print(path)
        for f in found:
            total += 1
            print("  " + format_finding(f))
    print("=" * 72)
    print("files scanned : %d" % len(files))
    print("findings      : %d" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
