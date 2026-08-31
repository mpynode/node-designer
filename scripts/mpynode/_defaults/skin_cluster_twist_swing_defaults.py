"""Shipped default source strings for a TWIST/SWING mPySkinCluster.

mPySkinCluster is a genuine ``MPxSkinCluster``; this default runs **twist/swing
skinning** -- dual quaternion skinning (DQS) for the twist about each bone's local
X axis, linear blend skinning (LBS) for the remaining swing (bend). DQS keeps
volume on the twist (no LBS "candy-wrapper" collapse along a twisting limb), while
LBS stays clean and cheap on the bend. It reads the same live plugs as the LBS /
DQS defaults (``self.weightList`` / ``self.matrix`` / ``self.bindPreMatrix`` /
``self.envelope``), so Maya's Component Editor / Paint Skin Weights / skinPercent
all drive it.

The skinning math is the blessed ``self.twist_swing(rest, weights, joint,
bind)`` API method (SSOT: ``_common/methods/skin_blend.py``); the Compute below is
a one-liner that passes the node's own plugs explicitly. The method is a two-pass
COMPOSITION of the shipped LBS + DQS blends (split each per-joint matrix into a
twist part and a swing part about the joint centre, DQS-blend the twist, LBS-blend
the swing), so no skinning math is written a second time. It is written in the
same VECTORIZED numpy dialect the compiler lowers to pure C++ -- no quaternion
kernel needed.

Conventions (Maya row-vector matrices): the per-joint skinning matrix is
``M_j = bindPreMatrix_j @ jointWorld_j`` (identity at the bind pose). The twist
axis is the bone's local X at bind; rigid joints (no scale) are assumed so the
split is analytic.
"""

DEFAULT_INIT_SOURCE = "import numpy as np\n"


DEFAULT_COMPUTE_SOURCE = r'''# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: twist/swing skinning
#
# The skinning math is the blessed API method self.twist_swing(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It applies DUAL QUATERNION skinning to the twist about each bone's local X axis
# (volume-preserving, no candy-wrapper) and LINEAR BLEND skinning to the swing
# (bend), then returns the deformed object-space points (N, 3); the envelope +
# write stay here so partial-effect composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object-space rest points).
# A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Twist/swing skinning (envelope=0 rest, 1 fully skinned). The trailing arg is
# the twist axis (0=X, 1=Y, 2=Z); this bare default twists about X. The shipped
# twist/swing TEMPLATE exposes it as a `twistAxis` enum -- see MODE_COMPUTE_SOURCE.
mesh.setPoints(rest + float(self.envelope) * (
    self.twist_swing(rest, self.weightList, self.matrix, self.bindPreMatrix, 0)
    - rest))
'''


# Richer variant used by the shipped twist/swing TEMPLATE, not the bare default:
# a `skinMode` enum switches the blend at runtime so one node / one painted
# weightList can A/B all three shipped algorithms live. All three blessed
# methods are exercised, so the compiled deform() carries every algorithm and
# branches on skinMode -- flip the enum and re-evaluate to compare.
MODE_COMPUTE_SOURCE = r'''# ----------------------------------------------------------------------
# mPySkinCluster -- twist/swing template Compute with a live skin-MODE switch.
#
# `skinMode` (enum) picks the blend at runtime, so ONE node / ONE painted
# weightList can A/B the three shipped skinCluster algorithms:
#   0 Linear          -> self.linear_blend    (classic LBS)
#   1 Dual Quaternion -> self.dual_quaternion (volume-preserving)
#   2 Twist/Swing     -> self.twist_swing     (DQS twist + LBS swing; default)
# `twistAxis` (enum) picks the bone-local axis the twist is decomposed about --
# 0 X (default), 1 Y, 2 Z -- so the node adapts to any bone orientation.
# Every operand is passed EXPLICITLY (the methods read nothing off self); they are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
#
# self.outputGeometry[0] is the writable mesh handle (object-space rest points).
# A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

mode = int(self.skinMode)
if mode == 0:
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif mode == 1:
    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
else:
    deformed = self.twist_swing(rest, self.weightList, self.matrix, self.bindPreMatrix, int(self.twistAxis))

# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).
mesh.setPoints(rest + float(self.envelope) * (deformed - rest))
'''
