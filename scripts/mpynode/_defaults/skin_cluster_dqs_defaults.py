"""Shipped default source strings for a dual-quaternion mPySkinCluster.

mPySkinCluster is a genuine ``MPxSkinCluster``; this default runs **dual
quaternion skinning (DQS)** instead of linear blend skinning (LBS). DQS blends
each influence's rigid transform as a unit dual quaternion, so a bent joint keeps
its volume (no LBS "candy-wrapper" collapse). It reads the same live plugs as the
LBS default (``self.weightList`` / ``self.matrix`` / ``self.bindPreMatrix`` /
``self.envelope``), so Maya's Component Editor / Paint Skin Weights / skinPercent
all drive it.

The skinning math is the blessed ``self.dual_quaternion(rest, weights, joint,
bind)`` API method (SSOT: ``_common/methods/skin_blend.py``); the Compute below is
a one-liner that passes the node's own plugs explicitly, and
the DQS math lives in exactly ONE place -- shared by the interpreted node (bound
via SelfProxy) and the native compiler. Like the LBS default, the method is
written in the VECTORIZED numpy dialect the compiler lowers to pure C++ (batched
matmul, ``transpose(axes)``, integer-index, ``sqrt`` / ``maximum`` / ``sign``,
``where`` cascade, ``stack(axis=)``, ``einsum``, ``reshape`` -- every op maps 1:1
onto an ``nd::*`` runtime kernel; no quaternion kernel needed) and lowers via the
``Transpile`` blessed marker, so "Compile" produces a genuine native
``MPxSkinCluster::deform()`` (never an AI port).

Conventions (Maya row-vector matrices): the per-joint skinning matrix is
``M_j = bindPreMatrix_j @ jointWorld_j`` (identity at the bind pose). The rotation
used for the quaternion is the COLUMN form ``M_j[:3, :3].T`` and the translation is
row ``M_j[3, :3]``. The matrix->quaternion step uses the standard 4-case trace
cascade (via ``np.where``) so it is stable even when the trace is near -1.
"""

DEFAULT_INIT_SOURCE = "import numpy as np\n"


DEFAULT_COMPUTE_SOURCE = r'''# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: dual quaternion skinning (DQS)
#
# The skinning math is the blessed API method self.dual_quaternion(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It blends each influence's rigid transform as a unit dual quaternion, so a bent
# joint keeps its volume (no LBS "candy-wrapper" collapse), and returns the
# deformed object-space points (N, 3); the envelope + write stay here so
# partial-effect composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object-space rest points).
# A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Dual quaternion skinning of the rest points (envelope=0 rest, 1 fully skinned).
mesh.setPoints(rest + float(self.envelope) * (
    self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
    - rest))
'''
