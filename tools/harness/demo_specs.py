"""Demo discovery for the audit harnesses (import-safe, no side effects).

Standalone AST mirror of ``node_setups.find_demos``: the orchestrators run under
plain python3, so they cannot import mpynode/maya. Lives in its own module
because ``run_all.py`` has no ``__main__`` guard -- importing IT to reuse the
parser would run a whole audit as a side effect.
"""
import ast
import json
import os


def load_templates(harness_dir, root):
    """``templates.json``, with each row's ``node_name`` REFRESHED from its
    ``.mpn``.

    The manifest duplicates ``node_name`` from the template payload, and the
    payload is the thing that actually ships -- so a rename in the generator
    left the manifest stale and pointing two rows at one type name. That is not
    a loud failure: ``mega_plugin`` dedups by ``node_name`` and silently SKIPS
    the second row, and per-template builds emit two artifacts registering the
    same Maya type, where only one can load. Reading the name back from the
    .mpn keeps the payload the single source of truth."""
    with open(os.path.join(harness_dir, "templates.json")) as f:
        rows = json.load(f)
    for t in rows:
        mpn = t.get("mpn")
        if not mpn:
            continue
        path = mpn if os.path.isabs(mpn) else os.path.join(root, mpn)
        try:
            with open(path) as f:
                data = (json.load(f) or {}).get("data") or {}
        except Exception:
            continue
        if data.get("node_name"):
            t["node_name"] = data["node_name"]
    return rows


def mpn_methods_source(mpn_path):
    """The template's methods_source string (under data/, with fallbacks)."""
    try:
        d = json.load(open(mpn_path))
    except Exception:
        return ""
    if isinstance(d.get("data"), dict) and isinstance(
            d["data"].get("methods_source"), str):
        return d["data"]["methods_source"]
    for k in ("methods_source", "methodsSource", "_methodsSource"):
        if isinstance(d.get(k), str):
            return d[k]
    return ""


def demo_specs_for(mpn_path):
    """Every demo in the template's methods_source as (func_name, label), in
    source order: every top-level def decorated with @maya_demo (bare or called,
    honoring a `label=`/positional label) UNIONED with the reserved `def demo`
    when not already decorated.

    Returns [] on a parse error or when there is no demo (caller falls back to
    the default/first demo with the templates.json label)."""
    src = mpn_methods_source(mpn_path)
    if not src.strip():
        return []
    try:
        tree = ast.parse(src)
    except Exception:
        return []
    out, seen = [], set()

    def _label(fn):
        for dec in fn.decorator_list:
            name = label = None
            if isinstance(dec, ast.Name):
                name = dec.id
            elif isinstance(dec, ast.Attribute):
                name = dec.attr
            elif isinstance(dec, ast.Call):
                f = dec.func
                name = f.id if isinstance(f, ast.Name) else getattr(
                    f, "attr", None)
                for kw in (dec.keywords or []):
                    if kw.arg == "label" and isinstance(kw.value, ast.Constant):
                        label = kw.value.value
                for a in dec.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        label = a.value
            if name == "maya_demo":
                return True, label
        return False, None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_demo, label = _label(node)
            if is_demo and node.name not in seen:
                seen.add(node.name)
                out.append((node.name, label or node.name, node.lineno))
    if "demo" not in seen:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "demo":
                out.append(("demo", "Run demo", node.lineno))
    out.sort(key=lambda t: t[2])
    return [(fn, lbl) for fn, lbl, _ in out]
