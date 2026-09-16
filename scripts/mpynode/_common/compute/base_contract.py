"""Shared base-node contract primitives.

Every mpynode node type re-implements its own compute / expression
pipeline on top of the Maya base class it is REQUIRED to inherit
(``MPxDeformerNode``, ``MPxLocatorNode``, ``MPxSkinCluster``,
``MPxTransform``, ``MPxIkSolverNode``, ...). Because of that, the base
``mPyNode`` behaviors are NOT inherited -- they are re-expressed in each
type's compute path, and historically drifted apart (one path suppressed
a benign error, another spammed it; one deferred during scene load,
another did not).

This module holds the ONE canonical implementation of the cross-cutting
behaviors that every compute path must share, so a fix lands in a single
place instead of N. Compute paths call these helpers instead of
open-coding the policy.

Currently:
  * ``broadcast_compute_error`` -- the benign / transient error
    suppression policy (base contract item "C10"). A
    "'self' has no plug ... named X" raise that fires when the
    Evaluation Manager pulls an output in a transient state (scene load,
    attribute-surgery reorder, EM graph rebuild) BEFORE a DECLARED plug
    is resolvable is SUPPRESSED; every other error is broadcast to
    ``stderr`` + the Qt-free ``log_bus``.
"""

from __future__ import annotations


def broadcast_compute_error(type_label: str, message: str, *, declared_names=()) -> bool:
    """Broadcast a user-expression error unless it is the benign,
    self-correcting missing-plug transient.

    Args:
        type_label: Node type label used in the broadcast prefixes
            (e.g. ``"mPyNode"`` / ``"mPyDeformer"``).
        message: The captured error message from the expression exec.
        declared_names: Iterable of attribute names the node actually
            DECLARED (its user input + output schema). A missing-plug
            error for one of these is treated as transient; a missing
            plug for an UNDECLARED name (a genuine typo) still surfaces.

    Returns:
        True if the error was broadcast (``stderr`` + ``log_bus``),
        False if it was suppressed as benign / transient.

    Suppression policy (identical to the api2 base ``compute``):
      * The message must match the SelfProxy missing-plug signature.
      * AND either the missing name is a DECLARED user input/output,
        OR the scene is in a transient state (loading / post-open grace
        / attribute-surgery).
    """
    from mpynode._common.lifecycle import scene_state as scene_io

    declared = set(declared_names or ())
    miss     = scene_io.extract_missing_name(message)
    spurious = scene_io.is_missing_plug_error(message) and (
        (miss is not None and miss in declared)
        or scene_io.should_defer_transient()
    )
    if spurious:
        return False

    import sys

    sys.stderr.write("[{} expression error] {}".format(type_label, message))
    try:
        from mpynode._common.util.log_bus import log as _log_bus

        _log_bus("[{}] {}".format(type_label, message), level="error")
    except Exception:
        pass
    return True
