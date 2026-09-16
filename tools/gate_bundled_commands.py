"""End-to-end gate for @maya_command -> MPxCommand inside the node's OWN bundle.

Builds a real .bundle from the generated C++, loads it in Maya, and calls the
commands through ``maya.cmds`` -- proving the whole chain rather than just that
the codegen produced plausible text.

Covers the things that were measured to go wrong:
  * flags of every supported type actually reach Python with the right VALUE
    and the right PYTHON TYPE (a kString guess for a list was measured to
    decompose a node name character by character);
  * an ABSENT flag falls through to the Python default and is never
    materialised as an empty value (measured: doing so silently produced a
    zero-rider result with no error);
  * results keep their type -- int stays int, list stays list (routing
    everything through the string channel would be a regression against the
    Python companion's typed setResult);
  * the whole command is ONE undo;
  * NO Python runs at plug-in load (the bundle must register with mpynode
    unimportable, or a merged plug-in loses every node when one command fails).

Run with mayapy (see tools/run_tests.sh for the env):
  <mayapy> tools/gate_bundled_commands.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
os.environ.setdefault("MPYNODE_ROOT", _ROOT)

MAYA = "/Applications/Autodesk/maya2026"

FAILURES = []


def check(ok, what, extra=""):
    print("  %s  %s%s" % ("ok  " if ok else "FAIL", what,
                          ("  [%s]" % extra) if extra and not ok else ""))
    if not ok:
        FAILURES.append(what)


# A methods source exercising the whole flag/return matrix. It does NOT
# import maya_command: build_methods_namespace injects that name (plus
# maya_demo/maya_test and test_helpers.HELPERS) before exec'ing this source, so
# the decorators below bind the copy VENDORED into the bundle -- which is what
# makes the mpynode-free invocation at the end of main() a real test of the
# prelude. An import here would be exec'd on the bare machine and raise
# ModuleNotFoundError at the first CALL (measured), and would shadow the
# injected name even where it resolved.
METHODS = '''
@maya_command(name="gateEcho")
def echo(self, text: str = "dflt", count: int = 3, scale: float = 1.5,
         loud: bool = False):
    """Every scalar flag type, all with defaults so absence is testable."""
    return "%s|%d|%.3f|%d" % (text, count, scale, 1 if loud else 0)


@maya_command(name="gateSum")
def total(self, values: list[float]):
    """Multi-use float flag -> a real Python list of floats."""
    return sum(values)


@maya_command(name="gateNames")
def names(self, items: list[str]):
    """Multi-use string flag; returns a list so result typing is checked."""
    return [s.upper() for s in items]


@maya_command(name="gateTypes")
def types_of(self, values: list[float], text: str = "x"):
    """Report the PYTHON types that arrived, so a wrong coercion is visible."""
    return "%s/%s/%s" % (type(values).__name__,
                         type(values[0]).__name__ if values else "-",
                         type(text).__name__)


@maya_command(name="gateCount")
def count_ints(self, nums: list[int]):
    return len(nums)


@maya_command(name="gateMakeNodes", undoable=True)
def make_nodes(self, prefix: str = "gate"):
    """Three scene mutations -- the whole command must be ONE undo."""
    from maya import cmds
    a = cmds.createNode("transform", name=prefix + "A")
    b = cmds.createNode("transform", name=prefix + "B")
    cmds.setAttr(b + ".tx", 5.0)
    return [a, b]


@maya_command(name="gateDict")
def as_dict(self):
    return {"a": 1, "b": [2, 3]}
'''


def build_bundle(tmp):
    from mpynode._common.methods.maya_command import detect_commands
    from mpynode.native.compiler.kernels import command_dispatch as cd
    from mpynode.native.toolchain import toolchain

    cmds_found = detect_commands(METHODS)
    out        = cd.emit_dispatch_commands(cmds_found, "gateProbeNode", METHODS)
    if out["errors"]:
        for e in out["errors"]:
            check(False, "codegen error: %s" % e)
        return None, cmds_found

    src = os.path.join(tmp, "gate_cmds.cpp")
    with open(src, "w") as fh:
        fh.write("\n".join("#include <%s>" % h for h in out["includes"]))
        fh.write("\n#include <maya/MFnPlugin.h>\n")
        fh.write(out["classes"])
        fh.write("\nMStatus initializePlugin(MObject obj) {\n")
        fh.write('    MFnPlugin plugin(obj, "mpynode-gate", "1.0", "Any");\n')
        for r in out["register"]:
            fh.write("    " + r + "\n")
        fh.write("    return MS::kSuccess;\n}\n")
        fh.write("MStatus uninitializePlugin(MObject obj) {\n")
        fh.write("    MFnPlugin plugin(obj);\n")
        for d in out["deregister"]:
            fh.write("    " + d + "\n")
        fh.write("    return MS::kSuccess;\n}\n")

    bundle = os.path.join(tmp, "gateCmds.bundle")
    cmd = toolchain.compile_to_plugin_cmd(
        "clang++", src, bundle,
        include_dir = toolchain.maya_include_dir(MAYA),
        lib_dir     = toolchain.maya_lib_dir(MAYA),
        libs=["OpenMaya", "OpenMayaAnim", "OpenMayaUI", "OpenMayaRender",
              "Foundation"],
        arch=toolchain.mac_arch(), maya=MAYA)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        check(False, "generated C++ compiles")
        print(p.stderr[:8000])
        return None, cmds_found
    check(True, "generated C++ compiles (%d bytes)" % os.path.getsize(bundle))
    return bundle, cmds_found


def main():
    try:
        from PySide6.QtWidgets import QApplication            # noqa: F401
    except ImportError:
        pass

    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds as mc

    tmp = tempfile.mkdtemp(prefix="mpy_gate_cmds_")
    try:
        print("\n[build]")
        bundle, found = build_bundle(tmp)
        if bundle is None:
            print("\n%d PROBLEM(S)" % len(FAILURES))
            return 1
        check(len(found) == 7, "detected 7 commands (got %d)" % len(found))

        print("\n[load -- must need NO Python at initializePlugin]")
        mc.loadPlugin(bundle)
        loaded = mc.pluginInfo(os.path.basename(bundle), q=True, loaded=True)
        check(bool(loaded), "the bundle loads")
        reg = set(mc.pluginInfo(os.path.basename(bundle), q=True,
                                command=True) or [])
        for name in ("gateEcho", "gateSum", "gateNames", "gateTypes",
                     "gateCount", "gateMakeNodes", "gateDict"):
            check(name in reg, "%s is registered by the BUNDLE itself" % name)

        # These are self-first INSTANCE commands, so they need a target node --
        # a compiled command has no implicit self. Named explicitly here; the
        # active-selection fallback is checked separately below.
        tgt = mc.createNode("transform", name="gateTarget")

        print("\n[flags reach Python with the right value and type]")
        r = mc.gateEcho(tgt, text="hi", count=7, scale=2.25, loud=True)
        check(r == "hi|7|2.250|1", "all scalar flags round-trip", r)
        r = mc.gateEcho(tgt)
        check(r == "dflt|3|1.500|0",
              "ABSENT flags fall through to the Python defaults", r)
        r = mc.gateEcho(tgt, count=9)
        check(r == "dflt|9|1.500|0", "a partial flag set keeps other defaults", r)

        r = mc.gateSum(tgt, values=[1.5, 2.25, 3.0])
        check(abs(r - 6.75) < 1e-9, "multi-use float flag sums correctly", r)
        r = mc.gateTypes(tgt, values=[1.0, 2.0], text="q")
        check(r == "list/float/str",
              "a list flag arrives as a real list of floats", r)
        r = mc.gateNames(tgt, items=["ab", "cd"])
        check(r == ["AB", "CD"], "multi-use string flag preserves ORDER", r)
        r = mc.gateCount(tgt, nums=[1, 2, 3, 4])
        check(r == 4, "multi-use int flag", r)

        print("\n[target resolution]")
        mc.select(tgt, replace=True)
        r = mc.gateEcho(text="sel")
        check(r == "sel|3|1.500|0",
              "an unnamed target falls back to the active selection", r)
        mc.select(clear=True)
        try:
            mc.gateEcho(text="none")
            check(False, "no target + empty selection must raise")
        except RuntimeError as exc:
            check("select (or name) the target node" in str(exc),
                  "no target + empty selection raises a clear error", str(exc))

        print("\n[result types survive]")
        check(isinstance(mc.gateCount(tgt, nums=[1, 2]), int),
              "an int return stays an int")
        check(isinstance(mc.gateNames(tgt, items=["z"]), list),
              "a list return stays a list")
        check(isinstance(mc.gateSum(tgt, values=[1.0]), float),
              "a float return stays a float")
        d = mc.gateDict(tgt)
        check(isinstance(d, str) and '"a": 1' in d,
              "a dict return comes back as JSON (no MPxCommand dict type)", d)

        print("\n[undo atomicity -- the whole command is ONE undo]")
        mc.undoInfo(state=True, infinity=True)
        mc.file(new=True, force=True)
        mc.loadPlugin(bundle) if not mc.pluginInfo(
            os.path.basename(bundle), q=True, loaded=True) else None
        sentinel = mc.createNode("transform", name="sentinel")
        made     = mc.gateMakeNodes(sentinel, prefix="gate")
        check(mc.objExists("gateA") and mc.objExists("gateB"),
              "the command built its nodes", str(made))
        check(abs(mc.getAttr("gateB.tx") - 5.0) < 1e-9, "and set the attr")
        mc.undo()
        gone = not mc.objExists("gateA") and not mc.objExists("gateB")
        check(gone, "ONE undo reverts all three mutations")
        check(mc.objExists("sentinel"),
              "and does NOT touch the unrelated earlier node")
        mc.redo()
        check(mc.objExists("gateA") and mc.objExists("gateB"),
              "redo restores them")

        print("\n[no Python at load: the bundle registers with mpynode absent]")
        # A child mayapy with PYTHONPATH stripped: if anything Python ran at
        # initializePlugin, registration would silently fail and, in a merged
        # bundle, take every other node down with it.
        script = os.path.join(tmp, "noimport.py")
        with open(script, "w") as fh:
            fh.write(
                "import maya.standalone; maya.standalone.initialize('python')\n"
                "from maya import cmds as mc\n"
                "mc.loadPlugin(%r)\n"
                "import os\n"
                "n = os.path.basename(%r)\n"
                "print('LOADED', bool(mc.pluginInfo(n, q=True, loaded=True)))\n"
                "print('CMDS', sorted(mc.pluginInfo(n, q=True, command=True)"
                " or []))\n"
                # Registration is only half the chain: the command BODIES are
                # embedded Python that first runs on CALL, so an mpynode import
                # in the dispatch prelude or in a body is invisible until here.
                "try:\n"
                "    import mpynode; print('MPYNODE-AT', mpynode.__file__)\n"
                "except ImportError:\n"
                "    print('MPYNODE-ABSENT')\n"
                "t = mc.createNode('transform', name='coldTarget')\n"
                "print('ECHO', mc.gateEcho(t, text='hi', count=7, scale=2.25,"
                " loud=True))\n"
                "print('DFLT', mc.gateEcho(t))\n"
                "print('SUM', mc.gateSum(t, values=[1.5, 2.25, 3.0]))\n"
                "print('NAMES', mc.gateNames(t, items=['ab', 'cd']))\n"
                "print('MADE', mc.gateMakeNodes(t, prefix='cold'))\n"
                % (bundle, bundle))
        env                      = dict(os.environ)
        env["PYTHONPATH"]        = ""          # mpynode is now unimportable
        env["MAYA_PLUG_IN_PATH"] = ""
        # ...but PYTHONPATH alone does NOT make a machine mpynode-free, and a
        # child that can still import it makes every check below vacuous:
        #   * a user-site .pth (this machine carried one pointing at a scratch
        #     mpynode copy until it was deleted) is applied by site.py to EVERY
        #     interpreter, PYTHONPATH or not;
        #   * Maya runs the first userSetup.py it finds on sys.path, and the
        #     inherited cwd is the repo, whose userSetup.py re-adds scripts/.
        # Hence PYTHONNOUSERSITE + cwd=tmp, and the MPYNODE-ABSENT assertion.
        env["PYTHONNOUSERSITE"] = "1"
        p = subprocess.run(
            [os.path.join(MAYA, "Maya.app/Contents/bin/mayapy"), script],
            capture_output=True, text=True, env=env, cwd=tmp)
        got  = p.stdout
        tail = (got + p.stderr)[-1500:]
        check("LOADED True" in got,
              "the bundle loads with mpynode unimportable", got[-400:])
        check("gateEcho" in got,
              "and still registers its commands", got[-400:])
        check("MPYNODE-ABSENT" in got,
              "the child really cannot import mpynode", tail)
        check("ECHO hi|7|2.250|1" in got,
              "a command RUNS there -- the embedded Python needs no mpynode",
              tail)
        check("DFLT dflt|3|1.500|0" in got,
              "and absent flags still fall through to the defaults", tail)
        check("SUM 6.75" in got, "a list flag still reaches the body", tail)
        check("NAMES ['AB', 'CD']" in got,
              "and a list result still comes back typed", tail)
        check("MADE ['coldA', 'coldB']" in got,
              "an undoable command still mutates the scene", tail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("ALL PASS" if not FAILURES
                    else "%d PROBLEM(S)" % len(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
