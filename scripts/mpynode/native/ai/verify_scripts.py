"""Emit the shipped ``verify_in_maya.py`` parity scripts.

Every script, whatever the node's family (geometry / deformer / IK solver /
scalar), is the same short program: it embeds the node's spec and runs the
compile pipeline's own parity check, ``native.toolchain.verify._verify_one``,
on the compiled plug-in beside it. There is one parity implementation. The
deformer, IK and scalar scripts used to carry their own sample / set / fit
code, which drifted from the pipeline's: 17 of the 38 shipped scripts raised
when run on their own (array, mesh, string, matrix, colour and connected time
inputs), and the scalar one compared against a live SOURCE node rather than
a rebuilt twin. Only the docstring says which family the node is.

The script picks the plug-in's extension when it runs, from the OS Maya runs
on (``toolchain.plugin_ext()``: ``.mll``, ``.bundle`` or ``.so``), so the
generator's output is the same whatever OS generates it. It used to write
the generating host's extension: on macOS every script named a ``.bundle``.

Built by plain string concatenation (no % / .format / f-string) because the
embedded spec may itself contain ``%`` and ``{}``.
"""

from __future__ import annotations

import json

from mpynode.native import compiler as codegen


# What each family's check builds and compares, for the script's docstring.
# The check itself is verify._verify_one for every family.
_FAMILY_DOC = {
    "geo": ("GEOMETRY node", "the original mPyNode",
            "the built geometry (topology + every point)"),
    "deformer": ("DEFORMER", "the original mPy deformer",
                 "the deformed points"),
    "iksolver": ("IK solver", "the original mPyIkSolver",
                 "the joint world positions over several goals"),
    "scalar": ("node", "the original mPyNode",
               "every component of every output"),
}

_BODY = r'''def run():
    from mpynode.native.toolchain import verify as _cc
    _cc._load_python_plugins(cmds)
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    row = _cc._verify_one(cmds, BUNDLE, SPEC)
    print("VERIFY ROW", row)
    if not row.get("ran"):
        print("VERIFY SKIP (" + str(row.get("reason")) + ")")
        return True
    if row.get("pass"):
        print("VERIFY PASS maxerr", row.get("maxerr"))
        return True
    print("VERIFY FAIL", row.get("reason"), row.get("maxerr"))
    return False


if __name__ == "__main__":
    run()
'''


def _family(spec: dict) -> str:
    """``geo`` / ``deformer`` / ``iksolver`` / ``scalar``: the branch
    ``verify._verify_one`` takes for this spec."""
    base = spec.get("suggested", {}).get("mpx_base", "MPxNode")
    if codegen._geo_kind(spec):
        return "geo"
    if base in codegen._DEFORMER_BASES:
        return "deformer"
    if base == codegen._IKSOLVER_BASE:
        return "iksolver"
    return "scalar"


def _verify_script(spec: dict) -> str:
    """A Maya-side equivalence check: compiled node vs original mPyNode.

    The script embeds ``spec`` and runs ``verify._verify_one`` on the plug-in
    beside it, the same check the compile pipeline runs: it rebuilds the
    Python original from the spec, so no source node needs to be in the
    scene. It registers the mpynode node types first, as the pipeline's
    verify does. ``_verify_one`` opens a new scene before it drives the two
    nodes, so the script says to save first. Prints a ``VERIFY PASS`` /
    ``FAIL`` / ``SKIP`` line and returns False only on a FAIL.

    The plug-in's extension is picked when the script runs
    (``toolchain.plugin_ext()`` on that host), never when it is generated:
    the text depends on ``spec`` alone.
    """
    name = spec["suggested"]["node_type_name"]
    what, src, compared = _FAMILY_DOC[_family(spec)]
    consts = (
        '"""Equivalence check: compiled native ' + what + " vs " + src + ".\n"
        "Run in Maya. Runs the compile pipeline's own parity check,\n"
        "mpynode.native.toolchain.verify._verify_one, on the spec embedded\n"
        "below: it rebuilds the Python original, builds the compiled node,\n"
        "drives identical inputs on both, and compares\n"
        + compared + ".\n"
        "It opens a new scene (file new, force) before it drives the nodes:\n"
        "save your work first.\n"
        '"""\n'
        "import os, json\n"
        "import maya.cmds as cmds\n"
        "from mpynode.native.toolchain import toolchain\n\n"
        "# .mll, .bundle or .so: picked for the OS this runs on.\n"
        "EXT = toolchain.plugin_ext()\n"
        "BUNDLE = os.path.join(os.path.dirname(__file__), "
        + repr(name) + " + EXT)\n"
        "SPEC = json.loads(" + repr(json.dumps(spec)) + ")\n\n\n"
    )
    return consts + _BODY
