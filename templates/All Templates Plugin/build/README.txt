MPyNode compiled plugin: mPyMega
================================

This 'build/' folder holds everything the compiler produced EXCEPT the
plugin itself: the C++ source (under source/) plus the scripts to rebuild
it. The importable plugin lives ONE LEVEL UP, in a folder named after the
Maya version it was built for (../2026/), so you (or an AI agent) can
read/tweak the source here and recompile in place.

What you'll see
---------------
  ../<year>/mPyMega.mll   <- the plugin you load into Maya (one level up, in
                   the folder named after its Maya version: ../2026/).
  ../<type>_commands.py   <- companion command plugin(s), if any (also
                             one level up, beside this build/ folder).
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
  source/circularText.cpp
  source/plugin_main.cpp   <- registers every node above.
  source/shared_helpers.cpp (if present) <- helpers shared across nodes.

Rebuild
-------
  macOS / Linux:  ./build.sh
  Windows:        build.bat   (any cmd.exe -- it locates MSVC via vswhere)

Both take an optional Maya version (./build.sh 2026, build.bat 2026);
without one they use $MAYA / %MAYA%, else the newest installed Maya with
a devkit. The rebuilt plugin is written one level up from here, into a
folder named after the Maya version it was built against:
  ../<year>/mPyMega.mll      e.g. ../2026/mPyMega.mll
The year comes from the install's folder name (Maya2026), else from its
devkit's MAYA_API_VERSION. A build folder that already sits inside its
version folder (a multi-version compile's <out>/2026/build/) writes the
plugin beside itself instead.

The version is never part of the file name: Maya records the plugin's
file name in every scene that uses it, so a versioned name would tie each
scene to one Maya release. An older copy left one level up by an earlier
build (../mPyMega.mll) is never deleted; the scripts say when one is
there, because Maya loads whichever copy comes first on its plug-in path.

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
