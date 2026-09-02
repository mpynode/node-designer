"""Maya transform bridge for deterministically-lowered computes.

``MatrixView`` exposes the whole ``MMatrix`` + ``MTransformationMatrix`` surface
(``rotation``, ``scale``, ``shear``, ``rotationOrder``, ``asRotateMatrix`` ...).
Reimplementing those decompositions in ``nd::`` would be a standing parity
liability -- Maya's conventions for negative scale, shear extraction and
rotate-order reordering are not worth re-deriving and hoping. The generated
file IS a Maya plug-in, so it can simply call Maya and be bit-exact by
construction rather than to a tolerance.

WHY THIS IS NOT IN ``nd_runtime.h``: the eleven transpiler oracle harnesses
under ``tests/compile/native/`` compile that header with ``-std=c++17 -I <repo>``
and **no Maya include path** -- they carry their own ``MVector``/``MPoint``
shims (``TRANSPILER.md``). One ``maya/`` include in the runtime turns all
eleven red. This block therefore rides ON TOP of the runtime, the way
``nd_io_cpp`` does, and is emitted only when a spec actually needs it.

Design note: ``docs/notes/matrixview-lowering.md``.
"""
from __future__ import annotations

import re

# Emitted into the generated .cpp only alongside MAYA_XFORM_CPP.
MAYA_XFORM_INCLUDES = (
    "maya/MMatrix.h",
    "maya/MTransformationMatrix.h",
    "maya/MEulerRotation.h",
    "maya/MVector.h",
    # NOT maya/MSpace.h -- no such header. MSpace is declared in
    # maya/MTypes.h, which MTransformationMatrix.h already includes.
)

# Method names that require the bridge. The pure-nd ones -- translation,
# inverse, transpose, getElement, det3x3, det4x4, asNumpy -- are deliberately
# ABSENT: they lower through existing nd:: kernels and must not drag Maya
# headers into a file that would otherwise not need them.
XFORM_METHODS = (
    "rotation", "scale", "shear", "rotationOrder",
    "asRotateMatrix", "asScaleMatrix", "asMatrixInverse",
    "adjoint", "homogenize", "isSingular",
)

_XFORM_USE_RE = re.compile(r"\.(?:%s)\s*\(" % "|".join(XFORM_METHODS))


def _has_matrix_input(spec) -> bool:
    """True if any declared input is a matrix (scalar or array).

    Only a matrix plug can hand an expression a MatrixView, so this is the
    discriminating half of the gate below.
    """
    inputs = spec.get("inputs") or {}
    values = inputs.values() if isinstance(inputs, dict) else inputs
    for meta in values:
        if isinstance(meta, dict) and meta.get("type") == "matrix":
            return True
    return False


def spec_uses_maya_xform(spec) -> bool:
    """True if the node's compute or init calls a MatrixView method that needs
    Maya semantics.

    Matched on SOURCE plus the input table, NOT on transpiler state, for the
    same reason ``nd_io_cpp.spec_uses_ndio`` is: the include list and the
    emitted helper block are decided before, and independently of, compute
    lowering.

    BOTH halves are required. A bare method-name scan is far more
    collision-prone than ``ndio.read`` -- ``.scale(`` is a common spelling on
    unrelated objects -- and a false positive drags Maya headers into a file
    that never touches a matrix, changing its bytes for no reason.
    """
    if not _has_matrix_input(spec):
        return False
    src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    return bool(_XFORM_USE_RE.search(src))


# ---------------------------------------------------------------------------
# The C++ block. Own include guard, so bundling several nodes into one
# translation unit stays idempotent (same contract as NDIO_CPP).
# ---------------------------------------------------------------------------
MAYA_XFORM_CPP = r"""
#ifndef ND_MAYA_XFORM_H
#define ND_MAYA_XFORM_H
// Maya-backed MatrixView methods. Every function delegates to Maya so the
// compiled node and the interpreted node agree EXACTLY rather than to a
// tolerance -- these are the same MTransformationMatrix calls the Python
// MatrixView makes (mpynode/_common/plugs/promoted_types.py).
namespace ndx {

// nd (4,4) -> MMatrix. Element mapping is the identity used by
// nd_lower._materialise_input: numpy M[i,j] == MMatrix m(i,j), Maya's
// row-vector convention with the translation in ROW 3, not column 3.
// Read through strides + offset rather than assuming a dense buffer, so a
// sliced or transposed view still reads correctly.
inline MMatrix nd_to_mmatrix(const nd::Array<double>& a) {
    int64_t rank = a.ndim();
    if (rank < 2 || a.shape[rank-2] != 4 || a.shape[rank-1] != 4)
        throw std::runtime_error("ndx: expected a (4,4) matrix");
    int64_t s0 = a.strides[rank-2], s1 = a.strides[rank-1];
    double d[4][4];
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j)
            d[i][j] = (*a.data)[(size_t)(a.offset + i*s0 + j*s1)];
    return MMatrix(d);
}

inline nd::Array<double> mmatrix_to_nd(const MMatrix& m) {
    std::vector<double> f((size_t)16);
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j) f[(size_t)(i*4 + j)] = m(i, j);
    return nd::from_data<double>(f, nd::Shape{4, 4});
}

inline nd::Array<double> nd_triple(double x, double y, double z) {
    return nd::from_data<double>(std::vector<double>{x, y, z}, nd::Shape{3});
}

// Maya rotate-order INDEX (0=xyz 1=yzx 2=zxy 3=xzy 4=yxz 5=zyx -- the same
// numbering a rotateOrder enum plug uses) -> MEulerRotation::RotationOrder.
// Spelled out rather than cast: MTransformationMatrix::RotationOrder is NOT
// 0-based (kInvalid=0, kXYZ=1), and conflating the two silently rotates wrong.
inline MEulerRotation::RotationOrder euler_order(int64_t axes) {
    switch (axes) {
        case 1:  return MEulerRotation::kYZX;
        case 2:  return MEulerRotation::kZXY;
        case 3:  return MEulerRotation::kXZY;
        case 4:  return MEulerRotation::kYXZ;
        case 5:  return MEulerRotation::kZYX;
        default: return MEulerRotation::kXYZ;
    }
}

// MatrixView.rotation(axes=N) -> (3,) euler radians, reordered in place.
// The Python calls api2 MTransformationMatrix.rotation(), which returns an
// MEulerRotation; the C++ method of that name returns an MQuaternion, so the
// euler equivalent is eulerRotation().
inline nd::Array<double> xf_rotation(const nd::Array<double>& a, int64_t axes) {
    MTransformationMatrix tm(nd_to_mmatrix(a));
    MEulerRotation e = tm.eulerRotation();
    e.reorderIt(euler_order(axes));
    return nd_triple(e.x, e.y, e.z);
}

// .scale() / .shear() -> (3,) in MSpace::kTransform, the Python's space=None.
inline nd::Array<double> xf_scale(const nd::Array<double>& a) {
    MTransformationMatrix tm(nd_to_mmatrix(a));
    double s[3];
    tm.getScale(s, MSpace::kTransform);
    return nd_triple(s[0], s[1], s[2]);
}

inline nd::Array<double> xf_shear(const nd::Array<double>& a) {
    MTransformationMatrix tm(nd_to_mmatrix(a));
    double s[3];
    tm.getShear(s, MSpace::kTransform);
    return nd_triple(s[0], s[1], s[2]);
}

// .rotationOrder() -> plain int. Mirrors the Python exactly, INCLUDING that
// this is MTransformationMatrix's 1-based enum (kXYZ == 1) and not the 0-based
// index xf_rotation takes. Matching the interpreted node beats being
// self-consistent.
inline int64_t xf_rotation_order(const nd::Array<double>& a) {
    MTransformationMatrix tm(nd_to_mmatrix(a));
    return (int64_t)tm.rotationOrder();
}

inline nd::Array<double> xf_as_rotate_matrix(const nd::Array<double>& a) {
    return mmatrix_to_nd(MTransformationMatrix(nd_to_mmatrix(a)).asRotateMatrix());
}

inline nd::Array<double> xf_as_scale_matrix(const nd::Array<double>& a) {
    return mmatrix_to_nd(MTransformationMatrix(nd_to_mmatrix(a)).asScaleMatrix());
}

inline nd::Array<double> xf_as_matrix_inverse(const nd::Array<double>& a) {
    return mmatrix_to_nd(MTransformationMatrix(nd_to_mmatrix(a)).asMatrixInverse());
}

// MMatrix::isSingular carries Maya's own tolerance; det4x4()==0 is NOT the
// same predicate, so this goes through Maya rather than being derived.
inline bool xf_is_singular(const nd::Array<double>& a) {
    return nd_to_mmatrix(a).isSingular();
}

inline nd::Array<double> xf_adjoint(const nd::Array<double>& a) {
    return mmatrix_to_nd(nd_to_mmatrix(a).adjoint());
}

inline nd::Array<double> xf_homogenize(const nd::Array<double>& a) {
    return mmatrix_to_nd(nd_to_mmatrix(a).homogenize());
}

}  // namespace ndx
#endif  // ND_MAYA_XFORM_H
"""
