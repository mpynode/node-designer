"""Companion-command C++ codegen -- emit MPxCommands from ``@maya_command`` defs.

The Methods tab (see ``mpynode/_common/methods_registry``) lets a node declare
companion commands. ``maya_command.detect_commands`` finds the flagged defs
statically; this module turns the RECOGNISED ones into real ``MPxCommand`` C++.

v1 is DETERMINISTIC and bounded: it recognises exactly the two mesh-region
commands that are the feature's keystone test --

  * ``createMeshRegion`` -- create the locator node + auto-connect the selected
    mesh's ``worldMesh[0]`` into the node's mesh plug; optional ``-indices``
    writes the face region at create time.
  * ``setMeshRegion`` -- ``-indices`` (multi-use) writes the persistent face-id
    region attr on a given/selected node; undoable (restores the prior region).

Anything else is REPORTED as ``unsupported`` (the AI-porter fallback for
arbitrary commands is a documented follow-up -- never silently dropped).

Emission contract (rides the bundler, mirrors how nodes are merged):
  * command CLASSES go in the node's scaffold HEAD region -> the bundler wraps
    the whole head in ``namespace nd_<node>`` so two nodes' same-named helper
    classes don't collide;
  * ``registerCommand`` / ``deregisterCommand`` lines go INSIDE the node's
    ``initializePlugin`` / ``uninitializePlugin`` -> the bundler's ``_make_hook``
    carries them (with ``using namespace nd_<node>;``) into the merged plugin;
  * ``registerCommand`` has a different signature than
    ``registerNode``/``registerTransform`` so it never matches the bundler's
    main-class detection regex.

Pure (no maya, no Qt) -- it only assembles strings, so it is unit-testable
without a running Maya. The C++ it emits is compiled + parity-checked in the
real-Maya integration phase.
"""
from __future__ import annotations

import re
from typing import List

__all__ = [
    "cmd_class_name",
    "classify_command",
    "emit_commands",
    "COMMAND_INCLUDES",
]

# Headers the emitted command classes need, merged into the node's include set.
# Kept SELF-CONTAINED so a command node WITHOUT a mesh input (which otherwise
# pulls STL/mesh headers in via the locator's include sets) still compiles: the
# templates use std::vector<int>, size_t and MFn::k* directly. STL headers are
# bare names; codegen de-dups them against the locator's common set.
COMMAND_INCLUDES = [
    "vector",
    "cstddef",
    "maya/MPxCommand.h",
    "maya/MSyntax.h",
    "maya/MArgDatabase.h",
    "maya/MArgList.h",
    "maya/MSelectionList.h",
    "maya/MGlobal.h",
    "maya/MDagModifier.h",
    "maya/MDGModifier.h",
    "maya/MDagPath.h",
    "maya/MFn.h",
    "maya/MFnDagNode.h",
    "maya/MFnDependencyNode.h",
    "maya/MFnIntArrayData.h",
    "maya/MIntArray.h",
    "maya/MPlug.h",
    "maya/MObject.h",
]

# The two deterministic templates are keyed by command NAME. Recognising by name
# keeps v1 bounded; arbitrary commands are reported, not guessed at.
_CREATE_NAME = "createMeshRegion"
_SET_NAME = "setMeshRegion"


def cmd_class_name(command_name: str) -> str:
    """``"createMeshRegion"`` -> ``"CreateMeshRegionCmd"`` (always a valid C++
    identifier; non-identifier chars become ``_``)."""
    parts = re.split(r"[^0-9A-Za-z]+", command_name or "")
    pascal = "".join(p[:1].upper() + p[1:] for p in parts if p)
    if not pascal or not pascal[0].isalpha():
        pascal = "Cmd" + pascal
    return pascal + "Cmd"


def classify_command(cmd: dict):
    """Recognise a deterministic template by command name. Returns
    ``"create_mesh_region"`` / ``"set_mesh_region"`` / ``None``."""
    name = cmd.get("name")
    if name == _CREATE_NAME:
        return "create_mesh_region"
    if name == _SET_NAME:
        return "set_mesh_region"
    return None


# ---- Shared free helpers: read / write the persistent region face-id list on
# the int-array region attr. Emitted once per plugin. ------------------------

def _region_helpers(ctx: dict) -> str:
    region_attr = ctx["region_attr"]
    cls = ctx["node_cls"]
    return "\n".join([
        "// ---- companion-command region helpers (mesh-region commands) ----",
        "static std::vector<int> _readRegionFaces(const MObject& node) {",
        "    std::vector<int> out;",
        "    MStatus _s; MFnDependencyNode fn(node);",
        '    MPlug p = fn.findPlug("%s", false, &_s);' % region_attr,
        "    if (!_s || p.isNull()) return out;",
        "    MObject data = p.asMObject();",
        "    if (data.isNull() || !data.hasFn(MFn::kIntArrayData)) return out;",
        "    MFnIntArrayData iad(data);",
        "    MIntArray arr = iad.array();",
        "    for (unsigned i = 0; i < arr.length(); ++i) out.push_back(arr[i]);",
        "    return out;",
        "}",
        "static void _writeRegionFaces(const MObject& node,",
        "                              const std::vector<int>& ids) {",
        "    MStatus _s; MFnDependencyNode fn(node);",
        '    MPlug p = fn.findPlug("%s", false, &_s);' % region_attr,
        "    if (!_s || p.isNull()) return;",
        "    MIntArray arr;",
        "    for (size_t i = 0; i < ids.size(); ++i) arr.append(ids[i]);",
        "    MFnIntArrayData iad;",
        "    MObject data = iad.create(arr);",
        "    p.setValue(data);",
        "}",
        "// resolve a node of OUR type from a selection list. A selected",
        "// transform may parent MULTIPLE shapes, so search ALL its children for",
        "// one of our type (not just the first via extendToShape).",
        "static MObject _resolveOurNode(const MSelectionList& sel) {",
        "    for (unsigned i = 0; i < sel.length(); ++i) {",
        "        MDagPath dp;",
        "        if (sel.getDagPath(i, dp) == MS::kSuccess) {",
        "            MObject dn = dp.node();",
        "            if (dn.hasFn(MFn::kTransform)) {",
        "                MFnDagNode xform(dn);",
        "                for (unsigned c = 0; c < xform.childCount(); ++c) {",
        "                    MObject ch = xform.child(c);",
        "                    if (MFnDependencyNode(ch).typeId() == %s::id)" % cls,
        "                        return ch;",
        "                }",
        "            } else if (MFnDependencyNode(dn).typeId() == %s::id) {" % cls,
        "                return dn;",
        "            }",
        "        }",
        "        MObject o;",
        "        if (sel.getDependNode(i, o) == MS::kSuccess &&",
        "            MFnDependencyNode(o).typeId() == %s::id) return o;" % cls,
        "    }",
        "    return MObject::kNullObj;",
        "}",
        "",
    ])


def _collect_indices_block(indent: str) -> List[str]:
    """C++ that reads the multi-use ``-indices`` flag into ``std::vector<int>"
    " ids``."""
    return [
        indent + "std::vector<int> ids;",
        indent + 'unsigned _ni = db.numberOfFlagUses("-i");',
        indent + "for (unsigned k = 0; k < _ni; ++k) {",
        indent + "    MArgList al;",
        indent + '    if (db.getFlagArgumentList("-i", k, al) == MS::kSuccess)',
        indent + "        ids.push_back(al.asInt(0));",
        indent + "}",
    ]


def _set_mesh_region_class(ctx: dict) -> str:
    name = _SET_NAME
    cn = cmd_class_name(name)
    type_name = ctx["node_type_name"]
    L = [
        "class %s : public MPxCommand {" % cn,
        "public:",
        "    static void* creator() { return new %s(); }" % cn,
        "    static MSyntax newSyntax() {",
        "        MSyntax syn;",
        '        syn.addFlag("-i", "-indices", MSyntax::kLong);',
        '        syn.makeFlagMultiUse("-i");',
        "        syn.setObjectType(MSyntax::kSelectionList, 0, 1);",
        "        syn.useSelectionAsDefault(true);",
        "        return syn;",
        "    }",
        "    bool isUndoable() const override { return true; }",
        "    MStatus doIt(const MArgList& args) override {",
        "        MStatus st;",
        "        MArgDatabase db(syntax(), args, &st);",
        "        if (!st) return st;",
        "        MSelectionList sel; db.getObjects(sel);",
        "        _node = _resolveOurNode(sel);",
        "        if (_node.isNull()) {",
        '            displayError("%s: no %s node selected or named");'
        % (name, type_name),
        "            return MS::kFailure;",
        "        }",
    ]
    L += _collect_indices_block("        ")
    L += [
        "        _new = ids;",
        "        _old = _readRegionFaces(_node);  // snapshot for undo",
        "        return redoIt();",
        "    }",
        "    MStatus redoIt() override {",
        "        _writeRegionFaces(_node, _new);",
        "        return MS::kSuccess;",
        "    }",
        "    MStatus undoIt() override {",
        "        _writeRegionFaces(_node, _old);",
        "        return MS::kSuccess;",
        "    }",
        "private:",
        "    MObject _node;",
        "    std::vector<int> _new, _old;",
        "};",
        "",
    ]
    return "\n".join(L)


def _create_mesh_region_class(ctx: dict) -> str:
    name = _CREATE_NAME
    cn = cmd_class_name(name)
    type_name = ctx["node_type_name"]
    node_cls = ctx["node_cls"]
    mesh_plug = ctx["mesh_plug"]
    L = [
        "class %s : public MPxCommand {" % cn,
        "public:",
        "    static void* creator() { return new %s(); }" % cn,
        "    static MSyntax newSyntax() {",
        "        MSyntax syn;",
        '        syn.addFlag("-i", "-indices", MSyntax::kLong);',
        '        syn.makeFlagMultiUse("-i");',
        "        return syn;",
        "    }",
        "    bool isUndoable() const override { return true; }",
        "    MStatus doIt(const MArgList& args) override {",
        "        MStatus st;",
        "        MArgDatabase db(syntax(), args, &st);",
        "        if (!st) return st;",
    ]
    L += _collect_indices_block("        ")
    L += [
        "        // first selected mesh shape (if any) -> auto-connect target.",
        "        // Carry the selected shape's INSTANCE number so an instanced mesh",
        "        // selected on instance N connects worldMesh[N] (not always [0]).",
        "        MObject meshShape = MObject::kNullObj;",
        "        int _meshInst = 0;",
        "        MSelectionList sel; MGlobal::getActiveSelectionList(sel);",
        "        for (unsigned i = 0; i < sel.length(); ++i) {",
        "            MDagPath dp;",
        "            if (sel.getDagPath(i, dp) != MS::kSuccess) continue;",
        "            MDagPath shp(dp);",
        "            if (dp.node().hasFn(MFn::kTransform)) shp.extendToShape();",
        "            if (shp.node().hasFn(MFn::kMesh)) {",
        "                meshShape = shp.node();",
        "                _meshInst = (int)shp.instanceNumber();",
        "                break;",
        "            }",
        "        }",
        "        // Author every op on ONE MDagModifier so undo/redo is atomic +",
        "        // consistent and redoIt() merely REPLAYS it. (Issuing createNode/",
        "        // connect inside redoIt() would re-queue them on every redo and",
        "        // duplicate the node -- MDG/MDagModifier accumulate operations.)",
        '        MObject created = _dagMod.createNode("%s", MObject::kNullObj, &st);'
        % type_name,
        "        if (!st) return st;",
        "        st = _dagMod.doIt();   // create the node so we can resolve + wire it",
        "        if (!st) return st;",
        "        // resolve our shape (createNode may return the shape or its xform)",
        "        _locShape = MObject::kNullObj;",
        "        if (MFnDependencyNode(created).typeId() == %s::id) {"
        % node_cls,
        "            _locShape = created;",
        "        } else if (created.hasFn(MFn::kDagNode)) {",
        "            MFnDagNode dn(created);",
        "            for (unsigned i = 0; i < dn.childCount(); ++i) {",
        "                MObject c = dn.child(i);",
        "                if (MFnDependencyNode(c).typeId() == %s::id) {"
        % node_cls,
        "                    _locShape = c; break;",
        "                }",
        "            }",
        "        }",
        "        if (_locShape.isNull()) return MS::kFailure;",
        "        MFnDependencyNode lfn(_locShape);",
        "        // queue auto-connect selected mesh.worldMesh[inst] -> locShape.%s"
        % mesh_plug,
        "        if (!meshShape.isNull()) {",
        "            MFnDependencyNode mfn(meshShape);",
        '            MPlug src = mfn.findPlug("worldMesh", false, &st);',
        "            if (st && src.isArray())",
        "                src = src.elementByLogicalIndex(_meshInst);",
        '            MPlug dst = lfn.findPlug("%s", false, &st);' % mesh_plug,
        "            if (st && !src.isNull() && !dst.isNull())",
        "                _dgMod.connect(src, dst);",
        "        }",
        "        // queue optional region ids at create time (shares -indices) as an",
        "        // UNDOABLE modifier op (not a bare setValue) so redo re-applies it.",
        "        if (!ids.empty()) {",
        '            MPlug rp = lfn.findPlug("%s", false, &st);' % ctx["region_attr"],
        "            if (st && !rp.isNull()) {",
        "                MIntArray arr;",
        "                for (size_t i = 0; i < ids.size(); ++i) arr.append(ids[i]);",
        "                MFnIntArrayData iad; MObject dataObj = iad.create(arr);",
        "                _dgMod.newPlugValue(rp, dataObj);",
        "            }",
        "        }",
        "        st = _dgMod.doIt();   // execute the queued connect + region ops",
        "        if (!st) return st;",
        "        setResult(MFnDagNode(_locShape).fullPathName());",
        "        return MS::kSuccess;",
        "    }",
        "    // redoIt() only REPLAYS the two modifiers (never re-issues createNode/",
        "    // connect); undoIt() reverses them in the opposite order.",
        "    MStatus redoIt() override {",
        "        MStatus st = _dagMod.doIt();   // recreate the node",
        "        if (!st) return st;",
        "        return _dgMod.doIt();          // reconnect + rewrite region",
        "    }",
        "    MStatus undoIt() override {",
        "        MStatus st = _dgMod.undoIt();   // disconnect + restore region first",
        "        if (!st) return st;",
        "        return _dagMod.undoIt();        // then delete the created node",
        "    }",
        "private:",
        "    MDagModifier _dagMod;  // owns createNode (issued once in doIt)",
        "    MDGModifier  _dgMod;   // owns connect + region write (issued once)",
        "    MObject _locShape;",
        "};",
        "",
    ]
    return "\n".join(L)


_TEMPLATES = {
    "create_mesh_region": _create_mesh_region_class,
    "set_mesh_region": _set_mesh_region_class,
}


def emit_commands(commands: List[dict], ctx: dict) -> dict:
    """Emit C++ for the recognised companion commands.

    ``commands`` is ``maya_command.detect_commands(...)`` output;
    ``ctx`` carries the locator codegen context: ``node_type_name``,
    ``node_cls``, ``mesh_plug``, ``region_attr``.

    Returns a dict:
      * ``classes``      -- C++ block for the scaffold head ('' if none)
      * ``register``     -- registerCommand lines (initializePlugin)
      * ``deregister``   -- deregisterCommand lines (uninitializePlugin)
      * ``includes``     -- extra headers ([] if none)
      * ``needs_region_attr`` -- True iff a mesh-region command was emitted
      * ``supported`` / ``unsupported`` -- command NAMEs, in input order
    """
    classes: List[str] = []
    register: List[str] = []
    deregister: List[str] = []
    supported: List[str] = []
    unsupported: List[str] = []
    needs_region = False

    # Emit the shared region helpers once, BEFORE the command classes that use
    # them, when any mesh-region command is present.
    region_cmds = [c for c in commands if classify_command(c) is not None]
    if region_cmds:
        needs_region = True
        classes.append(_region_helpers(ctx))

    for c in commands:
        kind = classify_command(c)
        name = c.get("name")
        if kind is None:
            unsupported.append(name)
            continue
        cn = cmd_class_name(name)
        classes.append(_TEMPLATES[kind](ctx))
        register.append(
            'MStatus _cs_%s = plugin.registerCommand("%s", %s::creator, '
            "%s::newSyntax); if (!_cs_%s) return _cs_%s;"
            % (cn, name, cn, cn, cn, cn))
        deregister.append('plugin.deregisterCommand("%s");' % name)
        supported.append(name)

    return {
        "classes": "\n".join(classes),
        "register": register,
        "deregister": deregister,
        "includes": list(COMMAND_INCLUDES) if supported else [],
        "needs_region_attr": needs_region,
        "supported": supported,
        "unsupported": unsupported,
    }
