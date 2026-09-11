"""``.mpn`` node template I/O.

Captures everything about an mPyNode that can be reconstructed in a
fresh scene:
  * native_type (``mPyNode``, ``mPyConstraint``, etc.)
  * source name (informational only)
  * expression text
  * input attr map (with per-attr ``ui_color`` if set)
  * output attr map
  * stored variables
  * enum_names for enum attrs

On-disk format: a versioned JSON envelope. ``expression`` + attr maps
stay plain readable JSON; ``stored_vars`` is encoded as a single
pickle+compress+base64 string (the same codec the ``_storedVarsData``
plug uses, via ``serialization.encode_stored_vars``) so it round-trips
arbitrary values -- numpy arrays, custom classes, byte blobs, images --
that JSON can't natively represent. Compression (``zlib`` default,
``lzma`` for maximum) keeps the file small.

NOTE: connections to/from other Maya nodes are NOT exported \u2014 the.mpn is a **node template**, not a scene snapshot. To re-wire after
import, use the Connect dialog or a separate scene script.
"""

from __future__ import annotations

import json
from typing import Any

import maya.cmds as mc

MPN_FORMAT_VERSION = 2


def _ordered_attr_items(attr_map: dict):
    """(name, meta) pairs sorted by each meta's ``order`` field (authored
    add-order). The ``.mpn`` stores the attr map ``sort_keys=True`` so its key
    order is alphabetical; re-adding in ``order`` sequence rebuilds the Maya
    plugs (and thus the Channel Box) in the order the author created them.
    Legacy payloads with no ``order`` keep their dict order -- nothing to
    preserve."""
    return sorted(
        (attr_map or {}).items(),
        key=lambda kv: (kv[1].get("order", 1_000_000), kv[0]),
    )


# ---- Capture ----


def serialize_node(py_node, include_persistent: bool = True,
                   include_values: bool = True) -> dict:
    """Build a self-contained payload describing the given mPyNode.

    ``include_persistent`` (default ``True``) controls whether the node's
    persistent stored-variable VALUES are written into the payload. With
    ``include_persistent=False`` the payload carries only the node's
    DEFINITIONS (compute/init/attrs/metadata) and ``stored_vars`` stays ``{}``
    -- a "vanilla" template with no baked data. Default ``True`` keeps existing
    callers byte-identical.

    ``include_values=False`` (the Node Designer's "Declarations only") keeps
    every persistent NAME and drops the data: ``stored_vars`` maps each to
    ``None``, so the restored node has its variables declared and empty, the
    way one created through the API starts."""
    name = py_node.get_name()
    native_type = mc.nodeType(name)
    payload: dict[str, Any] = {
        "native_type": native_type,
        "node_name": name,
        "expression": "",
        "input_attrs": {},
        "output_attrs": {},
        "stored_vars": {},
    }
    try:
        payload["expression"] = py_node.get_compute_expression() or ""
    except Exception:
        pass
    try:
        payload["input_attrs"] = dict(py_node.get_input_attr_map() or {})
    except Exception:
        pass
    try:
        payload["output_attrs"] = dict(py_node.get_output_attr_map() or {})
    except Exception:
        pass
    if include_persistent:
        try:
            payload["stored_vars"] = dict(py_node.get_variables() or {})
        except Exception:
            pass
        if not include_values:
            try:
                names = list(py_node.get_variable_names() or [])
            except Exception:
                names = []
            payload["stored_vars"] = {n: None for n in names}
        # Record which stored vars are persistent (the .mpn's analog of the
        # _storedVarNames plug). Values stay in stored_vars -- the native spec
        # extractor needs the full set; only the persistence TAGS were missing,
        # so restore promoted every var to persistent.
        #
        # Written whenever the node HAS stored vars, even when none of them are
        # persistent: deserialize reads an ABSENT key as "legacy payload, assume
        # all persistent", so omitting an empty list would promote a node whose
        # vars are all session-only -- the common case now that set_variable
        # defaults to persistent=None. A node with no stored vars at all still
        # omits the key, so plain-node payloads stay byte-identical.
        try:
            persistent_names = list(py_node.get_variable_names() or [])
            if persistent_names or payload.get("stored_vars"):
                payload["persistent_vars"] = persistent_names
        except Exception:
            pass
    # Sister source tiers (Init / Viewport / OSL / Methods). Captured only when
    # the wrapper exposes the tier AND it is non-empty -- so a plain node's
    # payload is unchanged, but a node carrying Init or Methods code no longer
    # loses it on save. (Additive + optional: forward/backward compatible, so
    # no MPN_FORMAT_VERSION bump is needed -- a tier-unaware reader ignores the
    # extra keys; this reader .get()s them.)
    for key, getter in _SOURCE_TIERS:
        fn = getattr(py_node, getter, None)
        if fn is None:
            continue
        try:
            val = fn() or ""
        except Exception:
            val = ""
        if val:
            payload[key] = val
    # Per-node metadata (authors/version/license/description). Handled
    # as a separate STRUCTURED key (a dict, like ``stored_vars``) rather than a
    # string source tier. Captured only when the wrapper exposes get_metadata
    # AND it is non-empty -- so a plain node's payload is byte-identical.
    get_meta = getattr(py_node, "get_metadata", None)
    if get_meta is not None:
        try:
            meta = get_meta()
        except Exception:
            meta = None
        try:
            from mpynode._common.lifecycle.metadata_registry import is_empty as _meta_empty
            non_empty = meta is not None and not _meta_empty(meta)
        except Exception:
            non_empty = bool(meta)
        if non_empty:
            payload["metadata"] = dict(meta)
    # API-view blank-line spacing (a structured dict, like ``metadata``).
    # Captured only when NON-EMPTY, and it is empty unless the user has moved a
    # boundary by hand -- so a plain node's payload is byte-identical and every
    # shipped template round-trips exactly as before.
    get_gaps = getattr(py_node, "get_api_gap_spacing", None)
    if get_gaps is not None:
        try:
            gaps = get_gaps()
        except Exception:
            gaps = None
        if gaps:
            payload["api_gap_spacing"] = dict(gaps)
    # Logical class identity (``_pyClass`` dotted import path). Captured only
    # when set -- a plain/root-typed node's payload stays byte-identical.
    get_pc = getattr(py_node, "get_py_class", None)
    if get_pc is not None:
        try:
            pc = get_pc()
        except Exception:
            pc = None
        if pc:
            payload["class_path"] = pc
    return payload


# (payload key, wrapper getter, wrapper setter) for the optional source tiers.
_SOURCE_TIERS = (
    ("init_source", "get_init_expression"),
    ("viewport_source", "get_viewport_expression"),
    ("osl_source", "get_osl_expression"),
    ("methods_source", "get_methods_source"),
)
_SOURCE_TIER_SETTERS = {
    "init_source": "set_init_expression",
    "viewport_source": "set_viewport_expression",
    "osl_source": "set_osl_expression",
    "methods_source": "set_methods_source",
}


# ---- Disk envelope ----


def save_mpn(payload: dict, path: str, compression: str = "zlib") -> None:
    """Write a payload to disk as a ``.mpn`` file.

    ``expression`` + attr maps are written as readable JSON;
    ``stored_vars`` is encoded as a pickle+compress+base64 string so it
    handles arbitrary Python values. ``compression``: ``"zlib"``
    (default), ``"lzma"`` (maximum), or ``"none"``.
    """
    from mpynode._common.io import serialization

    data = dict(payload)
    stored = dict(data.get("stored_vars") or {})
    data["stored_vars"], _dropped = serialization.encode_stored_vars_resilient(
        stored, compression=compression
    )
    envelope = {"version": MPN_FORMAT_VERSION, "data": data}
    with open(path, "w") as f:
        json.dump(envelope, f, indent=2, sort_keys=True)


def _read_envelope_data(path: str) -> dict:
    """Open a ``.mpn`` file, parse its JSON envelope, validate the version, and
    return the ``data`` dict -- WITHOUT touching ``stored_vars``.

    Shared envelope+version-validation prelude used by both :func:`load_mpn`
    (which then decodes ``stored_vars``) and :func:`load_mpn_header` (which does
    NOT). Raises ``ValueError`` on a bad envelope / version mismatch."""
    with open(path, "r") as f:
        envelope = json.load(f)
    if not isinstance(envelope, dict):
        raise ValueError(f"{path!r}: envelope is not a JSON dict")
    version = envelope.get("version")
    if version != MPN_FORMAT_VERSION:
        raise ValueError(
            f"{path!r}: unsupported version {version!r} (expected "
            f"{MPN_FORMAT_VERSION})"
        )
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"{path!r}: payload missing or not a dict")
    return data


def load_mpn(path: str, return_failures: bool = False, trusted=None, prompt_fn=None):
    """Read a ``.mpn`` file and return the payload dict (``stored_vars``
    decoded back to a live dict). Raises ``ValueError`` on a bad envelope
    / version mismatch.

    Decoding stored vars is GRACEFUL: any value that can't be
    reconstructed (e.g. a class instance whose class isn't importable
    here) is skipped and the rest still load. With
    ``return_failures=True`` the call returns ``(data, failures)`` where
    ``failures`` is ``{var_name: reason}`` for the skipped values.

    SECURITY: a ``.mpn`` can carry pickled stored vars, and ``pickle.loads``
    on an untrusted file is remote code execution. A ``.mpn`` load is NOT a
    Maya scene open, so no scene callback resolves trust for it -- this
    function resolves a per-file pickle-trust decision itself (the path is
    known) and passes it SCOPED into the decode, instead of relying on the
    ambient per-scene flag (which is ``True`` for an authored session). It
    never mutates the scene's trust. ``trusted`` (bool) forces the decision;
    otherwise, if the file has pickle, ``prompt_fn(path) -> "yes"|"no"|
    "always_file"|"always_folder"`` is consulted (``None`` => fail closed /
    refuse, e.g. headless or non-UI callers)."""
    from mpynode._common.io import serialization

    data = _read_envelope_data(path)
    sv = data.get("stored_vars")
    failures: dict = {}
    if isinstance(sv, str):
        if trusted is None:
            # Resolve per-file: a pickle-free .mpn is trivially safe (no
            # prompt); a pickle-bearing one needs a trust decision.
            if serialization.blob_has_pickle(sv):
                from mpynode._common.io import trust

                trusted = trust.resolve_for_open(path, True, prompt_fn=prompt_fn)
            else:
                trusted = True
        data["stored_vars"], failures = serialization.decode_stored_vars_detailed(
            sv, trusted=trusted
        )
    elif not isinstance(sv, dict):
        data["stored_vars"] = {}
    if return_failures:
        return data, failures
    return data


def load_mpn_header(path: str) -> dict:
    """Read a ``.mpn`` file's raw JSON envelope and return its ``data`` dict
    WITHOUT decoding ``stored_vars``.

    SECURITY: this is the safe, no-pickle accessor for metadata-only reads
    (``native_type`` and any future banner / ``metadata`` read). It parses the
    raw JSON envelope only -- it NEVER calls
    ``serialization.decode_stored_vars_detailed``, NEVER imports ``trust``, and
    NEVER prompts. ``stored_vars`` is returned exactly as it sits on disk (the
    encoded string, or a dict for an unencoded payload). Use this -- not
    ``load_mpn`` -- when scanning many ``.mpn`` files, so a bulk scan can never
    silently ``pickle.loads`` an untrusted template.

    Raises ``ValueError`` on a bad envelope / version mismatch (same contract
    as :func:`load_mpn`)."""
    return _read_envelope_data(path)


# ---- Reconstruct ----


def _source_name_node_name(payload):
    """The scene node name a template create should use (its ``node_name``),
    or None when there is no usable one (-> Maya's default type-based name, no
    behaviour change). Node names are already clean identifiers; the sanitize
    is defensive (Maya node names must start with a letter/underscore)."""
    try:
        sn = (payload or {}).get("node_name")
    except Exception:
        sn = None
    if not isinstance(sn, str) or not sn.strip():
        return None
    import re

    cleaned = re.sub(r"\W", "_", sn.strip())
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = "_" + cleaned
    return cleaned or None


def deserialize_node(
    payload: dict, name: str | None = None, return_failures: bool = False,
    restore_persistent: bool = True, skip_selection: bool = False,
):
    """Recreate an mPyNode from a payload. Returns the wrapper instance.

    ``name`` overrides the node name (else Maya picks one based on the
    native_type).

    ``skip_selection=True`` creates the node without selecting it
    (``skipSelect=True``); default False keeps Maya's select-on-create.

    With ``return_failures=True`` the call returns ``(py_node, failures)``
    where ``failures`` is ``{tier_key: reason_str}`` for any sister source
    tier (init/viewport/osl/methods) that did NOT cleanly restore -- a
    setter exception, a setter returning False (e.g. a syntax-error
    methods source whose text IS still persisted but failed to validate),
    or the wrapper lacking the setter for a tier present in the payload
    (the silent-drop case). The default (``return_failures=False``) keeps the
    legacy contract -- a bare ``py_node`` -- so existing callers (the
    ``_ImportNodeCommand`` production caller and the test callers) stay green;
    only opt-in callers see the ``(py_node, failures)`` tuple. Mirrors
    ``load_mpn``'s opt-in failure channel.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    native_type = payload.get("native_type")
    if not native_type:
        raise ValueError("payload missing native_type")

    # No explicit name? Name the node after the template's short class name
    # (source_name) so a scene node is demo-relevant -- e.g. gameOfLifeMesh1
    # instead of the generic base type mPyMesh1 -- matching the compiled plugin
    # type (already _sanitize_ident(source_name)). Every create path funnels
    # through here (UI commands, File>Import .mpn, the audit harness), so this is
    # the single place that fixes it. Callers with a preferred_name pass it as
    # `name`, which still wins (e.g. the dnet template keeps "mPyDnet").
    if not name:
        name = _source_name_node_name(payload)

    # Use the wrap_node + create path so we go through the proper
    # plugin loader.
    from mpynode._node_registry import wrap_node

    plugin_name = None
    try:
        from mpynode._node_registry import get_spec

        spec = get_spec(native_type)
        plugin_name = spec.plugin_name if spec else None
    except Exception:
        pass
    # Bypass _CreateNodeCommand here \u2014 the import dialog itself wraps
    # this whole call in _ImportNodeCommand for undo coverage.
    if plugin_name:
        try:
            if not mc.pluginInfo(plugin_name, query=True, loaded=True):
                mc.loadPlugin(plugin_name, quiet=True)
        except Exception:
            pass
    # Create the node.
    if name:
        new_name = mc.createNode(native_type, name=name, skipSelect=skip_selection)
    else:
        new_name = mc.createNode(native_type, skipSelect=skip_selection)
    py_node = wrap_node(new_name, native_type)

    # Create-time scene wiring the wrapper's own create() would have done but
    # this path skips (it goes straight to cmds.createNode) -- e.g. mPyFile's
    # always-on time1.outTime -> _timeIn, without which a gallery/.mpn node
    # never advances in time. Opt-in per wrapper, best-effort, and only ever on
    # the node we JUST created, so nothing existing can be clobbered.
    hook = getattr(py_node, "_wire_on_create", None)
    if hook is not None:
        try:
            hook()
        except Exception:
            pass

    return apply_payload_to_node(
        py_node, payload, restore_persistent=restore_persistent,
        return_failures=return_failures,
    )


def apply_payload_to_node(
    py_node, payload: dict, restore_persistent: bool = True,
    return_failures: bool = False,
):
    """Restore a payload's DEFINITIONS -- input/output attrs, stored vars, the
    sister source tiers (Init/Viewport/OSL/Methods), per-node metadata, and the
    Compute expression -- onto an ALREADY-CREATED node.

    Split out of :func:`deserialize_node` (which creates the node via
    ``createNode`` then calls this) so callers that must create + WIRE the node
    themselves first can still seed it. The right-click "Create + run setup"
    path uses this: it builds a deformer / IK solver via ``cmds.deformer`` /
    ``ikHandle`` (so the node is attached to the scene) and then seeds the
    type's template expression/attrs onto that attached node.

    ``return_failures=True`` returns ``(py_node, {tier_key: reason})`` for any
    sister tier that did not cleanly restore (same contract as
    :func:`deserialize_node`)."""
    # A legacy payload can carry an attr whose name has since become a
    # framework slot. The add-attr guard RAISES on that name, which would abort
    # the restore mid-way and leave a half-built node, so mark an
    # attr-surgery window: inside it the guard degrades to a warning and the
    # node still loads whole (same downgrade ``_reorder_attrs`` relies on).
    from mpynode._common.lifecycle import scene_state as scene_io
    scene_io.begin_attr_surgery()
    try:
        # Restore input attrs (in authored add-order, not the .mpn's alphabetical
        # key order, so the rebuilt plugs / Channel Box match the original).
        for attr_name, meta in _ordered_attr_items(payload.get("input_attrs")):
            attr_type = meta.get("attr_type", "float")
            is_array = bool(meta.get("is_array", False))
            enum_names = meta.get("enum_names")
            limits = {
                "min_value": meta.get("min_value"),
                "max_value": meta.get("max_value"),
                "default_value": meta.get("default_value"),
            }
            # sparse is array-only; absent => dense (the default read). Restore the
            # flag only when present so legacy payloads stay dense.
            sp_kw = {"sparse": bool(meta["sparse"])} \
                if is_array and "sparse" in meta else {}
            # packed is array-only and is the plug KIND, so a payload carrying it
            # MUST restore it -- otherwise the attr silently returns as a numeric
            # multi and the table write is back to one setAttr per element.
            if is_array and meta.get("packed"):
                sp_kw["packed"] = True
            try:
                py_node.add_input_attr(
                    attr_name, attr_type, is_array, enum_names=enum_names,
                    **limits, **sp_kw
                )
            except TypeError:
                # Older add API without enum_names / numeric limits; fall back.
                try:
                    py_node.add_input_attr(attr_name, attr_type, is_array, enum_names=enum_names)
                except TypeError:
                    py_node.add_input_attr(attr_name, attr_type, is_array)
            # Restore custom UI color if present.
            ui_color = meta.get("ui_color")
            if ui_color:
                try:
                    py_node.set_input_attr_color(attr_name, ui_color)
                except Exception:
                    pass

        # Restore output attrs (authored add-order; see input note above).
        for attr_name, meta in _ordered_attr_items(payload.get("output_attrs")):
            attr_type = meta.get("attr_type", "float")
            is_array = bool(meta.get("is_array", False))
            enum_names = meta.get("enum_names")
            limits = {
                "min_value": meta.get("min_value"),
                "max_value": meta.get("max_value"),
                "default_value": meta.get("default_value"),
            }
            try:
                py_node.add_output_attr(
                    attr_name, attr_type, is_array, enum_names=enum_names,
                    **limits
                )
            except TypeError:
                try:
                    py_node.add_output_attr(attr_name, attr_type, is_array, enum_names=enum_names)
                except TypeError:
                    py_node.add_output_attr(attr_name, attr_type, is_array)
            ui_color = meta.get("ui_color")
            if ui_color:
                try:
                    py_node.set_output_attr_color(attr_name, ui_color)
                except Exception:
                    pass
    finally:
        scene_io.end_attr_surgery()

    # Restore stored variables. Gated by ``restore_persistent`` -- with it False
    # the reconstructed node carries only its DEFINITIONS (a "vanilla" node), no
    # baked persistent data. Default True keeps the legacy contract.
    if restore_persistent:
        # Honor the recorded persistence set so a session-only var isn't promoted
        # to persistent on restore. A legacy .mpn with no "persistent_vars" key
        # falls back to all-persistent (the prior behavior), so old templates load
        # unchanged.
        persistent_vars = payload.get("persistent_vars")
        # Surgery window: a var whose name collides with a framework slot is
        # only WARNED about here (never rejected), so a legacy payload still
        # restores with its value intact. Re-entrant, so an enclosing window
        # is unaffected.
        from mpynode._common.lifecycle import scene_state

        scene_state.begin_attr_surgery()
        try:
            for var_name, value in (payload.get("stored_vars") or {}).items():
                is_persistent = True if persistent_vars is None else (var_name in persistent_vars)
                try:
                    py_node.set_variable(var_name, value, persistent=is_persistent)
                except Exception:
                    pass
        finally:
            scene_state.end_attr_surgery()

    # Restore the sister source tiers (Init / Viewport / OSL / Methods) when
    # present + supported. Done before Compute so Init is in place first.
    # Failures are collected per-tier and reported via the opt-in
    # ``return_failures`` channel -- a setter exception, a False return (text
    # persisted but didn't validate, e.g. a syntax error), or the wrapper
    # missing the setter altogether (F12 / F13). Reasons stay plain strings
    # so the channel is JSON/marshal-friendly across the command boundary.
    tier_failures: dict = {}
    for key, setter in _SOURCE_TIER_SETTERS.items():
        val = payload.get(key)
        if not val:
            continue
        fn = getattr(py_node, setter, None)
        if fn is None:
            # F13: wrapper does not support this tier -- silent drop is the bug.
            tier_failures[key] = (
                "node type does not support this tier (no %s)" % setter
            )
            continue
        ok = True
        reason = None
        try:
            ok = fn(val)
        except Exception as exc:
            ok = False
            reason = str(exc)
        if ok is False:
            # F12: setter returned False (no exception) -- e.g. text was
            # persisted but failed to validate. Surface it instead of dropping.
            if reason is None:
                reason = "stored but did not validate (e.g. syntax error)"
            tier_failures[key] = reason

    # Restore per-node metadata (a structured dict, NOT a string source tier).
    metadata = payload.get("metadata")
    if metadata and isinstance(metadata, dict):
        set_meta = getattr(py_node, "set_metadata", None)
        if set_meta is not None:
            try:
                set_meta(metadata)
            except Exception:
                pass

    # Restore the API view's blank-line spacing (structured, like metadata).
    gaps = payload.get("api_gap_spacing")
    if gaps and isinstance(gaps, dict):
        set_gaps = getattr(py_node, "set_api_gap_spacing", None)
        if set_gaps is not None:
            try:
                set_gaps(gaps)
            except Exception:
                pass

    # Restore the logical class identity (``_pyClass``). Stamps the plug on the
    # (root-typed) wrapper; a later re-wrap upgrades to the subclass via
    # import-on-wrap. No-op when the payload has no py_class.
    py_class = payload.get("class_path")
    if py_class:
        # Synthesize the in-memory class so the immediate re-wrap upgrades to it
        # (mpynode_user classes only; external modules import normally).
        try:
            if py_class.startswith("mpynode_user."):
                from mpynode._common.io.user_classes import synthesize
                synthesize(py_class.rpartition(".")[2],
                           payload.get("native_type"))
        except Exception:
            pass
        set_pc = getattr(py_node, "set_py_class", None)
        if set_pc is not None:
            try:
                set_pc(py_class)
            except Exception:
                pass

    # Restore expression LAST (after attrs are in place so compute can run).
    expression = payload.get("expression") or ""
    if expression:
        try:
            py_node.set_compute_expression(expression)
        except Exception:
            pass

    if return_failures:
        return py_node, tier_failures
    return py_node
