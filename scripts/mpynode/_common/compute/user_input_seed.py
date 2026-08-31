"""Seed dense USER inputs into an api1 compute_locals dict (C2 base contract).

The api2 own-path nodes (mesh / nurbs curve / nurbs surface / file / locator)
seed every USER input into the SelfProxy ``compute_locals`` so ``self.<input>``
is a DENSE numpy value -- never the ragged live ``(index, value)`` plug proxy
that raises ``ValueError: ... inhomogeneous shape`` under ``np.asarray(...)``.

The api1 compute paths built their ``compute_locals`` from curated internals +
pre-sized array outputs but historically SKIPPED user inputs, so
``self.<vector-array input>`` fell through to the plug tree -> ragged proxy ->
the inhomogeneous-shape error. The three api1 sites:

  * ``mpynode._api1.mpy_transform.MPyTransformMatrix._run_expression``
  * ``mpynode._common.compute.compute.run_generic_compute`` (the deformer family:
    mPyDeformer / mPyBlendShape / mPySkinCluster)
  * ``mpynode._api1.helpers.compute_ik_user_solve`` (mPyIkSolver)

This helper closes the gap by reusing the SAME dense reader
(``read_user_inputs_dict``) the api2 nodes use, resolving the node as an api2
``MObject`` so it works from api1 code. It is best-effort: any failure leaves
``compute_locals`` unchanged, so ``self.<input>`` degrades to the pre-existing
plug-tree read rather than breaking compute.
"""

from __future__ import annotations


def seed_user_inputs_into_locals(node_obj_api1, compute_locals: dict) -> None:
    """Seed every USER input of ``node_obj_api1`` (an api1 ``MObject``) into
    ``compute_locals`` as a DENSE value (via ``setdefault`` -- never clobbers a
    curated internal already present). Best-effort; silent on any failure.

    Reuses :func:`mpynode._api2.helpers.read_user_inputs_dict` through an api2
    ``MObject`` resolved from the node's unique identifier -- the full DAG path
    for DAG nodes (short names can collide) or the node name otherwise.
    """
    if compute_locals is None:
        return
    try:
        import maya.OpenMaya as om1
    except Exception:
        return

    # Resolve a UNIQUE identifier: DAG nodes can share short names, so prefer
    # the full DAG path; fall back to the DG node name.
    name = None
    try:
        if node_obj_api1.hasFn(om1.MFn.kDagNode):
            name = om1.MFnDagNode(node_obj_api1).fullPathName()
    except Exception:
        name = None
    if not name:
        try:
            name = om1.MFnDependencyNode(node_obj_api1).name()
        except Exception:
            return
    if not name:
        return

    try:
        import maya.api.OpenMaya as om2

        from mpynode._api2.helpers import read_user_inputs_dict

        sel = om2.MSelectionList()
        sel.add(name)
        node_obj2 = sel.getDependNode(0)
    except Exception:
        return

    # Decode the input schema off the node's _inputAttrs plug.
    try:
        from mpynode._common.io import serialization as _serialization

        in_str = om2.MFnDependencyNode(node_obj2).findPlug(
            "_inputAttrs", True
        ).asString()
        input_map = _serialization.decode_attr_map(in_str) if in_str else {}
    except Exception:
        input_map = {}
    if not input_map:
        return

    try:
        values = read_user_inputs_dict(node_obj2, input_map)
    except Exception:
        return
    for key, val in values.items():
        compute_locals.setdefault(key, val)
