"""Setup source for mPyBlendShape nodes (self-first instance method)."""

# PARTIALLY VANILLA -- read this before adding @maya_command(creates=True) here.
# The setup_helpers import (_selection, _meshes, SetupError) is inlined below, so
# the only mpynode name left is the MPyBlendShape wrapper. That one CANNOT be
# vendored: add_target() calls add_input_attr, and rebuild() calls add_input_attr
# plus get_compute_expression -- all three are in
# command_dispatch.COMPILED_UNSUPPORTED, because a compiled node has no
# _inputAttrs / _computeSource plug to back them, so a hand-copied version could
# only fail silently. This is why this file, alone among the eight per-type
# setups, carries NO @maya_command(creates=True): create_command_blockers rejects
# the body outright ("constructs the interpreted wrapper MPyBlendShape(...)"), so
# it never lowers into a bundle as a command and the import is never reached
# there. The second reason is broader and applies to a PLAIN @maya_command too --
# reachable_mpynode_imports fails the compile on any mpynode import a command
# can reach -- which is why the factory commands at the bottom of this file go
# through ``self`` and import nothing. The helpers are FUNCTION-LOCAL because
# node_setups.merge_type_default APPENDS this file to the host node's own methods
# source -- a module-level def would clobber a same-named helper the host already
# defines.
def setup(self, *args, **kwargs):
    from maya import cmds as mc
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

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

    def _meshes(sel):
        out = []
        for n in sel:
            if mc.nodeType(n) == "mesh" or mc.listRelatives(
                    n, shapes=True, type="mesh", noIntermediate=True):
                out.append(n)
        return out

    name = self.get_name()
    meshes = _meshes(_selection(override=kwargs.get("selection"), exclude=name))
    if len(meshes) < 2:
        raise SetupError("select one or more TARGET meshes then the BASE mesh LAST "
                         "to build %s" % self.NATIVE_TYPE)
    base = meshes[-1]
    targets = meshes[:-1]
    # S4 idempotency: "Run setup" is re-runnable -- only adopt the base mesh if
    # this blendShape is not already in its history.
    if name not in (mc.listHistory(base) or []):
        mc.deformer(name, e=True, g=base)   # adopt the pre-built bare self
    # Reuse the canonical target wiring: add_target connects outMesh ->
    # targetGeometry[i] AND aliases weight[i] to the target's name, so the
    # channel box reads like a stock blendShape.
    bs = MPyBlendShape(name)
    for t in targets:
        bs.add_target(t)
    # Bake the delta tables. Wiring alone is not enough any more -- the compute
    # reads baked deltas, not the live target meshes, so a wired-but-unbaked
    # blendShape would deform nothing.
    bs.rebuild()
    return name


# ---------------------------------------------------------------------------
# Factory commands. Seeded onto every mPyBlendShape by merge_type_default, so a
# node arrives able to take targets without the user writing anything -- and
# because they are ordinary source in the Methods tab, they can be edited or
# deleted per node.
#
# These ARE decorated where the setup above is not, and the difference is the
# reason they are written the way they are: a @maya_command body ships as
# EMBEDDED PYTHON inside a compiled .mll, and
# command_dispatch.reachable_mpynode_imports fails the compile on any mpynode
# import a command can reach. The setup's function-scope
# `from mpynode.wrappers... import MPyBlendShape` is invisible to that gate only
# because setup is undecorated; decorating it would break every blendShape
# template's compile.
#
# So these bodies import NOTHING from mpynode. They go through ``self``, which
# is the MPyBlendShape wrapper on every interpreted path (`build()`, the Scene
# tab, and `call_command` all bind the type wrapper), and therefore already has
# the whole target API. On a COMPILED node the same members are refused with an
# explanation rather than an AttributeError -- see
# command_dispatch.COMPILED_UNSUPPORTED, which lists them for exactly this case.
#
# The mesh filter below is a near-copy of the setup's ``_meshes`` on purpose:
# hoisting it to module level would clobber a same-named helper in the host
# node's own methods source, which is the same reason the setup keeps its
# helpers function-local.
#
# DO NOT DROP THE ``_cmd`` SUFFIXES. A def whose name also exists on the wrapper
# is emitted by ``py_export`` as a member of ``class X(MPyBlendShape)``, where it
# SHADOWS the very method its body calls -- ``load_target`` forwarding to
# ``self.load_target`` is then genuinely infinite recursion in the baked ``.py``
# (interpreted is fine, because the Methods func is never bound to the wrapper).
# The command NAME is pinned separately, so ``cmds.load_target`` is unaffected.


@maya_command
def add_targets(self, meshes: list[str] = None):
    """Add meshes as blend-shape targets, each weight aliased after its mesh.

    Defaults to the current selection, which is the usual way to call it: pick
    the shapes, then run. Passing ``meshes`` explicitly is for scripts.
    """
    from maya import cmds as mc

    name = self.get_name()
    sel = list(meshes) if meshes else (mc.ls(selection=True, long=False) or [])
    picked = []
    for n in sel:
        # Never let the node be its own target, whatever is selected.
        if n == name:
            continue
        if mc.nodeType(n) == "mesh" or mc.listRelatives(
                n, shapes=True, type="mesh", noIntermediate=True):
            picked.append(n)
    if not picked:
        raise ValueError(
            "select one or more MESHES to add as targets of %s" % name)

    added = [self.add_target(t) for t in picked]
    # Wiring alone deforms nothing -- the compute reads baked deltas, not the
    # live target meshes.
    self.rebuild()
    aliases = self.aliases
    return [aliases[i] if i < len(aliases) else "" for i in added]


@maya_command(name="load_target")
def load_target_cmd(self, path: str, name: str = ""):
    """Load ONE shape from a file and add it as a target.

    ``.ma`` / ``.mb`` / ``.obj`` / ``.fbx`` are imported to read their points
    and removed again; ``.npz`` / ``.json`` are read directly. Either way the
    shape needs no mesh in the scene and leaves no construction history on the
    node. Returns the weight index.
    """
    return self.load_target(path, name=name or None)


@maya_command(name="load_shapes")
def load_shapes_cmd(self, path: str):
    """Load a whole shape cluster from a ``.npz`` / ``.json``.

    One target per record, in file order, each aliased to its stored name.
    Returns a summary of what was loaded, including how many names decoded as
    in-betweens or combos.
    """
    return self.load_shapes(path)
