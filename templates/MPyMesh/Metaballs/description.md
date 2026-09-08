# Metaballs

An `mPyMesh` that builds one solid out of simple shapes -- spheres, boxes and cylinders -- and extracts a single watertight quad mesh from it. Shapes merge, blend or cut into each other, and because it is all one field, dragging any shape re-solves the whole mesh live.

Add shapes with the commands below. Each spawns a transform, and that transform places the shape. Order matters: every shape combines with everything added before it, and two attributes decide how.

* `additive` **on**, `smoothing` **0** -- hard union, a crisp merge.
* `additive` **on**, `smoothing` **above 0** -- smooth union, the metaball blend the template is named for. Bigger `smoothing`, softer fillet.
* `additive` **off** -- difference. The shape is carved out of the solid built so far.

## Inputs

* `shapeMatrix` -- one entry per shape, placing it. Driven by the transform each Add command creates.
* `shapeType` -- which primitive that entry is. Set for you by the Add commands.
* `additive` -- whether this shape adds to the solid or is subtracted from it.
* `smoothing` -- how soft the join is where this shape meets the rest. 0 gives a crisp seam.
* `radius` -- size, for spheres and cylinders.
* `height` / `axis` -- length and orientation, for cylinders.
* `halfExtents` -- box size, measured out from its centre.
* `resolution` -- how finely the surface is sampled. Higher is smoother and slower.
* `isoValue` -- pushes the surface out or in. Positive fattens, negative shrinks.

## Outputs

* The generated quad mesh -- watertight, and rebuilt whenever any shape moves or any attribute changes.

## Commands

* `addSphere` -- adds a sphere, plus a transform to position it.
* `addBox` -- adds a box, plus a transform to position it.
* `addCylinder` -- adds a cylinder, plus a transform to position it.
* `setup` -- makes the node live. Offered as **Run setup on selection**, and also what the Create command runs.

## Create + Run demo

Builds the word **MPyNode** as one mesh, plus a cube / sphere / cylinder blob below it so all three operations are on screen at once. Move the `metaSphere` or `metaCylinder` transforms to watch the blend and the tunnel update.
