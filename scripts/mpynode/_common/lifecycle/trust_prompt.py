"""Pickle-trust resolution + prompt — split out of ``init_registry.py``
(behavior unchanged).

Resolves (ONCE, on the MAIN thread, at open/import) whether a scene's pickled
MPyNode data is trusted, so the worker-thread compute decode path never has to
prompt. See ``_common/io/trust.py`` for the per-scene trust store.

Clean ``lifecycle -> io`` edge (uses ``io/trust`` + ``io/serialization``) plus a
one-way read of ``_INIT_TRACKED_NODE_TYPES`` from the sibling ``init_registry``.
"""

from __future__ import annotations

import sys

from .init_registry import _INIT_TRACKED_NODE_TYPES


# ---- Pickle-trust resolution (MAIN THREAD, at open/import) -- see _common/io/trust.py ----

def _is_batch(cmds) -> bool:
    """True if Maya is headless (no GUI to prompt in)."""
    try:
        return bool(cmds.about(batch=True))
    except Exception:
        return True  # unsure -> treat as headless (no prompt; fail closed)


def _node_has_pickle_python_literal(cmds, node) -> bool:
    """True if ``node`` has an UNCONNECTED python-typed input attr holding a
    (pickle) literal value loaded from the file -- as opposed to a runtime
    value driven by an upstream connection (which is not a file-trust concern)."""
    from mpynode._common.io import serialization as _ser

    try:
        if not cmds.attributeQuery("_inputAttrs", node=node, exists=True):
            return False
        amap = _ser.decode_attr_map(cmds.getAttr(node + "._inputAttrs") or "")
    except Exception:
        return False
    for name, meta in amap.items():
        if not isinstance(meta, dict) or meta.get("attr_type") != "python":
            continue
        base = "%s.%s" % (node, name)
        try:
            if meta.get("is_array"):
                # Per-ELEMENT: listConnections on the base name reports ANY
                # element, so a connected element[0] must not mask an
                # unconnected file-literal on element[1] -- which the read path
                # does read, and pickle would execute.
                for i in cmds.getAttr(base, multiIndices=True) or []:
                    elem = "%s[%d]" % (base, i)
                    try:
                        if cmds.listConnections(elem, s=True, d=False):
                            continue  # driven at runtime -> not a file literal
                        if cmds.getAttr(elem):
                            return True
                    except Exception:
                        continue
            else:
                if cmds.listConnections(base, s=True, d=False):
                    continue  # driven at runtime by an upstream node
                if cmds.getAttr(base):
                    return True  # non-empty pickle literal persisted in the file
        except Exception:
            continue
    return False


def _node_has_exec_source(cmds, node) -> bool:
    """True if ``node`` carries non-empty Init, Compute or Viewport Python.

    That source is read straight out of the file and exec'd -- Init on open
    (``init_registry.register_init_source``), Compute on every evaluation
    (``compute.expression.exec_with_profile_watch``) -- so it needs exactly the
    same trust decision pickle does. Source that execs to nothing is not a
    reason to ask: empty/whitespace, and the literal ``"None"`` that api1
    creates ``_computeSource`` with (``_api1/helpers.make_expression_attr``) --
    the same unset test the solve path uses at ``_api1/helpers.py:713``.

    ``_jitSource`` is the legacy Init attr; the open sweep still migrates AND
    execs it (``scene_callbacks._register_init_sources_for_tracked``), so an
    old ``.ma`` carrying only that one must be caught here too.

    ``_viewportSource`` (mPyFile) is the same shape: a STORABLE string plug
    (``_api2/helpers.make_internal_string_attr`` defaults ``storable=True``)
    run through the same ``exec_with_profile_watch`` on every VP2 shader
    update (``_api2/mpy_file.py``). Omitting it let a pickle-free ``.ma``
    whose payload lives ONLY there resolve trusted with no prompt, and the
    exec gate then waved it through. Costs nothing on shipped content: all six
    templates that seed a viewport source also seed an Init source, so they
    already asked."""
    for attr in ("_initSource", "_jitSource", "_computeSource",
                 "_viewportSource"):
        try:
            if not cmds.attributeQuery(attr, node=node, exists=True):
                continue
            src = (cmds.getAttr("%s.%s" % (node, attr)) or "").strip()
        except Exception:
            continue
        if src and src != "None":
            return True
    return False


def _scene_has_pickle_blobs(cmds) -> bool:
    """True if opening/importing needs a trust decision, because some mPy node
    carries something the load would EXECUTE:

      * pickled data -- a stored-var pickle blob or a python-attr literal
        (``pickle.loads`` is arbitrary code); or
      * node Python -- a non-empty ``_initSource`` / legacy ``_jitSource`` /
        ``_computeSource`` (see :func:`_node_has_exec_source`).

    The second arm is not optional: the resolved flag now gates Init and
    Compute exec as well as pickle decode, so a scene that is pickle-FREE but
    full of node Python must still be asked about -- otherwise it resolves
    trusted with no prompt and runs its own code on open."""
    from mpynode._common.io import serialization as _ser

    try:
        known = set(cmds.allNodeTypes() or [])
    except Exception:
        known = None
    for node_type in _INIT_TRACKED_NODE_TYPES:
        if known is not None and node_type not in known:
            continue
        try:
            nodes = cmds.ls(type=node_type) or []
        except Exception:
            continue
        for node in nodes:
            try:
                if cmds.attributeQuery("_storedVarsData", node=node, exists=True):
                    blob = cmds.getAttr(node + "._storedVarsData")
                    if blob and _ser.blob_has_pickle(blob):
                        return True
            except Exception:
                pass
            # Cheapest check first; the python-literal scan below decodes the
            # attr map and walks multi-element connections.
            if _node_has_exec_source(cmds, node):
                return True
            if _node_has_pickle_python_literal(cmds, node):
                return True
    return False


def _make_trust_prompt(allow_always: bool, subject: str = "scene"):
    """Build a MAIN-THREAD Qt ``prompt_fn(path) -> decision``. The returned
    callable shows a modal warning; it falls back to "no" (refuse) if Qt is
    unavailable. ``subject`` tunes the wording (e.g. ``"scene"`` or
    ``".mpn template"``). ``allow_always`` is suppressed automatically when the
    path is falsy (an unsaved scene has no stable location to remember)."""
    def _prompt(path):
        try:
            from mpynode.ui.qt_wrapper import QMessageBox
        except Exception:
            return "no"
        box = QMessageBox()
        try:
            box.setIcon(QMessageBox.Warning)
        except Exception:
            pass
        # The ".mpn template" caller (io/mpn_io.load_mpn) gates ONLY the pickle
        # decode -- a template's Init/Compute is applied through the authoring
        # setters (trusted=True) -- so only the SCENE case may say exec is
        # blocked too.
        is_scene = subject == "scene"
        box.setWindowTitle("MPyNode — Trust this %s?" % subject)
        if is_scene:
            box.setText(
                "This scene contains MPyNode node code and/or pickled "
                "Python data.")
            detail = (
                "Loading it can run arbitrary code. Choosing \"Don't Trust\" "
                "blocks BOTH: the pickled stored-variable data will not load, "
                "AND the MPyNode Init/Compute Python in this scene will not "
                "run. Re-open and choose Trust to restore it.")
        else:
            box.setText(
                "This %s contains pickled Python data in MPyNode node(s)."
                % subject)
            detail = (
                "Decoding pickled data can run arbitrary code. Choosing "
                "\"Don't Trust\" skips the pickled stored-variable data in "
                "this %s." % subject)
        box.setInformativeText(
            "%s Only open files from a source you trust.\n\n%s"
            % (detail, path or "(unsaved scene)"))
        b_yes = box.addButton("Trust", QMessageBox.YesRole)
        # Only offer "Always" when there's a real path to persist.
        b_always = (box.addButton("Always Trust This Folder",
                                  QMessageBox.AcceptRole)
                    if (allow_always and path) else None)
        box.addButton("Don't Trust", QMessageBox.NoRole)
        try:
            box.exec_()
        except AttributeError:
            box.exec()
        clicked = box.clickedButton()
        if clicked is b_yes:
            return "yes"
        if b_always is not None and clicked is b_always:
            return "always_folder"
        return "no"
    return _prompt


# Public alias so UI code (e.g. the .mpn import dialog) reuses the same prompt
# without reaching into a private name.
def make_trust_prompt(allow_always: bool = True, subject: str = "scene"):
    return _make_trust_prompt(allow_always, subject=subject)


def _resolve_pickle_trust(is_import: bool) -> None:
    """Resolve (ONCE, on the MAIN thread) whether this scene's pickled data is
    trusted, so the worker-thread compute decode path never has to prompt.

    The resolved flag gates pickle DECODE and Init/Compute EXEC alike, so the
    fast path is "nothing to execute" -- a scene with neither pickle nor node
    Python resolves True with no prompt. Headless (batch) never prompts -- it
    relies on ``MPYNODE_TRUST_PICKLE`` / the store, and otherwise fails closed
    (refuses)."""
    try:
        from maya import cmds
    except Exception:
        return
    from mpynode._common.io import trust

    try:
        has_pickle = _scene_has_pickle_blobs(cmds)
    except Exception:
        has_pickle = True  # can't tell -> require trust (fail safe)
    # A prompt/persist hiccup must NOT escape the scene callback -- it would
    # abort the rest of _on_scene_opened (init registration, stored-var
    # hydration, transform force-eval). Fail CLOSED instead.
    resolved = False
    try:
        if is_import:
            # The imported file's path isn't reliably available in the
            # after-callback, so no per-folder "Always" for it.
            prompt   = None if _is_batch(cmds) else _make_trust_prompt(allow_always=False)
            resolved = trust.resolve_for_import(None, has_pickle, prompt_fn=prompt)
            trust.note_file_imported(resolved)
        else:
            try:
                path = cmds.file(q=True, sceneName=True) or None
            except Exception:
                path = None
            prompt   = None if _is_batch(cmds) else _make_trust_prompt(allow_always=True)
            resolved = trust.resolve_for_open(path, has_pickle, prompt_fn=prompt)
            trust.note_file_opened(resolved)
    except Exception as exc:
        # Fail closed: leave the per-scene flag at whatever the before-event set
        # (False during the transition), and (for open) make it explicit.
        if not is_import:
            try:
                trust.note_file_opened(False)
            except Exception:
                pass
        sys.stderr.write(
            "[init_registry] pickle-trust resolution failed (%s); failing "
            "closed (pickled data will not load).\n" % exc)
        return
    if has_pickle and not resolved:
        sys.stderr.write(
            "[init_registry] this scene was NOT trusted: pickled MPyNode data "
            "will not load and MPyNode Init/Compute Python will not run. Open "
            "from a trusted location, click Trust, or set "
            "MPYNODE_TRUST_PICKLE=1 (headless).\n")
