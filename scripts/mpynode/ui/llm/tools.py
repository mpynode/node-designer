"""Assistant tools -- the bridge between the LLM and the mpynode wrapper API.

Each tool maps to one or more public wrapper methods. ``dispatch`` runs a
single tool call and returns a JSON-serializable result dict. Every
node-mutating tool runs inside a Maya undo chunk so a whole assistant
session can be undone in one step.

THREADING: ``dispatch`` touches ``maya.cmds`` and the wrapper API, so it
MUST run on Maya's main thread. The client worker thread marshals each call
through ``maya.utils.executeInMainThreadWithResult`` -- callers here can
assume they are already on the main thread.
"""

from __future__ import annotations

import json
import re
from typing import Any

import maya.cmds as mc

# Curated subset of the wrapper type map the assistant may create.
_ATTR_TYPES = [
    "float", "int", "bool", "vector", "quaternion", "color", "euler", "matrix",
    "string", "hex", "python", "angle", "enum", "time",
    "mesh", "nurbsCurve", "nurbsSurface",
]

# Reusable attribute / variable item schemas for the batched ``define_node``.
_CAMEL = ("camelCase, lowercase first letter (e.g. noiseAmount, driverMatrix); "
          "never snake_case, never a leading capital, never spaces")
# Enum plugs are the one type whose declaration is incomplete without a
# second field. Maya stores the field INDEX, so the order here is the contract.
_ENUM_NAMES_PROP = {
    "type": "array",
    "items": {"type": "string"},
    "description": "REQUIRED when type is 'enum': the ordered field labels, "
                   "index 0 first. A rotate-order plug is "
                   "['xyz','yzx','zxy','xzy','yxz','zyx'], which matches "
                   "transform.rotateOrder 1:1. Omit it and the plug is a "
                   "meaningless two-field False/True enum.",
}

_INPUT_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "plug name -- " + _CAMEL},
        "type": {"type": "string", "enum": _ATTR_TYPES},
        "is_array": {"type": "boolean"},
        "min": {"type": "number"},
        "max": {"type": "number"},
        "default": {"type": "number"},
        "enum_names": _ENUM_NAMES_PROP,
    },
    "required": ["name", "type"],
}
_OUTPUT_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "plug name -- " + _CAMEL},
        "type": {"type": "string", "enum": _ATTR_TYPES},
        "is_array": {"type": "boolean"},
        "enum_names": _ENUM_NAMES_PROP,
    },
    "required": ["name", "type"],
}
_VAR_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "variable name -- snake_case "
                 "(Python convention), e.g. kernel_size; NOT a plug name"},
        "value": {"description": "any JSON value"},
        "persistent": {"type": "boolean"},
    },
    "required": ["name", "value"],
}


class ToolContext:
    """Per-session mutable state shared across tool calls.

    * ``working_node`` -- the node name most tools default to (set by
      ``create_node`` / ``set_working_node``, or seeded from the Node
      Designer's active tab).
    * ``on_nodes_changed`` -- optional callback fired after any mutation so
      the host UI (Attributes / Variables / script tabs) can refresh.
    """

    def __init__(self, working_node: str | None = None, on_nodes_changed=None):
        self.working_node = working_node
        self.on_nodes_changed = on_nodes_changed

    def _notify(self):
        if callable(self.on_nodes_changed):
            try:
                self.on_nodes_changed(self.working_node)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic "tools" format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_node_types",
        "description": "List every mPy node type that can be created, with a "
                       "one-line description. Call this first if unsure which "
                       "node type fits the task.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_node",
        "description": "Inspect a node: its type, Compute + Init expressions, "
                       "user inputs, user outputs, and stored variables. "
                       "Defaults to the working node.",
        "input_schema": {
            "type": "object",
            "properties": {"node": {"type": "string"}},
        },
    },
    {
        "name": "list_nodes",
        "description": "List the mPy node INSTANCES already in the scene (name + "
                       "type). Call this to FIND an existing node to edit -- e.g. "
                       "when the user says 'my node' / 'the gizmo' / 'the region' "
                       "but no working node is set. PREFER editing an existing node "
                       "over building a new one; only create_node / define_node a "
                       "fresh node when the user explicitly asks to build one, and "
                       "NEVER create throwaway/probe/scratch nodes.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "define_node",
        "description": "Build or fully configure a node in ONE call: create it "
                       "(node_type) or target an existing one (node), add ALL "
                       "inputs/outputs, set stored variables, and set the "
                       "Compute + Init expressions together. PREFER THIS over a "
                       "chain of small calls -- it minimizes API round-trips. "
                       "Expressions are syntax-checked before anything is "
                       "applied; the whole thing is one undo step.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_type": {"type": "string",
                              "description": "type to create, e.g. mPyNode "
                                             "(omit when editing an existing 'node')"},
                "node": {"type": "string",
                         "description": "existing node to configure "
                                        "(omit to create node_type)"},
                "name": {"type": "string", "description": "optional name when creating"},
                "inputs": {"type": "array", "items": _INPUT_ITEM},
                "outputs": {"type": "array", "items": _OUTPUT_ITEM},
                "variables": {"type": "array", "items": _VAR_ITEM},
                "compute": {"type": "string",
                            "description": "Compute expression source. Inputs read "
                                           "via self.<name> are already the right "
                                           "type (float/int/bool/str, vector->np "
                                           "(3,), matrix->MatrixView) -- do NOT "
                                           "recast: no float()/int()/str() on "
                                           "scalars, no np.asarray()/np.array()/"
                                           ".reshape(-1)/.astype() on vector/array "
                                           "reads, and no float()/int() around a "
                                           "numpy scalar used only in math -- "
                                           "np.linalg.norm/np.dot/np.clip/np.sin/... "
                                           "already work in arithmetic, abs(), "
                                           "math.*, indexing & output writes, so "
                                           "write abs(np.dot(a,b)) not "
                                           "abs(float(np.dot(a,b))), and "
                                           "np.linalg.norm(v) not "
                                           "float(np.linalg.norm(v)). "
                                           "A MatrixView is numpy-transparent (index/"
                                           "@/np.linalg work on it directly; use "
                                           ".asNumpy() only if you need a plain (4,4) "
                                           "copy) -- never hand-roll _mv_to_np / "
                                           "mv._as_floats(). For outputs assign numpy/"
                                           "Python natives; NEVER build om.MMatrix/"
                                           "MVector for a plug write or import "
                                           "maya.api in an expression. mPyTransform: "
                                           "write self.local_matrix "
                                           "(numpy (4,4) or None) + self.apply_rotate/"
                                           "translate/scale gates (no world_matrix slot; "
                                           "for world placement set local_matrix = "
                                           "world @ inv(parentWorld) off a connected "
                                           "parent input); NEVER self.matrix "
                                           "(that recurses into asMatrix -> infinite "
                                           "recursion). "
                                           "Use imports/helpers from Init directly; "
                                           "don't re-import here."},
                "init": {"type": "string",
                         "description": "Init expression source. Put imports + "
                                        "helper/function defs here (visible in "
                                        "Compute as globals)."},
                "methods": {"type": "string",
                            "description": "Methods source: companion @maya_command "
                                           "commands + helper functions, ISOLATED "
                                           "from Compute/Init. Import `from "
                                           "mpynode._common.methods.maya_command import "
                                           "maya_command` (no try/except) and "
                                           "decorate each command def "
                                           "@maya_command(name='...', "
                                           "undoable=True) with `self` as the first "
                                           "param. Methods MAY mutate the scene -- "
                                           "they run only when invoked."},
            },
        },
    },
    {
        "name": "create_node",
        "description": "Create a bare mPy node (no attrs). Prefer define_node "
                       "when you also know the attributes/expressions. Makes it "
                       "the working node; returns its name + schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_type": {"type": "string",
                              "description": "e.g. mPyNode, mPyLocator, mPyDeformer"},
                "name": {"type": "string", "description": "optional desired name"},
            },
            "required": ["node_type"],
        },
    },
    {
        "name": "set_working_node",
        "description": "Focus an existing node so subsequent tools default to it.",
        "input_schema": {
            "type": "object",
            "properties": {"node": {"type": "string"}},
            "required": ["node"],
        },
    },
    {
        "name": "add_input",
        "description": "Add a USER INPUT attribute to the node. Read it in the "
                       "Compute expression as self.<name>. Plug names MUST be "
                       "camelCase, lowercase first letter (e.g. noiseAmount).",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "name": {"type": "string", "description": "plug name -- " + _CAMEL},
                "type": {"type": "string", "enum": _ATTR_TYPES},
                "is_array": {"type": "boolean"},
                "min": {"type": "number"},
                "max": {"type": "number"},
                "default": {"type": "number"},
                "enum_names": _ENUM_NAMES_PROP,
            },
            "required": ["name", "type"],
        },
    },
    {
        "name": "add_output",
        "description": "Add a USER OUTPUT attribute. Write it in Compute as "
                       "self.<name> = value. Use type 'hex' to drive Maya's "
                       "type node textInput from plain text. Plug names MUST be "
                       "camelCase, lowercase first letter (e.g. outValue).",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "name": {"type": "string", "description": "plug name -- " + _CAMEL},
                "type": {"type": "string", "enum": _ATTR_TYPES},
                "is_array": {"type": "boolean"},
                "enum_names": _ENUM_NAMES_PROP,
            },
            "required": ["name", "type"],
        },
    },
    {
        "name": "set_compute_expression",
        "description": "Replace the node's Compute expression (the per-frame "
                       "body). Inputs read via self.<name> are ALREADY native "
                       "Python (float/int/bool/str; vector->numpy (3,); "
                       "matrix->MatrixView) -- do NOT recast with "
                       "float()/int()/str(), and do NOT wrap a numpy scalar "
                       "(np.linalg.norm/np.dot/np.clip/np.sin/...) in "
                       "float()/int() -- it already works in arithmetic, abs(), "
                       "math.*, indexing & writes (write np.linalg.norm(v), not "
                       "float(np.linalg.norm(v))). A MatrixView is numpy-transparent "
                       "(index/@/np.linalg work directly; .asNumpy() for a plain "
                       "(4,4) copy) -- never write _mv_to_np/mv._as_floats(). "
                       "Assign outputs as the matching native type; NEVER build "
                       "om.MMatrix/MVector or import maya.api for a plug write. "
                       "mPyTransform: write self.local_matrix "
                       "(numpy (4,4) or None) + self.apply_rotate/translate/scale "
                       "gates (no world_matrix slot; for world placement set "
                       "local_matrix = world @ inv(parentWorld) off a connected "
                       "parent input), NEVER self.matrix (infinite recursion). "
                       "compile_check first for non-trivial code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "set_init_expression",
        "description": "Replace the node's Init expression (runs once on file "
                       "open / edit). Put imports + helper/function defs HERE -- "
                       "their names are visible in Compute as globals, so don't "
                       "re-import in Compute.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "set_osl_expression",
        "description": "Set the node's OSL (Open Shading Language) render-target "
                       "string -- ONLY for OSL-capable nodes (mPyFile). This is "
                       "NOT Python: it is a renderer shader the node exposes as "
                       "its connectable .osl output (wireable into an Arnold "
                       "aiOslShader). Use it to TRANSLATE the node's Compute "
                       "look-math into OSL so Arnold reproduces the same look. "
                       "Write a complete `shader name(params...) { ... outColor "
                       "= ...; }`. Not syntax-checked as Python.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "source": {"type": "string",
                           "description": "complete OSL shader source"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "set_methods_source",
        "description": "Set the node's METHODS source -- a third code tier beside "
                       "Compute and Init, ISOLATED from both (its own namespace). "
                       "Put companion COMMANDS and helper functions here. A def "
                       "decorated @maya_command becomes a real Maya command "
                       "callable from maya.cmds / MEL (and is compiled into a "
                       "companion MPxCommand by the native pipeline). Import the "
                       "decorator DIRECTLY -- it ALWAYS exists, do NOT guard it "
                       "with try/except: `from mpynode._common.methods.maya_command import "
                       "maya_command`. Write each command as "
                       "`@maya_command(name='doThing', undoable=True)` then `def "
                       "do_thing(self, arg=None): ...`; the first param `self` IS "
                       "the node (use self.set_variable(...), self.get_name(), "
                       "self.<plug>). UNLIKE Compute/Init, a Methods command MAY "
                       "mutate the scene (cmds.connectAttr / createNode) because "
                       "it runs ONLY when explicitly invoked, never per-frame. Use "
                       "Methods when the user wants to DRIVE or interact with the "
                       "node via a command (e.g. 'add the selected faces to the "
                       "region'); keep per-frame math in Compute and imports/"
                       "helpers for Compute in Init.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "source": {"type": "string",
                           "description": "complete Methods source (Python)"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "set_variable",
        "description": "Set a stored variable on the node (persisted with the "
                       "scene). Value is JSON (number/string/bool/list/nested). "
                       "Variable names use snake_case (Python convention), NOT "
                       "camelCase -- these are internal vars, not plugs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string"},
                "name": {"type": "string", "description": "variable name -- "
                         "snake_case, e.g. kernel_size (NOT a plug name)"},
                "value": {"description": "any JSON value"},
                "persistent": {"type": "boolean"},
            },
            "required": ["name", "value"],
        },
    },
    {
        "name": "compile_check",
        "description": "Syntax-check a Python expression WITHOUT running it. "
                       "Returns {ok, error}. Use before set_compute_expression.",
        "input_schema": {
            "type": "object",
            "properties": {"source": {"type": "string"}},
            "required": ["source"],
        },
    },
]

# Exact tool names the model is allowed to call.
VALID_TOOLS = [t["name"] for t in TOOL_SCHEMAS]


def _norm(name: str) -> str:
    """Lowercase + strip non-alphanumerics (so define_node == DefineNode)."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


# Pre-normalized canonical names, longest first so the most specific wins.
_NORM_TOOLS = sorted(
    ((_norm(t), t) for t in VALID_TOOLS), key=lambda p: len(p[0]), reverse=True
)


def resolve_tool_name(name: str):
    """Map a possibly-mangled tool name to a canonical one, or None.

    Some models rewrite snake_case tool names (e.g. emit ``DefineNodeInputs``
    for ``define_node``). Rather than reject and loop, we normalize and match:
    exact-normalized, then prefix either direction (``definenodeinputs`` starts
    with ``definenode``). Conservative: unrelated names (e.g. ``Lock``) stay
    unresolved so the caller returns the valid-tools error.
    """
    if name in VALID_TOOLS:
        return name
    n = _norm(name)
    if not n:
        return None
    for cn, canon in _NORM_TOOLS:
        if cn == n:
            return canon
    for cn, canon in _NORM_TOOLS:  # longest canonical that prefixes/extends n
        if n.startswith(cn) or cn.startswith(n):
            return canon
    return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _wrap(name: str):
    import mpynode

    w = mpynode.wrap_node(name)
    if w is None:
        raise ValueError("node %r not found (or not an mPy node)" % name)
    return w


def _resolve(ctx: ToolContext, args: dict) -> str:
    name = args.get("node") or ctx.working_node
    if not name:
        raise ValueError("no node specified and no working node set; "
                         "call create_node or set_working_node first")
    if not mc.objExists(name):
        raise ValueError("node %r does not exist" % name)
    return name


def _node_schema(name: str) -> dict:
    w = _wrap(name)
    out = {
        "name": w.get_name(),
        "type": mc.nodeType(name),
        "inputs": {},
        "outputs": {},
        "variables": {},
    }
    try:
        out["compute_expression"] = w.get_compute_expression()
    except Exception:
        out["compute_expression"] = ""
    try:
        out["init_expression"] = w.get_init_expression()
    except Exception:
        out["init_expression"] = ""
    try:
        out["inputs"] = w.get_input_attr_map() or {}
    except Exception:
        pass
    try:
        out["outputs"] = w.get_output_attr_map() or {}
    except Exception:
        pass
    try:
        # variables can hold large arrays -- summarize, don't dump.
        for k, v in (w.get_variables() or {}).items():
            out["variables"][k] = _summarize(v)
    except Exception:
        pass
    # Methods tier (companion @maya_command commands + helpers), so the model can
    # SEE and extend existing methods rather than re-inventing them in Init.
    if hasattr(w, "get_methods_source"):
        try:
            out["methods_source"] = w.get_methods_source()
        except Exception:
            out["methods_source"] = ""
        out["commands"] = _command_names(w)
    return out


def _command_names(w) -> list:
    """Statically-detected @maya_command names on a wrapper's Methods source
    (never exec's user code)."""
    try:
        return [c["name"] for c in (w.list_commands() or [])]
    except Exception:
        return []


def _summarize(v: Any) -> str:
    """Compact description of a stored-var value (avoid dumping big arrays)."""
    try:
        import numpy as np

        if isinstance(v, np.ndarray):
            return "ndarray%s %s" % (tuple(v.shape), v.dtype)
    except Exception:
        pass
    r = repr(v)
    return r if len(r) <= 200 else r[:200] + "...(truncated)"


# LLM attr-spec key -> add_*_attr kwarg. Outputs take no numeric limits, so
# they get their own map rather than a shared one with holes.
_INPUT_EXTRA = {"is_array": "is_array", "min": "min_value",
                "max": "max_value", "default": "default_value",
                "enum_names": "enum_names"}
_OUTPUT_EXTRA = {"is_array": "is_array", "enum_names": "enum_names"}
# Keys that identify the spec rather than configure the plug.
_SPEC_KEYS = ("name", "type", "attr_type", "node")


def attr_kwargs(spec, mapping, warnings=None):
    """Map one LLM attribute spec onto ``add_*_attr`` kwargs. Pure.

    An enum with no field names is REJECTED here rather than quietly created
    as False/True. ``add_input_attr`` documents that fallback and .mpn files
    depend on it, so the wrapper keeps it; but a model that forgot the labels
    can read this error and fix it inside the same turn, which is strictly
    better than shipping a plug that looks finished and is not.

    Unrecognised keys are appended to ``warnings`` instead of vanishing. A key
    dropped in silence is exactly how ``enum_names`` stayed missing: the model
    sent it, the layers below discarded it, and every result reported success.
    """
    if (spec.get("type") or spec.get("attr_type")) == "enum" \
            and not spec.get("enum_names"):
        raise ValueError(
            "attribute %r is an enum with no enum_names. Pass the ordered "
            'field labels, e.g. enum_names: ["xyz", "yzx", "zxy", "xzy", '
            '"yxz", "zyx"] for a rotate-order plug.' % (spec.get("name"),))
    out = {}
    for key, value in spec.items():
        if key in mapping:
            if value is not None:
                out[mapping[key]] = value
        elif key not in _SPEC_KEYS and warnings is not None:
            warnings.append("%s: ignored unknown key %r"
                            % (spec.get("name") or "?", key))
    if "is_array" in out:
        out["is_array"] = bool(out["is_array"])
    return out


def _do(name: str, ctx: ToolContext, fn) -> dict:
    """Run a mutation inside an undo chunk + notify the host."""
    mc.undoInfo(openChunk=True, chunkName="assistant: %s" % name)
    try:
        result = fn()
    finally:
        mc.undoInfo(closeChunk=True)
    ctx._notify()
    return result


def dispatch(tool_name: str, args: dict, ctx: ToolContext) -> dict:
    """Execute one tool call. Returns a JSON-serializable result dict.
    Never raises -- errors are returned as ``{"error": "..."}`` so the model
    can read + recover. MUST be called on Maya's main thread.
    """
    try:
        canon = resolve_tool_name(tool_name)
        if canon is None:
            return {"error": "unknown tool %r. Call ONLY these tools (exact "
                             "names): %s" % (tool_name, ", ".join(VALID_TOOLS))}
        return _dispatch(canon, args or {}, ctx)
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, exc)}


def _dispatch(tool_name: str, args: dict, ctx: ToolContext) -> dict:
    if tool_name == "list_node_types":
        from mpynode._node_registry import REGISTRY

        return {"types": [
            {"type": t, "description": spec.description}
            for t, spec in sorted(REGISTRY.items())
        ]}

    if tool_name == "list_nodes":
        from mpynode._node_registry import REGISTRY

        # Pre-filter to LOADED node types: cmds.ls(type=X) on an unregistered
        # type prints a spurious "Unknown object type: X" to the Script Editor
        # (same guard as _common/time_utils.py + stored_var_store.py).
        try:
            known = set(mc.allNodeTypes() or [])
        except Exception:
            known = None
        seen = set()
        nodes = []
        for t in REGISTRY:
            if known is not None and t not in known:
                continue
            for n in (mc.ls(type=t, long=False) or []):
                if n not in seen:
                    seen.add(n)
                    nodes.append({"name": n, "type": t})
        nodes.sort(key=lambda d: d["name"])
        return {"nodes": nodes, "working_node": ctx.working_node}

    if tool_name == "get_node":
        return _node_schema(_resolve(ctx, args))

    if tool_name == "define_node":
        return _define_node(args, ctx)

    if tool_name == "create_node":
        from mpynode._node_registry import get_spec

        node_type = args["node_type"]
        spec = get_spec(node_type)
        if spec is None:
            return {"error": "unknown node_type %r" % node_type}
        cls = spec.get_wrapper_class()

        def _make():
            kwargs = {}
            if args.get("name"):
                kwargs["name"] = args["name"]
            # build() (NOT create()) so AI-created nodes seed their per-type
            # setup source onto _methodsSource, like the UI command path.
            # setup=True is deliberately NOT passed: an AI agent must not run
            # scene-mutating setup(self) against the ambient selection.
            w = cls.build(**kwargs)
            return w.get_name()

        name = _do("create_node", ctx, _make)
        ctx.working_node = name
        return {"created": name, "schema": _node_schema(name)}

    if tool_name == "set_working_node":
        name = args["node"]
        if not mc.objExists(name):
            return {"error": "node %r does not exist" % name}
        ctx.working_node = name
        return {"working_node": name, "schema": _node_schema(name)}

    if tool_name == "add_input":
        name = _resolve(ctx, args)

        def _add():
            warnings = []
            extra = attr_kwargs(args, _INPUT_EXTRA, warnings)
            _wrap(name).add_input_attr(args["name"], args["type"], **extra)
            res = {"added_input": args["name"], "type": args["type"]}
            if warnings:
                res["warnings"] = warnings
            return res

        return _do("add_input", ctx, _add)

    if tool_name == "add_output":
        name = _resolve(ctx, args)

        def _add():
            warnings = []
            extra = attr_kwargs(args, _OUTPUT_EXTRA, warnings)
            _wrap(name).add_output_attr(args["name"], args["type"], **extra)
            res = {"added_output": args["name"], "type": args["type"]}
            if warnings:
                res["warnings"] = warnings
            return res

        return _do("add_output", ctx, _add)

    if tool_name == "set_compute_expression":
        name = _resolve(ctx, args)
        ok, err = _compile_check(args["source"])
        if not ok:
            return {"error": "expression has a syntax error: %s" % err}
        guard = _expr_guard(args["source"])
        if guard:
            return guard

        def _set():
            _wrap(name).set_compute_expression(args["source"])
            return {"set_compute_expression": name}

        return _do("set_compute_expression", ctx, _set)

    if tool_name == "set_init_expression":
        name = _resolve(ctx, args)
        ok, err = _compile_check(args["source"])
        if not ok:
            return {"error": "expression has a syntax error: %s" % err}
        guard = _expr_guard(args["source"])
        if guard:
            return guard

        def _set():
            _wrap(name).set_init_expression(args["source"])
            return {"set_init_expression": name}

        return _do("set_init_expression", ctx, _set)

    if tool_name == "set_osl_expression":
        name = _resolve(ctx, args)
        w = _wrap(name)
        # Capability-gated: only OSL-capable wrappers (mPyFile) carry an .osl
        # render-target output. NOTE: deliberately NOT _compile_check'd or
        # _expr_guard'd -- OSL is not Python, so those would reject valid OSL.
        if not hasattr(w, "set_osl_expression"):
            return {"error": "node %r does not support an OSL output "
                             "(set_osl_expression is only for OSL-capable nodes "
                             "like mPyFile)" % name}

        def _set():
            w.set_osl_expression(args["source"])
            return {"set_osl_expression": name}

        return _do("set_osl_expression", ctx, _set)

    if tool_name == "set_methods_source":
        name = _resolve(ctx, args)
        w = _wrap(name)
        # Capability-gated like set_osl_expression: only wrappers exposing the
        # Methods tier accept it (all current mPy types do, via base MPyNode).
        if not hasattr(w, "set_methods_source"):
            return {"error": "node %r does not support a Methods tab "
                             "(set_methods_source)" % name}
        # Syntax-check (it IS Python) but DO NOT _expr_guard: Methods are
        # explicitly-invoked companion commands whose purpose is scene mutation
        # (createMeshRegion calls cmds.connectAttr). The per-frame guard that
        # protects Compute/Init does not apply.
        ok, err = _compile_check(args["source"])
        if not ok:
            return {"error": "methods source has a syntax error: %s" % err}

        def _set():
            w.set_methods_source(args["source"])
            return {"set_methods_source": name, "commands": _command_names(w)}

        return _do("set_methods_source", ctx, _set)

    if tool_name == "set_variable":
        name = _resolve(ctx, args)

        def _set():
            persistent = bool(args.get("persistent", True))
            value = _coerce_value(args["value"])
            _wrap(name).set_variable(args["name"], value, persistent=persistent)
            return {"set_variable": args["name"]}

        return _do("set_variable", ctx, _set)

    if tool_name == "compile_check":
        ok, err = _compile_check(args["source"])
        return {"ok": ok, "error": err}

    return {"error": "unknown tool %r. Call ONLY these tools (exact names): %s"
                     % (tool_name, ", ".join(VALID_TOOLS))}


def _define_node(args: dict, ctx: ToolContext) -> dict:
    """One-shot build/configure: create-or-target + attrs + vars + expressions.

    Validates up front (node existence, node_type, expression syntax) so the
    single undo chunk either applies cleanly or makes no changes.
    """
    from mpynode._node_registry import get_spec

    node = args.get("node")
    node_type = args.get("node_type")
    if not node and not node_type:
        return {"error": "define_node needs 'node_type' (to create) or 'node' "
                         "(to configure an existing node)"}
    if node and not mc.objExists(node):
        return {"error": "node %r does not exist" % node}
    if not node and get_spec(node_type) is None:
        return {"error": "unknown node_type %r" % node_type}

    compute = args.get("compute")
    init = args.get("init")
    for label, src in (("compute", compute), ("init", init)):
        if src is not None:
            ok, err = _compile_check(src)
            if not ok:
                return {"error": "%s expression syntax error: %s" % (label, err)}
            guard = _expr_guard(src)
            if guard:
                return {"error": "%s expression %s" % (label, guard["error"])}

    # Methods are explicitly-invoked companion commands -- syntax-check only,
    # NO _expr_guard (scene mutation like cmds.connectAttr is legitimate here).
    methods = args.get("methods")
    if methods is not None:
        ok, err = _compile_check(methods)
        if not ok:
            return {"error": "methods source syntax error: %s" % err}

    state = {"node": node}

    def _apply():
        created = None
        warnings = []
        try:
            if not state["node"]:
                cls = get_spec(node_type).get_wrapper_class()
                kwargs = {"name": args["name"]} if args.get("name") else {}
                # build() (NOT create()) seeds the per-type setup source; no
                # setup=True (the all-or-nothing atomicity guard below must not
                # be weakened by build()'s setup-failure-swallow).
                state["node"] = cls.build(**kwargs).get_name()
                created = state["node"]
            w = _wrap(state["node"])

            added_in = []
            for s in (args.get("inputs") or []):
                w.add_input_attr(s["name"], s["type"],
                                 **attr_kwargs(s, _INPUT_EXTRA, warnings))
                added_in.append(s["name"])

            added_out = []
            for s in (args.get("outputs") or []):
                w.add_output_attr(s["name"], s["type"],
                                  **attr_kwargs(s, _OUTPUT_EXTRA, warnings))
                added_out.append(s["name"])

            set_vars = []
            for s in (args.get("variables") or []):
                persistent = bool(s.get("persistent", True))
                w.set_variable(s["name"], _coerce_value(s["value"]),
                               persistent=persistent)
                set_vars.append(s["name"])

            if init is not None:
                w.set_init_expression(init)
            if compute is not None:
                w.set_compute_expression(compute)
            if methods is not None:
                if not hasattr(w, "set_methods_source"):
                    raise ValueError("node type does not support a Methods tab")
                w.set_methods_source(methods)
        except Exception:
            # Atomicity: if THIS call created the node, delete it so a failed
            # define_node never litters the scene with a half-built orphan.
            if created and mc.objExists(created):
                try:
                    mc.delete(created)
                except Exception:
                    pass
            raise

        result = {
            "node": state["node"],
            "added_inputs": added_in,
            "added_outputs": added_out,
            "set_variables": set_vars,
            "set_compute": compute is not None,
            "set_init": init is not None,
            "set_methods": methods is not None,
        }
        if created:
            result["created"] = created
        if warnings:
            result["warnings"] = warnings
        return result

    try:
        res = _do("define_node", ctx, _apply)
    except Exception as exc:
        return {"error": "define_node failed (no node left behind): %s: %s"
                         % (type(exc).__name__, exc)}
    ctx.working_node = res.get("node") or ctx.working_node
    res["schema"] = _node_schema(res["node"])
    return res


def _coerce_value(v: Any) -> Any:
    """Parse a JSON-looking string into its native value.

    Anthropic passes native JSON for ``set_variable.value``; Gemini's schema
    requires every property to be typed, so ``value`` is declared a STRING and
    the model sends JSON *text* (e.g. ``"[1, 2, 3]"``). This makes both paths
    behave the same. Plain words (invalid JSON) are left as-is.
    """
    if isinstance(v, str):
        s = v.strip()
        if s and s[0] in "[{tfn-0123456789.\"":
            try:
                return json.loads(s)
            except Exception:
                return v
    return v


# ---------------------------------------------------------------------------
# Expression safety guard
# ---------------------------------------------------------------------------
# Defense-in-depth: agents must only touch the node being designed. Expressions
# run on EVERY evaluation, so a scene-mutating maya.cmds call in one can corrupt
# or wipe the user's scene (we observed cmds.file(new=True)). Matched only when
# namespaced (cmds./mc./maya.cmds.) to avoid false positives.
_DANGER_FILE = re.compile(
    r"(?:^|[^\w.])(?:cmds|mc|maya\.cmds)\.file\s*\([^)]*"
    r"\b(?:new|open|rename|save|saveAs)\b",
    re.IGNORECASE,
)
_DANGER_CALLS = re.compile(
    r"(?:^|[^\w.])(?:cmds|mc|maya\.cmds)\."
    r"(newFile|quit|delete|createNode|connectAttr|disconnectAttr|parent)\s*\(",
    re.IGNORECASE,
)


def _scan_expression_safety(source: str) -> tuple[bool, str]:
    """Return (ok, forbidden_op). ok=False if the source mutates the scene."""
    src = source or ""
    if _DANGER_FILE.search(src):
        return False, "cmds.file scene operation (new/open/save/rename)"
    m = _DANGER_CALLS.search(src)
    if m:
        return False, "cmds.%s" % m.group(1)
    return True, ""


def _expr_guard(source: str) -> dict | None:
    """Return an error dict if the expression is forbidden, else None."""
    ok, op = _scan_expression_safety(source)
    if ok:
        return None
    return {"error": "refused: the expression contains a forbidden %s call. "
                     "Agents may ONLY read self.<input> and write self.<output> "
                     "on the node being designed -- no scene-wide changes, no "
                     "creating/deleting/connecting other nodes, no new/open/save "
                     "scene. Rewrite the expression without it." % op}


def _compile_check(source: str) -> tuple[bool, str]:
    """Syntax-check WITHOUT executing. ast.parse only (no exec)."""
    import ast

    try:
        ast.parse(source or "")
        return True, ""
    except SyntaxError as exc:
        return False, "line %s: %s" % (exc.lineno, exc.msg)
    except Exception as exc:
        return False, str(exc)


def compact_result(name: str, result: Any) -> str:
    """Compact one-line rendering of a tool result for the chat transcript."""
    if not isinstance(result, dict):
        return "%s -> %r" % (name, result)
    if "error" in result:
        return "%s -> ERROR: %s" % (name, result["error"])
    if "added_inputs" in result:  # define_node
        parts = []
        if result.get("created"):
            parts.append("created %s" % result["created"])
        elif result.get("node"):
            parts.append(result["node"])
        if result.get("added_inputs"):
            parts.append("+%d in" % len(result["added_inputs"]))
        if result.get("added_outputs"):
            parts.append("+%d out" % len(result["added_outputs"]))
        if result.get("set_variables"):
            parts.append("%d vars" % len(result["set_variables"]))
        if result.get("set_compute"):
            parts.append("compute")
        if result.get("set_init"):
            parts.append("init")
        if result.get("set_methods"):
            parts.append("methods")
        line = "define_node -> " + (", ".join(parts) or "ok")
        if result.get("warnings"):
            line += "  [!] " + "; ".join(result["warnings"])
        return line
    if "created" in result:
        return "created %s" % result["created"]
    if "nodes" in result:  # list_nodes
        return "list_nodes -> %d node(s)" % len(result["nodes"])
    for k in ("added_input", "added_output", "set_compute_expression",
              "set_init_expression", "set_osl_expression", "set_methods_source",
              "set_variable", "working_node", "ok"):
        if k in result:
            return "%s -> %s" % (name, result[k])
    return "%s -> ok" % name


def tool_summary(tool_name: str, args: dict) -> str:
    """Short human-readable one-liner for the chat transcript."""
    a = args or {}
    if tool_name == "define_node":
        target = a.get("node") or a.get("node_type", "?")
        n_in = len(a.get("inputs") or [])
        n_out = len(a.get("outputs") or [])
        bits = [target]
        if n_in:
            bits.append("%d in" % n_in)
        if n_out:
            bits.append("%d out" % n_out)
        if a.get("compute"):
            bits.append("compute")
        return "define %s" % " ".join(bits)
    if tool_name == "create_node":
        return "create %s" % a.get("node_type", "?")
    if tool_name in ("add_input", "add_output"):
        return "%s %s (%s%s)" % (
            tool_name, a.get("name", "?"), a.get("type", "?"),
            "[]" if a.get("is_array") else "",
        )
    if tool_name in ("set_compute_expression", "set_init_expression",
                     "set_osl_expression", "set_methods_source"):
        return tool_name
    if tool_name == "set_variable":
        return "set var %s" % a.get("name", "?")
    return tool_name
