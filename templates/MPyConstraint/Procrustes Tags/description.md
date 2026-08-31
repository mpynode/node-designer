# Procrustes Rivet (Tags)

A many-rivet `mPyConstraint` where you pick each cluster by NAME rather than by vertex index. Membership comes from geometry component tags authored on the mesh, so the mesh stays the single source of truth -- edit a tag's verts and the rivet follows, with no node data to re-sync.

`clusterTags` is a live multi-string input, one tag name per rivet (`ring0`, `ring1`, ...). Retype an element in the Channel Box or Attribute Editor and that rivet retargets to the newly named tag on the next evaluation. `bindMatrices` is a matrix-array input holding one `(4, 4)` rest offset per rivet, and `outMatrix` is an array with one entry per tag.

**Create + Run demo** builds a twisting tube, 0 -> 540 deg, with four ring tags authored on the mesh (plus a spare `ringAlt` band) and one cube riveted per tag -- scrub and every cube rides the ring named by its tag.

**Run setup** (right-click the node on the Scene tab) rivets transforms you already have: select the mesh and one or more transforms, run setup, and each binds to a NAMED tag -- the one already in its `clusterTags` element if that tag exists on the mesh, otherwise one authored from the K nearest verts at the current pose.
