"""Setup source for mPyNurbsSurface nodes (self-first instance method)."""

# Also this node's CREATE command, the way cmds.blendShape both makes the node
# and wires it. Un-named because this file is shared by every node of the type
# -- see maya_command.resolve_create_command_names.
@maya_command(creates=True)
def setup(self, *args, **kwargs):
    from maya import cmds as mc
    name = self.get_name()
    # build() owns ``self`` -- never delete it on failure. Only roll back the
    # render transform/shape this body creates so a partial failure leaves no
    # orphan; re-raise so build()/the command records built-but-unwired.
    created = []
    conn    = None  # break any wired connection before delete so the rollback
                 # doesn't cascade-delete the upstream ``self``.
    try:
        xform = mc.createNode("transform", name=name + "Render"); created.append(xform)
        shape = mc.createNode("nurbsSurface", name=name + "RenderShape", parent=xform)
        src, dst = name + ".outSurface", shape + ".create"
        mc.connectAttr(src, dst, force=True); conn = (src, dst)
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
