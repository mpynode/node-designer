"""SDK-independent ``.mpn``-payload transport for the CLI providers.

The CLI providers (Claude / Gemini / Codex CLI) drive an EXTERNAL agent binary
that CANNOT call back into the live Maya session. The old design bridged them to
the in-Maya tool spine over an MCP HTTP server -- which pulled in the 3rd-party
``mcp`` SDK (pydantic-core Rust wheel, a Windows install headache) as the plugin's
only hard external dependency.

This module replaces that bridge with a dependency-free protocol:

  1. We serialize the user's ACTIVE node and inject it (in the SAME schema the
     model must emit) plus the node cheat-sheet into the prompt.
  2. The agent replies with ONE fenced ``json`` payload -- a ``define_node``-shaped
     object describing the desired node.
  3. We extract that payload and APPLY it by reusing the exact, already-tested
     ``llm.tools.dispatch("define_node", ...)`` spine (safety guard + syntax
     check + undo chunk + atomicity + host refresh), on Maya's MAIN THREAD.

Nothing here imports Qt or ``mcp``; the pure helpers (``extract_payload``,
``to_define_args``, ``build_prompt``) are unit-testable off-thread, and the apply
path is exercised headlessly under ``maya.standalone``.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Fenced block, language tag optional. Mirrors the native porter's fence regex
# so both extractors behave identically.
_FENCE_RE = re.compile(r"```[a-zA-Z0-9+_.-]*[ \t]*\r?\n(.*?)```", re.DOTALL)

# Keys marking a JSON object as a node payload: define_node-shaped OR raw
# ``.mpn`` serialize_node shape. Both accepted, then normalized.
_PAYLOAD_KEYS = frozenset((
    "node", "node_type", "native_type", "name",
    "compute", "expression", "init", "init_source",
    "methods", "methods_source", "osl", "osl_source", "viewport", "viewport_source",
    "inputs", "outputs", "input_attrs", "output_attrs",
    "variables", "stored_vars",
))


# ---------------------------------------------------------------------------
# Extraction  (pure)
# ---------------------------------------------------------------------------


def _try_json_object(text: str):
    """Parse ``text`` into a JSON dict, tolerating trailing/leading prose.

    Tries a straight ``json.loads`` first; on failure, falls back to the span
    from the first ``{`` to the last ``}`` (models sometimes wrap the object in
    a sentence even inside a fence). Returns a dict or ``None``.
    """
    if not text:
        return None
    s = text.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        try:
            obj = json.loads(s[i:j + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _looks_like_payload(obj) -> bool:
    return isinstance(obj, dict) and any(k in obj for k in _PAYLOAD_KEYS)


def extract_payload(text: str):
    """Pull the node payload out of an agent's reply, or return ``None``.

    Prefers the LAST fenced ``json`` block that parses to a node payload (an
    agent may show a draft then a final block); falls back to a bare top-level
    JSON object when the reply wasn't fenced. Returns ``None`` for a pure prose
    answer (a chat turn that changes nothing) so the caller applies nothing.
    """
    if not text:
        return None
    for chunk in reversed(_FENCE_RE.findall(text)):
        obj = _try_json_object(chunk)
        if _looks_like_payload(obj):
            return obj
    obj = _try_json_object(text)
    if _looks_like_payload(obj):
        return obj
    return None


def strip_payload_for_display(text: str) -> str:
    """Return ``text`` with the fenced node payload removed, for showing in the
    chat transcript.

    The ``.mpn``/``define_node`` JSON the agent emits is machine transport (it's
    applied via the tool spine), NOT conversation -- users don't want their chat
    window filled with the raw node definition. This drops every fenced block
    that parses to a node payload, leaving prose and ordinary (non-payload) code
    fences intact. Also strips a bare top-level JSON payload when the whole reply
    was unfenced JSON. Returns the original text unchanged when nothing looks
    like a payload (so API-provider prose, which carries no payload, is
    untouched)."""
    if not text:
        return text
    out = []
    last = 0
    removed = False
    for m in _FENCE_RE.finditer(text):
        obj = _try_json_object(m.group(1))
        if _looks_like_payload(obj):
            out.append(text[last:m.start()])
            last = m.end()
            removed = True
    out.append(text[last:])
    result = "".join(out)
    if not removed:
        # No fenced payload. Guard the unfenced case: if the ENTIRE reply is a
        # bare JSON payload object, drop it too; otherwise leave prose intact.
        if _looks_like_payload(_try_json_object(text)):
            return ""
        return text
    # Collapse the blank gap the removal leaves behind.
    result = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# Normalization  (pure)  --  any accepted shape -> define_node args
# ---------------------------------------------------------------------------


def _norm_attr_list(spec) -> list:
    """Normalize an inputs/outputs spec to a list of define_node attr items.

    Accepts either a define_node-shaped list ``[{name, type, ...}]`` or a raw
    ``.mpn`` attr map ``{name: {attr_type, is_array, ...}}`` and returns the
    list form ``[{name, type, is_array?, min?, max?, default?}]``.
    """
    out: list = []
    if isinstance(spec, dict):
        # Raw .mpn attr map (name -> meta). Preserve authored add-order.
        items = sorted(spec.items(),
                       key=lambda kv: (kv[1].get("order", 1_000_000)
                                       if isinstance(kv[1], dict) else 0, kv[0]))
        for name, meta in items:
            meta = meta if isinstance(meta, dict) else {}
            item = {"name": name,
                    "type": meta.get("attr_type") or meta.get("type") or "float"}
            if meta.get("is_array"):
                item["is_array"] = True
            for k_src, k_dst in (("min_value", "min"), ("max_value", "max"),
                                 ("default_value", "default"),
                                 ("enum_names", "enum_names")):
                if meta.get(k_src) is not None:
                    item[k_dst] = meta[k_src]
            out.append(item)
        return out
    if isinstance(spec, list):
        for meta in spec:
            if not isinstance(meta, dict) or not meta.get("name"):
                continue
            item = {"name": meta["name"],
                    "type": meta.get("type") or meta.get("attr_type") or "float"}
            if meta.get("is_array"):
                item["is_array"] = True
            for k in ("min", "max", "default", "enum_names"):
                if meta.get(k) is not None:
                    item[k] = meta[k]
            # Anything else the model wrote rides through UNCHANGED, so that
            # tools.py stays the single place deciding what a key means. This
            # was a whitelist, and the drop was silent: enum_names never
            # reached the apply layer, the plug came out as a bare False/True
            # enum, and the model -- seeing a clean result -- reported success.
            for k, v in meta.items():
                if k not in item and k != "attr_type":
                    item[k] = v
            out.append(item)
    return out


def _norm_vars(spec, persistent_names=None) -> list:
    """Normalize a variables spec to define_node ``[{name, value, persistent}]``."""
    out: list = []
    pset = set(persistent_names or [])
    if isinstance(spec, dict):
        for name, value in spec.items():
            out.append({"name": name, "value": value,
                        "persistent": (name in pset) if persistent_names else True})
        return out
    if isinstance(spec, list):
        for meta in spec:
            if isinstance(meta, dict) and meta.get("name") is not None:
                item = {"name": meta["name"], "value": meta.get("value")}
                if "persistent" in meta:
                    item["persistent"] = bool(meta["persistent"])
                out.append(item)
    return out


def _first_present(payload: dict, *keys):
    """Return the first key's value that is present (not None), else None."""
    for k in keys:
        if payload.get(k) is not None:
            return payload[k]
    return None


def to_define_args(payload: dict, node_name: str | None = None) -> dict:
    """Map an accepted payload onto ``define_node`` tool args (pure).

    Targeting:
      * an explicit ``node`` (name) -> EDIT that node;
      * else ``node_type`` / ``native_type`` -> CREATE a new node;
      * else fall back to the active ``node_name`` (edit it).
    Source tiers, attrs and variables are pulled from either the define_node
    field names (``compute``/``inputs``/...) or the raw ``.mpn`` names
    (``expression``/``input_attrs``/...).
    """
    p = dict(payload or {})
    args: dict[str, Any] = {}

    if p.get("node"):
        args["node"] = p["node"]
    elif p.get("node_type") or p.get("native_type"):
        args["node_type"] = p.get("node_type") or p.get("native_type")
    elif node_name:
        args["node"] = node_name

    if p.get("name"):
        args["name"] = p["name"]

    inputs = _norm_attr_list(_first_present(p, "inputs", "input_attrs"))
    if inputs:
        args["inputs"] = inputs
    outputs = _norm_attr_list(_first_present(p, "outputs", "output_attrs"))
    if outputs:
        args["outputs"] = outputs
    variables = _norm_vars(_first_present(p, "variables", "stored_vars"),
                           p.get("persistent_vars"))
    if variables:
        args["variables"] = variables

    compute = _first_present(p, "compute", "expression")
    if compute is not None:
        args["compute"] = compute
    init = _first_present(p, "init", "init_source")
    if init is not None:
        args["init"] = init
    methods = _first_present(p, "methods", "methods_source")
    if methods is not None:
        args["methods"] = methods
    return args


def payload_osl(payload: dict):
    """The OSL source in a payload (define_node has no OSL field), or None."""
    return _first_present(payload or {}, "osl", "osl_source")


def summary_line(payload: dict) -> str:
    """Short human label for the toolStarted line, e.g. ``apply mPyNode 2 in``."""
    p = payload or {}
    target = p.get("node") or p.get("node_type") or p.get("native_type") or "node"
    bits = [str(target)]
    n_in = len(_norm_attr_list(_first_present(p, "inputs", "input_attrs")))
    n_out = len(_norm_attr_list(_first_present(p, "outputs", "output_attrs")))
    if n_in:
        bits.append("%d in" % n_in)
    if n_out:
        bits.append("%d out" % n_out)
    if _first_present(p, "compute", "expression") is not None:
        bits.append("compute")
    return "apply %s" % " ".join(bits)


# ---------------------------------------------------------------------------
# Prompt composition  (pure-ish -- reads the active node via the wrapper)
# ---------------------------------------------------------------------------

_PAYLOAD_REMINDER = (
    "RESPOND WITH EXACTLY ONE fenced ```json code block containing the node "
    "payload (schema above), and NOTHING else that looks like JSON. To EDIT the "
    "active node, set \"node\" to its exact name (shown above) and include its "
    "FULL desired definition (all inputs/outputs/compute/init you want it to "
    "have -- existing attributes are kept, new ones are added; attributes are "
    "never deleted). To BUILD A NEW node instead, set \"node_type\" (and OMIT "
    "\"node\"). After the block, add AT MOST 1-2 short sentences describing what "
    "you built and how to drive it. Do NOT call any tools, read files, or run "
    "commands -- you have none; the JSON payload IS how the node is applied."
)


def _serialized_to_display_payload(serialized: dict, node_name: str) -> dict:
    """Render a ``serialize_node`` payload as a define_node-shaped dict for the
    prompt, so the model sees the active node in the exact schema it must emit."""
    disp: dict[str, Any] = {"node": node_name,
                            "node_type": serialized.get("native_type")}
    inputs = _norm_attr_list(serialized.get("input_attrs"))
    if inputs:
        disp["inputs"] = inputs
    outputs = _norm_attr_list(serialized.get("output_attrs"))
    if outputs:
        disp["outputs"] = outputs
    if serialized.get("expression"):
        disp["compute"] = serialized["expression"]
    if serialized.get("init_source"):
        disp["init"] = serialized["init_source"]
    if serialized.get("methods_source"):
        disp["methods"] = serialized["methods_source"]
    if serialized.get("osl_source"):
        disp["osl"] = serialized["osl_source"]
    return disp


def node_context_block(node_name: str | None) -> str:
    """A prompt block describing the active node (its current definition in the
    payload schema), or the scene's mPy nodes when none is active. Best-effort:
    returns ``""`` if nothing can be read. Touches Maya, so call on the main /
    GUI thread (the panel captures the active node there before ``send``)."""
    if node_name:
        try:
            import mpynode
            from mpynode._common.io import mpn_io

            w = mpynode.wrap_node(node_name)
            if w is not None:
                serialized = mpn_io.serialize_node(w, include_persistent=False)
                disp = _serialized_to_display_payload(serialized, node_name)
                return (
                    "ACTIVE NODE -- the user is currently editing `%s` (type "
                    "`%s`). Its current definition, in the payload schema:\n"
                    "```json\n%s\n```\n"
                    "If the request is to change THIS node, edit the payload "
                    "above (keep \"node\": \"%s\") and return the full updated "
                    "definition." % (node_name, serialized.get("native_type"),
                                     json.dumps(disp, indent=2), node_name))
        except Exception:
            pass
    # No active node -- list the mPy nodes in the scene so the model can target
    # one by name instead of building an orphan.
    try:
        names = _scene_node_names()
        if names:
            return ("No node is active. Existing mPy nodes in the scene "
                    "(edit one by setting \"node\" to its name, or build a new "
                    "one with \"node_type\"):\n  " + "\n  ".join(names))
    except Exception:
        pass
    return ""


def _scene_node_names() -> list:
    import maya.cmds as mc
    from mpynode._node_registry import REGISTRY

    try:
        known = set(mc.allNodeTypes() or [])
    except Exception:
        known = None
    seen: list = []
    for t in REGISTRY:
        if known is not None and t not in known:
            continue
        for n in (mc.ls(type=t, long=False) or []):
            label = "%s (%s)" % (n, t)
            if label not in seen:
                seen.append(label)
    return sorted(seen)


def build_prompt(user_text: str, node_name: str | None = None) -> str:
    """Compose the full CLI prompt: cheat-sheet + active-node context + request
    + the single-payload reminder. One string for all three CLI providers."""
    from mpynode.ui.llm import system_prompt

    parts = [system_prompt.build_payload_system_prompt()]
    ctx = node_context_block(node_name)
    if ctx:
        parts.append(ctx)
    parts.append("USER REQUEST:\n" + (user_text or ""))
    parts.append(_PAYLOAD_REMINDER)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Apply  (main thread)  --  reuse the tested define_node spine
# ---------------------------------------------------------------------------


def _existing_attr_names(target: str):
    """(input_names, output_names) already on ``target`` -- so a full-definition
    edit payload can skip re-adding them (add_input_attr on an existing name
    would abort the whole define_node)."""
    ins: set = set()
    outs: set = set()
    try:
        import mpynode

        w = mpynode.wrap_node(target)
        if w is not None:
            try:
                ins = set((w.get_input_attr_map() or {}).keys())
            except Exception:
                pass
            try:
                outs = set((w.get_output_attr_map() or {}).keys())
            except Exception:
                pass
    except Exception:
        pass
    return ins, outs


def apply_payload(node_name: str | None, payload: dict, ctx) -> dict:
    """Apply a node payload via the tested define_node spine. MUST run on Maya's
    main thread (touches ``maya.cmds`` + the wrapper API through ``tools``).

    Returns the define_node result dict (``{node, added_inputs, ...}`` or
    ``{"error": ...}``). Never raises -- the tool layer converts exceptions to
    ``{"error": ...}`` so the client can surface a clean finish line.
    """
    import maya.cmds as mc

    from mpynode.ui.llm import tools

    args = to_define_args(payload, node_name)

    # Editing an existing node: drop attrs it already has so a full-definition
    # payload doesn't abort on re-adding them (additive edit -- never deletes).
    target = args.get("node")
    if target and mc.objExists(target):
        existing_in, existing_out = _existing_attr_names(target)
        if args.get("inputs"):
            args["inputs"] = [a for a in args["inputs"]
                              if a.get("name") not in existing_in]
        if args.get("outputs"):
            args["outputs"] = [a for a in args["outputs"]
                               if a.get("name") not in existing_out]

    result = tools.dispatch("define_node", args, ctx)
    if not isinstance(result, dict) or "error" in result:
        return result if isinstance(result, dict) else {"error": "apply failed"}

    # OSL is not a define_node field; apply it as a follow-up on the resolved
    # node (capability-gated inside the tool -- a no-op error on non-OSL nodes).
    osl = payload_osl(payload)
    tgt = result.get("node")
    if osl and tgt:
        r2 = tools.dispatch("set_osl_expression", {"node": tgt, "source": osl}, ctx)
        result["set_osl"] = isinstance(r2, dict) and "error" not in r2
    return result


def apply_payload_main_thread(node_name: str | None, payload: dict, ctx) -> dict:
    """``apply_payload`` marshaled onto Maya's main thread (client worker calls
    this). Falls back to an inline call outside Maya (unit tests)."""
    def _call():
        return apply_payload(node_name, payload, ctx)

    try:
        import maya.utils as mu

        return mu.executeInMainThreadWithResult(_call)
    except Exception:
        return _call()


def finalize_turn(client, node_name: str | None, ctx, text: str) -> bool:
    """End-of-turn hook shared by all CLI clients: extract a payload from the
    accumulated reply and apply it, emitting toolStarted/toolFinished on the
    client. Returns True if a payload was applied, False for a pure-chat turn.
    Never raises."""
    try:
        payload = extract_payload(text)
    except Exception:
        payload = None
    if payload is None:
        return False
    try:
        client.toolStarted.emit(summary_line(payload))
    except Exception:
        pass
    try:
        result = apply_payload_main_thread(node_name, payload, ctx)
    except Exception as exc:
        result = {"error": "%s: %s" % (type(exc).__name__, exc)}
    try:
        from mpynode.ui.llm import tools

        client.toolFinished.emit(tools.compact_result("define_node", result))
    except Exception:
        try:
            client.toolFinished.emit("applied")
        except Exception:
            pass
    return True
