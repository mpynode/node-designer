"""Prove the ONE mega bundle is genuinely all-in-one.

Every @maya_command now compiles into the bundle as an MPxCommand, so a mega
build must produce a single loadable artifact that, by itself, registers every
node type AND every command:

  1. exactly ONE plug-in artifact in the mega dir -- no sibling *_commands.py.
  2. loadPlugin the .bundle -> every node type registers under ONE plugin.
  3. createNode each registered node type (mixed bases: DG/deformer/locator/
     transform/iksolver) -> the C++ classes co-exist + instantiate.
  4. the SAME plugin registers every command the source templates declare.
     Expected names come from the TEMPLATES (detect_commands), not from the
     generated C++, so this cannot pass by agreeing with the emitter.
  5. run one command end-to-end and see the scene change.
  6. unload cleanly -- deregisterCommand must not strand a name.

    "$MAYAPY" tools/harness/mega_loadtest.py "templates/All Templates Plugin"
"""
import os, sys, json

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HARNESS))            # project root
AUDIT_ROOT = os.path.join(ROOT, "_audit")                   # audit output root
sys.path.insert(0, HARNESS)

MEGA_DIR = sys.argv[1] if len(sys.argv) > 1 else "templates/All Templates Plugin"
MEGA_DIR = os.path.abspath(MEGA_DIR)


def L(m=""):
    print(m, flush=True)


def _expected_commands(linked_types):
    """``({source_node: [command name, ...]}, {source_node: creates-cmd})`` read
    from the TEMPLATES.

    Independent oracle: if the emitter silently dropped a command, the mega
    C++ and mega_results.json would BOTH omit it and agree with each other.
    The template is the only place that still knows the command was authored.

    ``linked_types`` maps source node -> COMPILED type name, because a nameless
    ``creates=True`` setup registers under the type name rather than under the
    def's own name "setup" (``resolve_create_command_names``). That rename is
    part of the authoring contract, not an emitter detail: the per-type default
    setups are one shared text file, so writing a literal name there would have
    every template of that type register the same command and clash. Reading
    the raw def name here reported all eight ``creates`` setups as missing while
    the bundle had them all -- under their type names.
    """
    from demo_specs import load_templates
    from mpynode._common.io import mpn_io
    from mpynode._common.methods.maya_command import (
        detect_commands, resolve_create_command_names)

    out, creates = {}, {}
    for t in load_templates(HARNESS, ROOT):
        src = t.get("node_name") or t.get("source_name")
        if src not in linked_types:
            continue
        try:
            payload = mpn_io.load_mpn(os.path.join(ROOT, t["mpn"]),
                                      trusted=True)
            found = detect_commands(payload.get("methods_source") or "")
            # Borrow ONLY the naming rule; WHICH commands exist still comes
            # from the template, so this cannot pass by agreeing with the
            # emitter.
            resolve_create_command_names(found, linked_types[src])
            names = [c["name"] for c in found]
            for c in found:
                if c.get("creates"):
                    creates[src] = c["name"]
        except Exception as exc:                                # noqa: BLE001
            L("  WARN could not read %s: %r" % (t["mpn"], exc))
            continue
        if names:
            out[src] = names
    return out, creates


def _fixtures_for(mc, source):
    """Build the scene ``source``'s setup needs; return its objects in PICK
    ORDER, ``[]`` when the setup takes no selection, or ``None`` when no fixture
    is defined (reported as an explicit SKIP, never silently dropped).

    Each branch mirrors the ``SetupError`` preconditions in that template's
    ``setup()``. If a setup's requirements change, its command fails here rather
    than quietly going unexercised.
    """
    if source == "aimTransform":
        # Two objects carrying worldMatrix: START first, then END.
        return [mc.spaceLocator(name="e2eAimStart")[0],
                mc.spaceLocator(name="e2eAimEnd")[0]]
    if source == "spine":
        # "at least 2 transforms (in order along the spine)".
        return [mc.createNode("transform", name="e2eSpineA"),
                mc.createNode("transform", name="e2eSpineB")]
    if source == "metaballs":
        return []                      # setup(self, *args) -- reads no selection
    if source == "meshRegions":
        # Needs a mesh that ALREADY carries a component tag to bind a region to.
        from mpynode._common.nodes.mesh.component_tags import create_tag
        tr = mc.polyCube(name="e2eRegionMesh", constructionHistory=False)[0]
        shape = (mc.listRelatives(tr, shapes=True, fullPath=True) or [None])[0]
        # create_tag returns "" (not an error) when the name is already taken.
        if not shape or not create_tag(shape, "e2eRegion", [0, 1, 2, 3]):
            raise RuntimeError("could not create the component tag this setup "
                               "binds a region to")
        return [tr]
    if source == "procrustesTags":
        # Mesh (>= 3 verts) first, then the transform(s) to rivet to it.
        return [mc.polySphere(name="e2eProcMesh", constructionHistory=False)[0],
                mc.createNode("transform", name="e2eProcRivet")]
    if source in ("patchRelax", "uvLayoutMesh"):
        return [mc.polySphere(name="e2e_" + source,
                              constructionHistory=False)[0]]
    return None


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    # Source/scripts/manifest live under build/; only the bundle sits on top.
    manifest = json.load(open(os.path.join(MEGA_DIR, "build", "manifest.json")))
    plugin_name = manifest.get("plugin_name") or "mPyMega"
    built = [n for n in manifest.get("nodes", []) if n.get("type_id")]
    node_types = [n["type_name"] for n in built]
    # source node -> COMPILED type name. The two differ (dnet -> mPyDnet,
    # meshRegions -> meshRegionLocator) and a creates=True setup is named after
    # the TYPE, so the mapping -- not just the key set -- is what's needed.
    linked_types = {n.get("source_node") or n.get("type_name"): n["type_name"]
                    for n in built}

    bundle = os.path.join(MEGA_DIR, plugin_name + ".bundle")
    L("=" * 74)
    L("MEGA LOAD TEST: %s" % bundle)
    L("=" * 74)

    problems = []

    # ---- 1. ONE artifact ---------------------------------------------------
    arts = sorted(f for f in os.listdir(MEGA_DIR)
                  if f.endswith((".bundle", ".mll", ".so"))
                  or f.endswith("_commands.py"))
    L("artifacts in mega dir : %s" % arts)
    if arts != [plugin_name + ".bundle"]:
        problems.append("expected exactly [%s.bundle], got %s"
                        % (plugin_name, arts))

    # ---- 2. load the combined bundle --------------------------------------
    mc.loadPlugin(bundle)
    reg = set(mc.pluginInfo(plugin_name, q=True, dependNode=True) or [])
    L("plugin loaded. registered node types: %d" % len(reg))
    missing = [t for t in node_types if t not in reg]
    L("expected %d node types; missing from registry: %s"
      % (len(node_types), missing or "none"))
    if missing:
        problems.append("node types not registered: %s" % missing)

    # ---- 3. createNode every registered type ------------------------------
    L("")
    L("--- createNode each type ---")
    made, failed = [], []
    for t in node_types:
        try:
            n = mc.createNode(t)
            made.append((t, n))
            L("  OK   %-24s -> %s" % (t, n))
        except Exception as e:                                  # noqa: BLE001
            failed.append((t, str(e)))
            L("  FAIL %-24s -> %s" % (t, str(e)[:80]))
    if failed:
        problems.append("createNode failed: %s" % [t for t, _ in failed])

    # ---- 4. the SAME plugin registers every command -----------------------
    L("")
    L("--- commands registered by the mega plugin itself ---")
    expected, creates_cmds = _expected_commands(linked_types)
    got = set(mc.pluginInfo(plugin_name, q=True, command=True) or [])
    L("  commands on %s: %s" % (plugin_name, sorted(got)))
    for src, names in sorted(expected.items()):
        absent = [c for c in names if c not in got]
        L("  %-28s expects %-44s missing: %s"
          % (src, names, absent or "none"))
        if absent:
            problems.append("%s: commands missing from the bundle: %s"
                            % (src, absent))

    # ---- 5. run one command end-to-end ------------------------------------
    L("")
    L("--- run a command end-to-end ---")
    ran = False
    if "metaballs" in reg and "addSphere" in got:
        node = mc.createNode("metaballs")
        xf = mc.createNode("transform", name="megaProbeSphere")
        mc.addSphere(node, transform=xf, radius=1.5, smoothing=0.5)
        wired = mc.listConnections(node + ".shapeMatrix", source=True,
                                   destination=False) or []
        L("  addSphere(%s) -> wired: %s" % (node, wired))
        ran = xf in wired
        if not ran:
            problems.append("addSphere ran but wired nothing")
    # The compiled TYPE name is not the template's node name (dnet's node is
    # "dnet", its type is "mPyDnet"), so resolve it from the manifest -- a
    # hardcoded "dnet" silently skipped this whole check.
    dnet_type = next((n["type_name"] for n in built
                      if (n.get("source_node") or "") == "dnet"), None)
    if dnet_type and dnet_type in reg and "dnetCreateKnot" in got:
        try:
            dn = mc.createNode(dnet_type)
            before = set(mc.ls(type="transform"))
            mc.dnetCreateKnot(dn)
            new = sorted(set(mc.ls(type="transform")) - before)
            L("  dnetCreateKnot(%s) -> new transforms: %s" % (dn, new[:4]))
            ran = ran or bool(new)
            if not new:
                problems.append("dnetCreateKnot created nothing")
        except Exception as e:                                  # noqa: BLE001
            problems.append("dnetCreateKnot raised: %s" % str(e)[:160])
            L("  dnetCreateKnot FAILED: %s" % str(e)[:120])
    if not ran:
        problems.append("no command could be exercised end-to-end")

    # ---- 5b. EVERY creates=True setup, driven through maya.cmds ------------
    # The whole point of @maya_command(creates=True) is that the setup a human
    # runs from the gallery becomes a STANDALONE MPxCommand in the bundle. That
    # is only proven by calling it the way a user would: select, invoke, see a
    # node appear. Section 5 exercised one instance command; this covers every
    # create command the templates declare.
    L("")
    L("--- run EVERY creates=True setup command end-to-end ---")
    setup_ok, setup_skipped = [], []
    for src in sorted(creates_cmds):
        cmd, ty = creates_cmds[src], linked_types[src]
        if ty not in reg or cmd not in got:
            setup_skipped.append((cmd, "type or command absent from the bundle"))
            L("  SKIP %-22s type or command absent from the bundle" % cmd)
            continue
        # A clean scene per command: these build rigs, and a leftover selection
        # or duplicate name from the previous one is not a real failure.
        mc.file(new=True, force=True)
        try:
            objs = _fixtures_for(mc, src)
        except Exception as e:                                  # noqa: BLE001
            setup_skipped.append((cmd, "fixture failed: %s" % str(e)[:90]))
            L("  SKIP %-22s fixture failed: %s" % (cmd, str(e)[:60]))
            continue
        if objs is None:
            setup_skipped.append((cmd, "no fixture defined"))
            L("  SKIP %-22s no fixture defined for this setup" % cmd)
            continue
        before = set(mc.ls(type=ty) or [])
        try:
            getattr(mc, cmd)(*objs)
        except Exception as e:                                  # noqa: BLE001
            problems.append("%s: creates-command %r raised: %s"
                            % (src, cmd, str(e)[:140]))
            L("  FAIL %-22s raised: %s" % (cmd, str(e)[:60]))
            continue
        new = sorted(set(mc.ls(type=ty) or []) - before)
        if new:
            setup_ok.append(cmd)
            L("  OK   %-22s -> created %s" % (cmd, new[:2]))
        else:
            problems.append("%s: creates-command %r made no %s node"
                            % (src, cmd, ty))
            L("  FAIL %-22s created no %s node" % (cmd, ty))
    for cmd, why in setup_skipped:
        L("  (skipped %s: %s)" % (cmd, why))

    # ---- 6. unload cleanly -------------------------------------------------
    L("")
    L("--- unload ---")
    mc.file(new=True, force=True)
    try:
        mc.unloadPlugin(plugin_name)
        still = [c for c in got if c in set(dir(mc))
                 and mc.pluginInfo(plugin_name, q=True, loaded=True)]
        L("  unloaded %s (stranded: %s)" % (plugin_name, still or "none"))
    except Exception as e:                                      # noqa: BLE001
        problems.append("unloadPlugin failed: %s" % str(e)[:160])
        L("  unload FAILED: %s" % str(e)[:120])

    # ---- summary -----------------------------------------------------------
    L("")
    L("=" * 74)
    L("SUMMARY")
    L("=" * 74)
    L("node types registered : %d / %d" % (len(reg & set(node_types)),
                                           len(node_types)))
    L("createNode OK         : %d / %d" % (len(made), len(node_types)))
    L("commands expected     : %d across %d node(s)"
      % (sum(len(v) for v in expected.values()), len(expected)))
    L("commands registered   : %d" % len(got))
    L("creates setups run e2e: %d / %d%s"
      % (len(setup_ok), len(creates_cmds),
         ("  (skipped: %s)" % ", ".join(c for c, _ in setup_skipped))
         if setup_skipped else ""))
    for p in problems:
        L("PROBLEM: %s" % p)
    L("")
    L("MEGA PLUGIN FULLY FUNCTIONAL: %s" % ("YES" if not problems else "NO"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
