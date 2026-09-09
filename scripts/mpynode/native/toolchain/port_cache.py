"""Content-addressed cache: a node's port "recipe" -> its generated C++ file.

The porter (Claude CLI subprocess) is the only expensive step in the native
compile pipeline (10s-min per node), so its output -- the **full spliced
``.cpp``** (codegen skeleton + AI-filled compute body) -- is cached
content-addressed by a key derived from everything that changes that file. On a
hit the cached ``.cpp`` feeds straight to ``bundler.assemble`` (which recompiles
it namespaced), so a node ported once is reused across plugins *and* sessions.

This module is deliberately **Qt-free, Maya-free, stdlib-only** so the whole
engine stays headlessly testable. It is the per-user cache in the same location
family as ``typeid_registry`` (``~/mpynode/port_cache``).

Design contract (incl. the design-review C1 + C2 fixes):

  * **C1 -- deny-list key, not allow-list.** The key hashes a canonical JSON of
    the spec with only a tiny deny-list of provably-irrelevant keys removed
    (``source_node``, ``schema_version``, ``portability`` at the top level, plus
    the nested ``suggested.type_id`` -- a baked MTypeId that ``bundler`` always
    overrides from the registry). Everything else is
    kept -- crucially the full normalized ``inputs``/``outputs`` meta
    (``default_value``, ``is_array``, ``min_value``, ``max_value``,
    ordered ``enum_names``) and the whole ``variables`` block, because
    ``codegen`` bakes those into the C++ as literals (``codegen._num_default``,
    ``_ik_default``, ``_loc_stored_vars``). An allow-list was exactly what the
    review caught producing stale hits. The resolved ``provider``/``model`` and
    ``PORTER_RECIPE_VERSION`` are folded in too: porter output differs by model
    and by translation-knowledge guidance, so both change the key.

  * **C2 -- atomic writes.** Write ``<hash>.cpp`` then the ``<hash>.json``
    sidecar each via a ``*.tmp-<pid>`` file + ``os.replace`` (atomic on POSIX),
    the ``.cpp`` **first** and the sidecar **last**, and gate a hit on the
    **sidecar existing**. So a port cancelled/crashed mid-write never leaves a
    half-written ``.cpp`` that a later run honors as a valid hit and compiles
    into garbage; a lone ``.cpp`` with no sidecar is a miss. This also makes two
    concurrent writers of the same hash safe (last writer wins, no torn file).

Effect: the key tracks exactly what changes the generated C++. Changing a
default / array-ness / baked var / model / recipe is a clean **miss** -- and so
is **renaming** the node, because the name is baked into the C++ as the
registered type-name string and the C++ class name (``codegen`` emits
``registerNode("<name>", <Class>::id)`` and ``bundler`` reuses that string
verbatim, overriding only the MTypeId). The one name-derived field deliberately
EXCLUDED from the key is the node's MTypeId (``suggested.type_id``):
``bundler.transform_node_cpp`` rewrites every ``MTypeId X::id(0x...)`` from the
global registry, so the baked id never survives into the binary and must not
spuriously split the cache. ``PORTER_RECIPE_VERSION`` is the single knob that
force-invalidates everything after a porter upgrade (bumping
``translation_knowledge`` must bump it).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Optional


# Bump to invalidate ALL cache entries (e.g. after a porter / codegen /
# translation_knowledge change that alters generated C++ for unchanged specs).
# v2: locator mesh-input support + the fail-loud locator input gate landed; a v1
# entry may predate mesh-plug generation and would serve a plug-less node.
# v3: every generated .cpp carries a metadata banner + MFnPlugin vendor/version +
# build-hash (codegen._apply_metadata). The key is spec+recipe, not the .cpp text,
# so a v2 HIT would serve a banner-less node.
# v4: the deterministic lowering path INLINES the full nd_runtime.h into every
# lowered .cpp (codegen._nd_runtime_cpp), and that runtime changed materially
# across SP-4..SP-6 (P1 mask/where/nonzero/gather/stencil; P2 diag/det/einsum/svd;
# batched matmul/broadcast). A v3 HIT would serve a STALE inlined runtime.
# v5: constructs with no deterministic lowering no longer ABORT the compile --
# they are reported as portability["unported"], injected into the porter prompt
# and answered by prompt._UNPORTED_RULE. Same spec, materially different prompt,
# so a v4 HIT would serve a .cpp ported WITHOUT that context.
# v6: the system prompt gained prompt._COMPLEXITY_RULE -- port the named data
# structure, never an asymptotically worse equivalent. Written after a port
# replaced cKDTree(...).query(...) with an O(N*M) scan and passed every gate (it
# compiled, was deterministic, matched exactly -- just 29x slower). Cost is
# invisible to the key, so a v5 HIT would serve the downgraded port forever.
# v7: four constructs that used to reject now lower deterministically -- a guard
# `raise`, `is (not) None`, meshgrid 'ij'/3-input, unique(return_index=True). Both
# halves go stale: a node that reached the PORTER for one now has a deterministic
# .cpp, and nd_runtime.h grew meshgrid3/unique_index (inlined -- see v4).
# v8: every lowered body is spliced inside a boundary handler at its Maya entry
# point (spec_model.lowered_guard). v7 made `raise` lowerable, so a transpiled
# body can leave by exception, and a v7 .cpp has no try/catch anywhere -- a v7 HIT
# would serve an unguarded node.
# v9: closest-point mesh queries are classified (_MESH_QUERY_PATTERNS). Such a
# node now carries suggested.uses_mesh_intersector, so its key moves anyway; the
# bump is for the OTHER half -- the porter prompt gained a portability["unported"]
# entry plus the MESH_CLOSEST_POINT guidance, and the scaffold gained
# <maya/MMeshIntersector.h>. `portability` is deny-listed, so a v8 HIT would serve
# a .cpp ported with neither: with no header it could only fabricate a divergent
# algorithm.
# v10: MESH_CLOSEST_POINT now ORDERS the porter to emit MMeshIntersector when the
# Python did (was 'prefer'), and prompt._COMPLEXITY_RULE gained a Maya API cost
# table. A v9 port made exactly the substitution v10 forbids -- MFnMesh::
# getClosestPoint with its NULL accelerator -- and took 714 s per evaluation while
# passing every gate. Cost is invisible to the key, so a v9 HIT serves that port.
# v11: four independent changes altered generated C++ for UNCHANGED specs, so a
# v10 HIT (which `compile_controller` takes for fully-lowered nodes too, since
# `use_cache = reuse_cache and (ai_assist or not needs_llm)`) would serve a .cpp
# predating all four. (a) nd_runtime.h's matmul2d generic fallback gained a
# 4-row register-blocked pre-pass -- the same INLINED-runtime case as v4 above.
# (b) nd_lower's mesh `.points` channel and mesh `.region(tag)` gather now read
# MFnMesh::getRawPoints instead of getPoints(MPointArray). (c) a lowered
# creates=True command now selects the body's LAST created DAG node (not the
# mPyNode) and restores the prior selection on undo. (d) a LOWERED locator emits
# <maya/MGlobal.h> above the `#ifndef MPYNODE_PROBE` scaffold -- without it the
# probe TU does not compile at all, so a v10 HIT serves an unbuildable probe.
# v12 (T14): emit_attr._array_write_lines flushes an array OUTPUT through a FRESH
# builder sized to the value count -- `MArrayDataBuilder _b(&data, <mem>,
# out_<mem>.size())` -- instead of the datablock's own `_outArr.builder()`, which
# copied every existing element before the loop overwrote it (measured 1.39x at
# N=1000 .. 3.22x at N=100000). Codegen-only, so specs are UNCHANGED and the key
# does not move on its own: 48 cached .cpp in this tree still carry the old
# builder line, and a v11 HIT is a copyfile with codegen SKIPPED
# (compile_controller (c)), so it would serve the pre-change flush forever.
# v13: three more codegen-only changes moved generated C++ for UNCHANGED specs.
# (a) T96 -- emit_attr._array_write_lines now wraps the v12 fresh-builder flush
# in `if (!out_<mem>.empty())`, so an evaluation whose compute assigns nothing
# LEAVES the array alone instead of rewriting it to zero elements. MEASURED: 7
# of the 46 specs embedded in this tree's build manifests emit a different .cpp
# (bubbleSort, mPyDnet, procrustesCluster, spine, spline, springChain, and
# compiled_templates' spline) with byte-identical specs, so the v12 key does not
# move on its own and a v12 HIT would serve the wiping flush.
# (b) T3 -- nd_lower's persistent `self.<x>` state is no longer a function-static
# `std::vector<_NdState>` registry keyed on `this` inside compute() (which was
# never evicted, so a recycled MPxNode address inherited a destroyed node's
# value): node_scaffold now declares `_NdState _ndState` + `std::mutex
# _ndStateMutex` as CLASS MEMBERS and the includes gain <mutex>. Every
# deterministically-lowered node carrying persistent state emits different C++.
# T3 also rewrote translation_knowledge's state guidance for the PORTER (a vector
# of RECORDS with `&s_states.back()` dangles under the parallel EM; it now
# prescribes a vector of POINTERS) -- the classic "bumping translation_knowledge
# must bump it" case from the module docstring above.
# (c) T5 -- a lowered creates=True command REFUSES two createNode shapes the
# recogniser used to accept and mis-lower (a DG type, which MDagModifier rejects
# outright, and a parentless SHAPE, where MDagModifier hands back the
# auto-created transform so the rename/sets land on the wrong object). Such a
# command now keeps its embedded Python payload, i.e. different .cpp for the
# same spec. No shipped template hits this today; a user setup can.
# NOT the reason for this bump, but related: T97 makes a bool `default_value`
# reach the spec at all (wrappers/_mpy_node._record_bool_default), so a node that
# declares one changes its SPEC and moves the key on its own.
# v14: batch 7. MEASURED, not assumed -- every spec embedded in this tree's build
# manifests was regenerated against the pre-batch snapshot and against the current
# tree and the sha256s diffed: 28 of 46 emit a DIFFERENT .cpp for a BYTE-IDENTICAL
# spec, so the v13 key does not move on its own and a v13 HIT (which
# `compile_controller` takes for fully-lowered nodes too) would serve a .cpp
# predating all three changes below.
# (a) T107 -- nd_runtime.h's `concatenate` gained a block-copy fast path (a flat
# source no longer recomputes a multi-index per element; blk==1 strided store /
# blk<16 inline loop / blk>=16 memcpy). Same INLINED-runtime case as v4/v11(a),
# and the widest: isolating it moves 28 of the 46. Byte-identical output --
# pure data movement, no reassociation -- but different .cpp text.
# (b) T106 -- py_to_cpp now DECLINES to emit a fused fast path whose runtime
# guard is unconditionally false, i.e. any block with a trailing-axis
# `nd::newaxis` leaf (newaxis inserts stride 0; c_strides' last entry is always
# 1, so `is_contiguous()` can never hold). 38 unreachable blocks removed;
# isolating it moves 13 of the 46 rows (11 unique nodes: dualQuaternionSkin,
# metaballs, patchRelax, procrustes{Cluster,Single,SingleTag}, rbfWrap,
# rbfWrapDeformer, sineRipple, sineRippleDefault, twistSwingSkin).
# (c) T104 -- translation_knowledge's PERSISTENT_STATE guidance was rewritten
# again: v13's note above narrates the T3 prose ("it now prescribes a vector of
# POINTERS"), and that text no longer exists -- pointers fix the dangle only, the
# registry is UNSYNCHRONISED by construction, and the guide now names the
# per-instance class-member shape the optimizer lifts to. That is the literal
# "bumping translation_knowledge must bump it" case from the module docstring,
# and it changes AI-ported C++ rather than deterministic codegen.
# NOT a reason for this bump, but related, same as T97 above: T102 adds
# `default_value: true` to the animated_selection template's `show_wireframe`,
# which changes that node's SPEC and moves its key on its own.
# v15 (T16(c)): nd_runtime.h's BATCHED matmul arm hoists the row/column index
# arithmetic out of the innermost `l` loop. Same INLINED-runtime case as
# v4/v11(a)/v14(a), and the reason the bump is not optional: 28 LIVE shipped
# build/source/*.cpp (24 distinct nodes, patchRelax among them -- 4 under
# compiled_templates/basics, 24 under compiled_templates/_combined_plugin) embed
# the OLD arm verbatim, so the v14 key does not move on its own and a v14
# HIT -- a `shutil.copyfile` with codegen SKIPPED (compile_controller (c)) --
# would serve the pre-hoist runtime forever. (A tree-wide grep answers 3710 for
# that same pattern, but 3682 of those are frozen copies under _snapshots/ that
# are never rebuilt; 28 is the count that matters.) Output is BYTE-identical,
# not merely within tolerance: ascending `l` and the a*b operand order are
# untouched, and a 20-case differential (patchRelax's (N,3,3)@(N,3,1), 4x4,
# transposed and newaxis stride-0 views, k=1, m=1, n=1, empty batch, broadcast
# and multi-dim batches, nonzero-offset slices, int64, plus a magnitude-spanning
# k=8 accumulation-order canary) dumped from two binaries built from ONE source
# against the pre- and post-edit header compared equal over 620944 bytes at every
# -O0/-O1/-O2/-O3 x -ffp-contract=off/on combination; the same oracle rejects a
# merely reversed (mathematically identical) `l` order at 5931 bytes. An
# independent 17-case re-derivation at integration agreed (23492 bytes, 8/8
# combinations, 794 bytes rejected under the same sabotage).
# MEASURED, N=20000 over a 30-iteration sweep, clang++ -O2 -ffp-contract=off,
# interleaved x9 with ONE SHAPE PER PROCESS: 1.29x min / 1.30x median on
# patchRelax's (N,3,3)@(N,3,1), and 1.21x on (N,4,4)@(N,4,4). Measuring the 4x4
# in the same process AFTER the 3x3 reads only 1.05x -- that figure is a
# thermal-loading artifact of the harness, not a property of the shape.
# The hoisted row/column terms are INTEGER offsets rather than iterators, so a
# k==0 (empty inner dimension) call never forms an out-of-range iterator; and
# the element reads go through iterators, not raw .data() pointers, so the
# T=bool instantiation, which vector<bool> would otherwise fail to compile,
# still builds.
# v16 (2026-08-16): `morph_blend.resolve_weights` became ADDITIVE -- an
# in-between hat and a combo product are now ADDED to the target's own channel
# instead of REPLACING it, so a corrective can be dialled by hand as well as
# driven. That function is the blessed `Transpile` lowering behind
# `self.morphs.resolved` / `morph_weights()` / `morph_apply()` /
# `blend_targets()`, so its body is inlined into every mPyBlendShape TU that
# calls one of them -- but the node SPEC (compute source, attrs, commands) does
# not change by one byte. Without this bump a fully-lowered blendShape takes a
# v15 HIT, which is a `shutil.copyfile` with codegen SKIPPED, and would serve
# the REPLACE arm forever while the interpreted node added. That is the same
# trap the v4 and v15 notes above record; it has now bitten three times.
# v17 (2026-08-17): the geometry read surface gained
# ``self.<mesh>.tag_clusters(self.<multiStringIn>)`` -- a RUNTIME-named component
# tag decode (nd_lower._materialise_geo_tag_clusters) plus the widened header gate
# in node_scaffold._spec_reads_component_tag. Both are codegen, embedded in the
# emitted TU, so a cached port would be served with the old arm (which had no such
# form at all and fell back to the AI porter).
# v18 (2026-08-17): the sanctioned image-FILE read reaches two more emitters and
# stops lying on a third. emit_deformer + emit_iksolver now emit the cached load
# (they declared a cache and never filled it / had no wiring at all), the PORT
# region gains the arm-correct row-order + transfer-function + !_imgOK hints, and
# a sanctioned node with NO path input no longer declares a cache or promises the
# porter a buffer. All of it is codegen inside the emitted TU with no change to
# the node SPEC, so a cached port would be served the old, buffer-less arm.
# Folded into this same bump rather than a second one, because nothing has been
# ported under v18 yet: a deterministically LOWERED body no longer declares the
# cache either, and translation_knowledge stops appending IMAGE_FILE_READ when no
# path input resolves -- a guidance change, which the header above requires bump.
# v19 (2026-08-19): locator draw dirtying + implicit stored vars. Three changes,
# all codegen or guidance, NONE of which move the spec by one byte:
#   * every input attr now calls setAffectsAppearance(true) (numeric / enum /
#     mesh / generic; string + color already did), so an offset/alpha edit
#     redraws the viewport instead of limping on the 30Hz idle poll;
#   * emit_locator._loc_implicit_stored_vars promotes cross-frame tween state
#     written as `self.X = ...` and read as `getattr(self, "X", <literal>)`.
#     spec["variables"] stays {} -- the vars were never DECLARED -- so the key
#     cannot move on its own, yet the emitted TU gains a populated g_tween
#     struct plus the sv_ conduits where it used to emit `char _unused;`;
#   * the STORED VARS paragraph of the porter guide no longer tells the model
#     that stored-var writes are local no-ops. It is that sentence that made
#     the porter fold every read to its seed, pinning the hover blend at 0 and
#     killing hoverOffset / hoverColor / hoverDur outright.
# The guidance change alone requires the bump per this header's own rule, and
# the codegen change is the v4/v15/v16 trap verbatim: a v18 HIT is a
# `shutil.copyfile` with codegen SKIPPED, so it would serve the folded body --
# and the emitter fix could never reach a shipped bundle. Measured blast radius
# of the codegen half: 2 of 43 stage-1 artifacts change (animatedSelection,
# meshRegions); the other 41 are byte-identical.
# Folded into this same bump (nothing outside the four locators has been ported
# under v19, and all four re-port here anyway): RegionMesh gains the mesh
# input's own SOURCE TRANSFORM -- worldMesh[0] DATA carries OBJECT-space points
# plus a separate matrix, and a data-built MFnMesh has no DAG path, so
# getPoints(kWorld) cannot reach world space. The reader now fills
# RegionMesh.matrix off the same MFnGeometryData as the tags, and the PORT
# region advertises mesh_to_world / mesh_dir_to_world / mesh_matrix. Struct
# layout + helpers + guidance, all inside the emitted TU with no spec change --
# a v19 HIT would serve the old struct and keep drawing regions at the origin.
# v20 (2026-08-27): the texture-read path gained an EXACT PNG decoder and the VP2
# bake lost its resolution cap -- both pure codegen, no spec byte moves.
# ``file_texture_cpp.CACHE_CPP`` now leads with a Maya-free ``nd_png_*`` inflate +
# unfilter and tries it BEFORE MImage (MImage premultiplies and quantises to 8
# bits, which is what made a compiled node disagree with the interpreted one on
# 19.84% of a composite); ``file_texture_cpp`` also gained the
# ``nd_tex_composite_layers`` kernel behind the new blessed ``composite_layers``;
# and ``emit_vp2_override`` dropped ``_kMaxBake``, which capped the CPU bake at
# 1024 with no Python analogue and made 26% of a 2048 source's texels wrong.
# This bump is not optional, and the cost of skipping it was measured, not
# theorised: WITHOUT it, `compositeTexture` re-ported only because its spec moved
# (it adopted `composite_layers`), while `fileTexture` and `scanlineTex` -- whose
# specs did not move -- took a v19 HIT, i.e. a `shutil.copyfile` with codegen
# SKIPPED, and shipped in the mega bundle with ZERO nd_png symbols while their own
# `1_transpiled.cpp` carried 31. Same trap as the v4 / v15 / v16 notes above; it
# has now bitten four times, and this is the first time it reached a bundle.
# v21 (2026-08-27): the VP2 bake's STATE-ARRAY branch lost its cap too.
# ``emit_vp2_override`` sized a state-driven bake from ``_ndState.<array>`` and
# then clamped it to 2048, which the interpreted tier does not do -- the same
# different-sized-texture divergence v20 removed from the texload branch, just
# one branch over. Inert on the only node that uses it today (gameOfLifeTex's
# board is 100x100, so the ceiling never binds), but latent for any larger board.
# This needs its OWN bump even though v20 is minutes old, because the VP2
# override is injected into the .cpp and then CACHED with it: compile_controller
# skips injection outright when the served file already contains
# ``MPxShadingNodeOverride`` (compile_controller.py:1043), so a v20 HIT would
# hand back the already-injected copy and the cap would survive forever.
# A VP2-emitter change is therefore exactly as cache-invisible as a codegen one.
# v22 (2026-08-28): the VP2 bake gained a CONTENT-KEY GUARD. ``emit_vp2_override``
# now builds ``texName`` BEFORE the bake and asks ``MTextureManager::findTexture``
# first, skipping the whole synthesis on a hit. Maya calls updateShader on every
# viewport refresh, so a node nothing drives was still paying for it: measured on
# bugs/mpyfile_debug.ma, a STATIC 1024x1024 fileTexture -- no time input at all --
# ran at 46 fps, 21.7 ms/frame, spent re-running 1,048,576 nd_texel calls and a
# 16 MB float allocation to rebuild pixels that had not changed. gameOfLifeTex
# (470 fps) is deliberately NOT guarded: its key folds in a hash of the baked
# pixels, so the key cannot be computed until the bake has already run.
# Same cache-invisibility as v21 -- injection is skipped when the served file
# already contains ``MPxShadingNodeOverride`` (compile_controller.py:1043) -- so
# without this bump every mPyFile node would take a v21 HIT and keep the old
# unguarded override forever.
# v23 (2026-08-28): the VP2 bake is now ROW-PARALLEL, and a stateful bake hoists
# its state lock out of the per-texel path. v22's guard only helps a node whose
# content key is stable; the two that must genuinely re-bake every frame were
# left paying the full serial cost -- measured on bugs/mpyfile_debug.ma,
# scanlineTex (``frame`` is in its key) and a 1024x1024 gameOfLifeTex (a state
# key cannot exist before the bake) both ran under 30 fps, ~33 ms/frame.
# ``emit_vp2_override`` now partitions ROWS across
# ``min(hardware_concurrency, 12)`` workers writing disjoint slices of ``baked``,
# with no accumulation or reduction, so the buffer is bit-identical to the serial
# one at any thread count; each worker catches into a ``std::atomic<bool>``
# because an exception leaving a std::thread calls std::terminate.
# Separately, a STATE node's ``nd_texel`` carries the ported body's own
# ``lock_guard(_ndStateMutex)`` -- 1,048,576 acquisitions of a SHARED mutex per
# frame, and an absolute barrier to threading. The real mutex is now taken ONCE
# around the dispatch and each worker is handed a local one; the prime call
# settles the frame transition beforehand and ``nd_tex_write`` is independently
# serialised, so the workers perform no state transition at all.
# Cache-invisible for the third bump running -- injection is skipped when the
# served file already contains ``MPxShadingNodeOverride``
# (compile_controller.py:1043) -- so without this every mPyFile node would take a
# v22 HIT and keep the serial override forever.
# v24 (2026-08-28): ``nd_tex_sample`` gained an EXACT-TEXEL fast path. v23 made
# the bake row-parallel, which took scanlineTex 30 -> 100 fps, but the
# INTERPRETED tier runs the same node at 150 -- so the compiled node was still a
# regression to a user. The reason is structural and was measured, not guessed:
# the template's own ``viewport_source`` does the work per FRAME and per ROW
# (one ``read_texture()``, ``h`` sins via broadcast, an in-place row-scaled
# multiply) while the compiled bake re-derives all of it per texel.
# Two of those three turned out not to be worth chasing: clang -O3 ALREADY
# hoists the row-invariant sin to the row loop (verified in the emitted assembly
# -- ``bl _sin`` sits at Depth=1, the texel loop is Depth=2), and a pointer
# fast-path for the ``nd_tex_load_linear`` memo is UNSAFE, because compute()
# passes a stack-local MString whose buffer address is reused across calls, so
# pointer identity there would serve the wrong image.
# What was left is the sampler: on the corner grid the bilinear weights collapse
# (tx == 0 for 100% of texels, ty == 0 for ~58% of rows) and three quarters of
# the blend is multiplication by zero, including two loads a full row away.
# Short-circuiting it measured 2.02x on a 1024x1024 bake with ZERO bit-differing
# floats out of 4,194,304 -- arithmetic identity, so the interpreted tier needs
# no mirror change and parity is preserved by construction.
# Codegen, so unlike v23 this moves the emitted TU directly -- but it needs the
# bump for the SAME reason regardless: a v23 hit is a copyfile with codegen
# skipped (compile_controller.py:1043), and every mPyFile node would keep the
# old sampler forever.
# v25: compiled mPyBlendShape gained CONSTRUCTION HISTORY. The deform now reads
# its CONNECTED target meshes, diffs them against originalGeometry (resolved BY
# NAME -- 2026 exposes MPxGeometryFilter::originalGeometry as a static, 2024 does
# not) and hands the result to the blessed delta kernels as a live CSR, so
# sculpting a target reaches a compiled node as you drag instead of only after a
# re-bake. Same bump reason as v24: this is CODEGEN, and a v24 hit is a copyfile
# with codegen skipped (compile_controller.py:1043), so every compiled
# blendShape would keep the baked-only deform forever.
# v26: MatrixView methods now LOWER instead of falling to the AI porter.
# A matrix input arrives as a MatrixView carrying the whole MMatrix +
# MTransformationMatrix surface; py_to_cpp previously knew exactly one of its
# 42 methods (.asNumpy(), an identity passthrough) so anything else -- rotation,
# scale, shear, rotationOrder, translation, det -- forced a PORT region. Fifteen
# now lower: the pure-nd ones through existing kernels, the ten needing Maya
# semantics through a new ndx:: bridge (kernels/nd_maya_cpp.py) that CALLS Maya
# rather than re-deriving its decompositions, so the compiled node matches the
# interpreted one exactly instead of to a tolerance. nd::det also gained a 4x4
# arm. Same bump reason as v24 and v25: this is CODEGEN, and a v25 hit is a
# copyfile with codegen skipped (compile_controller.py:1043), so every affected
# node would keep its AI-ported compute forever.
# Design note: docs/notes/matrixview-lowering.md
# v27: a LOWERED deform reads its positions off the output mesh's raw float
# store (MFnMesh::getRawPoints, full-membership mesh only), writes the narrowed
# result back into that store and refreshes the surface, instead of the
# MPointArray allPositions/setAllPositions round trip -- bit-identical (the same
# float<->double casts), and the single most frequent thing the AI optimizer had
# been doing by hand (8 of 50 accepted shipped rounds). Measured on sineRipple
# at 160k vertices: 23.3 -> 20.9 ms; MFnMesh::setPoints and setAllPositions as
# the write did not pay. NURBS and partial-membership deforms keep the
# MPointArray path. Same bump reason as v24-v26: this is CODEGEN, and a v26 hit
# is a copyfile with codegen skipped (compile_controller.py:1043), so every
# compiled deformer would keep the MPointArray round trip forever.
PORTER_RECIPE_VERSION = "27"

# Spec keys excluded from the cache key -- provably irrelevant to the generated
# C++. A deny-list, NOT an allow-list (design C1).
#   * source_node -- scene node name; unstable, reaches the C++ only as a comment.
#   * schema_version -- spec_extractor schema rev; advisory, not baked.
#   * portability -- derived. ``unported`` DOES reach the porter prompt, but it is
#     a pure function of compute/init/inputs/outputs/variables, all of which ARE
#     in the key, so it cannot vary independently. Changes to its PHRASING are
#     covered by PORTER_RECIPE_VERSION above.
_DENY_LIST = ("source_node", "schema_version", "portability")

# Nested (parent, child) spec paths excluded from the key. ``suggested.type_id``
# is baked into the .cpp as a literal but ``bundler.transform_node_cpp`` ALWAYS
# rewrites it from the global registry -- it never survives into the binary, so
# two specs identical but for type_id must share one entry. We do NOT drop
# ``suggested.node_type_name`` / ``class_name``: those ARE baked into the
# registered type-name and C++ class, so a rename is correctly a MISS (dropping
# them would let two different-named, same-compute nodes collide on one cached
# .cpp registered under the wrong name). ``metadata.type_id`` is the USER's pin
# for the same value, rewritten by the same pass, so it is denied too -- which
# also keeps the key byte-identical for nodes predating the field.
_DENY_NESTED = (("suggested", "type_id"), ("metadata", "type_id"))

# ``commands`` is baked into the generated .cpp on EVERY base: each @maya_command
# compiles to an MPxCommand inside the node's OWN bundle. Dropping it from the key
# (correct while commands lived in a companion plug-in) served a stale .cpp whose
# command classes were absent, so the node registered no commands at all --
# silently, because the build still succeeded. So it is ALWAYS part of the key.
#
# ``methods`` only reaches the .cpp through the command dispatcher's embedded
# module, so it is keyed ONLY when the spec HAS commands -- a command-less spec
# keeps its old key byte-identical and never re-ports on a setup/demo-only edit.
_METHODS_KEY = "methods"


def cache_dir() -> str:
    """Return the per-user port-cache directory (``MPYNODE_PORT_CACHE``, else
    ``[paths] port_cache``, else under the home -- resolved by
    ``_common.home``). Created on demand."""
    from mpynode._common import home
    d = home.port_cache_dir()
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    return d


def _canonical_spec(spec: dict) -> dict:
    """Copy ``spec`` with the deny-listed keys removed (top-level ``_DENY_LIST``
    plus the nested ``_DENY_NESTED`` paths). Copies only the sub-dicts it has to
    mutate, so the caller's spec is never modified -- the engine reuses the spec
    after keying it (it goes into the manifest and on to the porter). json.dumps
    then walks the rest deterministically (sort_keys handles dict ordering; list
    order is preserved as-is)."""
    out = {k: v for k, v in (spec or {}).items() if k not in _DENY_LIST}
    # ``methods`` only reaches the .cpp via the commands (see _METHODS_KEY), so
    # key on it only when there ARE commands. ``commands`` itself is always kept.
    if not (out.get("commands") or []):
        out.pop(_METHODS_KEY, None)
    for parent, child in _DENY_NESTED:
        sub = out.get(parent)
        if isinstance(sub, dict) and child in sub:
            sub = dict(sub)  # copy before popping -- don't mutate caller's spec
            sub.pop(child, None)
            # Popping the only meaningful entry must leave NO trace. A node
            # whose sole metadata is a pinned ``type_id`` produces a
            # byte-identical banner, but keeping the emptied husk in the payload
            # moves the hash -- so merely pinning an id would force a full LLM
            # re-port for nothing. ``suggested`` never trips this: its remaining
            # names are non-empty.
            out[parent] = sub
            if not any(sub.values()):
                out.pop(parent, None)
    return out


def cache_key(spec: dict, *, provider: str, model: str) -> str:
    """SHA-256 hex over the CANONICAL JSON of the cache payload.

    Payload = ``{"spec": <spec minus deny-list>, "provider": provider,
    "model": model, "recipe": PORTER_RECIPE_VERSION}``.

    Canonicalized with ``json.dumps(payload, sort_keys=True,
    separators=(",", ":"), default=str)`` so dict ordering can't spuriously
    change the hash, while **list order is preserved** (enum_names, array
    indices). Non-JSON-able values are coerced via ``default=str``.
    """
    payload = {
        "spec": _canonical_spec(spec),
        "provider": provider,
        "model": model,
        "recipe": PORTER_RECIPE_VERSION,
    }
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cpp_path(key: str) -> str:
    return os.path.join(cache_dir(), "%s.cpp" % key)


def _sidecar_path(key: str) -> str:
    return os.path.join(cache_dir(), "%s.json" % key)


def _complete(key: str) -> bool:
    """A cache entry is COMPLETE only when BOTH the ``.cpp`` and its sidecar
    exist. The sidecar is written last (atomically), so gating on it means a
    lone/half-written ``.cpp`` is treated as a miss (design C2)."""
    return os.path.isfile(_cpp_path(key)) and os.path.isfile(_sidecar_path(key))


def get_path(key: str) -> Optional[str]:
    """Path to the cached ``.cpp`` if a COMPLETE entry exists, else ``None``."""
    return _cpp_path(key) if _complete(key) else None


def get(key: str) -> Optional[str]:
    """The cached ``.cpp`` TEXT if a COMPLETE entry exists, else ``None``."""
    if not _complete(key):
        return None
    try:
        with open(_cpp_path(key), "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        # Raced with a clear()/eviction between the check and the read.
        return None


def _atomic_write(path: str, text: str) -> None:
    """Write ``text`` to ``path`` via a per-pid tmp file + ``os.replace``
    (atomic on POSIX). Mirrors ``typeid_registry._save``."""
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)  # atomic on POSIX


def put(key: str, cpp_text: str, *, meta: dict) -> str:
    """Store ``cpp_text`` under ``key`` atomically and return the ``.cpp`` path.

    Writes the ``.cpp`` FIRST then the sidecar LAST, each via tmp + os.replace
    (design C2), so a crash mid-``put`` never leaves a hit-able ``.cpp`` without
    its sidecar. The sidecar records ``meta`` plus a write timestamp and the
    recipe version (so a human / future eviction can reason about staleness).
    """
    cdir = cache_dir()  # ensure the dir exists
    cpp_p = os.path.join(cdir, "%s.cpp" % key)
    side_p = os.path.join(cdir, "%s.json" % key)

    # .cpp first.
    _atomic_write(cpp_p, cpp_text)

    # Sidecar last -- this is the bit that flips the entry "complete".
    sidecar = dict(meta or {})
    sidecar.setdefault("key", key)
    sidecar.setdefault("porter_recipe_version", PORTER_RECIPE_VERSION)
    sidecar.setdefault("created", time.time())
    _atomic_write(
        side_p,
        json.dumps(sidecar, sort_keys=True, indent=2, default=str) + "\n",
    )
    return cpp_p


def clear() -> int:
    """Remove all cache entries (``.cpp`` + ``.json`` + any stray ``.tmp-*``)
    and return the number of files removed."""
    d = cache_dir()
    removed = 0
    for name in os.listdir(d):
        if name.endswith(".cpp") or name.endswith(".json") or ".tmp-" in name:
            try:
                os.remove(os.path.join(d, name))
                removed += 1
            except OSError:
                pass
    return removed
