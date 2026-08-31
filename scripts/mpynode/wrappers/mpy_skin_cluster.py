"""User-facing wrapper for the mPySkinCluster plug-in.

mPySkinCluster is a custom expression-driven skinCluster built on
``MPxSkinCluster`` (API 1.0 only). It is a GENUINE skinCluster by type
(registered under ``MPxNode.kSkinCluster``), so Maya's native skinning tools
recognise it: the Component Editor "Smooth Skins" tab, Paint Skin Weights,
``cmds.skinPercent`` and ``MFnSkinCluster`` all work, and they read/write the
``weightList[v].weights[j]`` plug -- the live source of truth. You write the
skinning formula in Python -- linear-blend (LBS), dual-quaternion, custom --
reaching the rig through the plug tree (the old auto-densified ``self.points``
/ ``self.joint_matrices`` / ``self.weights`` schema was removed):

 * ``self.outputGeometry[i]`` -- writable MFnMesh handle
 (``getPoints()`` -> ``(N, 3)`` numpy; ``setPoints()`` commits)
 * ``self.input[i].inputGeometry`` -- read-only upstream mesh
 * ``self.envelope`` -- deformer envelope (inherited)
 * ``self.matrix[j].asNumpy()`` -- (4, 4) joint world matrix
 * ``self.bindPreMatrix[j].asNumpy()`` -- (4, 4) bind-pose inverse
 * ``self.weightList[i].weights`` -- per-vertex sparse weights, the same plug
 the Component Editor / Paint Skin Weights edit; densify it in the expression
 (iterate ``for v, vp in self.weightList: for j, w in vp.weights``)

Note: ``MFnSkinCluster`` is ASYMMETRIC on a Python subclass. ``getWeights()``
returns zeros (the C++ cache is divorced from the plug), so read the
``weightList`` plug or use ``skinPercent`` instead. ``setWeights()`` DOES land
in the plug, and one call replaces a per-element ``setAttr`` loop (measured 13x
on 3721 verts x 4 influences) -- see ``_common/methods/skin_methods.py``
``_bulk_set_weights``, which also documents the cases where it must not be used
(multiple or non-mesh geometry, a gapped ``matrix[]``, and an all-zero trailing
influence column, which setWeights prunes away and thereby shrinks J).

Typical workflow::

 from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
 import maya.cmds as mc

 # Build a joint chain + a mesh to skin.
 j1 = mc.joint(name="j1"); mc.select(clear=True)
 j2 = mc.joint(name="j2", p=(2, 0, 0))
 cyl = mc.polyCylinder(h=4, sx=20, sy=10, axis=(1, 0, 0))[0]

 # Attach + wire joints (worldMatrix -> matrix[i], bindPreMatrix seeded).
 sc = MPySkinCluster.create(cyl, joints=[j1, j2], name="mySkin")
 # Seed the weightList plug (then refine with Maya's Paint Skin Weights).
 for v in range(mc.polyEvaluate(cyl, vertex=True)):
     sc.set_vertex_weight(v, 0, 1.0)
     sc.set_vertex_weight(v, 1, 0.0)
 sc.set_compute_expression('''
 import numpy as np
 mesh = self.outputGeometry[0]
 rest = mesh.getPoints()
 N = rest.shape[0]
 sparse = {}
 n_inf = 0
 for v, vp in self.weightList:                           # live weightList plug
     for j, w in vp.weights:
         sparse[(int(v), int(j))] = float(w)
         n_inf = max(n_inf, int(j) + 1)
 W = np.zeros((N, n_inf), dtype=np.float64)
 for (v, j), w in sparse.items():
     W[v, j] = w
 joint_mats = np.stack([self.matrix[j].asNumpy() for j in range(n_inf)])
 bind_mats = np.stack([self.bindPreMatrix[j].asNumpy() for j in range(n_inf)])
 M = bind_mats @ joint_mats                              # (J, 4, 4)
 pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)
 out = np.einsum("vj,jkc,vk->vc", W, M, pts_h)[:, :3]
 mesh.setPoints(rest + float(self.envelope) * (out - rest))
 ''')

 # Rotate j2 -> the mesh deforms. See _demos/build_mPySkinCluster_customLBS.py.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._common.interface.skin_method_interface import (
    INTERNAL_API_METHODS as _INTERNAL_API_METHODS,
)
from mpynode._common.util.selection_util import restore_selection
from mpynode.wrappers._mpy_node import MPyNode


_SC_TYPE_NAME = "mPySkinCluster"


class MPySkinCluster(MPyNode):
    # No bridge-injected non-plug ``self.X`` names: every ``self.X`` the
    # expression touches is either a plug (visible in Attributes) or per-call
    # user storage (visible in Variables-User).
    INTERNAL_API_SLOTS = ()

    # Blessed METHOD-kind ops (self.linear_blend / self.dual_quaternion),
    # surfaced in the Variables tab. SSOT = skin_method_interface.
    INTERNAL_API_METHODS = _INTERNAL_API_METHODS

    # Wrapper-level API for the API tab (setup / demo / @maya_command bodies);
    # never reachable as ``self.X`` from an expression tier.
    AUTHORING_API = (
        ("set_vertex_weight", ""),
    )

    NATIVE_TYPE = _SC_TYPE_NAME

    # Attributes-tab allowlist (framework OFF): deformer I/O + the skin knobs
    # an artist drives. Hides the ~40 inherited noise plugs (paintWeights /
    # wtDrty / bindPose / influenceColor / dqsScale / ...).
    from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL as _DEF_USEFUL
    USEFUL_INHERITED_PLUGS = _DEF_USEFUL | frozenset({
        "skinningMethod", "normalizeWeights", "maxInfluences",
        "maintainMaxInfluences", "dropoff", "blendWeights",
        "bindPreMatrix", "geomMatrix",
    })
    del _DEF_USEFUL

    @classmethod
    def create(
        cls,
        mesh: str | None = None,
        joints: list[str] | None = None,
        name: str = None,
        skip_selection: bool = False,
    ) -> "MPySkinCluster":
        """Create an mPySkinCluster.

        If ``mesh`` is provided, attaches the deformer to it via
        ``mc.deformer`` and connects each joint's ``worldMatrix`` into
        the inherited ``matrix[]`` multi (plus seeds bindPreMatrix
        from each joint's current ``worldInverseMatrix``).

        If ``mesh`` is None, just creates a bare node -- the caller
        is responsible for wiring it manually.

        Note: this does NOT paint weights -- the user must populate
        ``weightList[*].weights[*]`` themselves (or write a Python
        helper). For a normal Maya skinning workflow you'd typically
        use ``mc.skinCluster`` for the bind, but that command is
        hard-coded to the native skinCluster type and can't target a
        custom MPxSkinCluster subclass. Instead, this helper does the
        plug wiring directly.
        """
        from mpynode._common.lifecycle.plugin_loader import ensure_loaded

        ensure_loaded(cls.NATIVE_TYPE)
        if name is None:
            name = cls._default_create_name()
        if mesh is None:
            node = mc.createNode(cls.NATIVE_TYPE, name=name,
                                 skipSelect=skip_selection)
            return cls._stamp_py_class(cls(node))

        # mc.deformer works for any MPxGeometryFilter subclass. It has no
        # skipSelect and is selection-neutral in practice; snapshot + restore
        # anyway so the uniform contract always holds.
        prior = mc.ls(selection=True, long=True) if skip_selection else None
        sc_name = mc.deformer(mesh, type=cls.NATIVE_TYPE, name=name)[0]

        if joints:
            cls._wire_joints(sc_name, joints)

        if skip_selection:
            restore_selection(prior)
        return cls._stamp_py_class(cls(sc_name))

    @staticmethod
    def _wire_joints(sc_name: str, joints: list[str]) -> None:
        """Connect each joint's worldMatrix into matrix[i] and seed
        bindPreMatrix[i] from worldInverseMatrix at the current pose.
        Equivalent to the standard skinCluster bind setup.
        """
        for i, jnt in enumerate(joints):
            mc.connectAttr(
                jnt + ".worldMatrix[0]",
                f"{sc_name}.matrix[{i}]",
                force=True,
            )
            # Seed bindPreMatrix from the joint's bind-time inverse world matrix.
            inv = mc.getAttr(jnt + ".worldInverseMatrix[0]")
            mc.setAttr(f"{sc_name}.bindPreMatrix[{i}]", inv, type="matrix")

    def set_vertex_weight(
        self, vertex_index: int, joint_index: int, weight: float
    ) -> None:
        """Helper: set a single ``weightList[v].weights[j]`` entry."""
        mc.setAttr(
            f"{self._name}.weightList[{vertex_index}].weights[{joint_index}]",
            float(weight),
        )
