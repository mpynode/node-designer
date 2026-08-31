"""osl_targets -- apply an mPyNode's authored OSL string to a renderer.

v1 target: Arnold. ``apply_osl_to_arnold(node)`` reads the node's ``osl`` string
(authored in the OSL tab / AI-translated), creates an ``aiOslShader``, commits
the source to ``.code`` and COMPILES it via ``mtoa.osl.OSLSceneModel`` (which is
what materializes the param_* attrs Arnold needs -- a bare string wire to
``codeCache`` does NOT recompile, so this is the loop-closer), and wires the
node's connectable ``osl`` output into the shader's ``codeCache`` so later edits
flow through. Best-effort: returns the aiOslShader name, or ``None`` if MtoA /
the OSL machinery is unavailable.

This generalizes the scanline demo's ``wire_arnold_osl`` so any mPyFile can be
applied to Arnold from its OSL tab.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile

# Cap on the oslc diagnostic fed to the AI repair prompt. Compiler messages are
# short; anything longer is unrelated renderer chatter that happened to land in
# the same window, so keep the TAIL (the diagnostic comes last).
_MAX_DIAGNOSTIC_CHARS = 4000


def _flush_c_streams() -> None:
    """Flush Python's and libc's stdio buffers. Best-effort.

    Load-bearing for :func:`_capture_c_output`: with fd 1 redirected to a FILE
    (not a tty) libc switches to block buffering, so a ``printf``-ed diagnostic
    can still be sitting in the C buffer when the fds are restored -- it would
    then flush to the real console and the capture would come back empty.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    try:
        import ctypes

        ctypes.CDLL(None).fflush(None)  # fflush(NULL) == flush every stream
    except Exception:
        pass


def _restore_fds(saved) -> None:
    for fd, dup_fd in saved:
        try:
            os.dup2(dup_fd, fd)
        except Exception:
            pass
        try:
            os.close(dup_fd)
        except Exception:
            pass


@contextlib.contextmanager
def _capture_c_output():
    """Redirect fd 1 + fd 2 into a temp file for the duration of the block and
    yield a list that receives the captured text on exit.

    ``oslc`` reports through Arnold's C-level logger, NOT through Python's
    ``sys.stderr``, so ``contextlib.redirect_stderr`` catches nothing -- only a
    dup2 of the real descriptors does.

    Fail-soft by contract: if the redirect can't be installed the block still
    runs (unredirected) and the list stays empty, and the fds are restored even
    when the body raises. A missing diagnostic must never turn a compile error
    into a crash.
    """
    captured: list = []
    saved: list = []
    tmp = None
    try:
        tmp = tempfile.TemporaryFile()
        _flush_c_streams()
        for fd in (1, 2):
            saved.append((fd, os.dup(fd)))
            os.dup2(tmp.fileno(), fd)
    except Exception:
        _restore_fds(saved)
        if tmp is not None:
            try:
                tmp.close()
            except Exception:
                pass
        yield captured
        return
    try:
        yield captured
    finally:
        # Read BEFORE restoring: the flush has to land in the temp file while
        # the fds still point at it.
        try:
            _flush_c_streams()
            tmp.seek(0)
            captured.append(tmp.read().decode("utf-8", "replace"))
        except Exception:
            pass
        _restore_fds(saved)
        try:
            tmp.close()
        except Exception:
            pass


def _osl_error_message(exc_text: str, diagnostic: str) -> str:
    """The error string the AI self-repair prompt is fed: the captured oslc
    diagnostic first (the actionable part), then the Python-level exception
    text when it adds something, then the generic fallback when we have
    neither."""
    diagnostic = (diagnostic or "").strip()
    if len(diagnostic) > _MAX_DIAGNOSTIC_CHARS:
        diagnostic = diagnostic[-_MAX_DIAGNOSTIC_CHARS:]
    exc_text = (exc_text or "").strip()
    parts = [p for p in (diagnostic, exc_text) if p]
    if len(parts) == 2 and parts[1] in parts[0]:
        parts.pop()
    return "\n".join(parts) or ("OSL did not compile (no shader params "
                                "materialized)")


def _node_osl_source(node: str) -> str:
    """Read the node's authored OSL string from the connectable ``osl`` plug."""
    from maya import cmds
    if not cmds.attributeQuery("osl", node=node, exists=True):
        return ""
    try:
        return cmds.getAttr(node + ".osl") or ""
    except Exception:
        return ""


def validate_osl_via_arnold(osl_src: str):
    """Compile-validate an OSL source string. Returns ``(ok, error)``.

    This is the compile gate the AI Compute->OSL fallback uses (and feeds the
    error back to the model for one self-repair round). It compiles the source in
    a THROWAWAY ``aiOslShader`` via ``mtoa.osl.OSLSceneModel`` -- the same
    param-materialization success signal :func:`apply_osl_to_arnold` relies on --
    then deletes the temp node (success OR failure) so nothing is left behind.

    GOTCHA: ``OSLSceneModel`` is a Maya/Arnold API call -> the caller MUST invoke
    this on Maya's MAIN thread (e.g. the UI marshals it via
    ``maya.utils.executeInMainThreadWithResult``).

    When MtoA / the OSL machinery is unavailable this returns ``(True, "")``: we
    can't compile-check headless, so we DON'T block the translation -- the
    structural gate in :mod:`osl_ai_convert` remains the acceptance test.
    """
    if not osl_src or not osl_src.strip():
        return False, "empty OSL source"

    from maya import cmds

    try:
        if not cmds.pluginInfo("mtoa", q=True, loaded=True):
            cmds.loadPlugin("mtoa")
    except Exception:
        return True, ""  # can't validate -> don't block
    try:
        from mtoa.osl import OSLSceneModel
    except Exception:
        return True, ""

    tmp = cmds.createNode("aiOslShader", name="_oslValidate#", skipSelect=True)
    compile_err = ""
    try:
        try:
            cmds.setAttr(tmp + ".code", osl_src, type="string")
            cmds.setAttr(tmp + ".codeCache", osl_src, type="string")
        except Exception as exc:
            return False, "could not set OSL code: %s" % exc
        # oslc reports through Arnold's C-level logger, so the ONLY way to get a
        # real compiler diagnostic into the repair prompt is an fd-level capture
        # around the compile. Fail-soft: no capture -> the old error text.
        with _capture_c_output() as captured:
            try:
                # Compiles + materializes the param_* attrs. May raise WITH the
                # oslc diagnostic on a genuine error -- keep that too.
                OSLSceneModel(osl_src, tmp)
            except Exception as exc:
                compile_err = str(exc)
        # Authoritative signal (mirrors apply_osl_to_arnold): a valid shader
        # compiles to at least one user-defined param (its inputs/outputs). A
        # raise that still materialized params means it compiled enough.
        params = cmds.listAttr(tmp, userDefined=True) or []
        if not params:
            return False, _osl_error_message(compile_err, "".join(captured))
        return True, ""
    finally:
        try:
            cmds.delete(tmp)
        except Exception:
            pass


def recompile_osl_targets(node: str) -> int:
    """Re-COMPILE the ``aiOslShader``(s) already wired to ``node``'s ``osl``
    output so a Save / F5 edit of the OSL tab takes effect in Arnold.

    This is the OSL analogue of the Viewport tab's dgdirty+refresh: changing
    the ``osl`` string (``set_osl_expression`` -> ``setAttr``) flows into the
    shader's ``codeCache`` plug, but -- as ``apply_osl_to_arnold`` documents --
    a bare string wire to ``codeCache`` does NOT recompile. The compile only
    happens when ``OSLSceneModel(src, shader)`` re-runs, which re-materializes
    the ``param_*`` attrs Arnold renders from. Here we push the fresh source to
    each connected shader's ``.code`` / ``.codeCache`` and re-run the compile.

    Only ever recompiles EXISTING targets -- it never creates an
    ``aiOslShader`` (that's ``apply_osl_to_arnold``'s job, invoked explicitly
    from the OSL tab). Returns the number of shaders recompiled. Best-effort:
    returns 0 (never raises) when MtoA / the OSL machinery is unavailable or no
    target is wired. MUST run on Maya's MAIN thread (OSLSceneModel is a
    Maya/Arnold API call) -- the Save handler already runs there."""
    try:
        from maya import cmds
    except Exception:
        return 0
    try:
        if not cmds.attributeQuery("osl", node=node, exists=True):
            return 0
    except Exception:
        return 0
    src = _node_osl_source(node)
    if not src.strip():
        return 0
    # Find aiOslShaders the node's osl output already feeds. No target wired ->
    # nothing to recompile (don't auto-create one on save).
    try:
        targets = (
            cmds.listConnections(
                node + ".osl", source=False, destination=True,
                type="aiOslShader",
            )
            or []
        )
    except Exception:
        targets = []
    targets = list(dict.fromkeys(targets))  # dedupe, keep order
    if not targets:
        return 0
    try:
        if not cmds.pluginInfo("mtoa", q=True, loaded=True):
            cmds.loadPlugin("mtoa")
    except Exception:
        return 0
    try:
        from mtoa.osl import OSLSceneModel
    except Exception:
        return 0
    recompiled = 0
    for osl in targets:
        try:
            cmds.setAttr(osl + ".code", src, type="string")
            cmds.setAttr(osl + ".codeCache", src, type="string")
        except Exception:
            continue
        try:
            OSLSceneModel(src, osl)
        except Exception as exc:
            # A genuine compile error -- surface it but don't abort the others.
            sys.stderr.write(
                "[osl_targets] recompile OSLSceneModel raised for %s: %s\n"
                % (osl, exc)
            )
        recompiled += 1
    return recompiled


def apply_osl_to_arnold(node: str, name: str | None = None,
                        connect: bool = True) -> str | None:
    """Create + compile an ``aiOslShader`` from ``node``'s OSL string.

    ``node``: an mPyNode (e.g. mPyFile) carrying an authored ``osl`` string.
    ``connect``: also wire ``node.osl -> aiOslShader.codeCache`` so the shader
    tracks future edits to the tab (the proven proof-scene pattern).

    Returns the aiOslShader node name, or ``None`` (no MtoA / empty OSL / the
    OSL failed to compile -- no dangling node is left behind).
    """
    from maya import cmds

    src = _node_osl_source(node)
    if not src.strip():
        return None

    # MtoA must be loaded for the aiOslShader type AND for OSLSceneModel, which
    # compiles the code in an Arnold universe to create the param attrs.
    try:
        if not cmds.pluginInfo("mtoa", q=True, loaded=True):
            cmds.loadPlugin("mtoa")
    except Exception:
        return None
    try:
        from mtoa.osl import OSLSceneModel
    except Exception:
        return None

    osl = cmds.createNode("aiOslShader", name=(name or (node + "_arnoldOsl")))
    # code is what Arnold compiles/renders; codeCache mirrors the AE buffer.
    cmds.setAttr(osl + ".code", src, type="string")
    cmds.setAttr(osl + ".codeCache", src, type="string")
    try:
        # Compiles + adds the param_* Maya attrs (inputs created before the
        # sometimes-buggy output step, so a raise still leaves the inputs).
        OSLSceneModel(src, osl)
    except Exception as exc:
        sys.stderr.write("[osl_targets] OSLSceneModel raised: %s\n" % exc)

    # A valid OSL shader compiles to at least one param; if none materialized
    # the source didn't compile -- don't leave a dangling node.
    params = [a for a in (cmds.listAttr(osl, userDefined=True) or [])]
    if not params:
        try:
            cmds.delete(osl)
        except Exception:
            pass
        return None

    if connect:
        try:
            cmds.connectAttr(node + ".osl", osl + ".codeCache", force=True)
        except Exception:
            pass
    return osl
