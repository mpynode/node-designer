"""ADVERSARIAL VERIFY probe: does the for_port=False branch of emit_compute
really produce a COMPILABLE, LOADABLE stub plug-in with a TODO + commented
Python body + stub-default outputs + full initializePlugin/registerNode?

Sections:
  A  source-level: print emit_compute.py else-branch verbatim
  B  generate_cpp(spec, for_port=False) on a cv2 (unportable) compute
  C  compile the emitted .cpp to a real Maya plug-in, then LOAD it, create the
     node, and read the output plug
  D  control: does the SAME spec get an artifact when the compute is scipy KDTree
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.environ["MPYNODE_ROOT"], "scripts"))
# The suite lives at the repo root, alongside scripts/ rather than inside it.
sys.path.insert(0, os.environ["MPYNODE_ROOT"])

from tests._setup import standalone_init, ensure_plugins_loaded


def hdr(t):
  print("\n" + "=" * 72)
  print(t)
  print("=" * 72)


def section_a():
  hdr("A. SOURCE: emit_compute.py for_port=False else-branch (lines 283-302)")
  p = os.path.join(os.environ["MPYNODE_ROOT"],
                   "scripts/mpynode/native/compiler/emit_compute.py")
  with open(p) as f:
    lines = f.readlines()
  for n in range(282, 302):
    print("%4d\t%s" % (n + 1, lines[n].rstrip()))


def make_spec(compute_src, node_type, arr_input=False):
  import maya.cmds as cmds
  from mpynode import MPyNode
  from mpynode.native.spec import spec_extractor

  w = MPyNode.create(name="probeSrc#")
  if arr_input:
    w.add_input_attr("pixels", "float", is_array=True)
  else:
    w.add_input_attr("pixels", "float")
  w.add_output_attr("result", "float")
  w.set_compute_expression(compute_src)
  spec                                = spec_extractor.extract_spec(w.get_name())
  spec["suggested"]["node_type_name"] = node_type
  spec["suggested"]["class_name"]     = node_type
  return spec


CV2_COMPUTE = (
  "import cv2\n"
  "blurred = cv2.GaussianBlur(self.pixels, (5, 5), 1.5)\n"
  "self.result = float(blurred.mean())\n")

KDTREE_COMPUTE = (
  "from scipy.spatial import cKDTree\n"
  "tree = cKDTree(self.pixels.reshape(-1, 1))\n"
  "d, i = tree.query(self.pixels.reshape(-1, 1), k=1)\n"
  "self.result = float(d.sum())\n")


def section_b(spec, label):
  hdr("B. generate_cpp(spec, for_port=False)  [%s]" % label)
  from mpynode.native import compiler as codegen
  cpp = codegen.generate_cpp(spec, for_port=False)
  # print from the compute() signature to the end
  idx   = cpp.find("::compute(")
  start = cpp.rfind("\n", 0, idx)
  print(cpp[start:])
  print("\n---- ASSERTIONS ----")
  checks = [
    ("TODO comment",
     "// TODO: translate the Python compute below into C++." in cpp),
    ("python-as-comment (cv2/scipy line)",
     ("//   | import cv2" in cpp) or ("//   | from scipy.spatial" in cpp)),
    ("stub-default outputs header", "// --- outputs (stub defaults) ---" in cpp),
    ("return MS::kSuccess;", "return MS::kSuccess;" in cpp),
    ("initializePlugin", "MStatus initializePlugin(MObject obj)" in cpp),
    ("registerNode", "plugin.registerNode(" in cpp),
    ("uninitializePlugin", "MStatus uninitializePlugin(MObject obj)" in cpp),
  ]
  for name, ok in checks:
    print("  %-38s %s" % (name, "PRESENT" if ok else "*** MISSING ***"))
  return cpp


def section_c(cpp, node_type):
  hdr("C. COMPILE + LOAD the emitted stub")
  from mpynode.native import compiler as codegen
  from mpynode.native.toolchain import toolchain

  outdir = tempfile.mkdtemp(prefix="forport-false-")
  src    = os.path.join(outdir, node_type + ".cpp")
  with open(src, "w") as f:
    f.write(cpp)
  plugin = os.path.join(outdir, node_type + ".bundle")
  maya   = toolchain.default_maya_dir()
  cmd = toolchain.compile_to_plugin_cmd(
    toolchain.default_compiler(), src, plugin,
    include_dir = toolchain.maya_include_dir(maya),
    lib_dir     = toolchain.maya_lib_dir(maya),
    libs        = codegen._libs_for({}),
    arch        = toolchain.mac_arch(),
    maya        = maya,
  )
  print("cpp:    %s" % src)
  print("cmd:    %s" % " ".join(cmd))
  r = subprocess.run(cmd, capture_output=True, text=True)
  print("rc:     %s" % r.returncode)
  if r.stdout.strip():
    print("stdout:\n%s" % r.stdout[-4000:])
  if r.stderr.strip():
    print("stderr:\n%s" % r.stderr[-4000:])
  if r.returncode != 0:
    print("*** COMPILE FAILED -- claim's 'COMPILABLE' is REFUTED ***")
    return False
  print("COMPILE OK -> %s (%d bytes)" % (plugin, os.path.getsize(plugin)))

  import maya.cmds as cmds
  try:
    cmds.loadPlugin(plugin)
  except Exception as exc:
    print("*** LOAD FAILED: %s ***" % exc)
    return False
  print("LOAD OK. registered node types from plugin: %s"
        % cmds.pluginInfo(os.path.basename(plugin), q=True, dependNode=True))
  n = cmds.createNode(node_type)
  cmds.setAttr(n + ".pixels", 3.0)
  print("createNode OK: %s   .result = %s" % (n, cmds.getAttr(n + ".result")))
  return True


def main():
  standalone_init()
  ensure_plugins_loaded()
  import maya.cmds as cmds
  cmds.file(new=True, force=True)

  section_a()

  spec = make_spec(CV2_COMPUTE, "probeNode")
  cpp  = section_b(spec, "cv2 GaussianBlur -- no deterministic lowering")
  ok   = section_c(cpp, "probeNode")

  hdr("D. CONTROL: same emitter, scipy cKDTree compute")
  cmds.file(new=True, force=True)
  spec2 = make_spec(KDTREE_COMPUTE, "probeKdNode")
  try:
    cpp2 = section_b(spec2, "scipy cKDTree")
    section_c(cpp2, "probeKdNode")
  except Exception as exc:
    print("emitter raised for kdtree spec: %s: %s" % (type(exc).__name__, exc))

  hdr("RESULT")
  print("cv2 stub compilable+loadable: %s" % ok)


if __name__ == "__main__":
  main()
