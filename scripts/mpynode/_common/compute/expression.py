"""Compile + execute user expressions.

A user expression is run with **a single namespace dict** and
**only ``__builtins__``** is auto-injected. The user must explicitly
``import numpy as np`` (or whatever modules they need) at the top of their
expression. This treats every expression as a fresh Python interpreter
\u2014 no surprise globals.

The bridge populates the namespace with:
  * input plug values as bare names (``seed``, ``x``,...)
  * output plug pre-seeded values as bare names (``out``, ``mults``,...)
  * a ``self`` SelfProxy exposing per-class internal vars + per-instance
    user storage
  * ``__builtins__`` (so ``len``, ``range``, ``print``, ``dict`` etc. work)

The expression mutates the namespace in place; the bridge reads back USER
output values (bare names) and ``self.X`` writes (via SelfProxy) after exec
returns.
"""

from __future__ import annotations

import builtins
import sys
import traceback
import types  # noqa: F401  (kept for downstream tools that import from here)


# ``log_event_name``s already warned about a trust refusal, so an untrusted
# scene logs once per key instead of once per evaluation (compute fires every
# dirty eval; the scene-level banner is printed separately at open time by
# ``trust_prompt._resolve_pickle_trust``). Set add/lookup is atomic under the
# GIL, so an EM worker thread can only ever duplicate a message.
_UNTRUSTED_EXEC_WARNED: set = set()


def compile_expression(source: str, filename: str = "<mpynode-expression>"):
    """Compile a user expression to a code object.

    Returns the compiled code object on success. Raises ``SyntaxError``
    on failure (the bridge catches + logs)."""
    if not source:
        # Compile an empty no-op so exec doesn't complain.
        return compile("pass", filename, "exec")
    return compile(source, filename, "exec")


def safe_compile_expression(
    source: str,
    node_name: str = "",
    filename: str = "<mpynode-expression>",
):
    """Compile a user expression and surface any ``SyntaxError`` to the
    Maya script editor / Output Window via ``MGlobal.displayWarning`` AND
    ``stderr``.

    Returns the compiled code object on success, OR ``None`` on
    SyntaxError (caller should KEEP its previous ``_expr_code`` so the
    node continues running with its last-known-good expression).

    previously ``setInternalValue`` wrapped the
    compile in a bare ``try/except Exception: pass`` which silently
    swallowed SyntaxErrors. Users typed invalid syntax in the Designer,
    saved, and got NO feedback \u2014 the node just stopped computing
    silently. This helper guarantees the user sees the compile failure.
    """
    try:
        return compile_expression(source, filename)
    except SyntaxError as exc:
        # Build a user-facing message including the node name and a
        # caret-pointer to the offending column when available.
        line = (exc.text or "").rstrip("\n") if exc.text else ""
        msg_lines = [
            "[mpynode] expression compile failed for node "
            f"{node_name!r}: {exc.msg} (line {exc.lineno or '?'}, "
            f"col {exc.offset or '?'})",
        ]
        if line:
            msg_lines.append(f"    {line}")
            if exc.offset and exc.offset > 0:
                msg_lines.append("    " + " " * (exc.offset - 1) + "^")
        msg = "\n".join(msg_lines)

        # displayWarning makes the script editor pop the Output Window. API 2
        # first (most callers are api2), API 1 as fallback.
        _displayed = False
        try:
            import maya.api.OpenMaya as _om2

            _om2.MGlobal.displayWarning(msg)
            _displayed = True
        except Exception:
            pass
        if not _displayed:
            try:
                import maya.OpenMaya as _om1

                _om1.MGlobal.displayWarning(msg)
            except Exception:
                pass
        # Also write to stderr so headless mayapy + log capture see it.
        sys.stderr.write(msg + "\n")
        return None
    except Exception as exc:  # noqa: BLE001
        # Other compile-time errors (extremely rare; e.g. encoding).
        msg = f"[mpynode] unexpected compile error for {node_name!r}: {exc}"
        try:
            import maya.api.OpenMaya as _om2

            _om2.MGlobal.displayWarning(msg)
        except Exception:
            sys.stderr.write(msg + "\n")
        return None


def build_exec_namespace(
    extras: dict | None = None,
    cmds_module=None,  # kept for back-compat; ignored as
) -> dict:
    """Build the namespace for user expression exec.

    only ``__builtins__`` is auto-injected. Users must
    explicitly ``import numpy as np``, ``import math``, ``import maya.cmds``
    in their expressions. No more magic globals.

    The legacy ``cmds_module`` parameter is accepted but ignored \u2014 callers
    can pass it harmlessly during the migration window. ``extras`` is the
    bridge's hook for injecting input values, output buffers, and the
    ``self`` SelfProxy.
    """
    ns: dict = {"__builtins__": builtins}
    if extras:
        ns.update(extras)
    return ns


def exec_with_profile_watch(
    code,
    namespace: dict,
    log_event_name: str = "<mpynode-exec>",
    on_error=None,
    *,
    node_obj=None,
    compute_ctx: dict = None,
) -> bool:
    """Execute a compiled expression. Returns True on success.

    if ``node_obj`` is provided AND its UUID has a
    registered ``init_source`` namespace (set via:meth:`JitKernelMixin.set_init_expression`), inject the contents of
    that namespace into ``namespace`` before exec. This is what
    lets the main expression call kernel functions defined in the
    sister window with no per-call decorator overhead.

    signature simplified to a SINGLE namespace dict (was
    separate ``exec_globals`` + ``exec_locals``). This makes list
    comprehensions and other Python scope-sensitive constructs Just Work
    \u2014 ``[seed * i for i in range(5)]`` no longer raises NameError on
    ``seed`` because there's only one namespace for both globals and
    locals.

    when ``node_obj`` is provided AND any of its 3 instrumentation
    toggles (``profile_enabled`` / ``deep_profile_enabled`` / ``watch_enabled``)
    are on, also collects per-instance timing stats (cheap), an optional
    cProfile drill-down (heavyweight), and a snapshot of the namespace
    (after exec). Snapshots are written to the ``_profileSnapshotData``
    and ``_watchVarsData`` plugs on a throttle (every Nth call, default
    N=30). When all toggles are off OR ``node_obj`` is None, this is a
    near-zero-overhead pass-through.

    On exception:
      * the traceback is captured + formatted
      * if ``on_error`` is provided, it's called with the formatted str
      * returns False (so the bridge can decide whether to skip writing
        outputs back to plugs)
    """
    # T38 trust gate. A node-bound call runs code that came out of the node's
    # ``_computeSource`` plug -- i.e. out of the scene file -- so an untrusted
    # scene must not exec it. Checked FIRST: before the Init merge, the
    # SelfProxy patching and the ``node`` PlugProxy injection, so a refusal
    # can't leave the node half-wired. A node-less call carries code the
    # caller supplied in-process (tests, ad-hoc tools) and is NOT gated.
    # Same predicate the Init gate reads (init_registry._exec_trusted), so the
    # two exec paths share one decision and one MPYNODE_TRUST_PICKLE opt-in.
    if node_obj is not None:
        from mpynode._common.io import trust as _trust

        if not _trust.exec_trusted():
            if log_event_name not in _UNTRUSTED_EXEC_WARNED:
                _UNTRUSTED_EXEC_WARNED.add(log_event_name)
                sys.stderr.write(
                    "[%s] expression NOT run -- this scene is not trusted. "
                    "Re-open the file and click Trust, or set "
                    "MPYNODE_TRUST_PICKLE=1 (headless).\n" % log_event_name
                )
            return False

    # Inject the Init namespace as bare names in the expression's globals, and
    # the Init bindings (self.X writes from Init code) behind self.X. Keys
    # already in ``namespace`` win -- never shadow them.
    if node_obj is not None:
        try:
            from mpynode._common.lifecycle import init_registry as _ir

            # (a) merge module-level init names into globals. The ensure_*
            # variant lazy-binds from the ``_initSource`` plug if not yet
            # registered -- covers compute() firing before the kAfterOpen sweep.
            kernel_ns = _ir.ensure_init_namespace_for_mobject(node_obj)
            if kernel_ns:
                for k, v in kernel_ns.items():
                    if k.startswith("__"):
                        continue
                    if k in namespace:
                        continue
                    namespace[k] = v

            # Stash on the SelfProxy so blessed API-method adapters can resolve
            # Init helpers by name via SelfProxy.get_init_helper.
            _self_for_ns = namespace.get("self")
            if _self_for_ns is not None:
                try:
                    object.__setattr__(
                        _self_for_ns, "_psp_exec_namespace", namespace)
                except Exception:
                    pass

            # (b) feed init bindings into the SelfProxy for self.X reads: look
            # up `self` in the namespace and patch its bindings slot, which was
            # constructed empty.
            init_bindings = _ir.get_init_bindings_for_mobject(node_obj)
            if init_bindings:
                self_obj = namespace.get("self")
                if self_obj is not None:
                    try:
                        # legacy SelfProxy is gone; only the
                        # ``_psp_init_bindings`` slot exists now.
                        object.__setattr__(self_obj, "_psp_init_bindings", init_bindings)
                    except Exception:
                        pass
        except Exception:
            pass

    # Inject `node`, a PlugProxy on the executing node's plug tree. Reads are
    # always available; writes go through the compute-time DataBlock when
    # ``compute_ctx`` is given (E4), else cmds.setAttr (E3 init-time).
    # ``compute_ctx`` keys: datablock (compute only), geom_iter (deformer).
    if node_obj is not None and "node" not in namespace:
        try:
            from mpynode._common.plugs.plug_proxy import PlugProxy

            db = compute_ctx.get("datablock") if compute_ctx else None
            gi = compute_ctx.get("geom_iter") if compute_ctx else None
            namespace["node"] = PlugProxy(
                node_obj, datablock=db, geom_iter=gi,
                compute_ctx=compute_ctx,
            )
        except Exception:
            pass

    # Bare-exec path when no node_obj provided (covers tests, ad-hoc
    # callers).
    if node_obj is None:
        try:
            exec(code, namespace)
            return True
        except Exception:
            tb_lines = traceback.format_exception(*sys.exc_info())
            msg = f"[{log_event_name}] expression error:\n{''.join(tb_lines)}"
            if on_error is not None:
                try:
                    on_error(msg)
                except Exception:
                    pass
            else:
                sys.stderr.write(msg)
            return False

    # Deferred import so test_node_registry (no node_obj) skips the cost.
    from mpynode._common import instrumentation as _instr

    success, captured = _instr.run_instrumented_exec(code, namespace, node_obj)
    if success:
        return True

    if isinstance(captured, BaseException):
        tb_lines = traceback.format_exception(
            type(captured), captured, captured.__traceback__
        )
    else:
        tb_lines = traceback.format_exception(*sys.exc_info())
    msg = f"[{log_event_name}] expression error:\n{''.join(tb_lines)}"
    if on_error is not None:
        try:
            on_error(msg)
        except Exception:
            pass
    else:
        sys.stderr.write(msg)
    return False
