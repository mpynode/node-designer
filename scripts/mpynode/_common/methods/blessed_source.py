import ast
import importlib.util
from mpynode._common.interface.api_methods import Transpile

def resolve_method_source(spec):
    """Return (abspath, lineno) for a blessed MethodSpec's source def, or None.
    Prefers the transpiled free fn for Transpile specs (the golden math), else
    the interpreted runtime adapter. Pure static: importlib.util.find_spec +
    ast -- NEVER imports the target (no user code runs, adapter deps stay
    unloaded)."""
    lower = getattr(spec, "lower", None)
    if isinstance(lower, Transpile):
        ref = lower.free_fn
    else:
        ref = getattr(spec, "runtime", None)
    if not ref or ":" not in ref:
        return None
    mod_name, _, qual = ref.partition(":")
    if not mod_name or not qual:
        return None
    try:
        found = importlib.util.find_spec(mod_name)
    except (ImportError, ValueError, AttributeError, ModuleNotFoundError):
        return None
    if found is None or not found.origin or not found.origin.endswith(".py"):
        return None
    path = found.origin
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        tree = ast.parse(src)
    except (OSError, SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == qual:
            return (path, node.lineno)
    return None
