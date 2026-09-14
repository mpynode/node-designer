MPyNode compiled plugin: mPyMega
================================

This 'build/' folder holds everything the compiler produced EXCEPT the
plugin itself: the C++ source (under source/) plus the scripts to rebuild
it. The importable plugin lives ONE LEVEL UP, beside this folder, so you
(or an AI agent) can read/tweak the source here and recompile in place.

What you'll see
---------------
  ../mPyMega.mll   <- the plugin you load into Maya (one level up).
  ../<type>_commands.py   <- companion command plugin(s), if any (also
                             one level up, beside the bundle).
  source/       <- the C++ source for every node that LINKED.
  build.sh, build.bat   <- rebuild scripts (see Rebuild below).
  README.txt    <- this file.
  manifest.json <- build receipt: every node, its id, and -- for any that
                   dropped -- the reason.
  <node>/       <- ONLY appears when a node FAILED (see 'Failed nodes'
                   below); a clean, all-linked build has none.

Source (in source/)
-------------------
  source/mPyDnet.cpp
  source/comboCorrectives.cpp
  source/procrustesTags.cpp
  source/nurbsWave.cpp
  source/patchRelax.cpp
  source/rbfWrapDeformer.cpp
  source/sineRipple.cpp
  source/unitSphereCollision.cpp
  source/compositeTexture.cpp
  source/scanlineTex.cpp
  source/fileTexture.cpp
  source/gameOfLifeTex.cpp
  source/twoBoneIK.cpp
  source/animatedSelection.cpp
  source/animatedText.cpp
  source/meshRegionLocator.cpp
  source/widgetShowcase.cpp
  source/diskMeshCache.cpp
  source/gameOfLifeMesh.cpp
  source/jsonMeshReader.cpp
  source/meshMaze.cpp
  source/metaballs.cpp
  source/uvLayoutMesh.cpp
  source/voxelizeMesh.cpp
  source/bubbleSort.cpp
  source/hexAttribute.cpp
  source/ouch.cpp
  source/spine.cpp
  source/spline.cpp
  source/springChain.cpp
  source/helixCurve.cpp
  source/rippleSurf.cpp
  source/dualQuaternionSkin.cpp
  source/linearBlendSkin.cpp
  source/twistSwingSkin.cpp
  source/aimTransform.cpp
  source/plugin_main.cpp   <- registers every node above.
  source/shared_helpers.cpp (if present) <- helpers shared across nodes.

Rebuild
-------
  macOS / Linux:  ./build.sh
  Windows:        build.bat   (any cmd.exe -- it locates MSVC via vswhere)

Both scripts read $MAYA / %MAYA% for the Maya install (defaulting to the
standard location). The rebuilt plugin is written to the PARENT folder
(one level up from here) as:
  ../mPyMega.mll

Failed nodes leave breadcrumbs
------------------------------
  In a multi-node build, a node that FAILS to port or compile is DROPPED
  from the bundle (the others still link) and leaves a folder here so you
  can see WHY:
    <node>/<node>.cpp     the generated C++ that would not compile, and/or
    <node>/compile.log    the port / compile transcript.
  A node rejected earlier, at the portability gate, never got that far, so
  it leaves NO folder -- only a reason in manifest.json. Nodes that built
  successfully leave no folder either, so ANY <node>/ folder in here marks
  a failure worth investigating (the one-line reason is in manifest.json).

Notes
-----
  * MTypeId values come from your per-user id registry and are already
    baked into the source -- do not hand-edit them (two plugins could
    otherwise collide).
  * To load in Maya: loadPlugin this bundle (.bundle on macOS, .mll on
    Windows).
