// mPyMeshSDF -- hand-port of mpynode/_common/sdf_dmc.py to C++.
//
// A DG node that folds an ORDERED stream of SDF primitives (sphere/box/
// cylinder) with CSG (union / smooth-union / difference) and extracts a
// quad-dominant mesh via dual marching cubes -- a faithful translation of
// the pure-numpy reference so it reproduces the same field bit-for-bit
// (within float tolerance) while running far faster + handling denser grids.
//
// The math mirrors sdf_dmc.py exactly: decompose_matrix, affine_inverse,
// sample_shape, the three eval_* primitives, the CSG ops, effective_bounds,
// make_grid, and dual_marching_cubes (same corner-bit classification, same
// lexicographic active-cube ordering, same owned-edge (0,3,8) faces +
// gradient winding).

#include <maya/MPxNode.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnNumericAttribute.h>
#include <maya/MFnMatrixAttribute.h>
#include <maya/MFnTypedAttribute.h>
#include <maya/MFnNumericData.h>
#include <maya/MFnData.h>
#include <maya/MFnMesh.h>
#include <maya/MFnMeshData.h>
#include <maya/MPointArray.h>
#include <maya/MIntArray.h>
#include <maya/MMatrix.h>
#include <maya/MTypeId.h>
#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>
#include <maya/MArrayDataHandle.h>
#include <maya/MGlobal.h>

#include <vector>
#include <array>
#include <cmath>
#include <cstdint>
#include <algorithm>

// ---------------------------------------------------------------------------
// SDF primitives + CSG (verbatim ports of sdf_dmc.py)
// ---------------------------------------------------------------------------

static inline double eval_sphere(double x, double y, double z, double r) {
    return std::sqrt(x * x + y * y + z * z) - r;
}

static inline double eval_box(double x, double y, double z, const double h[3]) {
    double dx = std::fabs(x) - h[0];
    double dy = std::fabs(y) - h[1];
    double dz = std::fabs(z) - h[2];
    double mx = std::max(dx, 0.0), my = std::max(dy, 0.0), mz = std::max(dz, 0.0);
    double outside = std::sqrt(mx * mx + my * my + mz * mz);
    double inside = std::min(std::max(dx, std::max(dy, dz)), 0.0);
    return outside + inside;
}

static inline double eval_cylinder(double x, double y, double z,
                                   double radius, double height, int axis) {
    double c[3] = {x, y, z};
    double half_h = height / 2.0;
    int r0 = -1, r1 = -1;
    for (int i = 0; i < 3; ++i) {
        if (i == axis) continue;
        if (r0 < 0) r0 = i; else r1 = i;
    }
    double d_radial = std::sqrt(c[r0] * c[r0] + c[r1] * c[r1]) - radius;
    double d_height = std::fabs(c[axis]) - half_h;
    double mr = std::max(d_radial, 0.0), mh = std::max(d_height, 0.0);
    return std::sqrt(mr * mr + mh * mh) + std::min(std::max(d_radial, d_height), 0.0);
}

static inline double sdf_union(double a, double b) { return std::min(a, b); }
static inline double sdf_difference(double a, double b) { return std::max(a, -b); }
static inline double sdf_smooth_union(double a, double b, double k) {
    double h = 0.5 + 0.5 * (b - a) / k;
    h = std::min(std::max(h, 0.0), 1.0);
    return b * (1.0 - h) + a * h - k * h * (1.0 - h);
}

// ---------------------------------------------------------------------------
// Per-shape precompute (decompose_matrix + affine_inverse of the rigid frame)
// ---------------------------------------------------------------------------

struct Shape {
    int type;            // 0 sphere, 1 box, 2 cylinder
    double radius, height;
    int axis;
    double half[3];
    double scale[3];     // raw per-axis scale (row norms)
    double min_scale;
    double inv[3][3];     // rigid_inverse upper 3x3 (column c = inv[*][c])
    double inv_t[3];      // rigid_inverse translation row
};

// MMatrix is row-major: M(r,c). Maya row-vector convention -> M3 = diag(scale)@R,
// translate in row 3 -- matches sdf_dmc.decompose_matrix.
static Shape precompute(const MMatrix& M, int type, double radius,
                        double height, int axis, const double half[3]) {
    Shape s;
    s.type = type; s.radius = radius; s.height = height; s.axis = axis;
    s.half[0] = half[0]; s.half[1] = half[1]; s.half[2] = half[2];

    double R[3][3];
    for (int r = 0; r < 3; ++r) {
        double sq = M(r, 0) * M(r, 0) + M(r, 1) * M(r, 1) + M(r, 2) * M(r, 2);
        double sc = std::sqrt(sq);
        s.scale[r] = sc;
        double safe = (sc == 0.0) ? 1.0 : sc;
        R[r][0] = M(r, 0) / safe;
        R[r][1] = M(r, 1) / safe;
        R[r][2] = M(r, 2) / safe;
    }
    double t0 = M(3, 0), t1 = M(3, 1), t2 = M(3, 2);
    s.min_scale = std::min(std::fabs(s.scale[0]),
                           std::min(std::fabs(s.scale[1]), std::fabs(s.scale[2])));

    // affine_inverse of rigid (R upper, translate row3). Row sq-norms (=1).
    double sx = R[0][0]*R[0][0] + R[0][1]*R[0][1] + R[0][2]*R[0][2];
    double sy = R[1][0]*R[1][0] + R[1][1]*R[1][1] + R[1][2]*R[1][2];
    double sz = R[2][0]*R[2][0] + R[2][1]*R[2][1] + R[2][2]*R[2][2];
    double i00 = R[0][0]/sx, i01 = R[1][0]/sy, i02 = R[2][0]/sz;
    double i10 = R[0][1]/sx, i11 = R[1][1]/sy, i12 = R[2][1]/sz;
    double i20 = R[0][2]/sx, i21 = R[1][2]/sy, i22 = R[2][2]/sz;
    s.inv[0][0]=i00; s.inv[0][1]=i01; s.inv[0][2]=i02;
    s.inv[1][0]=i10; s.inv[1][1]=i11; s.inv[1][2]=i12;
    s.inv[2][0]=i20; s.inv[2][1]=i21; s.inv[2][2]=i22;
    s.inv_t[0] = -(t0*i00 + t1*i10 + t2*i20);
    s.inv_t[1] = -(t0*i01 + t1*i11 + t2*i21);
    s.inv_t[2] = -(t0*i02 + t1*i12 + t2*i22);
    return s;
}

// sample_shape: world point -> local (rigid_inv) -> /scale -> eval -> *min_scale.
static inline double sample(const Shape& s, double px, double py, double pz) {
    double lx = px*s.inv[0][0] + py*s.inv[1][0] + pz*s.inv[2][0] + s.inv_t[0];
    double ly = px*s.inv[0][1] + py*s.inv[1][1] + pz*s.inv[2][1] + s.inv_t[1];
    double lz = px*s.inv[0][2] + py*s.inv[1][2] + pz*s.inv[2][2] + s.inv_t[2];
    lx /= s.scale[0]; ly /= s.scale[1]; lz /= s.scale[2];
    double d;
    if (s.type == 1)      d = eval_box(lx, ly, lz, s.half);
    else if (s.type == 2) d = eval_cylinder(lx, ly, lz, s.radius, s.height, s.axis);
    else                  d = eval_sphere(lx, ly, lz, s.radius);
    return d * s.min_scale;
}

// shape_bounding_box -> world AABB (port of SDFx.bounding_box).
static void shape_bbox(const MMatrix& M, int type, double radius, double height,
                       int axis, const double half[3],
                       double outMin[3], double outMax[3]) {
    double R[3][3], scale[3], translate[3];
    for (int r = 0; r < 3; ++r) {
        double sq = M(r,0)*M(r,0) + M(r,1)*M(r,1) + M(r,2)*M(r,2);
        double sc = std::sqrt(sq);
        scale[r] = sc;
        double safe = (sc == 0.0) ? 1.0 : sc;
        R[r][0]=M(r,0)/safe; R[r][1]=M(r,1)/safe; R[r][2]=M(r,2)/safe;
    }
    translate[0]=M(3,0); translate[1]=M(3,1); translate[2]=M(3,2);
    double lh[3];
    if (type == 1) {
        lh[0]=half[0]*scale[0]; lh[1]=half[1]*scale[1]; lh[2]=half[2]*scale[2];
    } else if (type == 2) {
        double base[3] = {radius, radius, radius};
        base[axis] = height / 2.0;
        lh[0]=base[0]*scale[0]; lh[1]=base[1]*scale[1]; lh[2]=base[2]*scale[2];
    } else {
        lh[0]=radius*scale[0]; lh[1]=radius*scale[1]; lh[2]=radius*scale[2];
    }
    // world_half[r] = sum_c |R[c][r]| * lh[c]   (Rb = R^T)
    for (int r = 0; r < 3; ++r) {
        double wh = std::fabs(R[0][r])*lh[0] + std::fabs(R[1][r])*lh[1]
                  + std::fabs(R[2][r])*lh[2];
        outMin[r] = translate[r] - wh;
        outMax[r] = translate[r] + wh;
    }
}

// ---------------------------------------------------------------------------
// The node
// ---------------------------------------------------------------------------

class MPyMeshSDF : public MPxNode {
public:
    MPyMeshSDF() {}
    ~MPyMeshSDF() override {}
    static void* creator() { return new MPyMeshSDF(); }
    static MStatus initialize();
    MStatus compute(const MPlug& plug, MDataBlock& data) override;

    static MTypeId id;
    static MObject aShapeMatrix, aShapeType, aAdditive, aSmoothing, aRadius;
    static MObject aHeight, aAxis, aHalfExtents, aResolution, aIsoValue, aOutMesh;
};

MTypeId MPyMeshSDF::id(0x00076d05);
MObject MPyMeshSDF::aShapeMatrix;
MObject MPyMeshSDF::aShapeType;
MObject MPyMeshSDF::aAdditive;
MObject MPyMeshSDF::aSmoothing;
MObject MPyMeshSDF::aRadius;
MObject MPyMeshSDF::aHeight;
MObject MPyMeshSDF::aAxis;
MObject MPyMeshSDF::aHalfExtents;
MObject MPyMeshSDF::aResolution;
MObject MPyMeshSDF::aIsoValue;
MObject MPyMeshSDF::aOutMesh;

MStatus MPyMeshSDF::initialize() {
    MFnNumericAttribute nAttr;
    MFnMatrixAttribute  mAttr;
    MFnTypedAttribute   tAttr;

    aShapeMatrix = mAttr.create("shapeMatrix", "sm", MFnMatrixAttribute::kDouble);
    mAttr.setArray(true); mAttr.setStorable(true); mAttr.setKeyable(true);
    addAttribute(aShapeMatrix);

    aShapeType = nAttr.create("shapeType", "st", MFnNumericData::kInt, 0);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aShapeType);

    aAdditive = nAttr.create("additive", "ad", MFnNumericData::kBoolean, 1);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aAdditive);

    aSmoothing = nAttr.create("smoothing", "sg", MFnNumericData::kDouble, 0.0);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aSmoothing);

    aRadius = nAttr.create("radius", "rd", MFnNumericData::kDouble, 1.0);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aRadius);

    aHeight = nAttr.create("height", "hg", MFnNumericData::kDouble, 1.0);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aHeight);

    aAxis = nAttr.create("axis", "ax", MFnNumericData::kInt, 1);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aAxis);

    aHalfExtents = nAttr.create("halfExtents", "he", MFnNumericData::k3Double);
    nAttr.setArray(true); nAttr.setStorable(true); nAttr.setKeyable(true);
    nAttr.setDefault(0.5, 0.5, 0.5);
    addAttribute(aHalfExtents);

    aResolution = nAttr.create("resolution", "rs", MFnNumericData::kInt, 8);
    nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aResolution);

    aIsoValue = nAttr.create("isoValue", "iv", MFnNumericData::kDouble, 0.0);
    nAttr.setStorable(true); nAttr.setKeyable(true);
    addAttribute(aIsoValue);

    aOutMesh = tAttr.create("outMesh", "out", MFnData::kMesh);
    tAttr.setStorable(false); tAttr.setWritable(false); tAttr.setReadable(true);
    addAttribute(aOutMesh);

    MObject ins[] = {aShapeMatrix, aShapeType, aAdditive, aSmoothing, aRadius,
                     aHeight, aAxis, aHalfExtents, aResolution, aIsoValue};
    for (MObject& a : ins) attributeAffects(a, aOutMesh);
    return MS::kSuccess;
}

MStatus MPyMeshSDF::compute(const MPlug& plug, MDataBlock& data) {
    if (plug != aOutMesh) return MS::kUnknownParameter;

    // --- read shapeMatrix into a logical-index-keyed vector ---
    std::vector<MMatrix> mats;
    {
        MStatus st;
        MArrayDataHandle ah = data.inputArrayValue(aShapeMatrix, &st);
        if (st) {
            unsigned cnt = ah.elementCount();
            for (unsigned e = 0; e < cnt; ++e) {
                unsigned li = ah.elementIndex();
                if (li >= mats.size()) mats.resize(li + 1);
                mats[li] = ah.inputValue().asMatrix();
                ah.next();
            }
        }
    }
    int n = (int)mats.size();

    MFnMeshData meshData;
    MObject newMesh = meshData.create();

    if (n > 0) {
        // --- per-shape arrays, defaulted then overwritten by logical index ---
        std::vector<int>    stype(n, 0);
        std::vector<int>    addv(n, 1);
        std::vector<double> smooth(n, 0.0);
        std::vector<double> radius(n, 1.0);
        std::vector<double> height(n, 1.0);
        std::vector<int>    axis(n, 1);
        std::vector<std::array<double,3>> half(n, {0.5, 0.5, 0.5});

        auto readInt = [&](MObject a, std::vector<int>& v) {
            MStatus st; MArrayDataHandle ah = data.inputArrayValue(a, &st);
            if (!st) return; unsigned cnt = ah.elementCount();
            for (unsigned e = 0; e < cnt; ++e) {
                unsigned li = ah.elementIndex();
                if ((int)li < n) v[li] = ah.inputValue().asInt();
                ah.next();
            }
        };
        auto readBool = [&](MObject a, std::vector<int>& v) {
            MStatus st; MArrayDataHandle ah = data.inputArrayValue(a, &st);
            if (!st) return; unsigned cnt = ah.elementCount();
            for (unsigned e = 0; e < cnt; ++e) {
                unsigned li = ah.elementIndex();
                if ((int)li < n) v[li] = ah.inputValue().asBool() ? 1 : 0;
                ah.next();
            }
        };
        auto readDbl = [&](MObject a, std::vector<double>& v) {
            MStatus st; MArrayDataHandle ah = data.inputArrayValue(a, &st);
            if (!st) return; unsigned cnt = ah.elementCount();
            for (unsigned e = 0; e < cnt; ++e) {
                unsigned li = ah.elementIndex();
                if ((int)li < n) v[li] = ah.inputValue().asDouble();
                ah.next();
            }
        };

        readInt(aShapeType, stype);
        readBool(aAdditive, addv);
        readDbl(aSmoothing, smooth);
        // radius default depends on type (cylinder 0.5 else 1.0).
        for (int i = 0; i < n; ++i) radius[i] = (stype[i] == 2) ? 0.5 : 1.0;
        readDbl(aRadius, radius);
        readDbl(aHeight, height);
        readInt(aAxis, axis);
        {
            MStatus st; MArrayDataHandle ah = data.inputArrayValue(aHalfExtents, &st);
            if (st) {
                unsigned cnt = ah.elementCount();
                for (unsigned e = 0; e < cnt; ++e) {
                    unsigned li = ah.elementIndex();
                    if ((int)li < n) {
                        double3& v = ah.inputValue().asDouble3();
                        half[li] = {v[0], v[1], v[2]};
                    }
                    ah.next();
                }
            }
        }

        int res = data.inputValue(aResolution).asInt();
        double iso = data.inputValue(aIsoValue).asDouble();

        // --- precompute shapes ---
        std::vector<Shape> shapes;
        shapes.reserve(n);
        for (int i = 0; i < n; ++i) {
            shapes.push_back(precompute(mats[i], stype[i], radius[i], height[i],
                                        axis[i], half[i].data()));
        }

        // --- effective_bounds (all shapes, 10% pad) ---
        double mn[3] = {1e300, 1e300, 1e300};
        double mx[3] = {-1e300, -1e300, -1e300};
        for (int i = 0; i < n; ++i) {
            double bmn[3], bmx[3];
            shape_bbox(mats[i], stype[i], radius[i], height[i], axis[i],
                       half[i].data(), bmn, bmx);
            for (int d = 0; d < 3; ++d) {
                mn[d] = std::min(mn[d], bmn[d]);
                mx[d] = std::max(mx[d], bmx[d]);
            }
        }
        double lo[3], hi[3], ext[3];
        for (int d = 0; d < 3; ++d) {
            double e = mx[d] - mn[d];
            double pad = e * 0.1;
            lo[d] = mn[d] - pad;
            hi[d] = mx[d] + pad;
            ext[d] = hi[d] - lo[d];
        }

        // --- grid shape = max(2, ceil(extent * res)) ---
        int nx = std::max(2, (int)std::ceil(ext[0] * (double)res));
        int ny = std::max(2, (int)std::ceil(ext[1] * (double)res));
        int nz = std::max(2, (int)std::ceil(ext[2] * (double)res));
        double sxp = (hi[0]-lo[0]) / (double)(nx - 1);
        double syp = (hi[1]-lo[1]) / (double)(ny - 1);
        double szp = (hi[2]-lo[2]) / (double)(nz - 1);

        // --- sample + CSG-fold the field (field[(i*ny+j)*nz+k]) ---
        std::vector<double> field((size_t)nx * ny * nz);
        for (int i = 0; i < nx; ++i) {
            double x = lo[0] + (double)i * sxp;     // linspace endpoint-exact below
            // match np.linspace: value = lo + i*(hi-lo)/(N-1); for i==N-1 use hi.
            x = (i == nx - 1) ? hi[0] : lo[0] + (double)i * sxp;
            for (int j = 0; j < ny; ++j) {
                double y = (j == ny - 1) ? hi[1] : lo[1] + (double)j * syp;
                for (int k = 0; k < nz; ++k) {
                    double z = (k == nz - 1) ? hi[2] : lo[2] + (double)k * szp;
                    double c = sample(shapes[0], x, y, z);
                    for (int s = 1; s < n; ++s) {
                        double d = sample(shapes[s], x, y, z);
                        if (addv[s]) {
                            if (smooth[s] > 0.0) c = sdf_smooth_union(c, d, smooth[s]);
                            else                 c = sdf_union(c, d);
                        } else {
                            c = sdf_difference(c, d);
                        }
                    }
                    field[((size_t)i * ny + j) * nz + k] = c;
                }
            }
        }

        // --- dual marching cubes ---
        static const uint16_t edge_table[256] = {
            0x000,0x109,0x203,0x30a,0x406,0x50f,0x605,0x70c,0x80c,0x905,0xa0f,0xb06,0xc0a,0xd03,0xe09,0xf00,
            0x190,0x099,0x393,0x29a,0x596,0x49f,0x795,0x69c,0x99c,0x895,0xb9f,0xa96,0xd9a,0xc93,0xf99,0xe90,
            0x230,0x339,0x033,0x13a,0x636,0x73f,0x435,0x53c,0xa3c,0xb35,0x83f,0x936,0xe3a,0xf33,0xc39,0xd30,
            0x3a0,0x2a9,0x1a3,0x0aa,0x7a6,0x6af,0x5a5,0x4ac,0xbac,0xaa5,0x9af,0x8a6,0xfaa,0xea3,0xda9,0xca0,
            0x460,0x569,0x663,0x76a,0x066,0x16f,0x265,0x36c,0xc6c,0xd65,0xe6f,0xf66,0x86a,0x963,0xa69,0xb60,
            0x5f0,0x4f9,0x7f3,0x6fa,0x1f6,0x0ff,0x3f5,0x2fc,0xdfc,0xcf5,0xfff,0xef6,0x9fa,0x8f3,0xbf9,0xaf0,
            0x650,0x759,0x453,0x55a,0x256,0x35f,0x055,0x15c,0xe5c,0xf55,0xc5f,0xd56,0xa5a,0xb53,0x859,0x950,
            0x7c0,0x6c9,0x5c3,0x4ca,0x3c6,0x2cf,0x1c5,0x0cc,0xfcc,0xec5,0xdcf,0xcc6,0xbca,0xac3,0x9c9,0x8c0,
            0x8c0,0x9c9,0xac3,0xbca,0xcc6,0xdcf,0xec5,0xfcc,0x0cc,0x1c5,0x2cf,0x3c6,0x4ca,0x5c3,0x6c9,0x7c0,
            0x950,0x859,0xb53,0xa5a,0xd56,0xc5f,0xf55,0xe5c,0x15c,0x055,0x35f,0x256,0x55a,0x453,0x759,0x650,
            0xaf0,0xbf9,0x8f3,0x9fa,0xef6,0xfff,0xcf5,0xdfc,0x2fc,0x3f5,0x0ff,0x1f6,0x6fa,0x7f3,0x4f9,0x5f0,
            0xb60,0xa69,0x963,0x86a,0xf66,0xe6f,0xd65,0xc6c,0x36c,0x265,0x16f,0x066,0x76a,0x663,0x569,0x460,
            0xca0,0xda9,0xea3,0xfaa,0x8a6,0x9af,0xaa5,0xbac,0x4ac,0x5a5,0x6af,0x7a6,0x0aa,0x1a3,0x2a9,0x3a0,
            0xd30,0xc39,0xf33,0xe3a,0x936,0x83f,0xb35,0xa3c,0x53c,0x435,0x73f,0x636,0x13a,0x033,0x339,0x230,
            0xe90,0xf99,0xc93,0xd9a,0xa96,0xb9f,0x895,0x99c,0x69c,0x795,0x49f,0x596,0x29a,0x393,0x099,0x190,
            0xf00,0xe09,0xd03,0xc0a,0xb06,0xa0f,0x905,0x80c,0x70c,0x605,0x50f,0x406,0x30a,0x203,0x109,0x000,
        };
        static const int edge_vertices[12][2] = {
            {0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}
        };
        static const int corner_offsets[8][3] = {
            {0,0,0},{1,0,0},{1,1,0},{0,1,0},{0,0,1},{1,0,1},{1,1,1},{0,1,1}
        };
        static const int edge_axis[12] = {0,1,0,1,0,1,0,1,2,2,2,2};
        static const int face_off_x[4][3] = {{0,0,0},{0,-1,0},{0,-1,-1},{0,0,-1}};
        static const int face_off_y[4][3] = {{0,0,0},{-1,0,0},{-1,0,-1},{0,0,-1}};
        static const int face_off_z[4][3] = {{0,0,0},{-1,0,0},{-1,-1,0},{0,-1,0}};
        static const int owned_edges[3] = {0, 3, 8};

        int cx = nx - 1, cy = ny - 1, cz = nz - 1;
        if (cx > 0 && cy > 0 && cz > 0) {
            auto FIDX = [&](int i, int j, int k) {
                return ((size_t)i * ny + j) * nz + k;
            };
            auto CIDX = [&](int i, int j, int k) {
                return ((size_t)i * cy + j) * cz + k;
            };
            // classify cubes
            std::vector<uint8_t> config((size_t)cx * cy * cz, 0);
            for (int i = 0; i < cx; ++i)
            for (int j = 0; j < cy; ++j)
            for (int k = 0; k < cz; ++k) {
                uint8_t cfg = 0;
                if (field[FIDX(i,   j,   k  )] >= iso) cfg |= 1;
                if (field[FIDX(i+1, j,   k  )] >= iso) cfg |= 2;
                if (field[FIDX(i+1, j+1, k  )] >= iso) cfg |= 4;
                if (field[FIDX(i,   j+1, k  )] >= iso) cfg |= 8;
                if (field[FIDX(i,   j,   k+1)] >= iso) cfg |= 16;
                if (field[FIDX(i+1, j,   k+1)] >= iso) cfg |= 32;
                if (field[FIDX(i+1, j+1, k+1)] >= iso) cfg |= 64;
                if (field[FIDX(i,   j+1, k+1)] >= iso) cfg |= 128;
                config[CIDX(i,j,k)] = cfg;
            }
            // active cubes in lexicographic (i,j,k) order
            std::vector<int> ai, aj, ak;
            std::vector<int> cube_to_vertex((size_t)cx * cy * cz, -1);
            for (int i = 0; i < cx; ++i)
            for (int j = 0; j < cy; ++j)
            for (int k = 0; k < cz; ++k) {
                uint8_t cfg = config[CIDX(i,j,k)];
                if (cfg > 0 && cfg < 255) {
                    cube_to_vertex[CIDX(i,j,k)] = (int)ai.size();
                    ai.push_back(i); aj.push_back(j); ak.push_back(k);
                }
            }
            int nActive = (int)ai.size();

            MPointArray pts;
            for (int a = 0; a < nActive; ++a) {
                int i = ai[a], j = aj[a], k = ak[a];
                uint8_t cfg = config[CIDX(i,j,k)];
                uint16_t eb = edge_table[cfg];
                double sx=0, sy=0, sz=0; int count=0;
                for (int e = 0; e < 12; ++e) {
                    if (!(eb & (1 << e))) continue;
                    int c0 = edge_vertices[e][0], c1 = edge_vertices[e][1];
                    const int* o0 = corner_offsets[c0];
                    const int* o1 = corner_offsets[c1];
                    double v0 = field[FIDX(i+o0[0], j+o0[1], k+o0[2])];
                    double v1 = field[FIDX(i+o1[0], j+o1[1], k+o1[2])];
                    double dv = v1 - v0;
                    double t = (std::fabs(dv) < 1e-10) ? 0.5 : (iso - v0) / dv;
                    double p0x = lo[0] + (i+o0[0]) * sxp, p1x = lo[0] + (i+o1[0]) * sxp;
                    double p0y = lo[1] + (j+o0[1]) * syp, p1y = lo[1] + (j+o1[1]) * syp;
                    double p0z = lo[2] + (k+o0[2]) * szp, p1z = lo[2] + (k+o1[2]) * szp;
                    sx += p0x + t * (p1x - p0x);
                    sy += p0y + t * (p1y - p0y);
                    sz += p0z + t * (p1z - p0z);
                    ++count;
                }
                if (count > 0) {
                    double inv = 1.0 / count;
                    pts.append(MPoint(sx*inv, sy*inv, sz*inv));
                } else {
                    pts.append(MPoint(lo[0]+(i+0.5)*sxp, lo[1]+(j+0.5)*syp,
                                      lo[2]+(k+0.5)*szp));
                }
            }

            // faces: owned edges (0,3,8), gradient winding
            MIntArray counts, connects;
            for (int a = 0; a < nActive; ++a) {
                int i = ai[a], j = aj[a], k = ak[a];
                uint8_t cfg = config[CIDX(i,j,k)];
                uint16_t eb = edge_table[cfg];
                for (int oe = 0; oe < 3; ++oe) {
                    int e = owned_edges[oe];
                    if (!(eb & (1 << e))) continue;
                    int ax = edge_axis[e];
                    const int (*offs)[3] = (ax==0) ? face_off_x
                                         : (ax==1) ? face_off_y : face_off_z;
                    int vi[4]; bool valid = true;
                    for (int ni = 0; ni < 4; ++ni) {
                        int ci = i + offs[ni][0];
                        int cj = j + offs[ni][1];
                        int ck = k + offs[ni][2];
                        if (ci<0||ci>=cx||cj<0||cj>=cy||ck<0||ck>=cz) { valid=false; break; }
                        int vm = cube_to_vertex[CIDX(ci,cj,ck)];
                        if (vm < 0) { valid=false; break; }
                        vi[ni] = vm;
                    }
                    if (!valid) continue;
                    int c0 = edge_vertices[e][0], c1 = edge_vertices[e][1];
                    const int* o0 = corner_offsets[c0];
                    const int* o1 = corner_offsets[c1];
                    double v0 = field[FIDX(i+o0[0], j+o0[1], k+o0[2])];
                    double v1 = field[FIDX(i+o1[0], j+o1[1], k+o1[2])];
                    counts.append(4);
                    if (v0 < v1) {
                        connects.append(vi[0]); connects.append(vi[1]);
                        connects.append(vi[2]); connects.append(vi[3]);
                    } else {
                        connects.append(vi[3]); connects.append(vi[2]);
                        connects.append(vi[1]); connects.append(vi[0]);
                    }
                }
            }

            if (pts.length() > 0 && counts.length() > 0) {
                MFnMesh fnMesh;
                fnMesh.create((int)pts.length(), (int)counts.length(),
                              pts, counts, connects, newMesh);
            }
        }
    }

    MDataHandle hOut = data.outputValue(aOutMesh);
    hOut.setMObject(newMesh);
    hOut.setClean();
    data.setClean(plug);
    return MS::kSuccess;
}

MStatus initializePlugin(MObject obj) {
    MFnPlugin plugin(obj, "mpynode-native-handport", "1.0", "Any");
    return plugin.registerNode("mPyMeshSDF", MPyMeshSDF::id,
                               MPyMeshSDF::creator, MPyMeshSDF::initialize);
}
MStatus uninitializePlugin(MObject obj) {
    MFnPlugin plugin(obj);
    return plugin.deregisterNode(MPyMeshSDF::id);
}
