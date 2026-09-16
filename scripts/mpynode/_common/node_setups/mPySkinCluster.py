"""Setup source for mPySkinCluster nodes (self-first instance method)."""

# Also this node's CREATE command -- cmds.<compiledType>(joints..., mesh), the
# skinCluster shape. Un-named because this file is shared by every node of the
# type -- see maya_command.resolve_create_command_names.
#
# Do NOT "modernise" the signature to (self, selection=None, ...): the body reads
# kwargs.get("selection"), and a named parameter would swallow it, leaving
# _selection() to fall back to the live selection -- which createNode has already
# replaced with the new node.
#
# VANILLA: this body ships as EMBEDDED PYTHON inside a compiled .mll and must run
# on a machine with Maya but WITHOUT mpynode. The setup_helpers it used to import
# (_selection, _joints, _meshes, SetupError) are inlined below, and so is
# MPySkinCluster._wire_joints -- create_command_blockers deliberately ALLOWS that
# pure-cmds @staticmethod (it binds a compiled skinCluster correctly), so the
# command was NOT dropped: the wrappers import shipped with it and blew up at
# command-run time. The helpers are FUNCTION-LOCAL rather than module-level
# because node_setups.merge_type_default APPENDS this file to the host node's own
# methods source -- a module-level def would clobber a same-named helper the host
# already defines.
@maya_command(creates=True)
def setup(self, *args, **kwargs):
    from maya import cmds as mc

    class SetupError(Exception):
        """The current selection / scene state can't support setup for this node.
        Message is user-facing (it names what to select)."""

    def _selection(override=None, exclude=None):
        """Inputs for setup: `override` (the snapshot "Run setup" passes) wins
        over the live selection; `exclude` drops this node so it is never its
        own input."""
        sel = list(override) if override is not None else (
            mc.ls(selection=True, long=False) or [])
        return [n for n in sel if n != exclude] if exclude else sel

    def _joints(sel):
        return [n for n in sel if mc.nodeType(n) == "joint"]

    def _meshes(sel):
        out = []
        for n in sel:
            if mc.nodeType(n) == "mesh" or mc.listRelatives(
                    n, shapes=True, type="mesh", noIntermediate=True):
                out.append(n)
        return out

    def _wire_joints(sc_name, joints):
        """Connect each joint's worldMatrix into matrix[i] and seed
        bindPreMatrix[i] from worldInverseMatrix at the current pose.
        Equivalent to the standard skinCluster bind setup. Vendored verbatim
        from wrappers.mpy_skin_cluster.MPySkinCluster._wire_joints, which is a
        pure maya.cmds @staticmethod -- importing it would drag mpynode into a
        compiled bundle."""
        for i, jnt in enumerate(joints):
            mc.connectAttr(
                jnt + ".worldMatrix[0]",
                f"{sc_name}.matrix[{i}]",
                force=True,
            )
            # Seed bindPreMatrix from the joint's inverse world matrix
            # at bind time.
            inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
            mc.setAttr(f"{sc_name}.bindPreMatrix[{i}]", inv, type="matrix")

    name = self.get_name()
    sel  = _selection(override=kwargs.get("selection"), exclude=name)
    joints = _joints(sel); meshes = _meshes(sel)
    if not joints or not meshes:
        raise SetupError("select one or more influence joints AND a mesh to bind "
                         "%s" % self.NATIVE_TYPE)
    mesh = meshes[-1]
    # S4 idempotency: "Run setup" is re-runnable -- only adopt the mesh if this
    # skinCluster is not already in its history.
    if name not in (mc.listHistory(mesh) or []):
        mc.deformer(name, e=True, g=mesh)   # adopt the pre-built bare self
    # The canonical joint wiring (connectAttr force=True + bindPreMatrix).
    _wire_joints(name, joints)
    return name
