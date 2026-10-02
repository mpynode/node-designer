"""Combine compiled MPyNode node sources into ONE Maya plug-in.

    mayapy -m mpynode.native.bundle NAME INPUT... [--maya VER] [options]
    mayapy -m mpynode.native.bundle --check INPUT... [--maya VER]
    mayapy -m mpynode.native.bundle --refresh DIR [--from-self]

``tools/bundle.bat`` and ``tools/bundle.sh`` find a mayapy and run this.

INPUT (any mix; wildcards are expanded here, so they work from cmd.exe)
  X.cpp          a node source: a single-node compile's build/source/<node>.cpp,
                 a multi-node compile's fragment (used as-is), or the scratch
                 build/<node>/<node>.cpp (its placeholder ids come from the
                 sibling manifest)
  FOLDER         every node in FOLDER/build/source (plugin_main / shared unit skipped)
  FOLDER::a,b    only node types a and b from FOLDER
  @list.txt      one INPUT per line, '#' comments

exit status
  0  ok                     1  compile, link or load check failed
  2  refused by pre-flight  3  usage or input error

Everything that decides what goes in lives in
:mod:`mpynode.native.toolchain.bundle_plan`; this file is the argument parsing
and the printing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import List, Optional

from mpynode.native.toolchain import bundle_plan, toolchain

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

EXIT_OK, EXIT_BUILD, EXIT_REFUSED, EXIT_USAGE = 0, 1, 2, 3


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog        = "mpynode.native.bundle",
        description = "Combine compiled MPyNode node sources into one Maya plug-in.",
        epilog      = "INPUT (any mix" + __doc__.split("INPUT (any mix", 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("args", nargs="*", metavar="NAME INPUT...",
                   help="the plug-in name, then the inputs")
    p.add_argument("--check", action="store_true",
                   help="run every pre-flight check on the inputs; write nothing")
    p.add_argument("--refresh", metavar="DIR",
                   help="rebuild DIR's bundle from the inputs its manifest lists")
    p.add_argument("--from-self", action="store_true",
                   help="with --refresh: rebuild from DIR/build/source instead")
    p.add_argument("--maya", metavar="VER|ROOT",
                   help="target Maya: a version (2025) or an install root. Default: "
                        "the Maya this mayapy belongs to; required when that cannot "
                        "be told and more than one devkit is installed")
    p.add_argument("--out", metavar="DIR",
                   help="output folder (default ./NAME); must be new, empty, or one "
                        "the bundler wrote. The plug-in lands in DIR/<maya year>/"
                        "NAME.mll (.bundle on macOS), its build tree in DIR/build")
    p.add_argument("--exclude", action="append", default=[], metavar="T[,T]",
                   help="drop node type(s) after resolving")
    p.add_argument("--pin", action="append", default=[], metavar="KEY=0xID",
                   help="force an id; KEY is a node type or type#Class. Changes what "
                        ".mb scenes saved with the old id bind to")
    p.add_argument("--vendor", default="mpynode-native", help="MFnPlugin vendor")
    p.add_argument("--version", help="MFnPlugin version (default 1.0+<sha12 of the inputs>)")
    p.add_argument("--strict-load", action="store_true",
                   help="the plug-in refuses to load if any member conflicts with the "
                        "session (default: skip that member with a warning)")
    p.add_argument("--best-effort", action="store_true",
                   help="drop members that fail to compile (default: any failure aborts)")
    p.add_argument("--no-compile", action="store_true",
                   help="write build/source, build.bat, build.sh and the manifest only")
    p.add_argument("--no-load-check", action="store_true",
                   help="skip loading the result in the target Maya's mayapy")
    p.add_argument("--json", action="store_true", help="machine-readable plan / report")
    return p


def _resolve_maya(spec: Optional[str]) -> str:
    """An install root with a devkit, from ``--maya`` or the running Maya."""
    installs = toolchain.discover_maya_installs()
    if spec:
        if os.path.isdir(spec):
            if not os.path.isdir(os.path.join(toolchain.maya_include_dir(spec), "maya")):
                raise bundle_plan.InputError("%s has no devkit headers (include/maya)" % spec)
            return spec
        for e in installs:
            if e["version"] == spec or e["label"].lower() == spec.lower():
                return e["root"]
        raise bundle_plan.InputError(
            "no Maya %s with a devkit here; installed: %s"
            % (spec, ", ".join(e["label"] for e in installs) or "none"))
    running = toolchain.running_maya_dir()
    if running:
        return running
    if len(installs) == 1:
        return installs[0]["root"]
    raise bundle_plan.InputError(
        "pass --maya VER; this process is not inside a Maya with a devkit and "
        "%d are installed (%s)" % (len(installs), ", ".join(e["label"] for e in installs)))


def _pins(specs: List[str]) -> dict:
    pins = {}
    for s in specs:
        if "=" not in s:
            raise bundle_plan.InputError("--pin wants KEY=0xID, got %r" % s)
        k, v = s.split("=", 1)
        pins[k.strip()] = v.strip()
    return pins


def _excludes(specs: List[str]) -> List[str]:
    out = []
    for s in specs:
        out += [t.strip() for t in s.split(",") if t.strip()]
    return out


def _say(line: str = "") -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _print_plan(plan: bundle_plan.Plan, members_all) -> None:
    for m in members_all:
        if m.kind == "refused":
            _say("  REFUSED     %-40s %s" % (os.path.basename(m.path), m.reason))
    for m in plan.members:
        main  = m.resolved.get(m.node, "?")
        src   = m.id_source.get(m.node, "")
        extra = []
        if m.commands:
            extra.append("%d command(s)" % len(m.commands))
        if m.needs_qt:
            extra.append("Qt")
        if m.kind == "fragment":
            extra.append("fragment v%d" % m.fragment_version)
        _say("  %-11s %-24s %-10s %-9s %s" % (m.kind, m.node, main, src, " ".join(extra)))
    for w in plan.warnings:
        _say("  warning: %s" % w)
    for code, msg in plan.errors:
        _say("  %s %s" % (code, msg))


def _plan_json(plan, members_all) -> dict:
    return {
        "members": [m.row() for m in plan.members],
        "refused": [{"path": m.path, "reason": m.reason}
                    for m in members_all if m.kind == "refused"],
        "errors":   [{"code": c, "message": m} for c, m in plan.errors],
        "warnings": list(plan.warnings),
        "needs_qt": plan.needs_qt,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ns = _parser().parse_args(argv)
    try:
        maya = _resolve_maya(ns.maya)
        pins = _pins(ns.pin)
        excl = _excludes(ns.exclude)

        if ns.refresh:
            out_dir = os.path.abspath(ns.refresh)
            paths, man = bundle_plan.refresh_inputs(out_dir, from_self=ns.from_self)
            name        = man.get("plugin_name") or os.path.basename(out_dir)
            vendor      = ns.vendor if ns.vendor != "mpynode-native" else man.get("vendor", ns.vendor)
            version     = ns.version or man.get("version")
            strict_load = ns.strict_load or bool(man.get("strict_load"))
            maya        = maya if ns.maya else (man.get("maya") or maya)
        elif ns.check:
            if not ns.args:
                raise bundle_plan.InputError("--check needs at least one INPUT")
            name, paths = "check", bundle_plan.resolve_inputs(ns.args)
            out_dir = vendor = version = strict_load = None
        else:
            if len(ns.args) < 2:
                raise bundle_plan.InputError("usage: NAME INPUT... (see --help)")
            name = ns.args[0]
            if not _NAME_RE.match(name):
                raise bundle_plan.InputError(
                    "%r is not a plug-in name: letters, digits and _ only (Maya takes "
                    "the plug-in's name from the file name)" % name)
            paths       = bundle_plan.resolve_inputs(ns.args[1:])
            out_dir     = os.path.abspath(ns.out or name)
            vendor      = ns.vendor
            version     = ns.version
            strict_load = ns.strict_load
    except bundle_plan.InputError as exc:
        _say("bundle: %s" % exc)
        return EXIT_USAGE

    members = [bundle_plan.scan(p) for p in paths]
    plan    = bundle_plan.preflight(members, maya=maya, exclude=excl, pins=pins)

    if ns.check:
        if ns.json:
            _say(json.dumps(_plan_json(plan, members), indent=1))
        else:
            _say("target Maya: %s" % maya)
            _print_plan(plan, members)
            _say("pre-flight: %s" % ("ok, %d member(s)" % len(plan.members)
                                     if plan.ok else "REFUSED (%s)" % ", ".join(
                                         sorted({c for c, _m in plan.errors}))))
        return EXIT_OK if plan.ok else EXIT_REFUSED

    if not ns.json:
        _say("target Maya: %s" % maya)
        _say("out        : %s" % out_dir)
        _print_plan(plan, members)
    if not plan.ok:
        if ns.json:
            _say(json.dumps(_plan_json(plan, members), indent=1))
        else:
            _say("pre-flight: REFUSED")
        return EXIT_REFUSED

    log = None if ns.json else (lambda ev: None)
    try:
        report = bundle_plan.build(
            plan, name, out_dir, maya=maya, compile_now=not ns.no_compile,
            best_effort=ns.best_effort, strict_load=strict_load, vendor=vendor,
            version=version, log_cb=log)
    except bundle_plan.BundleRefused as exc:
        for code, msg in exc.errors:
            _say("  %s %s" % (code, msg))
        return EXIT_REFUSED

    result = {"plan": _plan_json(plan, members), "report": report, "load_check": None}
    ok     = bool(report.get("ok"))
    if not ns.json:
        for rec in report.get("nodes", []):
            _say("  %-11s %-24s %s" % (rec.get("status", "?"), rec.get("name"),
                                       rec.get("reason") or ""))
        if not ok:
            _say("build: FAILED -- %s" % (report.get("reason") or "see the nodes above"))
            tail = (report.get("stderr") or "").strip().splitlines()[-12:]
            for ln in tail:
                _say("    " + ln)
        elif ns.no_compile:
            _say("generated: %s (build with build\\build.bat / build/build.sh)"
                 % os.path.join(out_dir, "build"))
        else:
            _say("built    : %s" % report.get("bundle"))
        if report.get("older_plugin_note"):
            _say("  %s" % report["older_plugin_note"])
        _say("manifest : %s" % report.get("manifest"))

    if ok and not ns.no_compile and not ns.no_load_check:
        expected = [rec["name"] for rec in report.get("nodes", [])
                    if rec.get("status") == "compiled"]
        lc                   = bundle_plan.load_check(report["bundle"], expected, maya)
        result["load_check"] = lc
        if not ns.json:
            if lc["ok"]:
                _say("load check: ok -- %d type(s), %d command(s) in %s"
                     % (len(lc["registered"]), len(lc["commands"]),
                        os.path.basename(lc["mayapy"])))
            else:
                _say("load check: FAILED -- %s" % (lc.get("error") or
                     ("missing %s" % lc["missing"] if lc["missing"] else
                      "createNode failed: %s" % lc["create_failed"])))
        ok = ok and lc["ok"]

    if ns.json:
        _say(json.dumps(result, indent=1, default=str))
    return EXIT_OK if ok else EXIT_BUILD


if __name__ == "__main__":
    sys.exit(main())
