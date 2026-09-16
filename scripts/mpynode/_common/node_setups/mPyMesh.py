"""Setup source for mPyMesh nodes (self-first instance method)."""

# Also this node's CREATE command, the way cmds.blendShape both makes the node
# and wires it. Un-named because this file is shared by every node of the type
# -- see maya_command.resolve_create_command_names.
@maya_command(creates=True)
def setup(self, *args, **kwargs):
    from maya import cmds as mc
    name = self.get_name()
    # build() owns ``self`` -- never delete it on failure. Only roll back the
    # render transform/shape this body creates so a partial failure leaves no
    # *Render / *RenderShape orphan (self is left built-but-unwired); re-raise.
    created = []
    conn    = None  # (src, dst) we wired; break it before delete so the rollback
                 # doesn't cascade-delete the upstream ``self``.
    try:
        xform = mc.createNode("transform", name=name + "Render"); created.append(xform)
        shape = mc.createNode("mesh", name=name + "RenderShape", parent=xform)
        src, dst = name + ".outMesh", shape + ".inMesh"
        mc.connectAttr(src, dst, force=True); conn = (src, dst)
        mc.sets(shape, edit=True, forceElement="initialShadingGroup")
        return name
    except Exception:
        if conn:
            try:
                mc.disconnectAttr(conn[0], conn[1])
            except Exception:
                pass
        if created:
            mc.delete([n for n in created if mc.objExists(n)])
        raise
