"""Setup source for mPyIkSolver nodes (self-first instance method)."""

# Also this node's CREATE command, the way cmds.blendShape both makes the node
# and wires it. Un-named because this file is shared by every node of the type
# -- see maya_command.resolve_create_command_names.
#
# VANILLA: this body ships as EMBEDDED PYTHON inside a compiled .mll and must run
# on a machine with Maya but WITHOUT mpynode, so the setup_helpers it used to
# import (_selection, _joints, SetupError) are inlined below. They are
# FUNCTION-LOCAL rather than module-level because node_setups.merge_type_default
# APPENDS this file to the host node's own methods source -- a module-level def
# would clobber a same-named helper the host already defines.
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

    name = self.get_name()
    joints = _joints(_selection(override=kwargs.get("selection"), exclude=name))
    if len(joints) < 2:
        raise SetupError("select the START joint then the END joint of the chain "
                         "to build an IK handle for %s" % self.NATIVE_TYPE)
    # GOTCHA: ikHandle solver= wants an EXISTING solver NODE NAME -- ``self`` is
    # that already-created solver. Build the handle against the selected chain.
    mc.ikHandle(startJoint=joints[0], endEffector=joints[-1], solver=name)
    return name
