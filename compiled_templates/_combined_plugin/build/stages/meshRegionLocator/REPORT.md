# meshRegionLocator -- compile report

**Source node:** `meshRegions`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 1 region(s) still marked incomplete |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Draw the bound mesh's component-tag region as a coloured patch. The region
# MEMBERSHIP is resolved LIVE from the input mesh DATA every evaluation (via
# MFnGeometryData), keyed by this gizmo's tag NAME (`regionTag`, baked once by
# setup) -- so editing the component tag (add/remove faces) updates the drawn
# region immediately, and a compiled C++ node resolves the SAME way off its own
# input handle. self.inMesh is the live world-space MFnMesh (worldMesh[0]) used
# for the geometry; the tag membership comes from that same input's data. Falls
# back to a legacy baked `regions` dict for scenes saved before this change.
mesh = self.inMesh
# The region is chosen purely by NAME via the `regionTag` string input. If the
# name matches no component tag on the input mesh, the region goes BLANK (a typo
# or a removed/renamed tag reads as empty). Only when regionTag is unset do we
# honour a legacy baked `regions` dict (scenes saved before regionTag existed /
# the build probe).
_tag = getattr(self, "regionTag", None)
# ONE read of the input data, shared by the tag membership and the source
# transform below (both live on the same MFnGeometryData).
_mdata = mesh_data_from_node_plug(node_name_from_self(self), "inMesh")
_wmat = mesh_matrix_from_mesh_data(_mdata)
regions = None
if _tag:
    _faces = tag_indices_from_mesh_data(_mdata, _tag)
    if _faces:
        regions = {_tag: _faces}
    # else: named tag has no match -> leave regions None -> blank (no fallback).
else:
    _legacy = getattr(self, "regions", None)
    if isinstance(_legacy, dict) and _legacy:
        regions = _legacy
if mesh is None or not regions:
    self.draw = None
else:
    offset = self.offset
    hover_offset = self.hoverOffset
    select_offset = self.selectOffset
    hover_dur = max(self.hoverDur, 1e-3)
    alpha = float(self.alpha)
    # Per-state RGB colours (each a 3-float `color` input) + one shared alpha.
    # The active colour tweens default->hover on the SAME elastic curve as the
    # lift, and snaps to the select colour when selected. Each input carries its
    # own attr DEFAULT, so what is read here is exactly what the user dialled --
    # all-zero means BLACK, not "unset". Nothing is substituted.
    def_c = np.asarray(self.defaultColor, dtype=np.float64).ravel()[:3]
    hov_c = np.asarray(self.hoverColor, dtype=np.float64).ravel()[:3]
    sel_c = np.asarray(self.selectColor, dtype=np.float64).ravel()[:3]
    # The outline around each patch has the SAME three states, on the same
    # curve, so it can read as its own accent rather than a fixed dark edge.
    odef_c = np.asarray(self.outlineColor, dtype=np.float64).ravel()[:3]
    ohov_c = np.asarray(self.outlineHoverColor, dtype=np.float64).ravel()[:3]
    osel_c = np.asarray(self.outlineSelectColor, dtype=np.float64).ravel()[:3]

    hovered = bool(self.hovered)
    selected = bool(self.selected)
    if selected:
        hovered = False          # selected shows only its selected form
    now = float(_wallclock.time())

    h_cur, h_e = tween(now, float(getattr(self, "hv_start", 0.0)),
                       float(getattr(self, "hv_from", 0.0)),
                       float(getattr(self, "hv_to", 0.0)), hover_dur)
    if hovered != bool(getattr(self, "hv_prev", False)):
        self.hv_start = now
        self.hv_from = h_cur
        self.hv_to = 1.0 if hovered else 0.0
        self.hv_prev = hovered
        h_e = 0.0

    # THREE ABSOLUTE normal offsets (world units): the patch floats at `offset`
    # at rest, tweens to `hoverOffset` on hover, and snaps to `selectOffset`
    # when selected. Absolute (not additive) + a fixed normal lift (never an
    # in-plane centroid balloon), so the pop is identical no matter how many
    # faces the tag covers -- a tag grown to span the whole mesh lifts by the
    # same amount as a tiny one.
    lift = offset + (hover_offset - offset) * h_cur
    if selected:
        lift = select_offset
    if lift < MIN_OFFSET:
        lift = MIN_OFFSET

    # Active fill colour: tween default->hover on the hover curve, snap to the
    # select colour when selected; append the shared alpha to make the RGBA row
    # the polygons buffer expects.
    rgb = def_c + (hov_c - def_c) * h_cur
    if selected:
        rgb = sel_c
    rgba = np.concatenate([rgb, [alpha]])

    # The outline rides the SAME hover curve and the same select snap. It stays
    # opaque: `alpha` fades the FILL so the surface shows through, and letting
    # the silhouette fade with it would wash the patch's edge out entirely.
    orgb = odef_c + (ohov_c - odef_c) * h_cur
    if selected:
        orgb = osel_c
    orgba = np.concatenate([orgb, [1.0]])

    # One DrawMesh per tag. `self.draw` takes the LIST straight -- no `sum()`
    # and no `+` chain to build -- and draws them in the order appended. This
    # used to be four parallel accumulator lists plus a hand-rolled
    # `idx + voff` rebase.
    patches = []
    for tag in sorted(regions.keys()):
        faces = np.asarray(regions[tag], dtype=np.int64).ravel()
        if faces.size == 0:
            continue
        pts, idx, cnt, nrm = extract_region(mesh, faces, with_normals=True)
        if pts.shape[0] == 0:
            continue
        # extract_region reads OBJECT space: the mesh DATA carries the source
        # transform as a SEPARATE matrix, and a data-built MFnMesh has no DAG
        # path so getPoints(kWorld) cannot reach world. `world_space=True` below
        # takes these points AS world, so apply that matrix here -- without it
        # the patch draws at the ORIGIN and never follows the mesh. Maya is
        # row-vector (p * M): the 3x3 rotates/scales, row 3 translates.
        if _wmat is not None:
            _m = np.asarray(_wmat, dtype=np.float64).reshape(4, 4)
            pts = pts @ _m[:3, :3] + _m[3, :3]
            nrm = nrm @ _m[:3, :3]
            _mag = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm = nrm / np.where(_mag > 1e-12, _mag, 1.0)
        patches.append(DrawMesh(
            pts + nrm * lift, cnt, idx, color=rgba,
            outline=orgba, outline_width=2.0,
            outline_boundary_only=True,   # clean outer silhouette only
            world_space=True,             # follow the mesh, not the locator
            precise_hover=True))

    if not patches:
        self.draw = None
    else:
        self.draw = patches
        self.auto_highlight = False
        self.auto_refresh = bool(h_e < 1.0)
```

## Unfinished work in the generated C++

* **not translated:** legacy baked `self.regions` dict (pre-regionTag

## Files

```
build/stages/meshRegionLocator/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/meshRegionLocator/2_assisted.cpp       AI filled the unported region(s)
build/source/meshRegionLocator.cpp      SHIPPED
```
