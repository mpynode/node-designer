"""Emit the shipped ``verify_in_maya.py`` parity scripts.

Every script, whatever the node's family (geometry / deformer / IK solver /
scalar), is the same short program: it embeds the node's spec and runs the
compile pipeline's own verify, ``native.toolchain.verify._default_verify``,
on the compiled plug-in beside it. That is the generic parity check
(``_verify_one``) plus the node's authored ``@maya_test``, merged as the
pipeline merges them (``_merge_authored_test``), so the script's verdict is
the pipeline's final one. There is one parity implementation. The deformer,
IK and scalar scripts used to carry their own sample / set / fit code, which
drifted from the pipeline's: 17 of the 38 shipped scripts raised when run on
their own (array, mesh, string, matrix, colour and connected time inputs),
and the scalar one compared against a live SOURCE node rather than a rebuilt
twin. Later every script ran ``_verify_one`` alone, and 8 of them said SKIP
where the pipeline passes the node on its authored test. Only the docstring
says which family the node is.

The verify opens new scenes (``file new, force``), so the script refuses to
run while the open scene has unsaved changes: it raises before it touches
the scene, and says to save first or to run it in a fresh mayapy. The guard
trusts Maya's own modified flag, so a selection-only change isn't flagged
and the script runs and replaces that scene; no file is touched. A verify
leaves the scene it made modified, so a second run in the same session is
refused as well: the refusal says to clear a scene a previous verify left
with ``cmds.file(new=True, force=True)`` first. Run as
``mayapy verify_in_maya.py`` it starts Maya itself, before it imports
``mpynode``: ``maya.cmds`` was empty there, so the script failed at the
guard, and a ``userSetup.py`` install could not import ``mpynode`` at all. It
prints the folder of the ``mpynode`` package it imported first, so an
outdated install on the path is obvious.

The merged row passes a node on its authored test alone when the generic
check did not run, and that includes a harness error ("verify could not
run": an outdated ``mpynode`` that rejects an attr type, say). The PASS line
then gives the row's reason and says whether the generic check was skipped
or COULD NOT RUN; a bare ``VERIFY PASS maxerr None`` hid both.

Run as a script, a FAIL raises after its ``VERIFY FAIL`` line, so ``mayapy
verify_in_maya.py`` exits 1 and Maya shows an error; it used to exit 0, and
a shell caller read the FAIL as success. When the generic check failed, the
line names it, with its maxerr and tolerance, before the merged reason: that
reason alone can say only "authored @maya_test: 1/1 passed". ``run()`` itself still returns
False to a caller that imports the script. A PASS and a SKIP exit 0, and
so does a PASS the authored test alone decided, even when the generic check
COULD NOT RUN: the pipeline calls that a PASS too.

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
# The check itself is verify._default_verify for every family.
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
    pkg = os.path.dirname(os.path.abspath(mpynode.__file__))
    print("VERIFY MPYNODE " + pkg)
    if cmds.file(q=True, modified=True):
        raise RuntimeError(
            "VERIFY REFUSED: the open scene has unsaved changes, and this "
            "check opens new scenes (file new, force). Save first, or run "
            "it in a fresh mayapy. If a previous verify left this scene, "
            "run cmds.file(new=True, force=True) first.")
    from mpynode.native.toolchain import verify as _cc
    rows = _cc._default_verify(BUNDLE, [{"type_name": NAME, "spec": SPEC}])
    row = rows[NAME]
    print("VERIFY ROW", row)
    if not row.get("ran"):
        print("VERIFY SKIP (" + str(row.get("reason")) + ")")
        return True
    if row.get("pass"):
        if row.get("generic_ran") is False:
            # The authored @maya_test alone passed it: say why the generic
            # check did not run, and whether its harness failed.
            how = "skipped"
            if str(row.get("reason")).startswith("verify could not run"):
                how = "COULD NOT RUN"
            print("VERIFY PASS (authored @maya_test only; generic check "
                  + how + ") " + str(row.get("reason")))
            return True
        print("VERIFY PASS maxerr", row.get("maxerr"))
        return True
    maxerr, tol = row.get("maxerr"), row.get("tol")
    if (row.get("generic_ran", True) and maxerr is not None
            and tol is not None and maxerr > tol):
        # The generic check failed: name it, with its tolerance. The merged
        # reason may speak only of the authored test, which can have passed.
        why = row.get("reason")
        print("VERIFY FAIL generic check maxerr " + str(maxerr) + " > tol "
              + str(tol) + (" | " + str(why) if why else ""))
        return False
    print("VERIFY FAIL", row.get("reason"), row.get("maxerr"))
    return False


if __name__ == "__main__":
    # Run as a script, a FAIL raises: mayapy exits 1 and Maya shows an
    # error. A caller that imports this file gets run()'s False instead.
    if not run():
        raise RuntimeError(
            "VERIFY FAIL: the compiled " + NAME + " does not match the "
            "original; see the VERIFY FAIL line above.")
'''


def _family(spec: dict) -> str:
    """``geo`` / ``deformer`` / ``iksolver`` / ``scalar``: the branch
    ``verify._verify_one`` (the generic check) takes for this spec."""
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

    The script embeds ``spec`` and runs ``verify._default_verify`` on the
    plug-in beside it, the same verify the compile pipeline runs: the
    generic check rebuilds the Python original from the spec, so no source
    node needs to be in the scene, and the node's authored ``@maya_test``
    runs on the compiled node; the two merge as in the pipeline's row.
    ``_default_verify`` registers the mpynode node types and loads the
    plug-in itself.

    The verify opens new scenes, so the script first raises when the open
    scene has unsaved changes, before it touches the scene; the error says
    to clear a scene a previous verify left with
    ``cmds.file(new=True, force=True)``. Run as
    ``__main__`` where ``maya.cmds`` is still empty (a bare mayapy), it
    initializes ``maya.standalone`` before it imports ``mpynode``. It prints
    the folder of the ``mpynode`` it imported first, then a ``VERIFY PASS``
    / ``FAIL`` / ``SKIP`` line from the merged row, and returns False only
    on a FAIL; run as ``__main__``, a FAIL then raises, so mayapy exits 1.
    A PASS the authored test alone decided gives the row's reason, marked
    ``skipped`` or ``COULD NOT RUN`` (a harness error).

    The plug-in's extension is picked when the script runs
    (``toolchain.plugin_ext()`` on that host), never when it is generated:
    the text depends on ``spec`` alone.
    """
    name = spec["suggested"]["node_type_name"]
    what, src, compared = _FAMILY_DOC[_family(spec)]
    consts = (
        '"""Equivalence check: compiled native ' + what + " vs " + src + ".\n"
        "Run it in Maya, or as `mayapy verify_in_maya.py`, which starts\n"
        "Maya first. Runs the compile pipeline's own verify,\n"
        "mpynode.native.toolchain.verify._default_verify, on the spec\n"
        "embedded below. Its generic check rebuilds the Python original,\n"
        "builds the compiled node, drives identical inputs on both, and\n"
        "compares " + compared + ".\n"
        "The node's authored @maya_test methods then run on the compiled\n"
        "node, and the verdicts merge as in the pipeline's verify row. A\n"
        "PASS on the authored test alone says why the generic check did\n"
        "not run, and COULD NOT RUN when its harness failed.\n"
        "It opens new scenes (file new, force), so it refuses to run while\n"
        "the open scene has unsaved changes: save first, or run it in a\n"
        "fresh mayapy. It prints the folder of the mpynode it imported.\n"
        "The guard trusts Maya's own modified flag, so a selection-only\n"
        "change isn't flagged. A verify leaves its own scene modified, so\n"
        "a second run in the same session is refused too: clear that\n"
        "scene with cmds.file(new=True, force=True) first.\n"
        "Run as a script, a FAIL raises, so mayapy exits 1 and Maya shows\n"
        "an error; a PASS or SKIP exits 0. run() returns False on a FAIL.\n"
        '"""\n'
        "import os, json\n"
        "import maya.cmds as cmds\n"
        'if __name__ == "__main__" and not hasattr(cmds, "file"):\n'
        "    # Run as `mayapy verify_in_maya.py`: Maya has not started. Start\n"
        "    # it before mpynode is imported, so a userSetup.py install's\n"
        "    # paths apply.\n"
        "    import maya.standalone\n"
        "    maya.standalone.initialize()\n"
        "import mpynode\n"
        "from mpynode.native.toolchain import toolchain\n\n"
        "# .mll, .bundle or .so: picked for the OS this runs on.\n"
        "EXT = toolchain.plugin_ext()\n"
        "NAME = " + repr(name) + "\n"
        "BUNDLE = os.path.join(os.path.dirname(__file__), NAME + EXT)\n"
        "SPEC = json.loads(" + repr(json.dumps(spec)) + ")\n\n\n"
    )
    return consts + _BODY
