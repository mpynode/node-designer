# Metaballs

An `mPyMesh` that builds one solid out of simple SDF shapes -- spheres, boxes and cylinders -- and extracts one watertight quad mesh into `outMesh` by **dual marching cubes**. Shapes merge, blend or cut into each other. It is all one field, so dragging any shape re-solves the whole mesh live.

Add shapes with the `addSphere` / `addBox` / `addCylinder` commands on the Methods tab. Each spawns a transform, and that transform's `shapeMatrix` places the shape.

Order matters: every shape combines with everything added before it, and two flags decide how.

* `additive` **on**, `smoothing` **0** -> **hard union**, a crisp merge.
* `additive` **on**, `smoothing` **> 0** -> **smooth union**, the metaball blend the template is named for. Bigger `smoothing` = softer fillet.
* `additive` **off** -> **difference**. The shape is carved OUT of the solid so far.

`resolution` sets how finely the surface is sampled (higher = smoother and slower); `isoValue` pushes the surface out or in -- positive fattens, negative shrinks.

**Create + Run demo** builds the word **MPyNode** as one mesh, plus a Cube / Sphere / Cylinder blob below it so all three operations are on screen at once. Move the `metaSphere` or `metaCylinder` transforms to watch the blend and the tunnel update.
