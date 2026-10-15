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

## See also

- The compiled mesh, curve, surface and transform types create `_timeIn` but
  do not read it: `native/compiler/TRANSPILER.md`, "`_timeIn`: created, not
  read". Accepted for now; revisit when a compiled generator reads time
  through `_timeIn`.
