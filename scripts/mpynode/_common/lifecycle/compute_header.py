"""Compute_registry -- the Compute (Expression) tab's auto-generated header.

The Compute tab is the node's per-evaluation expression: it runs every time
the Dependency Graph pulls the node (i.e. whenever an output is dirty and
something reads it). Unlike Init (which runs ONCE at file open / on edit) the
Compute source is the hot path.

The Compute source itself lives on the node's ``_computeSource`` string plug
and is compiled + cached by the bridge; this module only provides the
friendly commented header that prefills a *fresh* (empty) Compute tab when
the ``new_node_mode`` preference is ``"headers"``. The header is display-only
-- it is never written to the node.

Mirrors :func:`init_registry.make_init_header` /
:func:`viewport_registry.make_viewport_header`.
"""

from __future__ import annotations


def make_compute_header(node_type: str) -> str:
    """Return a friendly commented header to prefill a fresh Compute tab.

    Kept deliberately generic + accurate for every node type (it does not
    enumerate per-type plug bindings -- the Init header already does that,
    and the live plug tree is what the autocomplete surfaces). Falls back
    to a usable header for unknown types.
    """
    nt  = node_type or "unknown"
    bar = "# " + "-" * 68
    lines = [
        bar,
        f"# {nt} -- Compute code (runs every DG evaluation)",
        "#",
        "# This is the node's per-frame expression. It re-runs whenever an",
        "# output is needed and an input has changed, so keep it fast.",
        "#",
        "# Read inputs and write outputs through ``self``:",
        "#     value = self.myInput          # read an input plug",
        "#     self.myOutput = value * 2.0   # write an output plug",
        "#",
        "# Array plugs read/write as numpy arrays; matrices arrive as a",
        "# MatrixView (use .asNumpy() for a 4x4). ``np`` (numpy) is NOT",
        "# auto-injected -- ``import numpy as np`` in the Init tab; anything",
        "# you defined there is in scope here as a bare name (helpers,",
        "# kernels, cached matrices, ...).",
        "#",
        "# Only assignments to declared OUTPUT plugs propagate downstream;",
        "# scratch ``self.x`` writes persist as stored vars across evals.",
        bar,
        "",
    ]
    return "\n".join(lines)
