# Importing a v1 (`node-designer`) node — design note

**Status: BUILT.** `_common/io/v1_import.py`, 22 tests in
`tests/framework/test_v1_import.py`.

## Result against the real corpus

All nine upstream `examples/*.ma` scenes, imported and evaluated:

| | count | |
|---|---|---|
| Parsed and built as native v2 nodes | **9 / 9** | |
| Compute runs clean | 4 | gameOfLife, springChain, textMeshGenerator, textureSwitch |
| Blocked by the fixture, not the converter | 3 | bubbleSort + spine ship the node with nothing wired to its array/curve inputs; ouch needs `pyaudio` |
| Need hand-finishing | 2 | spline, unitSphereCollision |

The last two are the one thing a converter cannot do for you, and the importer
flags them itself via `needs_hand_finish` / `api_objects`: **v1 made its own
`MPoint` / `MVector` / `MMatrix` shims ambient in the expression namespace AND
handed plug values as those objects.** v2 hands numpy and `MatrixView`, so
`MPoint * MatrixView` and `MVector(<numpy row>)` stop type-checking. That is a
rewrite of the maths, not a substitution, so it is reported rather than
guessed at. Five of the nine touch those names; two actually break on it.

Four things the real files did that a reading of v1's source would not have
predicted, each now a test:

* the payload is the **last** quoted run on a `setAttr` line, not the first --
  taking the first yields the plug name and every file fails to decode;
* **any** string plug may be wrapped across `( "..." + "..." )`, not just the
  expression -- four of the nine wrap;
* a continuation run has **no closing-paren line**; Maya writes the final
  fragment and the `);` together, so a parser waiting for a lone `)` eats the
  rest of the node;
* stored vars can hold **v1's own classes**, which would otherwise need v1 on
  `sys.path` -- handled by a restricted unpickler that maps them to plain data
  and refuses anything outside an allow-list.

And one thing the spec got wrong: leaving a shadowed input bare is not enough.
`splineNode` reads `degree` *before* assigning to it, so bare raised
`NameError`. The fix reproduces v1 exactly -- prepend `degree = self.degree`,
then leave every later use bare, so the name starts as the plug value and any
assignment shadows it locally from there.

## Context

MPyNode 2.0 replaces [mpynode/node-designer](https://github.com/mpynode/node-designer)
and is not compatible with it: v1 registers `mPyNode` under MTypeId
`0x001255C3`, v2 under `0x00135700`, so v1 scenes do not open under v2 and the
two plug-ins cannot be loaded in one Maya session.

An importer is what makes that break acceptable rather than hostile. The
precedent is `2to3`: Python 3 was a hard break too, and the migration tool is
most of why it was tolerated. Without one, "2.0" means every v1 node ever
written is thrown away.

Everything below was measured against a real v1 scene —
`examples/quaternionSpineNode.ma` from the upstream repo — not inferred from
source.

## Ground truth: what a v1 node actually stores

Five plugs on the node, `expression` public and the rest underscore-private:

| Plug | Content | Encoding |
|---|---|---|
| `expression` | the single compute source | plain string, `.ma`-escaped |
| `_inputAttrs` | `{name: [type]}` | base64 + pickle |
| `_outputAttrs` | `{name: [type]}` | base64 + pickle |
| `_storedVarNames` | `[name, ...]` | base64 + pickle |
| `_storedVarsData` | `{name: value}` | base64 + pickle |

Decoded from the spine example:

```
_inputAttrs    controlMatrices ['matrix']   inputCurve ['nurbsCurve']
               curveAimAxis ['enum']        pivot ['float'] ...        (13 total)
_outputAttrs   outputTranslate ['vector']   outputRotate ['euler'] ...  (4 total)
_storedVarNames  ['defaultLength']
_storedVarsData  {'defaultLength': 12.0}
expression       6,834 chars (a first, cruder decode said 18,734 --
                 it was swallowing the following setAttr lines)
```

Three things worth knowing before writing any code:

* **Never compressed.** `_dumpPickle` is
  `codecs.encode(pickle.dumps(data, HIGHEST_PROTOCOL), "base64")`. There is no
  zlib/gzip/bz2/lzma anywhere in v1's 1,548-line node module. (v2's `.mpn`
  export *does* have a compression option — that is a different thing.)
* **Mixed pickle protocols inside one node.** In the spine example
  `_inputAttrs` carries a protocol-2 marker (`gAJ9`) while `_outputAttrs`
  carries protocol 4 (`gASV`) — the file was written across a Python 2 → 3
  migration. `pickle.loads` handles both, but a reader that assumes one
  protocol will be wrong on real files.
* **v1 fails silently.** `_loadPickle` ends in a bare `except: pass`, returning
  `None`. Any v1 node whose data was already corrupt will read as empty rather
  than as an error, so the importer must treat "no attrs" as suspicious rather
  than as an empty node.

## What converts mechanically

**Attribute types need no mapping at all.** v1's 15 types are a strict subset
of v2's 19:

```
v1: int float bool enum vector matrix color time angle euler
    string mesh nurbsCurve nurbsSurface python
v2: the same 15, plus double float2 hex quaternion
```

So `_inputAttrs` and `_outputAttrs` feed `add_input_attr` / `add_output_attr`
directly, name and type unchanged. Stored variables likewise: `_storedVarsData`
is already `{name: value}`, which is what `set_variable(name, value,
persistent=True)` wants.

That is most of a node, and it is close to free.

## What needs a real transform: the expression

v1 exposed plugs as **bare locals**. An input named `pivot` was readable as
`pivot`; an output named `outputTranslate` was written as `outputTranslate = ...`.
v2 uses `self.pivot` and `self.outputTranslate = ...`.

An AST pass, not a regex — a text substitution would corrupt string literals,
comments, attribute access on unrelated objects, and any local that happens to
share a plug's name:

* build the declared-name set from `_inputAttrs` + `_outputAttrs`;
* rewrite `Name(id=n, ctx=Load)` → `Attribute(Name('self'), n, Load)` for reads;
* rewrite `Name(id=n, ctx=Store)` → the same with `Store` for writes;
* **do not** rewrite a name that is bound locally before use — a v1 expression
  that did `pivot = pivot * 2` as a scratch variable must not become
  `self.pivot = self.pivot * 2`, which would write the plug. Track assignments
  and shadowing per scope.

This codebase already does harder AST work than this in
`native/compiler/py_to_cpp.py`; the machinery and the idioms are there.

### The Init / Compute split

v1 had one blob. v2 has tiers, and the split matters: Init runs once per file
open and its names are bare globals in Compute.

The spine example opens with `from bisect import bisect_left as bl`,
`import math`, `import maya.api.OpenMaya as om`, then several `def`s, then the
per-frame body. The natural rule:

* leading `Import` / `ImportFrom` and top-level `FunctionDef` / `ClassDef`
  → **Init**;
* everything else, in order → **Compute**.

Get this wrong in the safe direction: anything ambiguous stays in Compute,
which merely costs per-evaluation work rather than breaking the node.

## What will not convert cleanly

| Problem | Why | Suggested handling |
|---|---|---|
| **Enum field names are absent** | v1 stores `['enum']` and nothing else — no labels. The spine example has **5 enum inputs** and not one has field names | Real collision: v2 now *rejects* an enum with no `enum_names`. Synthesise `["0", "1", ...]` up to the highest index the expression compares against, and report every one so the user can rename them |
| **`maya.api.OpenMaya` in the body** | v1 expressions routinely build `om.MMatrix`/`om.MVector`. v2 asks that outputs be written as numpy/native and warns that constructing api objects for a plug write is almost always wrong | Convert as-is, flag it. It will still run; it just will not lower to C++ |
| **Outputs written via api objects** | Same root cause, but this one can actually be wrong rather than merely slow | Flag loudly in the report |
| **`python` type plugs** | Both sides have the type, but v1 pickles arbitrary objects; unpickling executes code | Refuse by default; honour the existing `MPYNODE_TRUST_PICKLE` / trust-prompt path rather than inventing a second policy |
| **Silently-empty v1 data** | The bare `except: pass` above | Treat empty attrs on a node with a non-empty expression as an error, not an empty node |

## Delivery

Read from a **`.ma` file**, not from a live node. That is the decision that
makes the whole feature possible without renaming v2's node type: v1's plug-in
never has to be loaded, so the `mPyNode` name collision never arises. A `.ma`
is text and all five plugs are string-valued.

Reuse rather than reinvent:

* `_common/io/mpn_io.py` — the `.mpn` round-trip already knows how to
  reconstruct a node from attr maps + sources + stored vars. The importer
  should produce that shape and hand off, not build a second node-builder.
* `ui/llm/tools.py :: dispatch("define_node", ...)` — the tested apply spine.
* `_common/io/trust.py` — the existing pickle-trust policy.

Suggested surface: `mpynode.io.v1_import.read_v1_ma(path) -> [spec, ...]` plus a
`File ▸ Import v1 Node…` entry, and a conversion **report** — what converted,
what was synthesised, what was flagged — because a silent 90% conversion is
worse than a noisy one.

## Verification: the corpus already exists

Upstream ships **8 example scenes**, and six of them have v2 template twins:

| v1 example | v2 template |
|---|---|
| `bubbleSortNode.ma` | `MPyNode/Bubble Sort` |
| `splineNode.ma` | `MPyNode/Spline` |
| `springChainNode.ma` | `MPyNode/Spring Chain` |
| `unitSphereCollisionNode.ma` | `MPyDeformer/Unit Sphere Collision` |
| `ouchNode.ma` | `MPyNode/Ouch` |
| `gameOfLifeNode.ma` | `MPyMesh/Game Of Life` |

That is a matched before/after pair for six nodes: import the v1 scene, and
compare the result against the v2 template that was written by hand from the
same idea. Not byte-equality — the v2 templates were rewritten, not converted —
but a strong check that the importer produces something of the same shape, with
the same attributes and a compute that runs.

`quaternionSpineNode.ma` and `textMeshGeneratorNode.ma` have no twin and are the
better regression fixtures precisely because nobody has hand-tuned a v2 answer
for them.

Start with the spine: 13 inputs, 4 outputs, 1 stored var, 179 lines, five
enums with no labels, and `om` usage throughout. If that one converts and runs,
the shape is right.

---

# Converting on scene open — the other path

**Status: BUILT.** `_common/io/v1_upgrade.py`, 27 tests in
`tests/framework/test_v1_upgrade.py`.

The text importer above needs a `.ma`. That rules out `.mb`, references,
imports and paste, and it asks the user to know their scene contains a v1 node.
The on-open path asks nothing: v2 registers the same node TYPE name as v1, so
Maya builds a v2 `mPyNode` and replays v1's `setAttr` calls at it, and the node
can be converted where it sits.

One plug had to be added for this to be possible at all —
`_api2.helpers.make_legacy_expression_attr` declares a hidden, unconnectable
`expression` string so v1's single compute source lands instead of being
dropped. `is_pending` then gates on *non-empty `expression` + empty
`_computeSource`*, a state no v2-authored node can be in, which makes the sweep
idempotent with no marker attribute.

## The trap: a shared plug name is not a shared format

Everything else about the open looked like good news, and that was the problem.
All 26 user attributes survive — `addAttr` is type-agnostic — and every
internal plug loads without complaint. The node looks converted. It is not:

| Plug | v1 | v2 | Symptom |
|---|---|---|---|
| `_inputAttrs` / `_outputAttrs` | base64+pickle `{name: [type]}` | **plain JSON** `{name: {attr_type, is_array, order}}` | plugs on the node, Attributes tab **empty**, `self.<attr>` unresolved |
| `_storedVarNames` | base64+pickle `[name, ...]` | **comma-joined string** | every stored variable reads back absent, plus one garbage name in the UI |
| `_storedVarsData` | base64+pickle `{name: value}` | same | — genuinely compatible |

A payload that survives intact and is then read as nothing is much harder to
notice than one that failed to load, and both of these shipped past a check
that read the plug back and found it undamaged. The tests assert through v2's
own readers (`get_input_attr_map`, `get_variables`) for exactly that reason.

Two details v1's schema simply cannot express, so they come from elsewhere:

* **`is_array`** — a multi is stored as `['matrix']` just like a single. Read
  from the live plug with `attributeQuery(multi=True)`; the plug is the only
  witness.
* **`order`** — taken from the v1 dict, which preserves authoring order, and
  which is what drives Channel Box ordering.

## The ordering constraint

`stored_var_store.load_and_clear_all()` hydrates `_storedVarsData` into an
in-memory cache and then **clears the plug**, on the grounds that the cache is
authoritative for the session. So the upgrade must be sequenced *before* it in
`_on_scene_opened` and `_on_after_import` — placed after, it reads an empty
plug and drops every stored variable, silently. Nor can it read the cache
instead: hydration keys off `_storedVarNames`, which is in v1's format at that
point, so the values are not in the cache either.

Neither ordering is observable from the outside — both produce a node that
looks right apart from its missing variables — so it is pinned by a
source-order assertion in `TestTheCallbackOrdering`.

**`kAfterReference` deliberately does not sweep.** A referenced node's plugs
are locked, so the rewrite could not be written, and the edit would not belong
to the referencing scene. Reference a v1 scene and it stays v1; import it, or
open and re-save it, to convert.

## What still needs a human

Unchanged from the text importer, and the report now names the concrete fix:
a matrix plug read is a `MatrixView`, so `om.MMatrix(x)` and
`om.MTransformationMatrix(x)` become `x.asMatrix()` and
`x.asTransformationMatrix()`. On `quaternionSpineNode.ma` the conversion is
otherwise complete — 13 inputs, 4 outputs, 1 stored var, 38 rewrites, 6 enums
relabelled — and what remains is that substitution.

## Standing down when v1 owns the node type

The whole on-open design assumes v1's plug-in is **not** loaded. If it is, the
feature must do nothing, and getting that wrong is destructive rather than
merely useless.

Both versions register the node type name `mPyNode`, and whichever plug-in
gets there first wins. v1 wins easily, because every v1 scene contains

```
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
```

which loads v1 **by filename** from the plug-in path — so a v1 install in the
Maya user directory is pulled in by the scene itself, no autoload preference
required. v2's registration then fails (`kFailure` from `mpynode_api2.py`),
and with it every other api2 type, which is the tell:

```
# Error: RuntimeError: ... mpynode_api2.py line 191: (kFailure): Unexpected Internal Failure
# Warning: Unknown object type: mPyLocator
# Warning: Unknown object type: mPyConstraint      ... and four more
```

The nodes in the scene are then **v1 nodes running v1's compute**, and the v2
sweep must not touch them. Rewriting `_inputAttrs` into v2's JSON leaves v1
unable to build its expression locals, and its compute dies with
`NameError: name 'inputCurve' is not defined`. Observed exactly that way: the
scene opened and evaluated correctly, then the Designer was launched — which
imported `mpynode` and installed v2's scene callbacks — and the next open of
the same scene broke the node.

`is_pending` therefore requires `_computeSource` to **EXIST**, not merely to be
empty. That is an exact test, because v1 does not declare `_computeSource`
anywhere in its source tree, so a v1-owned node can never satisfy it. The
original gate could not tell the two cases apart: its `_get` helper returned
`""` for "plug absent" and "plug empty" alike.

`find_foreign` reports the stand-down once per session rather than silently,
because this state is otherwise invisible — v2's plug-in loaded, its node type
did not, and every Designer panel reads an empty node with nothing to say why.

To use v2, move v1 out of the Maya plug-in and script paths
(`plug-ins/mpynode_plugin.py`, `plug-ins/_mpynode`, `scripts/mpylib`) and
restart Maya. Maya will then warn that it cannot find `mpynode_plugin.py` when
opening a v1 scene, which is harmless: v2 already owns the type by then.

This also revises an earlier assessment recorded during scoping, that the
`requires` field mismatch was non-blocking. It is non-blocking **only** when
v1 is not installed.

## The two type mismatches the converter now repairs

Both appear in nearly every non-trivial v1 node, both are invisible until the
node evaluates, and they **hide behind each other** — fixing the first only
reveals the second:

| | v1 | v2 | Error |
|---|---|---|---|
| Matrix plug read | `MMatrix` | `MatrixView` | `MTransformationMatrix : no matching constructor found` |
| `MPoint` → 3-component plug | 4 components, `w` silently dropped | numpy | `could not broadcast input array from shape (4,) into shape (3,)` |

`_ApiTypeFix` in `v1_import.py` fixes both, and because `v1_upgrade.convert`
delegates to `V.convert`, the on-open sweep and `File ▸ Import v1 Node` share
one implementation.

Both rules are driven by the **declared** attribute type from `_inputAttrs` /
`_outputAttrs`, never by inferring what an expression evaluates to, so neither
can fire on something that merely looks like a plug:

* `om.MMatrix(X)` / `om.MTransformationMatrix(X)` — and the bare forms, since
  v1 made those names ambient — become `X.asMatrix()` /
  `X.asTransformationMatrix()` **only** when `X` is `self.<n>` or
  `self.<n>[...]` and `<n>` is declared `matrix`. A helper that returns a real
  `MMatrix` keeps its constructor.
* A write to a `vector` / `color` / `euler` plug is wrapped in a `_v1_vec3`
  shim injected into Init, unless the right-hand side is already a 3-element
  display.

The shim rather than a table of api return types, because the spine wrote
`p0 + t0 * n` — MPoint-valued with nothing on the line to infer it from, and
no table can see through a user helper either.

### Result on the corpus

Nine upstream scenes, through convert-on-open, with v1's `mpylib` importable:

| | before | after |
|---|---|---|
| Evaluate clean | 4 | **5** |

`splineNode` went from *needs hand-finishing* to clean on the auto-fix alone,
and `quaternionSpineNode` converts and runs with **zero** hand edits — 13
inputs, 4 outputs, 1 stored var, 38 rewrites, 1 matrix fix, 3 vector fixes.

The remaining four are all pre-existing categories the converter already
reports and cannot fix: a helper reading a plug as a global (`gameOfLife`),
and v1 api-object arithmetic (`ouch`, `springChain`, `unitSphereCollision`).

### A sharp edge worth knowing

Four of the nine examples do `from mpylib import MVector`. Once v1 is moved
out of the script path — which v2 requires — that import raises
`ModuleNotFoundError`, and because Init is all-or-nothing that takes down
**every** Init name with it. The reported error is then whichever Init name
Compute reaches first, which since this change is usually `_v1_vec3` — a
misleading trail that points at the shim instead of at the dead import. The
converter should drop and report those imports so the failure localises to the
actual use of `MVector`.

**Fixed.** The converter drops any top-level `mpylib` import and reports it.
`import mpylib, math` keeps the `math` half, so an unrelated import is never
collateral damage, and one nested inside a `def` is reported but left alone --
it fails when that function is called rather than during Init, and removing it
could leave an empty function body.

The measurable difference on `gameOfLifeNode`, with v1 absent:

| | before | after |
|---|---|---|
| `set_init_expression` | `False` | **`True`** |
| Compute reports | `NameError: name '_v1_vec3' is not defined` | `NameError: name 'MVector' is not defined` |

The node still does not evaluate -- `MVector` has no v2 equivalent unless you
reach for numpy or `mpynode.api` -- but the error now names the real problem
instead of the importer's own shim, and the report states outright what was
dropped and what to replace it with.
