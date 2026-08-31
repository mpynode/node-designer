"""Mpynode._common — pure-Python helpers usable by either API plugin.

Nothing in this package may import maya.OpenMaya / maya.OpenMayaMPx /
maya.api.OpenMaya at module-import time. Modules here are exercised by
unit tests with no Maya plugin loaded.
"""

from mpynode._common.util import recipes
from mpynode._common.util.recipes import HydrationRecipe

# mPyNode has nothing to declare -- ALL its inputs/outputs are user-added via
# the wrapper API, so they live in _inputAttrs / _outputAttrs JSON, not here.
recipes.register_recipe(HydrationRecipe(native_type="mPyNode"))

from mpynode._common.util.recipes import HydrationInputEntry, HydrationOutputEntry

# mPyIkSolver. Only _solverContextSnapshot is a real plug; everything else is
# SYNTHETIC, filled by compute_ik_doSolve from the connected IK handle.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyIkSolver",
        inputs=[
            HydrationInputEntry(
                name="joints",
                source_plug="",  # SYNTHETIC
                kind="joint_chain",
                arity="list_of_dict",
                children={
                    "name": "str",
                    "world_position": "vector",
                    "rotation": "vector",
                    "matrix": "matrix",
                    "world_matrix": "matrix",
                },
                description=(
                    "Joint chain walked from the IK handle's start joint "
                    "down to (but not including) the effector. 'matrix' is the "
                    "local (parent-relative) frame, 'world_matrix' the rest "
                    "world frame (both incl. bind offset). Synthetic \u2014 "
                    "populated by the bridge from MFnIkHandle."
                ),
            ),
            HydrationInputEntry(
                name="end_effector",
                source_plug="",  # SYNTHETIC
                kind="vector",
                description=(
                    "World-space position of the IK HANDLE (the user's "
                    "puppet string). Synthetic \u2014 populated by the bridge."
                ),
            ),
            HydrationInputEntry(
                name="pole_vector",
                source_plug="",  # SYNTHETIC
                kind="vector",
                description=(
                    "Pole vector from the IK handle. Synthetic \u2014 populated "
                    "by the bridge from handle.poleVector."
                ),
            ),
            HydrationInputEntry(
                name="twist",
                source_plug="",  # SYNTHETIC
                kind="float",
                description=(
                    "Twist value from the IK handle. Synthetic \u2014 populated "
                    "by the bridge from handle.twist."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="local_matrices",
                target_plug="",  # SYNTHETIC
                kind="matrix",
                arity="list",
                shape_from_input="joints",
                mode="compute",
                description=(
                    "Per-joint list (one slot per joint, all None by default) of "
                    "desired LOCAL (parent-relative) 4x4 matrices. Assign a slot "
                    "to drive that joint via offsetParentMatrix (rotate/translate/"
                    "scale gated), leaving its own channels + jointOrient "
                    "untouched. Synthetic \u2014 not a real plug."
                ),
            ),
            HydrationOutputEntry(
                name="world_matrices",
                target_plug="",  # SYNTHETIC
                kind="matrix",
                arity="list",
                shape_from_input="joints",
                mode="compute",
                description=(
                    "Per-joint list (one slot per joint, all None by default) of "
                    "desired WORLD (absolute) 4x4 matrices. Same application as "
                    "local_matrices; per-joint dispatch is WORLD > LOCAL > rest. "
                    "Synthetic \u2014 not a real plug."
                ),
            ),
            HydrationOutputEntry(
                name="apply_rotate",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=("Gate: take rotation from the matrix (default True). "
                             "Scalar broadcasts; a per-joint list gates each joint."),
            ),
            HydrationOutputEntry(
                name="apply_translate",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=("Gate: take translate from the matrix (default False). "
                             "Scalar broadcasts; a per-joint list gates each joint."),
            ),
            HydrationOutputEntry(
                name="apply_scale",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=("Gate: take scale from the matrix (default False). "
                             "Scalar broadcasts; a per-joint list gates each joint."),
            ),
        ],
    )
)

# mPyConstraint. Preset INPUT plugs are all real (added in the initializer).
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyConstraint",
        inputs=[
            HydrationInputEntry(
                name="targetTranslate",
                source_plug="targetTranslate",
                kind="vector",
                description="World-space target position to constrain to.",
            ),
            HydrationInputEntry(
                name="targetRotate",
                source_plug="targetRotate",
                kind="vector",
                description="World-space target rotation (Euler XYZ degrees).",
            ),
            HydrationInputEntry(
                name="targetWeight",
                source_plug="targetWeight",
                kind="float",
                description="Constraint weight, 0\u20131. Multiply your output by this.",
            ),
            HydrationInputEntry(
                name="restTranslate",
                source_plug="restTranslate",
                kind="vector",
                description="Rest-pose translate; output when targetWeight is 0.",
            ),
            HydrationInputEntry(
                name="restRotate",
                source_plug="restRotate",
                kind="vector",
                description="Rest-pose rotate; output when targetWeight is 0.",
            ),
        ],
    )
)

recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyLocator",
        inputs=[
            HydrationInputEntry(
                name="localPosition",
                source_plug="localPosition",
                kind="vector",
                description="Local-space position offset of the locator.",
            ),
            HydrationInputEntry(
                name="localScale",
                source_plug="localScale",
                kind="vector",
                description="Local-space scale of the locator.",
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="draw",
                target_plug="",  # SYNTHETIC -- not a real plug
                kind="draw",
                arity="object",
                mode="compute",
                description=(
                    "The whole drawing, in DRAW ORDER: one DrawItem, several "
                    "composed with '+', or a (possibly nested) list of them. "
                    "DrawCurve / DrawLines / DrawPoints / DrawMesh / "
                    "DrawSphere / DrawBox / DrawCone / DrawCylinder / "
                    "DrawCircle / DrawText, from "
                    "mpynode._common.draw.draw_types. None = draw nothing."
                ),
            ),
        ],
    )
)

# mPyDeformer. Real inputs: envelope + input[].inputGeometry. Real output:
# outputGeometry[]. NO synthetics -- the whole surface is the plug tree, same as
# mPySkinCluster / mPyBlendShape. The 5 internal-vars schema (points / normals /
# weights / deformed, filled by the bridge) was DELETED; see the migration note
# in _api1.mpy_deformer. Verified on a live node: self.points / self.normals /
# self.deformed raise AttributeError. As on mPySkinCluster, the inherited
# weightList[*].weights[*] paint weights stay reachable through the plug tree
# without being a curated entry here.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyDeformer",
        inputs=[
            HydrationInputEntry(
                name="envelope",
                source_plug="envelope",
                kind="float",
                description=(
                    "Deformer envelope, 0.0 = no effect, 1.0 = full. "
                    "Inherited from MPxDeformerNode / geometryFilter."
                ),
            ),
            HydrationInputEntry(
                name="inputGeometry",
                source_plug="input.inputGeometry",
                kind="geometry",
                description=(
                    "Multi -- the upstream geometry, READ-ONLY, reached as "
                    "self.input[i].inputGeometry. An MFnMesh / MFnNurbsCurve / "
                    "MFnNurbsSurface function set matching the incoming type."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="outputGeometry",
                target_plug="outputGeometry",
                kind="geometry",
                mode="compute",
                description=(
                    "Multi -- the deformed geometry, reached as "
                    "self.outputGeometry[i]. A WRITABLE handle eager-copied "
                    "from the matching input, so an empty expression is a "
                    "no-op; mutate it (setPoints / setCVPositions / any other "
                    "function-set method) and the bridge commits on compute "
                    "exit."
                ),
            ),
        ],
    )
)

# mPyTransform -- GATED LOCAL-MATRIX contract, mirroring mPyIkSolver as a single
# joint with an identity bind offset. Five curated per-channel READS (translate /
# rotate [RADIANS] / scale / shear / rotate_order = this node's own live
# channels); read external drivers by adding matrix INPUT attrs. The four
# synthetic WRITE slots publish a desired LOCAL matrix + per-channel gates and
# the bridge authors opm = inv(L) @ D onto offsetParentMatrix (flush-free). All
# default to a no-op, so a vanilla node is a plain Maya transform. WORLD
# placement is opt-in and cycle-free: read a CONNECTED parent-world matrix and
# set local_matrix = worldDesired @ inv(parentWorld). Never reads its DAG parent.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyTransform",
        inputs=[
            HydrationInputEntry(
                name="translate", source_plug="translate", kind="vector",
                description=(
                    "This node's own live translate channel as a (3,) numpy "
                    "(tx, ty, tz). READ; a change re-evaluates the node."
                ),
            ),
            HydrationInputEntry(
                name="rotate", source_plug="rotate", kind="vector",
                description=(
                    "This node's own live rotate channel as a (3,) numpy in "
                    "RADIANS (rx, ry, rz). READ; a change re-evaluates the node."
                ),
            ),
            HydrationInputEntry(
                name="scale", source_plug="scale", kind="vector",
                description=(
                    "This node's own live scale channel as a (3,) numpy "
                    "(sx, sy, sz). READ; a change re-evaluates the node."
                ),
            ),
            HydrationInputEntry(
                name="shear", source_plug="shear", kind="vector",
                description=(
                    "This node's own live shear channel as a (3,) numpy "
                    "(shearXY, shearXZ, shearYZ). READ; a change re-evaluates."
                ),
            ),
            HydrationInputEntry(
                name="rotate_order", source_plug="rotateOrder", kind="enum",
                description=(
                    "This node's own rotate-order enum as an int 0..5 "
                    "(0 == xyz, matching the .rotateOrder plug). READ; a change "
                    "re-evaluates the node."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="local_matrix",
                target_plug="",  # SYNTHETIC
                kind="matrix",
                mode="compute",
                description=(
                    "Desired LOCAL (parent-relative) (4, 4) matrix, or None "
                    "(default). Applied via offsetParentMatrix when at least "
                    "one apply_* gate is open. For WORLD placement set it to "
                    "worldDesired @ inv(parentWorld), reading the parent from a "
                    "connected matrix input. Synthetic."
                ),
            ),
            HydrationOutputEntry(
                name="apply_rotate",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=(
                    "Gate (default True): take rotation from the matrix; "
                    "else keep the live TRS rotation. Synthetic."
                ),
            ),
            HydrationOutputEntry(
                name="apply_translate",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=(
                    "Gate (default True): take translate from the matrix; "
                    "else keep the live TRS translate. Synthetic."
                ),
            ),
            HydrationOutputEntry(
                name="apply_scale",
                target_plug="",  # SYNTHETIC
                kind="bool",
                mode="compute",
                description=(
                    "Gate (default True): take scale from the matrix; "
                    "else keep the live TRS scale. Synthetic."
                ),
            ),
        ],
    )
)

# mPyMesh. Real output: outMesh (typed kMesh); the only real input is _timeIn
# (auto-wired from time1.outTime). Everything else (time, frame, points, counts,
# indices, colors, normals) is SYNTHETIC, filled per compute by the bridge.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyMesh",
        inputs=[
            HydrationInputEntry(
                name="time",
                source_plug="_timeIn",
                kind="time",
                description=(
                    "Current Maya scene time (frames). Auto-wired from "
                    "time1.outTime by the wrapper's create()."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="outMesh",
                target_plug="outMesh",
                kind="mesh",
                mode="compute",
                description=(
                    "The cached MFnMesh built from self.points / "
                    "self.counts / self.indices each compute. Connect "
                    "this to a real Maya mesh shape's inMesh for "
                    "viewport rendering (the canonical Maya pattern)."
                ),
            ),
        ],
    )
)

# mPySkinCluster. Real inputs: envelope, matrix[] (joint world matrices),
# bindPreMatrix[] (bind inverses), weightList[*].weights[*]. Real output:
# outputGeometry[]. No synthetics -- everything is reachable via the plug tree.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPySkinCluster",
        inputs=[
            HydrationInputEntry(
                name="envelope",
                source_plug="envelope",
                kind="float",
                description=(
                    "Deformer envelope (0.0 = no effect, 1.0 = full). "
                    "Inherited from MPxGeometryFilter."
                ),
            ),
            HydrationInputEntry(
                name="matrix",
                source_plug="matrix",
                kind="matrix",
                description=(
                    "Multi -- joint world matrices. Wrapper connects "
                    "each joint's worldMatrix[0] to matrix[i]."
                ),
            ),
            HydrationInputEntry(
                name="bindPreMatrix",
                source_plug="bindPreMatrix",
                kind="matrix",
                description=(
                    "Multi -- joint bind-pose inverse matrices. "
                    "Wrapper seeds from joint.worldInverseMatrix at "
                    "bind time."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="outputGeometry",
                target_plug="outputGeometry",
                kind="mesh",
                mode="compute",
                description=(
                    "Multi -- deformed mesh data. Maya's standard "
                    "deformer output."
                ),
            ),
        ],
    )
)

# mPyBlendShape. Real inputs: envelope, targetGeometry[] (multi typed kMesh).
# Real output: outputGeometry[]. The aliased weight[] multi is NOT listed: it is
# a USER attr (a static multi can't ride the preset path -- preset meta has no
# is_array), so the generic user-attribute binding exposes it as self.weight.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyBlendShape",
        inputs=[
            HydrationInputEntry(
                name="envelope",
                source_plug="envelope",
                kind="float",
                description="Deformer envelope (0..1).",
            ),
            HydrationInputEntry(
                name="targetGeometry",
                source_plug="targetGeometry",
                kind="mesh",
                description=(
                    "Multi -- target mesh shapes. Wrapper connects each "
                    "target's outMesh to targetGeometry[i]."
                ),
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="outputGeometry",
                target_plug="outputGeometry",
                kind="mesh",
                mode="compute",
                description="Multi -- deformed mesh data.",
            ),
        ],
    )
)

# mPyFile. All inputs/outputs are REAL plugs (preset surface modelled on Maya's
# stock ``file`` node). No synthetics -> the Solver Context tab stays hidden.
recipes.register_recipe(
    HydrationRecipe(
        native_type="mPyFile",
        inputs=[
            HydrationInputEntry(
                name="fileName",
                source_plug="fileName",
                kind="string",
                description="Path to the texture image on disk.",
            ),
            HydrationInputEntry(
                name="uvCoord",
                source_plug="uvCoord",
                kind="vector",
                description="UV sample coordinate (compound float2).",
            ),
            HydrationInputEntry(
                name="uvFilterSize",
                source_plug="uvFilterSize",
                kind="vector",
                description="UV filter footprint (compound float2).",
            ),
            HydrationInputEntry(
                name="colorSpace",
                source_plug="colorSpace",
                kind="enum",
                description="Input color space (25 entries).",
            ),
            HydrationInputEntry(
                name="preFilter",
                source_plug="preFilter",
                kind="bool",
                description="Enable CPU pre-filter blur.",
            ),
            HydrationInputEntry(
                name="preFilterKernel",
                source_plug="preFilterKernel",
                kind="enum",
                description="Kernel shape (Box / Quadratic / Quartic / Gaussian).",
            ),
            HydrationInputEntry(
                name="preFilterRadius",
                source_plug="preFilterRadius",
                kind="float",
                description="Kernel radius in texels.",
            ),
            HydrationInputEntry(
                name="filterMode",
                source_plug="filterMode",
                kind="enum",
                description="GPU sampler filter mode.",
            ),
            HydrationInputEntry(
                name="maxAnisotropy",
                source_plug="maxAnisotropy",
                kind="int",
                description="Anisotropic-filter sample budget.",
            ),
            HydrationInputEntry(
                name="mipmapMode",
                source_plug="mipmapMode",
                kind="enum",
                description="GPU mipmap generation (None / Auto).",
            ),
            HydrationInputEntry(
                name="mipLODBias",
                source_plug="mipLODBias",
                kind="float",
                description="LOD bias for mipmap selection.",
            ),
            HydrationInputEntry(
                name="minLOD",
                source_plug="minLOD",
                kind="int",
                description="Smallest mip the GPU may use.",
            ),
            HydrationInputEntry(
                name="maxLOD",
                source_plug="maxLOD",
                kind="int",
                description="Largest mip the GPU may use.",
            ),
            HydrationInputEntry(
                name="wrapModeU",
                source_plug="wrapModeU",
                kind="enum",
                description="U-axis address mode.",
            ),
            HydrationInputEntry(
                name="wrapModeV",
                source_plug="wrapModeV",
                kind="enum",
                description="V-axis address mode.",
            ),
            HydrationInputEntry(
                name="borderColor",
                source_plug="borderColor",
                kind="vector",
                description="Color used when wrap mode = Border.",
            ),
        ],
        outputs=[
            HydrationOutputEntry(
                name="outColor",
                target_plug="outColor",
                kind="vector",
                mode="read",
                description="Sampled color3 (UV bilinear, scene-linear).",
            ),
            HydrationOutputEntry(
                name="outAlpha",
                target_plug="outAlpha",
                kind="float",
                mode="read",
                description="Sampled alpha.",
            ),
        ],
    )
)
