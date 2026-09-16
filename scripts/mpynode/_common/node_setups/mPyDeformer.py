"""Setup source for mPyDeformer nodes (self-first instance method)."""

# Also this node's CREATE command, the way cmds.blendShape both makes the node
# and wires it. Un-named because this file is shared by every node of the type
# -- see maya_command.resolve_create_command_names.
#
# VANILLA: this body ships as EMBEDDED PYTHON inside a compiled .mll and must run
# on a machine with Maya but WITHOUT mpynode, so the setup_helpers it used to
# import (_selection, _deformables, SetupError) are inlined below. They are
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

    def _deformables(sel):
        """The entries carrying deformable geometry (directly or as a shape)."""
        kinds = ("mesh", "nurbsSurface", "nurbsCurve", "lattice")
        out   = []
        for n in sel:
            if mc.nodeType(n) in kinds:
                out.append(n)
                continue
            for st in kinds:
                if mc.listRelatives(n, shapes=True, type=st, noIntermediate=True):
                    out.append(n)
                    break
        return out

    name = self.get_name()
    geo = _deformables(_selection(override=kwargs.get("selection"),
                                  exclude=name))
    if not geo:
        raise SetupError("select a mesh (or other deformable geometry) to apply "
                         "%s" % self.NATIVE_TYPE)
    # S4 idempotency: "Run setup" is re-runnable -- only adopt geometry that does
    # not already have this deformer in its history.
    todo = [g for g in geo if name not in (mc.listHistory(g) or [])]
    if todo:
        mc.deformer(name, e=True, g=todo)   # adopt the pre-built bare self
    return name
