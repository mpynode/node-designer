"""Setup source for mPyFile nodes (self-first instance method)."""

# VANILLA: this body ships as EMBEDDED PYTHON inside a compiled .mll and must run
# on a machine with Maya but WITHOUT mpynode, so the setup_helpers ``_selection``
# and the pure-cmds ``_api2.mpy_file.ensure_in_texture_list`` it used to import are
# inlined below. They are FUNCTION-LOCAL rather than module-level because
# node_setups.merge_type_default APPENDS this file to the host node's own methods
# source -- a module-level def would clobber a same-named helper the host already
# defines. ``warm_init_namespace`` is the one name that stays an import; see the
# call site for why that is safe.
def setup(self, *args, **kwargs):
    from maya import cmds as mc

    def _selection(override=None, exclude=None):
        """Inputs for setup: `override` (the snapshot "Run setup" passes) wins
        over the live selection; `exclude` drops this node so it is never its
        own input."""
        sel = list(override) if override is not None else (
            mc.ls(selection=True, long=False) or [])
        return [n for n in sel if n != exclude] if exclude else sel

    def _ensure_in_texture_list(n):
        """Wire ``n.message -> defaultTextureList1.textures`` so the Hypershade
        can graph the node (parity with ``shadingNode -asTexture``).

        Idempotent AND self-healing: it inspects the texture-list's source plugs
        so it is robust to the create-time race where ``shadingNode -asTexture``
        ALSO wires this connection -- duplicates are disconnected so exactly one
        remains. Vendored from _api2.mpy_file.ensure_in_texture_list, which is
        pure maya.cmds and works against a compiled node too -- importing it
        would drag mpynode into a compiled bundle."""
        try:
            if not mc.objExists(n):
                return False
            msg = n + ".message"
            if not mc.objExists("defaultTextureList1"):
                # Default node is created on demand by shadingNode; make it so
                # the connection has a destination even in a minimal scene.
                try:
                    mc.createNode("defaultTextureList",
                                  name="defaultTextureList1", shared=True)
                except Exception:
                    pass
            pairs = mc.listConnections(
                "defaultTextureList1.textures", connections=True, plugs=True,
                source=True, destination=False) or []
            mine = [pairs[i] for i in range(0, len(pairs) - 1, 2)
                    if pairs[i + 1] == msg]
            if mine:
                for extra in mine[1:]:
                    try:
                        mc.disconnectAttr(msg, extra)
                    except Exception:
                        pass
                return True
            mc.connectAttr(msg, "defaultTextureList1.textures",
                           nextAvailable=True)
            return True
        except Exception:
            return False

    name = self.get_name()
    # ``self`` is the already-created mPyFile (create() ran shadingNode -asTexture,
    # wired time1, seeded Init/Compute/Viewport + a place2dTexture). Wire outColor
    # on top of that plumbing -- do NOT re-create place2dTexture or re-seed.
    _ensure_in_texture_list(name)
    # INTERPRETED-ONLY, and deliberately left as an import rather than vendored:
    # it registers the node's Init source into mpynode's init registry, and it
    # gates on the ``_initSource`` plug -- which a compiled node does not have
    # (command_dispatch.COMPILED_UNSUPPORTED), so a vendored copy could only ever
    # return False in a bundle. Guarded so a missing mpynode skips it instead of
    # killing the whole setup; the function itself never raises.
    try:
        from mpynode._api2.mpy_file import warm_init_namespace
        warm_init_namespace(name)
    except Exception:
        pass

    # Selection snapshot (build()/Run setup pass it via kwargs["selection"]);
    # exclude self so it is never treated as its own shader input.
    def _is_surface_shader(n):
        cls_tags = mc.getClassification(mc.nodeType(n)) or []
        return any("shader/surface" in t for t in cls_tags)
    sel = [s for s in _selection(override=kwargs.get("selection"),
                                 exclude=name) if _is_surface_shader(s)]

    if sel:
        shader = sel[-1]
        dest = next((a for a in ("color", "baseColor")
                     if mc.attributeQuery(a, node=shader, exists=True)), None)
        if dest:
            mc.connectAttr(name + ".outColor", "%s.%s" % (shader, dest), force=True)
    return name
