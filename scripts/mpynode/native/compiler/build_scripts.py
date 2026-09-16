"""build.sh / build.bat / load_test.py generators + write_plugin."""
from __future__ import annotations

import os

from mpynode.native.toolchain import toolchain
from .node_scaffold import generate_cpp


def _libs_for(spec):
    base = spec.get("suggested", {}).get("mpx_base", "MPxNode")
    libs = ["OpenMaya", "Foundation"]
    if base in ("MPxDeformerNode", "MPxSkinCluster", "MPxGeometryFilter",
                "MPxIkSolverNode", "MPxLocatorNode"):
        # MPxLocatorNode draw override reads the frame via MAnimControl (Anim).
        libs.append("OpenMayaAnim")
    if base == "MPxLocatorNode":
        libs += ["OpenMayaUI", "OpenMayaRender"]
    # A compiled mPyFile carries a VP2 MPxShadingNodeOverride (MHWRender::*),
    # which lives in OpenMayaRender.
    if spec.get("mpy_type") == "mPyFile" and "OpenMayaRender" not in libs:
        libs.append("OpenMayaRender")
    return libs

def generate_build_sh(spec: dict, maya=None) -> str:
    """Bash build script (macOS / Linux). Reference + standalone rebuild path.

    A hover-capable locator (``spec['needs_hover']``) links Maya's Qt frameworks
    (its self-contained C++ hover service includes QCursor/QWidget) + an rpath so
    the bundle resolves Qt at load -- mirrors ``toolchain.qt_link_flags``.

    ``maya`` is provenance only; the Maya root is resolved at RUN time from the
    optional version argument (``./build.sh 2026``).
    """
    name     = spec["suggested"]["node_type_name"]
    libflags = " ".join("-l%s" % l for l in _libs_for(spec))
    lines = [
        "#!/usr/bin/env bash",
        "# Generated build for native node '%s'." % name,
        "#",
        "# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026",
        "# With no argument the newest installed Maya is used; MAYA=<path>",
        "# overrides discovery.",
    ] + toolchain.build_provenance(maya) + [
        "set -euo pipefail",
    ] + toolchain.maya_resolver_sh("darwin") + [
        'HERE="$(cd "$(dirname "$0")" && pwd)"',
        # Mirrors toolchain.compile_to_plugin_cmd. -ffp-contract=off is MANDATORY
        # for byte-parity: clang defaults to contract=on and fuses `a*b + c` into
        # one FMA (one rounding, not two), drifting from numpy. py_to_cpp's fused
        # loops are full of `a - (b*c)`, so this is live -- the old
        # -O2-without-contract default produced non-bit-parity binaries.
        "clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -bundle \\",
        "  -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL \\",
        "  -Wno-nontrivial-memcall \\",
        '  -I"$MAYA/include" \\',
        '  -L"$MAYA/Maya.app/Contents/MacOS" \\',
        "  %s \\" % libflags,
    ]
    if spec.get("needs_hover"):
        fw = '"$MAYA/Maya.app/Contents/Frameworks"'
        lines += [
            "  -F%s \\" % fw,
            "  -framework QtCore -framework QtGui -framework QtWidgets \\",
            "  -Wl,-rpath,%s \\" % fw,
        ]
    lines += [
        '  -o "$HERE/%s.bundle" "$HERE/%s.cpp"' % (name, name),
        'echo "Built: $HERE/%s.bundle"' % name,
        'lipo -info "$HERE/%s.bundle"' % name,
        "",
    ]
    return "\n".join(lines)

def generate_build_bat(spec: dict, maya=None) -> str:
    """Windows ``cl.exe`` build script. Self-bootstraps MSVC via vswhere +
    vcvarsall x64, so it runs from any cmd.exe; an *x64 Native Tools Command
    Prompt for VS* is used as-is. Mirrors ``native.toolchain.compile_to_plugin_cmd``
    for MSVC.

    ``maya`` is provenance only; the Maya root is resolved at RUN time from the
    optional version argument (``build.bat 2026``).
    """
    name = spec["suggested"]["node_type_name"]
    libs = " ".join("%s.lib" % l for l in _libs_for(spec))
    # A hover-capable locator also links Maya's Qt import libs (best-effort; only
    # macOS is build-verified). No rpath on Windows -- Qt6*.dll sits next to maya.exe.
    qt_inc   = ""
    needs_qt = bool(spec.get("needs_hover"))
    if needs_qt:
        libs = libs + " Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib"
        # Maya's Qt headers are NOT under <maya>/include (the devkit ships them
        # as an unextracted archive), so the dir has to go on the line -- but it
        # is resolved by the SCRIPT (qt_resolver_bat -> %QTINC%), not by this
        # host. Resolving here meant only a Windows generator could emit a
        # working recipe, and this project is generated on macOS: the script
        # shipped with neither the include path nor the MSVC Qt flags and died
        # at C1083. The MSVC-only flags Qt 6 requires ride along with it, or the
        # hand rebuild dies at C1189/C2338 while the programmatic build
        # (qt_compile_flags) succeeds. One source of truth.
        qt_inc = (' %s /I "%%QTINC%%" /FI %s'
                  % (" ".join(toolchain.qt_msvc_flags()),
                     toolchain.QT_MSVC_COMPAT_HEADER))
    pre, out_args, post = toolchain.link_via_temp_bat(name, "%HERE%" + name + ".mll")
    return "\r\n".join([
        "@echo off",
        "setlocal",
        "REM Generated build for native node '%s'." % name,
        "REM Runs from any cmd.exe: MSVC is located via vswhere and vcvarsall x64",
        "REM is called for you. An 'x64 Native Tools Command Prompt' is used as-is.",
        "REM",
        "REM Usage:  build.bat [maya-version]      e.g. build.bat 2026",
        "REM With no argument the newest installed Maya is used; set MAYA to",
        "REM override discovery.",
    ] + toolchain.build_provenance(maya, "REM")
      + toolchain.msvc_resolver_bat()
      + toolchain.maya_resolver_bat("win32")
      + (  # Must follow the Maya resolver: the Qt probe reads %MAYA%\include.
        toolchain.qt_resolver_bat() if needs_qt else []) + [
        'set "HERE=%~dp0"',
        *pre,
        # /fp:precise is MSVC's -ffp-contract=off (mirrors _MSVC_CXXFLAGS): it
        # keeps mul+add from contracting into an FMA.
        ('cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 '
         '/D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS '
         '/D _CRT_SECURE_NO_WARNINGS '
         '/I "%%MAYA%%\\include"%s "%%HERE%%%s.cpp" /Fo"%%HERE%%%s.obj" '
         '/link /LIBPATH:"%%MAYA%%\\lib" %s %s '
         '/EXPORT:initializePlugin /EXPORT:uninitializePlugin'
         % (qt_inc, name, name, libs, out_args)),
        *post,
        # cl /LD drops <name>.obj in the CWD; /Fo above pins it beside the
        # script so this can remove it (link byproducts went with the temp folder).
        'del "%%HERE%%%s.obj" 2>nul' % name,
        'echo Built: %%HERE%%%s.mll' % name,
        # Cleanup is best effort; it must not decide the exit status.
        "exit /b 0",
        "",
    ])

def generate_build_script(spec: dict, maya=None, os_name=None):
    """Platform build script as ``(filename, contents)``.

    ``build.sh`` on macOS/Linux, ``build.bat`` on Windows. Single entry point so
    callers don't branch on platform.
    """
    if toolchain.is_windows(os_name):
        return "build.bat", generate_build_bat(spec, maya=maya)
    return "build.sh", generate_build_sh(spec, maya=maya)

def write_plugin(spec: dict, out_dir: str) -> dict:
    """Emit ``<node>.cpp`` + build script + ``load_test.py`` into ``out_dir``.

    The build script is ``build.sh`` (macOS/Linux) or ``build.bat`` (Windows).
    Raises UnsupportedSpec (via generate_cpp) before writing anything if the
    spec is out of phase-1 scope.
    """
    name    = spec["suggested"]["node_type_name"]
    cpp_src = generate_cpp(spec)  # validates first
    os.makedirs(out_dir, exist_ok=True)
    build_name, build_src = generate_build_script(spec)
    paths = {
        "cpp":       os.path.join(out_dir, name + ".cpp"),
        "build_sh":  os.path.join(out_dir, build_name),
        "load_test": os.path.join(out_dir, "load_test.py"),
        "node":      name,
    }
    with open(paths["cpp"], "w", encoding="utf-8") as f:
        f.write(cpp_src)
    # newline="": generate_build_bat emits its own CRLF and generate_build_sh
    # its own LF. A second translation on a Windows host turns the .bat into
    # \r\r\n and the .sh into CRLF ("$'\r': command not found"). No-op on macOS.
    with open(paths["build_sh"], "w", newline="", encoding="utf-8") as f:
        f.write(build_src)
    if not toolchain.is_windows():
        os.chmod(paths["build_sh"], 0o755)
    # A Windows Qt build force-includes toolchain.QT_MSVC_COMPAT_HEADER by BARE
    # name, so the copy has to sit beside the .cpp for build.bat to find it.
    toolchain.ship_qt_msvc_compat_header(out_dir, bool(spec.get("needs_hover")))
    with open(paths["load_test"], "w", encoding="utf-8") as f:
        f.write(generate_load_test(spec))
    return paths

def generate_load_test(spec: dict) -> str:
    name        = spec["suggested"]["node_type_name"]
    plugin_file = name + toolchain.plugin_ext()
    return "\n".join([
        '"""Smoke-load the generated %s plugin in Maya."""' % name,
        "import os",
        "import maya.cmds as cmds",
        "",
        'BUNDLE = os.path.join(os.path.dirname(__file__), "%s")' % plugin_file,
        "",
        "",
        "def run():",
        "    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):",
        "        cmds.loadPlugin(BUNDLE)",
        '    node = cmds.createNode("%s")' % name,
        '    print("created", node)',
        "    return node",
        "",
        "",
        'if __name__ == "__main__":',
        "    run()",
        "",
    ])
