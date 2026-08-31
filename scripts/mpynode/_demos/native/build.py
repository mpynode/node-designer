"""Compile the hand-ported ``mPyMeshSDF.cpp`` into a Maya plugin.

This is a REFERENCE build for the SDF dual-marching-cubes demo: a golden,
by-hand C++ translation of ``mpynode._common.nodes.mesh.sdf_dmc`` that the toolkit's
on-demand auto-porter is expected to reproduce. Run it under any ``mayapy``
to get a loadable plugin you can parity-check with :mod:`parity`.

Usage (from a shell)::

    mayapy -B build.py                 # newest installed Maya, bundle in ./build
    MAYA_ROOT=/path/to/maya mayapy -B build.py

It routes through :mod:`mpynode.native.toolchain.toolchain` so the clang/gcc/MSVC recipe
is identical to the toolkit's own compile path on every platform, then ad-hoc
codesigns on macOS (an unsigned .bundle loads, but an in-place replace can be
SIGKILL'd by Gatekeeper -- ad-hoc signing is the proven fix).
"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ is three levels up: _demos/native -> _demos -> mpynode -> scripts
_SCRIPTS = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
sys.dont_write_bytecode = True

from mpynode.native.toolchain import toolchain

SRC = os.path.join(_HERE, "mPyMeshSDF.cpp")


def _maya_root():
    env = os.environ.get("MAYA_ROOT")
    if env:
        return env
    installs = toolchain.discover_maya_installs()
    if installs:
        return installs[-1]["root"]
    return toolchain.default_maya_dir()


def build(out_dir=None):
    maya = _maya_root()
    # Build into a temp dir by default so no .bundle lands in the source tree.
    out_dir = out_dir or os.path.join(tempfile.gettempdir(), "mpynode_native_build")
    os.makedirs(out_dir, exist_ok=True)
    bundle = os.path.join(out_dir, "mPyMeshSDF" + toolchain.plugin_ext())

    exe = toolchain.resolve_compiler(toolchain.default_compiler())
    cmd = toolchain.compile_to_plugin_cmd(
        exe, SRC, bundle,
        include_dir=toolchain.maya_include_dir(maya),
        lib_dir=toolchain.maya_lib_dir(maya),
        libs=["OpenMaya", "Foundation"],
        arch=toolchain.mac_arch() if toolchain.is_macos() else None,
    )
    sys.stderr.write("COMPILE: " + " ".join(cmd) + "\n")
    rc, _out = toolchain.run_streaming(cmd, log_cb=lambda l: sys.stderr.write(l + "\n"))
    if rc != 0:
        raise SystemExit("compile failed rc=%d" % rc)

    if toolchain.is_macos():
        subprocess.run(["codesign", "--force", "--sign", "-", bundle],
                       capture_output=True, text=True)
    sys.stderr.write("BUILT %s\n" % bundle)
    return bundle


if __name__ == "__main__":
    build()
