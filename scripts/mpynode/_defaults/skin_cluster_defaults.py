"""Shipped default source strings for mPySkinCluster's Init + Compute tabs.

mPySkinCluster is a genuine ``MPxSkinCluster`` (registered under
``MObject.kSkinCluster``), so Maya's native skinning tools -- the Component
Editor, Paint Skin Weights, ``cmds.skinPercent`` -- read and write the
``weightList[v].weights[j]`` plug, which is the live source of truth this
default reads. The Compute below is standard linear-blend skinning (LBS); it is
numerically identical to the verified demo in
``_demos/build_mPySkinCluster_customLBS.py`` (proven by
``tests/nodes/test_skin_cluster_lbs_parity.py``), so a freshly-created node deforms
correctly the moment weights are painted.

The skinning math is the blessed ``self.linear_blend(rest, weights, joint,
bind)`` API method (SSOT: ``_common/methods/skin_blend.py``); the Compute below is
a one-liner that passes the node's own plugs explicitly, and
the LBS math lives in exactly ONE place -- shared by the interpreted node (bound
via SelfProxy) and the native compiler. The method is written in the VECTORIZED
numpy dialect the compiler lowers to pure C++ (``bind @ joint`` batched matmul +
``einsum`` blend map 1:1 onto ``nd::matmul`` / ``nd::einsum``), and it lowers via
the ``Transpile`` blessed marker (``native/compiler/kernels/blessed_transpile.py``
-> the SAME free fn transpiled as a C++ helper). So "Compile" produces a genuine
native ``MPxSkinCluster::deform()`` -- never an AI port.

Contract: weights must be painted (Maya populates ``weightList`` for the whole
deformer set on bind / first eval), so ``N`` (dense weightList rows) equals the
mesh vertex count. An unpainted, never-evaluated skin has no weights to blend.
"""

# ``np`` is not auto-injected into Compute. The Init namespace merges into the
# Compute globals, so the import must live here.
DEFAULT_INIT_SOURCE = "import numpy as np\n"


DEFAULT_COMPUTE_SOURCE = r'''# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: linear blend skinning (LBS)
#
# The skinning math is the blessed API method self.linear_blend(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It blends M_j = bindPreMatrix_j @ jointWorld_j linearly (identity at the bind
# pose, so the mesh stays at rest until a joint moves) and returns the deformed
# object-space points (N, 3); the envelope + write stay here so partial-effect
# composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object space). It holds a
# copy of the input geometry, so getPoints() == rest and setPoints() commits the
# deform. A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Linear blend skinning of the rest points (envelope=0 rest, 1 fully skinned).
mesh.setPoints(rest + float(self.envelope) * (
    self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
    - rest))
'''
