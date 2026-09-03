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
