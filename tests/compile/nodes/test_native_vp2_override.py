"""VP2 shading-node-override injection for compiled mPyFile textures.

Guards emit_vp2_override.inject_vp2_override: the deterministic post-port
transform that splices an MHWRender::MPxShadingNodeOverride into a finalized
texture .cpp so Viewport 2.0 shades the node's pixel buffer (compute renders in
software/Arnold; VP2 needs the override). Pure text transform -- no Maya needed.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from mpynode.native.compiler import emit_vp2_override as vp2


# A minimal but structurally-faithful reproduction of the codegen scaffold for a
# reads_image_file mPyFile (raw-cache + PORT region), carrying every anchor the
# transform keys off: the raw cache, the inputs block, the create() plug names,
# the PORT markers, the class, and the plugin entry points.
_RAW_TEX_CPP = r"""#include <cmath>
#include <maya/MPxNode.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnNumericAttribute.h>
#include <maya/MFnTypedAttribute.h>
#include <maya/MFnUnitAttribute.h>
#include <maya/MImage.h>
#include <mutex>

static bool nd_img_load_raw(int&, std::mutex&, const MString&,
                            unsigned int&, unsigned int&, const unsigned char*&) {
    return false;
}

class MyTex : public MPxNode {
public:
    MyTex() {}
    ~MyTex() override {}
    static void*   creator() { return new MyTex(); }
    static MStatus initialize();
    MStatus        compute(const MPlug& plug, MDataBlock& data) override;
    static MTypeId id;
    static MObject aFileName;
    static MObject aBands;
    static MObject aUvCoord;
    static MObject aOutColor;
    static MObject aOutAlpha;
    int _imgRawCache;
    std::mutex _imgRawMutex;
};

MTypeId MyTex::id(0x00078099);

MStatus MyTex::initialize() {
    MFnNumericAttribute nAttr;
    MFnTypedAttribute   tAttr;
    aFileName = tAttr.create("fileName", "fileName", MFnData::kString);
    aBands = nAttr.create("bands", "bands", MFnNumericData::kInt, 12);
    MObject aUvCoordX = nAttr.create("uvCoordX", "uvCoordX", MFnNumericData::kFloat, 0.0);
    MObject aUvCoordY = nAttr.create("uvCoordY", "uvCoordY", MFnNumericData::kFloat, 0.0);
    aUvCoord = nAttr.create("uvCoord", "uvCoord", aUvCoordX, aUvCoordY);
    aOutColor = nAttr.createColor("outColor", "outColor");
    aOutAlpha = nAttr.create("outAlpha", "outAlpha", MFnNumericData::kFloat, 0.0);
    return MS::kSuccess;
}

MStatus MyTex::compute(const MPlug& plug, MDataBlock& data) {
    if (plug != aOutColor && plug != aOutAlpha)
        return MS::kUnknownParameter;

    // --- inputs ---
    const MString in_aFileName = data.inputValue(aFileName).asString();
    const int in_aBands = data.inputValue(aBands).asInt();
    const float2& in_aUvCoord = data.inputValue(aUvCoord).asFloat2();

    unsigned int _imgW = 0, _imgH = 0;
    const unsigned char* _imgPixels = nullptr;
    bool _imgOK = nd_img_load_raw(_imgRawCache, _imgRawMutex, in_aFileName,
                                 _imgW, _imgH, _imgPixels);

    MDataHandle h_aOutColor = data.outputValue(aOutColor);
    h_aOutColor.set3Float(0.0f, 0.0f, 0.0f);
    MDataHandle h_aOutAlpha = data.outputValue(aOutAlpha);
    h_aOutAlpha.setFloat(0.0f);

    // ===== BEGIN PORTED COMPUTE =====
    double u = (double)in_aUvCoord[0];
    double v = (double)in_aUvCoord[1];
    (void)u; (void)v; (void)in_aBands; (void)_imgW; (void)_imgH;
    (void)_imgPixels; (void)_imgOK;
    h_aOutColor.set3Float(0.5f, 0.5f, 0.5f);
    h_aOutAlpha.setFloat(1.0f);
    // ===== END PORTED COMPUTE =====

    h_aOutColor.setClean();
    h_aOutAlpha.setClean();
    return MS::kSuccess;
}

MStatus initializePlugin(MObject obj) {
    MFnPlugin plugin(obj, "mpynode-native", "1.0", "Any");
    return plugin.registerNode("myTex", MyTex::id, MyTex::creator, MyTex::initialize);
}

MStatus uninitializePlugin(MObject obj) {
    MFnPlugin plugin(obj);
    return plugin.deregisterNode(MyTex::id);
}
"""

# The SAME node, but the ported body ECHOED the PORT marker comments -- nesting a
# second BEGIN/END pair inside codegen's frame (exactly what an AI port did to the
# fileTexture cache). A first-occurrence index() would stop at the nested END that
# sits INSIDE compute(), and (once nd_texel carries a copy of the nested BEGIN)
# splice across and DELETE the class. inject_vp2_override must anchor on the OUTER
# frame (first BEGIN, last END) and strip the nested markers.
_NESTED_MARKER_TEX_CPP = _RAW_TEX_CPP.replace(
    "    // ===== BEGIN PORTED COMPUTE =====\n"
    "    double u = (double)in_aUvCoord[0];",
    "    // ===== BEGIN PORTED COMPUTE =====\n"
    "        // ===== BEGIN PORTED COMPUTE =====\n"
    "    double u = (double)in_aUvCoord[0];",
    1,
).replace(
    "    h_aOutAlpha.setFloat(1.0f);\n"
    "    // ===== END PORTED COMPUTE =====",
    "    h_aOutAlpha.setFloat(1.0f);\n"
    "        // ===== END PORTED COMPUTE =====\n"
    "    // ===== END PORTED COMPUTE =====",
    1,
)

# The SAME node with the raw image cache swapped for PERSISTENT STATE, i.e. the
# gameOfLifeTex shape. The raw-cache branch is removed deliberately: the bake-grid
# selector tests `has_raw and fn_inp` BEFORE `state`, so a fixture that kept both
# would exercise the texload path and never reach the state one.
_STATE_TEX_CPP = _RAW_TEX_CPP.replace(
    """static bool nd_img_load_raw(int&, std::mutex&, const MString&,
                            unsigned int&, unsigned int&, const unsigned char*&) {
    return false;
}

""",
    "",
    1,
).replace(
    "    int _imgRawCache;\n    std::mutex _imgRawMutex;\n",
    "    struct _NdState {\n"
    "        nd::Array<bool> board{};\n"
    "        double lastFrame = 0.0;\n"
    "    };\n"
    "    _NdState _ndState;\n"
    "    std::mutex _ndStateMutex;\n",
    1,
).replace(
    """    unsigned int _imgW = 0, _imgH = 0;
    const unsigned char* _imgPixels = nullptr;
    bool _imgOK = nd_img_load_raw(_imgRawCache, _imgRawMutex, in_aFileName,
                                 _imgW, _imgH, _imgPixels);

""",
    "",
    1,
).replace(
    """    (void)u; (void)v; (void)in_aBands; (void)_imgW; (void)_imgH;
    (void)_imgPixels; (void)_imgOK;
""",
    """    std::lock_guard<std::mutex> _ndStateLock(_ndStateMutex);
    _NdState& st = _ndState;
    (void)u; (void)v; (void)in_aBands; (void)st;
""",
    1,
)

# A non-texture node (no PORT region) -- the transform must leave it untouched.
_NON_TEXTURE_CPP = r"""#include <maya/MPxNode.h>
class Plain : public MPxNode {
    MStatus compute(const MPlug&, MDataBlock&) override { return MS::kSuccess; }
};
MStatus initializePlugin(MObject obj) { return MS::kSuccess; }
MStatus uninitializePlugin(MObject obj) { return MS::kSuccess; }
"""


def _update_shader_body(text):
    """The generated ``updateShader`` method body, sliced by brace balance."""
    at = text.index("void updateShader(")
    i = text.index("{", text.index(")", at))
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        j += 1
    raise AssertionError("unterminated updateShader body")


def _brace_depth(body, pos):
    return body.count("{", 0, pos) - body.count("}", 0, pos)


def _bake_worker_body(body):
    """The ``_bakeRows`` lambda ONLY, up to its terminating ``};``.

    Stopping at the dispatch instead would swallow the scope below it, whose
    whole job is to take the shared state mutex -- an assertion that the worker
    never touches that mutex would then always fail.
    """
    at = body.index("auto _bakeRows")
    return body[at:body.index("};", at) + 2]


def _matching_brace(body, open_at):
    """Index of the ``}`` closing the ``{`` at ``open_at``."""
    depth = 0
    for j in range(open_at, len(body)):
        if body[j] == "{":
            depth += 1
        elif body[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise AssertionError("unbalanced brace from %d" % open_at)


class TestCanInject(unittest.TestCase):
    def test_recognizes_texture_port(self):
        self.assertTrue(vp2.can_inject(_RAW_TEX_CPP))

    def test_rejects_non_texture(self):
        self.assertFalse(vp2.can_inject(_NON_TEXTURE_CPP))

    def test_rejects_already_injected(self):
        once = vp2.inject_vp2_override(_RAW_TEX_CPP)
        self.assertFalse(vp2.can_inject(once))


class TestParseInputs(unittest.TestCase):
    def test_parses_types_and_plugs(self):
        ins = {i.var: i for i in vp2._parse_inputs(_RAW_TEX_CPP)}
        self.assertEqual(ins["in_aBands"].plug, "bands")
        self.assertEqual(ins["in_aBands"].bare_type, "int")
        self.assertTrue(ins["in_aUvCoord"].is_uv)
        self.assertEqual(ins["in_aFileName"].plug, "fileName")


class TestInject(unittest.TestCase):
    def setUp(self):
        self.out = vp2.inject_vp2_override(_RAW_TEX_CPP)

    def test_emits_override_class(self):
        self.assertIn("class MyTexOverride : public MHWRender::MPxShadingNodeOverride",
                      self.out)

    def test_emits_shared_texel(self):
        self.assertIn("static void nd_texel(", self.out)
        # compute() now CALLS nd_texel instead of inlining the body.
        self.assertIn("nd_texel(", self.out.split("MStatus MyTex::compute")[1])

    def test_registers_override_creator_and_classification(self):
        self.assertIn("registerShadingNodeOverrideCreator", self.out)
        self.assertIn("drawdb/shader/texture/2d/myTex", self.out)
        self.assertIn("texture/2d:swatch/2dTextureSwatchGen", self.out)

    def test_timechanged_callback(self):
        self.assertIn('addEventCallback(', self.out)
        self.assertIn('"timeChanged"', self.out)
        self.assertIn("removeCallback", self.out)

    def test_sets_used_as_filename(self):
        self.assertIn("setUsedAsFilename(true)", self.out)

    def test_fragment_is_stock_file_texture(self):
        self.assertIn('MString("mayaFileTexture")', self.out)

    def test_uploads_float_rgba_texture(self):
        self.assertIn("kR32G32B32A32_FLOAT", self.out)
        self.assertIn("acquireTexture", self.out)

    def test_idempotent(self):
        twice = vp2.inject_vp2_override(self.out)
        self.assertEqual(twice, self.out)

    def test_non_texture_untouched(self):
        self.assertEqual(vp2.inject_vp2_override(_NON_TEXTURE_CPP),
                         _NON_TEXTURE_CPP)

    def test_port_body_reused_verbatim(self):
        # The exact ported write survives into nd_texel (body reused, not rewritten).
        self.assertIn("h_aOutColor.set3Float(0.5f, 0.5f, 0.5f);", self.out)

    def test_bake_is_guarded_by_the_content_key(self):
        """Maya calls updateShader every refresh. A node nothing drives was
        re-baking its whole buffer each frame -- measured at 21.7 ms/frame for a
        static 1024x1024 fileTexture. The key must be built BEFORE the bake and
        consulted, or the guard is decorative."""
        body = _update_shader_body(self.out)
        self.assertIn("findTexture(texName)", body,
                      "the override must ask the texture manager before baking")
        key_at = body.find("MString texName(")
        loop_at = body.find("for (unsigned int py")
        self.assertNotEqual(key_at, -1)
        self.assertNotEqual(loop_at, -1)
        self.assertLess(key_at, loop_at,
                        "texName must be built BEFORE the bake loop, otherwise "
                        "the expensive work happens before the cache is checked")
        self.assertLess(body.find("findTexture(texName)"), loop_at,
                        "the lookup must precede the bake loop")

    def test_the_rebind_is_still_unconditional(self):
        """Only the SYNTHESIS is skipped. Maya drives several MShaderInstances
        per node, so setParameter must run on every call -- this is exactly the
        distinction that made the interpreted tier disable its own
        ``_last_acquired_*`` short-circuit (_api2/mpy_file.py)."""
        body = _update_shader_body(self.out)
        guard_at = body.find("if (!tex) {")
        set_at = body.find("setParameter(mapParam")
        self.assertNotEqual(guard_at, -1)
        self.assertNotEqual(set_at, -1)
        self.assertLess(guard_at, set_at)
        # setParameter must land AFTER the `if (!tex) {` block closes, i.e. it is
        # not nested inside the branch that only runs on a cache MISS.
        self.assertGreater(set_at, _matching_brace(body, body.index("{", guard_at)),
                           "setParameter must sit OUTSIDE the bake guard so the "
                           "re-bind still happens on a cache hit")

    def test_bake_loop_is_row_parallel(self):
        """v22's key guard only helps a node whose key is STABLE. scanlineTex has
        `frame` in its key and a state node cannot be keyed at all, so both
        re-bake every frame -- measured at ~33 ms for 1024x1024. Rows are the
        partition because each worker then writes a disjoint slice of `baked`."""
        for inc in ("<thread>", "<atomic>", "<algorithm>"):
            self.assertIn("#include %s" % inc, self.out)
        body = _update_shader_body(self.out)
        self.assertIn("std::thread::hardware_concurrency()", body)
        self.assertIn("_bakeThreads.emplace_back(_bakeRows, _y0, _y1);", body)
        self.assertIn("if (_th.joinable()) _th.join();", body)
        # The row loop must be bounded by the worker's OWN slice, and the write
        # offset must derive from py -- that pair is what makes the slices
        # disjoint and the buffer thread-count-independent.
        self.assertIn("for (unsigned int py = _y0; py < _y1; ++py) {", body)
        self.assertIn("float* drow = &baked[(size_t)py * _w * 4];", body)
        # Joined before the upload, never after.
        self.assertLess(body.index("_th.join();"), body.index("acquireTexture"))

    def test_a_worker_never_lets_an_exception_escape(self):
        """nd_runtime throws on a bad shape/index and a lowered `raise` throws the
        same. An exception leaving a std::thread calls std::terminate -- it would
        take Maya down rather than skip a frame, which is the whole reason
        updateShader has an outer try in the first place."""
        body = _update_shader_body(self.out)
        lam = _bake_worker_body(body)
        self.assertIn("catch (...) { _bakeFailed.store(true); }", lam,
                      "the worker body must catch everything")
        self.assertIn("if (_bakeFailed.load()) return;", body)
        # ...and the failure check must precede the upload, or a half-baked
        # buffer reaches the GPU.
        self.assertLess(body.index("if (_bakeFailed.load()) return;"),
                        body.index("acquireTexture"))

    def test_thread_creation_failure_bakes_the_chunk_inline(self):
        """std::thread's constructor throws when the OS refuses a thread, and
        that would destroy _bakeThreads with joinable members in it -- terminate
        again, just one layer out."""
        body = _update_shader_body(self.out)
        self.assertIn("} catch (...) { _bakeRows(_y0, _y1); }", body)

    def test_the_calling_thread_takes_a_chunk(self):
        body = _update_shader_body(self.out)
        self.assertIn("_bakeRows(0u, std::min(_chunk, _h));", body)
        # Worker chunks start at 1; chunk 0 belongs to this thread.
        self.assertIn("for (unsigned int _t = 1u; _t < _nthr; ++_t) {", body)

    def test_worker_count_never_exceeds_the_row_count(self):
        """A 20x20 Game of Life board is a real case; spawning 12 threads to do
        20 rows costs more than it saves."""
        body = _update_shader_body(self.out)
        self.assertIn("if (_nthr > _h) _nthr = (_h > 0u) ? _h : 1u;", body)
        self.assertIn("if (_nthr == 0u) _nthr = 1u;", body)
        self.assertIn("if (_nthr <= 1u) {", body)


class TestStatefulBake(unittest.TestCase):
    """The state shape (gameOfLifeTex): no content-key guard is possible, so the
    bake runs every frame and the per-texel state lock is the dominant cost."""

    def setUp(self):
        self.out = vp2.inject_vp2_override(_STATE_TEX_CPP)
        self.body = _update_shader_body(self.out)

    def test_fixture_actually_selects_the_state_path(self):
        # Non-vacuity: without this the assertions below pass on a texload node
        # that simply has no state members to get wrong.
        self.assertIn("_nodePtr->_ndState", self.body)
        self.assertNotIn("nd_img_load_raw", self.body)

    def test_state_lock_is_hoisted_out_of_the_per_texel_path(self):
        """The ported body's own `lock_guard(_ndStateMutex)` cannot be stripped --
        compute() needs it against concurrent DG evaluation -- so the loop was
        taking a SHARED mutex 1,048,576 times per frame at 1024x1024. Take the
        real one once around the dispatch and hand each worker a local one."""
        self.assertIn("std::lock_guard<std::mutex> "
                      "_bakeStateLock(_nodePtr->_ndStateMutex);", self.body)
        lam = _bake_worker_body(self.body)
        self.assertIn("std::mutex _ndLocalStateMutex;", lam,
                      "each worker needs its OWN mutex, declared inside the "
                      "lambda so it is per-invocation")
        self.assertNotIn("_nodePtr->_ndStateMutex", lam,
                         "the per-texel call must not touch the shared mutex")
        self.assertIn("_ndLocalStateMutex", lam.split("nd_texel(")[1])

    def test_the_prime_call_still_uses_the_real_mutex(self):
        """The prime is what settles the frame transition for every worker texel.
        It must run against the SHARED state, single-threaded, or the workers are
        no longer read-only."""
        prime = self.body[:self.body.index("auto _bakeRows")]
        self.assertIn("_nodePtr->_ndStateMutex", prime.split("nd_texel(")[1])

    def test_hoisted_lock_sits_below_the_prime_and_shape_scopes(self):
        """std::mutex is not recursive: the prime call locks it internally and
        the shape read takes it explicitly, so taking it above either deadlocks
        the render thread outright."""
        hoist = self.body.index("_bakeStateLock")
        self.assertGreater(hoist, self.body.index("nd_texel("),
                           "the prime call must complete first")
        self.assertGreater(hoist,
                           self.body.rindex("_lk(_nodePtr->_ndStateMutex)"),
                           "the shape-read scope must close first")

    def test_lock_is_released_before_the_upload(self):
        """Scoped to the dispatch only. Holding it across acquireTexture would
        block compute() on GPU work it has nothing to do with."""
        open_at = self.body.rindex("{", 0, self.body.index("_bakeStateLock"))
        close_at = _matching_brace(self.body, open_at)
        self.assertLess(close_at, self.body.index("acquireTexture"))

    def test_state_bake_is_structurally_unguarded(self):
        """Not a preference: the key folds in a hash of the baked pixels, so it
        does not exist until the bake has already run."""
        self.assertNotIn("findTexture(texName)", self.body)
        self.assertLess(self.body.index("_bakeRows(0u"),
                        self.body.index("MString texName("))

    def test_generated_update_shader_is_brace_balanced(self):
        self.assertEqual(self.body.count("{"), self.body.count("}"))

    def test_idempotent(self):
        self.assertEqual(vp2.inject_vp2_override(self.out), self.out)

    def test_generated_update_shader_is_brace_balanced(self):
        body = _update_shader_body(self.out)
        self.assertEqual(body.count("{"), body.count("}"),
                         "the guard must not leave an unbalanced brace")


class TestNestedMarkerPort(unittest.TestCase):
    """Regression: a ported body that echoed the PORT marker comments (nested
    BEGIN/END) must inject cleanly, not delete the node class (the fileTexture
    mega-drop root cause)."""

    def setUp(self):
        self.out = vp2.inject_vp2_override(_NESTED_MARKER_TEX_CPP)

    def test_class_survives(self):
        # The class MUST NOT be swallowed by a cross-boundary marker span.
        self.assertIn("class MyTex : public MPxNode", self.out)
        self.assertIn("MStatus MyTex::compute", self.out)

    def test_texel_has_real_body_not_a_self_call(self):
        # nd_texel's body is the real ported compute, not a recursive nd_texel().
        # Isolate JUST the function body: from its signature to its own closing
        # brace ("\n}\n") -- NOT up to compute() (the VP2 override's bake loop
        # between them legitimately calls nd_texel).
        after = self.out.split("static void nd_texel(", 1)[1]
        texel_body = after.split("\n}\n", 1)[0]
        self.assertIn("h_aOutColor.set3Float(0.5f, 0.5f, 0.5f);", texel_body)
        self.assertNotIn("nd_texel(", texel_body.split("{", 1)[1])

    def test_compute_calls_texel(self):
        comp = self.out.split("MStatus MyTex::compute", 1)[1]
        self.assertIn("nd_texel(", comp)

    def test_override_still_injected(self):
        self.assertIn("MPxShadingNodeOverride", self.out)
        self.assertIn("registerShadingNodeOverrideCreator", self.out)

    def test_matches_clean_port(self):
        # Injecting the nested-marker port yields the SAME result as injecting the
        # clean port -- the echoed markers are the only difference and are stripped.
        self.assertEqual(self.out, vp2.inject_vp2_override(_RAW_TEX_CPP))


if __name__ == "__main__":
    unittest.main()
