#!/usr/bin/env python
"""Reachability scan: mpynode dependencies reachable from a @maya_command.

A @maya_command body ships as EMBEDDED PYTHON inside the compiled .mll (see
``native/compiler/kernels/command_dispatch.py``). On a machine with Maya but
WITHOUT mpynode on sys.path, any ``import mpynode...`` that the command path
touches raises ModuleNotFoundError. This tool finds those, statically.

WHAT COUNTS AS REACHABLE (the two ways an import fires):

  1. MODULE SCOPE. ``build_methods_namespace`` execs the WHOLE methods source
     before it looks up any function, so every module-scope import runs on the
     first command call -- reachability is irrelevant, it always fires.
  2. FROM A COMMAND, BY NAME. Every top-level def transitively referenced from a
     ``@maya_command`` def (to fixpoint), including imports nested INSIDE those
     bodies -- a deferred import still fires when the function is called.

WHAT IS EXEMPT. A bundle never invokes a demo or a test, so their bodies (and
helpers only they reach) are out of scope: ``@maya_test`` defs, ``@maya_demo``
defs, and the reserved bare ``def demo`` that ``node_setups.find_demos`` unions
in (LAST top-level binding, accepted when it is a self-first instance def OR a
cls-first/@classmethod factory). Exemption is expressed by NOT making them
roots -- so a demo/test that a command actually calls is still scanned.

WHAT SOURCE IS SCANNED. NOT the .mpn payload verbatim -- the source a bundle
ACTUALLY gets. ``native/spec/mpn_spec_adapter.py`` runs
``node_setups.merge_type_default(methods_source, native_type)`` BEFORE codegen,
which APPENDS ``_common/node_setups/<type>.py`` whenever the template has no
self-first ``def setup`` of its own; live nodes are seeded identically by
``MPyNode._populate_methods_source``. That appended setup is itself a
``@maya_command``, so a template with no command of its own acquires one in the
bundle. This tool applies the SAME merge and walks the merged source, then tags
every hit with WHERE it came from -- ``template`` (the .mpn's own methods
source) or ``seeded`` (the merge-appended per-type default) -- because the fix
differs: the first is edited in the template, the second in
``_common/node_setups/<Type>.py``.

Only a template that declares no ``@maya_command`` even AFTER the merge emits no
dispatch module, and only that one is reported SKIPPED.

SKIPPED IS NOT UNSCANNED. Such a template has no command, so nothing is
reachable -- but its MODULE-SCOPE imports are still walked and reported LATENT.
``build_methods_namespace`` execs the WHOLE source before it looks up anything,
so the day the template (or the per-type default merged into it) acquires a
single ``@maya_command``, every module-scope mpynode import becomes fatal with
no edit to the import itself -- which is exactly how 13 templates went from
"SKIPPED, clean" to broken when the merge was taken into account. Def-LOCAL
imports in a command-less template are deliberately not reported: nothing can
reach them, and a demo/test-local import is exempt anyway -- moving an import
inside the def that needs it is the escape hatch for a template that genuinely
wants mpynode when run interpreted.

Pure stdlib + ast, plus ``node_setups`` itself (pure filesystem + ast; loaded
without importing Maya). Runs under plain python3 and under mayapy. Never
imports or execs the scanned source. Exit 0 = every template clean, 1 = at least
one dirty or latent, 2 = a template could not be read/parsed or the merge helper
could not be loaded.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
import sys
import types


# ---------------------------------------------------------------------------
# The merge helper, loaded WITHOUT Maya
# ---------------------------------------------------------------------------

def load_node_setups(root):
    """``mpynode._common.node_setups`` (the module that owns THE merge rule), or
    None if it cannot be loaded.

    ``mpynode/_common/__init__.py`` eagerly imports ``util``, which imports
    ``maya.cmds`` -- fatal under plain python3. ``node_setups`` and the
    ``maya_command`` module it needs are pure ast/stdlib, so on that failure the
    parent packages are stubbed with the real ``__path__`` and the two pure
    modules are loaded through them. Under mayapy the plain import wins and no
    stub is installed."""
    try:
        from mpynode._common import node_setups
        return node_setups
    except Exception:
        pass
    pkg = os.path.join(root, "scripts", "mpynode")
    if not os.path.isdir(pkg):
        return None
    for name, path in (
            ("mpynode", pkg),
            ("mpynode._common", os.path.join(pkg, "_common")),
            ("mpynode._common.methods", os.path.join(pkg, "_common", "methods"))):
        if name in sys.modules:
            continue
        stub = types.ModuleType(name)
        stub.__path__ = [path]
        sys.modules[name] = stub
    try:
        return importlib.import_module("mpynode._common.node_setups")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Decorator / def classification (mirrors _common/methods/maya_command.py)
# ---------------------------------------------------------------------------

def _has_marker(fn, marker):
    """True if ``fn`` carries a ``marker`` decorator, bare or parameterized.
    Mirrors maya_command._decorator_is_marker (literal Name, or Attribute whose
    attr matches -- an aliased ``@mc`` is invisible to the real detector too)."""
    for dec in (getattr(fn, "decorator_list", None) or []):
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == marker:
            return True
        if isinstance(target, ast.Attribute) and target.attr == marker:
            return True
    return False


def _named_decorator(fn, name):
    return any(
        isinstance(d, ast.Name) and d.id == name
        for d in (getattr(fn, "decorator_list", None) or []))


def _is_factory_def(fn):
    """cls-first or @classmethod. Mirrors maya_command._is_factory_def."""
    if _named_decorator(fn, "classmethod"):
        return True
    pos = (getattr(fn.args, "posonlyargs", None) or []) + (fn.args.args or [])
    return bool(pos) and pos[0].arg == "cls"


def _is_instance_def(fn):
    """self-first FunctionDef with no @classmethod/@staticmethod.
    Mirrors maya_command._is_instance_def."""
    if not isinstance(fn, ast.FunctionDef):
        return False
    for dec in (getattr(fn, "decorator_list", None) or []):
        nm = dec.id if isinstance(dec, ast.Name) else getattr(dec, "attr", None)
        if nm in ("classmethod", "staticmethod"):
            return False
    pos = (getattr(fn.args, "posonlyargs", None) or []) + (fn.args.args or [])
    return bool(pos) and pos[0].arg == "self"


def _accept_demo_hook(fn):
    """node_setups._accept_demo_hook: instance def OR factory def."""
    return _is_instance_def(fn) or _is_factory_def(fn)


def _reserved_demo(tree):
    """The reserved bare ``def demo``, mirroring node_setups._find_hook: the LAST
    top-level ``def demo`` of any kind, discarded when a later module-level
    assignment rebinds the name, then gated by _accept_demo_hook."""
    last = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "demo":
            last = node
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "demo"
                for t in node.targets):
            last = None
        elif (isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "demo"):
            last = None
    if last is None or not _accept_demo_hook(last):
        return None
    return last


# ---------------------------------------------------------------------------
# Import inspection
# ---------------------------------------------------------------------------

def _import_roots(node):
    """Top-level package name(s) an import statement binds against, plus a
    marker for a relative import (which cannot resolve in an exec'd namespace
    that has no package)."""
    if isinstance(node, ast.Import):
        return [a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return ["." * node.level + (node.module or "")]
        return [(node.module or "").split(".")[0]]
    return []


def _is_mpynode_dep(node):
    """The offending root if this import reaches mpynode (or is relative and so
    cannot resolve at all), else None."""
    for root in _import_roots(node):
        if root.startswith(".") or root.startswith("mpynode"):
            return root
    return None


def _module_scope_imports(tree):
    """Import statements that ``build_methods_namespace``'s exec runs -- i.e.
    everything not inside a def/lambda. if/try/with/for/class bodies at module
    level DO exec, so they are walked."""
    out = []

    def walk(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                out.append(node)
                continue
            for field in ("body", "orelse", "finalbody"):
                sub = getattr(node, field, None)
                if isinstance(sub, list):
                    walk(sub)
            for handler in (getattr(node, "handlers", None) or []):
                walk(handler.body)

    walk(tree.body)
    return out


def _imports_within(node):
    """Every import anywhere inside a def (nested defs included -- a deferred
    import in a closure still fires when that closure is called)."""
    return [n for n in ast.walk(node)
            if isinstance(n, (ast.Import, ast.ImportFrom))]


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------

def _top_level_bindings(tree):
    """Module-level def/class name -> node. LAST binding wins, matching what
    exec leaves in the namespace."""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            out[node.name] = node
    return out


def _referenced_names(node, candidates):
    """Names in ``candidates`` LOADed anywhere inside ``node``. Any load counts,
    not just a call: passing a helper as a callback reaches it just the same."""
    hits = []
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
                and sub.id in candidates):
            hits.append(sub.id)
    return hits


def _reach(roots, bindings):
    """Fixpoint closure over ``roots``. Returns (ordered names, parent map)."""
    parent = {}
    order = []
    stack = []
    for name in roots:
        if name in bindings and name not in parent:
            parent[name] = None
            order.append(name)
            stack.append(name)
    while stack:
        name = stack.pop(0)
        for ref in _referenced_names(bindings[name], bindings):
            if ref not in parent:
                parent[ref] = name
                order.append(ref)
                stack.append(ref)
    return order, parent


def _chain(name, parent):
    path = [name]
    while parent.get(name) is not None:
        name = parent[name]
        path.append(name)
    return " <- ".join(path)


# ---------------------------------------------------------------------------
# Per-template scan
# ---------------------------------------------------------------------------

def _source_of(src_lines, node):
    """The offending statement text, collapsed to one line."""
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    text = " ".join(l.strip() for l in src_lines[start:end])
    return " ".join(text.split())


def scan_source(src, seed_offset=None):
    """Scan one MERGED methods source. Returns a dict describing the verdict.

    ``seed_offset`` is the number of leading lines of ``src`` that came from the
    template's own methods source; everything past it is the merge-appended
    per-type default. None = no merge happened, so every line is the template's
    own. Used only to tag origin -- it does not change what is scanned."""
    result = {
        "commands": [], "seeded_commands": [], "demos": [], "tests": [],
        "reserved_demo": None, "reachable": [], "hits": [], "latent": [],
        "status": None, "error": None,
    }
    if not src or not src.strip():
        result["status"] = "SKIPPED"
        return result
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError) as exc:
        result["status"] = "ERROR"
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
        return result

    src_lines = src.splitlines()
    bindings = _top_level_bindings(tree)

    def origin_of(lineno):
        """('template'|'seeded', line number within that origin's own file)."""
        if seed_offset is None or lineno <= seed_offset:
            return "template", lineno
        return "seeded", lineno - seed_offset

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _has_marker(node, "maya_command"):
            # detect_commands drops an async def with a warning; so do we.
            if isinstance(node, ast.FunctionDef):
                result["commands"].append(node.name)
                if origin_of(node.lineno)[0] == "seeded":
                    result["seeded_commands"].append(node.name)
            continue
        if _has_marker(node, "maya_demo"):
            result["demos"].append(node.name)
        elif _has_marker(node, "maya_test"):
            result["tests"].append(node.name)

    if "demo" not in result["demos"] and _reserved_demo(tree) is not None:
        result["reserved_demo"] = "demo"

    def module_scope_hits(chain):
        out = []
        for node in _module_scope_imports(tree):
            root = _is_mpynode_dep(node)
            if not root:
                continue
            where, own_line = origin_of(node.lineno)
            out.append({"where": "module-scope", "root": root,
                        "lineno": node.lineno, "origin": where,
                        "origin_lineno": own_line,
                        "text": _source_of(src_lines, node),
                        "chain": chain})
        return out

    if not result["commands"]:
        # THE SKIPPED-BUCKET GAP. No command post-merge means no dispatch
        # module ships today and nothing is reachable -- but the module-scope
        # imports still exec ahead of any lookup, so they turn fatal the moment
        # this template or its per-type default grows one @maya_command.
        result["latent"] = module_scope_hits(
            "<module scope: LATENT -- fires unconditionally once this template "
            "has any command>")
        result["status"] = "SKIPPED"
        return result

    order, parent = _reach(result["commands"], bindings)
    result["reachable"] = [n for n in order if n not in result["commands"]]

    hits = module_scope_hits("<module scope: execs before any command>")
    for name in order:
        for node in _imports_within(bindings[name]):
            root = _is_mpynode_dep(node)
            if root:
                where, own_line = origin_of(node.lineno)
                hits.append({"where": "def %s" % name, "root": root,
                             "lineno": node.lineno, "origin": where,
                             "origin_lineno": own_line,
                             "text": _source_of(src_lines, node),
                             "chain": _chain(name, parent)})
    hits.sort(key=lambda h: h["lineno"])
    result["hits"] = hits
    result["status"] = "DIRTY" if hits else "CLEAN"
    return result


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def iter_templates(templates_root):
    for dirpath, _dirs, files in os.walk(templates_root):
        if "template.mpn" in files:
            yield os.path.join(dirpath, "template.mpn")


def default_root():
    env = os.environ.get("MPYNODE_ROOT")
    if env and os.path.isdir(os.path.join(env, "templates")):
        return env
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None,
                    help="repo root (default: $MPYNODE_ROOT, else ../ of this "
                         "file)")
    ap.add_argument("--only", action="append", default=None,
                    help="scan only templates whose path contains this string "
                         "(repeatable)")
    ap.add_argument("--quiet", action="store_true",
                    help="print dirty templates and the summary only")
    args = ap.parse_args(argv)

    root = args.root or default_root()
    templates_root = os.path.join(root, "templates")
    if not os.path.isdir(templates_root):
        sys.stderr.write("no templates dir at %s\n" % templates_root)
        return 2

    # Hard requirement, not a soft degrade: without the merge this scan is the
    # misleading verbatim one it replaces, and it would exit 0 on the very class
    # of defect it exists to catch.
    node_setups = load_node_setups(root)
    if node_setups is None:
        sys.stderr.write(
            "cannot load mpynode._common.node_setups from %s -- the merge that "
            "mpn_spec_adapter applies cannot be reproduced, so this scan would "
            "be misleading. Set --root/$MPYNODE_ROOT to the repo root.\n" % root)
        return 2
    setups_root = os.path.join(root, "scripts", "mpynode", "_common",
                               "node_setups")

    clean, dirty, skipped, errors = [], [], [], []
    seeded_dirty = []
    latent = []

    def print_hits(hits, seed_file):
        for h in hits:
            print("      L%-5d %-14s %s" % (h["lineno"], h["where"], h["text"]))
            print("             via %s   [root: %s]" % (h["chain"], h["root"]))
            if h["origin"] == "seeded":
                print("             from SEEDED %s:%d  (fix the shared "
                      "per-type setup)" % (seed_file, h["origin_lineno"]))
            else:
                print("             from TEMPLATE methods_source:%d  (fix the "
                      "template)" % h["origin_lineno"])

    for path in sorted(iter_templates(templates_root)):
        rel = os.path.relpath(os.path.dirname(path), templates_root)
        if args.only and not any(o in rel for o in args.only):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, IOError, ValueError) as exc:
            errors.append(rel)
            print("=== %s\n    ERROR reading .mpn: %s" % (rel, exc))
            continue
        data = payload.get("data", payload)
        native_type = data.get("native_type") or ""
        own_src = data.get("methods_source") or ""

        # THE merge, exactly as mpn_spec_adapter.spec_from_mpn_payload does it
        # (and as MPyNode._populate_methods_source does at node-create time).
        merged = node_setups.merge_type_default(own_src, native_type,
                                                root=setups_root)
        seed_offset = None
        seed_file = None
        if merged != own_src:
            type_src = node_setups.setup_source_for_type(native_type,
                                                         root=setups_root) or ""
            # merge_type_default APPENDS type_src verbatim, so the seeded part is
            # exactly the last len(type_src) lines of merged.
            seed_offset = len(merged.splitlines()) - len(type_src.splitlines())
            seed_file = os.path.join("_common", "node_setups",
                                     native_type + ".py")

        res = scan_source(merged, seed_offset=seed_offset)
        status = res["status"]

        if status == "ERROR":
            errors.append(rel)
        elif status == "DIRTY":
            dirty.append(rel)
            if all(h["origin"] == "seeded" for h in res["hits"]):
                seeded_dirty.append(rel)
        elif status == "CLEAN":
            clean.append(rel)
        else:
            skipped.append(rel)
            if res["latent"]:
                latent.append(rel)

        if (args.quiet and status not in ("DIRTY", "ERROR")
                and not res["latent"]):
            continue

        print("=== %s   [%s]" % (rel, native_type or "?"))
        if seed_file:
            print("    merged   : + %s (template has no def setup of its own; "
                  "its lines start at L%d)" % (seed_file, seed_offset + 1))
        if status == "ERROR":
            print("    ERROR parsing merged methods source: %s" % res["error"])
            print("")
            continue
        if status == "SKIPPED":
            print("    SKIPPED -- no @maya_command after the merge "
                  "(no dispatch module is emitted)")
            if res["latent"]:
                print("    LATENT (%d) -- inert today, fatal the moment this "
                      "template has any command" % len(res["latent"]))
                print_hits(res["latent"], seed_file)
            print("")
            continue
        exempt = list(res["demos"]) + list(res["tests"])
        if res["reserved_demo"]:
            exempt.append("demo (reserved)")
        cmds = ["%s%s" % (c, " (seeded)" if c in res["seeded_commands"] else "")
                for c in res["commands"]]
        print("    commands : %s" % ", ".join(cmds))
        print("    reached  : %s" % (", ".join(res["reachable"]) or "-"))
        print("    exempt   : %s" % (", ".join(exempt) or "-"))
        if status == "CLEAN":
            print("    CLEAN")
        else:
            print("    DIRTY (%d)" % len(res["hits"]))
            print_hits(res["hits"], seed_file)
        print("")

    print("-" * 72)
    print("clean   (%d): %s" % (len(clean), ", ".join(clean) or "-"))
    print("dirty   (%d): %s" % (len(dirty), ", ".join(dirty) or "-"))
    print("skipped (%d): %s" % (len(skipped), ", ".join(skipped) or "-"))
    if errors:
        print("errors  (%d): %s" % (len(errors), ", ".join(errors)))
    print("  of the dirty, seed-only (%d): %s"
          % (len(seeded_dirty), ", ".join(seeded_dirty) or "-"))
    print("  of the skipped, latent module-scope mpynode imports (%d): %s"
          % (len(latent), ", ".join(latent) or "-"))
    print("SCOPE: the source scanned is POST-MERGE -- what a bundle actually "
          "gets. Each .mpn's")
    print("       methods_source is run through "
          "node_setups.merge_type_default(src, native_type),")
    print("       mirroring mpn_spec_adapter.spec_from_mpn_payload, so a "
          "template that acquires a")
    print("       @maya_command only from the seeded "
          "_common/node_setups/<Type>.py is scanned too.")
    print("       Each hit is tagged TEMPLATE (fix the .mpn) or SEEDED (fix the "
          "shared setup).")
    print("       A SKIPPED template is still walked for MODULE-SCOPE mpynode "
          "imports: those exec")
    print("       ahead of any lookup, so they turn fatal the moment it "
          "acquires a command. Move")
    print("       such an import inside the def that needs it.")

    if errors:
        return 2
    return 1 if (dirty or latent) else 0


if __name__ == "__main__":
    sys.exit(main())
