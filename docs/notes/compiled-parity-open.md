# Compiled ↔ interpreted parity: what is still open — note

**Status: OPEN, 2026-10-15.** Every parity change follows one rule: the
interpreted node decides, and if it is wrong it is fixed first, then the
compiled node is made to match. This note records what does not match yet, and
why it waits. Read `docs/ARCHITECTURE.md` section 5 first for the stage
lineage.

## Baked image — OPEN, a design is needed

### What the interpreted node does

- The baked image is a **persistent stored variable**, not an attribute. File
  Simple's demo (`_demos/build_templates.py`, `DEMO_FILE_SIMPLE`, ~:4941)
  calls `self.set_variable("embeddedImage", <png bytes>, persistent=True)`, so
  the bytes are pickled into the node's `_storedVarsData` and saved with the
  scene. There is no `embeddedImage` plug to copy.
- `read_texture()` (`_common/methods/file_methods.py`) reads `fileName` first;
  when that does not load, it stages the bytes to a temp file named by their
  md5 and reads that. An explicit path, `read_texture(path)`, never falls back.
- So File Simple and File Scanline fall back, in compute and in the viewport
  (both viewports read `fileName` by explicit path, then retry
  `read_texture()`).
  File Composite does not: `composite_layers` reads every layer by explicit
  path, so a blank layer drops out. Game of Life Texture shows its board, not
  an image, in the viewport.

### What the compiled node does

- The compile path has a fallback (#98), but per **type**, frozen at compile
  time. When the spec being compiled carries the stored variable,
  `extract_spec` / `spec_from_mpn_payload` put its bytes on
  `suggested.embedded_image_b64`, and codegen compiles them into the `.cpp` as
  a byte array (`kernels/file_texture_cpp.make_embedded_stage_cpp`), retried
  through `nd_img_embedded_path()` when `fileName` does not load.
- No shipped spec carries the bytes: no template `.mpn` holds them, the demo
  bakes them into a scene later. No shipped final contains
  `nd_img_embedded_path`.
- A compiled node has no `_storedVarsData`. A node swapped to the shipped
  plug-in therefore loses a scene-baked image: with `fileName` blank or missing
  it shows magenta where the interpreted node shows the baked image.

### Why a splice cannot carry it

3 of the 4 shipped mPyFile finals load their viewport image in code an
optimizer round rewrote, so a fallback hunk has no stage-1 text to land on:

| Type | Viewport image load in `build/<t>/<t>.cpp` | Rewritten by |
|---|---|---|
| `compositeTexture` | `nd_resolve_layers` (~:4795) | `01_resolve_layers_once` |
| `scanlineTex` | `nd_tex_load_linear`, hoisted out of the texel grid (~:5140) | `01_scalar_texel_row_scan` |
| `fileTexture` | `nd_tex_load_linear`, hoisted out of the texel grid (~:5224) | `01_fused_bake_row_pool` |
| `gameOfLifeTex` | none; its one image load (`outSize`, in compute) is stage-1 code | — |

Line numbers are as of 2026-10-15. The compute-side loads were not assessed.

### What the design has to settle

- Where a compiled node keeps per-node bytes, since it has no stored-variable
  store, and how a swap to an already-built plug-in (the shipped finals, the
  All Templates Plugin) carries the interpreted stored variable into it.
  Convert to C++ from a live node already compiles that node's bytes into the
  new type.
- How the fallback reaches the rewritten viewport loads in File Simple and
  File Scanline, which take no splice.
- Whether File Composite gets a fallback at all: its interpreted twin has none.

## Blocking re-entered before an evaluation — KNOWN DIFFERENCE

### The case

Under parallel evaluation only: nodeState leaves Blocking, goes back to
Blocking with nothing evaluated in between, an input changes, and nodeState
leaves Blocking again. The first read through a downstream node then keeps the
old value on the interpreted node. The compiled twin reads the new value.

- Any evaluation between the two state changes avoids it.
- Reads after the next input change are right on both sides.
- DG evaluation does not show it.

### Measured, 2026-10-15

Connected-input nodeState probe: 12 cases over the 6 MPxNode families,
nodeState 1–5, 4 sequences, every input change arriving through a connection.

| Plug-in | DG | Parallel |
|---|---|---|
| All Templates Plugin | 0 of 1080 reads differ | 1 of 1080 |
| De Boor Spline and Procrustes Tags finals | 0 of 540 | 1 of 540 |

The one read is a Procrustes Tags `outMatrix` element read through a
`decomposeMatrix`, at nodeState 2 (Blocking), in the sequence that reaches the
case by undoing and redoing the state changes.

### Why it stays

- The interpreted node is the one that is off, so by the rule above any fix
  belongs there. The compiled node needs nothing.
- Entering a suspended state dirties nothing on the interpreted node
  (`_common/plugs/dirty_affects.declare_user_affects`, whose docstring records
  this case). Dirtying on the way in as well left that same downstream read
  stale after resuming under the Evaluation Manager.
- Marking the plug clean in the suspended compute was tried: 75 of 180 reads
  then differed under parallel evaluation.

## Consumers past an input-driven array length — KNOWN DIFFERENCE, fixed at re-optimization

### The case

Some array outputs take their length from the inputs: DNET's `positions` and
`lengths`, and Spine's `outputTranslate`, `outputRotate`, `outputScale` and
`controlKeys`. With consumers connected past that length, the two nodes write
different elements:

| Side | Writer | Where value k goes |
|---|---|---|
| Interpreted | `_api2/helpers.write_multi_plug_value` | With outgoing connections and fewer values than the highest connected index + 1: the k-th connected element, in index order. Otherwise element k |
| Compiled | `native/compiler/emit_attr._array_write_lines` | Always element k, in a fresh builder sized to the value count. A connected element past the values is dropped and reads 0 |

Example: DNET with 5 matrices, consumers on `positions[0]` and `positions[5]`.
The interpreted `[5]` gets the 2nd value, (0.0166, -0.0193, 0). The compiled
`[5]` reads (0, 0, 0), and its elements stop at `[4]`.

An unconnected read past the length reads 0 on both sides.

### Measured, 2026-10-15

| Probe | Reads that differ |
|---|---|
| Consumers on `[0]` and on the first element past the length; read the consumer, the element, then the consumer after an input change. Finals, DG | **18** of 18 values, 3 on each of the 6 outputs; each output's index list differs too |
| Consumers on `[2]` and `[9]`, or on `[0]` and `[5]`. Finals and All Templates, DG and parallel | DNET 15, Spine 29 (38 values, 6 index lists) at a 1e-6 tolerance, the same in each of the 4 runs of 612 reads. The probe's own 2e-3 relative tolerance counts DNET 14: it misses `lengths[2]`, which holds the 1st value interpreted (1.2806) and the 3rd compiled (1.2819), 0.1% apart |

The same probes also differ in which elements exist past the values, on DNET,
Spine and Procrustes Tags: the compiled writer drops an element it did not
write this evaluation, where the interpreted one keeps it. That is the
short-write divergence documented at `write_multi_plug_value` (T94), not this
case.

### Why it waits

- The interpreted mapping goes into the stage-1 writer,
  `emit_attr._array_write_lines`, first, with a port-cache recipe bump. That
  moves every array writer's text, so the splice has a hunk in each one.
- Where the writers stand in the 6 shipped finals with array outputs:

  | Final | Array writer in `build/<t>/<t>.cpp` |
  |---|---|
  | De Boor Spline, Bubble Sort, Spring Chain | rewritten by an optimizer round. Their length is their own element count, so this case does not arise |
  | DNET | rewritten, both outputs |
  | Spine | `outputWeights` rewritten. The 4 affected outputs are still stage-1 text |
  | Procrustes Tags | stage-1 text |

- DNET: both writers are optimizer code, which a splice never edits. It takes
  the fix at its next re-optimization, from the new stage 1.
- Spine: the 4 affected writers are still stage-1 text, but the splice refuses
  the whole file, because its hunk in the rewritten `outputWeights` writer
  lands in optimizer code. The 4 writers could take the fix by hand, as
  036ce1b inserted the nodeState gate. On 2026-10-15 it was decided to wait
  for Spine's next re-optimization instead, as DNET does.

## See also

- The compiled mesh, curve, surface and transform types create `_timeIn` but
  do not read it: `native/compiler/TRANSPILER.md`, "`_timeIn`: created, not
  read". Accepted for now; revisit when a compiled generator reads time
  through `_timeIn`.
