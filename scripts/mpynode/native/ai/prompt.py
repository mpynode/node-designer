"""LLM system prompts + prompt assembly for the AI porter.

The system prompts (one per node family), the geo-family prompt composer, the
followed-helper translation prompt, and the ``build_prompt`` / ``splice_body`` /
``_strip_fences`` helpers that assemble the user prompt and splice the AI's C++
body back into the codegen skeleton.
"""

from __future__ import annotations

import os
import re

from mpynode.native import compiler as codegen
from mpynode.native.ai import translation_knowledge


# ---------------------------------------------------------------------------
# Prompt + splice
# ---------------------------------------------------------------------------

_SYSTEM = """\
You port a Maya custom-node's Python compute expression into C++ for a native
MPxNode. You are given the original Python and a C++ scaffold. Output ONLY the
C++ statements that go between the BEGIN/END PORTED COMPUTE markers -- no
function signature, no #includes, no markdown fences, no commentary.

Rules:
- Read inputs from the pre-declared `in_<name>` locals (already in scope).
- Write EVERY output through its pre-declared handle `h_<name>` using the
  setter shown in the scaffold (e.g. h_out.setFloat(x)). Do not redeclare them.
- Matrix inputs are MMatrix; vectors are double3 (index [0],[1],[2]); angles
  and times are doubles (radians / seconds).
- Use <cmath>, MVector, MMatrix, MEulerRotation, MQuaternion as needed.
- Pure compute only: NO maya.cmds, NO file/scene/network access, no I/O.
- If the Python relies on numpy, reproduce the math with plain loops / MMatrix.
- Keep it deterministic and self-contained."""

# Deformer family overrides the output contract: there are no `h_<name>` output
# handles -- the deformation happens by mutating the point array in place.
_SYSTEM_DEFORMER = """\
You port a Maya custom DEFORMER's Python compute into C++ for a native
MPxDeformerNode/MPxSkinCluster. You are given the original Python and a C++
scaffold. Output ONLY the C++ statements between the BEGIN/END PORTED COMPUTE
markers -- no function signature, no #includes, no markdown fences, no commentary.

Rules:
- The geometry is the `MPointArray pts` (length `n`), already filled with the
  object-space vertices. DEFORM by mutating pts[i] in place; do not redeclare it.
- `env` (float) is the deformer envelope (0..1). Per-vertex painted weight is
  `weightValue(block, multiIndex, i)`. Honour both as the original Python did
  (the Python `self.outputGeometry[0].getPoints()/setPoints()` <-> pts).
- Read user inputs from the pre-declared `in_<name>` locals (already in scope).
- `adjStart`/`adjNbr` (std::vector<int>) are the CSR 1-ring vertex adjacency:
  neighbors of pts[i] are adjNbr[adjStart[i] .. adjStart[i+1]). Use them for
  Laplacian / Taubin / umbrella relaxation, e.g.
    MVector avg(0,0,0); int s0=adjStart[i],s1=adjStart[i+1];
    for(int k=s0;k<s1;++k) avg+=MVector(pts[adjNbr[k]]);
    if(s1>s0) avg=avg*(1.0/(s1-s0));
  If adjNbr is empty (topology unavailable) leave pts[i] unchanged.
- numba: drop @njit/@guvectorize/prange and write plain loops. A prange step is
  JACOBI -- read a source buffer, write a SEPARATE destination buffer, then swap.
  Do NOT smooth in place (that is Gauss-Seidel and gives different numbers).
- Skin only: `jointMat[j]` is influence j's world MMatrix, `bindPre[j]` its
  bind-pose inverse; per-influence weights are in the inherited
  MPxSkinCluster::weightList[i].weights[j] plug (read via MArrayDataHandle if
  needed). There are NO `h_<name>` output handles.
- Matrix inputs are MMatrix; vectors are double3 ([0],[1],[2]); angles/times are
  doubles (radians/seconds). MPoint supports `p * matrix`.
- Pure math only: NO maya.cmds, NO file/scene/network access, no I/O.
- If the Python relies on numpy, reproduce the math with plain loops / MMatrix.
- Keep it deterministic and self-contained."""


# IK solver: the output contract is per-joint desired matrices (LOCAL or WORLD)
# applied via offsetParentMatrix, NOT euler angles / h_<name> handles / a point
# array. The doSolve() marshalling is fixed; the AI ports only the solve math.
_SYSTEM_IKSOLVER = """\
You port a Maya custom IK solver's Python solve expression into C++ for a native
MPxIkSolverNode. You are given the original Python and a C++ scaffold. Output
ONLY the C++ statements between the BEGIN/END PORTED COMPUTE markers -- no
function signature, no #includes, no markdown fences, no commentary.

The scaffold has ALREADY marshalled the IK context into these locals (in scope):
- int numJoints
- std::vector<MMatrix> bindWorld    -- bindWorld[j] = joint j REST WORLD matrix
                                       (row-vector Maya; STABLE reference pose,
                                       includes the bind offset). m(row,col):
                                       rows 0..2 = basis axes, row 3 = translation.
- std::vector<MMatrix> jointLocal   -- jointLocal[j] = joint j REST LOCAL
                                       (parent-relative) matrix.
- std::vector<MVector> jointPos     -- jointPos[j] = bindWorld[j] translation
- MVector endEffector               -- the IK handle's world target position
- MVector poleVector                -- the handle's pole vector
- double  twist                     -- the handle's twist attribute
- std::vector<MMatrix> outWorldMat  -- OUTPUT: per-joint desired WORLD (absolute)
                                       matrix; pre-seeded to bindWorld[j].
- std::vector<char>    outWorldSet  -- OUTPUT: set outWorldSet[j]=1 for each joint
                                       you drive in WORLD space.
- std::vector<MMatrix> outLocalMat  -- OUTPUT: per-joint desired LOCAL
                                       (parent-relative) matrix; pre-seeded to the
                                       rest parent-relative.
- std::vector<char>    outLocalSet  -- OUTPUT: set outLocalSet[j]=1 for each joint
                                       you drive in LOCAL space. Leave BOTH *Set 0
                                       to leave a joint at rest. A written matrix
                                       does nothing unless its flag is set; if both
                                       are set for a joint, WORLD wins.
- std::vector<char> applyRotate, applyTranslate, applyScale -- OUTPUT per-joint
                                       gates (default 1,0,0): which channels of the
                                       desired matrix drive joint j. Ungated
                                       channels come from the joint's rest pose, so
                                       rotate-only reorients in place.

USER INPUTS (if the solver node declares them) are also in scope:
- scalar input X (float/double/int/bool/enum): local `in_X`. Map BOTH self.X and
  bare X to in_X. For an enum X there is also `in_X_name` (std::string field name)
  -- map self.X.name()/string compares to in_X_name (compare with ==).
- mesh input M (a floor/collision surface): local `RegionMesh M` (WORLD space).
  M.present is the connected flag; M.pts (std::vector<MPoint>) the world vertices;
  M.normals aligns to M.pts. Query the nearest surface point + its normal with:
     int v = rm_closestVertex(M, somePoint); MVector nrm = rm_normalAt(M, v);
  (Use these to keep a joint/effector above the surface along the normal.)

Map the Python contract to these locals:
- self.joints[i]["world_position"]     -> jointPos[i]   (an MVector; .x/.y/.z, length())
- self.joints[i]["world_matrix"]       -> bindWorld[i]  (an MMatrix; rest world)
- self.joints[i]["matrix"]             -> jointLocal[i] (an MMatrix; rest local)
- self.end_effector                    -> endEffector
- self.pole_vector                     -> poleVector
- self.twist                           -> twist
- self.world_matrices[i] = M     -> outWorldMat[i] = M; outWorldSet[i] = 1;
- self.local_matrices[i] = M           -> outLocalMat[i] = M; outLocalSet[i] = 1;
- self.apply_rotate = b (scalar bool)  -> for all j: applyRotate[j] = b;
- self.apply_rotate = [b0,b1,...]      -> applyRotate[j] = bj; (same for translate/scale)
- self.<inputName>                     -> in_<inputName>
- self.<meshName>                      -> the RegionMesh <meshName>

Working with matrices (the Python builds numpy (4,4) matrices):
- Build an MMatrix from 16 doubles: double m[4][4] = {{r0x,r0y,r0z,0},{...},
  {...},{tx,ty,tz,1}}; MMatrix M(m);  (row 3 is translation; row-vector Maya).
- Read an element with M(row,col). A world direction rotates as v_row * R (row
  vector). To rotate the WHOLE frame of a matrix Wb by a rotation Rc whose COLUMN
  form maps a->b (Rc*a==b), the new rows are Wb.rows * Rc^T; the cleanest port is
  to compute basis rows directly from your aim vectors.
- A numpy 3x3 rotation assigned as M[0,:3]=xAxis; M[1,:3]=yAxis; M[2,:3]=zAxis
  maps to setting rows 0,1,2 of the MMatrix to those axis vectors.
- A Python `w @ delta` (numpy matmul, row-vector) maps to MMatrix `w * delta`.

Rules:
- MVector supports +, -, *scalar, ^ (cross), * (dot), .length(), .normal().
  MMatrix supports *, .inverse(), M(i,j). np.cross(a,b) -> (a ^ b); np.dot ->
  (a * b) for MVectors.
- Use <cmath> (std::sin/cos/acos/atan2/sqrt). Reproduce numpy with plain math.
- Set outWorldSet[j]=1 ONLY for joints the Python assigns via
  self.world_matrices[j], and outLocalSet[j]=1 ONLY for joints assigned via
  self.local_matrices[j]; leave the rest 0.
- If the Python computes a nearest point on the floor mesh, use rm_closestVertex/
  rm_normalAt (closest VERTEX) so the C++ and the Python match exactly.
- Pure math only: NO maya.cmds, NO file/scene/network access, no I/O.
- Keep it deterministic and self-contained."""


_SYSTEM_LOCATOR = """\
You port a Maya custom locator's Python DRAW expression into C++ for a native
MPxLocatorNode + MPxDrawOverride. You are given the original Python and a C++
scaffold. Output ONLY the C++ statements between the BEGIN/END PORTED COMPUTE
markers -- no function signature, no #includes, no markdown fences, no commentary.

DRAW STATE in scope (all already declared):
- double timeVal          -- current frame (self.time; self.time.asSeconds() == timeVal here)
- double wallClock        -- self.wallclock: seconds since the epoch, time.time() (0 in the
                             deterministic probe; map BOTH self.wallclock and time.time() -> wallClock)
- bool   selected, is_lead, hovered   -- self.selected / self.is_lead / self.hovered
- MColor selection_color  -- self.selection_color (r,g,b,a)
- <Data>& data            -- OUTPUT (data.reset() already called)

USER INPUT attrs (if the node has them) are declared as locals:
- scalar input X (float/int/bool/enum): local `in_X`. Map BOTH self.X and bare X to in_X.
  For an enum X there is also `in_X_name` (std::string, the field name) -- map self.X.name()
  to in_X_name (compare with ==, e.g. in_X_name == "face").
- mesh input M: local `RegionMesh M` (bare name). `M.present` is the connected flag.
  Build a region with:  RegionBuffer rb = extract_region(M, faceIds, withNormals);
  where faceIds is std::vector<int> and rb has .points (std::vector<MPoint>),
  .indices (std::vector<int>), .counts (std::vector<int>), .normals (std::vector<MVector>).
  This mirrors Python's extract_region(mesh, face_ids, with_normals=...).
  COMPONENT TAGS travel with M -- they are read off the mesh DATA when the input is
  read, so they need NO scene/plug query. Resolve a named tag with:
      std::vector<int> ids = tag_indices(M, tagName);   // empty if the tag is absent
  Map Python's mesh_data_from_node_plug(...) + tag_indices_from_mesh_data(data, name)
  (and any component-tag lookup helper on a mesh input) onto this ONE call. It is a
  PORTABLE lookup -- never emit ND_PORT_INCOMPLETE for it, and never fall back to an
  empty face list, which silently draws nothing.
STORED VARS (self.X that are persisted): a mutable local `X`, pre-seeded to its stored
  value. These PERSIST across frames -- the scaffold commits every one of them back to
  the per-node g_tween map after your block, so `X = <expr>;` IS the next frame's seed.
  Translate both the reads AND the writes faithfully; do NOT fold a read to a constant
  and do NOT drop a write as a no-op. A `getattr(self, "X", <literal>)` read is the SAME
  variable as the `self.X = ...` write -- both become the local `X`.
  This is what makes elastic hover/selection tweens animate: the blend factor is carried
  frame to frame, so folding it away pins it at its seed and the whole tween goes dead.

EMIT the drawing ITEM BY ITEM, in the SAME order the Python composes it -- authoring
order IS draw order. One emit* call per DrawItem. NEVER push into the SoA vectors
(data.lineStart, data.polyPts, ...) directly; the emit* helpers are the only path
that records draw order.
- DrawLines / DrawCurve -> data.emitLine(start, end, MColor(r,g,b,a), worldSpace)
      ONE call PER SEGMENT (a curve of N points is N-1 segments, or N if closed).
- DrawPoints -> data.emitPoint(MPoint, MColor, float size)
- DrawText   -> data.emitText(MPoint, MString, MColor, double size)
      size is the RAW value; do NOT truncate to int.
- DrawSphere/DrawCircle/DrawBox/DrawCone/DrawCylinder ->
      data.emitShape(kind, MPoint center, double radius, MVector axis, MColor, bool filled)
      kind: sphere->0, circle->1, box->2, cone->3, cylinder->4.
      axis is the normal; pass MVector(0,1,0) for spheres.
- DrawMesh -> DrawPoly& pg = data.emitPoly();  then fill pg:
    "points" -> pg.pts (MPoint);  "indices" -> pg.idx (int, flat);
    "counts" -> pg.cnt (int, per-face);
    "colors" (one RGBA tuple)        -> pg.colorMode=0; pg.uniform=MColor(r,g,b,a)
    "face_colors" (F x RGBA)         -> pg.colorMode=1; pg.faceColors
    "vertex_colors" (nPts x RGBA)    -> pg.colorMode=2; pg.vertexColors
    "face_vertex_colors" (sumCnt x RGBA) -> pg.colorMode=3; pg.faceVertexColors
    "cull_backfaces"->pg.cull; "wireframe"(RGBA)->pg.hasWire=true, pg.wireColor
    "wireframe_width"->pg.wireWidth; "wireframe_boundary_only"->pg.wireBoundaryOnly
    "world_space"->pg.worldSpace; "highlight_fill"/"highlight_wire"->pg.highlightFill/Wire
    "precise_hover"->pg.preciseHover
    SEVERAL DrawMeshes -> several emitPoly() calls. Do NOT merge them into one soup.
- self.auto_highlight->data.autoHighlight; self.auto_refresh->data.autoRefresh;
  self.precise_hover->data.preciseHover (accepted; visual no-ops in C++).
- ``self.draw`` is the ONLY draw surface -- there are no per-type dict slots.
  It holds one DrawItem, several composed with `+`, or a (possibly nested) LIST
  of them. Walk it in order and emit each item as it appears.
Nothing drawn -> emit nothing (leave data.cmds empty).

Rules:
- MPoint(x,y,z), MColor(r,g,b,a), MVector(x,y,z) constructors; std::vector::push_back.
- Reproduce numpy with plain loops/std::vector. linspace(a,b,n): step=(b-a)/(n-1).
  Matrix @ : write the explicit 3x3 multiply. region/np.unique work: use extract_region.
- Use <cmath> (std::sin/cos/sqrt/atan2/floor/pow). Colors are 0..1 floats.
- Bake any constants the Init defines (cube verts, palettes, REGION_FACES, etc.) as C++
  literals/std::vector. Reproduce their numpy expressions faithfully (np.arange, etc.).
- Pure math only: NO maya.cmds, NO scene/file/network access, no I/O.
- Keep it deterministic and self-contained."""


_SYSTEM_GEO_HEAD = """\
You port a Maya custom geometry GENERATOR's Python compute expression into C++
for a native MPxNode that outputs %s data. You are given the original Python and
a C++ scaffold. Output ONLY the C++ statements between the BEGIN/END PORTED
COMPUTE markers -- no function signature, no #includes, no markdown fences, no
commentary.

The scaffold has read the node's INPUT attrs into locals named `in_<attr>`
(float/int/etc.). Fill these OUTPUT buffers (already declared, in scope):
"""

_SYSTEM_GEO_TAIL = """\

Rules:
- MPoint(x,y,z) constructor; std::vector::push_back. Match the Python element
  ORDER exactly (CV / vertex ordering must be identical for parity).
- Use <cmath> (std::sin/cos/sqrt). Reproduce numpy (linspace/meshgrid/stack)
  with explicit loops -- e.g. linspace(a,b,n): step=(b-a)/(n-1), x=a+i*step.
- The scaffold builds the geometry + default knots from your buffers; do NOT
  call MFn*::create yourself, and do NOT compute knots.
- Pure math only: NO maya.cmds, NO scene/file/network access, no I/O.
- Keep it deterministic and self-contained."""

_GEO_BUFFERS_DOC = {
    "mesh": (
        "- std::vector<MPoint> points  -- vertex positions (self.points rows)\n"
        "- std::vector<int>    counts  -- verts per face   (self.counts)\n"
        "- std::vector<int>    indices -- flat face-vertex ids, length==sum(counts)\n"
        "                                 (self.indices)\n"
        "Map: self.points[i] -> points.push_back(MPoint(x,y,z)); self.counts/"
        "self.indices likewise."),
    "curve": (
        "- std::vector<MPoint> cvs    -- control vertices (self.cvs or self.points rows)\n"
        "- int degree                 -- pre-set to 3; set it if the expression sets self.degree\n"
        "Map: self.cvs[i] (or self.points[i]) -> cvs.push_back(MPoint(x,y,z))."),
    "surface": (
        "- std::vector<MPoint> cvs        -- control vertices, U-MAJOR order\n"
        "                                    (CV(u,v) at index u*numV+v)\n"
        "- int numU, numV                 -- CV grid dims (self.num_cvs_u/_v)\n"
        "- int degreeU, degreeV           -- pre-set to 3; set if expr sets self.degree_u/_v\n"
        "Map: self.cvs (Nu*Nv,3) U-major -> cvs.push_back(MPoint(x,y,z)); set numU/numV.\n"
        "If the Python builds an (Nu,Nv,3) grid, flatten U-major (u outer, v inner)."),
}


def _geo_system(kind, scalar_outs=()):
    """``scalar_outs`` is ``[(plug, setter_hint)]`` for the scalar OUTPUT attrs a
    generator declares beside its geometry output (emit_attr._setter_hint, the
    same text the scaffold comments carry). Empty for a generator without any, so
    its prompt is byte-identical to before they existed. Without this the model
    had no way to know the handles were there: Mesh Maze's porter, told only
    about the geometry buffers, correctly wrote ND_PORT_INCOMPLETE for
    `solutionSteps`."""
    geo_word = {"mesh": "polygon mesh (kMesh)",
                "curve": "NURBS curve (kNurbsCurve)",
                "surface": "NURBS surface (kNurbsSurface)"}[kind]
    doc = _GEO_BUFFERS_DOC[kind]
    if scalar_outs:
        doc += (
            "\n\nThe node ALSO declares scalar OUTPUT attrs. Each already has an "
            "MDataHandle in scope, seeded with a neutral default; write it exactly "
            "once with the setter shown (the scaffold marks it clean afterwards). "
            "These are declared plugs, not missing features -- never emit "
            "ND_PORT_INCOMPLETE for them:\n"
            + "\n".join("- self.%s -> %s" % (plug, hint) for plug, hint in scalar_outs))
    return (_SYSTEM_GEO_HEAD % geo_word) + doc + _SYSTEM_GEO_TAIL


_SYSTEM_TRANSFORM = """\
You port a Maya custom transform's Python matrix expression into C++ for a
native MPxTransformationMatrix::desiredLocal() override under the GATED DUAL-
MATRIX contract (the transform is a single-joint IK solver whose bind offset is
the identity, so un-gated channels fall back to the live TRS). You are given the
original Python and a C++ scaffold. Output ONLY the C++ statements between the
BEGIN/END PORTED COMPUTE markers -- no function signature, no #includes, no
markdown fences, no commentary.

The scaffold has already set up these READ locals (in scope):
- MMatrix m             -- the default local TRS matrix (row-vector Maya; rows
                           0..2 = basis axes, row 3 = translation). This is the
                           BASE for un-gated channels. numpy m[i,j] == C++ m(i,j).
- MVector t             -- translate channels (t.x=self.translate[0], etc.)
- MEulerRotation r      -- rotate channels in RADIANS (r.x/r.y/r.z)
- MVector sc            -- scale channels (sc.x/sc.y/sc.z)
- MMatrix in_a<Cap>     -- one per declared SCALAR MATRIX input, e.g. matrix0 ->
                           in_aMatrix0 (self.matrix0 / self.matrix0.asNumpy()).
                           The node NEVER reads its own DAG parent; for WORLD
                           placement declare a matrix input for the parent world
                           (connect parent.worldMatrix[0]) and convert yourself:
                           local_matrix = worldDesired * in_aParentWorld.inverse().

Write these OUTPUT sinks (already declared, default to a plain transform):
- MMatrix local_matrix; bool local_set  -- self.local_matrix = X  =>
                           local_matrix = X (an MMatrix); local_set = true;
- bool apply_rotate, apply_translate, apply_scale -- self.apply_* = b => set the
                           matching bool. Ungated channels come from the live TRS
                           (m), so rotate-only reorients in place. Leave every gate
                           false (or set no matrix) to leave the node at rest.
The scaffold DISPATCHES for you AFTER your code: local_matrix (if local_set and
>=1 gate) > no-op, mixing gated channels via nd_gate_mix and returning the
desired local D (compute() then authors opm = inv(L) * D). Do NOT do the dispatch
yourself -- just set local_matrix (a parent-relative frame) plus the gates. There
is no world_matrix sink: convert any world target to local via the parent input
as shown above.

Working with matrices (the Python builds numpy (4,4) matrices):
- Build an MMatrix from 16 doubles: double mm[4][4] = {{r0x,r0y,r0z,0},{...},
  {...},{tx,ty,tz,1}}; MMatrix M(mm);  (row 3 is translation; row-vector Maya).
- Read an element with M(row,col). A numpy 3x3 assigned as M[0,:3]=xAxis;
  M[1,:3]=yAxis; M[2,:3]=zAxis maps to setting rows 0,1,2 of the MMatrix.
- A Python `w @ delta` (numpy matmul, row-vector) maps to MMatrix `w * delta`.

Rules:
- MVector supports +, -, *scalar, ^ (cross), * (dot), .length(), .normal().
  np.cross(a,b) -> (a ^ b); np.dot -> (a * b) for MVectors. MMatrix supports *,
  .inverse(), M(i,j).
- numpy m[i,j] == C++ M(i,j); Maya MMatrix is row-major (translate in row 3) --
  no transpose. Use <cmath> (std::sin/cos/acos/atan2/sqrt); reproduce numpy math
  directly.
- Pure math only: NO maya.cmds, NO scene/file/network access, no I/O.
- Keep it deterministic and self-contained."""


_SYSTEM_HELPER = """\
You translate ONE pure-Python helper function into ONE C++ free function.
Rules:
- You are given the function NAME to use; use it EXACTLY (never rename it).
- If you are given a full signature, use it EXACTLY. If you are asked to CHOOSE
  the signature (a non-scalar helper), pick C++ types per the TYPE MAPPING below,
  then FIRST output a line
    PROTO: <the full C++ prototype, no trailing semicolon>
  and AFTER it the matching function definition.
- C++17. <cmath> / <vector> / <algorithm> are available; MVector and MMatrix are
  also available (vector/matrix helpers may take/return them).
- Pure math only: NO maya.cmds, NO file/scene/network access, no I/O.
- Deterministic and self-contained.
- Output ONLY the (optional PROTO: line plus the) C++ function definition -- no
  prose, no extra comments, no markdown fences, no markers.
- ASCII ONLY: emit strictly 7-bit ASCII in code AND comments -- no smart/curly
  quotes, em/en dashes, Unicode minus, math symbols, arrows, ellipsis or
  non-breaking spaces (use plain " ' - * / <= >= != -> instead); clang cannot
  lex non-ASCII outside a string literal.

TYPE MAPPING (Python -> C++ free-function types; pass big args by const ref):
- a single float / int           -> double (by value); a bool -> bool.
- a 3-component vector / point    -> const MVector&  (param) / MVector  (return).
- a list / 1-D array of numbers   -> const std::vector<double>&  / std::vector<double>.
- a list of vectors / (N,3) array -> const std::vector<MVector>& / std::vector<MVector>.
- a 4x4 matrix                    -> const MMatrix&  / MMatrix.
- a list-of-lists (jagged)        -> const std::vector<std::vector<double>>&.
- a dict / set parameter or return -> NOT translatable here (do not attempt).

PERFORMANCE (apply AFTER correctness; never at the cost of determinism):
- Pass std::vector / MVector / MMatrix params by const&; return small results by
  value. reserve() a std::vector before a push_back loop of known length; hoist
  loop-invariant subexpressions out of inner loops. Stay IEEE-deterministic: no
  -ffast-math and no reordering of floating-point reductions."""


# The escape hatch. Nothing used to tell the model what to do with a construct it
# cannot translate -- it was told to translate faithfully and nothing else, which
# is pressure to invent. The compile gate used to absorb that by refusing such
# nodes; now that valid Python is never refused, the honesty lives HERE.
PORT_INCOMPLETE = "ND_PORT_INCOMPLETE"

_UNPORTED_RULE = (
    "WHEN YOU CANNOT TRANSLATE SOMETHING -- SAY SO. Do not invent a mechanism.\n"
    "Parts of this node may use a library or construct with no C++ equivalent "
    "available to you (dataframes, a trained model, a network call, a plotting "
    "or GUI call, file I/O, a scene query). Port everything you CAN, and for "
    "each construct you cannot, emit on its own line, inside the body:\n"
    "    // %s: <what you could not translate, and why>\n"
    "immediately followed by the most neutral fallback that keeps the node "
    "well-formed -- leave the affected output at its pass-through or zero value, "
    "or leave the point/vertex unchanged. Every output must still be written.\n"
    "Absolute limits, no exceptions: NEVER emit file, process or network I/O -- "
    "no <fstream>/ifstream/ofstream/fopen/freopen/system()/popen/sockets, no "
    "shelling out, no attempt to reach maya.cmds or mutate the scene. If the "
    "Python needed one of those, that is exactly a %s case; mark it.\n"
    "Do not fabricate constants, weights or model outputs to make something "
    "look ported. Porting most of a node and marking the rest is a SUCCESS and "
    "is reported as such; a plausible-looking invention is a wrong answer that "
    "nothing downstream can catch." % (PORT_INCOMPLETE, PORT_INCOMPLETE)
)


# Learned from a real port. Handed `cKDTree(pts).query(queries, k=1)`, the model
# wrote a correct O(N*M) scan and a comment explaining that a tree and a scan
# return the same answer -- which is true, and which made the node 29x slower at
# 160k points (tools/kdtree_lowering_bench.cpp). Every gate passed: it compiled,
# it was deterministic, and it matched the interpreted result exactly. Nothing
# downstream tests asymptotic cost, so the only place this can be caught is here.
_COMPLEXITY_RULE = (
    "PRESERVE THE ALGORITHM, NOT JUST THE ANSWER. A port that returns the right "
    "values with worse asymptotic cost is a WRONG port, and it is one that every "
    "correctness check will pass.\n"
    "- When the Python names a data structure or algorithm -- a k-d / ball / "
    "R tree, Delaunay or convex hull, a sparse matrix, a heap or priority queue, "
    "a bisect/binary search, a hash set or dict used for membership -- port that "
    "structure, with its complexity class intact.\n"
    "- NEVER substitute an asymptotically worse equivalent because it is simpler "
    "or because the results agree: no linear scan in place of a tree or binary "
    "search, no dense matrix in place of a sparse one, no repeated list scan in "
    "place of a set lookup, no re-sorting inside a loop.\n"
    "- If you cannot port the structure, that is exactly an %s case -- mark it "
    "and say which structure and why. Marking it is a SUCCESS; silently trading "
    "O(log n) for O(n) is not, and a comment justifying the trade does not make "
    "it acceptable.\n"
    "- Keep the cost of the surrounding code too: hoist loop-invariant work and "
    "allocations out of loops, reserve() before a push_back loop of known length, "
    "and never build a container inside a loop that could be built once.\n"
    "- MAYA API PAIRS THAT LOOK INTERCHANGEABLE AND ARE NOT. Same answer, "
    "different complexity class. Emit the one the Python named.\n"
    "    * MMeshIntersector::getClosestPoint -- spatial structure, built once by "
    "create(); each query sublinear in face count. VS MFnMesh::getClosestPoint / "
    "getClosestPointAndNormal / getClosestNormal, whose trailing "
    "MMeshIsectAccelParams* DEFAULTS TO NULL, and with it NULL the call walks the "
    "polygon list. Measured on a 40k-face closest-point sweep: 714 SECONDS per "
    "evaluation against 0.125 s.\n"
    "    * MFnMesh::closestIntersection / anyIntersection / allIntersections with "
    "accelerator = nullptr walks the polygon list; the same call given "
    "MFnMesh::autoUniformGridParams() uses a uniform grid. Not measured here -- "
    "listed because it is the identical NULL-default shape.\n"
    "  These are cost notes, not a licence to upgrade. If the Python passed an "
    "accelerator, pass one; if it did not, do NOT invent one -- Maya caches that "
    "structure on the mesh and it goes stale under deformation unless "
    "freeCachedIntersectionAccelerator() is called. Match the Python's structure "
    "in BOTH directions."
    % PORT_INCOMPLETE
)


_ASCII_RULE = (
    "ASCII ONLY -- CRITICAL: emit strictly 7-bit ASCII C++. NEVER use smart/"
    "curly quotes, em-dashes or en-dashes, the Unicode MINUS SIGN, Unicode math "
    "(x / <= >= != +-), arrows, ellipsis, non-breaking spaces, or any other "
    "typographic Unicode -- clang cannot lex these outside a string literal and "
    "the port will fail. Use plain ASCII \" ' - * / <= >= != and -> instead, in "
    "code AND in comments."
)


def build_prompt(spec: dict, skeleton: str, shared_protos=None) -> tuple:
    """Return (system, user) prompts for porting this node's compute/deform.

    ``shared_protos`` (``[(py_qualname, c_proto)]``) switches the helper section
    to "these are already defined+declared, CALL them" instead of dumping the
    helper source for inline porting -- used when the followed helpers were
    hoisted into the shared C++ unit."""
    base = spec.get("suggested", {}).get("mpx_base", "MPxNode")
    gk   = codegen._geo_kind(spec)
    if gk:
        # Lazy import: emit_attr sits under the compiler package prompt.py
        # already depends on, but keep the module-level surface unchanged.
        from mpynode.native.compiler.emit_attr import _members, _setter_hint
        scalar_outs = [(m["plug"], _setter_hint(m))
                       for m in _members(spec) if m["kind"] == "outputs"]
        system = _geo_system(gk, scalar_outs)
    elif base == codegen._TRANSFORM_BASE:
        system = _SYSTEM_TRANSFORM
    elif base == codegen._LOCATOR_BASE:
        system = _SYSTEM_LOCATOR
    elif base == codegen._IKSOLVER_BASE:
        system = _SYSTEM_IKSOLVER
    elif base in codegen._DEFORMER_BASES:
        system = _SYSTEM_DEFORMER
    else:
        system = _SYSTEM
    # ASCII-only guard (all families + every fix round, since `system` is reused
    # across the bounded fix loop). Belt-and-braces with the always-on ASCII scrub
    # in llm_client._ascii_typography.
    system = system + "\n\n" + _ASCII_RULE
    # Cross-compiler include hygiene. Rides on the SYSTEM prompt for the same
    # reason the ASCII rule does, and for a sharper one: the ONLY compile gate is
    # macOS clang, so a fix round told "it did not compile" has already proved
    # libc++ accepted whatever it wrote.
    system = system + "\n\n" + translation_knowledge.PORTABILITY_RULE
    # The escape hatch rides on the SYSTEM prompt for the same reason the ASCII
    # rule does: `system` is reused across every fix round, so a model that
    # marked a construct incomplete in round 1 is not pressured to "fix" the
    # marker away in round 2 by inventing something that compiles.
    system = system + "\n\n" + _UNPORTED_RULE
    # Rides on the SYSTEM prompt for the same reason: a fix round that is only
    # shown "it did not compile" must not be free to reach for a simpler, slower
    # algorithm to make the error go away.
    system = system + "\n\n" + _COMPLEXITY_RULE
    # Append the library-aware translation guide (numpy/scipy/numba/imaging ->
    # C++, plus verified helper bodies for the libs this node actually uses).
    guide = translation_knowledge.guide_for_spec(spec)
    if guide:
        system = system + "\n\n" + guide
    # Source of pure-Python helpers the node imports from external modules
    # (resolved by spec_extractor via import_follower). Emitted ONLY when present
    # -- with no helpers the prompt is byte-for-byte identical to before.
    helper_block = ""
    if shared_protos:
        # Shared mode: the helpers are ALREADY defined + declared in this file
        # (hoisted into the shared C++ unit). Tell the model to CALL them.
        listing = "\n".join("  %s   ->   %s" % (qn, proto)
                            for (qn, proto) in shared_protos)
        helper_block = (
            "The followed-import helpers this node calls are ALREADY defined and "
            "declared in this file as C++ free functions -- CALL them by name, "
            "do NOT reimplement them. Python call -> C++ function:\n%s\n"
            "If a helper takes an MVector but a single vector INPUT is a double3 "
            "local (in_<x>), wrap it: MVector(in_<x>[0], in_<x>[1], in_<x>[2]). "
            "If a helper RETURNS an MVector, unpack it into the vector setter: "
            "h_<o>.set3Double(v.x, v.y, v.z).\n\n"
            % listing
        )
    else:
        helpers = (spec.get("external_helpers") or "").strip()
        if helpers:
            helper_block = (
                "External helper modules (followed imports) the node CALLS -- "
                "port these into the C++ alongside the compute (same determinism "
                "rules; they are pure-Python, not stubs):\n```python\n%s\n```\n\n"
                % helpers
            )
    # What the deterministic compiler already knows it has no path for -- the
    # node-specific half of the escape hatch. Each reason is the analyser's own
    # text, which for several constructs (the MorphStack surface, ndio,
    # bake_deltas) names the supported form outright, so the model gets the
    # correct route rather than just a warning.
    unported       = list((spec.get("portability") or {}).get("unported") or [])
    unported_block = ""
    if unported:
        unported_block = (
            "KNOWN GAPS -- the deterministic compiler found no C++ lowering for "
            "the following in this node. Translate what you can; where a "
            "supported alternative is named below, prefer it; and mark anything "
            "you genuinely cannot do with the %s comment described in your "
            "instructions:\n%s\n\n"
            % (PORT_INCOMPLETE,
               "\n".join("  - %s" % u for u in unported))
        )
    user = (
        "Node type: %s (was %s)\n\n"
        "Original Python compute expression:\n```python\n%s\n```\n\n"
        "Original Init (helpers/imports), for reference:\n```python\n%s\n```\n\n"
        "%s%s"
        "C++ scaffold (fill ONLY between the markers):\n```cpp\n%s\n```\n"
        % (spec.get("mpy_type"), spec.get("source_node"),
           spec.get("compute") or "", spec.get("init") or "", unported_block,
           helper_block, skeleton)
    )
    return system, user


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    return t.strip("\n")


# A fenced code block anywhere in the answer -- ```lang\n...\n``` (lang optional).
_FENCE_RE = re.compile(r"```[a-zA-Z0-9+_.-]*[ \t]*\n(.*?)```", re.DOTALL)

# STRONG C++ structural characters. A line containing ANY of these is treated as
# code, never stripped as prose. Deliberately a SMALL set that real statements
# almost always carry (`;` `{}` `()` `[]` `=<>`) and prose almost never does.
# `.`/`,` are excluded on purpose: an English sentence ends in `.`, and a code line
# with none of the strong tokens is invalid C++ anyway.
_CODE_CHARS = set(";{}()[]=<>")


def _looks_like_prose(line: str) -> bool:
    """True if ``line`` is almost certainly natural-language narration, not C++.

    Conservative by construction: any strong C++ structural char, any comment or
    preprocessor lead, or a single-token line -> NOT prose (kept). Only a
    multi-word line that starts with a letter and carries none of the strong code
    characters is flagged. Used to peel leaked preamble/postamble ("Looking at
    the rotation.", "Confirmed.") off the TOP and BOTTOM of an answer only."""
    s = line.strip()
    if not s:
        return False
    if s[:2] in ("//", "/*") or s[:1] in ("*", "#"):
        return False
    if any(c in _CODE_CHARS for c in s):
        return False
    words = s.split()
    return len(words) >= 2 and words[0][:1].isalpha()


def _peel_prose(text: str) -> str:
    """Drop leading/trailing prose-looking lines (never touch the middle)."""
    lines = text.splitlines()
    while lines and (not lines[0].strip() or _looks_like_prose(lines[0])):
        lines.pop(0)
    while lines and (not lines[-1].strip() or _looks_like_prose(lines[-1])):
        lines.pop()
    return "\n".join(lines)


def _extract_body(text: str) -> str:
    """Pull the C++ compute body out of a raw model answer, dropping any prose.

    Output-hygiene guard for the porter (the model is told to emit code only, but
    at lower effort it sometimes narrates -- "Looking at ...", a trailing
    "Confirmed", a stray checkmark -- and that prose lands as invalid C++). Two
    passes, both safe: (1) if the answer contains fenced code block(s), return
    their concatenated contents (narration lives OUTSIDE the fence); (2) else peel
    leading/trailing prose lines. Interleaved mid-body prose is left for the
    compile fix-loop -- stripping it heuristically would risk real code. Pairs
    with the always-on ASCII scrub in ``llm_client._ascii_typography``."""
    t      = _strip_fences(text)
    blocks = _FENCE_RE.findall((text or "").strip())
    if blocks:
        t = "\n".join(b.rstrip("\n") for b in blocks).strip("\n")
    return _peel_prose(t)


# I/O the porter is told it may never emit. Scanned in the AI-authored body ONLY
# (see ported_bodies): the SCAFFOLD emits several of these legitimately (ndio
# reader/writer, embedded-image staging, emit_locator's fopen). MGlobal::execute*
# is here because it is the C++ shape of "call maya.cmds".
_BODY_IO_PATTERNS = [
    (re.compile(r"\b(?:std::)?[io]?fstream\b"),
     "C++ file stream (fstream/ifstream/ofstream)"),
    (re.compile(r"\b(?:fopen|freopen|fdopen|fwrite|fread)\s*\("),
     "C stdio file access"),
    (re.compile(r"\b(?:system|popen|fork|execl|execv|execvp)\s*\("),
     "process / shell execution"),
    (re.compile(r"\b(?:socket|connect|gethostbyname|getaddrinfo|"
                r"curl_easy_init)\s*\("),
     "network access"),
    (re.compile(r"\bMGlobal::execute(?:Command|PythonCommand)\w*\b"),
     "scene access via MGlobal::execute* (the C++ shape of maya.cmds)"),
]

_CPP_STR_RE           = re.compile(r'"(?:\\.|[^"\\])*"')
_CPP_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CPP_LINE_COMMENT_RE  = re.compile(r"//[^\n]*")


def _strip_cpp_comments(text: str) -> str:
    """Blank string literals then comments, preserving line structure.

    Both matter for the I/O scan: an ND_PORT_INCOMPLETE marker is REQUIRED to
    explain itself ("would need std::ifstream"), and flagging the model for
    honestly describing what it declined to do would punish exactly the
    behaviour the rule asks for. Literals go first so a `"//"` inside a path
    string cannot swallow real code to its right."""
    def _blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    t = _CPP_STR_RE.sub(_blank, text or "")
    t = _CPP_BLOCK_COMMENT_RE.sub(_blank, t)
    return _CPP_LINE_COMMENT_RE.sub(_blank, t)


def ported_bodies(cpp_text: str) -> list:
    """The text of every PORT region in ``cpp_text`` -- what the model authored.

    Deliberately NOT the whole file. Bounding by the markers is what separates
    LLM-authored code from codegen's own, so no allow-list of sanctioned
    emitters is needed. A deterministically-lowered .cpp has no markers at all
    and yields ``[]``, which is the correct answer: nothing was AI-authored."""
    out = []
    cur = None
    for ln in (cpp_text or "").splitlines():
        if codegen.PORT_BEGIN in ln:
            cur = []
            continue
        if codegen.PORT_END in ln:
            if cur is not None:
                out.append("\n".join(cur))
            cur = None
            continue
        if cur is not None:
            cur.append(ln)
    return out


# ---------------------------------------------------------------------------
# Portable-include check on the AI-authored region.
#
# The only compile gate on an AI body is a macOS clang rc=0, and libc++ leaks
# transitive includes where the MSVC STL does not -- so a body that says
# `std::mutex` with no `<mutex>` builds here and fails C2039 on Windows. The
# static name -> header check in tools/check_std_includes.py is the only thing
# on this machine that sees it (clang catches 2 of 5 injected defects, this
# catches 5 of 5). Loaded by path because it is a repo tool, not a package
# module; if it is absent the port proceeds unchanged rather than failing.
# ---------------------------------------------------------------------------

_STD_INC_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "tools", "check_std_includes.py"))

_STD_INC_MOD: list = []       # one-slot cache: [] = not tried, [None] = absent


def _std_include_checker():
    """The ``tools/check_std_includes.py`` module, or None if unavailable."""
    if not _STD_INC_MOD:
        mod = None
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "mpynode_check_std_includes", _STD_INC_PATH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            mod = None
        _STD_INC_MOD.append(mod)
    return _STD_INC_MOD[0]


def missing_std_includes(cpp_text: str) -> list:
    """Headers the AI-authored PORT regions use that the file never includes.

    Region-scoped on purpose: codegen owns the include block, so a name used by
    codegen's own emitted code is codegen's problem, not a port finding. The
    result is in first-use order, so it is deterministic."""
    mod = _std_include_checker()
    if mod is None:
        return []
    out = []
    for body in ported_bodies(cpp_text):
        for h in mod.missing_headers(mod.check_region(body, cpp_text)):
            if h not in out:
                out.append(h)
    return out


_ANGLE_INC_RE = re.compile(r"^\s*#\s*include\s*<")


def add_std_includes(cpp_text: str, headers) -> str:
    """Insert ``#include <h>`` for each of ``headers`` after the first include.

    Adding a standard header to a TU that already compiled cannot break it, so
    this is the "trivially safe" repair: a missing include is never a reason to
    throw away an otherwise good port. Placement is after the FIRST ``<>``
    include rather than the last, because the last one can be buried inside the
    inlined nd_runtime header hundreds of lines below first use."""
    if not headers:
        return cpp_text
    text  = cpp_text or ""
    tail  = "\n" if text.endswith("\n") else ""
    lines = text.splitlines()
    new   = ["#include <%s>" % h for h in headers]
    at    = None
    for i, ln in enumerate(lines):
        if _ANGLE_INC_RE.match(ln):
            at = i
            break
    if at is None:
        return "\n".join(new + lines) + tail
    return "\n".join(lines[:at + 1] + new + lines[at + 1:]) + tail


def scan_ported_body(cpp_text: str) -> dict:
    """Report what the AI-authored body admits to, and what it should not contain.

    Returns ``{"ported": bool, "incomplete": [reason...], "io": [what...]}``:

      * ``ported`` -- the file has PORT regions, i.e. an LLM wrote this compute.
        Read from the artifact rather than re-deriving it, which also makes
        "verify did not run" mean something different here than on a
        deterministically-lowered node.
      * ``incomplete`` -- the model followed the escape hatch and marked a
        construct it could not translate. This is the SUCCESS case for honesty:
        the build is real, and now says what is missing instead of pretending.
      * ``io`` -- the model emitted file/process/network/scene access it was told
        never to emit. A finding, NOT a gate: the bundle still ships, the user is
        told. Blocking here would just relocate the hard stop we removed.
      * ``includes`` -- std facilities the region uses with no include for them,
        i.e. what libc++ accepted and the MSVC STL will not. Same severity as
        ``io``: a finding, never a gate. PRESENT ONLY WHEN NON-EMPTY, because
        callers compare the clean result against the three-key dict literal;
        an absent key and an empty list mean the same thing. On the porter path
        this is normally empty -- ``porter`` has already added the headers.

    Pure text; safe on a cached .cpp, so a cache HIT reports the same state a
    fresh port would."""
    incomplete = []
    io         = []
    bodies     = ported_bodies(cpp_text)
    for body in bodies:
        for ln in body.splitlines():
            if PORT_INCOMPLETE in ln:
                said = ln.split(PORT_INCOMPLETE, 1)[1].lstrip(": \t")
                incomplete.append(said.strip() or "(no reason given)")
        code = _strip_cpp_comments(body)
        for pat, what in _BODY_IO_PATTERNS:
            if pat.search(code) and what not in io:
                io.append(what)
    out  = {"ported": bool(bodies), "incomplete": incomplete, "io": io}
    need = missing_std_includes(cpp_text)
    if need:
        out["includes"] = need
    return out


def splice_body(skeleton: str, body: str) -> str:
    """Replace the text between the PORT markers with the AI body (indented).

    The model sometimes ECHOES the ``// ===== BEGIN/END PORTED COMPUTE =====``
    marker comment lines it was shown in the skeleton back into its answer (seen
    in the fix-loop especially, where the whole file -- markers and all -- is
    handed back). Splicing those verbatim nests a SECOND marker pair inside
    codegen's frame, and every downstream text consumer that locates the region
    with a first-occurrence match (the VP2 override injector, the bundler) then
    mis-spans across the class boundary and deletes the class. The markers are
    codegen's frame, never body, so strip any body line that IS a marker."""
    lines = skeleton.splitlines()
    begin = end = None
    for i, ln in enumerate(lines):
        if codegen.PORT_BEGIN in ln:
            begin = i
        elif codegen.PORT_END in ln:
            end = i
            break
    if begin is None or end is None or end <= begin:
        raise ValueError("port markers not found in skeleton")
    body_src = "\n".join(
        bl for bl in _extract_body(body).splitlines()
        if codegen.PORT_BEGIN not in bl and codegen.PORT_END not in bl)
    body_lines = ["    " + bl if bl.strip() else bl
                  for bl in body_src.splitlines()]
    return "\n".join(lines[: begin + 1] + body_lines + lines[end:])
