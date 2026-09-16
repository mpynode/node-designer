"""Scene-change lifecycle callbacks — split out of ``init_registry.py``
(behavior unchanged).

Owns the scene-message callback handlers (open / new / import / reference /
save / export) that:

 * wipe + repopulate the per-node Init namespace registry on scene change;
 * hydrate/flush the deferred stored-var cache;
 * resolve pickle-trust once on the main thread (delegated to ``trust_prompt``).

This module IMPORTS the live registry dict objects from the sibling
``init_registry`` (one-way edge — do NOT import ``scene_callbacks`` back into
``init_registry``) and the trust resolver from ``trust_prompt``.
"""

from __future__ import annotations

import sys

import maya.OpenMaya as om

# Live registry objects owned by init_registry (shared, mutated here).
from .init_registry import (
    _INIT_BINDINGS,
    _INIT_TRACKED_NODE_TYPES,
    _NODE_INIT_NS,
    has_init_expression,
    register_init_source,
)
from .trust_prompt import _resolve_pickle_trust

# The aliased per-target weight multi, taken from the Maya-free SSOT rather than
# spelled again here -- the wrapper and the codegen desugar both key off it.
try:
    from mpynode._common.interface.morph_method_interface import WEIGHT_PLUG

    _WEIGHT_ELEM_PREFIX = WEIGHT_PLUG + "["
except Exception:  # pragma: no cover - interface always importable in practice
    _WEIGHT_ELEM_PREFIX = "weight["


def _register_init_sources_for_tracked(only_new: bool = False) -> tuple[int, int, int]:
    """Walk every JIT-capable node in the scene and register its ``_initSource``
    namespace (with legacy ``_jitSource`` fallback + migration). Returns
    ``(loaded, failed, migrated)``.

    Shared by the scene-OPEN sweep (``_on_scene_opened``) and the
    scene-IMPORT sweep (``_on_after_import``) so the two lifecycle paths can
    NOT drift -- a previous divergence (import never registered init sources)
    caused ``NameError: name 'np' is not defined`` from imported nodes whose
    Init code did ``import numpy as np``.

    ``only_new=True`` (the IMPORT path) skips nodes whose init namespace is
    already registered, so re-importing into a populated scene doesn't re-run
    the Init code of nodes that are already live (which could rebuild kernels
    or clobber runtime stored-var state). The OPEN path uses
    ``only_new=False`` (fresh scene -- register everything)."""
    try:
        from maya import cmds
    except Exception:
        return (0, 0, 0)
    # Pre-filter to known types, else "Unknown object type: mPyX" warnings.
    try:
        known_types = set(cmds.allNodeTypes() or [])
    except Exception:
        known_types = None
    loaded   = 0
    failed   = 0
    migrated = 0
    for node_type in _INIT_TRACKED_NODE_TYPES:
        if known_types is not None and node_type not in known_types:
            continue
        try:
            nodes = cmds.ls(type=node_type) or []
        except Exception:
            continue
        for node in nodes:
            try:
                # IMPORT path: leave already-registered (live) nodes alone.
                if only_new and has_init_expression(node):
                    continue
                src = ""
                has_new = cmds.attributeQuery(
                    "_initSource", node=node, exists=True
                )
                has_old = cmds.attributeQuery(
                    "_jitSource", node=node, exists=True
                )
                if has_new:
                    src = cmds.getAttr(f"{node}._initSource") or ""
                elif has_old:
                    src = cmds.getAttr(f"{node}._jitSource") or ""
                    migrated += 1
                if not src.strip():
                    continue
                if register_init_source(node, src):
                    loaded += 1
                else:
                    failed += 1
            except Exception as exc:
                sys.stderr.write(
                    f"[init_registry] {node!r}: init_source load "
                    f"failed: {exc}\n"
                )
                failed += 1
    return (loaded, failed, migrated)


# Cap on the per-collision lines in the scene-open report: a wall of warnings
# gets ignored, which defeats the point of warning at all.
_COLLISION_REPORT_LIMIT = 20


def _scan_reserved_name_collisions():
    """Every user attr / stored var in the CURRENT scene whose name is reserved
    by the framework, as ``(node_type, node, kind, name, reason)`` tuples.

    Topology only: three small string-plug reads per node (the two attr maps
    plus the persistent-var registry). No stored-var value is decoded and
    nothing is evaluated, so this can never trigger a compute. The reserved set
    is resolved ONCE per node TYPE, not per node. Never raises."""
    hits = []
    try:
        from maya import cmds

        from mpynode._common.interface.reserved_names import (
            RESERVED_PREFIXES,
            check_reserved_name,
            known_types,
            reserved_names_for_type,
        )
        from mpynode._common.io.serialization import decode_attr_map
        from mpynode._common.storedvars.stored_vars_api import get_variable_names
    except Exception:
        return hits
    # Same pre-filter as the init sweep.
    try:
        registered = set(cmds.allNodeTypes() or [])
    except Exception:
        registered = None
    for node_type in known_types():
        if registered is not None and node_type not in registered:
            continue
        try:
            nodes = cmds.ls(type=node_type) or []
        except Exception:
            continue
        if not nodes:
            continue
        reserved = reserved_names_for_type(node_type)
        if not reserved:
            continue  # fail-open: resolver had nothing to say about this type
        for node in nodes:
            candidates = []
            for plug, kind in (("_inputAttrs", "input attr"),
                               ("_outputAttrs", "output attr")):
                try:
                    raw   = cmds.getAttr("{}.{}".format(node, plug)) or ""
                    names = decode_attr_map(raw) if raw else {}
                except Exception:
                    continue
                candidates.extend((kind, n) for n in names)
            try:
                candidates.extend(
                    ("stored var", n) for n in get_variable_names(node)
                )
            except Exception:
                pass
            for kind, name in candidates:
                reason = reserved.get(name)
                if reason is None and name.startswith(RESERVED_PREFIXES):
                    # Rare enough that re-entering the resolver is free.
                    reason = check_reserved_name(name)
                if reason:
                    hits.append((node_type, node, kind, name, reason))
    return hits


def _warn_reserved_name_collisions():
    """Emit ONE consolidated warning for the whole scene. Returns the collision
    count (0 = silent)."""
    hits = _scan_reserved_name_collisions()
    if not hits:
        return 0
    n_nodes = len({h[1] for h in hits})
    lines = [
        "[reserved_names] scene-open scan: %d reserved-name collision(s) on "
        "%d node(s). These names belong to the framework's 'self', so the "
        "user's value can be silently shadowed (or dropped) at compute time:"
        % (len(hits), n_nodes)
    ]
    for node_type, node, kind, name, reason in hits[:_COLLISION_REPORT_LIMIT]:
        lines.append(
            "  %s (%s) %s %r -- %s" % (node, node_type, kind, name, reason)
        )
    if len(hits) > _COLLISION_REPORT_LIMIT:
        lines.append("  ... and %d more" % (len(hits) - _COLLISION_REPORT_LIMIT))
    msg = "\n".join(lines)
    sys.stderr.write(msg + "\n")
    try:
        from mpynode._common.util.log_bus import log as _log

        _log(msg, level="warning")
    except Exception:
        pass
    return len(hits)


def _restore_blend_shape_weights(known_types=None):
    """Re-materialise mPyBlendShape ``weight[]`` elements after a file load.

    ``weight[]`` is a DYNAMIC multi (it has to be a user attr to reach the
    compile spec), and Maya's file writer omits any multi element sitting at the
    attribute DEFAULT. Rig weights rest at 0.0 = the default, so on save EVERY
    element is dropped. The ALIAS table is written separately and survives, so
    the file reloads with aliases pointing at elements that no longer exist and
    the channel box comes up EMPTY -- the node looks like it lost its targets. A
    stock blendShape is immune because its ``weight[]`` is a built-in typed
    attribute, not a dynamic one.

    Reading the plug materialises the element; the keyable flag then has to be
    re-applied because it lived on the element that was dropped. Returns the
    number of elements restored.
    """
    try:
        from maya import cmds
    except Exception:
        return 0
    if known_types is not None and "mPyBlendShape" not in known_types:
        return 0
    try:
        nodes = cmds.ls(type="mPyBlendShape") or []
    except Exception:
        return 0
    if not nodes:
        return 0

    # A repair is not a user edit. Restore the modified flag so reopening a
    # saved scene doesn't come up dirty and prompt to save on close.
    try:
        was_modified = cmds.file(query=True, modified=True)
    except Exception:
        was_modified = True

    n = 0
    for node in nodes:
        try:
            flat = cmds.aliasAttr(node, query=True) or []
        except Exception:
            continue
        for i in range(0, len(flat) - 1, 2):
            plug_part = flat[i + 1]
            if not plug_part.startswith(_WEIGHT_ELEM_PREFIX):
                continue
            plug = "%s.%s" % (node, plug_part)
            try:
                cmds.getAttr(plug)
                cmds.setAttr(plug, keyable=True)
                n += 1
            except Exception:
                pass

    if n and not was_modified:
        try:
            cmds.file(modified=False)
        except Exception:
            pass
    return n


# Set between kBeforeOpen and the end of _on_scene_opened. References loading
# DURING an open are covered by that open's single kAfterOpen trust scan, so
# their own after-handlers stand down and the user isn't prompted twice.
_OPEN_IN_PROGRESS = False
# One createReference can emit several "after" events (kAfterReference +
# kAfterCreateReference); only the first resolves trust.
_REF_RESOLVE_PENDING = False


def _on_scene_change(_unused_client_data):
    """Wipe the namespace + bindings registries on kBeforeOpen /
    kBeforeNew."""
    # Fail pickle-trust CLOSED for the transition so a compute firing mid-open
    # can't decode pickle. The after-event restores it.
    global _OPEN_IN_PROGRESS
    _OPEN_IN_PROGRESS = True
    try:
        from mpynode._common.io import trust

        trust.begin_scene_change()
    except Exception:
        pass
    n_ns   = len(_NODE_INIT_NS)
    n_bind = len(_INIT_BINDINGS)
    if n_ns or n_bind:
        _NODE_INIT_NS.clear()
        _INIT_BINDINGS.clear()
        sys.stderr.write(
            f"[init_registry] cleared {n_ns} init namespace(s) + "
            f"{n_bind} binding set(s) on scene change\n"
        )
    # Drop the decode cache too -- the previous scene's blobs are gone.
    try:
        from mpynode._common.io import serialization as _ser

        _ser.clear_stored_var_decode_cache()
    except Exception:
        pass
    try:
        from mpynode._common.storedvars import stored_var_store as _svs

        _svs.evict_all()
    except Exception:
        pass


def _on_scene_new(_unused_client_data):
    """kAfterNew: a fresh, empty scene is authored content -> pickle-trusted.
    Pairs with the fail-closed ``begin_scene_change`` fired at kBeforeNew."""
    global _OPEN_IN_PROGRESS
    _OPEN_IN_PROGRESS = False
    try:
        from mpynode._common.io import trust

        trust.reset_for_new_scene()
    except Exception:
        pass


def _on_before_import(_unused_client_data):
    """kBeforeImport: fail CLOSED for the import transition (snapshotting the
    prior authored trust) so a mid-import worker compute can't unpickle the
    incoming file before kAfterImport resolves it. Pairs with _on_after_import,
    which reduces trust against the snapshot."""
    try:
        from mpynode._common.io import trust

        trust.begin_import_change()
    except Exception:
        pass


def _on_before_reference(_unused_client_data):
    """kBeforeReference / kBeforeCreateReference / kBeforeLoadReference: fail
    CLOSED for the reference load (referenced .ma data is untrusted-by-default,
    exactly like an import) and arm the dedupe guard. References that load
    during an open are handled by the open's kAfterOpen scan instead."""
    global _REF_RESOLVE_PENDING
    try:
        from mpynode._common.io import trust

        trust.begin_import_change()
    except Exception:
        pass
    _REF_RESOLVE_PENDING = True


def _on_after_reference(_unused_client_data):
    """kAfterReference / kAfterCreateReference / kAfterLoadReference: resolve
    pickle-trust for the referenced data (reduce-only, like import). Stands down
    during a scene open (kAfterOpen covers referenced nodes) and dedupes the
    multiple after-events a single createReference can emit."""
    global _REF_RESOLVE_PENDING
    if _OPEN_IN_PROGRESS:
        _REF_RESOLVE_PENDING = False
        return
    if not _REF_RESOLVE_PENDING:
        return  # already resolved this reference operation
    _REF_RESOLVE_PENDING = False
    # Trust resolution only: referenced plugs are locked, so their stored vars
    # decode per-compute via the gated read path -- this flag is that gate.
    _resolve_pickle_trust(is_import=True)


# One-shot latch for the v1-owns-the-type warning below. Static condition;
# saying it once per session is informative, once per open is noise.
_V1_CONFLICT_WARNED = False


def _upgrade_v1_nodes(nodes=None):
    """Sweep v1 payloads that arrived with this open/import/reference.

    v2 registers the same node TYPE name as v1, so a v1 scene does not yield
    unknown nodes -- Maya builds a v2 mPyNode and replays v1's setAttrs at it.
    The legacy ``expression`` plug catches the one value that used to be
    dropped; this turns it into a real v2 node.

    Warn-only and never raises: an exception here would abort the rest of the
    open and take unrelated panels down with it.
    """
    try:
        from mpynode._common.io import v1_upgrade
    except Exception:
        return

    # Stand-down case: nodes carrying a v1 payload that v2 does not own,
    # because a v1 install won the `mPyNode` type registration and v2's
    # failed. Warn ONCE per session -- it is a static condition, so repeating
    # it on every open would be noise, but staying silent is worse: every
    # Designer panel reads an empty node and nothing says why.
    global _V1_CONFLICT_WARNED
    try:
        foreign = v1_upgrade.find_foreign(nodes)
    except Exception:
        foreign = []
    if foreign and not _V1_CONFLICT_WARNED:
        _V1_CONFLICT_WARNED = True
        sys.stderr.write(
            "[v1_upgrade] STANDING DOWN: %d node(s) carry a v1 payload but "
            "are not owned by v2 (%s). A node-designer v1 install has claimed "
            "the 'mPyNode' node type, so v2's registration failed and these "
            "nodes are served by v1. They are left untouched -- converting "
            "one would break v1's own compute. To use v2, move v1 out of the "
            "Maya plug-in and script paths (plug-ins/mpynode_plugin.py, "
            "plug-ins/_mpynode, scripts/mpylib) and restart Maya."
            % (len(foreign), ", ".join(foreign[:4])) + chr(10))

    try:
        reports, failures = v1_upgrade.upgrade_scene(nodes)
    except Exception as _exc:
        sys.stderr.write("[v1_upgrade] sweep failed: %s" % _exc + chr(10))
        return
    for line in v1_upgrade.summarize(reports, failures):
        sys.stderr.write("[v1_upgrade] %s" % line + chr(10))


def _on_scene_opened(_unused_client_data):
    """Walk every JIT-capable node and register its ``_initSource``
    attribute. Backward-compat: also reads legacy ``_jitSource`` attr
    if present and ``_initSource`` is absent (auto-migration for.ma files written by older versions).

    Polish: pre-filter the tracked type list against
    ``cmds.allNodeTypes()`` so we don't trigger
    ``# Warning: Unknown object type: mPyX`` warnings when an
    mpynode plug-in (api1 or api2) isn't loaded. Common case: user
    opens a scene that only requires mpynode_api1; api2 types
    (mPyMesh / mPyNurbsCurve / mPyNurbsSurface / mPyNode /
    mPyLocator / mPyConstraint) aren't registered with Maya and
    each ``cmds.ls(type=X)`` emits a noisy warning."""
    try:
        from maya import cmds
    except Exception:
        return

    # Resolve pickle-trust ONCE here (main thread), BEFORE any stored-var decode
    # or transform force-eval below, so the worker compute path never prompts.
    _resolve_pickle_trust(is_import=False)

    # If allNodeTypes() fails, fall through unfiltered -- noisy but correct.
    try:
        known_types = set(cmds.allNodeTypes() or [])
    except Exception:
        known_types = None

    # Register every tracked node's init source (shared with the import path).
    loaded, failed, migrated = _register_init_sources_for_tracked(only_new=False)

    if loaded or failed or migrated:
        msg = (
            f"[init_registry] scene-open init load: "
            f"{loaded} loaded, {failed} failed"
        )
        if migrated:
            msg += f" ({migrated} migrated from legacy _jitSource attr)"
        sys.stderr.write(msg + "\n")

    # Rebuild the in-memory mpynode_user classes so ``from mpynode_user import
    # <Class>`` resolves without a bake. Identity is code-free, so a miss is safe.
    try:
        from mpynode._common.io.user_classes import synthesize_from_scene

        synthesize_from_scene()
    except Exception as _exc:
        sys.stderr.write(
            "[init_registry] scene-open class synth failed: %s\n" % _exc)

    # A v1 scene arrives as v2 nodes carrying a legacy payload; convert them
    # before anyone can save over the original and lose the expression.
    #
    # This MUST run before the stored-var hydration below. That pass reads
    # `_storedVarsData` into the cache and then deliberately CLEARS the plug,
    # so an upgrade placed after it finds the v1 payload already gone and
    # silently drops every stored variable. It cannot simply read the cache
    # instead: hydration keys off `_storedVarNames`, which v1 wrote as a
    # base64 pickle where v2 expects a comma-joined string, so the v1 values
    # would not be in the cache either. Converting first means the plugs are
    # in v2's format by the time hydration looks at them, and the normal path
    # takes over from there.
    #
    # Safe this early: set_init_expression registers the Init namespace itself
    # (init_registry.set_init_expression -> register_init_source), so the
    # sweep above having already run is not a problem.
    _upgrade_v1_nodes()

    # Hydrate persistent vars into the store and clear the plug, so the session
    # reads the cache rather than a stale serialized blob.
    try:
        from mpynode._common.storedvars import stored_var_store as _svs

        _svs.load_and_clear_all()
    except Exception as _exc:
        sys.stderr.write(
            f"[init_registry] scene-open stored-var load failed: {_exc}\n"
        )

    # Transform-family nodes write their USER OUTPUTS as a side-effect of
    # asMatrix(), so a downstream pull on open reads stale data until something
    # pulls the matrix. Force a one-shot worldMatrix read -- no TRS touch, so it
    # doesn't flag the scene modified.
    try:
        if known_types is None or "mPyTransform" in known_types:
            for node in cmds.ls(type="mPyTransform") or []:
                try:
                    cmds.getAttr(node + ".worldMatrix[0]")
                except Exception:
                    pass
    except Exception:
        pass

    # Put the aliased blend-shape weights back in the channel box (the file
    # writer drops every element that rests at the 0.0 default).
    try:
        _restore_blend_shape_weights(known_types)
    except Exception as _exc:
        sys.stderr.write(
            "[init_registry] scene-open weight restore failed: %s\n" % _exc)

    # The ONLY diagnostic for a name that collides with a framework 'self' slot
    # without passing an authoring guard -- a compute can create a stored var
    # under ANY name, and a write to a seeded name is absorbed and dropped.
    # Runs last, warns only, never blocks the open.
    try:
        _warn_reserved_name_collisions()
    except Exception as _exc:
        sys.stderr.write(
            f"[reserved_names] scene-open collision scan failed: {_exc}\n"
        )

    # Open finished: later references are interactive and re-resolve trust.
    global _OPEN_IN_PROGRESS
    _OPEN_IN_PROGRESS = False


def _on_after_import(_unused_client_data):
    """Hydrate stored-var plugs AND register init namespaces for freshly
    imported nodes.

    The init registration mirrors the scene-OPEN sweep
    (``_on_scene_opened``). Without it, imported nodes whose Init code does
    ``import numpy as np`` raise ``NameError: name 'np' is not defined`` from
    their expression, because the per-node Init namespace was never registered
    for them (the only fallback -- ``ensure_init_namespace_for_mobject`` -- is
    racy: it bails on worker threads under EM-parallel evaluation, and depends
    on the ``_initSource`` plug already being loaded when a solve/compute fires
    mid-import). Stored vars are hydrated FIRST so Init code can read them."""
    # Resolve pickle-trust for the imported data (main thread) BEFORE decode.
    _resolve_pickle_trust(is_import=True)

    # Same reason as the scene-open path: convert v1 payloads BEFORE the
    # hydration below clears `_storedVarsData`, or their stored variables are
    # lost. Importing a v1 scene is as common as opening one.
    #
    # Deliberately NOT done on kAfterReference: a referenced node's plugs are
    # locked, so the rewrite could not be written, and the edit would not
    # belong to this scene anyway. Reference a v1 scene and it stays v1 --
    # import it, or open and re-save it, to convert.
    _upgrade_v1_nodes()
    try:
        from mpynode._common.storedvars import stored_var_store as _svs

        _svs.load_and_clear_all()
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] after-import stored-var load failed: {exc}\n"
        )
    # only_new: re-running Init on already-live nodes would rebuild kernels and
    # clobber runtime state.
    try:
        loaded, failed, migrated = _register_init_sources_for_tracked(
            only_new=True
        )
        if loaded or failed or migrated:
            msg = (
                f"[init_registry] after-import init load: "
                f"{loaded} loaded, {failed} failed"
            )
            if migrated:
                msg += f" ({migrated} migrated from legacy _jitSource attr)"
            sys.stderr.write(msg + "\n")
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] after-import init load failed: {exc}\n"
        )
    # Rebuild in-memory mpynode_user classes for the imported nodes too.
    try:
        from mpynode._common.io.user_classes import synthesize_from_scene

        synthesize_from_scene()
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] after-import class synth failed: {exc}\n"
        )
    # Imported blend shapes lost their weight elements the same way an opened
    # one did (see _restore_blend_shape_weights).
    try:
        _restore_blend_shape_weights()
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] after-import weight restore failed: {exc}\n"
        )


def _on_before_serialize(_unused_client_data):
    """Flush in-memory stored vars to plugs before save / export so they
    persist in the written file."""
    try:
        from mpynode._common.storedvars import stored_var_store as _svs

        _svs.flush_all()
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] stored-var flush failed: {exc}\n"
        )


def _on_after_serialize(_unused_client_data):
    """Re-clear stored-var plugs after save / export to restore the
    empty-plug session invariant (the data lives in the cache)."""
    try:
        from mpynode._common.storedvars import stored_var_store as _svs

        _svs.clear_loaded_plugs()
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] stored-var re-clear failed: {exc}\n"
        )


_SCENE_CALLBACKS_REGISTERED = False


def register_scene_change_callbacks() -> int:
    """Install kBeforeOpen/kBeforeNew (clear) and kAfterOpen
    (auto-load) callbacks. Idempotent."""
    global _SCENE_CALLBACKS_REGISTERED
    if _SCENE_CALLBACKS_REGISTERED:
        return 0
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED

        last_token = -1
        for event in (
            om.MSceneMessage.kBeforeOpen,
            om.MSceneMessage.kBeforeNew,
        ):
            cb_id = om.MSceneMessage.addCallback(event, _on_scene_change)
            last_token = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterOpen, _on_scene_opened
        )
        last_token = CALLBACK_MANAGER.register(
            cb_id, om.MMessage.removeCallback
        )
        # kAfterNew: a fresh empty scene is authored -> restore pickle-trust.
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterNew, _on_scene_new
        )
        last_token = CALLBACK_MANAGER.register(
            cb_id, om.MMessage.removeCallback
        )
        # Stored-var cache: hydrate on import, flush before save, re-clear after.
        cb_id = om.MSceneMessage.addCallback(
            om.MSceneMessage.kAfterImport, _on_after_import
        )
        last_token = CALLBACK_MANAGER.register(
            cb_id, om.MMessage.removeCallback
        )

        # Import + reference are file-trust boundaries like open: fail CLOSED on
        # "before", resolve on "after". Registered via getattr so a constant
        # missing in some Maya version can't abort the whole registration.
        def _add(event_name, fn):
            nonlocal last_token
            event = getattr(om.MSceneMessage, event_name, None)
            if event is None:
                return
            cb_id2 = om.MSceneMessage.addCallback(event, fn)
            last_token = CALLBACK_MANAGER.register(
                cb_id2, om.MMessage.removeCallback, OWNER_SHARED
            )

        # Import resolves in the existing kAfterImport.
        _add("kBeforeImport", _on_before_import)
        # References resolve reduce-only and deduped.
        for _ev_name in ("kBeforeCreateReference", "kBeforeLoadReference",
                         "kBeforeReference"):
            _add(_ev_name, _on_before_reference)
        for _ev_name in ("kAfterCreateReference", "kAfterLoadReference",
                         "kAfterReference"):
            _add(_ev_name, _on_after_reference)

        for _ev in (
            om.MSceneMessage.kBeforeSave,
            om.MSceneMessage.kBeforeExport,
        ):
            cb_id = om.MSceneMessage.addCallback(_ev, _on_before_serialize)
            last_token = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
        for _ev in (
            om.MSceneMessage.kAfterSave,
            om.MSceneMessage.kAfterExport,
        ):
            cb_id = om.MSceneMessage.addCallback(_ev, _on_after_serialize)
            last_token = CALLBACK_MANAGER.register(
                cb_id, om.MMessage.removeCallback, OWNER_SHARED
            )
        _SCENE_CALLBACKS_REGISTERED = True
        return last_token
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] failed to register scene-change "
            f"callbacks: {exc}\n"
        )
        return -1


def teardown_shared_callbacks() -> None:
    """Last-plugin-out teardown of the cross-plugin ``shared`` callbacks.

    Called from a plug-in's ``uninitializePlugin`` ONLY when the plugin
    load-refcount has hit zero (i.e. this is the final mpynode plug-in
    unloading). It:

      1. deregisters every ``shared``-owned callback in the manager
         (scene-change, time-unit, scene-io, auto-dirty scene-clear, the
         init-registry scene lifecycle, refresh-hub UI hooks); and
      2. resets every install-guard latch + transient flag so a later
         reload re-registers from a clean slate.

    Step 2 is the fix for the latch half of AUDIT #3: the guards
    (``_SCENE_CALLBACKS_REGISTERED``, ``scene_io._installed``,
    ``auto_dirty._scene_change_clear_installed``,
    ``time_utils._time_unit_callback_installed``) used to stay latched
    True across an unload, so a reload silently skipped re-registration
    and the shared callbacks were gone until a Maya restart.

    Fail-soft + idempotent: every step is wrapped so a teardown can't
    raise out of ``uninitializePlugin``.
    """
    global _SCENE_CALLBACKS_REGISTERED, _OPEN_IN_PROGRESS, _REF_RESOLVE_PENDING
    try:
        from mpynode._common.lifecycle.callbacks import CALLBACK_MANAGER, OWNER_SHARED

        CALLBACK_MANAGER.remove_for_owner(OWNER_SHARED)
    except Exception as exc:
        sys.stderr.write(
            f"[init_registry] shared-callback teardown failed: {exc}\n"
        )

    # Reset our own latch + transient open/reference flags.
    _SCENE_CALLBACKS_REGISTERED = False
    _OPEN_IN_PROGRESS           = False
    _REF_RESOLVE_PENDING        = False

    # Sibling install guards -- lazy import to avoid a load-time cycle.
    import importlib

    for mod_name in (
        "mpynode._common.lifecycle.scene_state",
        "mpynode._common.plugs.auto_dirty",
        "mpynode._common.plugs.plug_governance",
        "mpynode._common.lifecycle.time_utils",
    ):
        try:
            mod   = importlib.import_module(mod_name)
            reset = getattr(mod, "reset_install_state", None)
            if reset is not None:
                reset()
        except Exception as exc:
            sys.stderr.write(
                f"[init_registry] reset_install_state failed for "
                f"{mod_name}: {exc}\n"
            )
