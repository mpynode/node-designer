"""Maya-free skinning math -- the single source of truth for the LBS + DQS
blessed API methods on ``mPySkinCluster``.

Each function is a pure numpy ``(rest, weights, joint, bind) -> (N, 3)`` map:
  rest    : (N, 3)  object-space rest points
  weights : (N, J)  dense per-vertex, per-influence weights
  joint   : (J, 4, 4) live joint WORLD matrices (Maya row-vector)
  bind    : (J, 4, 4) joint bind-pose inverse matrices
returns   : (N, 3)  deformed object-space points (envelope applied by the caller)

Both the interpreted adapters (``skin_methods.py``) and the native compiler's
blessed ``Transpile`` lowering read THESE functions, so the interpreted node and
the compiled ``MPxSkinCluster::deform()`` run one shared algorithm -- no math is
written twice. Written in the vectorized numpy dialect the compiler lowers to
pure C++ (batched matmul, ``transpose(axes)``, integer-index, ``sqrt`` /
``maximum`` / ``sign``, ``where`` cascade, ``stack(axis=)``, ``einsum``,
``reshape``) -- every op maps 1:1 onto an ``nd::*`` kernel, no quaternion kernel
needed.

Convention (Maya row-vector matrices): ``M_j = bind_j @ joint_j`` (identity at the
bind pose). LBS blends ``M_j`` linearly; DQS blends each ``M_j`` as a unit dual
quaternion (rotation from the COLUMN form ``M_j[:3, :3].T``, translation from row
``M_j[3, :3]``), so a bent joint keeps its volume.
"""
import numpy as np


def linear_blend(rest, weights, joint, bind):
    """Linear blend skinning: deformed[v] = sum_j W[v,j] * (rest_h[v] @ M_j)."""
    N     = rest.shape[0]
    W     = weights
    M     = bind @ joint                                     # (J, 4, 4)
    pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)  # (N, 4)
    return np.einsum("vj,jkc,vk->vc", W, M, pts_h)[:, :3]         # (N, 3)


def dual_quaternion(rest, weights, joint, bind):
    """Dual quaternion skinning: blend each influence's rigid transform as a
    unit dual quaternion (volume-preserving; no linear "candy-wrapper" collapse).
    """
    N = rest.shape[0]
    W = weights
    M = bind @ joint                                    # (J, 4, 4)

    # Per-joint column-form rotation + translation from the Maya row-vector matrix.
    R = np.transpose(M[:, :3, :3], (0, 2, 1))  # (J, 3, 3)
    t = M[:, 3, :3]                            # (J, 3)
    r00 = R[:, 0, 0]; r01 = R[:, 0, 1]; r02 = R[:, 0, 2]
    r10 = R[:, 1, 0]; r11 = R[:, 1, 1]; r12 = R[:, 1, 2]
    r20 = R[:, 2, 0]; r21 = R[:, 2, 1]; r22 = R[:, 2, 2]

    # Rotation matrix -> unit quaternion, 4-case trace cascade (stable near tr=-1).
    tr = r00 + r11 + r22
    S0 = np.sqrt(np.maximum(tr + 1.0, 1e-12)) * 2.0
    qw0 = 0.25 * S0; qx0 = (r21 - r12) / S0; qy0 = (r02 - r20) / S0; qz0 = (r10 - r01) / S0
    S1 = np.sqrt(np.maximum(1.0 + r00 - r11 - r22, 1e-12)) * 2.0
    qw1 = (r21 - r12) / S1; qx1 = 0.25 * S1; qy1 = (r01 + r10) / S1; qz1 = (r02 + r20) / S1
    S2 = np.sqrt(np.maximum(1.0 + r11 - r00 - r22, 1e-12)) * 2.0
    qw2 = (r02 - r20) / S2; qx2 = (r01 + r10) / S2; qy2 = 0.25 * S2; qz2 = (r12 + r21) / S2
    S3 = np.sqrt(np.maximum(1.0 + r22 - r00 - r11, 1e-12)) * 2.0
    qw3 = (r10 - r01) / S3; qx3 = (r02 + r20) / S3; qy3 = (r12 + r21) / S3; qz3 = 0.25 * S3

    m0 = tr > 0.0
    m1 = (~m0) & (r00 >= r11) & (r00 >= r22)
    m2 = (~m0) & (~m1) & (r11 >= r22)
    qw = np.where(m0, qw0, np.where(m1, qw1, np.where(m2, qw2, qw3)))
    qx = np.where(m0, qx0, np.where(m1, qx1, np.where(m2, qx2, qx3)))
    qy = np.where(m0, qy0, np.where(m1, qy1, np.where(m2, qy2, qy3)))
    qz = np.where(m0, qz0, np.where(m1, qz1, np.where(m2, qz2, qz3)))
    qr = np.stack([qw, qx, qy, qz], axis=1)             # (J, 4) unit rotation quats

    # Dual part: qd_j = 0.5 * (pureQuat(t_j) (x) qr_j).
    tx = t[:, 0]; ty = t[:, 1]; tz = t[:, 2]
    dw = -(tx * qx + ty * qy + tz * qz)
    dx = tx * qw + ty * qz - tz * qy
    dy = -tx * qz + ty * qw + tz * qx
    dz = tx * qy - ty * qx + tz * qw
    qd = 0.5 * np.stack([dw, dx, dy, dz], axis=1)       # (J, 4)

    # Hemisphere alignment: flip influences pointing away from influence 0.
    dot0 = np.sum(qr * qr[0], axis=1)                   # (J,)
    sgn  = np.sign(dot0)
    sgn  = np.where(sgn == 0.0, 1.0, sgn)
    qr   = qr * sgn[:, None]
    qd   = qd * sgn[:, None]

    # Weighted blend of the dual quaternions, then re-normalise.
    br  = np.einsum("vj,jk->vk", W, qr)     # (N, 4)
    bd  = np.einsum("vj,jk->vk", W, qd)     # (N, 4)
    mag = np.sqrt(np.sum(br * br, axis=1))  # (N,)
    br  = br / mag[:, None]
    bd  = bd / mag[:, None]

    # Blended unit dual quaternion -> rotation matrix + translation.
    bw = br[:, 0]; bx = br[:, 1]; by = br[:, 2]; bz = br[:, 3]
    R00 = 1.0 - 2.0 * (by * by + bz * bz); R01 = 2.0 * (bx * by - bw * bz); R02 = 2.0 * (bx * bz + bw * by)
    R10 = 2.0 * (bx * by + bw * bz); R11 = 1.0 - 2.0 * (bx * bx + bz * bz); R12 = 2.0 * (by * bz - bw * bx)
    R20 = 2.0 * (bx * bz - bw * by); R21 = 2.0 * (by * bz + bw * bx); R22 = 1.0 - 2.0 * (bx * bx + by * by)
    Rn = np.reshape(np.stack([R00, R01, R02, R10, R11, R12, R20, R21, R22], axis=1), (N, 3, 3))

    # translation = 2 * vec(bd (x) conj(br))
    cw = bw; cx = -bx; cy = -by; cz = -bz
    dwb = bd[:, 0]; dxb = bd[:, 1]; dyb = bd[:, 2]; dzb = bd[:, 3]
    px = dwb * cx + dxb * cw + dyb * cz - dzb * cy
    py = dwb * cy - dxb * cz + dyb * cw + dzb * cx
    pz = dwb * cz + dxb * cy - dyb * cx + dzb * cw
    tn = 2.0 * np.stack([px, py, pz], axis=1)           # (N, 3)

    return np.einsum("vij,vj->vi", Rn, rest) + tn       # (N, 3)


# ---- Twist/swing skinning: DQS for the twist about a selectable bone-local
# axis (twist_axis 0=X/1=Y/2=Z, default X), LBS for the remaining swing. A
# two-pass COMPOSITION of the functions above -- it reuses the shipped, verified
# LBS + DQS blends by passing an identity ``bind``, so no skinning math is
# written twice and linear_blend / dual_quaternion stay untouched. ----


def _mat_to_quat_cols(R):
    """(J, 3, 3) COLUMN-form rotation matrices -> (J, 4) unit quaternions
    [w, x, y, z]. Same 4-case trace cascade as ``dual_quaternion`` (stable
    near tr = -1); written in the vectorized dialect the compiler lowers to C++."""
    r00 = R[:, 0, 0]; r01 = R[:, 0, 1]; r02 = R[:, 0, 2]
    r10 = R[:, 1, 0]; r11 = R[:, 1, 1]; r12 = R[:, 1, 2]
    r20 = R[:, 2, 0]; r21 = R[:, 2, 1]; r22 = R[:, 2, 2]
    tr = r00 + r11 + r22
    S0 = np.sqrt(np.maximum(tr + 1.0, 1e-12)) * 2.0
    qw0 = 0.25 * S0; qx0 = (r21 - r12) / S0; qy0 = (r02 - r20) / S0; qz0 = (r10 - r01) / S0
    S1 = np.sqrt(np.maximum(1.0 + r00 - r11 - r22, 1e-12)) * 2.0
    qw1 = (r21 - r12) / S1; qx1 = 0.25 * S1; qy1 = (r01 + r10) / S1; qz1 = (r02 + r20) / S1
    S2 = np.sqrt(np.maximum(1.0 + r11 - r00 - r22, 1e-12)) * 2.0
    qw2 = (r02 - r20) / S2; qx2 = (r01 + r10) / S2; qy2 = 0.25 * S2; qz2 = (r12 + r21) / S2
    S3 = np.sqrt(np.maximum(1.0 + r22 - r00 - r11, 1e-12)) * 2.0
    qw3 = (r10 - r01) / S3; qx3 = (r02 + r20) / S3; qy3 = (r12 + r21) / S3; qz3 = 0.25 * S3
    m0 = tr > 0.0
    m1 = (~m0) & (r00 >= r11) & (r00 >= r22)
    m2 = (~m0) & (~m1) & (r11 >= r22)
    qw = np.where(m0, qw0, np.where(m1, qw1, np.where(m2, qw2, qw3)))
    qx = np.where(m0, qx0, np.where(m1, qx1, np.where(m2, qx2, qx3)))
    qy = np.where(m0, qy0, np.where(m1, qy1, np.where(m2, qy2, qy3)))
    qz = np.where(m0, qz0, np.where(m1, qz1, np.where(m2, qz2, qz3)))
    return np.stack([qw, qx, qy, qz], axis=1)           # (J, 4)


def _quat_to_mat_cols(q):
    """(J, 4) unit quaternions [w, x, y, z] -> (J, 3, 3) COLUMN-form rotation
    matrices (same formula as ``dual_quaternion``'s blend->matrix step)."""
    w = q[:, 0]; x = q[:, 1]; y = q[:, 2]; z = q[:, 3]
    R00 = 1.0 - 2.0 * (y * y + z * z); R01 = 2.0 * (x * y - w * z); R02 = 2.0 * (x * z + w * y)
    R10 = 2.0 * (x * y + w * z); R11 = 1.0 - 2.0 * (x * x + z * z); R12 = 2.0 * (y * z - w * x)
    R20 = 2.0 * (x * z - w * y); R21 = 2.0 * (y * z + w * x); R22 = 1.0 - 2.0 * (x * x + y * y)
    return np.reshape(
        np.stack([R00, R01, R02, R10, R11, R12, R20, R21, R22], axis=1),
        (q.shape[0], 3, 3))


def _joint_centre(bind):
    """Joint rest centre ``c_j`` = translation of ``inv(bind_j)`` (rigid inverse),
    (J, 3). The twist + swing rotations are built ABOUT this point, not the origin,
    so a swing blends like a normal skinning matrix (see ``_swing_matrix``)."""
    Rb_row = bind[:, :3, :3]; tb = bind[:, 3, :3]
    return -np.einsum("vj,vjk->vk", tb, np.transpose(Rb_row, (0, 2, 1)))  # -tb @ Rb.T


def _twist_rotation_row(M, bind, twist_axis=0):
    """Row-form rotation of the TWIST-about-a-bone-local-axis part of each ``M_j``
    -> (J, 3, 3). ``twist_axis`` selects the bone-local axis at bind (0=X, 1=Y,
    2=Z; default X) -- a fixed reference a bone's own twist about that axis leaves
    invariant, so a pure twist lands entirely here and a pure bend leaves it
    identity. A 180-deg swing perpendicular to the axis is the singular case,
    guarded to identity."""
    R_row = M[:, :3, :3]                    # (J, 3, 3) full rotation, row
    Rc    = np.transpose(R_row, (0, 2, 1))  # (J, 3, 3) column form (for quat)
    q     = _mat_to_quat_cols(Rc)           # (J, 4) [w, x, y, z]

    # Twist axis a_j = the selected bone-local column at bind (X=0/Y=1/Z=2), a
    # column-vector in the geometry frame. Picked by a scalar-coefficient blend
    # of the three bind columns -- Lagrange interpolation in ``twist_axis`` over
    # {0,1,2}, so cx/cy/cz are (1,0,0) at X, (0,1,0) at Y, (0,0,1) at Z. Scalar
    # arithmetic, literal-index columns and scalar*array only, all of which lower
    # 1:1 to C++ (no dynamic index, no scalar-condition where). At twist_axis==0
    # this is cx=1, cy=cz=0, so ``a`` is the X column byte-for-byte.
    t  = float(twist_axis)
    cx = (t - 1.0) * (t - 2.0) * 0.5
    cy = t * (2.0 - t)
    cz = t * (t - 1.0) * 0.5
    a  = cx * bind[:, :3, 0] + cy * bind[:, :3, 1] + cz * bind[:, :3, 2]  # (J, 3)
    a  = a / np.sqrt(np.sum(a * a, axis=1) + 1e-30)[:, None]

    qw = q[:, 0]; qx = q[:, 1]; qy = q[:, 2]; qz = q[:, 3]
    d   = qx * a[:, 0] + qy * a[:, 1] + qz * a[:, 2]                     # v . a
    tw  = np.stack([qw, d * a[:, 0], d * a[:, 1], d * a[:, 2]], axis=1)  # (J, 4)
    nrm = np.sqrt(np.sum(tw * tw, axis=1))                               # (J,)
    # Singularity guard: |twist| ~ 0 (180-deg swing perpendicular to a) -> identity.
    safe = nrm > 1e-8
    tw   = tw / np.where(safe, nrm, 1.0)[:, None]
    ident_q = np.zeros_like(tw); ident_q[:, 0] = 1.0
    tw = np.where(safe[:, None], tw, ident_q)           # (J, 4) unit twist quat
    return np.transpose(_quat_to_mat_cols(tw), (0, 2, 1))   # (J,3,3) twist rotation, row


def _twist_matrix(M, bind, twist_axis=0):
    """Twist part of each per-joint skinning matrix ``M_j`` (row-vector): a
    rotation about the joint rest centre ``c_j`` by the twist rotation ->
    ``[Rt_row | c@(I - Rt)]``, (J, 4, 4). ``twist_axis`` (0=X/1=Y/2=Z) picks the
    bone-local twist axis."""
    Rt_row             = _twist_rotation_row(M, bind, twist_axis)
    c                  = _joint_centre(bind)
    M_twist            = np.zeros_like(M)
    M_twist[:, :3, :3] = Rt_row
    M_twist[:, 3, :3]  = c - np.einsum("vj,vjk->vk", c, Rt_row)
    M_twist[:, 3, 3]   = 1.0
    return M_twist


def _swing_matrix(M, bind, twist_axis=0):
    """Swing (bend) part of each per-joint skinning matrix ``M_j`` (row-vector):
    the residual rotation ``Rs = inv(twist) @ full`` about the joint rest centre
    ``c_j``, carrying the net non-rotational translation of ``M`` so that
    ``M_twist_j @ M_swing_j == M_j`` exactly, (J, 4, 4). ``twist_axis``
    (0=X/1=Y/2=Z) picks the bone-local twist axis subtracted off here.

    Both parts rotate about ``c_j`` (NOT the origin): a swing that rotates about
    the joint centre blends like a normal skinning matrix, whereas ``inv(M_twist)
    @ M`` would rotate about ``M``'s translation -- a point that flies far from the
    joint under large rotation, so LBS-blending it collapses the mesh at the blend
    region."""
    R_row  = M[:, :3, :3]  # (J, 3, 3) full rotation, row
    t      = M[:, 3, :3]   # (J, 3) full translation
    Rt_row = _twist_rotation_row(M, bind, twist_axis)
    # Swing rotation (row) = inv(twist) @ full = Rt_row.T @ R_row.
    Rs_row = np.einsum("vij,vjk->vik", np.transpose(Rt_row, (0, 2, 1)), R_row)
    c      = _joint_centre(bind)
    # Net non-rotational translation of M about c_j: e = t - c@(I - R).
    e                  = t - (c - np.einsum("vj,vjk->vk", c, R_row))
    M_swing            = np.zeros_like(M)
    M_swing[:, :3, :3] = Rs_row
    M_swing[:, 3, :3]  = (c - np.einsum("vj,vjk->vk", c, Rs_row)) + e
    M_swing[:, 3, 3]   = 1.0
    return M_swing


def _split_twist_swing(M, bind, twist_axis=0):
    """Split each per-joint skinning matrix ``M_j`` (row-vector) into a
    twist-about-the-bone's-local-axis part and a swing part, such that
    ``M_twist_j @ M_swing_j == M_j`` (row-vector composition = apply twist, then
    swing). ``twist_axis`` (0=X/1=Y/2=Z) picks the axis. Returns
    ``(M_twist, M_swing)``, each (J, 4, 4). Rigid joints assumed.

    Thin interpreted/oracle convenience over :func:`_twist_matrix` /
    :func:`_swing_matrix` (the compiled ``twist_swing`` calls those two directly:
    the transpiler follows single-value helpers, not a tuple return)."""
    return _twist_matrix(M, bind, twist_axis), _swing_matrix(M, bind, twist_axis)


def twist_swing_dual(rest, twist_weights, swing_weights, joint, bind, twist_axis=0):
    """Twist/swing skinning with SEPARATE weight sets for the two passes:
    ``twist_weights`` drives the dual-quaternion TWIST (about the bone-local axis
    picked by ``twist_axis``: 0=X/1=Y/2=Z, default X), ``swing_weights`` the
    linear-blend SWING (bend). Both are dense (N, J).

    This is the general form; :func:`twist_swing` is the ``twist_weights ==
    swing_weights`` case. Distinct weight sets let an artist tune the volume-
    preserving twist falloff independently of the bend falloff on ONE node (see the
    ``twist_swing_skin`` template). Every operand is EXPLICIT -- the
    method reads nothing off self.
    """
    M       = bind @ joint                        # (J, 4, 4)
    M_twist = _twist_matrix(M, bind, twist_axis)  # (J, 4, 4)
    M_swing = _swing_matrix(M, bind, twist_axis)  # (J, 4, 4)
    # bind = identity, so the reused blends see exactly M_twist / M_swing
    # (identity @ X == X byte-for-byte). Built with zeros + a set diagonal, not
    # np.broadcast_to / np.eye, so the whole method lowers to pure C++.
    ident = np.zeros_like(M)
    ident[:, 0, 0] = 1.0; ident[:, 1, 1] = 1.0
    ident[:, 2, 2] = 1.0; ident[:, 3, 3] = 1.0
    p1 = dual_quaternion(rest, twist_weights, M_twist, ident)   # DQS twist
    return linear_blend(p1, swing_weights, M_swing, ident)      # LBS swing


def twist_swing(rest, weights, joint, bind, twist_axis=0):
    """Twist/swing skinning: dual quaternion for the TWIST about each bone's local
    axis (``twist_axis``: 0=X/1=Y/2=Z, default X), linear blend for the remaining
    SWING (bend).

    DQS keeps volume on the twist (no LBS candy-wrapper collapse); LBS stays clean
    and cheap on the bend. Two passes: split each ``M_j = bind_j @ joint_j`` into a
    twist part and a swing part, DQS-blend the twist to an intermediate mesh, then
    LBS-blend the swing on top. Single-joint influence recovers the full transform
    exactly (M_twist @ M_swing == M). One weight set drives both passes (the
    ``twist_weights == swing_weights`` case of :func:`twist_swing_dual`). Every
    operand is an EXPLICIT argument -- the method reads nothing off self.
    """
    return twist_swing_dual(rest, weights, weights, joint, bind, twist_axis)
