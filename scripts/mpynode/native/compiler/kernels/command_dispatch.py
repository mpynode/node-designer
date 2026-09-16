"""command_dispatch -- emit a real ``MPxCommand`` into the node's OWN bundle for
every ``@maya_command``, so a compile produces ONE plug-in.

Before this, an arbitrary ``@maya_command`` shipped as a SIBLING Python plug-in
(``<type>_commands.py``) that had to be loaded alongside the ``.bundle``. The
command bodies are host orchestration (``createNode`` / ``curve`` / numpy /
``mpynode`` imports) and cannot become node math, so the body still runs in
Python -- but the COMMAND is now a genuine C++ ``MPxCommand`` registered by the
bundle's own ``initializePlugin``. One artifact, real ``MSyntax`` flags, real
undo. The node's ``compute`` is untouched and stays pure C++ (TRANSPILER.md's
rule scopes itself to compute; commands are explicitly carved out).

Distinct from ``command_codegen``, which holds two HAND-WRITTEN C++ command
bodies (``createMeshRegion`` / ``setMeshRegion``) selected by name match. Those
still win where they apply -- they need no Python at all. This module is the
general fallback for every other command.

FOUR measured constraints shape the generated code; each was a real failure:

1. **Nothing Python may run at ``initializePlugin``.** If it does and ``mpynode``
   is unimportable, the node type silently fails to register: ``loadPlugin``
   returns None without raising, saved nodes open as ``unknown`` (data loss),
   and in a MERGED bundle the first failing register hook aborts the whole
   plug-in, taking every other node with it. So the Python side is bootstrapped
   LAZILY, inside ``doIt``, and registration is pure C++ string work.

2. **``executePythonCommand``'s ``undoEnabled`` defaults to FALSE**, and the
   default silently corrupts the undo queue: the command's own mutations become
   permanently un-undoable while one Ctrl+Z reverts an unrelated earlier
   operation. It is passed explicitly here, and the call is wrapped in an
   ``undoInfo -openChunk/-closeChunk`` pair so the whole command is ONE undo.

3. **``isUndoable``/``undoIt`` must NOT be implemented.** C++ cannot reverse an
   arbitrary Python body; a no-op ``undoIt`` makes the first Ctrl+Z do nothing
   at all. Atomicity comes from the chunk instead. Honest claim: undoable iff
   the body mutates only through ``maya.cmds`` (raw OpenMaya writes escape undo
   -- unchanged from the Python companion).

4. **``MSyntax`` flag types cannot be guessed.** Inferring from a ``None``
   default and falling back to ``kString`` was measured to decompose a node name
   character by character, and mapping "flag absent" to an empty value silently
   built a zero-rider spine with NO error. Types come from an explicit source
   (annotation, then default literal); anything left unknown FAILS the compile
   by name. An absent flag is never materialised -- it is simply omitted from
   the call so Python's own default applies.

FOUR COMMAND KINDS reach ``_dispatch`` (``_KINDS`` maps command name -> kind):

* ``instance`` -- self-first. Binds an EXISTING node: the named object, else the
  first selected one. Errors if neither is available.
* ``factory``  -- ``cls``-first / ``@classmethod``. Binds the proxy CLASS; the
  body creates whatever it wants.
* ``static``   -- ``@staticmethod``. No binding at all.
* ``creates``  -- self-first + ``@maya_command(..., creates=True)``. The
  ``blendShape``/``skinCluster`` shape: the dispatcher CREATES the node, binds it
  as ``self``, and passes the free objects (or the live selection) through as
  ``selection=``. This is what lets the node's existing ``setup`` body double as
  a one-call create command with no second function -- ``invoke_command``'s
  ``fn(wrapper, ...)`` invokes a self-first body verbatim.

  ``self`` is only the body's first parameter; nothing about it requires the node
  to pre-exist. Both callers run the same create-then-configure order -- the UI
  creates from the gallery, the command creates in ``_dispatch``. ``setup``
  deliberately stays the primitive because create+configure is derivable from
  configure and the reverse is impossible, and "re-run setup on an existing
  node" is a shipped feature.

ENCODING NOTE. Everything crossing the C++/Python boundary is base64, and every
result is separator-delimited rather than JSON. This is deliberate: the payload
is arbitrary user source, the call is Python text built by C++ which is itself
built by Python, and hand-escaping quotes/backslashes through three layers is
where this kind of codegen goes wrong. base64 is pure ASCII needing no escaping,
and splitting on control characters needs no parser on the C++ side.
"""
from __future__ import annotations

import ast
import base64
import re
import sys
import textwrap
from typing import List

_VALID_COMMAND_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Python type -> (MSyntax arg type, MArgDatabase getter, multi-use)
_FLAG_TYPES = {
    "str":         ("MSyntax::kString", "asString", False),
    "int":         ("MSyntax::kLong", "asInt", False),
    "float":       ("MSyntax::kDouble", "asDouble", False),
    "bool":        ("MSyntax::kBoolean", "asBool", False),
    "list[str]":   ("MSyntax::kString", "asString", True),
    "list[int]":   ("MSyntax::kLong", "asInt", True),
    "list[float]": ("MSyntax::kDouble", "asDouble", True),
}

COMMAND_INCLUDES = (
    "maya/MPxCommand.h",
    "maya/MSyntax.h",
    "maya/MArgDatabase.h",
    "maya/MArgList.h",
    "maya/MGlobal.h",
    "maya/MString.h",
    "maya/MStringArray.h",
    "maya/MIntArray.h",
    "maya/MDoubleArray.h",
    "maya/MSelectionList.h",
    "string",
    "vector",
    "sstream",
)


class CommandSpecError(ValueError):
    """A command cannot be lowered to an MPxCommand as authored."""


# ---- Signature -> flag spec -----------------------------------------------

def _dedent_def(src: str) -> str:
    """``body_src`` is captured from a class body, so it arrives indented."""
    try:
        ast.parse(src)
        return src
    except SyntaxError:
        return textwrap.dedent(src)


def _annotation_type(node) -> str:
    """Normalise an annotation AST to a _FLAG_TYPES key, or '' if unusable."""
    if node is None:
        return ""
    try:
        txt = ast.unparse(node)
    except Exception:                                           # noqa: BLE001
        return ""
    t = txt.replace(" ", "").lower().replace("typing.", "")
    # A parameter defaulting to None is honestly Optional[X] / X | None; the
    # flag type is X either way (absence is carried by isFlagSet, not by the
    # annotation), so unwrap it rather than force templates to mistype.
    m = re.match(r"^optional\[(.+)\]$", t)
    if m:
        t = m.group(1)
    else:
        parts = [p for p in t.split("|") if p and p != "none"]
        if len(parts) == 1 and "|" in t:
            t = parts[0]
    m = re.match(r"^(?:list|sequence|tuple|iterable)\[(\w+)(?:,\.\.\.)?\]$", t)
    if m:
        inner = m.group(1)
        if inner == "bool":
            inner = "int"
        return "list[%s]" % inner if inner in ("str", "int", "float") else ""
    return t if t in ("str", "int", "float", "bool") else ""


def _default_type(node) -> str:
    """Infer a flag type from a DEFAULT literal, or '' when it carries none.

    ``None`` deliberately yields '' -- it is the most common default in the
    corpus and says nothing about the parameter's type. Guessing here is what
    produced the measured silent-wrong-answer failures.
    """
    if node is None:
        return ""
    try:
        val = ast.literal_eval(node)
    except Exception:                                           # noqa: BLE001
        return ""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "str"
    if isinstance(val, (list, tuple)) and val:
        kinds = {type(x).__name__ for x in val}
        if kinds <= {"str"}:
            return "list[str]"
        if kinds <= {"int", "bool"}:
            return "list[int]"
        if kinds <= {"int", "float", "bool"}:
            return "list[float]"
    return ""


def _short_name(long_name: str, taken: set) -> str:
    """A unique short flag.

    MSyntax accepts a DUPLICATE short name SILENTLY and the second flag then
    becomes unreachable by its short form (measured: it collides on metaballs'
    axis/additive and spine's rider_type/rider_prefix), so uniqueness is
    enforced here rather than discovered at runtime.
    """
    words = [w for w in re.split(r"[^A-Za-z0-9]+", long_name) if w]
    cands = []
    if words:
        cands.append("".join(w[0] for w in words[:3]).lower())
        cands.append(words[0][:1].lower())
        cands.append(words[0][:2].lower())
        cands.append(words[0][:3].lower())
    base = re.sub(r"[^A-Za-z0-9]", "", long_name).lower() or "f"
    cands += [base[:1], base[:2], base[:3], base[:4]]
    for c in cands:
        if c and c not in taken and re.match(r"^[A-Za-z]\w*$", c):
            taken.add(c)
            return c
    i = 1
    while True:
        c = "%s%d" % (base[:2] or "f", i)
        if c not in taken:
            taken.add(c)
            return c
        i += 1


def flag_spec_for(cmd: dict) -> List[dict]:
    """``[{param, long, short, type, multi, required}, ...]`` for one command.

    Raises :class:`CommandSpecError` naming any parameter whose flag type cannot
    be established -- never guesses.
    """
    src = _dedent_def(cmd.get("body_src") or "")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise CommandSpecError(
            "%s: could not parse the command source (%s)"
            % (cmd.get("name"), exc)) from exc

    fn = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == cmd.get("func_name"):
            fn = node
            break
    if fn is None:
        raise CommandSpecError(
            "%s: def %r not found in its own source"
            % (cmd.get("name"), cmd.get("func_name")))

    a       = fn.args
    creates = bool(cmd.get("creates"))
    if (a.vararg or a.kwarg) and not creates:
        raise CommandSpecError(
            "%s: *args/**kwargs cannot be expressed as MSyntax flags"
            % cmd.get("name"))
    # A create command is written on the reserved ``setup`` hook, whose contract
    # is ``setup(self, selection=None, *args, **kwargs)``. The tail is the hook's
    # forward-compat slack, not command parameters, so SKIP it rather than reject.
    # Every other named parameter still becomes a flag (cmds.spine(riderCount=5)).

    pos = list(a.posonlyargs) + list(a.args)
    if pos and pos[0].arg in ("self", "cls"):
        pos = pos[1:]
    defaults     = list(a.defaults)
    pos_defaults = [None] * (len(pos) - len(defaults)) + defaults

    params = [(arg, d, d is None) for arg, d in zip(pos, pos_defaults)]
    params += [(arg, d, d is None)
               for arg, d in zip(a.kwonlyargs, a.kw_defaults)]

    explicit = cmd.get("flags") or {}
    out: List[dict] = []
    taken = {"h"}                       # -h is Maya's own help flag
    unknown: List[str] = []
    for arg, dflt, required in params:
        pname = arg.arg
        if creates and pname == "selection":
            # The dispatcher fills ``selection`` from the command's free objects
            # (the blendShape/skinCluster shape). Also exposing it as a flag
            # would give two ways to say the same thing, and the untyped
            # ``selection=None`` default carries no MSyntax type anyway.
            continue
        ftype = (str(explicit.get(pname) or "").strip()
                 or _annotation_type(arg.annotation)
                 or _default_type(dflt))
        if ftype not in _FLAG_TYPES:
            unknown.append(pname)
            continue
        out.append({
            "param":    pname,
            "long":     pname,
            "short":    _short_name(pname, taken),
            "type":     ftype,
            "multi":    _FLAG_TYPES[ftype][2],
            "required": required,
        })
    if unknown:
        raise CommandSpecError(
            "%s: cannot determine an MSyntax flag type for parameter(s) %s. "
            "Annotate them (e.g. `def %s(self, %s: list[str])`) -- a default of "
            "None carries no type, and guessing was measured to fail silently."
            % (cmd.get("name"), ", ".join(repr(u) for u in unknown),
               cmd.get("func_name"), unknown[0]))
    return out


# ---- The setup-safe contract (injected into the bundle AND used by the gate) --

# Wrapper members a setup body may reach for that a COMPILED node cannot honor,
# mapped to why. Each exists on the interpreted MPyNode but is backed by a plug
# the compile never emits, so forwarding it would write nowhere and silently
# succeed. ONE table, injected into the generated module as _COMPILED_UNSUPPORTED
# and read by create_command_blockers below, so the runtime refusal and the
# compile-time rejection can never drift apart.
COMPILED_UNSUPPORTED = {
    "set_variable":
        "stored variables are const-folded into C++ at compile time; a "
        "compiled node has no _storedVarNames/_storedVarsData plug to write to",
    "get_variable":  "same as set_variable -- no stored-variable plugs exist",
    "get_variables": "same as set_variable -- no stored-variable plugs exist",
    "set_variables": "same as set_variable -- no stored-variable plugs exist",
    "get_variable_names":
        "same as set_variable -- no stored-variable plugs exist",
    "add_variable":    "same as set_variable -- no stored-variable plugs exist",
    "remove_variable": "same as set_variable -- no stored-variable plugs exist",
    "get_input_attr_map":
        "attributes are baked into C++ initialize(); there is no _inputAttrs plug",
    "get_output_attr_map":
        "attributes are baked into C++ initialize(); there is no _outputAttrs plug",
    "add_input_attr":
        "attributes are baked into C++ initialize() and cannot be added at runtime",
    "add_output_attr":
        "attributes are baked into C++ initialize() and cannot be added at runtime",
    "get_compute_expression":
        "the compute is C++; there is no _computeSource plug",
    "get_init_expression": "there is no _initSource plug on a compiled node",
    "set_compute_expression":
        "the compute is C++ and cannot be reassigned at runtime",
    # The mPyBlendShape authoring surface. Every one of these ends in
    # rebuild(), which calls get_compute_expression() to derive shapeSlot, so
    # they inherit that entry's problem rather than having one of their own --
    # listed by name so the refusal names the method the user actually called
    # instead of surfacing as a bare AttributeError from the proxy.
    "add_target":
        "adding a blend-shape target rebuilds the delta tables, which needs "
        "get_compute_expression -- there is no _computeSource plug",
    "add_target_from_offsets": "same as add_target -- the rebuild cannot run",
    "load_target":             "same as add_target -- the rebuild cannot run",
    "load_shapes":             "same as add_target -- the rebuild cannot run",
    "rebuild":
        "rebuilding the blend-shape tables derives shapeSlot from the compute "
        "source, and the compute is C++ -- there is no _computeSource plug",
}

# Modules whose contents are written for an INTERPRETED node. The IMPORT itself
# is harmless -- measured: MPySkinCluster._wire_joints and
# mpy_file.ensure_in_texture_list are pure maya.cmds and bind a compiled node
# fine. What is NOT safe is binding an INSTANCE: MPyBlendShape("<compiled node>")
# does not raise (__new__ misses the registry, __init__ only checks objExists),
# it binds and then reads EMPTY or raises deep inside -- measured
# get_variable_names() -> [], get_input_attr_map() -> {},
# get_compute_expression() -> ValueError on the missing _computeSource plug.
# So the gate keys on the CONSTRUCTION, not the import.
INTERPRETED_ONLY_IMPORTS = ("mpynode.wrappers", "mpynode._api2")

# wrap/wrap_node go through the native-type REGISTRY, which deliberately excludes
# compiled types ("the coexist compiled sibling is intentionally excluded --
# unregistered = hidden from the tree", _node_registry.py). Measured: they return
# None for a compiled node rather than raising, so the body silently no-ops.
_REGISTRY_MODULES = ("mpynode._node_registry", "mpynode")
_REGISTRY_BINDERS = ("wrap", "wrap_node")

# Classmethods that CREATE an interpreted node -- inside a create command that
# already made the compiled one, that is a second, wrong-typed node.
_BINDING_CLASSMETHODS = ("create", "build")

# Every MPyNode subclass under wrappers/ and _api2/ is named MPy<Something>
# (verified exhaustively). A real issubclass() test would drag ``maya`` into this
# module and cost compile_controller its headless testability, so the naming
# convention is what separates a wrapper CLASS from a plain helper function.
_WRAPPER_CLASS = re.compile(r"^MPy[A-Z0-9_]")


def create_command_blockers(cmd: dict) -> List[str]:
    """Reasons ``cmd`` cannot be lowered as a ``creates=True`` command, else [].

    A create command runs its body against a :class:`_CompiledProxy`, not the
    interpreted wrapper. Most setups are already proxy-safe (measured: 13 of 17
    touch nothing but ``get_name``), but two classes of body are not, and both
    fail at RUN time in the user's scene rather than at compile time unless they
    are caught here:

      * ``self.<member>`` for a member with no compiled backing (stored
        variables, the attr maps, the source plugs) -- see COMPILED_UNSUPPORTED.
      * binding an interpreted wrapper INSTANCE (``MPyBlendShape(name)``,
        ``wrap_node(name)``, ``MPyX.create()``). Note this keys on the
        construction, NOT the import: importing the module and calling a
        module-level helper or a pure-cmds staticmethod off it is fine, and two
        shipped setups rely on that.

    Returns reasons rather than raising so ``emit_dispatch_commands`` can report
    every problem in one pass.
    """
    src = _dedent_def(cmd.get("body_src") or "")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []          # flag_spec_for reports the parse failure itself

    # Which local names came from an interpreted-only module?
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == p or mod.startswith(p + ".")
                   for p in INTERPRETED_ONLY_IMPORTS):
                bound.update(a.asname or a.name for a in node.names)
            if mod in _REGISTRY_MODULES:
                bound.update(a.asname or a.name for a in node.names
                             if a.name in _REGISTRY_BINDERS)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if any(a.name == p or a.name.startswith(p + ".")
                       for p in INTERPRETED_ONLY_IMPORTS):
                    bound.add(a.asname or a.name.split(".")[0])

    def _root(node):
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    out, seen = [], set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and node.attr in COMPILED_UNSUPPORTED
                and node.attr not in seen):
            seen.add(node.attr)
            out.append("self.%s is not available on a compiled node (%s)"
                       % (node.attr, COMPILED_UNSUPPORTED[node.attr]))
        if not (bound and isinstance(node, ast.Call)):
            continue
        f, why = node.func, None
        if isinstance(f, ast.Name) and f.id in bound:
            if _WRAPPER_CLASS.match(f.id):
                why = ("constructs the interpreted wrapper %s(...) -- against a "
                       "compiled node it binds but then reads empty or raises "
                       "(no _storedVarNames / _inputAttrs / _computeSource plug)"
                       % f.id)
            elif f.id in _REGISTRY_BINDERS:
                why = ("calls %s(...), which resolves through the native-type "
                       "registry and returns None for a compiled type" % f.id)
        elif isinstance(f, ast.Attribute) and f.attr in _BINDING_CLASSMETHODS:
            r = _root(f)
            if r in bound and _WRAPPER_CLASS.match(r or ""):
                why = ("calls %s.%s(...), which createNode()s an INTERPRETED "
                       "node of the wrong type inside a command that already "
                       "created the compiled one" % (r, f.attr))
        if why and why not in seen:
            seen.add(why)
            out.append(why)
    if out:
        return ["%s: %s" % (cmd.get("name"), r) for r in out]
    return []


# ---- Reachable-mpynode gate ------------------------------------------------

# The gate above deliberately PERMITS an mpynode import, keying on the
# construction instead. Right for an INSTALLED mpynode, blind to the other case:
# a DISTRIBUTED artifact loaded on a machine with Maya but NOT the mpynode
# package, where the same import is a ModuleNotFoundError the first time the
# command runs.
#
# This WAS a stderr warning ("Not fatal -- the command still compiles"), on the
# reasoning that the source is valid Python and the bundle may never leave this
# machine. 13 templates shipped broken straight through it, so the outcome now
# splits on whether the artifact ACTUALLY CARRIES the import:
#
#   * a PAYLOAD is emitted (at least one command still runs Python) -- the
#     import is embedded in the .mll and the compile FAILS, by name. Same
#     reject-or-lower rule the rest of the compiler follows.
#   * NO payload is emitted (command-less, or every command lowered to pure
#     C++) -- nothing embeds the source, so the artifact is correct and refusing
#     it would be a false alarm. Reported as LATENT instead: it execs ahead of
#     every lookup, and turns fatal, the day the node gains one @maya_command
#     with no edit to the import itself. That is exactly how the 13 went from
#     "no command, nothing to break" to broken.
#
# Reachability is the two ways an import actually fires, matching
# tools/scan_command_mpynode_deps.py:
#   1. MODULE SCOPE -- build_methods_namespace execs the WHOLE methods source
#      before it looks up any function, so it runs regardless.
#   2. FROM A COMMAND, BY NAME -- every top-level def transitively referenced
#      from a command def, including imports nested inside those bodies (a
#      deferred import still fires when the function is called).
# A @maya_demo / @maya_test body is not a root: a bundle never invokes one.


def _mpynode_import_root(node) -> str:
    """``"mpynode"`` if this import statement reaches the package, else ''."""
    if isinstance(node, ast.Import):
        roots = [a.name.split(".")[0] for a in node.names]
    elif isinstance(node, ast.ImportFrom) and not node.level:
        roots = [(node.module or "").split(".")[0]]
    else:
        return ""
    return "mpynode" if "mpynode" in roots else ""


def _module_scope_imports(tree) -> list:
    """Imports the namespace exec runs -- everything not inside a def.
    if/try/with/for/class bodies at module level DO exec, so they are
    walked."""
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


def reachable_mpynode_imports(methods_source: str,
                              commands: List[dict]) -> List[str]:
    """One report line per mpynode import a ``@maya_command`` can reach.

    Empty for a clean node. Pass ``commands=[]`` for the LATENT set -- with no
    roots the closure is empty, so what comes back is exactly the module-scope
    imports.
    """
    try:
        tree = ast.parse(methods_source or "")
    except (SyntaxError, ValueError):
        return []                # flag_spec_for reports the parse failure

    bindings = {n.name: n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef))}
    parent, order, queue = {}, [], []
    for c in commands:
        nm = c.get("func_name")
        if nm in bindings and nm not in parent:
            parent[nm] = None
            order.append(nm)
            queue.append(nm)
    while queue:                                        # fixpoint closure
        nm = queue.pop(0)
        for sub in ast.walk(bindings[nm]):
            # Any LOAD counts, not just a call: passing a helper as a callback
            # reaches it just the same.
            if (isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
                    and sub.id in bindings and sub.id not in parent):
                parent[sub.id] = nm
                order.append(sub.id)
                queue.append(sub.id)

    lines = (methods_source or "").splitlines()

    def _text(node):
        end = getattr(node, "end_lineno", node.lineno)
        return " ".join(" ".join(lines[node.lineno - 1:end]).split())

    def _chain(nm):
        path = [nm]
        while parent.get(nm) is not None:
            nm = parent[nm]
            path.append(nm)
        return " <- ".join(path)

    out = []
    for node in _module_scope_imports(tree):
        if _mpynode_import_root(node):
            out.append("L%d module scope (execs before any command is looked "
                       "up): %s" % (node.lineno, _text(node)))
    for nm in order:
        for node in ast.walk(bindings[nm]):
            if (isinstance(node, (ast.Import, ast.ImportFrom))
                    and _mpynode_import_root(node)):
                out.append("L%d in def %s (via %s): %s"
                           % (node.lineno, nm, _chain(nm), _text(node)))
    return out


def report_latent_mpynode_imports(node_type_name: str,
                                  methods_source: str) -> List[str]:
    """Warn about module-scope mpynode imports on a node that ships NO payload.

    Returns the lines reported (empty when clean) so a caller can assert on
    them. Never fatal -- see the section note above: with no payload the import
    is not in the artifact at all, and the compile that produced it is correct.
    """
    latent = reachable_mpynode_imports(methods_source, [])
    if not latent:
        return []
    sys.stderr.write(
        "[command_dispatch] LATENT %s: %d module-scope mpynode import(s). This "
        "node emits no Python payload today (no @maya_command, or every command "
        "lowered to pure C++), so nothing ships them -- but the namespace exec "
        "runs them ahead of every lookup, and the compile FAILS, the day it "
        "gains one command. Vendor the code into the Methods source or move the "
        "import inside a @maya_demo / @maya_test body.\n"
        % (node_type_name, len(latent)))
    for line in latent:
        sys.stderr.write("[command_dispatch]     %s\n" % line)
    return latent


# ---- Native lowering: PURE C++ bodies, no embedded Python ------------------
#
# Everything below this line is the ESCAPE from the base64 payload. A command
# whose body reduces to a bounded, deterministic set of scene effects is
# BACK-TRANSPILED to Maya API C++ and ships with no Python at all; a node whose
# commands ALL lower that way gets no dispatch module, no payload, no
# MGlobal::executePythonCommand -- nothing for a distributed .mll to carry.
#
# The recogniser is deliberately a WHITELIST that refuses on the first statement
# it does not model. An unrecognised command falls through to the Python payload
# and is byte-identical to before, so a miss costs nothing and a MIS-recognition
# (the only dangerous outcome) needs an unmodelled statement to slip past --
# which is why the grammar admits no wildcard.
#
# SHAPE 1 -- ``render_shape_setup``. The ``creates=True`` setup that builds a
# node's display geometry, and the single most common command in the corpus
# (measured over all shipped templates: 6 of 32 commands, spanning mPyMesh x4 +
# mPyNurbsCurve + mPyNurbsSurface):
#
#     @maya_command(creates=True)
#     def setup(self, *args, **kwargs):
#         from maya import cmds as mc
#         name = self.get_name()
#         created = []
#         conn = None
#         try:
#             xform = mc.createNode("transform", name=name + "Render")
#             created.append(xform)
#             shape = mc.createNode("mesh", name=name + "RenderShape",
#                                   parent=xform)
#             src, dst = name + ".outMesh", shape + ".inMesh"
#             mc.connectAttr(src, dst, force=True); conn = (src, dst)
#             mc.sets(shape, edit=True, forceElement="initialShadingGroup")
#             return name
#         except Exception:
#             ...rollback...
#             raise
#
# The try/except is NOT transpiled statement for statement: an MDagModifier /
# MDGModifier already gives exactly that rollback, structurally. What IS checked
# is that the handler can only ever roll back -- it may call nothing but
# disconnectAttr / delete / objExists, may not return, and must end by
# re-raising. Anything else and the shape is refused, because a handler with a
# side effect is not equivalent to a modifier undo.
#
# The node's OWN creation rides a SEPARATE modifier from the body, because the
# Python contract is explicit that it must survive a body failure ("build() owns
# ``self`` -- never delete it on failure ... self is left built-but-unwired").
#
# ---- WHAT IS NOT COVERED, AND WHAT EACH WOULD TAKE -------------------------
#
# Measured over the shipped templates (post type-default merge): 6 of 32
# commands lower, and 5 of the 25 command-bearing templates come out with NO
# payload at all. The remaining 26 fall into four groups, hardest last:
#
# 1. SELECTION-DRIVEN SETUP (~9: mPyDeformer x4, mPySkinCluster x3, uv_layout,
#    two_bone_ik). Same createNode/connect vocabulary, but first they filter the
#    incoming selection ("the deformable geometry", "the transforms") and raise
#    SetupError when it is empty. Needs three grammar additions: reading the
#    command's free objects, a bounded filter vocabulary (nodeType /
#    listRelatives -shapes -type), and a raise-with-message form that lowers to
#    displayError + kFailure. The filters are loops over the selection, so this
#    is the first shape that needs any control flow at all.
#
# 2. ATTR WRITES + MULTI-ELEMENT PLUGS (~5: metaballs add*, procrustes rebind,
#    voxelize). setAttr of a literal, and INDEXED plugs ("%s.radius[%d]"), which
#    _plug_expr deliberately refuses today because the Python string form and
#    MPlug::elementByLogicalIndex diverge. Needs an indexed-plug model plus a
#    setAttr -> MDGModifier::newPlugValue lowering (the mesh-region template in
#    command_codegen already shows that shape).
#
# 3. CALLS OUT TO MODULE-LEVEL HELPERS (~7: spine, patch_relax, dnet, rbf_wrap).
#    The command is a thin wrapper over a top-level def in the Methods source.
#    Nothing lowers until the CALLEE does, so this group is gated on 1 and 2 and
#    on inlining a whitelisted helper -- which is the point where the recogniser
#    stops being a shape matcher and becomes a real transpiler.
#
# 4. UNLOWERABLE, OR BLOCKED ON A DAG CREATE (5: the three procrustes setups,
#    mesh_regions setup, aim_between_matrices). numpy/scipy/KD-tree work and
#    arbitrary host orchestration; aim_between_matrices is additionally an
#    MPxTransform, so it is gated on NATIVE_LOWERABLE_BASES as well. These
#    should KEEP the payload -- the honest end state is "the payload exists
#    only for the nodes that provably need it", not "no payload ever".
#
# Do NOT widen the grammar without extending tools/gate_bundled_commands.py's
# sibling proof: every shape added here must be compiled, loaded, RUN, and
# diffed against the Python body it replaces, exactly as shape 1 was.

# Only a DEPENDENCY-node base may lower today: the emitted C++ creates the
# command's own node with MDGModifier::createNode, which fails outright on a DAG
# type. mPyMesh / mPyNurbsCurve / mPyNurbsSurface -- the whole measured corpus
# for this shape -- are MPxNode, so this costs no coverage; a DAG base simply
# keeps the Python payload until the DAG create is written and TESTED.
NATIVE_LOWERABLE_BASES = ("MPxNode",)

# The types a recognised BODY may createNode -> is that type a SHAPE.
#
# The body's creates all ride an MDagModifier, which is NOT interchangeable with
# cmds.createNode for every type. Both divergences were MEASURED against Maya
# 2026, and neither is caught anywhere downstream:
#
#   * a DG type -- MDagModifier::createNode("decomposeMatrix", ...) comes back
#     kInvalidParameter, so the compiled command FAILS where the
#     cmds.createNode it replaced succeeded;
#   * a SHAPE with no parent -- cmds.createNode("mesh", name=X) names the SHAPE
#     X, while MDagModifier::createNode("mesh", kNullObj) hands back the
#     AUTO-CREATED TRANSFORM. The rename then lands on the transform and the
#     local binds to it, so a later sets() shades the TRANSFORM -- wrong, and
#     SILENTLY so, because MFnSet::addMember accepts it without error.
#
# So the type is a TABLE, not a wildcard, and it holds exactly what the shipped
# corpus creates. A type that is not in it is a MISS -- the command keeps the
# Python body it has today -- never an assumption that it behaves like these.
# Adding one means measuring it against MDagModifier the same way first.
_DAG_CREATE_TYPES = {
    "transform":    False,
    "mesh":         True,
    "nurbsCurve":   True,
    "nurbsSurface": True,
}

# Headers the pure-C++ bodies need, on top of COMMAND_INCLUDES.
NATIVE_COMMAND_INCLUDES = (
    "maya/MDagModifier.h",
    "maya/MDGModifier.h",
    "maya/MFnDagNode.h",
    "maya/MFnDependencyNode.h",
    "maya/MFnSet.h",
    "maya/MPlug.h",
    "maya/MObject.h",
)

_SELF = "\x00self"          # plan-internal marker for "the node this command made"


def _is_str_const(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _kw(call, name):
    """The keyword argument ``name`` of a Call, or None."""
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _is_true(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


class _ShapeRefused(Exception):
    """The body left the recognised grammar -- keep the Python payload."""


class _RenderShapeReader(object):
    """Reduce a ``render_shape_setup`` body to a flat list of scene effects.

    Every method raises :class:`_ShapeRefused` the moment it sees something it
    does not model. Nothing here is best-effort.
    """

    def __init__(self, fn):
        self.fn       = fn
        self.mc       = None   # the ``maya.cmds`` alias in scope
        self.name     = None   # the local bound to self.get_name()
        self.books    = set()  # created=[] / conn=None bookkeeping locals
        self.nodes    = {}     # local -> plan node id
        self.plugs    = {}     # local -> (node id, ".attr")
        self.creates  = []
        self.connects = []
        self.sets     = []
        self.returned = False

    # -- helpers ------------------------------------------------------------

    def _mc_call(self, node, attr):
        """True if ``node`` is a Call of ``<cmds alias>.<attr>(...)``."""
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == attr
                and isinstance(node.func.value, ast.Name)
                and self.mc is not None
                and node.func.value.id == self.mc)

    def _plug_expr(self, node):
        """``<name-or-node-local> + ".attr"`` -> ``(node id, ".attr")``.

        A bare local already bound to a plug (the ``src, dst = ...`` idiom)
        resolves through the same table, so both spellings reach one place.
        """
        if isinstance(node, ast.Name):
            if node.id in self.plugs:
                return self.plugs[node.id]
            raise _ShapeRefused("plug %r is not a known plug expression"
                                % node.id)
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
                and isinstance(node.left, ast.Name)
                and _is_str_const(node.right)
                and node.right.value.startswith(".")):
            raise _ShapeRefused("not a '<node> + \".attr\"' plug expression")
        base, attr = node.left.id, node.right.value
        if "." in attr[1:] or "[" in attr:
            # A compound / indexed plug is findPlug-able but the Python string
            # form and the API form diverge; refuse rather than approximate.
            raise _ShapeRefused("compound or indexed plug %r" % attr)
        if base == self.name:
            return _SELF, attr
        if base in self.nodes:
            return self.nodes[base], attr
        raise _ShapeRefused("plug on unknown local %r" % base)

    def _node_name_expr(self, node):
        """``name + "Render"`` -> the suffix. Any other naming is refused."""
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
                and isinstance(node.left, ast.Name)
                and node.left.id == self.name
                and _is_str_const(node.right)):
            raise _ShapeRefused("node name is not '<get_name()> + \"suffix\"'")
        return node.right.value

    # -- statement handlers -------------------------------------------------

    def _create_node(self, target, call):
        if len(call.args) != 1 or not _is_str_const(call.args[0]):
            raise _ShapeRefused("createNode type is not a string literal")
        node_type = call.args[0].value
        if node_type not in _DAG_CREATE_TYPES:
            raise _ShapeRefused("createNode type %r is not a measured DAG type"
                                % node_type)
        suffix = None
        parent = None
        for k in call.keywords:
            if k.arg == "name":
                suffix = self._node_name_expr(k.value)
            elif k.arg == "parent":
                if not (isinstance(k.value, ast.Name)
                        and k.value.id in self.nodes):
                    raise _ShapeRefused("createNode parent is not a local this "
                                        "body created")
                parent = self.nodes[k.value.id]
                ptype = next(c["type"] for c in self.creates
                             if c["id"] == parent)
                if _DAG_CREATE_TYPES[ptype]:
                    # MDagModifier::createNode with a SHAPE parent comes back
                    # "parent is not a transform type", while cmds.createNode
                    # only WARNS and re-homes under a fresh transform -- the
                    # compiled command would fail where the body succeeded.
                    raise _ShapeRefused("createNode parent is the shape %r"
                                        % ptype)
            else:
                raise _ShapeRefused("createNode flag %r is not modelled"
                                    % k.arg)
        if suffix is None:
            raise _ShapeRefused("createNode without an explicit name")
        if parent is None and _DAG_CREATE_TYPES[node_type]:
            raise _ShapeRefused("shape type %r is created without a parent"
                                % node_type)
        nid = "n%d" % len(self.creates)
        self.creates.append({"id": nid, "type": node_type, "suffix": suffix,
                             "parent": parent})
        self.nodes[target] = nid

    def _assign(self, stmt):
        # ``src, dst = <plug>, <plug>`` and ``conn = (src, dst)``
        if len(stmt.targets) != 1:
            raise _ShapeRefused("chained assignment")
        tgt = stmt.targets[0]

        if isinstance(tgt, ast.Tuple):
            if not isinstance(stmt.value, ast.Tuple) \
                    or len(tgt.elts) != len(stmt.value.elts):
                raise _ShapeRefused("unbalanced tuple assignment")
            for t, v in zip(tgt.elts, stmt.value.elts):
                if not isinstance(t, ast.Name):
                    raise _ShapeRefused("tuple assignment to a non-name")
                self.plugs[t.id] = self._plug_expr(v)
            return

        if not isinstance(tgt, ast.Name):
            raise _ShapeRefused("assignment to a non-name")
        target = tgt.id
        val    = stmt.value

        # name = self.get_name()
        if (isinstance(val, ast.Call) and not val.args and not val.keywords
                and isinstance(val.func, ast.Attribute)
                and val.func.attr == "get_name"
                and isinstance(val.func.value, ast.Name)
                and val.func.value.id == "self"):
            if self.name is not None:
                raise _ShapeRefused("get_name() bound twice")
            self.name = target
            return

        # created = []  /  conn = None  /  conn = (src, dst): pure bookkeeping
        # for the Python rollback, which the C++ modifiers replace.
        if (isinstance(val, ast.List) and not val.elts) \
                or (isinstance(val, ast.Constant) and val.value is None):
            self.books.add(target)
            return
        if target in self.books:
            return

        if self._mc_call(val, "createNode"):
            self._create_node(target, val)
            return

        # A lone plug string, e.g. ``src = name + ".outMesh"``.
        self.plugs[target] = self._plug_expr(val)

    def _expr(self, stmt):
        val = stmt.value
        if _is_str_const(val):
            return                                  # docstring / bare string
        if not isinstance(val, ast.Call):
            raise _ShapeRefused("bare expression is not a call")

        # created.append(xform) -- bookkeeping for the Python rollback only.
        if (isinstance(val.func, ast.Attribute) and val.func.attr == "append"
                and isinstance(val.func.value, ast.Name)
                and val.func.value.id in self.books):
            return

        if self._mc_call(val, "connectAttr"):
            if len(val.args) != 2:
                raise _ShapeRefused("connectAttr takes other than two plugs")
            for k in val.keywords:
                if k.arg in ("force", "f"):
                    if not _is_true(k.value):
                        raise _ShapeRefused("connectAttr force is not True")
                else:
                    raise _ShapeRefused("connectAttr flag %r is not modelled"
                                        % k.arg)
            src, dst = self._plug_expr(val.args[0]), self._plug_expr(val.args[1])
            # ``force=True`` breaks an existing incoming connection first;
            # MDGModifier::connect does not. That divergence is unreachable here
            # ONLY because _plug_expr admits no node this command did not just
            # create, so a destination can never already be connected -- which
            # is asserted rather than assumed, so it stays true if the grammar
            # ever grows a node the command did not make.
            if dst[0] != _SELF and dst[0] not in self.nodes.values():
                raise _ShapeRefused("connect destination is not a node this "
                                    "command creates")
            self.connects.append((src, dst))
            return

        if self._mc_call(val, "sets"):
            if len(val.args) != 1 or not isinstance(val.args[0], ast.Name) \
                    or val.args[0].id not in self.nodes:
                raise _ShapeRefused("sets() target is not a local this body "
                                    "created")
            set_name = None
            edit     = False
            for k in val.keywords:
                if k.arg in ("edit", "e"):
                    if not _is_true(k.value):
                        raise _ShapeRefused("sets() is not an edit")
                    edit = True
                elif k.arg in ("forceElement", "fe"):
                    if not _is_str_const(k.value):
                        raise _ShapeRefused("sets() set name is not a literal")
                    set_name = k.value.value
                else:
                    raise _ShapeRefused("sets() flag %r is not modelled" % k.arg)
            # MFnSet::addMember is the twin of the EDIT form only. Without -e,
            # ``sets`` is in create mode, where -forceElement means something
            # else entirely, so an unflagged call is refused rather than
            # assumed to be the membership the lowering emits.
            if set_name is None or not edit:
                raise _ShapeRefused("sets() is not an edit with forceElement")
            self.sets.append((self.nodes[val.args[0].id], set_name))
            return

        raise _ShapeRefused("call is not one of createNode / connectAttr / sets")

    def _check_handler(self, handler):
        """The rollback must be a rollback: no result, no side effect beyond
        undoing what the body did, and it must re-raise."""
        if handler.type is not None and not (
                isinstance(handler.type, ast.Name)
                and handler.type.id in ("Exception", "BaseException")):
            raise _ShapeRefused("except clause is not a bare Exception handler")
        allowed = ("disconnectAttr", "delete", "objExists")
        raises  = False
        for node in ast.walk(handler):
            if isinstance(node, ast.Return):
                raise _ShapeRefused("the rollback returns a value")
            if isinstance(node, ast.Raise):
                if node.exc is None:
                    raises = True
                else:
                    raise _ShapeRefused("the rollback raises a NEW exception")
            if isinstance(node, ast.Call):
                f = node.func
                if not (isinstance(f, ast.Attribute) and f.attr in allowed):
                    raise _ShapeRefused(
                        "the rollback calls something other than %s"
                        % "/".join(allowed))
        if not raises:
            raise _ShapeRefused("the rollback swallows the exception")

    def _body(self, body, toplevel):
        for stmt in body:
            if self.returned:
                raise _ShapeRefused("statements after the return")
            if isinstance(stmt, ast.Expr):
                self._expr(stmt)
            elif isinstance(stmt, ast.Assign):
                self._assign(stmt)
            elif isinstance(stmt, ast.ImportFrom):
                if not (stmt.module == "maya" and not stmt.level
                        and len(stmt.names) == 1
                        and stmt.names[0].name == "cmds"):
                    raise _ShapeRefused("import other than 'from maya import "
                                        "cmds'")
                self.mc = stmt.names[0].asname or "cmds"
            elif isinstance(stmt, ast.Try) and toplevel:
                if stmt.orelse or stmt.finalbody or len(stmt.handlers) != 1:
                    raise _ShapeRefused("try/except with else/finally or "
                                        "multiple handlers")
                self._body(stmt.body, toplevel=False)
                self._check_handler(stmt.handlers[0])
            elif isinstance(stmt, ast.Return):
                if not (isinstance(stmt.value, ast.Name)
                        and stmt.value.id == self.name):
                    raise _ShapeRefused("the body returns something other than "
                                        "the node name")
                self.returned = True
            else:
                raise _ShapeRefused("statement %s is not modelled"
                                    % type(stmt).__name__)

    def read(self):
        self._body(self.fn.body, toplevel=True)
        if self.name is None:
            raise _ShapeRefused("the body never calls self.get_name()")
        if not self.returned:
            raise _ShapeRefused("the body does not return the node name")
        if not self.creates:
            raise _ShapeRefused("the body creates nothing")
        return {"kind": "render_shape_setup", "creates": self.creates,
                "connects": self.connects, "sets": self.sets}


def native_plan_for(cmd: dict, flags: List[dict]):
    """A pure-C++ lowering plan for ``cmd``, or None to keep the Python body.

    ``flags`` is :func:`flag_spec_for`'s output; a command with flags is not a
    candidate today -- every recognised shape is parameterless, and inventing a
    C++ read for a flag nothing consumes would be untested code.
    """
    if flags:
        return None
    if not cmd.get("creates") or cmd.get("is_factory") or cmd.get("is_static"):
        return None
    src = _dedent_def(cmd.get("body_src") or "")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == cmd.get("func_name"):
            fn = node
            break
    if fn is None:
        return None
    try:
        return _RenderShapeReader(fn).read()
    except _ShapeRefused:
        return None


_CPP_NATIVE_CLASS = r'''
// ==== @CMD@ -- PURE C++, no embedded Python ====
// Back-transpiled from the @maya_command body by command_dispatch's
// render_shape_setup recogniser: the whole body is createNode / connectAttr /
// sets, which the Maya API expresses directly. Nothing about this command
// ships as Python, so a plug-in whose commands ALL lower this way carries no
// payload and runs no Python at all. (Deliberately NOT naming the Python-exec
// entry point here: a grep-based "does this artifact embed Python" audit must
// not be tripped by a comment.)
class @CLS@ : public MPxCommand {
public:
    static void* creator() { return new @CLS@(); }
    static MSyntax newSyntax() {
        // Same surface as the dispatched form: the body ignores the free
        // objects (it swallows them through *args/**kwargs), but REJECTING
        // them here would change what the command accepts.
        MSyntax syn;
        syn.setObjectType(MSyntax::kSelectionList, 0, 255);
        syn.useSelectionAsDefault(true);
        return syn;
    }
    // Unlike the dispatched form -- which cannot reverse an arbitrary Python
    // body and so refuses to claim undoability -- every effect here is on a
    // modifier, so this one is genuinely undoable.
    bool isUndoable() const override { return true; }

    MStatus doIt(const MArgList& argList) override {
        MStatus st;
        MArgDatabase argData(syntax(), argList, &st);
        if (!st) return st;
        // creates=True: this command owns the node's creation. It rides its
        // OWN modifier because the Python contract is that a FAILED body must
        // leave the node standing ("build() owns self -- never delete it on
        // failure ... self is left built-but-unwired").
        _self = _nodeMod.createNode("@TYPE@", &st);
        if (!st) return st;
        st = _nodeMod.doIt();
        if (!st) return st;
        _name = MFnDependencyNode(_self).name();
        st = buildBody();
        if (!st) {
            _bodyMod.undoIt();
            _dagMod.undoIt();
            return st;
        }
@SELECT@
        setResult(_name);
        return MS::kSuccess;
    }

    // Both replay the modifiers in order; neither re-issues createNode (a
    // modifier ACCUMULATES operations, so re-issuing would duplicate nodes).
    MStatus redoIt() override {
        MStatus st = _nodeMod.doIt();
        if (!st) return st;
        st = _dagMod.doIt();
        if (!st) return st;
        st = _bodyMod.doIt();
        if (!st) return st;
        st = applySets();
        if (!st) return st;
@SELECT@
        setResult(_name);
        return MS::kSuccess;
    }

    MStatus undoIt() override {
        // Set membership needs no explicit reversal: the members are the very
        // nodes _dagMod deletes.
        _bodyMod.undoIt();
        _dagMod.undoIt();
        MStatus st = _nodeMod.undoIt();
        // What Maya's own createNode undo does: put back the selection the
        // do/redo replaced. Last, so the deletes above cannot drop out of it.
        MGlobal::setActiveSelectionList(_priorSel, MGlobal::kReplaceList);
        return st;
    }

private:
    MStatus buildBody() {
        MStatus st;
@CREATES@
        st = _dagMod.doIt();
        if (!st) return st;
@CONNECTS@
        st = _bodyMod.doIt();
        if (!st) return st;
        return applySets();
    }

    MStatus applySets() {
@SETS@
        return MS::kSuccess;
    }

    static MStatus _findPlug(const MObject& node, const char* attr,
                             MPlug& out) {
        MStatus st;
        MFnDependencyNode fn(node, &st);
        if (!st) return st;
        out = fn.findPlug(attr, false, &st);
        return st;
    }

    MDGModifier  _nodeMod;   // the node this command creates
    MDagModifier _dagMod;    // the DAG nodes the body creates
    MDGModifier  _bodyMod;   // the body's connections
    MObject _self;
    MString _name;
    MSelectionList _priorSel;   // what the do/redo replaced; undoIt puts it back
@MEMBERS@
};
'''


def _native_obj(node_id: str) -> str:
    return "_self" if node_id == _SELF else "_o_" + node_id


def _native_creates(plan: dict) -> str:
    out = []
    for c in plan["creates"]:
        parent = ("MObject::kNullObj" if c["parent"] is None
                  else _native_obj(c["parent"]))
        var = _native_obj(c["id"])
        out.append('        %s = _dagMod.createNode("%s", %s, &st);'
                   % (var, c["type"], parent))
        out.append("        if (!st) return st;")
        # createNode + renameNode on ONE modifier is the API twin of cmds
        # createNode(name=...): both land the node already named, and both undo
        # as a single queued unit.
        out.append('        st = _dagMod.renameNode(%s, _name + "%s");'
                   % (var, c["suffix"]))
        out.append("        if (!st) return st;")
    return "\n".join(out)


def _native_connects(plan: dict) -> str:
    out = []
    for (src_node, src_attr), (dst_node, dst_attr) in plan["connects"]:
        out.append("        {")
        out.append("            MPlug _s, _d;")
        out.append('            st = _findPlug(%s, "%s", _s);'
                   % (_native_obj(src_node), src_attr[1:]))
        out.append("            if (!st) return st;")
        out.append('            st = _findPlug(%s, "%s", _d);'
                   % (_native_obj(dst_node), dst_attr[1:]))
        out.append("            if (!st) return st;")
        out.append("            st = _bodyMod.connect(_s, _d);")
        out.append("            if (!st) return st;")
        out.append("        }")
    return "\n".join(out)


def _native_sets(plan: dict) -> str:
    out = []
    for node_id, set_name in plan["sets"]:
        out.append("        {")
        out.append("            MStatus st;")
        out.append("            MSelectionList _sl;")
        out.append('            st = _sl.add("%s");' % set_name)
        out.append("            if (!st) return st;")
        out.append("            MObject _sg;")
        out.append("            st = _sl.getDependNode(0, _sg);")
        out.append("            if (!st) return st;")
        out.append("            MFnSet _fn(_sg, &st);")
        out.append("            if (!st) return st;")
        out.append("            st = _fn.addMember(%s);" % _native_obj(node_id))
        out.append("            if (!st) return st;")
        out.append("        }")
    return "\n".join(out)


def _native_select(plan: dict) -> str:
    """Leave selected whatever the PYTHON form of this same command leaves
    selected -- which a modifier create does not do at all.

    That form is ``_CompiledProxy.create()`` (``cmds.createNode(<type>)``, which
    selects the mPyNode) followed by the body VERBATIM, and every
    ``cmds.createNode`` in the body reselects what IT makes -- the recognised
    grammar admits no ``skipSelect``. So the selection the command ends on is
    the body's LAST create, not the mPyNode, and it is only reached when the
    body ran to completion; hence the caller splices this AFTER buildBody().

    The snapshot rides along because Maya's own createNode undo restores the
    selection it replaced -- see the restore in ``undoIt``.
    """
    last = _native_obj(plan["creates"][-1]["id"])
    return "\n".join([
        "        // The Python form ends on the body's LAST cmds.createNode,",
        "        // which reselects what it makes; a modifier create does not.",
        "        // Snapshot first -- undo has to put back what this replaces.",
        "        MGlobal::getActiveSelectionList(_priorSel);",
        "        MGlobal::select(%s, MGlobal::kReplaceList);" % last,
    ])


def emit_native_command(cmd: dict, plan: dict, node_type_name: str) -> str:
    """The pure-C++ MPxCommand for one recognised command."""
    members = "    MObject %s;" % ", ".join(
        _native_obj(c["id"]) for c in plan["creates"])
    return (_CPP_NATIVE_CLASS
            .replace("@CREATES@", _native_creates(plan))
            .replace("@CONNECTS@", _native_connects(plan))
            .replace("@SETS@", _native_sets(plan))
            .replace("@SELECT@", _native_select(plan))
            .replace("@MEMBERS@", members)
            .replace("@CLS@", cmd_class_name(cmd["name"]))
            .replace("@CMD@", cmd["name"])
            .replace("@TYPE@", node_type_name))


# ---- Python side (embedded in the bundle, base64'd) ------------------------

_PY_DISPATCH = r'''
"""Bundled command dispatch for a compiled mPyNode.

Executed LAZILY on the first command call, never at plug-in load: ANY Python
run at initializePlugin that failed would unregister the node type and, in a
merged bundle, take every other node down with it.

This module imports NO mpynode -- every name it needs is VENDORED in below at
codegen time -- so it also runs on a machine that has Maya but not the mpynode
package, which is what a distributed plug-in actually gets.
"""
import base64
import json
import numbers

from maya import cmds

__MPY_PRELUDE__

US = "\x1f"     # tag / payload separator
RS = "\x1e"     # array item separator

_METHODS_SRC = __MPY_METHODS_SRC__
_NODE_TYPE = __MPY_NODE_TYPE__
_KINDS = __MPY_KINDS__
# command name AND def name -> def name, computed at BUILD time by the real
# detect_commands over the same source. Everything that loop knew is constant,
# so the AST walker does not have to be vendored into every bundle.
_FUNCS = __MPY_FUNCS__


_COMPILED_UNSUPPORTED = __MPY_UNSUPPORTED__


class _CompiledProxy(object):
    """Handle to a COMPILED node, standing in for the live wrapper. A FACTORY
    command uses the CLASS (create()/build() -> createNode(<type>)); an INSTANCE
    or CREATES command uses an instance bound to a node name.

    THE SETUP-SAFE CONTRACT. A setup body is written against the interpreted
    MPyNode, whose surface is built on plugs (_methodsSource, _storedVarNames,
    _inputAttrs, ...) that a compiled node does not have. Rather than let every
    such access decay into ``cmds.getAttr("<node>.set_variable")`` and surface as
    a bare ``AttributeError``, the proxy implements EXACTLY the members a setup
    may legitimately use and refuses the rest BY NAME with the reason.

    Measured across all 17 authored setups (8 type defaults + 9 templates), the
    entire surface actually used is four members:

        get_name()      -- 17/17
        NATIVE_TYPE     --  4/17 (the type defaults' SetupError message)
        call_command()  --  2/17 (spine, procrustesSingleTag)
        set_variable()  --  1/17 (unitSphereCollision)

    The first three are recoverable here with no node state: NATIVE_TYPE is the
    compiled type, and call_command/get_methods_source come from the methods
    source already embedded in this module. set_variable is NOT recoverable and
    is refused.
    """

    _compiled_type = _NODE_TYPE
    # The interpreted wrapper exposes this as a class attribute too, so a setup
    # doing "%s" % self.NATIVE_TYPE reads identically in both worlds. Declared
    # (rather than left to __getattr__) so it never becomes a plug lookup.
    NATIVE_TYPE = _NODE_TYPE

    def __init__(self, name=None):
        object.__setattr__(self, "_name", name)

    @classmethod
    def create(cls, name=None):
        kw = {"name": name} if name else {}
        return cls(cmds.createNode(cls._compiled_type, **kw))

    build = create

    def get_name(self):
        return object.__getattribute__(self, "_name")

    def get_methods_source(self):
        """The node's Methods source. On the interpreted node this is a plug
        read; here the source is already embedded in this module, so a setup
        that reaches for it (directly or via call_command) works unchanged."""
        return _METHODS_SRC

    def call_command(self, command_name, *args, **kwargs):
        """Invoke a sibling @maya_command by command name OR def name.

        Mirrors MethodsSourceMixin.call_command, but resolves out of the
        embedded _METHODS_SRC instead of the _methodsSource plug (which a
        compiled node does not have). spine's whole setup is one call_command,
        so without this a create command for it cannot work at all.

        The name -> def lookup is the precomputed _FUNCS rather than a live
        detect_commands scan: same first-match-wins result, and it is what lets
        this module carry no mpynode import at all."""
        ns = build_methods_namespace(_METHODS_SRC)
        func_name = _FUNCS.get(command_name)
        if func_name is None:
            raise RuntimeError(
                "no @maya_command named %r on %r"
                % (command_name, object.__getattribute__(self, "_name")))
        fn = ns.get(func_name)
        if fn is None:
            raise RuntimeError(
                "command %r did not define %r" % (command_name, func_name))
        return invoke_command(fn, self, args, kwargs)

    def __getattr__(self, attr):
        why = _COMPILED_UNSUPPORTED.get(attr)
        if why is not None:
            raise RuntimeError(
                "%s is not available on a compiled node: %s. Rework the setup "
                "to use node attributes instead, or drop creates=True so the "
                "node keeps its interpreted-only setup."
                % (attr, why))
        name = object.__getattribute__(self, "_name")
        if name is None:
            raise AttributeError(attr)
        try:
            return cmds.getAttr("%s.%s" % (name, attr))
        except Exception:
            raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr == "_name":
            object.__setattr__(self, attr, value)
            return
        name = object.__getattribute__(self, "_name")
        cmds.setAttr("%s.%s" % (name, attr), value)


def _resolve_target(target, cmd_name):
    """An INSTANCE command's target: the explicit object argument, else the
    active selection. A compiled command has no implicit ``self``.

    ``target`` arrives RS-joined (the C++ side sends every object name so a
    create command can see them all); an instance command is capped at one
    object by its own MSyntax, and takes the first regardless."""
    if target:
        first = next((t for t in target.split(RS) if t), "")
        if first:
            return first
    sel = cmds.ls(selection=True) or []
    if sel:
        return sel[0]
    raise RuntimeError(
        "%s: select (or name) the target node -- a compiled command has no "
        "implicit 'self'." % cmd_name)


def _tagged(result):
    """``"<tag>US<payload>"`` so C++ can setResult with the RIGHT type.

    Without the tag every result would come back through the string channel and
    an int/list return would silently become a string -- a regression against
    the Python companion's typed setResult. Arrays are RS-joined rather than
    JSON so the C++ side needs no parser.
    """
    if result is None:
        return "none" + US
    getter = getattr(result, "get_name", None)
    if callable(getter):
        result = getter()
        if result is None:
            return "none" + US
    item = getattr(result, "item", None)
    if callable(item) and getattr(result, "ndim", None) == 0:
        try:
            result = result.item()
        except Exception:
            pass
    # Bool FIRST: numpy.bool_ is not numbers.Integral, and str() of it is
    # "False", which is truthy and would invert downstream tests.
    if isinstance(result, bool) or type(result).__name__ in ("bool_", "bool8"):
        return "bool" + US + ("1" if result else "0")
    if isinstance(result, numbers.Integral):
        return "int" + US + str(int(result))
    if isinstance(result, numbers.Real):
        return "float" + US + repr(float(result))
    if isinstance(result, dict):
        # No MPxCommand result type carries a dict; JSON keeps it readable and
        # round-trippable instead of Python's repr.
        try:
            return "str" + US + json.dumps(result, default=str)
        except Exception:
            return "str" + US + str(result)
    if isinstance(result, (list, tuple)):
        vals = list(result)
        if not vals:
            return "strArray" + US
        if all(isinstance(v, bool) for v in vals):
            return "intArray" + US + RS.join(str(int(v)) for v in vals)
        if all(isinstance(v, numbers.Integral) and not isinstance(v, bool)
               for v in vals):
            return "intArray" + US + RS.join(str(int(v)) for v in vals)
        if all(isinstance(v, numbers.Real) and not isinstance(v, bool)
               for v in vals):
            return "floatArray" + US + RS.join(repr(float(v)) for v in vals)
        return "strArray" + US + RS.join(str(v).replace(RS, " ") for v in vals)
    return "str" + US + str(result)


GS = "\x1d"     # parameter separator in the argument blob


def _coerce(kind, raw):
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "bool":
        return raw == "1"
    return raw


def _parse_args(blob):
    """Decode the C++ argument blob into kwargs.

    Shape: ``name US kind US v1 RS v2 ... GS name US kind US ...``, where kind
    is one of str/int/float/bool optionally prefixed ``list:``. Deliberately not
    JSON: the blob is built by C++ inside a Python string built by Python, and
    escaping quotes and backslashes correctly through those three layers is
    exactly where this goes wrong. Only flags the user actually PASSED appear
    here -- an absent flag is omitted so the Python default applies, never
    materialised as an empty value (measured: mapping absent to empty silently
    built a zero-rider spine with no error).
    """
    out = {}
    if not blob:
        return out
    for part in blob.split(GS):
        if not part:
            continue
        bits = part.split(US)
        if len(bits) < 3:
            continue
        name, kind, joined = bits[0], bits[1], US.join(bits[2:])
        if kind.startswith("list:"):
            inner = kind[5:]
            items = joined.split(RS) if joined else []
            out[name] = [_coerce(inner, x) for x in items]
        else:
            out[name] = _coerce(kind, joined)
    return out


def _dispatch(cmd_name, func_name, args_b64, target_b64):
    """Entry point the generated C++ calls. Both arguments arrive base64'd so
    the C++ side never has to escape quotes or backslashes into Python text."""
    ns = build_methods_namespace(_METHODS_SRC)
    fn = ns.get(func_name)
    if fn is None:
        raise RuntimeError(
            "bundled command %s: method %s missing from methods source"
            % (cmd_name, func_name))

    def _b64(s):
        return base64.b64decode(s.encode("ascii")).decode("utf-8") if s else ""

    kwargs = _parse_args(_b64(args_b64))
    target = _b64(target_b64)
    kind = _KINDS.get(cmd_name, "instance")
    if kind == "creates":
        # The blendShape/skinCluster shape. The free objects are the geometry
        # the node is applied TO -- NOT the node, which does not exist yet. They
        # were captured by the C++ doIt before any Python ran, precisely because
        # cmds.createNode reselects the node it makes; the cmds.ls fallback here
        # only fires when the command was driven with no objects at all.
        sel = [t for t in target.split(RS) if t] if target else []
        if not sel:
            sel = cmds.ls(selection=True, long=True) or []
        proxy = _CompiledProxy.create()
        # setdefault, not assignment: an explicit -selection flag wins.
        kwargs.setdefault("selection", sel)
    elif kind == "instance":
        proxy = _CompiledProxy(_resolve_target(target, cmd_name))
    else:
        proxy = _CompiledProxy()
    # invoke_command takes kwargs as a NAMED parameter, not **kwargs. Its final
    # branch is fn(wrapper, *args, **kwargs), so a freshly created proxy invokes
    # a self-first setup body verbatim -- no shim, no second entry point.
    return _tagged(invoke_command(fn, proxy, kwargs=kwargs))
'''


# Head of the vendored prelude. ``inspect`` is here rather than inside the
# vendored chunks because invoke_command's body needs it and its own module's
# import line is not part of its getsource() slice.
_PRELUDE_HEAD = '''# ---- vendored at codegen time; see command_dispatch._prelude_source ----
# A compiled bundle is loaded on machines that have Maya but NOT the mpynode
# Python package, so this module may not import mpynode at all -- the names
# below are EXTRACTED from the live package when the bundle is built.
import inspect
'''

# The ONE hand-written member of the prelude. The original reads HELPERS off the
# test_helpers MODULE object; a flat prelude vendors that module's CONTENTS, so
# there is no module to attribute through and HELPERS is bound directly.
_PRELUDE_NAMESPACE = '''
def build_methods_namespace(source):
    """Twin of methods_registry.build_methods_namespace.

    Injects exactly the same names: maya_command / maya_demo / maya_test plus
    every key of test_helpers.HELPERS."""
    ns = {
        "maya_command": maya_command,
        "maya_demo": maya_demo,
        "maya_test": maya_test,
    }
    ns.update(HELPERS)
    exec(compile(source or "", "<methods>", "exec"), ns)
    return ns
'''

# A __future__ import is only legal at the top of a FILE; a vendored chunk lands
# mid-module, where it is a hard SyntaxError.
_FUTURE_IMPORT = re.compile(r"(?m)^from\s+__future__\s+import\s+[^\n]*\n?")


def _prelude_source() -> str:
    """The mpynode names the dispatch module needs, as VENDORED source text.

    Extracted with ``inspect.getsource`` rather than hand-copied so the bundle
    cannot drift from the SSOT (notably ``test_helpers.HELPERS``, which decides
    what ``build_methods_namespace`` injects). Raises rather than emitting a
    partial prelude: a missing name here is invisible until a user runs the
    command in a scene.
    """
    import inspect as _inspect

    from mpynode._common.methods import maya_command as _maya_command
    from mpynode._common.methods import methods_registry as _methods_registry
    from mpynode._common.methods import test_helpers as _test_helpers

    wanted = (
        ("mpynode._common.methods.test_helpers", _test_helpers),
        ("maya_command", _maya_command.maya_command),
        ("maya_demo", _maya_command.maya_demo),
        ("maya_test", _maya_command.maya_test),
        ("methods_registry.invoke_command", _methods_registry.invoke_command),
    )
    parts = [_PRELUDE_HEAD]
    for what, obj in wanted:
        try:
            src = _inspect.getsource(obj)
        except (OSError, TypeError) as exc:
            raise RuntimeError(
                "command_dispatch: cannot read the source of %s to vendor it "
                "into the bundle (%s). Emitting the prelude without it would "
                "ship a module that only fails once a user RUNS the command, "
                "so the compile stops here." % (what, exc)) from exc
        if not src.strip():
            raise RuntimeError(
                "command_dispatch: inspect.getsource(%s) came back empty; "
                "refusing to emit a truncated prelude." % what)
        parts.append(_FUTURE_IMPORT.sub("", src))
    parts.append(_PRELUDE_NAMESPACE)

    out = "\n\n".join(p.strip("\n") for p in parts) + "\n"
    # Parse-check here, at codegen, where the failure is attributable -- and
    # re-assert the whole point of the prelude: nothing in it imports mpynode.
    try:
        tree = ast.parse(out)
    except SyntaxError as exc:
        raise RuntimeError(
            "command_dispatch: the vendored prelude does not parse (%s)" % exc
        ) from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        else:
            continue
        bad = [m for m in mods if m == "mpynode" or m.startswith("mpynode.")]
        if bad:
            raise RuntimeError(
                "command_dispatch: the vendored prelude still imports %s. The "
                "bundle runs where mpynode is absent, so the compile stops "
                "here." % ", ".join(bad))
    return out


def python_module_source(node_type_name: str, methods_source: str,
                         commands: List[dict]) -> str:
    """The Python dispatch module embedded in the bundle for one node."""
    from mpynode._common.methods.maya_command import detect_commands

    kinds = {}
    for c in commands:
        if c.get("is_factory"):
            kinds[c["name"]] = "factory"
        elif c.get("is_static"):
            kinds[c["name"]] = "static"
        elif c.get("creates"):
            # Checked AFTER factory/static: detect_commands already forces
            # creates False on those, and this ordering keeps the classification
            # correct even for a hand-built command dict that did not.
            kinds[c["name"]] = "creates"
        else:
            kinds[c["name"]] = "instance"
    # What _CompiledProxy.call_command used to recompute per call. Its loop was
    # FIRST-match-wins across (name, func_name) and a dict is last-write-wins,
    # so setdefault -- in source order -- is what preserves the resolution.
    # Built from the WHOLE source, not `commands`, because that is what the loop
    # scanned (an un-lowerable sibling command was still reachable here).
    funcs = {}
    for c in detect_commands(methods_source or ""):
        for key in (c["name"], c["func_name"]):
            funcs.setdefault(key, c["func_name"])
    # The prelude goes in FIRST so a Methods source that happens to contain the
    # token cannot be spliced into.
    return (_PY_DISPATCH
            .replace("__MPY_PRELUDE__", _prelude_source())
            .replace("__MPY_METHODS_SRC__", repr(methods_source))
            .replace("__MPY_NODE_TYPE__", repr(node_type_name))
            .replace("__MPY_KINDS__", repr(kinds))
            .replace("__MPY_FUNCS__", repr(funcs))
            .replace("__MPY_UNSUPPORTED__", repr(COMPILED_UNSUPPORTED)))


# MSVC error C2026 caps string LITERALS twice over: a single literal at 16380
# bytes, and the CONCATENATION of adjacent literals at 65535. The payload used
# to be emitted as adjacent literals, so BOTH bound it, and the second one
# rejected a real node outright -- MPyNode/DNET is 75016 bytes of base64, of
# which ~15KB is the vendored prelude that every node pays. The payload is now
# the initialiser of a `static const char[]` (see _b64_array_body): an
# aggregate initialiser is not a string literal, so neither cap reaches it and
# the payload has no size ceiling at all.
#
# What still binds is per-LINE, not per-payload. MSVC caps one source line at
# 65535 characters, and a row of the initialiser costs 4 source characters
# ("'x',") per base64 character -- so it is the CHUNK WIDTH below, never the
# payload size, that has to stay under this.
MSVC_SOURCE_LINE_MAX = 65535

_B64_LINE_WIDTH = 100


def _b64_lines(text: str, width: int = _B64_LINE_WIDTH) -> List[str]:
    """base64, split into per-source-line chunks."""
    b = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return [b[i:i + width] for i in range(0, len(b), width)] or [""]


def _b64_array_body(text: str, indent: str = "    ") -> str:
    """``text`` as the element list of the C++ ``char[]`` in ``_CPP_SUPPORT``.

    One ``'x',`` per base64 character -- four times the source of a string
    literal, but a brace-initialised array is the one form with no MSVC size
    cap on the payload. base64 is pure printable ASCII (A-Za-z0-9+/=) so every
    character is a valid, escape-free C++ character literal.

    The terminating 0 belongs to the template, not here, so ``sizeof - 1`` on
    the C++ side is exactly the base64 length.
    """
    rows = []
    for chunk in _b64_lines(text):
        row = indent + "".join("'%s'," % ch for ch in chunk)
        if len(row) > MSVC_SOURCE_LINE_MAX:
            raise AssertionError(
                "command_dispatch: an initialiser row is %d characters, past "
                "MSVC's %d-character source-line cap. Lower _B64_LINE_WIDTH "
                "(currently %d; each base64 character costs 4)."
                % (len(row), MSVC_SOURCE_LINE_MAX, _B64_LINE_WIDTH))
        rows.append(row)
    return "\n".join(rows)


def cmd_class_name(name: str) -> str:
    """``"addSphere"`` -> ``"AddSphereCmd"`` (always a valid C++ identifier)."""
    sane = re.sub(r"\W", "_", name or "cmd")
    return sane[:1].upper() + sane[1:] + "Cmd"


def module_symbol(node_type_name: str) -> str:
    """The sys.modules key for a node's dispatch module. Per-node so a merged
    bundle's nodes cannot overwrite each other's dispatch."""
    return "mpynode_cmd_" + re.sub(r"\W", "_", node_type_name)


# ---- C++ side --------------------------------------------------------------

# Raw string: every backslash below belongs to the GENERATED C++, not to Python.
_CPP_SUPPORT = r'''
// ==== bundled @maya_command dispatch (shared support) ====
// The command BODIES are Python (host orchestration -- createNode/curve/numpy),
// but the COMMANDS are real MPxCommands registered by THIS plug-in, so a
// compile emits ONE artifact. The node's compute is untouched and pure C++.
namespace mpycmd_@NS@ {

// The dispatch module, base64'd. base64 rather than a raw string literal
// because the payload embeds the user's arbitrary Methods source, which could
// contain any delimiter we picked and would otherwise need escaping.
//
// A char ARRAY rather than a run of adjacent string literals: MSVC caps one
// literal at 16380 bytes AND their concatenation at 65535 (error C2026), and a
// real payload passes the second. An aggregate initialiser has neither cap.
static const char kPayloadB64[] = {
@LIT@
    0
};

static const std::string& payloadB64() {
    static const std::string s(kPayloadB64, sizeof(kPayloadB64) - 1);
    return s;
}

static bool& ready() { static bool r = false; return r; }

// Bootstrapped on the FIRST command call, NEVER at initializePlugin. Measured:
// running Python at load time and having it fail silently unregisters the node
// type -- saved scenes then open with `unknown` nodes, and in a merged bundle
// the whole plug-in aborts, taking every other node with it.
static MStatus ensurePython() {
    if (ready()) return MS::kSuccess;
    MString py("import base64,types,sys; _n='@MOD@'; _m=types.ModuleType(_n); ");
    py += "exec(compile(base64.b64decode('";
    py += payloadB64().c_str();
    py += "').decode('utf-8'), '<@MOD@>', 'exec'), _m.__dict__); ";
    py += "sys.modules[_n]=_m";
    MStatus st = MGlobal::executePythonCommand(py, false, false);
    if (!st) {
        MGlobal::displayError(
            "@MOD@: could not initialise the embedded command dispatch module "
            "-- see the Script Editor for the Python traceback. The module is "
            "self-contained and imports no mpynode, so this is a fault in the "
            "embedded payload, not a missing package.");
        return st;
    }
    ready() = true;
    return MS::kSuccess;
}

static std::string b64(const std::string& in) {
    static const char* T =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string o;
    size_t i = 0;
    while (i + 2 < in.size()) {
        unsigned v = ((unsigned char)in[i] << 16) |
                     ((unsigned char)in[i + 1] << 8) |
                     ((unsigned char)in[i + 2]);
        o += T[(v >> 18) & 63]; o += T[(v >> 12) & 63];
        o += T[(v >> 6) & 63];  o += T[v & 63];
        i += 3;
    }
    if (i + 1 == in.size()) {
        unsigned v = ((unsigned char)in[i] << 16);
        o += T[(v >> 18) & 63]; o += T[(v >> 12) & 63]; o += "==";
    } else if (i + 2 == in.size()) {
        unsigned v = ((unsigned char)in[i] << 16) |
                     ((unsigned char)in[i + 1] << 8);
        o += T[(v >> 18) & 63]; o += T[(v >> 12) & 63];
        o += T[(v >> 6) & 63];  o += "=";
    }
    return o;
}

// Run the dispatch and hand the tagged result back. The chunk makes the whole
// command ONE undo. undoEnabled MUST be true -- it defaults to FALSE, and the
// default was measured to leave the command's own mutations permanently
// un-undoable while one Ctrl+Z reverted an unrelated earlier operation.
static MStatus runDispatch(const char* cmdName, const char* funcName,
                           const std::string& argBlob,
                           const std::string& target, bool undoable,
                           MString& out) {
    MStatus st = ensurePython();
    if (!st) return st;
    MString py("import @MOD@ as _m; _m._dispatch('");
    py += cmdName;  py += "','";
    py += funcName; py += "','";
    py += b64(argBlob).c_str(); py += "','";
    py += b64(target).c_str();  py += "')";
    if (undoable) {
        MGlobal::executeCommand(
            MString("undoInfo -openChunk -chunkName \"") + cmdName + "\"",
            false, false);
    }
    // Note the argument order: the StringResult form RETURNS the MString and
    // takes (command, displayEnabled, undoEnabled, MStatus*) -- it does NOT
    // take an out-param second like the plain executePythonCommand overload.
    out = MGlobal::executePythonCommandStringResult(py, false, undoable, &st);
    if (undoable) {
        MGlobal::executeCommand("undoInfo -closeChunk", false, false);
    }
    return st;
}

// Split "<tag>\x1f<payload>" and setResult with the matching TYPE. Without the
// tag every result would return through the string channel, so an int or list
// return would silently become a string -- a regression against the Python
// companion's typed setResult.
static void applyResult(MPxCommand* cmd, const MString& tagged) {
    std::string s(tagged.asChar());
    size_t p = s.find('\x1f');
    if (p == std::string::npos) { cmd->setResult(MString(s.c_str())); return; }
    std::string tag = s.substr(0, p);
    std::string val = s.substr(p + 1);
    if (tag == "none") return;
    if (tag == "bool")  { cmd->setResult(val == "1"); return; }
    if (tag == "int")   { cmd->setResult((int)strtol(val.c_str(), 0, 10)); return; }
    if (tag == "float") { cmd->setResult(strtod(val.c_str(), 0)); return; }
    if (tag == "intArray" || tag == "floatArray" || tag == "strArray") {
        std::vector<std::string> items;
        if (!val.empty()) {
            size_t a = 0;
            while (true) {
                size_t b = val.find('\x1e', a);
                if (b == std::string::npos) { items.push_back(val.substr(a)); break; }
                items.push_back(val.substr(a, b - a));
                a = b + 1;
            }
        }
        if (tag == "intArray") {
            MIntArray arr;
            for (size_t i = 0; i < items.size(); ++i)
                arr.append((int)strtol(items[i].c_str(), 0, 10));
            cmd->setResult(arr);
        } else if (tag == "floatArray") {
            MDoubleArray arr;
            for (size_t i = 0; i < items.size(); ++i)
                arr.append(strtod(items[i].c_str(), 0));
            cmd->setResult(arr);
        } else {
            MStringArray arr;
            for (size_t i = 0; i < items.size(); ++i)
                arr.append(MString(items[i].c_str()));
            cmd->setResult(arr);
        }
        return;
    }
    cmd->setResult(MString(val.c_str()));
}

}  // namespace mpycmd_@NS@
'''

_CPP_CLASS = r'''
class @CLS@ : public MPxCommand {
public:
    static void* creator() { return new @CLS@(); }
    static MSyntax newSyntax() {
        MSyntax syn;
@FLAGS@
        // kSelectionList (not kStringObjects) to match getObjects(MSelectionList&)
        // and the shipped setMeshRegion contract; useSelectionAsDefault then
        // fills the target from the active selection when none is named.
        //
        // The object MAX is per-command (@OBJMAX@): an instance command operates
        // on ONE node, but a create command is the blendShape/skinCluster shape
        // -- its free objects are the geometry the new node is applied to, and
        // there can be many. Widening it for every command would stop Maya
        // rejecting a second object on an instance command, so it is not.
        syn.setObjectType(MSyntax::kSelectionList, 0, @OBJMAX@);
        syn.useSelectionAsDefault(true);
        return syn;
    }
    MStatus doIt(const MArgList& argList) override {
        MStatus st;
        MArgDatabase argData(syntax(), argList, &st);
        if (!st) return st;
        std::string blob;
@PARSE@
        // ALL object names, RS-joined. Reading them here -- inside doIt, before
        // any Python runs -- is what makes a create command see the user's
        // selection: cmds.createNode RESELECTS the node it makes, so a read
        // after the fact would return the new node instead. Python splits on RS
        // and an instance command still takes only the first.
        std::string target;
        {
            MSelectionList objs;
            MStringArray names;
            if (argData.getObjects(objs) == MS::kSuccess &&
                objs.getSelectionStrings(names) == MS::kSuccess &&
                names.length() > 0) {
                for (unsigned _oi = 0; _oi < names.length(); ++_oi) {
                    if (_oi) target += "\x1e";
                    target += names[_oi].asChar();
                }
            }
        }
        MString out;
        st = mpycmd_@NS@::runDispatch("@CMD@", "@FUNC@", blob, target,
                                      @UNDOABLE@, out);
        if (!st) return st;
        mpycmd_@NS@::applyResult(this, out);
        return MS::kSuccess;
    }
};
'''


def _flag_lines(flags: List[dict]) -> str:
    out = []
    for f in flags:
        atype = _FLAG_TYPES[f["type"]][0]
        out.append('        syn.addFlag("-%s", "-%s", %s);'
                   % (f["short"], f["long"], atype))
        if f["multi"]:
            out.append('        syn.makeFlagMultiUse("-%s");' % f["short"])
    return "\n".join(out)


def _parse_lines(flags: List[dict]) -> str:
    """Read each flag ONLY if the user set it.

    ``isFlagSet`` is what keeps an absent flag out of the blob entirely, so
    Python's own default applies. Materialising an absent flag as an empty
    value was measured to silently produce a wrong result rather than an error.
    """
    # C++ hex escapes are GREEDY: "\x1fbool" parses as one escape \x1fb and is a
    # hard error ("hex escape sequence out of range"). Adjacent string literals
    # concatenate, so every control byte is emitted as its own literal.
    US, RS, GS = '"\\x1f"', '"\\x1e"', '"\\x1d"'
    ctype = {"str": "MString", "int": "int", "float": "double", "bool": "bool"}

    out   = []
    for f in flags:
        short = f["short"]
        base  = f["type"][5:-1] if f["multi"] else f["type"]
        kind  = ("list:" + base) if f["multi"] else base
        out.append('        if (argData.isFlagSet("-%s")) {' % short)
        out.append('            if (!blob.empty()) blob += %s;' % GS)
        out.append('            blob += "%s"; blob += %s; blob += "%s"; '
                   'blob += %s;' % (f["param"], US, kind, US))
        if f["multi"]:
            out.append('            unsigned _n = argData.numberOfFlagUses("-%s");'
                       % short)
            out.append('            for (unsigned _i = 0; _i < _n; ++_i) {')
            out.append('                MArgList _al;')
            out.append('                if (argData.getFlagArgumentList("-%s", _i,'
                       ' _al) != MS::kSuccess) continue;' % short)
            out.append('                if (_i) blob += %s;' % RS)
            out.append('                blob += _str(_al.%s(0));'
                       % _FLAG_TYPES[f["type"]][1])
            out.append('            }')
        else:
            # MArgDatabase has NO asBool/asInt/asDouble -- values come out
            # through getFlagArgument(flag, index, T&) overloads.
            out.append('            %s _v%s{};' % (ctype[base], short))
            out.append('            argData.getFlagArgument("-%s", 0, _v%s);'
                       % (short, short))
            out.append('            blob += _str(_v%s);' % short)
        out.append('        }')
    return "\n".join(out)


_CPP_STRHELP = r'''
// Stringify a flag value for the argument blob; Python re-types it from the
// kind tag that travels with it.
static std::string _str(const MString& v) { return std::string(v.asChar()); }
static std::string _str(int v) { std::ostringstream o; o << v; return o.str(); }
static std::string _str(bool v) { return v ? "1" : "0"; }
static std::string _str(double v) {
    std::ostringstream o; o.precision(17); o << v; return o.str();
}
'''


EMPTY = {"classes": "", "register": [], "deregister": [], "includes": [],
         "supported": [], "native": [], "errors": []}


def dispatch_for_spec(spec: dict, node_type_name: str,
                      exclude=()) -> dict:
    """The ONE entry point every node emitter calls.

    Six emitters write their own ``initializePlugin`` (there is no shared
    scaffold), so the splice has to happen six times -- but the CODEGEN must
    not. Each emitter calls this and splices the four returned keys; nothing
    else is duplicated.

    ``exclude`` names commands the caller emits natively itself (the locator's
    hand-written mesh-region pair), so they are not also emitted here and do not
    double-register.

    Returns :data:`EMPTY` for a command-less node, which keeps a command-less
    build byte-identical to before.

    ``mpx_base`` is the one thing the spec knows and ``emit_dispatch_commands``
    cannot infer, so it is read here and passed down: it decides whether a
    command may be back-transpiled to pure C++ (see NATIVE_LOWERABLE_BASES).
    """
    cmds = (spec or {}).get("commands") or []
    todo = [c for c in cmds if c.get("name") not in set(exclude)]
    if not todo:
        # No dispatch module, so the Methods source is not embedded anywhere:
        # any mpynode import in it is LATENT, not shipped. Reported, never
        # fatal -- see the reachable-mpynode section note.
        report_latent_mpynode_imports(node_type_name,
                                      (spec or {}).get("methods") or "")
        return dict(EMPTY)
    return emit_dispatch_commands(
        todo, node_type_name, (spec or {}).get("methods") or "",
        mpx_base=(spec or {}).get("suggested", {}).get("mpx_base"))


def emit_dispatch_commands(commands: List[dict], node_type_name: str,
                           methods_source: str, mpx_base=None) -> dict:
    """Emit C++ for every command that has no hand-written native template.

    Returns ``{classes, register, deregister, includes, supported, native,
    errors}``. ``errors`` is non-empty when a command cannot be lowered as an
    MPxCommand at all; the caller decides whether that fails the compile.
    ``native`` names the commands whose BODY was back-transpiled to pure C++.

    ``mpx_base`` defaults to None, which disables native lowering entirely --
    a caller that cannot say what the node derives from gets exactly the output
    it got before this pass existed.
    """
    if not commands:
        return {"classes": "", "register": [], "deregister": [],
                "includes": [], "supported": [], "native": [], "errors": []}

    ns  = re.sub(r"\W", "_", node_type_name)
    mod = module_symbol(node_type_name)

    specs, errors, usable = {}, [], []
    for c in commands:
        name = c.get("name") or ""
        if not _VALID_COMMAND_NAME.match(name):
            errors.append("%r is not a valid Maya command identifier" % name)
            continue
        if c.get("creates"):
            blockers = create_command_blockers(c)
            if blockers:
                errors.extend(blockers)
                continue
        try:
            specs[name] = flag_spec_for(c)
            usable.append(c)
        except CommandSpecError as exc:
            errors.append(str(exc))
    if errors or not usable:
        return {"classes": "", "register": [], "deregister": [],
                "includes": [], "supported": [], "native": [],
                "errors": errors}

    # Which bodies escape Python entirely. Anything unrecognised keeps the
    # payload path unchanged.
    plans = {}
    if mpx_base in NATIVE_LOWERABLE_BASES:
        for c in usable:
            plan = native_plan_for(c, specs[c["name"]])
            if plan is not None:
                plans[c["name"]] = plan
    pythonic = [c for c in usable if c["name"] not in plans]

    # FATAL once a payload exists -- see the section note above. The roots stay
    # the FULL command set, because _CompiledProxy.call_command can reach a
    # natively lowered command's Python body out of the embedded source. With no
    # payload nothing embeds the source, so the module-scope imports are LATENT
    # and only reported.
    if pythonic:
        reachable = reachable_mpynode_imports(methods_source, usable)
        if reachable:
            from mpynode.native.compiler.errors import UnsupportedSpec
            raise UnsupportedSpec(
                "%s: %d mpynode import(s) are REACHABLE from a @maya_command. "
                "The bundle ships this source as EMBEDDED PYTHON and is loaded "
                "on machines that have Maya but NOT the mpynode package, where "
                "each one raises ModuleNotFoundError the first time the command "
                "runs. Vendor the code into the Methods source, or move the "
                "import inside a @maya_demo / @maya_test body (a bundle never "
                "invokes one):\n  %s"
                % (node_type_name, len(reachable), "\n  ".join(reachable)))
    else:
        report_latent_mpynode_imports(node_type_name, methods_source)

    # The payload and its support namespace exist ONLY for the commands that
    # still need Python. When every command lowered, none of it is emitted --
    # which is the whole point: the plug-in then carries no embedded Python and
    # never calls MGlobal::executePythonCommand.
    blocks = []
    if pythonic:
        py_src = python_module_source(node_type_name, methods_source, pythonic)
        blocks.append(_CPP_STRHELP)
        blocks.append(_CPP_SUPPORT.replace("@LIT@", _b64_array_body(py_src))
                                  .replace("@MOD@", mod)
                                  .replace("@NS@", ns))

    register, deregister, supported = [], [], []
    for c in usable:
        name = c["name"]
        cls  = cmd_class_name(name)
        if name in plans:
            blocks.append(emit_native_command(c, plans[name], node_type_name))
        else:
            blocks.append(
                _CPP_CLASS
                .replace("@CLS@", cls)
                .replace("@FLAGS@", _flag_lines(specs[name]))
                .replace("@PARSE@", _parse_lines(specs[name]))
                .replace("@CMD@", name)
                .replace("@FUNC@", c["func_name"])
                .replace("@NS@", ns)
                .replace("@OBJMAX@", "255" if c.get("creates") else "1")
                .replace("@UNDOABLE@",
                         "true" if c.get("undoable", True) else "false"))
        register.append(
            'MStatus _cs_%s = plugin.registerCommand("%s", %s::creator, '
            "%s::newSyntax); if (!_cs_%s) return _cs_%s;"
            % (cls, name, cls, cls, cls, cls))
        deregister.append('plugin.deregisterCommand("%s");' % name)
        supported.append(name)

    includes = list(COMMAND_INCLUDES)
    if plans:
        includes += [h for h in NATIVE_COMMAND_INCLUDES if h not in includes]

    return {
        "classes":    "\n".join(blocks),
        "register":   register,
        "deregister": deregister,
        "includes":   includes,
        "supported":  supported,
        "native":     [c["name"] for c in usable if c["name"] in plans],
        "errors":     [],
    }
