"""User-facing wrapper for the mPyBlendShape plug-in.

``mPyBlendShape`` is an expression-driven blendShape shaped to look like Maya's
own. Despite the name it is built on ``MPxDeformerNode`` -- deliberately, not
for want of an ``MPxBlendShape`` base. That base DOES ship, in API 1.0 (a note
here used to claim the opposite); the bridge module records the measured
reasons not to use it, the first of which is that a ``kBlendShape`` node
inherits a native ``weight[]`` and so cannot carry the aliased user-attr
``weight[]`` this wrapper builds below. So the core compute surface is the
deformer contract:

 * ``self.outputGeometry[i]`` -- writable mesh handle (``getPoints()`` ->
   ``(N, 3)`` numpy; ``setPoints()`` commits)
 * ``self.input[i].inputGeometry`` -- read-only upstream mesh
 * ``self.envelope`` -- overall envelope (inherited)

On top of that it mirrors a stock blendShape:

 * ``weight[]``          float multi, each element ALIASED to its target name,
                         so ``bs.browUp`` IS ``bs.weight[0]`` and the channel
                         box shows ``browUp``
 * ``targetGeometry[]``  the live target mesh connections (authoring)
 * baked delta tables    what the COMPUTE actually reads

Why deltas and not the target meshes
------------------------------------
Maya does the same thing, and it is what makes this node compilable.

A stock blendShape stores each target twice: as a live ``inputGeomTarget``
connection AND as sparse ``inputPointsTarget`` / ``inputComponentsTarget``
deltas. While the target mesh is connected Maya keeps the deltas in sync with
it; delete the target and the deltas keep driving the deformation. (Both halves
verified directly against Maya 2026.)

We need the same split for a harder reason: ``nd_lower`` only lowers a mesh
multi element read at a LITERAL index, and a blendShape's defining loop is over
targets at a RUNTIME index. Reading meshes would pin the node to interpreted
forever. Deltas are plain numeric arrays, so the loop lowers with no transpiler
work at all.

The delta tables are CSR (compressed sparse row) so they stay flat -- a multi of
arrays is not expressible, and the flat form is exactly the construct already
proven to lower:

    targetOffset[t] .. targetOffset[t+1]   slice of target t
    targetComponents[j]                    vertex id
    targetDeltas[3j], [3j+1], [3j+2]       xyz offset

Names never reach the compute
-----------------------------
``self.aliases`` is an authoring-time property, NOT something a compute may
read. Alias lookup is a side-channel DG query, and those return EMPTY on the
Evaluation-Manager worker thread where ``deform()`` runs -- so reading names in
a compute would be unreliable interpreted and impossible compiled. Naming
conventions are decoded HERE, in Python, into numeric tables, whenever the
target set changes.

Usage::

    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    bs = MPyBlendShape.create(mesh=base)
    bs.add_target(browUpMesh, "browUp")
    bs.add_target(mouthOpenMesh, "mouthOpen")
    bs.rebuild()                      # bake deltas + decode names
    mc.setAttr(bs.get_name() + ".browUp", 1.0)

Targets do not have to come from meshes in the scene -- ``load_target`` reads
one shape from an ``.ma`` / ``.obj`` / ``.fbx`` / ``.npz`` / ``.json``, and
``load_shapes`` reads a whole cluster from an ``.npz`` / ``.json``. Both end up
in the same baked tables as ``add_target``, so nothing downstream can tell where
a target came from.

See ``docs/node_types/mPyBlendShape.md``.
"""

from __future__ import annotations

import re

import maya.cmds as mc
from mpynode._common.interface.morph_method_interface import (
    INTERNAL_API_METHODS as _INTERNAL_API_METHODS,
)
from mpynode._common.util.selection_util import restore_selection
from mpynode.wrappers._mpy_node import MPyNode


_BS_TYPE_NAME = "mPyBlendShape"

# The per-target weight multi. Aliased element-by-element to the target names.
WEIGHT_ATTR = "weight"

# CSR delta tables -- always rebuilt, always read by the compute.
DELTA_ATTRS = (
    ("targetOffset", "int"),          # (T+1,) CSR offsets
    ("targetComponents", "int"),      # (K,)   vertex ids
    ("targetDeltas", "double"),       # (3K,)  flat xyz
)

# Corrective tables -- ALWAYS declared and written, even on a rig with no
# in-betweens or combos (every entry is then the inert -1 / 0 / empty form).
# ``morph_weights`` declares all four as implicit reads, and a declared read
# that fails to bind is a COMPILE-TIME reject, so a node missing these could
# not compile at all.
CORRECTIVE_ATTRS = (
    ("interBase", "int"),             # (T,) in-between -> main target, else -1
    ("interKnot", "double"),          # (T,) in-between position, else 0
    ("comboOffset", "int"),           # (T+1,) CSR into comboDriver
    ("comboDriver", "int"),           # driver target indices
)

# Name indirection for ``self.morphs["browUp"]`` in a Compute. shapeSlot[k] is
# the weight[] index of the k-th NAME the compute mentions, or -1 when this rig
# has no such target. The compiler bakes only k -- an ordinal over the compute
# SOURCE, identical on every rig -- so no target name reaches the generated C++
# and one bundle serves any rig. Declared unconditionally for the same reason
# as the corrective tables: morph_weight_at names it as an implicit read.
SLOT_ATTRS = (
    ("shapeSlot", "int"),             # (K,) slot -> weight[] index, else -1
)

# Every table above is stored PACKED (one typed-array plug, not a numeric
# multi), so a write is a single setAttr carrying the whole array. These two
# maps are derived from the spec tuples rather than hand-listed so a new table
# cannot be added without its element type coming along.
_TABLE_KIND = {name: kind
               for name, kind in DELTA_ATTRS + CORRECTIVE_ATTRS + SLOT_ATTRS}

# cmds.setAttr needs the Maya data-type name, and needs the values already in
# the right Python type -- an int table handed floats writes silently wrong.
_PACKED_SET_TYPE = {"double": "doubleArray", "int": "Int32Array"}
_TABLE_CAST = {"double": float, "int": int}

# Scene formats that need a plug-in before mc.file can read them. Loaded on
# demand: a rig that never loads an .obj should not pay for objExport.
_IMPORT_PLUGIN = {".obj": "objExport", ".fbx": "fbxmaya"}

# Trailing digits = an in-between percentage: browUp50 is browUp at 0.50.
_INBETWEEN_RE = re.compile(r"^(?P<base>.*?[^\d_])(?P<pct>\d{1,3})$")

# Maya alias names must be plain identifiers, unique, and must not collide with
# a real attribute (``envelope`` etc.) -- aliasAttr raises on all three.
_SANITISE_RE = re.compile(r"[^A-Za-z0-9_]")


def _sanitise(name: str) -> str:
    """A Maya-legal alias identifier derived from ``name``."""
    out = _SANITISE_RE.sub("_", str(name or "").strip())
    if not out or out[0].isdigit():
        out = "t" + out
    return out


def _orig_shape(shape: str) -> str | None:
    """The ORIG (intermediate) shape under ``shape``'s transform, if any."""
    xf = (mc.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
    for s in (mc.listRelatives(xf, shapes=True, fullPath=True) or []):
        if mc.getAttr(s + ".intermediateObject"):
            return s
    return None


class MPyBlendShape(MPyNode):
    # Authoring-time properties. NOT bound into the compute -- see the module
    # docstring on why names cannot cross the EM worker-thread boundary.
    INTERNAL_API_SLOTS = (
        ("morphs", "read", "MorphStack -- the target stack as an object"),
        ("aliases", "read", "list[str] -- target names, weight[] order"),
        ("target_count", "read", "int -- number of weight[] elements"),
        ("alias_fingerprint", "read", "str -- staleness key for the tables"),
    )

    # Blessed METHOD-kind ops (self.morph_weights / self.blend_targets / ...),
    # surfaced in the Framework and Variables tabs. SSOT = morph_method_interface.
    # The UI reads this CLASS attr (plug_tree_walker._internal_api_method_specs_for),
    # not method_registry, so a type that only registers there shows "(none)".
    INTERNAL_API_METHODS = _INTERNAL_API_METHODS

    # The wrapper-level API a user may call from the API tab (setup / demo /
    # @maya_command bodies) -- never as ``self.X`` in an expression tier.
    #
    # DELIBERATELY OMITTED, and why: ensure_slot_attrs / ensure_delta_attrs /
    # ensure_corrective_attrs are declared non-opt-in ("every mPyBlendShape gets
    # them"); rebuild_slots / rebuild_correctives are sub-steps `rebuild` runs
    # for you; compute_slot_names delegates to the compiler's own
    # nd_lower.morph_slot_names. Offering any of them invites a user to
    # hand-manage tables the node already manages.
    AUTHORING_API = (
        ("add_target", ""),
        ("add_target_from_offsets", ""),
        ("remove_target", ""),
        ("rename_target", ""),
        ("load_target", ""),
        ("load_shapes", ""),
        ("rebuild", ""),
        ("bake_deltas", ""),
        ("tables_stale", ""),
        ("parse_aliases", ""),
        ("get_weight",
         "The current value of target `target`'s weight (name or index)."),
        ("set_weight",
         "Set target `target`'s weight (name or index). Authoring-time; a "
         "Compute reads weights via self.morphs / morph_weights()."),
    )

    NATIVE_TYPE = _BS_TYPE_NAME

    # The ONE array input exempt from "array inputs are never keyable". Maya's
    # channel box descends into a multi's elements only when the ATTRIBUTE
    # itself is keyable, so without this the aliased weights are invisible there
    # no matter what the elements say -- measured against a real channel box,
    # and it is the whole reason a blendShape's targets are reachable at all.
    # Every other array input keeps the standing non-keyable rule.
    KEYABLE_ARRAY_INPUTS = (WEIGHT_ATTR,)

    # Attributes-tab allowlist (framework OFF): deformer I/O + the target
    # surface. `weight` is a user attr, so it shows without being listed here.
    from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL as _DEF_USEFUL
    USEFUL_INHERITED_PLUGS = _DEF_USEFUL | frozenset({"targetGeometry"})
    del _DEF_USEFUL

    # ------------------------------------------------------------------
    # creation
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        mesh: str | None = None,
        targets: list[str] | None = None,
        name: str = None,
        skip_selection: bool = False,
    ) -> "MPyBlendShape":
        """Create + attach an mPyBlendShape, with a stock-blendShape surface.

        Always adds the aliased ``weight[]`` multi, so a node built through this
        wrapper reads like a blendShape from the moment it exists.

        If ``mesh`` is provided, attaches via ``mc.deformer``; each entry in
        ``targets`` is then wired and aliased to its own transform name.

        Note: ``mc.blendShape`` is hardcoded to the native blendShape type, so
        the wrapper does the equivalent wiring manually.
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        ensure_loaded(cls.NATIVE_TYPE)
        if name is None:
            name = cls._default_create_name()
        if mesh is None:
            node = mc.createNode(cls.NATIVE_TYPE, name=name,
                                 skipSelect=skip_selection)
            self = cls._stamp_py_class(cls(node))
            self._ensure_weight_attr()
            return self

        # cmds.deformer has no skipSelect and is selection-neutral in practice;
        # snapshot + restore anyway so the uniform contract always holds.
        prior = mc.ls(selection=True, long=True) if skip_selection else None
        bs_name = mc.deformer(mesh, type=cls.NATIVE_TYPE, name=name)[0]
        self = cls._stamp_py_class(cls(bs_name))
        self._ensure_weight_attr()
        self._ensure_original_geometry()

        for t in (targets or []):
            self.add_target(t)

        if skip_selection:
            restore_selection(prior)
        return self

    # ------------------------------------------------------------------
    # attribute plumbing
    # ------------------------------------------------------------------
    def _has_attr(self, attr: str) -> bool:
        return bool(mc.objExists("%s.%s" % (self._name, attr)))

    def _ensure_weight_attr(self) -> None:
        if not self._has_attr(WEIGHT_ATTR):
            self.add_input_attr(WEIGHT_ATTR, "float", is_array=True)

    def _ensure_table_attrs(self, specs) -> None:
        for attr, kind in specs:
            if not self._has_attr(attr):
                # PACKED: every table here is a dense, machine-written int/double
                # array that nothing connects per element, so it is stored as ONE
                # typed-array plug. As numeric multis these cost one setAttr per
                # element -- a 167-target rig writes 655,928 of them and took 41.5
                # minutes; packed the same tables are three setAttr calls (0.017s).
                self.add_input_attr(attr, kind, is_array=True, packed=True)

    def ensure_delta_attrs(self) -> None:
        """Declare the CSR delta tables the compute reads."""
        self._ensure_table_attrs(DELTA_ATTRS)

    def ensure_corrective_attrs(self) -> None:
        """Declare the in-between / combo tables.

        Not opt-in: every mPyBlendShape gets them, because ``morph_weights``
        declares them as implicit reads and an unbound read is a compile-time
        reject. On a rig with no correctives they hold the inert -1 / 0 / empty
        form and ``resolve_weights`` returns the raw weights untouched.
        """
        self._ensure_table_attrs(CORRECTIVE_ATTRS)

    def ensure_slot_attrs(self) -> None:
        """Declare the compute's name->slot indirection table.

        Not opt-in, same reasoning as the correctives: ``morph_weight_at``
        declares ``shapeSlot`` as an implicit read, and an unbound read is a
        compile-time reject. A compute that names nothing leaves it empty, which
        ``weight_at_slot`` reads as "no slot maps anywhere".
        """
        self._ensure_table_attrs(SLOT_ATTRS)

    def _is_packed(self, attr: str, node: str = None) -> bool:
        """True when ``attr`` is a PACKED typed-array plug rather than a multi.

        Detected from the live plug, not from the spec tables, because a scene
        saved before packed storage existed still carries numeric multis. Both
        kinds therefore have to keep working through the same three helpers --
        an old rig must open, rebuild and evaluate unchanged.

        ``node`` defaults to this wrapper's node. It is explicit for the convert
        mirror, whose compiled sibling declares its own tables and can therefore
        answer differently from the node being mirrored FROM.
        """
        try:
            return not mc.attributeQuery(attr, node=node or self._name,
                                         multi=True)
        except Exception:
            return False

    def _multi_len(self, attr: str) -> int:
        """Logical length of a table.

        Multi: via ``multiIndices``, NOT ``getAttr`` on the parent -- that
        returns a list wrapping a single tuple (``[(0.0, 2.0, 3.0)]``), so
        ``len()`` on it is always 1 and every length check silently passes.
        Packed: the array IS the value, so its length is the element count.
        """
        if self._is_packed(attr):
            return len(mc.getAttr("%s.%s" % (self._name, attr)) or [])
        idx = mc.getAttr("%s.%s" % (self._name, attr), multiIndices=True) or []
        return (max(idx) + 1) if idx else 0

    def _read_multi(self, attr: str, cast=float) -> list:
        """Values of a table as a flat list.

        ``getAttr`` on a MULTI parent hands back a list wrapping ONE tuple --
        ``[(0.0, 2.0, 3.0)]`` -- so it has to be unwrapped before use. A PACKED
        typed array already reads back flat, so the same unwrap is a no-op and
        both kinds return the identical list. Callers cannot tell them apart,
        which is what keeps ``morph.py`` and the tests working untouched.
        """
        vals = mc.getAttr("%s.%s" % (self._name, attr))
        if not vals:
            return []
        if isinstance(vals[0], (tuple, list)):
            vals = vals[0]
        return [cast(v) for v in vals]

    def _write_multi(self, attr: str, values) -> None:
        """Overwrite a table with ``values``, clearing any stale tail.

        A shorter rebuild MUST remove the elements it no longer covers -- a
        leftover tail is exactly the stale-table case that reads as garbage,
        and compiled, reading past the end of a table is an out-of-bounds heap
        read.

        PACKED plugs get this for free: one ``setAttr`` REPLACES the whole
        array, so a stale tail is impossible by construction. The multi branch
        still has to delete the elements it no longer covers, one command each
        -- which is the cost packed storage exists to remove.
        """
        self._write_multi_to(self._name, attr, values)
        # A coexist convert leaves the compiled sibling DRIVING the mesh while
        # this node stays the authoring surface. A table written only here
        # therefore reaches nothing that deforms -- the compiled node keeps
        # replaying the snapshot copy_values took at convert time, which is why
        # sculpting a target (and add/remove/rename/load_shapes) never showed up
        # on it. Mirror every table write. No-op when the node is not converted.
        sib = self._compiled_sibling()
        if sib is not None and mc.attributeQuery(attr, node=sib, exists=True):
            self._write_multi_to(sib, attr, values)

    def _write_multi_to(self, node: str, attr: str, values) -> None:
        """The body of :meth:`_write_multi`, against an EXPLICIT node.

        Split out so the convert mirror runs the identical write -- packedness
        is re-tested per node, because the compiled sibling declares its own
        tables and need not agree with the node being mirrored from.
        """
        plug = "%s.%s" % (node, attr)
        if self._is_packed(attr, node):
            dt = _PACKED_SET_TYPE[_TABLE_KIND[attr]]
            seq = [_TABLE_CAST[_TABLE_KIND[attr]](v) for v in values]
            mc.setAttr(plug, seq, type=dt)
            return
        for idx in (mc.getAttr(plug, multiIndices=True) or []):
            if idx >= len(values):
                try:
                    mc.removeMultiInstance("%s[%d]" % (plug, idx), b=True)
                except Exception:
                    pass
        for i, v in enumerate(values):
            mc.setAttr("%s[%d]" % (plug, i), v)

    def _compiled_sibling(self):
        """The coexist convert's compiled C++ sibling, or ``None``.

        Resolved fresh on every write rather than cached: convert and revert are
        both undoable, so a cached name outlives the link it names.
        """
        try:
            from mpynode._base.commands import linked_compiled_node
        except Exception:
            return None
        try:
            return linked_compiled_node(self._name) or None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # aliases -- the authoring-time name surface
    # ------------------------------------------------------------------
    @property
    def morphs(self):
        """The target stack as a :class:`~mpynode._api2.morph.MorphStack`.

        The AUTHORING half of the same object a Compute reaches as
        ``self.morphs``. This one runs on the main thread, so it carries the
        target NAMES: index it by name, search it, and build correctives with the
        operator suite::

            m = bs.morphs
            m["browUp"] + m["mouthOpen"]      # sparse index-union merge
            m.find("brow*")                   # every browUp-derived target

        A view, rebuilt per access -- it holds no state and nothing to keep in
        sync with the plugs.
        """
        from mpynode._api2.morph import MorphStack
        return MorphStack.from_node(self)

    @property
    def aliases(self) -> list:
        """Target names in ``weight[]`` LOGICAL index order.

        Gaps (a removed target leaves a sparse index, exactly as Maya does) come
        back as ``""`` so position still equals logical index.
        """
        flat = mc.aliasAttr(self._name, query=True) or []
        by_index = {}
        for i in range(0, len(flat) - 1, 2):
            alias, plug = flat[i], flat[i + 1]
            m = re.match(r"^%s\[(\d+)\]$" % WEIGHT_ATTR, plug)
            if m:
                by_index[int(m.group(1))] = alias
        if not by_index:
            return []
        return [by_index.get(i, "") for i in range(max(by_index) + 1)]

    @property
    def target_count(self) -> int:
        """Logical target count = highest ``weight[]`` index + 1 (sparse-safe)."""
        idx = mc.getAttr("%s.%s" % (self._name, WEIGHT_ATTR),
                         multiIndices=True) or []
        n_w = (max(idx) + 1) if idx else 0
        return max(n_w, len(self.aliases))

    @property
    def target_names(self) -> list:
        """``aliases`` padded/truncated to ``target_count``.

        The single source of truth for "how many targets and what are they
        called". A weight element can exist without an alias (and vice versa
        mid-edit), so every table build indexes off THIS, never off one of the
        two underlying lists.
        """
        n = self.target_count
        al = self.aliases
        return [(al[i] if i < len(al) else "") for i in range(n)]

    @property
    def alias_fingerprint(self) -> str:
        """Staleness key: changes whenever the target set or its names change.

        The compute compares TABLE LENGTHS rather than this string (a compiled
        node cannot read aliases at all), but the tools and the rebuild check
        use it to tell "needs a rebuild" from "up to date".

        The COMPUTE's name keys are folded in too. ``shapeSlot`` is derived from
        them, so editing the expression to mention a different shape invalidates
        the table just as surely as renaming a target does -- and that edit
        touches no alias at all, so an alias-only fingerprint would call the
        stale table fresh and the node would drive the previous shape.
        """
        import hashlib

        payload = "|".join(self.aliases)
        slots = self.compute_slot_names()
        if slots:
            payload += "\x00slots\x00" + "|".join(slots)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    def _free_alias(self, wanted: str) -> str:
        """A sanitised alias that is unique and does not shadow a real attr."""
        base = _sanitise(wanted)
        taken = set(self.aliases)
        cand = base
        n = 1
        while cand in taken or (mc.objExists("%s.%s" % (self._name, cand))
                                and cand not in taken):
            n += 1
            cand = "%s%d" % (base, n)
        return cand

    def _next_free_index(self) -> int:
        idx = mc.getAttr("%s.%s" % (self._name, WEIGHT_ATTR),
                         multiIndices=True) or []
        return (max(idx) + 1) if idx else 0

    # ------------------------------------------------------------------
    # targets
    # ------------------------------------------------------------------
    @staticmethod
    def _shape_of(node: str) -> str:
        if mc.objectType(node, isAType="transform"):
            shapes = mc.listRelatives(node, shapes=True, noIntermediate=True)
            if not shapes:
                raise ValueError("target %r has no mesh shape under it" % node)
            return shapes[0]
        return node

    def _claim_weight_slot(self, name: str, index: int = None) -> int:
        """Reserve a ``weight[]`` element, make it keyable, alias it to ``name``.

        The channel surface a target needs, with no geometry involved -- shared
        by the mesh route (``add_target``) and the delta routes
        (``add_target_from_offsets`` / ``load_shapes``), which differ only in
        where the offsets come from.

        The element is made KEYABLE explicitly, which is what makes it
        keyframable. For the CHANNEL BOX that is necessary but NOT sufficient:
        Maya descends into a multi's elements only when the ATTRIBUTE itself is
        keyable, which is why ``KEYABLE_ARRAY_INPUTS`` exempts ``weight`` at
        creation time.

        An earlier version of this note claimed the per-element flag alone
        reproduced stock behaviour, on the evidence that
        ``listAttr(multi=True, keyable=True)`` reports the ALIAS. It does -- but
        it reports it whether or not the parent attribute is keyable, so it
        never tested what it appeared to. Measured against a real channel box,
        the weights were absent the whole time.
        """
        self._ensure_weight_attr()
        if index is None:
            index = self._next_free_index()
        wplug = "%s.%s[%d]" % (self._name, WEIGHT_ATTR, index)
        mc.setAttr(wplug, 0.0)
        mc.setAttr(wplug, keyable=True)
        mc.aliasAttr(self._free_alias(name), wplug)
        return index

    def add_target(self, mesh: str, name: str = None, index: int = None) -> int:
        """Wire ``mesh`` in as a target and alias its weight. Returns the index."""
        self._ensure_weight_attr()
        shape = self._shape_of(mesh)
        if index is None:
            index = self._next_free_index()
        if name is None:
            name = mesh.split("|")[-1].split(":")[-1]

        mc.connectAttr(shape + ".outMesh",
                       "%s.targetGeometry[%d]" % (self._name, index),
                       force=True)

        return self._claim_weight_slot(name, index)

    def rename_target(self, index: int, name: str) -> str:
        """Re-alias target ``index``. Returns the alias actually used."""
        wplug = "%s.%s[%d]" % (self._name, WEIGHT_ATTR, index)
        current = None
        flat = mc.aliasAttr(self._name, query=True) or []
        for i in range(0, len(flat) - 1, 2):
            if flat[i + 1] == "%s[%d]" % (WEIGHT_ATTR, index):
                current = flat[i]
                break
        # aliasAttr(remove=True) RAISES when there is no alias, so the guard is
        # load-bearing, not defensive noise.
        if current:
            mc.aliasAttr("%s.%s" % (self._name, current), remove=True)
        alias = self._free_alias(name)
        mc.aliasAttr(alias, wplug)
        return alias

    def remove_target(self, index: int) -> None:
        """Drop target ``index``, keeping the remaining logical indices SPARSE.

        Maya does exactly this -- it never compacts -- and compacting would
        silently re-point every alias and every table entry after the hole.
        """
        wplug = "%s.%s[%d]" % (self._name, WEIGHT_ATTR, index)
        flat = mc.aliasAttr(self._name, query=True) or []
        for i in range(0, len(flat) - 1, 2):
            if flat[i + 1] == "%s[%d]" % (WEIGHT_ATTR, index):
                mc.aliasAttr("%s.%s" % (self._name, flat[i]), remove=True)
                break
        gplug = "%s.targetGeometry[%d]" % (self._name, index)
        for src in (mc.listConnections(gplug, s=True, d=False, plugs=True) or []):
            mc.disconnectAttr(src, gplug)
        for p in (gplug, wplug):
            try:
                mc.removeMultiInstance(p, b=True)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # weights
    # ------------------------------------------------------------------
    def _weight_plug(self, target) -> str:
        """``target`` may be a logical index OR an alias name."""
        if isinstance(target, str):
            return "%s.%s" % (self._name, target)
        return "%s.%s[%d]" % (self._name, WEIGHT_ATTR, int(target))

    def set_weight(self, target, value: float) -> None:
        mc.setAttr(self._weight_plug(target), float(value))

    def get_weight(self, target) -> float:
        return float(mc.getAttr(self._weight_plug(target)))

    # ------------------------------------------------------------------
    # baking + name decoding
    # ------------------------------------------------------------------
    def _ensure_original_geometry(self) -> None:
        """Connect each driven geometry's ORIG shape to ``originalGeometry[i]``.

        Maya 2026 wires this for an MPxDeformerNode automatically; 2024 wires it
        only for deformers that ask, so there ``originalGeometry`` has no
        elements at all -- the deform has no rest reference and the live target
        path degrades to the baked tables on EVERY pull, silently. ``mc.deformer``
        does not make the connection; ``mc.blendShape`` does, on both versions,
        which is why the wrapper makes it by hand (see ``create``).

        Idempotent: a slot that is already connected is left alone.
        """
        idxs = mc.deformer(self._name, query=True, geometryIndices=True) or []
        geos = mc.deformer(self._name, query=True, geometry=True) or []
        for i, g in zip(idxs, geos):
            el = "%s.originalGeometry[%d]" % (self._name, i)
            if mc.listConnections(el, source=True, destination=False):
                continue
            orig = _orig_shape(g)
            if orig is None:
                continue
            mc.connectAttr(orig + ".outMesh", el)

    def _base_points(self):
        """(N,3) object-space points of the geometry this deformer drives."""
        import numpy as np
        import maya.api.OpenMaya as om2

        geo = mc.deformer(self._name, query=True, geometry=True) or []
        if not geo:
            # A coexist convert MOVES the output edge onto the compiled sibling,
            # and `deformer -q -geometry` answers from that edge -- so a
            # CONVERTED node cannot find its own base. That is silent rather
            # than loud: bake_deltas guards on ``base.shape[0]``, so an empty
            # base sends every target down the "keep the previous deltas" path
            # and the re-bake reports nothing changed. Ask the sibling, which is
            # driving the very geometry this node was built for.
            sib = self._compiled_sibling()
            if sib:
                geo = mc.deformer(sib, query=True, geometry=True) or []
        if not geo:
            return np.zeros((0, 3))
        # The ORIG (intermediate) shape is the undeformed base. Falling back to
        # the deformed shape would fold the current deformation into the deltas.
        shape = geo[0]
        orig = _orig_shape(shape)
        sel = om2.MSelectionList()
        sel.add(orig or shape)
        fn = om2.MFnMesh(sel.getDependNode(0))
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def _require_base(self):
        """``_base_points`` for the file loaders, which cannot work without it.

        An offset field is meaningless on its own: it is ``target - base``, so
        with no base there is nothing to measure it against and nothing to
        deform. The mesh route degrades quietly here (an unbound target just
        bakes empty and the node keeps working), but a file load asked for a
        specific result, so it says so instead.
        """
        base = self._base_points()
        if base.shape[0] == 0:
            raise ValueError(
                "%s has no geometry attached -- shapes can only be loaded onto "
                "a deformer that already drives a mesh. Deform the base mesh "
                "first, then load." % self._name)
        return base

    def _target_points(self, index: int):
        """(N,3) points of the mesh connected to ``targetGeometry[index]``."""
        import numpy as np
        import maya.api.OpenMaya as om2

        plug = "%s.targetGeometry[%d]" % (self._name, index)
        srcs = mc.listConnections(plug, s=True, d=False, shapes=True) or []
        if not srcs:
            return None
        sel = om2.MSelectionList()
        sel.add(srcs[0])
        try:
            fn = om2.MFnMesh(sel.getDependNode(0))
        except (ValueError, RuntimeError):
            return None
        return np.array([[p.x, p.y, p.z]
                         for p in fn.getPoints(om2.MSpace.kObject)])

    def parse_aliases(self, names=None) -> dict:
        """Decode the naming convention into pure index/number structure.

        ``browUp``             -> a MAIN target
        ``browUp50``           -> an IN-BETWEEN of browUp at 0.50
        ``browUp_mouthOpen``   -> a COMBO driven by browUp and mouthOpen

        Returns ``{"main": [...], "inter": {i: (main, knot)},
        "combo": {i: [drivers]}}``, all in logical-index space. Nothing here
        ever reaches the compute -- only the tables built from it do.
        """
        names = self.target_names if names is None else list(names)
        by_name = {n: i for i, n in enumerate(names) if n}

        inter, combo = {}, {}
        main = []
        for i, n in enumerate(names):
            if not n:
                continue
            # Combo first: an underscore form whose every part is a known
            # target is unambiguous, and `browUp_mouthOpen50` must read as a
            # combo in-between, not a main.
            if "_" in n:
                parts = n.split("_")
                if all(p in by_name for p in parts) and len(parts) > 1:
                    combo[i] = [by_name[p] for p in parts]
                    continue
            m = _INBETWEEN_RE.match(n)
            if m and m.group("base") in by_name:
                pct = int(m.group("pct"))
                if 0 < pct < 100:
                    inter[i] = (by_name[m.group("base")], pct / 100.0)
                    continue
            main.append(i)
        return {"main": main, "inter": inter, "combo": combo}

    def _previous_deltas(self) -> dict:
        """The currently-baked tables as ``{index: (vertex_ids, [xyz, ...])}``.

        Read back BEFORE a rebuild overwrites them, so a target whose mesh is
        gone can keep the deltas it already has.
        """
        if not self._has_attr("targetOffset"):
            return {}
        ofs = self._read_multi("targetOffset", int)
        comps = self._read_multi("targetComponents", int)
        flat = self._read_multi("targetDeltas", float)

        out = {}
        for i in range(max(0, len(ofs) - 1)):
            a, b = ofs[i], ofs[i + 1]
            # A truncated or mid-edit table is skipped rather than trusted:
            # slicing past the end would preserve garbage as if it were a shape.
            if b <= a or b > len(comps) or 3 * b > len(flat):
                continue
            out[i] = (comps[a:b],
                      [flat[3 * j:3 * j + 3] for j in range(a, b)])
        return out

    def bake_deltas(self, tol: float = 1e-7, supplied: dict = None) -> dict:
        """Derive sparse per-target deltas from the connected target meshes.

        Mirrors what Maya does while a target is connected: only vertices that
        actually moved are stored. Every target is stored as its RAW
        ``target - base`` offsets -- mains, in-betweens and combos alike. What
        a target's weight means is the COMPUTE's business, not the bake's.

        This deliberately does NOT reduce a corrective by its drivers. An
        earlier version subtracted ``knot * mainDelta`` from each in-between and
        every driver's delta from each combo, on the theory that a corrective
        sculpt is an absolute pose whose linear part must be removed. It is not:
        a corrective is sculpted as the correction ITSELF, on top of whatever
        the drivers already give. Measured on the shipped 167-shape corpus, the
        mains average 1.17 units of travel while the in-betweens average 0.12 --
        corrections, not poses. So the subtraction removed a contribution the
        sculpt never contained, and dialling ``jawDrop75`` to 1 rendered the
        shape minus three quarters of a jaw drop.

        ``supplied`` maps a weight index to a dense ``(N, 3)`` field of RAW
        ``target - base`` offsets, for targets that have no mesh in the scene
        (the file loaders) -- the same thing a connected mesh yields, stored the
        same way.

        A target with neither a mesh nor a supplied field KEEPS whatever it
        already had baked. That is the behaviour this node has always claimed --
        "delete the target and the deltas keep driving the deformation", as the
        module docstring puts it -- and without it any later ``rebuild()`` would
        silently empty every target loaded from a file.

        Returns the table dict it wrote (also useful for tests).
        """
        import numpy as np

        self.ensure_delta_attrs()
        base = self._base_points()
        names = self.target_names
        n_t = len(names)
        supplied = supplied or {}
        previous = self._previous_deltas()

        raw, kept = {}, {}
        for i in range(n_t):
            if i in supplied:
                raw[i] = np.asarray(supplied[i], dtype=np.float64)
                continue
            pts = self._target_points(i)
            if pts is not None and base.shape[0] and pts.shape == base.shape:
                raw[i] = pts - base
                continue
            raw[i] = None
            # Only a target that still EXISTS keeps its deltas. remove_target
            # drops the alias and leaves the logical index sparse, so an empty
            # name is how a removed slot is told apart from one whose mesh is
            # merely gone -- and "a slot with no alias contributes no deltas"
            # is what tables_stale already checks for.
            if names[i] and i in previous:
                kept[i] = previous[i]

        offset, comps, deltas = [0], [], []
        for i in range(n_t):
            d = raw.get(i)
            if d is not None:
                moved = np.nonzero((np.abs(d) > tol).any(axis=1))[0]
                for v in moved.tolist():
                    comps.append(int(v))
                    deltas.extend(float(x) for x in d[v])
            elif i in kept:
                ids, rows = kept[i]
                for j, v in enumerate(ids):
                    comps.append(int(v))
                    deltas.extend(float(x) for x in rows[j])
            offset.append(len(comps))

        # Idempotent: an UNCHANGED table is not written. setAttr dirties the
        # node even when the value it writes is identical, so an unconditional
        # write would put a pointless dirty (and a pointless undo entry) on
        # every re-bake -- and ``resync_targets`` reports "nothing changed" off
        # exactly this. The authoring callers are unaffected: skipping a write
        # that would change nothing leaves the same plug values behind either
        # way.
        for attr, vals, cast in (("targetOffset", offset, int),
                                 ("targetComponents", comps, int),
                                 ("targetDeltas", deltas, float)):
            if self._read_multi(attr, cast) != vals:
                self._write_multi(attr, vals)
        return {"targetOffset": offset, "targetComponents": comps,
                "targetDeltas": deltas}

    def _corrective_tables(self, names) -> dict:
        """Derive the in-between / combo tables from ``names``. Pure -- no DG
        writes -- so ``rebuild_correctives`` and ``tables_stale`` agree by
        construction instead of by two copies of the same logic."""
        n_t = len(names)
        struct = self.parse_aliases(names)

        inter_base = [-1] * n_t
        inter_knot = [0.0] * n_t
        for i, (m, knot) in struct["inter"].items():
            inter_base[i] = m
            inter_knot[i] = knot

        combo_ofs, combo_drv = [0], []
        for i in range(n_t):
            for d in struct["combo"].get(i, ()):
                combo_drv.append(int(d))
            combo_ofs.append(len(combo_drv))

        return {"interBase": inter_base, "interKnot": inter_knot,
                "comboOffset": combo_ofs, "comboDriver": combo_drv}

    def compute_slot_names(self) -> list:
        """The target NAMES this node's Compute reaches by ``self.morphs[...]``.

        Delegates to ``nd_lower.morph_slot_names`` -- the compiler's own
        ordering, not a second reading of it. That single-sourcing is the whole
        safety argument for this feature: if the compiler numbered the names one
        way and ``shapeSlot`` were filled another, the node would compile, run,
        deform, and silently drive the wrong shape.

        Imported lazily. The compiler is Maya-free but heavy, and a wrapper that
        never touches name keys should not pay to import it; a build without it
        present degrades to "no names", which reads as an empty slot table.
        """
        try:
            from mpynode.native.compiler.nd_lower import morph_slot_names
        except ImportError:
            return []
        return list(morph_slot_names(self.get_compute_expression() or ""))

    def _slot_table(self, names) -> list:
        """``shapeSlot``: each compute-declared name -> its weight[] index here.

        -1 for a name this rig has no target for, which the kernels read as a
        target at rest. ``names`` is ``target_names`` (position == logical
        weight index), so the mapping is a plain lookup.
        """
        by_name = {nm: i for i, nm in enumerate(names) if nm}
        return [by_name.get(s, -1) for s in self.compute_slot_names()]

    def rebuild_slots(self) -> dict:
        """Declare and write the name->slot indirection table."""
        self.ensure_slot_attrs()
        table = self._slot_table(self.target_names)
        self._write_multi("shapeSlot", table)
        return {"shapeSlot": table}

    def rebuild_correctives(self) -> dict:
        """Declare and write the in-between / combo tables.

        Always runs -- see ``ensure_corrective_attrs`` on why these are no longer
        opt-in. A rig with no correctives gets ``interBase`` all -1, ``interKnot``
        all 0, ``comboOffset`` all 0 and an empty ``comboDriver``, which
        ``resolve_weights`` reads as "leave every weight alone".
        """
        self.ensure_corrective_attrs()
        tables = self._corrective_tables(self.target_names)
        for attr, values in tables.items():
            self._write_multi(attr, values)
        return tables

    def rebuild(self, supplied: dict = None) -> dict:
        """Re-derive EVERY table from the current targets and their names.

        Call after any change to the target set. The node's own commands do it
        automatically; scene merge, import and reference edits bypass them, so
        the compute is written to degrade safely rather than trust this ran --
        see ``tables_stale``.

        ``supplied`` is forwarded to :meth:`bake_deltas` for targets with no
        mesh in the scene.
        """
        # Repairs a node whose rest reference was never wired -- every scene
        # authored on Maya 2024, where mc.deformer does not make the connection.
        self._ensure_original_geometry()
        out = dict(self.bake_deltas(supplied=supplied))
        out.update(self.rebuild_correctives())
        out.update(self.rebuild_slots())
        return out

    def resync_targets(self) -> bool:
        """Freeze the CONNECTED targets' current shapes into the baked tables.
        Returns True when something was written.

        The deform already follows a connected target live (``liveTargets``), so
        this is not needed to see a sculpt -- it is how you make that sculpt
        PERMANENT: the tables are what survives deleting the target mesh, what a
        compiled sibling reads, and what goes into the ``.ma``. Convert calls it
        for exactly that reason.

        Guarded: a node with no connected target is left alone, a slot that is
        neither connected nor aliased is never silently erased, and a settled
        node performs no plug write at all.
        """
        from mpynode._common.methods.morph_methods import _rebake_if_stale
        return bool(_rebake_if_stale(self._name))

    # ------------------------------------------------------------------
    # targets without a mesh -- offsets and files
    # ------------------------------------------------------------------
    def add_target_from_offsets(self, offsets, name: str = None,
                                indices=None, index: int = None) -> int:
        """Add a target from OFFSETS rather than a mesh. Returns the index.

        ``offsets`` is either a :class:`~mpynode._api2.morph.Morph` (its name,
        indices and offsets are used) or a ``(K, 3)`` array; ``indices`` gives
        the vertex ids for a sparse array and defaults to dense ``0..K-1``.
        Offsets are RAW ``target - base``, exactly what a connected mesh would
        have produced, so correctives reduce the same way.

        No ``targetGeometry`` connection is made, which is the point: the target
        lives in the baked tables only, and nothing has to stay in the scene to
        keep the deformation working.
        """
        import numpy as np
        from mpynode._api2.morph import Morph

        base = self._require_base()
        if isinstance(offsets, Morph):
            name = name or offsets.name
            indices = offsets.indices if indices is None else indices
            offsets = offsets.offsets

        rows = np.asarray(offsets, dtype=np.float64).reshape(-1, 3)
        n = base.shape[0]
        if indices is None:
            if rows.shape[0] != n:
                raise ValueError(
                    "%s: dense offsets have %d vertices but the base mesh has "
                    "%d -- pass `indices` for a sparse target."
                    % (self._name, rows.shape[0], n))
            dense = rows
        else:
            ids = np.asarray(indices, dtype=np.int64).reshape(-1)
            if ids.shape[0] != rows.shape[0]:
                raise ValueError("%s: %d indices for %d offsets"
                                 % (self._name, ids.shape[0], rows.shape[0]))
            if ids.size and (ids.max() >= n or ids.min() < 0):
                raise ValueError(
                    "%s: offsets reference vertex %d, outside the base mesh's "
                    "%d vertices" % (self._name, int(ids.max()), n))
            dense = np.zeros((n, 3), dtype=np.float64)
            if ids.size:
                dense[ids] = rows

        index = self._claim_weight_slot(name or "shape", index)
        self.rebuild(supplied={index: dense})
        return index

    def load_target(self, path: str, name: str = None) -> int:
        """Load ONE shape from a file and add it as a target. Returns the index.

        ``.ma`` / ``.mb`` / ``.obj`` / ``.fbx`` are imported to read their
        points and then removed again, so nothing is left in the scene and no
        construction history reaches the node. ``.npz`` / ``.json`` are read
        directly in the mesh form (``points`` / ``counts`` / ``indices``).

        Either way what lands on the node is offsets, not a mesh. The vertex
        count must match the base mesh -- a file that does not correspond to
        this geometry is an error, not a partial load.
        """
        import numpy as np
        import os

        base = self._require_base()
        ext = os.path.splitext(path)[1].lower()
        if not os.path.isfile(path):
            raise ValueError("%s: no such file" % path)

        if ext in (".npz", ".json"):
            from mpynode._common.io import shape_files
            doc = shape_files.read_mesh(path)
            points = doc["points"]
            found = doc["name"]
        else:
            points, found = self._points_from_scene_file(path)

        if points.shape != base.shape:
            raise ValueError(
                "%s: the shape has %d vertices but the base mesh has %d"
                % (path, points.shape[0], base.shape[0]))

        if not name:
            name = found or os.path.splitext(os.path.basename(path))[0]
        return self.add_target_from_offsets(np.asarray(points) - base,
                                            name=name)

    def load_shapes(self, path: str) -> dict:
        """Load a whole shape CLUSTER from a ``.npz`` / ``.json``.

        One target per record, in file order, each aliased to its stored name.
        A record that moves NO vertices still takes an index and an alias --
        dropping it would shift every later target.

        The names go through the usual convention decode, so ``browUp50`` loads
        as an in-between and ``browUp_mouthOpen`` as a combo, and their offsets
        are reduced accordingly. That is reported in the return value rather
        than being silent, because it is the one thing here that depends on how
        the shapes happen to be named.

        Returns ``{"loaded", "main", "inter", "combo", "names"}``.
        """
        from mpynode._common.io import shape_files

        base = self._require_base()
        n = base.shape[0]
        records = shape_files.read_shapes(path)

        # Validate the WHOLE file before claiming a single index: failing
        # halfway would leave the node carrying aliases for shapes it does not
        # have, and those indices cannot be handed back.
        for rec in records:
            ids = rec["indices"]
            if ids.size and (int(ids.max()) >= n or int(ids.min()) < 0):
                raise ValueError(
                    "%s: %r references vertex %d but the base mesh has %d -- "
                    "this file is not for this geometry."
                    % (path, rec["name"], int(ids.max()), n))

        supplied = {}
        for rec in records:
            idx = self._claim_weight_slot(rec["name"] or "shape")
            supplied[idx] = shape_files.dense_offsets(rec, n)
        self.rebuild(supplied=supplied)

        struct = self.parse_aliases()
        mine = set(supplied)
        return {"loaded": len(supplied),
                "main": len(mine & set(struct["main"])),
                "inter": len(mine & set(struct["inter"])),
                "combo": len(mine & set(struct["combo"])),
                "names": [r["name"] for r in records]}

    def _points_from_scene_file(self, path: str):
        """``((N,3) points, mesh name)`` from a scene file, leaving no trace.

        Imported into a throwaway namespace and deleted again -- the caller
        wants the POINTS, and anything left behind would show up in the outliner
        and in the next scene save.
        """
        import numpy as np
        import os
        import maya.api.OpenMaya as om2

        ext = os.path.splitext(path)[1].lower()
        plugin = _IMPORT_PLUGIN.get(ext)
        if plugin and not mc.pluginInfo(plugin, query=True, loaded=True):
            try:
                mc.loadPlugin(plugin, quiet=True)
            except RuntimeError:
                raise ValueError("%s: reading %s needs the %r plug-in, which "
                                 "will not load" % (path, ext, plugin))

        ns = "mPyLoadTarget"
        new = mc.file(path, i=True, returnNewNodes=True, namespace=ns,
                      ignoreVersion=True, options="v=0;") or []
        try:
            meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                      if not mc.getAttr(m + ".intermediateObject")]
            if not meshes:
                raise ValueError("%s: no mesh in this file" % path)
            sel = om2.MSelectionList()
            sel.add(meshes[0])
            fn = om2.MFnMesh(sel.getDependNode(0))
            points = np.array([[p.x, p.y, p.z]
                               for p in fn.getPoints(om2.MSpace.kObject)])
            found = meshes[0].split("|")[-1].split(":")[-1]
        finally:
            # Deleting a transform takes its shape with it, so by the time the
            # list is walked some entries are already gone -- filter, don't
            # assume, and never let cleanup mask the real error above.
            try:
                alive = [x for x in mc.ls(new, long=True) or []
                         if mc.objExists(x)]
                if alive:
                    mc.delete(alive)
            except (RuntimeError, ValueError):
                pass
            try:
                if mc.namespace(exists=ns):
                    mc.namespace(removeNamespace=ns,
                                 mergeNamespaceWithRoot=True)
            except RuntimeError:
                pass
        return points, found

    def tables_stale(self) -> bool:
        """True when the tables no longer describe the current target set.

        Cheap length check, matching what the compute itself guards on: a stale
        table is a silent out-of-bounds read compiled (nd::at1_ref does no
        bounds checking) while interpreted it would raise, so both sides clamp.
        """
        if not self._has_attr("targetOffset"):
            return True
        names = self.target_names
        n_t = len(names)
        if self._multi_len("targetOffset") != n_t + 1:
            return True                     # a target was added

        # A length check alone is not enough: removing a MIDDLE target leaves
        # the logical count unchanged (indices stay sparse, as Maya does), so
        # compare structure too. A slot with no alias contributes no deltas.
        ofs = self._read_multi("targetOffset", int)
        for i, nm in enumerate(names):
            if not nm and i + 1 < len(ofs) and ofs[i + 1] != ofs[i]:
                return True

        # Renaming changes no length at all, but it can turn a main into an
        # in-between or re-point a combo -- so re-decode and compare.
        if self._has_attr("interBase"):
            want = self._corrective_tables(names)
            if (self._read_multi("interBase", int) != want["interBase"]
                    or self._read_multi("comboOffset", int) != want["comboOffset"]
                    or self._read_multi("comboDriver", int) != want["comboDriver"]):
                return True
            got_k = self._read_multi("interKnot", float)
            if len(got_k) != n_t or any(
                    abs(a - b) > 1e-9 for a, b in zip(got_k, want["interKnot"])):
                return True

        # The compute's name keys move independently of the targets: naming a
        # different shape changes no alias and no length, so nothing above
        # notices. Compare the derived table directly.
        want_slots = self._slot_table(names)
        if want_slots or self._has_attr("shapeSlot"):
            if not self._has_attr("shapeSlot"):
                return True
            if self._read_multi("shapeSlot", int) != want_slots:
                return True
        return False

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._name!r}>"
