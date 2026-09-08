"""Follow a node's imports to the source of the pure-Python helpers it calls.

When a node's Compute/Init imports a helper from an external module -- e.g. a
shared ``geo_math`` the TA reuses across several nodes -- the native porter
otherwise sees only the *call site* (``geo_math.curvature(...)``) with no body to
translate. This module resolves those imports to their SOURCE so the porter can
port the helper into the C++ alongside the compute.

Resolution is STATIC and read-only: we locate each module's file with
``importlib.util.find_spec`` and extract the exact ``def``/``class`` source with
``ast`` -- we never ``import``/execute the user's module (no module-level side
effects; matters in this pickle/RCE-sensitive codebase). It is also best-effort:
ANY failure degrades to "no helper found" so spec extraction never breaks.

What we DON'T follow (by design -- the porter handles these another way, or they
can't be ported):
  * the curated math libraries (numpy/scipy/numba/PIL/cv2/skimage) -- the porter
    already injects hand-written C++ for these via ``translation_knowledge``;
  * hard-blocker libraries (requests/pandas/torch/...) -- non-portable anyway;
  * the standard library and C-extension / built-in modules -- no portable .py
    source to follow.

Pure (ast/importlib/sysconfig + file reads) -- no Maya/Qt, so it is unit-testable
headless and safe to call from ``spec_extractor.extract_spec``.
"""

from __future__ import annotations

import ast
import importlib.machinery as _machinery
import os
import sysconfig

# Single source of truth for "what counts as a library we DON'T follow" -- reuse
# spec_extractor's lists so this can never drift from the portability assessment.
from mpynode.native.spec import spec_extractor as _se

_SKIP_LIBS = set(_se._PORTABLE_MATH_LIBS) | set(_se._HARD_BLOCKER_LIBS)


def _stdlib_dirs() -> set:
    dirs = set()
    for key in ("stdlib", "platstdlib"):
        try:
            p = sysconfig.get_paths().get(key)
            if p:
                dirs.add(os.path.realpath(p))
        except Exception:
            pass
    return dirs


def _module_file(modname: str):
    """Abs ``.py`` path for ``modname`` or None -- resolved STATICALLY.

    We must NOT use ``importlib.util.find_spec(dotted)``: for a submodule it
    imports the parent package to read its ``__path__``, executing the parent's
    ``__init__.py`` (an RCE-on-extract surface this module exists to avoid). So
    we walk the dotted name level-by-level with ``PathFinder.find_spec``, which
    only LOCATES (never loads): each level's ``submodule_search_locations`` (the
    package ``__path__``, available without running ``__init__``) becomes the
    search path for the next level. Returns None for built-in / frozen /
    namespace / C-extension modules (no portable .py source) and for anything
    PathFinder can't resolve from the filesystem.
    """
    try:
        parts = modname.split(".")
        search = None  # None -> search sys.path (top level)
        spec = None
        for i, _part in enumerate(parts):
            full = ".".join(parts[: i + 1])
            spec = _machinery.PathFinder.find_spec(full, search)
            if spec is None:
                return None
            search = list(spec.submodule_search_locations or []) or None
            if search is None and i < len(parts) - 1:
                return None  # a non-package segment but more segments remain
        origin = getattr(spec, "origin", None)
        if not origin or origin in ("built-in", "frozen", "namespace"):
            return None
        if not origin.endswith(".py"):
            return None
        return origin
    except Exception:
        return None


def _is_followable(modname: str, path: str, stdlib_dirs: set) -> bool:
    """A module is followable iff it is not a curated/blocked lib and its source
    does not live under the standard library."""
    if modname.split(".")[0] in _SKIP_LIBS:
        return False
    rp = os.path.realpath(path)
    for d in stdlib_dirs:
        if rp == d or rp.startswith(d + os.sep):
            return False
    return True


def _build_import_map(tree: ast.AST) -> dict:
    """Map a bound NAME -> import target.

      ``import mod`` / ``import mod as m``  -> name -> ("module", modname)
      ``from mod import f as g``            -> g    -> ("from", modname, "f")

    Relative imports and ``import *`` are skipped (no resolvable target).
    """
    m = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    m[alias.asname] = ("module", alias.name)
                else:
                    top = alias.name.split(".")[0]
                    m[top] = ("module", top)
        elif isinstance(node, ast.ImportFrom):
            if (node.level or 0) > 0 or not node.module:
                continue  # relative import: no package context to resolve
            for alias in node.names:
                if alias.name == "*":
                    continue
                m[alias.asname or alias.name] = ("from", node.module, alias.name)
    return m


def _top_level_defs(tree: ast.AST) -> dict:
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _attr_chain(attr_node: ast.Attribute):
    """Flatten ``a.b.c`` -> ("a", ["b", "c"]) (base Name id, attr list, last =
    the accessed symbol). None if the chain root isn't a plain Name."""
    parts = []
    cur = attr_node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.reverse()
    return cur.id, parts


def _module_ref_from_attr(attr_node: ast.Attribute, import_map: dict):
    """Resolve an attribute access ``mod.sub.func`` against ``import_map`` to a
    ``(module, symbol)`` ref, handling dotted modules (``import pkg.sub`` ->
    ``pkg.sub.func``). None if the base isn't an imported module."""
    chain = _attr_chain(attr_node)
    if not chain:
        return None
    base, attrs = chain
    ent = import_map.get(base)
    if not (ent and ent[0] == "module"):
        return None
    real = ent[1]  # the real (possibly dotted) module the base binds to
    middle = attrs[:-1]  # extra package segments between base and the symbol
    module = real + ("." + ".".join(middle) if middle else "")
    return (module, attrs[-1])


def _param_names(node: ast.AST) -> set:
    """Parameter names bound by a FunctionDef (so a param that shadows a
    top-level def isn't mistaken for a call to that def)."""
    names = set()
    args = getattr(node, "args", None)
    if args is not None:
        for a in (list(getattr(args, "posonlyargs", [])) + list(args.args)
                  + list(args.kwonlyargs)):
            names.add(a.arg)
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
    return names


def _refs_in(tree: ast.AST, import_map: dict) -> set:
    """(module, symbol) pairs referenced through ``import_map`` inside ``tree``."""
    refs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            ent = import_map.get(node.id)
            if ent and ent[0] == "from":
                refs.add((ent[1], ent[2]))
        elif isinstance(node, ast.Attribute):
            ref = _module_ref_from_attr(node, import_map)
            if ref:
                refs.add(ref)
    return refs


def _deps_of(node: ast.AST, modname: str, top_defs: dict, import_map: dict) -> set:
    """Transitive (module, symbol) deps referenced from inside one def's body --
    same-module sibling defs, plus this module's own imports. Over-inclusion is
    harmless (extra reference context); under-inclusion would drop a real helper,
    so we err toward including -- except we skip the def's own parameter names so
    a param shadowing a sibling def isn't mistaken for a call to it."""
    deps = set()
    bound = _param_names(node)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            nm = sub.id
            if nm in bound:
                continue
            if nm in top_defs:
                deps.add((modname, nm))
            else:
                ent = import_map.get(nm)
                if ent and ent[0] == "from":
                    deps.add((ent[1], ent[2]))
        elif isinstance(sub, ast.Attribute):
            ref = _module_ref_from_attr(sub, import_map)
            if ref:
                deps.add(ref)
    return deps


def _node_source(text: str, node: ast.AST) -> str:
    decos = getattr(node, "decorator_list", None) or []
    # ``ast.get_source_segment`` returns the def/class WITHOUT its decorators, so
    # a decorated helper is sliced from the source to include them (its behaviour
    # depends on them). Undecorated defs use the precise segment.
    if not decos:
        try:
            seg = ast.get_source_segment(text, node)
            if seg:
                return seg
        except Exception:
            pass
    try:  # line slice -- extend start back over any decorators
        lines = text.splitlines()
        start = node.lineno - 1
        for d in decos:
            start = min(start, d.lineno - 1)
        end = getattr(node, "end_lineno", None)
        if end:
            return "\n".join(lines[start:end])
    except Exception:
        pass
    try:  # last resort
        seg = ast.get_source_segment(text, node)
        if seg:
            return seg
    except Exception:
        pass
    return ""


def collect_helper_sources(compute: str, init: str = "", *, max_sources: int = 50) -> dict:
    """Resolve the pure-Python helpers ``compute``+``init`` import and call.

    Returns ``{"sources": [{"module", "name", "source"}], "skipped":
    [{"ref", "reason"}], "errors": [str]}``. Never raises -- any failure leaves
    ``sources`` as-is (degrades to "nothing followed").
    """
    result = {"sources": [], "skipped": [], "errors": []}
    try:
        stdlib_dirs = _stdlib_dirs()
        entry_src = "%s\n%s" % (init or "", compute or "")
        try:
            entry_tree = ast.parse(entry_src)
        except Exception:
            return result  # unparseable expression -> follow nothing
        entry_imports = _build_import_map(entry_tree)
        # SORTED, not list(): ``_refs_in``/``_deps_of`` return SETS, and Python
        # randomizes string hashing per process, so raw iteration made the BFS
        # order -- and ``result["sources"]`` -- differ every run. That lands in
        # ``spec['external_helper_units']``, and port_cache's json.dumps(
        # sort_keys=True) sorts DICT KEYS but PRESERVES LIST ORDER. Measured across
        # two mayapy runs: 13 of 42 templates got a different cache key every time,
        # so the porter re-ran the LLM on every rebuild. Sorting the TRAVERSAL (not
        # ``result["sources"]``) keeps the BFS ordering -- sorted RESULTS would
        # change which unit shadows which in nd_lower._combined_helper_source.
        worklist = sorted(_refs_in(entry_tree, entry_imports))
        visited = set()
        module_cache = {}  # modname -> (text, top_defs, import_map) | None

        def _load(modname):
            if modname in module_cache:
                return module_cache[modname]
            entry = None
            path = _module_file(modname)
            if path and _is_followable(modname, path, stdlib_dirs):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                    tree = ast.parse(text)
                    entry = (text, _top_level_defs(tree), _build_import_map(tree))
                except Exception as exc:
                    result["errors"].append("parse %s: %s" % (modname, exc))
                    entry = None
            module_cache[modname] = entry
            return entry

        while worklist and len(result["sources"]) < max_sources:
            modname, symbol = worklist.pop(0)
            if (modname, symbol) in visited:
                continue
            visited.add((modname, symbol))

            if modname.split(".")[0] in _SKIP_LIBS:
                result["skipped"].append(
                    {"ref": "%s.%s" % (modname, symbol),
                     "reason": "curated/blocked library (handled elsewhere)"})
                continue
            loaded = _load(modname)
            if loaded is None:
                result["skipped"].append(
                    {"ref": "%s.%s" % (modname, symbol),
                     "reason": "not a followable pure-Python module"})
                continue
            text, top_defs, imap = loaded
            node = top_defs.get(symbol)
            if node is None:
                result["skipped"].append(
                    {"ref": "%s.%s" % (modname, symbol),
                     "reason": "name is not a top-level def/class"})
                continue
            src = _node_source(text, node)
            if not src:
                result["skipped"].append(
                    {"ref": "%s.%s" % (modname, symbol),
                     "reason": "could not extract source"})
                continue
            result["sources"].append(
                {"module": modname, "name": symbol, "source": src})
            for dep in sorted(_deps_of(node, modname, top_defs, imap)):
                if dep not in visited:
                    worklist.append(dep)
    except Exception as exc:  # defensive: never break spec extraction
        result["errors"].append("%s: %s" % (type(exc).__name__, exc))
    return result


def render_for_prompt(result: dict) -> str:
    """Render ``collect_helper_sources`` output into a prompt text block (or "")."""
    sources = (result or {}).get("sources") or []
    if not sources:
        return ""
    by_mod = {}
    order = []
    for s in sources:
        m = s.get("module", "?")
        if m not in by_mod:
            by_mod[m] = []
            order.append(m)
        by_mod[m].append(s.get("source", ""))
    blocks = []
    for m in order:
        blocks.append("# --- from module %r ---\n%s" % (m, "\n\n".join(by_mod[m])))
    return "\n\n".join(blocks)


def follow(compute: str, init: str = "") -> str:
    """Convenience: ``render_for_prompt(collect_helper_sources(...))``."""
    return render_for_prompt(collect_helper_sources(compute, init))
