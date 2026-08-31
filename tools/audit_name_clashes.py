"""Audit every template for the name clashes that break a merged plugin.

Maya has TWO global, flat string namespaces that a compile writes into, and a
mega build writes every template into BOTH at once:

  * command names  -- ``registerCommand``. The second registration of a name
    FAILS, and in a merged bundle a failing register hook aborts
    ``initializePlugin`` for the WHOLE plugin, taking every other node with it.
  * node type names -- ``registerNode``. Same global space, plus a reserved set
    (the interpreted mPy* types) that must never be shadowed.

The bundler already rejects command clashes before link, but only by reading
``registerCommand("...")` out of the generated C++ -- so it is blind to any
command that never reaches C++. This audit works from the TEMPLATES instead, so
it answers the question before a single node is compiled.

Run with mayapy (Maya is needed to know which names are already taken):
  <mayapy> tools/audit_name_clashes.py [--json]
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
os.environ.setdefault("MPYNODE_ROOT", _ROOT)

TEMPLATES = os.path.join(_ROOT, "templates")


def _iter_templates():
    for dirpath, _dirs, files in os.walk(TEMPLATES):
        if "template.mpn" in files:
            p = os.path.join(dirpath, "template.mpn")
            yield os.path.relpath(p, TEMPLATES), p


def _payload(path):
    """The canonical loader, NOT a hand-rolled json.load of the envelope.

    The raw ``data`` block stores ``stored_vars`` as a serialized STRING, which
    the spec adapter expects already decoded -- reading the envelope by hand
    made every template raise and the audit then reported "no clashes", a false
    pass on zero data.
    """
    from mpynode._common.io import mpn_io

    return mpn_io.load_mpn(path, trusted=True)


def collect():
    """[{template, type_name, source_node, commands: [...]}, ...] for every
    template, derived through the SAME code path the compiler uses so the audit
    cannot disagree with the build."""
    from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload
    from mpynode.native.toolchain.compile_controller import _type_name_for
    from mpynode._common.methods.maya_command import (
        detect_commands, resolve_create_command_names)

    rows = []
    for rel, path in sorted(_iter_templates()):
        try:
            data = _payload(path)
        except Exception as exc:                                # noqa: BLE001
            rows.append({"template": rel, "error": repr(exc)})
            continue
        try:
            spec = spec_from_mpn_payload(data)
            type_name = _type_name_for(spec)
        except Exception as exc:                                # noqa: BLE001
            rows.append({"template": rel, "error": "spec: %r" % (exc,)})
            continue
        try:
            # Resolve against the FINAL type_name, not spec["suggested"], so a
            # name-less creates= command is audited under exactly the name the
            # build will register. spec["commands"] is re-pointed too, or
            # _lower_errors below would judge a stale name.
            # spec["methods"], NOT the raw payload: spec_from_mpn_payload
            # merge-seeds the per-type default setup, so a template that carries
            # no setup of its own still contributes that setup's create command
            # to the build. Auditing the raw payload would miss every one of
            # them and report a false "no clashes".
            cmds_found = resolve_create_command_names(
                detect_commands(spec.get("methods") or ""), type_name)
            spec["commands"] = cmds_found
        except Exception:                                       # noqa: BLE001
            cmds_found = []
        rows.append({
            "template": rel,
            "type_name": type_name,
            "source_node": data.get("node_name"),
            "native_type": data.get("native_type"),
            "commands": [c["name"] for c in cmds_found],
            "lower_errors": _lower_errors(spec, type_name),
        })
    return rows


def _lower_errors(spec, type_name):
    """Ask the REAL emitter whether every command on this spec lowers.

    Without the companion plug-in there is no fallback path: a command that
    does not lower is simply absent from the bundle. ``emit_dispatch_commands``
    is all-or-nothing, so one unlowerable command costs the node ALL of its
    commands -- which makes this a pre-compile gate, not a warning.
    """
    from mpynode.native.compiler.kernels import command_dispatch
    from mpynode.native.compiler.kernels import command_codegen

    cmds = (spec or {}).get("commands") or []
    if not cmds:
        return []
    # mPyLocator hand-writes native templates for a few commands and passes
    # them to dispatch via exclude=; mirror that so the audit does not flag a
    # command the locator emitter never routes through dispatch.
    exclude = ()
    if (spec or {}).get("mpy_type") == "mPyLocator":
        exclude = tuple(c.get("name") for c in cmds
                        if command_codegen.classify_command(c) is not None)
    try:
        return list(command_dispatch.dispatch_for_spec(
            spec, type_name, exclude=exclude)["errors"])
    except Exception as exc:                                    # noqa: BLE001
        return ["dispatch raised: %r" % (exc,)]


def audit(rows):
    """Returns (problems, info). A problem is fatal for a merged build."""
    from maya import cmds as mc
    from mpynode.native.toolchain.compile_controller import (
        RESERVED_NODE_TYPE_NAMES)

    problems = []
    info = {}

    # ---- what Maya already owns -------------------------------------------
    # Two oracles: dir(maya.cmds) covers registered commands, and MEL `exists`
    # additionally covers MEL procs, which dir() cannot see. Measured to agree
    # on every command tested, including GUI-only ones under standalone.
    import maya.mel as mel

    existing_cmds = set(dir(mc))

    def _taken(name):
        if name in existing_cmds:
            return True
        try:
            return bool(mel.eval("exists %s" % name))
        except Exception:                                       # noqa: BLE001
            return False

    try:
        existing_types = set(mc.allNodeTypes() or [])
    except Exception:                                           # noqa: BLE001
        existing_types = set()
    info["maya_commands"] = len(existing_cmds)
    info["maya_node_types"] = len(existing_types)

    # ---- command names -----------------------------------------------------
    cmd_owners = {}
    for r in rows:
        for c in r.get("commands") or []:
            cmd_owners.setdefault(c, []).append(r["template"])

    for name, owners in sorted(cmd_owners.items()):
        if len(owners) > 1:
            problems.append({
                "kind": "command-name-duplicate",
                "name": name,
                "owners": owners,
                "why": "two templates register the same command; the 2nd "
                       "registerCommand fails and aborts the whole plugin",
            })
        if _taken(name):
            problems.append({
                "kind": "command-shadows-maya",
                "name": name,
                "owners": owners,
                "why": "a Maya command of this name already exists",
            })

    # ---- node type names ---------------------------------------------------
    type_owners = {}
    for r in rows:
        tn = r.get("type_name")
        if tn:
            type_owners.setdefault(tn, []).append(r["template"])

    for name, owners in sorted(type_owners.items()):
        if len(owners) > 1:
            problems.append({
                "kind": "node-type-duplicate",
                "name": name,
                "owners": owners,
                "why": "two templates compile to the same node type name; the "
                       "2nd registerNode fails and aborts the whole plugin",
            })
        if name.lower() in RESERVED_NODE_TYPE_NAMES:
            problems.append({
                "kind": "node-type-reserved",
                "name": name,
                "owners": owners,
                "why": "shadows an interpreted mPy* type",
            })
        if name in existing_types:
            problems.append({
                "kind": "node-type-shadows-maya",
                "name": name,
                "owners": owners,
                "why": "a Maya node type of this name already exists",
            })

    # ---- command lowerability ----------------------------------------------
    for r in rows:
        for msg in r.get("lower_errors") or []:
            problems.append({
                "kind": "command-not-lowerable",
                "name": msg,
                "owners": [r["template"]],
                "why": "no companion plug-in exists any more, so this command "
                       "would be ABSENT from the bundle (and it costs the node "
                       "all of its other commands too)",
            })

    info["templates"] = len(rows)
    info["errors"] = [r for r in rows if r.get("error")]
    # A template that could not be read contributes NO names, so a run where
    # everything failed would otherwise report "no clashes" -- a false pass on
    # zero data. Unreadable templates are themselves a fatal audit result.
    for r in info["errors"]:
        problems.append({
            "kind": "template-unreadable",
            "name": r["template"],
            "owners": [r["template"]],
            "why": "could not be read, so its names were NOT audited: %s"
                   % r["error"],
        })
    info["total_commands"] = sum(len(r.get("commands") or []) for r in rows)
    info["unique_commands"] = len(cmd_owners)
    info["unique_types"] = len(type_owners)
    return problems, info


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, query=True, loaded=True):
            try:
                mc.loadPlugin(p)
            except Exception:                                   # noqa: BLE001
                pass

    rows = collect()
    problems, info = audit(rows)

    if "--json" in sys.argv:
        print(json.dumps({"rows": rows, "problems": problems, "info": info},
                         indent=2))
        return 1 if problems else 0

    print("\n=== inventory ===")
    print("templates            : %d" % info["templates"])
    print("maya commands known  : %d" % info["maya_commands"])
    print("maya node types known: %d" % info["maya_node_types"])
    print("@maya_command total  : %d  (%d unique names)"
          % (info["total_commands"], info["unique_commands"]))
    print("compiled node types  : %d unique" % info["unique_types"])

    if info["errors"]:
        print("\n=== templates that could not be read (%d) ==="
              % len(info["errors"]))
        for r in info["errors"]:
            print("  %-58s %s" % (r["template"], r["error"]))

    print("\n=== templates carrying commands ===")
    for r in rows:
        if r.get("commands"):
            print("  %-52s type=%-22s cmds=%s"
                  % (r["template"], r.get("type_name"), r["commands"]))

    print("\n=== CLASHES ===")
    if not problems:
        print("  none -- safe to merge every template into one plugin")
    else:
        for p in problems:
            print("  [%s] %r" % (p["kind"], p["name"]))
            print("      owners: %s" % ", ".join(p["owners"]))
            print("      %s" % p["why"])
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
