# mPyBlendShape

Expression-driven custom blendShape. You write the deformation formula in
Python. Its runtime compute surface is **identical to
[`mPyDeformer`](mPyDeformer.md)** — the node is conceptually a "blend shape"
but, at the code level, it is a deformer you drive with an expression.

---

## Base class & MTypeId

- Base class: `MPxDeformerNode` — **not** `MPxBlendShape`, and that is a
  deliberate choice rather than a missing API. `maya.OpenMayaMPx.MPxBlendShape`
  **does** exist, on Maya 2024 and 2026 alike; it is API **2.0** that has no
  `MPxBlendShape` (`MPxNode.kBlendShape == 25` on both). An earlier version of
  this page stated the inverse. Measured against a probe node registered
  `kBlendShape` on both Mayas, re-basing would:
  - **stop the node deforming** — `MPxBlendShape` never calls `deform()`; it
    routes to `deformData(block, handle, geomIndex, matrix, multiIndex)`, and
    with only `deform()` overridden the node raises `kNotImplemented` and
    leaves the geometry untouched;
  - **break the aliased `weight[]`** — a `kBlendShape` node is a real
    `blendShape` in the type lineage and inherits the whole native surface
    (~79 extra attrs, including `inputTarget[].inputTargetGroup[]…`). Its
    native `weight[]` (short name `w`) owns the name, so
    `addAttr -ln weight -multi` fails and `weight` silently stops being a user
    attr — which is exactly the "compiled node with no weights" failure
    described under [Plug-in](#plug-in);
  - **fall outside the C++ codegen**, which accepts `MPxDeformerNode` /
    `MPxSkinCluster` only;
  - on Maya 2024, additionally **drop `weightList[].weights`** (the probe node
    is not a `weightGeometryFilter` there, though it is on 2026).
- MTypeId: `0x0013571C`.

---

## Expression contract (`self.X`)

There is **no** bridge-injected `self.points` / `self.targets` /
`self.target_weights` / `self.deformed` schema (that older auto-blend design
was removed). The live surface is the deformer contract plus a flat
multi-target surface:

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.outputGeometry[i]` | `MFnMeshHandle` | read/write | Writable output mesh, eager-copied from input. `getPoints()` → `(N, 3)` numpy; `setPoints(arr)` commits. |
| `self.input[i].inputGeometry` | `MFnMesh` | read | Read-only upstream source. |
| `self.envelope` | `float` | read | Inherited envelope. |
| `self.targetGeometry[j]` | `MFnMesh` or `None` | read | Read-only handle to the j-th connected target shape. A flat mesh-data multi declared by `node_initializer` — **not** Maya's native nested `inputTarget[].inputTargetGroup[]…` tree. Read points with `om.MFnMesh.getPoints(pa, om.MSpace.kObject)` and convert via `mpynode._common.array_io.points_array_to_numpy`. Reading this at a **runtime** index blocks the native compile (see below). |
| `self.weight[j]` | `float` | read | Per-target weight, each element **aliased** to its target name — `bs.browUp` *is* `bs.weight[0]`, and it shows in the channel box as `browUp`, exactly like a stock blendShape. A user attr added by `MPyBlendShape.create`, not by `node_initializer`. |
| `self.morphs` | `MorphStack` | read | The whole target stack as one object — a **view** over the baked tables, with no plugs of its own. This is the surface the shipped templates use; see below. |
| user input attrs / storage | per type | read/write | `add_input_attr(...)` names + `self.foo` Python state. |

`weight` is **not** a reserved name (an earlier version of this page claimed it
was). Verified against Maya 2026: long `weight` **plus short `w`** does fail,
because `w` belongs to the inherited `weightList[].weights` child — but `weight`
with any other short name registers fine, and a user attr takes `weight` as its
own short name.

Envelope-only deform (no targets):

```python
import numpy as np
mesh = self.outputGeometry[0]
rest = mesh.getPoints()
env  = float(self.envelope)
out  = rest.copy()
out[:, 0] *= 1.0 + 0.5 * env   # squash on X/Z, stretch on Y
out[:, 1] *= 1.0 - 0.5 * env
out[:, 2] *= 1.0 + 0.5 * env
mesh.setPoints(out)
```

---

## Multi-target morphing — read baked deltas, not live targets

`node_initializer` declares `targetGeometry[j]` (a mesh-data multi; connect each
target shape's `outMesh` into element `j` — `create(targets=[...])` does this).
`MPyBlendShape.create` adds the aliased `weight[j]` float multi. Both are wired
to `outputGeom`, so changing either re-evaluates the deform.

**The compute should read baked deltas, not the target meshes.** That is what
Maya itself does: a stock blendShape stores each target *twice* — as a live
`inputGeomTarget` connection **and** as sparse `inputPointsTarget` /
`inputComponentsTarget` deltas — and it is the deltas that drive the
deformation. Delete a target mesh and a native blendShape keeps working.

It is also the only form that compiles. `nd_lower` rewrites a mesh-multi element
read **only at a literal index**, and a blendShape's defining loop runs over
targets at a *runtime* index — so a compute containing `self.targetGeometry[i]`
honest-rejects the native compile. Numbers lower; meshes do not.

`MPyBlendShape.rebuild()` derives CSR (compressed sparse row) delta tables from
whatever is currently connected:

| table | shape | meaning |
|---|---|---|
| `targetOffset` | `(T+1,)` int | `targetOffset[t] .. targetOffset[t+1]` is target `t`'s slice |
| `targetComponents` | `(K,)` int | which vertex moved |
| `targetDeltas` | `(3K,)` double | flat xyz offset per entry |
| `shapeSlot` | `(S,)` int | the compute's `s`-th NAME key → its `weight[]` index here, or `-1` |

You do **not** index those tables by hand. `self.morphs` is the stack as an
object, and the deform is the formula written out:

```python
mesh = self.outputGeometry[0]
base = mesh.getPoints()

# out = base + envelope * sum_t weight[t] * delta_t
w = self.morphs.weights
mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
```

`w` is yours to reweight before it is accumulated — that is where in-between
and combo rules live, in the node that wants them, rather than in a shared
resolver. `combo_correctives` ships this shape with its corrective rules
spelled out in its Init tab.

### Construction history — `liveTargets`

Baked tables would mean the deform never re-reads a target, so sculpting a
connected target would change nothing. Instead the deltas surface reads a
target's offsets straight off its **connected mesh**: sculpt a target and the
shape follows as you drag, which is the construction history a rigger expects.
It is on by default and needs nothing in the compute.

A slot goes live only when **both** hold:

- it `isDestination()` — something is actually connected. `targetGeometry` is
  `setCached(True)`, so a *disconnected* element keeps serving its last mesh;
  the data alone cannot tell you the connection is gone. The plug tree is the
  only honest discriminator (and it is a topology query, safe off the
  Evaluation-Manager worker thread the deform runs on).
- its weight is non-zero. A zero-weight target contributes exactly zero, so
  skipping its read is *exact*, not an approximation — and it is what keeps a
  167-target rig affordable, since almost none of a face is dialled in at once.

Everything else falls back to the baked tables, so "delete the target and the
deltas keep driving the deform" still holds, as does the `.ma` round-trip.

The deltas are measured against `originalGeometry` — the same rest shape
`bake_deltas` uses — not against the points arriving in the compute, which
already carry any *upstream* deformation. An unsculpted live target therefore
matches its bake to the last bit, upstream deformers included.

**The deform writes nothing.** No `setAttr`, no dirty, nothing on the undo
stack. That is not incidental: a re-bake from inside an evaluation has to be
marshalled off it, which lands the write in its own undo chunk on top of
whatever the user was doing — so their vertex edit can no longer be undone.

Switch `liveTargets` **off** to pin the deform to the baked tables. Two reasons
to: deltas edited by hand or loaded from a file while the target mesh is still
connected, and a pose with enough targets dialled in at once that reading them
all costs more than the immediacy is worth.

`MPyBlendShape.resync_targets()` makes a live sculpt **permanent** by freezing
it into the tables. It is guarded — a settled node writes nothing, a node with
no connected target is left alone, and a slot that is neither connected nor
aliased is never silently erased (`bake_deltas` would drop it).

**After Convert Node to C++.** A compiled node reads the baked tables and has no
live path, so the convert calls `resync_targets()` first and the tables it runs
on are a *snapshot* taken at convert time. The interpreted node keeps its
connections and stays the source of truth, so nothing is lost, but sculpting a
target while converted will not move the shape. Revert to Python, sculpt, and
convert again.

### `self.morphs` in a compute

`MorphStack` (`scripts/mpynode/_api2/morph.py`) is a **view** over the baked
tables — it owns no plugs and there is nothing to keep in sync. In a compute,
exactly this surface is recognised:

| form | is | returns |
|---|---|---|
| `self.morphs.apply(base)` | the whole deform | `(N, 3)` deformed points |
| `self.morphs.apply(base, env)` | …enveloped | `(N, 3)` deformed points |
| `self.morphs.weights` | the raw `weight[]` channels | `(T,)` |
| `self.morphs.resolved` | weights **after** in-between + combo resolution | `(T,)` |
| `self.morphs.deltas(base)` | the offset field, weights auto-resolved | `(N, 3)` |
| `self.morphs.deltas(base, w)` | the offset field for a weight vector you built | `(N, 3)` |
| `self.morphs[i].weight` | one target's channel, `i` an int **literal** | `float` |
| `self.morphs["browUp"].weight` | one target's channel **by name** | `float` |
| `len(self.morphs)` | target count | `int` |

Everything comes back as a plain numpy array, so your own blend maths is just
maths:

```python
w = self.morphs.resolved
w = w * float(self.someMultiplier)
mesh.setPoints(base + float(self.envelope) * self.morphs.deltas(base, w))
```

**The object is erased at compile time.** `nd_lower._rewrite_morph_reads` is an
`ast.NodeTransformer` that rewrites each member into a blessed method
(`morph_apply`, `morph_weights`, `morph_deltas`), and each of those lowers by
transpiling the *same* pure-numpy kernel the interpreted node runs
(`mpynode._common.methods.morph_blend`). One algorithm, not two; no `MorphStack`
and no target name survives into the generated C++. This is the same
compile-time-erasure pattern as `Mesh` / `NurbsCurve` / `NurbsSurface`.

Anything outside that table **honest-rejects** rather than silently falling back
to interpreted — the portability gate runs the real desugar, so the Compile tab
reports the identical message the lowering would.

One shape constraint, inherited from `_rewrite_deform_io` and not specific to
this object: the getPoints/setPoints rewrite is **line-local**, so `base` must be
its own statement. `setPoints(self.morphs.apply(mesh.getPoints(), env))` does
not compile.

### Name keys in a compute — folded to a slot

`self.morphs["browUp"].weight` works in a compute, and it is worth knowing why,
because the obvious mechanism is impossible: aliases resolve through a
side-channel DG query that returns **empty** on the worker thread `deform()`
runs on. No name can be looked up live, on either path.

So the name is resolved at **compile time** instead. Each distinct name the
source mentions gets an ordinal **slot**; the compiler bakes only that integer,
and `rebuild()` writes the per-rig `weight[]` index into `shapeSlot[slot]`:

```
compute source ──► nd_lower.morph_slot_names ──► ("jawOpen", "browUp")
                                                    slot 0     slot 1
rig A: jawOpen=weight[2], browUp=weight[0]   ──►  shapeSlot = [2, 0]
rig B: jawOpen=weight[0], browUp=weight[2]   ──►  shapeSlot = [0, 2]
generated C++ (identical for both):  morph_weight_at(0), morph_weight_at(1)
```

The C++ holds pure integer indirection, no target name reaches it, and **one
bundle still serves any rig**. The interpreted `MorphStack` resolves through the
*same* ordering function and the *same* `shapeSlot` table, so the two halves
agree by construction rather than by two implementations happening to match.

The key must be a **provable compile-time constant**. All of these work:

```python
x     = self.morphs["browUp"].weight        # literal

JAW   = "jawOpen"                           # assigned once, at the top
y     = self.morphs[JAW].weight

NAMES = ("browUp", "mouthOpen", "jawOpen")  # constant tuple
tot   = 0.0
for n in NAMES:                              # unrolled at compile time
    tot = tot + self.morphs[n].weight

for i in range(len(NAMES)):                  # also fine
    tot = tot + self.morphs[NAMES[i]].weight
```

"Provable" is not pedantry. A string local is a genuine runtime value —
`key = "browUp"` lowers to a real `std::string` — so this is legal Python that
must **not** fold:

```python
k = "browUp"
if float(self.envelope) > 0.5:
    k = "mouthOpen"
x = self.morphs[k].weight        # rejects: 'k' is not a provable constant
```

Folding that would silently drive the wrong shape, so the rule is *prove, not
assume*: bound exactly once, at compute top level, from string literals, never
rebound and never mutated. Anything else rejects at the key site, naming the
variable.

Two more behaviours worth knowing:

- **A name this rig has no target for reads `0.0`** — a target at rest, on both
  paths, rather than an error. That is what lets one bundle run on a rig that
  simply lacks the shape. Authoring-side lookup still raises `KeyError` on an
  unknown name, where a typo is worth catching.
- **`rebuild()` must have run since the compute last changed.** Editing the
  expression to name a different shape touches no alias and no table length, so
  `alias_fingerprint` folds the compute's slot names in and `tables_stale()`
  compares the derived `shapeSlot` directly.

Unrolling is capped (256 emitted statements) with a loud message — naming 300
targets one at a time is a sign you want `self.morphs.resolved` instead.

Clamping lives in the kernels, not in your compute. A stale table would be a
*silent out-of-bounds heap write* once compiled (`nd::at1_ref` does no bounds
checking) while interpreted it would raise `IndexError` — the two halves would
disagree exactly when something is already wrong. Every kernel clamps, so both
degrade the same way.

### `self.morphs` while authoring

Off the wrapper (`MPyBlendShape.morphs`) the same object carries **names**,
because on the main thread the aliases resolve:

```python
from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
bs = MPyBlendShape.create(mesh=base)
bs.add_target(browUpMesh, "browUp")
bs.add_target(mouthOpenMesh, "mouthOpen")
bs.rebuild()                                # bake deltas + decode names
mc.setAttr(bs.get_name() + ".browUp", 1.0)  # by ALIAS, like Maya

bs.morphs["browUp"]          # by name
bs.morphs.find("brow")       # case-insensitive substring; glob if you pass * or ?
bs.morphs.names              # every alias, in weight order
len(bs.morphs)               # target count

m = bs.morphs["browUp"]
m.size, m.max_magnitude      # how many verts moved, and by how much
blended = 0.5 * m + 0.5 * bs.morphs["mouthOpen"]   # sparse-index UNION
bs.morphs["browUp"].dense(nv)                      # (N, 3) if you want it dense
```

`Morph` overloads `+ - * /` and unary `-`. Addition takes the **union** of the
two sparse index sets, so combining targets that touch different vertices does
not silently drop either one.

---

## Correctives: in-betweens and combos

Target **names** declare the rig, and `rebuild()` decodes them once, in Python:

| alias | meaning |
|---|---|
| `browUp` | a main target, driven by its own weight |
| `browUp50` | an in-between of `browUp`, peaking at `0.50` |
| `browUp_mouthOpen` | a combo, active only as **both** drivers rise |

Every target — corrective or not — is baked as its **raw** `target - base`
offsets. A corrective is sculpted as the correction itself, on top of whatever
its drivers already give, so there is nothing to subtract at bake time. That is
also why dialling a corrective's own channel to 1 puts exactly the shape it was
sculpted as on the mesh.

How those weights are *interpreted* is the compute's business, not the
framework's, and it differs per rig. The `combo_correctives` template rides a
**cross-blending** hat (1 on its own knot, 0 at the adjacent knots, so sibling
in-betweens hand off instead of stacking) and reads a combo as the product of
its drivers with the last alias keyword squared.

`ensure_corrective_attrs()` declares the tables that carry this:
`interBase[t]` (the main target an in-between corrects, else `-1`),
`interKnot[t]`, and `comboOffset` / `comboDriver` (CSR, same shape as the delta
tables). `rebuild()` declares them **unconditionally** — `morph_weights` names
all four as implicit reads, and a blessed method with an unbound declared read
is a compile-time reject, so a node without them could not compile.

They are inputs to *your* maths, not to a hidden one. **There is no shared
weight resolver**: a rig that wants in-betweens and combos writes the rules in
its own Init tab, where they can be read and changed. The `combo_correctives`
template does exactly that — `inbetween_hat`, `combo_blend` and
`resolve_morph_weights` are three ordinary functions sitting in its Init tab,
and its Compute is a summary that calls them:

```python
w = resolve_morph_weights(self.weight, self.interBase, self.interKnot,
                          self.comboOffset, self.comboDriver,
                          self.applyCorrectives, self.applyCombos)

mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
```

Without correctives it is the same shape, simpler — `w = self.morphs.weights`,
straight through. Init transpiles alongside the Compute, so an edited rule
still compiles to pure C++.

**No name reaches the generated C++.** `self.aliases` is an authoring-time
property only, and so is `MorphStack.names` — a stack built inside a compute has
no aliases at all. A name *key* does work in a compute, but it is folded to an
integer slot at compile time (above); the alias table is never consulted at
runtime on either path. Alias lookup is a side-channel DG query, and those return **empty** on the
Evaluation-Manager worker thread that `deform()` runs on — so a compute that
read names would be unreliable interpreted and impossible compiled. The
portability gate rejects `self.aliases` in a compute for exactly this reason.

Because the tables are node *data*, nothing character-specific is baked into the
generated C++: **one compiled bundle serves any rig.**

---

## Lineage

```
MPxNode
  └── MPxGeometryFilter
        └── MPxDeformerNode
              ├── MPxSkinCluster → mPySkinCluster
              ├── mPyDeformer
              └── mPyBlendShape
```

---

## Plug-in

Registered in `plug-ins/mpynode_api1.py` (API 1.0 only):

```python
plugin.registerNode(
    MPyBlendShape.NODE_NAME, MPyBlendShape.NODE_ID,
    MPyBlendShape.node_creator, MPyBlendShape.node_initializer,
    MPxNode.kDeformerNode,
)
```

`node_initializer` adds the framework/instrumentation plugs (via
`helpers.build_internal_attrs`) plus **one** multi-target plug:
`targetGeometry` (`MFnTypedAttribute` `kMesh`, array, connection-driven / not
storable), `attributeAffects`-wired to `outputGeom`.

`weight[]` is deliberately **not** declared there. The compile spec captures
*user* attrs, and preset meta carries no `is_array` flag — so a statically
declared multi could not ride the preset path and the compiled node would end up
with no weights at all. `MPyBlendShape.create` adds it with
`add_input_attr("weight", "float", is_array=True)` instead, which also puts it
in the decoded `_inputAttrs` map that feeds `setDependentsDirty` (so a
channel-box drag re-deforms).

`add_input_attr` forces `keyable=False` on every array input, to stop numeric
multis flooding the channel box. `add_target` overrides that per element, which
is the one case where the rule is backwards — an aliased weight *is* a rig
channel. `node_swap.copy_aliases` carries both the alias and that keyable state
onto the compiled node, so the C++ sibling presents the same channel surface.

---

## Output plug

The inherited `outputGeometry[]` multi from `MPxGeometryFilter`.

---

## Failure mode

Expression error → input mesh unchanged (error to `sys.stderr` + Log tab).
Vertex-count mismatch on commit → output drops back to input with an stderr
warning.

---

## Example

Build a two-target mPyBlendShape headlessly. `add_target` wires each target's
`outMesh` into `targetGeometry[j]` and aliases `weight[j]` to the name you give
it; `rebuild()` bakes the sparse deltas the compute reads. After that the node
is driven **by name**, and the deformed base is read back and asserted to have
stretched and widened.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

mc.file(new=True, force=True)

# Base sphere plus two same-topology targets edited in OBJECT space, so the
# blendShape bakes real per-vertex deltas (not transform offsets).
base   = mc.polySphere(name="morphBase", radius=1.0)[0]
taller = mc.polySphere(name="targetTaller", radius=1.0)[0]
mc.scale(1.0, 1.6, 1.0, taller + ".vtx[*]", relative=True)
wider = mc.polySphere(name="targetWider", radius=1.0)[0]
mc.scale(1.6, 1.0, 1.6, wider + ".vtx[*]", relative=True)

bs = MPyBlendShape.create(mesh=base, name="customMorph")
bs.ensure_delta_attrs()
bs.set_init_expression("import numpy as np\n")
bs.set_compute_expression(          # the object-surface compute from above
    "mesh = self.outputGeometry[0]\n"
    "base = mesh.getPoints()\n"
    "mesh.setPoints(self.morphs.apply(base, self.envelope))\n"
)
bs.add_target(taller, "browUp")
bs.add_target(wider, "mouthOpen")
bs.rebuild()                        # bake deltas + decode names

name = bs.get_name()
mc.setAttr(name + ".browUp", 1.0)   # by ALIAS -- no weight[0] anywhere
mc.setAttr(name + ".mouthOpen", 0.0)

# Force deform eval and read the deformed base back via its shape points.
base_shape = mc.listRelatives(base, shapes=True, noIntermediate=True)[0]
y_taller   = max(p[1] for p in mc.getAttr(base_shape + ".vrts[*]"))
assert y_taller > 1.4, "browUp did not stretch base (got %r)" % y_taller

mc.setAttr(name + ".mouthOpen", 1.0)
xs       = [p[0] for p in mc.getAttr(base_shape + ".vrts[*]")]
x_extent = max(xs) - min(xs)
assert x_extent > 2.4, "mouthOpen did not widen base (got %r)" % x_extent

print("OK morph deformed: top Y=%.3f (rest 1.0), X extent=%.3f (rest 2.0)"
      % (y_taller, x_extent))
```

Shipped template (compiles to pure C++, `deterministic: true`):

- `templates/MPyBlendShape/Combo Correctives` — aliased weights + baked
  deltas, plus in-betweens and combos decoded from the target names.

---

## Differences vs the other deformers

| Aspect | mPyDeformer | mPyBlendShape |
|---|---|---|
| Base class | `MPxDeformerNode` | `MPxDeformerNode` (`MPxBlendShape` ships in API 1.0 but is deliberately unused — see [Base class & MTypeId](#base-class--mtypeid)) |
| Geometry access | `self.outputGeometry[i]` | identical |
| Target morphing | — | `targetGeometry[j]` mesh multi (authoring) + aliased `weight[j]` float multi + baked CSR delta tables (what the compute reads) |
| MTypeId | `0x00135716` | `0x0013571C` |

---

## See also

- Template: `templates/MPyBlendShape/Combo Correctives`
- Object: `scripts/mpynode/_api2/morph.py` (`Morph`, `MorphStack`)
- Kernels (one algorithm, both halves):
  `scripts/mpynode/_common/methods/morph_blend.py`
- Blessed methods + the `morphs` property:
  `scripts/mpynode/_common/interface/morph_method_interface.py`
- Compile-time erasure: `nd_lower._rewrite_morph_reads`
- Wrapper: `scripts/mpynode/wrappers/mpy_blend_shape.py`
- Bridge: `scripts/mpynode/_api1/mpy_blend_shape.py`
- Plug-in registration: `plug-ins/mpynode_api1.py`
- Sibling deformers: [`mPyDeformer.md`](mPyDeformer.md),
  [`mPySkinCluster.md`](mPySkinCluster.md)
