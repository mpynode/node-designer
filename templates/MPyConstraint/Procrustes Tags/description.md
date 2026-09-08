# Procrustes Rivet (Tags)

A many-rivet `mPyConstraint` where each rivet picks its patch of mesh by NAME instead of by vertex index. Membership comes from component tags authored on the mesh, so the mesh stays the single source of truth -- edit a tag's vertices and the rivet follows, with nothing to re-sync on the node.

Rename a tag in the Channel Box or Attribute Editor and that rivet retargets on the next evaluation.

## Inputs

* `clusterTags` -- one tag name per rivet (`ring0`, `ring1`, ...). Live: retype an element and the rivet moves to the newly named tag.
* `mesh` -- the posed mesh the rivets ride.
* `meshOrig` -- the same mesh at rest, which is what the rest offsets are measured against.
* `bindMatrices` -- one rest offset per rivet. Written by `setup`.

## Outputs

* `outMatrix` -- one matrix per tag, ready to drive a transform. Connect each element to whatever should ride that patch.

## Commands

* `setup` -- rivets transforms you already have. Select the mesh and one or more transforms, then run: each binds to the tag already in its `clusterTags` element if that tag exists, otherwise to one authored from the nearest vertices at the current pose. Offered as **Run setup on selection**.

## Create + Run demo

Builds a tube that twists 0 to 540 degrees, with four ring tags authored on the mesh plus a spare `ringAlt` band, and one cube riveted per tag -- scrub and every cube rides the ring named by its tag.
