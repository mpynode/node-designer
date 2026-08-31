"""Native codegen C++ emission: classification, probe-guard flatten, metadata embed, locator hover, euler type

Consolidated from: test_hypershade_classification.py, test_bundler_locator_probe.py, test_codegen_metadata.py, test_locator_hover_codegen.py, test_euler_support.py.
"""

from __future__ import annotations

# ===================== from test_hypershade_classification.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__hypershade_classification():
    standalone_init()
    ensure_plugins_loaded()


class TestStripUnportedClassification(unittest.TestCase):
    """Pure ':'-segment filter -- no Maya needed."""

    def test_drops_drawdb_keeps_texture_and_swatch(self):
        from mpynode.native.spec import spec_extractor as se
        got = se._strip_unported_classification(
            "texture/2d:swatch/2dTextureSwatchGen:drawdb/shader/texture/2d/mPyFile")
        self.assertEqual(got, "texture/2d:swatch/2dTextureSwatchGen")

    def test_plain_texture_unchanged(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertEqual(se._strip_unported_classification("texture/2d"),
                         "texture/2d")

    def test_empty_stays_empty(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertEqual(se._strip_unported_classification(""), "")

    def test_all_drawdb_collapses_to_empty(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertEqual(
            se._strip_unported_classification("drawdb/shader/texture/2d/mPyFile"),
            "")

    def test_whitespace_segments_dropped(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertEqual(
            se._strip_unported_classification("texture/2d::drawdb/geometry/x"),
            "texture/2d")


class TestCodegenEmitsClassification(unittest.TestCase):
    """generate_cpp must emit the classification registerNode overload when the
    spec carries a classification, and the plain 4-arg call when it does not."""

    def _spec(self, classif=None):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="classSrc#")
        w.add_input_attr("uIn", "float")
        w.add_output_attr("outColor", "vector")
        w.set_compute_expression("self.outColor = [self.uIn, self.uIn, self.uIn]")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "classTestNode"
        if classif is not None:
            spec["suggested"]["classification"] = classif
        else:
            spec["suggested"].pop("classification", None)
        return spec

    def test_with_classification_emits_overload(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            self._spec("texture/2d:swatch/2dTextureSwatchGen"), for_port=True)
        self.assertIn('MString _classif("texture/2d:swatch/2dTextureSwatchGen");',
                      cpp)
        self.assertIn("MPxNode::kDependNode, &_classif", cpp)

    def test_without_classification_plain_register(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(None), for_port=True)
        self.assertNotIn("_classif", cpp)
        self.assertIn("registerNode(", cpp)


class TestCodegenEnumDefault(unittest.TestCase):
    """eAttr.create's 3rd arg (the default field index) must follow the enum's
    recorded default_value -- and stay 0 (byte-identical) when none is set."""

    def _spec_with_enum(self, default_value=None):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="enumDefSrc#")
        kw = {"enum_names": ["off", "on", "standby"]}
        if default_value is not None:
            kw["default_value"] = default_value
        w.add_input_attr("mode", "enum", **kw)
        w.add_output_attr("outVal", "float")
        w.set_compute_expression("self.outVal = float(self.mode)")
        return spec_extractor.extract_spec(w.get_name())

    def test_enum_default_emitted_in_create(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec_with_enum(2), for_port=True)
        self.assertIn('eAttr.create("mode", "mode", 2);', cpp)

    def test_enum_without_default_stays_zero(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec_with_enum(None), for_port=True)
        self.assertIn('eAttr.create("mode", "mode", 0);', cpp)


class TestBundlerPreservesClassification(unittest.TestCase):
    """The bundler rewrites initializePlugin into a register hook; the
    classification local + overloaded call must survive into the fragment."""

    def _spec(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="bclassSrc#")
        w.add_input_attr("uIn", "float")
        w.add_output_attr("outColor", "vector")
        w.set_compute_expression("self.outColor = [self.uIn, self.uIn, self.uIn]")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "bclassTestNode"
        spec["suggested"]["classification"] = "texture/2d:swatch/2dTextureSwatchGen"
        return spec

    def test_fragment_keeps_classification_call(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import bundler
        spec = self._spec()
        cpp = codegen.generate_cpp(spec, for_port=False)  # complete stub cpp
        frag, info = bundler.transform_node_cpp(
            cpp, spec["suggested"]["node_type_name"], lambda key: "0x00081234")
        self.assertIn('MString _classif("texture/2d:swatch/2dTextureSwatchGen");',
                      frag)
        self.assertIn("MPxNode::kDependNode, &_classif", frag)


class TestExtractSpecCapturesMpyFileClassification(unittest.TestCase):
    """End-to-end: a live mPyFile's classification is captured + stripped."""

    def test_mpyfile_classification_captured_and_stripped(self):
        import maya.cmds as cmds
        from mpynode.native.spec import spec_extractor

        cmds.file(new=True, force=True)
        try:
            node = cmds.createNode("mPyFile")
        except Exception as exc:
            self.skipTest("mPyFile node type not available: %s" % exc)
        spec = spec_extractor.extract_spec(node)
        classif = spec["suggested"].get("classification", "")
        self.assertIn("texture/2d", classif)
        self.assertNotIn("drawdb/", classif)  # VP2-override segment is Phase 2


class TestDeformNormalsLowering(unittest.TestCase):
    """#49 (D4): the per-vertex-normals deform idiom
    (om.MFloatVectorArray + mesh.getVertexNormals) is now DETERMINISTICALLY
    lowered (MFnMesh::getVertexNormals in C++), not sent to the AI porter."""

    _COMPUTE = (
        "mesh = self.outputGeometry[0]\n"
        "pts = mesh.getPoints()\n"
        "nrm = om.MFloatVectorArray()\n"
        "mesh.getVertexNormals(False, nrm, om.MSpace.kObject)\n"
        "normals = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]\n"
        "                    for i in range(nrm.length())], dtype=float)\n"
        "mesh.setPoints(pts + self.envelope * (self.amplitude * normals))\n"
    )

    def _spec(self):
        return {
            "suggested": {"node_type_name": "sineRippleTest",
                          "class_name": "SineRippleTest",
                          "type_id": "0x00070199",
                          "mpx_base": "MPxDeformerNode"},
            "mpy_type": "mPyDeformer",
            "compute": self._COMPUTE,
            "init": "import numpy as np\nimport maya.OpenMaya as om\n",
            "inputs": {"amplitude": {"type": "float"}},
            "outputs": {},
            "portability": {"portable": True, "blockers": [], "warnings": [],
                            "reads_image_file": False},
        }

    def test_rewrite_recognizes_normals_idiom(self):
        from mpynode.native.compiler import nd_lower
        src, info = nd_lower._rewrite_deform_io(self._COMPUTE)
        self.assertEqual(info, {"aw": False, "space": "kObject"})
        self.assertIn("normals = self.__ndnormals__", src)
        # the raw Maya-API lines must be gone from the transpiled source.
        self.assertNotIn("MFloatVectorArray", src)
        self.assertNotIn("getVertexNormals", src)

    def test_generate_cpp_lowers_deterministically(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)   # no AI port region
        self.assertIn("MFnMesh(_nMeshObj).getVertexNormals(false", cpp)
        self.assertIn("MSpace::kObject", cpp)

    def test_angle_weighted_true_threads_through(self):
        from mpynode.native.compiler import nd_lower
        aw_true = self._COMPUTE.replace("getVertexNormals(False",
                                        "getVertexNormals(True")
        _src, info = nd_lower._rewrite_deform_io(aw_true)
        self.assertEqual(info["aw"], True)

    def test_non_normals_deform_still_falls_through(self):
        # a plain getPoints/setPoints deform has no normals idiom -> info None
        from mpynode.native.compiler import nd_lower
        plain = ("mesh = self.outputGeometry[0]\n"
                 "rest = mesh.getPoints()\n"
                 "mesh.setPoints(rest * 2.0)\n")
        _src, info = nd_lower._rewrite_deform_io(plain)
        self.assertIsNone(info)


class TestGeoImageFileScaffold(unittest.TestCase):
    """A geometry GENERATOR may read an image FILE in its compiled compute
    (voxelize colours its cubes from a texture). The geo emitter must then wire
    the same CACHED decode the generic MPxNode path uses -- an MImage read per
    compute() is the difference between a live node and a stall -- and it must
    TELL the porter the buffer exists. Left unsaid, the translation guide still
    claims the pixels are "loaded above" while no such buffer is emitted, and the
    porter honestly drops the texture link instead of translating it.
    """

    _COMPUTE = ("import numpy as np\n"
                "px = sample_texture(self.fileName)\n"
                "self.points = np.zeros((8, 3), dtype=float) + px\n"
                "self.counts = np.zeros((0,), dtype=int)\n"
                "self.indices = np.zeros((0,), dtype=int)\n")

    def _spec(self, reads_image=True, inputs=None):
        return {
            "suggested": {"node_type_name": "imgGeoTest",
                          "class_name": "ImgGeoTest",
                          "type_id": "0x00070198",
                          "mpx_base": "MPxNode",
                          "reads_image_file": reads_image},
            "mpy_type": "mPyMesh",
            "compute": self._COMPUTE,
            "init": "",
            "inputs": (inputs if inputs is not None
                       else {"fileName": {"type": "string"}}),
            "outputs": {},
            "portability": {"portable": True, "blockers": [], "warnings": [],
                            "reads_image_file": reads_image},
        }

    def test_image_read_emits_cached_decode(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("maya/MImage.h", cpp)
        self.assertIn("NdImgRawCache", cpp)     # per-instance cache + lock
        self.assertIn("nd_img_load_raw", cpp)   # the cached decode, not a
        self.assertIn("_imgPixels", cpp)        # readFromFile per compute()

    def test_image_read_tells_the_porter_what_it_got(self):
        # The three facts a translator cannot recover from the buffer itself.
        # Without them a plausible port is silently upside-down, or in the wrong
        # transfer function, or crashes on a blank path.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("_imgPixels", cpp)
        self.assertIn("BOTTOM-UP", cpp)
        self.assertIn("RAW 8-bit", cpp)
        self.assertIn("_imgOK false", cpp)

    def test_no_image_read_omits_the_cache(self):
        # Every OTHER geo frag must stay byte-identical -- the cache is gated on
        # the spec flag, not emitted for all geometry nodes.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(reads_image=False),
                                   for_port=True)
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("nd_img_load_raw", cpp)
        self.assertNotIn("BOTTOM-UP", cpp)

    def test_string_array_path_input_rejects_honestly(self):
        # The path input is resolved by _pick_path_input, which prefers ANY
        # string ARRAY (the multi-file composite form) over a scalar fileName --
        # but this arm emits only the SINGLE-file cache, so a composite pick
        # would leave undeclared identifiers in the TU. A multi-string input on
        # a geometry node is ordinary (procrustes_tags has one), so the emitter
        # must REJECT rather than emit a .cpp that cannot build.
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler.errors import UnsupportedSpec
        spec = self._spec(inputs={"fileName": {"type": "string"},
                                  "clusterTags": {"type": "string",
                                                  "is_array": True}})
        with self.assertRaises(UnsupportedSpec):
            codegen.generate_cpp(spec, for_port=True)


# ---- shared spec factory for the image-read scaffold tests below -------------
# One place builds every base's spec so the cases differ ONLY in base + path
# input shape -- which is the whole point of the cross-base invariant test.

_IMG_SCALAR_IN = {"fileName": {"type": "string"}}
_IMG_ARRAY_IN = {"filePaths": {"type": "string", "is_array": True}}
# No string/hex input at all: the node's path is hardcoded (or comes from a
# stored var), so there is no path PLUG to read.
_IMG_NO_PATH_IN = {"amount": {"type": "float"}}

# Bare helper call (not self.<attr>), so the unbound-self-read guards do not
# claim the spec before the image wiring is reached, and nothing lowers.
_IMG_COMPUTE = {
    "MPxNode": ("import numpy as np\n"
                "px = sample_texture(%s)\n"
                "self.outVal = float(px)\n"),
    "geo": ("import numpy as np\n"
            "px = sample_texture(%s)\n"
            "self.points = np.zeros((8, 3), dtype=float) + px\n"
            "self.counts = np.zeros((0,), dtype=int)\n"
            "self.indices = np.zeros((0,), dtype=int)\n"),
    "MPxDeformerNode": ("mesh = self.outputGeometry[0]\n"
                        "pts = mesh.getPoints()\n"
                        "px = sample_texture(%s)\n"
                        "mesh.setPoints(pts * px)\n"),
    "MPxIkSolverNode": ("px = sample_texture(%s)\n"
                        "self.local_matrices = [px]\n"),
    "MPxLocatorNode": ("px = sample_texture(%s)\n"
                       "self.draw = [{'type': 'line',\n"
                       "              'points': [[0, 0, 0], [px, 0, 0]]}]\n"),
    "MPxTransform": ("px = sample_texture(%s)\n"
                     "self.translate = [px, 0.0, 0.0]\n"),
}
_IMG_MPY_TYPE = {"MPxNode": "mPyNode", "geo": "mPyMesh",
                 "MPxDeformerNode": "mPyDeformer",
                 "MPxSkinCluster": "mPySkinCluster",
                 "MPxIkSolverNode": "mPyIkSolver",
                 "MPxLocatorNode": "mPyLocator",
                 "MPxTransform": "mPyTransform"}


def _img_spec(base, inputs, reads_image=True):
    """Porter spec for ``base`` reading an image from ``inputs``' path plug.

    ``base`` "geo" means a plain MPxNode driven through the geometry GENERATOR
    emitter (mpy_type mPyMesh); every other value is the literal mpx_base."""
    src_key = "MPxDeformerNode" if base == "MPxSkinCluster" else base
    string_ins = [k for k, v in inputs.items() if v.get("type") == "string"]
    path = ('"/tmp/hardcoded.png"' if not string_ins
            else "self." + string_ins[0])
    outs = {"outVal": {"type": "float"}} if base == "MPxNode" else {}
    return {
        "suggested": {"node_type_name": "imgScafTest",
                      "class_name": "ImgScafTest",
                      "type_id": "0x000701a4",
                      "mpx_base": ("MPxNode" if base == "geo" else base),
                      "reads_image_file": reads_image},
        "mpy_type": _IMG_MPY_TYPE[base],
        "compute": _IMG_COMPUTE[src_key] % path,
        "init": "",
        "inputs": dict(inputs),
        "outputs": outs,
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": reads_image},
    }


class TestDeformerImageFileScaffold(unittest.TestCase):
    """A sanctioned DEFORMER (mPyDeformer/mPySkinCluster/mPyBlendShape) may read
    an image FILE in its compiled deform().

    node_scaffold already DECLARED the cache for these bases -- but the body came
    from emit_deformer, which never emitted the load, so the class carried a
    cache nothing ever filled while translation_knowledge told the porter "the
    image file IS already read for you". A port written against that promise
    either drops the feature or references an identifier that does not exist.
    """

    def test_scalar_path_emits_cached_decode_and_buffer(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_SCALAR_IN), for_port=True)
        self.assertIn("NdImgRawCache _imgRawCache;", cpp)   # declared
        self.assertIn("nd_img_load_raw(_imgRawCache", cpp)  # AND called
        self.assertIn("const unsigned char* _imgPixels", cpp)

    def test_skincluster_scalar_path_emits_cached_decode_and_buffer(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxSkinCluster", _IMG_SCALAR_IN), for_port=True)
        self.assertIn("MPxSkinCluster", cpp)
        self.assertIn("NdImgRawCache _imgRawCache;", cpp)
        self.assertIn("nd_img_load_raw(_imgRawCache", cpp)
        self.assertIn("const unsigned char* _imgPixels", cpp)

    def test_string_array_path_builds_the_composite(self):
        # _pick_path_input prefers a string ARRAY (the multi-file composite
        # form). node_scaffold already declares the composite cache for the
        # deformer bases, so unlike the geometry emitter this arm is real and
        # must be CALLED, not rejected.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_ARRAY_IN), for_port=True)
        self.assertIn("NdImgCompositeCache _imgCompCache;", cpp)
        self.assertIn("nd_img_composite(_imgCompCache", cpp)
        self.assertIn("const unsigned char* _imgPixels", cpp)
        self.assertNotIn("nd_img_load_raw(_imgRawCache", cpp)

    def test_read_is_before_the_geometry_harvest(self):
        # The load must sit after the user-input reads (it consumes the path
        # local one of them declares) and before allPositions -- a load placed
        # after the harvest would be out of scope for a lowered deform body.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_SCALAR_IN), for_port=True)
        self.assertLess(cpp.index("const MString in_aFileName"),
                        cpp.index("nd_img_load_raw(_imgRawCache"))
        self.assertLess(cpp.index("nd_img_load_raw(_imgRawCache"),
                        cpp.index("iter.allPositions(pts)"))

    def test_no_image_read_omits_the_cache(self):
        # Every OTHER deformer frag stays byte-identical: gated on the spec flag.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_SCALAR_IN, reads_image=False),
            for_port=True)
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("nd_img_load_raw", cpp)
        self.assertNotIn("_imgPixels", cpp)
        self.assertNotIn("BOTTOM-UP", cpp)

    def test_image_read_tells_the_porter_what_it_got(self):
        # Deformer counterpart of the geo test: the three facts a translator
        # cannot recover from the buffer itself. Without them a plausible port is
        # silently upside-down, in the wrong transfer function, or crashes on a
        # blank path.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_SCALAR_IN), for_port=True)
        self.assertIn("loaded above into _imgPixels", cpp)
        self.assertIn("BOTTOM-UP", cpp)
        self.assertIn("RAW 8-bit", cpp)
        self.assertIn("_imgOK false", cpp)

    def test_composite_hint_says_top_down_not_bottom_up(self):
        # The two arms disagree behind the SAME _imgPixels name: nd_img_load_raw
        # hands back MImage's native bottom-up rows, nd_img_composite
        # verticalFlips to top-down. A hint that names the wrong one flips every
        # sample vertically, so it must follow the arm actually emitted.
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxDeformerNode", _IMG_ARRAY_IN), for_port=True)
        self.assertIn("rows are TOP-DOWN", cpp)
        self.assertNotIn("BOTTOM-UP", cpp)
        self.assertIn("RAW 8-bit", cpp)
        self.assertIn("_imgOK false", cpp)


class TestIkSolverImageFileScaffold(unittest.TestCase):
    """mPyIkSolver gets the same three pieces (cache, load, hints). Its path
    input rides the generic findPlug readers (a string is never a bespoke
    scalar), so the read local is ``in_a_<ident>``."""

    def test_scalar_path_emits_cached_decode_and_buffer(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxIkSolverNode", _IMG_SCALAR_IN), for_port=True)
        self.assertIn("maya/MImage.h", cpp)
        self.assertIn("NdImgRawCache _imgRawCache;", cpp)
        self.assertIn("nd_img_load_raw(_imgRawCache, _imgRawMutex, "
                      "in_a_fileName", cpp)
        self.assertIn("const unsigned char* _imgPixels", cpp)
        self.assertIn("BOTTOM-UP", cpp)

    def test_string_array_path_builds_the_composite(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxIkSolverNode", _IMG_ARRAY_IN), for_port=True)
        self.assertIn("NdImgCompositeCache _imgCompCache;", cpp)
        self.assertIn("nd_img_composite(_imgCompCache, _imgCompMutex, "
                      "in_a_filePaths", cpp)
        self.assertIn("rows are TOP-DOWN", cpp)

    def test_no_image_read_omits_the_cache(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(
            _img_spec("MPxIkSolverNode", _IMG_SCALAR_IN, reads_image=False),
            for_port=True)
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("_imgPixels", cpp)


class TestSanctionedImageReadWithNoPathInput(unittest.TestCase):
    """A sanctioned node with NO string/hex input at all (hardcoded path in
    Init, or a stored var) has no path PLUG, so ``_image_read_lines`` has nothing
    to load and emits nothing. Declaring the cache anyway -- and telling the
    porter the pixels are "loaded above" -- promises a buffer that never exists.
    Both are suppressed: the porter then translates the read itself or emits
    ND_PORT_INCOMPLETE, which is honest for a node with no path plug."""

    def _cpp(self, base):
        from mpynode.native import compiler as codegen
        return codegen.generate_cpp(_img_spec(base, _IMG_NO_PATH_IN),
                                    for_port=True)

    def test_plain_node_declares_no_cache(self):
        cpp = self._cpp("MPxNode")
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("loaded above into _imgPixels", cpp)

    def test_geometry_generator_declares_no_cache(self):
        cpp = self._cpp("geo")
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("loaded above into _imgPixels", cpp)
        self.assertNotIn("BOTTOM-UP", cpp)

    def test_deformer_declares_no_cache(self):
        cpp = self._cpp("MPxDeformerNode")
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("loaded above into _imgPixels", cpp)

    def test_iksolver_declares_no_cache(self):
        cpp = self._cpp("MPxIkSolverNode")
        self.assertNotIn("NdImgRawCache", cpp)
        self.assertNotIn("loaded above into _imgPixels", cpp)

    def test_porter_guide_does_not_promise_the_buffer(self):
        # The scaffold is only the SECOND of three tellers. The AI porter reads
        # its guide, not the TU, and IMAGE_FILE_READ asserts flatly that
        # `_imgPixels` "IS already read for you" -- so left ungated it hands the
        # porter an identifier the suppressed scaffold never declares and the
        # port cannot compile.
        from mpynode.native.ai import translation_knowledge as tk
        anchor = "=== SANCTIONED IMAGE FILE READ"
        with_path = tk.guide_for_spec(
            _img_spec("MPxDeformerNode", _IMG_SCALAR_IN))
        without = tk.guide_for_spec(
            _img_spec("MPxDeformerNode", _IMG_NO_PATH_IN))
        self.assertIn(anchor, with_path)
        self.assertNotIn(anchor, without)


class TestImageCacheDeclarationMatchesUse(unittest.TestCase):
    """Cross-base invariant: a DECLARED image cache and an actual LOAD must never
    disagree, in either direction. Both halves of that pair have shipped broken
    (the deformer declared without loading; a pathless node declared, promised
    and never loaded), so it is checked for every base rather than per emitter.

    NOTE the anchors: ``NdImgRawCache``/``nd_img_load_raw`` alone can never fail
    -- the load's DEFINITION lives inside RAW_CACHE_CPP, so the two names always
    appear together. The member declaration and the argument-qualified CALL are
    the only anchors that distinguish "declared" from "used"."""

    _BASES = ["MPxNode", "geo", "MPxDeformerNode", "MPxSkinCluster",
              "MPxIkSolverNode", "MPxLocatorNode", "MPxTransform"]

    def _cases(self):
        from mpynode.native.compiler.errors import UnsupportedSpec
        from mpynode.native import compiler as codegen
        for base in self._BASES:
            for shape, ins in (("scalar", _IMG_SCALAR_IN),
                               ("array", _IMG_ARRAY_IN),
                               ("no-path", _IMG_NO_PATH_IN)):
                for reads in (True, False):
                    tag = "%s/%s/reads=%s" % (base, shape, reads)
                    try:
                        cpp = codegen.generate_cpp(
                            _img_spec(base, ins, reads_image=reads),
                            for_port=True)
                    except UnsupportedSpec:
                        # An honest reject (the geo emitter has no composite
                        # arm) emits no TU at all, so there is nothing to check.
                        continue
                    yield tag, cpp
        # Every case above uses the un-lowerable sample_texture() helper, so
        # without this one the deterministic-lowering arm -- the third way to
        # declare a cache nothing calls -- is never reached and the "every base"
        # claim in the docstring is not earned. nd_lower emits pure numeric C++
        # with no image intrinsic, so a lowered body can never name _imgPixels.
        for shape, ins in (("scalar", _IMG_SCALAR_IN),
                           ("no-path", _IMG_NO_PATH_IN)):
            spec = _img_spec("MPxNode", ins)
            spec["compute"] = "self.outVal = self.amount * 2.0\n"
            spec["inputs"] = dict(ins, amount={"type": "float"})
            cpp = codegen.generate_cpp(spec, for_port=True)
            yield "MPxNode/%s/lowered" % shape, cpp

    def test_declared_cache_is_always_used(self):
        for tag, cpp in self._cases():
            self.assertEqual("NdImgRawCache _imgRawCache;" in cpp,
                             "nd_img_load_raw(_imgRawCache" in cpp,
                             "%s: raw cache declared/used disagree" % tag)
            self.assertEqual("NdImgCompositeCache _imgCompCache;" in cpp,
                             "nd_img_composite(_imgCompCache" in cpp,
                             "%s: composite cache declared/used disagree" % tag)

    def test_buffer_exists_exactly_when_a_cache_was_declared(self):
        # Keyed across the TWO emitters that must agree: node_scaffold writes the
        # cache MEMBER, emit_attr's read lines write `_imgPixels`. Pairing the
        # buffer with the LOAD instead would be vacuous -- both of those strings
        # come out of the same literal list in _image_read_lines and cannot
        # disagree. This pair is exactly what the deformer shipped broken.
        for tag, cpp in self._cases():
            declared = ("NdImgRawCache _imgRawCache;" in cpp
                        or "NdImgCompositeCache _imgCompCache;" in cpp)
            self.assertEqual(declared, "const unsigned char* _imgPixels" in cpp,
                             "%s: cache declared without a buffer (or vice "
                             "versa)" % tag)

    def test_porter_is_only_promised_a_buffer_that_exists(self):
        for tag, cpp in self._cases():
            self.assertEqual("const unsigned char* _imgPixels" in cpp,
                             "loaded above into _imgPixels" in cpp,
                             "%s: porter hint and buffer disagree" % tag)


class TestImageReadSanctionGatesAgree(unittest.TestCase):
    """The live (spec_extractor) and .mpn (mpn_spec_adapter) sanction gates must
    list the same node types, or a template compiles differently depending on
    which entry point built its spec. Only types whose EMITTER wires the read may
    be listed -- sanctioning a base the emitter ignores is the half-wired state
    that shipped on the deformer."""

    def test_deformer_family_and_iksolver_are_sanctioned(self):
        from mpynode.native.spec import spec_extractor as se
        for t in ("mPyDeformer", "mPySkinCluster", "mPyBlendShape",
                  "mPyIkSolver"):
            self.assertIn(t, se._IMAGE_READ_BASE_TYPES)

    def test_unwired_emitters_are_not_sanctioned(self):
        # mPyLocator's ported body is Maya-free by contract and mPyTransform's
        # desiredLocal() is const; neither emitter can host the read today.
        from mpynode.native.spec import spec_extractor as se
        self.assertNotIn("mPyLocator", se._IMAGE_READ_BASE_TYPES)
        self.assertNotIn("mPyTransform", se._IMAGE_READ_BASE_TYPES)

    def test_both_entry_points_use_the_same_list(self):
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native.spec import mpn_spec_adapter as msa
        self.assertIs(msa._IMAGE_READ_BASE_TYPES, se._IMAGE_READ_BASE_TYPES)

    def test_deformer_image_read_is_a_warning_not_a_blocker(self):
        from mpynode.native.spec import spec_extractor as se
        src = "import cv2\npx = cv2.imread('/tmp/x.png')\n"
        allowed = se.assess_portability(src, "", {}, {}, {},
                                        allow_file_read=True)
        self.assertTrue(allowed["reads_image_file"])
        self.assertEqual(allowed["blockers"], [])
        denied = se.assess_portability(src, "", {}, {}, {},
                                       allow_file_read=False)
        self.assertFalse(denied.get("reads_image_file"))

    def test_image_read_sanction_does_not_also_sanction_binary_open(self):
        # Widening the READ list must not quietly widen the §2a embedded-STAGING
        # sanction with it: no deformer/solver emitter emits EMBEDDED_STAGE_CPP,
        # so on those bases the "stages an embedded image byte buffer" warning
        # would be false AND the `unported` signal the porter needs to know the
        # open() has no lowering would be dropped.
        from mpynode.native.spec import spec_extractor as se
        src = "buf = open('/tmp/x.png', 'wb')\nbuf.write(b'')\n"
        staged = se.assess_portability(src, "", {}, {}, {},
                                       allow_file_read=True,
                                       allow_embedded_stage=True)
        self.assertTrue(staged.get("reads_embedded_image"))
        self.assertEqual(staged["unported"], [])
        read_only = se.assess_portability(src, "", {}, {}, {},
                                          allow_file_read=True,
                                          allow_embedded_stage=False)
        self.assertFalse(read_only.get("reads_embedded_image"))
        self.assertTrue(any("open()" in u for u in read_only["unported"]))
        # Default keeps every pre-existing caller byte-identical.
        self.assertEqual(
            se.assess_portability(src, "", {}, {}, {}, allow_file_read=True),
            staged)

    def test_only_the_staging_capable_types_get_the_open_sanction(self):
        # The two entry points must split the flag the same way, or a template
        # gets a different portability report depending on which built its spec.
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native.spec import mpn_spec_adapter as msa
        for mod in (se, msa):
            src = _read_source(mod)
            self.assertIn("allow_embedded_stage", src)
            # The four newly sanctioned bases reach allow_file_read ONLY, never
            # the staging flag.
            stage_block = src.split("allow_embedded_stage = ", 1)[1] \
                             .split("allow_file_read", 1)[0]
            self.assertNotIn("_IMAGE_READ_BASE_TYPES", stage_block)


def _read_source(mod):
    import inspect
    return inspect.getsource(mod)


class TestImageReadKeepsRealParityOnItsOwnBranches(unittest.TestCase):
    """The image-read parity SKIP must not claim a base that has a real parity
    branch of its own further down ``_verify_parity``.

    This already cost the codebase once: a geo node that also read an image hit
    the skip first and lost ALL of its geometry parity, silently, because the
    controller swallows verify problems. The fix was to hoist the geo branch
    ABOVE the skip -- with a comment, but no guard, which is why widening the
    sanction to the deformer family and the ik solver could re-create it.

    Both of those drive loops leave string inputs at their DEFAULT on either
    node, so the two take the same no-file fallback: the compare is real and only
    the decoded-pixel path goes unexercised, which the row's reason records."""

    def _source(self):
        from mpynode.native.toolchain import verify
        return _read_source(verify)

    def test_the_skip_excludes_the_bases_that_verify_for_real(self):
        src = self._source()
        guard = src.split("reads_img = spec_extractor.spec_reads_image_file", 1)
        self.assertEqual(len(guard), 2, "the image skip guard was renamed")
        guard = guard[1].split("return {", 1)[0]
        self.assertIn("_DEFORMER_BASES", guard)
        self.assertIn("_IKSOLVER_BASE", guard)

    def test_both_branches_record_the_unexercised_image_path(self):
        src = self._source()
        self.assertEqual(
            src.count('"tol": tol, "reason": _IMAGE_UNEXERCISED_NOTE '
                      'if reads_img else ""'),
            2, "the deformer and iksolver rows must both carry the caveat")
        self.assertIn("NOT exercised", src.split(
            "_IMAGE_UNEXERCISED_NOTE = ", 1)[1][:400])


class TestColorTupleLowers(unittest.TestCase):
    """A fully-numeric compute ending in ``self.outColor = (r, g, b)`` (a color
    output written from a tuple literal) now lowers DETERMINISTICALLY: the tuple
    packs a rank-1 nd::Array (py_to_cpp.ex_Tuple) and the color writer sets the
    FLOAT R/G/B children (set3Float) -- no AI PORT region."""

    def _spec(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="colorTupleSrc#")
        w.add_input_attr("uIn", "float")
        w.add_output_attr("outColor", "color")
        w.set_compute_expression(
            "self.outColor = (self.uIn, self.uIn * 0.5, 0.0)")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "colorTupleNode"
        return spec

    def test_tuple_color_output_lowers_no_port(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        # Deterministic lowering: no AI PORT region.
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        # createColor attr; the tuple packs an nd::Array, the color writer
        # sets the float children.
        self.assertIn("createColor", cpp)
        self.assertIn("h_aOutColor.set3Float", cpp)
        self.assertIn("nd::from_data<double>(", cpp)


class TestTransformMatrixInputScaffold(unittest.TestCase):
    """#46 (T5): a custom MPxTransform that declares SCALAR MATRIX inputs
    (aim_between_matrices' matrix0/matrix1) gains the matrix-input scaffold --
    kMatrix input attrs, an fNode back-ref synced each compute(), parentMatrix[0]
    read via LOGICAL index, and a setDependentsDirty override -- and its asMatrix
    math lowers deterministically (no AI PORT region). An input-LESS transform is
    byte-identical to the frame-only scaffold (no fNode / no created attrs)."""

    _AIM = (
        "m0 = self.matrix0.asNumpy()\n"
        "m1 = self.matrix1.asNumpy()\n"
        "p0 = m0[3, :3]\n"
        "p1 = m1[3, :3]\n"
        "fwd = p1 - p0\n"
        "length = float(np.linalg.norm(fwd))\n"
        "if length < 1e-9:\n"
        "    fwd = np.array([1.0, 0.0, 0.0])\n"
        "else:\n"
        "    fwd = fwd / length\n"
        "up = np.array([0.0, 1.0, 0.0])\n"
        "if abs(float(np.dot(fwd, up))) > 0.999:\n"
        "    up = np.array([0.0, 0.0, 1.0])\n"
        "side = np.cross(fwd, up)\n"
        "side = side / (float(np.linalg.norm(side)) + 1e-12)\n"
        "up2 = np.cross(side, fwd)\n"
        "c = 0.5 * (p0 + p1)\n"
        "row0 = np.concatenate([fwd, np.zeros(1)])\n"
        "row1 = np.concatenate([up2, np.zeros(1)])\n"
        "row2 = np.concatenate([side, np.zeros(1)])\n"
        "row3 = np.concatenate([c, np.ones(1)])\n"
        "M = np.stack([row0, row1, row2, row3])\n"
        # GATED LOCAL-MATRIX contract: M is the desired WORLD frame, made
        # parent-relative with inv(P) off a CONNECTED parentWorld input, then the
        # rotate/translate gates open so the scaffold drives offsetParentMatrix.
        # The node never reads its own DAG parent -- world placement is opt-in
        # via the connected parent input (cycle-free).
        "P = self.parentWorld.asNumpy()\n"
        "self.local_matrix = M @ np.linalg.inv(P)\n"
        "self.apply_rotate = True\n"
        "self.apply_translate = True\n"
    )

    def _spec(self, inputs, compute):
        return {
            "schema_version": 1, "source_node": "aimTransform",
            "mpy_type": "mPyTransform",
            "suggested": {"node_type_name": "aimTransform",
                          "class_name": "AimTransform",
                          "type_id": "0x00070200",
                          "mpx_base": "MPxTransform"},
            "inputs": inputs, "outputs": {},
            "compute": compute, "init": "import numpy as np\n",
            "affects": "all",
            "portability": {"portable": True, "blockers": [], "warnings": [],
                            "reads_image_file": False},
        }

    def test_matrix_input_transform_gains_scaffold_and_lowers(self):
        from mpynode.native import compiler as codegen
        spec = self._spec({"matrix0": {"type": "matrix", "is_array": False},
                           "matrix1": {"type": "matrix", "is_array": False},
                           "parentWorld": {"type": "matrix", "is_array": False}},
                          self._AIM)
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Deterministic lowering: no AI PORT region.
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        # The compute writes self.local_matrix + the apply_* gates; the scaffold
        # dispatches LOCAL > no-op via nd_gate_mix and returns the local D.
        self.assertIn("nd_gate_mix(", cpp)
        self.assertIn("local_set = true;", cpp)            # local_matrix sink hit
        self.assertIn("local_matrix.matrix[_r][_c]", cpp)  # scattered 4x4
        self.assertIn("apply_rotate = ((", cpp)            # gate writers
        self.assertIn("apply_translate = ((", cpp)
        # Dispatch: local_matrix > no-op guard (no world branch, no parent read).
        self.assertIn("if (!local_set || !any_gate) return m;", cpp)
        # Scaffold machinery.
        self.assertIn("MObject fNode;", cpp)
        self.assertIn("MStatus AimTransform::initialize()", cpp)
        self.assertIn('mAttr.create("matrix0"', cpp)
        self.assertIn('mAttr.create("matrix1"', cpp)
        self.assertIn('mAttr.create("parentWorld"', cpp)
        self.assertIn("addAttribute", cpp)
        self.assertIn("setDependentsDirty", cpp)
        self.assertIn("_syncNode", cpp)
        # FLUSH-FREE: the expression D lives in desiredLocal(), asMatrix() = TRS.
        self.assertIn("desiredLocal", cpp)
        self.assertIn("MPxTransformationMatrix::asMatrix()", cpp)
        # opm = inv(L) * D on the _outLocalFlat double[16] output, rebuilt by a
        # stock fourByFourMatrix relay -> offsetParentMatrix.
        self.assertIn("_outLocalFlat", cpp)
        self.assertIn(".inverse()", cpp)
        self.assertIn("fourByFourMatrix", cpp)
        # NO DAG-PARENT READ: the scaffold never touches MDagPath /
        # inclusiveMatrix / parentMatrix (the old stale-opm bug).
        self.assertNotIn("inclusiveMatrix", cpp)
        self.assertNotIn("parent_matrix", cpp)
        self.assertNotIn("MDagPath", cpp)
        # asMatrix binds the same locals the lowered body materialises from.
        self.assertIn("in_aMatrix0", cpp)
        self.assertIn("in_aMatrix1", cpp)
        self.assertIn("in_aParentWorld", cpp)

    def test_inputless_transform_gains_flushfree_scaffold(self):
        from mpynode.native import compiler as codegen
        # A constant local offset, no matrix inputs. Under the FLUSH-FREE
        # re-arch EVERY transform carries the opm scaffold (the desired matrix
        # rides offsetParentMatrix so descendants track), so the old
        # "byte-identical frame-only, no scaffold" contract is gone.
        compute = ("m = np.eye(4)\n"
                   "m[3, 0] = 1.5\n"
                   "self.local_matrix = m\n"
                   "self.apply_translate = True\n")
        spec = self._spec({}, compute)
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Deterministic lowering (no AI PORT region) + gated dispatch present.
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        self.assertIn("local_set = true;", cpp)
        self.assertIn("apply_translate = ((", cpp)
        self.assertIn("nd_gate_mix(m, local_matrix", cpp)
        # The flush-free scaffold is present even with no matrix inputs.
        self.assertIn("_outLocalFlat", cpp)
        self.assertIn("desiredLocal", cpp)
        self.assertIn("setDependentsDirty", cpp)
        self.assertIn("_syncNode", cpp)
        self.assertIn("fourByFourMatrix", cpp)
        # ...but NO matrix-input attrs are created (there are none declared).
        self.assertNotIn('mAttr.create("matrix', cpp)
        self.assertNotIn("in_aMatrix", cpp)

    def test_nonmatrix_transform_input_accepted(self):
        from mpynode.native import compiler as codegen
        # A non-matrix input rides the shared findPlug reader into an
        # in_a<ident> local (bound by nd_lower or handed to the porter).
        spec = self._spec({"gain": {"type": "float", "is_array": False}},
                          "self.local_matrix = np.eye(4)\n"
                          "self.apply_translate = True\n")
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("in_a_gain", cpp)
        self.assertIn('findPlug("gain"', cpp)

    def test_array_matrix_transform_input_accepted(self):
        from mpynode.native import compiler as codegen
        # A matrix ARRAY reads densely into std::vector<MMatrix> off the plug.
        spec = self._spec({"mats": {"type": "matrix", "is_array": True}},
                          "self.local_matrix = np.eye(4)\n"
                          "self.apply_translate = True\n")
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("std::vector<MMatrix> in_a_mats;", cpp)
        self.assertIn("elementByPhysicalIndex", cpp)
        # the array attr must be created through the matrix function set
        self.assertIn("MFnMatrixAttribute mAttr;", cpp)


# ===================== from test_bundler_locator_probe.py =====================
import json
import os
import re

import unittest

from ._setup import standalone_init


def _setUpModule__bundler_locator_probe():
    standalone_init()


def _id_for(_key):
    return "0x00070123"


def _pp_balance(txt):
    nif = len(re.findall(r"(?m)^\s*#\s*if", txt))
    nend = len(re.findall(r"(?m)^\s*#\s*endif", txt))
    return nif, nend


def _locator_cpp(needs_hover):
    from mpynode.native import compiler as codegen
    spec = {
        "schema_version": 1, "source_node": "gizmoCube", "mpy_type": "mPyLocator",
        "suggested": {"node_type_name": "gizmoCube", "class_name": "GizmoCube",
                      "type_id": "0x00070123", "mpx_base": "MPxLocatorNode",
                      "note": "", "heaviness": "hard"},
        "inputs": {"wire_width": {"type": "float", "is_array": False,
                                  "default_value": 2.0}},
        "outputs": {},
        "variables": {"prev_hovered": {"kind": "bool", "value": False},
                      "anim_start_t": {"kind": "float", "value": 0.0}},
        "compute": ("scale = 1.0 if self.hovered else 0.5\n"
                    "self.auto_refresh = True\nself.polygons = None\n"),
        "init": "", "affects": "all",
    }
    if needs_hover:
        spec["needs_hover"] = True
    return codegen._generate_locator_cpp(spec, for_port=True)


class TestProbeGuardFlatten(unittest.TestCase):

    def test_hover_locator_fragment_is_balanced_and_probe_free(self):
        from mpynode.native.compiler import bundler
        src = _locator_cpp(True)
        self.assertEqual(*_pp_balance(src), msg="source cpp must be balanced")
        frag, _ = bundler.transform_node_cpp(src, "gizmoCube", _id_for)
        nif, nend = _pp_balance(frag)
        self.assertEqual(nif, nend,
                         "fragment preprocessor directives must balance "
                         "(was %d #if / %d #endif)" % (nif, nend))
        self.assertNotIn("MPYNODE_PROBE", frag,
                         "a bundle never defines MPYNODE_PROBE; flatten it away")

    def test_non_hover_locator_fragment_is_balanced(self):
        from mpynode.native.compiler import bundler
        src = _locator_cpp(False)
        frag, _ = bundler.transform_node_cpp(src, "gizmoCube", _id_for)
        nif, nend = _pp_balance(frag)
        self.assertEqual(nif, nend)
        self.assertNotIn("MPYNODE_PROBE", frag)

    def test_probe_only_main_is_dropped_but_plugin_kept(self):
        from mpynode.native.compiler import bundler
        src = _locator_cpp(True)
        frag, _ = bundler.transform_node_cpp(src, "gizmoCube", _id_for)
        # probe-only int main() must be gone; the plugin scaffold must remain.
        self.assertNotIn("_readFrames", frag, "probe block must be dropped")
        self.assertIn("addUIDrawables", frag, "plugin scaffold must be kept")
        self.assertIn("register_GizmoCube", frag, "register hook must be emitted")


def _cpp_with_directive(block):
    """A minimal but complete node .cpp whose compute() contains ``block``."""
    return (
        "#include <maya/MPxNode.h>\n"
        "#include <maya/MGlobal.h>\n"
        "\n"
        "class N : public MPxNode {\n"
        "public:\n"
        "    static MTypeId id;\n"
        "    MStatus compute(const MPlug&, MDataBlock&);\n"
        "};\n"
        "MTypeId N::id(0x00070123);\n"
        "MStatus N::compute(const MPlug& p, MDataBlock& d) {\n"
        + block +
        "    return MS::kSuccess;\n"
        "}\n"
        'MStatus initializePlugin(MObject o) {\n'
        "    MFnPlugin fn(o);\n"
        '    fn.registerNode("gizmoCube", N::id, N::creator, N::initialize);\n'
        "    return MS::kSuccess;\n"
        "}\n"
        "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }\n"
    )


class TestNamespaceAnchorIgnoresInFunctionDirectives(unittest.TestCase):
    """The node namespace must open at GLOBAL scope.

    The preamble anchor used to be "the last column-0 '#' line". The AI
    optimizer emits column-0 conditionals INSIDE function bodies -- an
    ``#if NDPROF`` profiling block (comboCorrectives, patchRelax) and an
    ``#if defined(__APPLE__)`` sincos guard (helixCurve) -- so the anchor landed
    mid-function and the namespace opened there, and clang rejected the whole
    node with "namespaces can only be defined in global or namespace scope".
    Those three dropped out of the merged build while compiling fine on their
    own. The anchor now requires brace depth 0.
    """

    def _assert_global_scope(self, block):
        from mpynode.native.compiler import bundler
        src = _cpp_with_directive(block)
        frag, _info = bundler.transform_node_cpp(src, "gizmoCube", _id_for)
        marker = "\nnamespace nd_gizmoCube {"
        self.assertIn(marker, frag)
        head = frag[:frag.index(marker)]
        self.assertEqual(
            head.count("{"), head.count("}"),
            "namespace opened inside an unclosed block -- anchor landed "
            "mid-function")
        return frag

    def test_ndprof_block_in_compute_does_not_move_the_anchor(self):
        frag = self._assert_global_scope(
            "#if NDPROF\n"
            '    MGlobal::displayInfo("prof");\n'
            "#endif\n")
        self.assertIn("#if NDPROF", frag, "the block itself must be preserved")

    def test_apple_guard_in_compute_does_not_move_the_anchor(self):
        self._assert_global_scope(
            "#if defined(__APPLE__)\n"
            "    double s, c; __sincos(0.0, &s, &c);\n"
            "#else\n"
            "    double s = 0.0, c = 1.0;\n"
            "#endif\n"
            "    (void)s; (void)c;\n")

    def test_no_directive_in_compute_still_works(self):
        self._assert_global_scope("    int a = 1; (void)a;\n")

    def test_toplevel_directive_lines_skips_nested_depth(self):
        from mpynode.native.compiler import bundler
        head = ("#include <a.h>\n"
                "void f() {\n"
                "#if NDPROF\n"
                "    int x = 0;\n"
                "#endif\n"
                "}\n")
        self.assertEqual(bundler._toplevel_directive_lines(head), [0])

    def test_toplevel_directive_lines_ignores_braces_in_comments(self):
        from mpynode.native.compiler import bundler
        head = ("#include <a.h>\n"
                "// stray { brace in a comment\n"
                'const char* s = "}";\n'
                "#define LATE 1\n")
        self.assertEqual(bundler._toplevel_directive_lines(head), [0, 3])


def _color_locator_spec():
    """A locator with a color input (mesh_regions-style defaultColor)."""
    return {
        "schema_version": 1, "source_node": "tintGizmo",
        "mpy_type": "mPyLocator",
        "suggested": {"node_type_name": "tintGizmo", "class_name": "TintGizmo",
                      "type_id": "0x00070124", "mpx_base": "MPxLocatorNode",
                      "note": "", "heaviness": "hard"},
        "inputs": {"defaultColor": {"type": "color", "is_array": False,
                                    "default_value": [0.2, 0.4, 0.8]}},
        "outputs": {},
        "variables": {},
        "compute": ("self.draw = DrawMesh([[0,0,0]], [0], [1],\n"
                    "                     colors=self.defaultColor)\n"),
        "init": "", "affects": "all",
    }


class TestArrayElementTypeCoverage(unittest.TestCase):
    """Every _ARRAY_OK element type -- now incl. string/hex/color/quaternion --
    generates a valid array read (input) AND array write (output) on a plain
    MPxNode. Locks in the closed gap so array coverage never silently regresses."""

    def _arr_spec(self, t):
        return {
            "schema_version": 1, "source_node": "arrProbe", "mpy_type": "mPyNode",
            "suggested": {"node_type_name": "arrProbe", "class_name": "ArrProbe",
                          "type_id": "0x00070311", "mpx_base": "MPxNode"},
            "inputs": {"aIn": {"type": t, "is_array": True}},
            "outputs": {"aOut": {"type": t, "is_array": True}},
            "compute": "pass\n", "init": "", "affects": "all",
            "portability": {"portable": True, "blockers": [], "warnings": [],
                            "reads_image_file": False},
        }

    def test_all_array_ok_types_generate(self):
        from mpynode.native import compiler as codegen
        for t in sorted(codegen._ARRAY_OK):
            cpp = codegen.generate_cpp(self._arr_spec(t), for_port=False)
            self.assertIn("std::vector<", cpp, "%s: no vector decl" % t)
            self.assertIn("inputArrayValue", cpp, "%s: no array read" % t)
            self.assertIn("MArrayDataBuilder", cpp, "%s: no array write" % t)

    def test_string_array_reads_and_writes_strings(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._arr_spec("string"), for_port=False)
        self.assertIn("std::vector<MString>", cpp)
        self.assertIn("eh.asString()", cpp)
        self.assertIn("eh.setString(", cpp)

    def test_hex_array_transcodes_per_element(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._arr_spec("hex"), for_port=False)
        self.assertIn("nd_hex_decode(eh.asString())", cpp)
        self.assertIn("nd_hex_encode(", cpp)

    def test_color_array_is_float3_vector(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._arr_spec("color"), for_port=False)
        self.assertIn("std::vector<MFloatVector>", cpp)
        self.assertIn("MFloatVector(eh.asFloat3())", cpp)
        self.assertIn("eh.set3Float(", cpp)

    def test_quaternion_array_uses_compound_children(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._arr_spec("quaternion"), for_port=False)
        self.assertIn("std::vector<MQuaternion>", cpp)
        self.assertIn("MFnCompoundAttribute _qf(", cpp)
        self.assertIn("eh.child(_qf.child(0)).setDouble", cpp)

    def test_numeric_array_input_is_not_keyable(self):
        # A scalar-numeric multi INPUT must be non-keyable or Maya leaks it into
        # the channel box (float/int/bool arrays do; compound and dt-typed ones
        # don't). The is_array block emits setKeyable(false), overriding the
        # earlier keyable=true.
        from mpynode.native import compiler as codegen
        for t in ("float", "double", "int", "bool"):
            cpp = codegen.generate_cpp(self._arr_spec(t), for_port=False)
            self.assertIn("nAttr.setKeyable(false);", cpp,
                          "%s array input still keyable (channel-box leak)" % t)

    def test_scalar_single_input_stays_keyable(self):
        # A single (non-array) numeric input is unchanged: keyable, no keyable-off.
        from mpynode.native import compiler as codegen
        spec = self._arr_spec("double")
        spec["inputs"] = {"aIn": {"type": "double", "is_array": False}}
        spec["outputs"] = {"aOut": {"type": "double", "is_array": False}}
        cpp = codegen.generate_cpp(spec, for_port=False)
        self.assertIn("nAttr.setKeyable(true);", cpp)
        self.assertNotIn("nAttr.setKeyable(false);", cpp)


class TestLocatorColorInput(unittest.TestCase):
    """color-type locator inputs (added for mesh_regions' 3 color attrs) must be
    portability-accepted AND fully wired into the draw scaffold (create + read +
    seed) so they are never silently dropped."""

    def test_spec_model_accepts_color_locator_input(self):
        from mpynode.native.compiler import spec_model
        spec = _color_locator_spec()
        spec["portability"] = {"portable": True, "blockers": []}
        # Must NOT raise UnsupportedSpec (color was previously rejected).
        spec_model._check(spec)

    def test_color_input_is_wired_into_draw(self):
        from mpynode.native import compiler as codegen
        cpp = codegen._generate_locator_cpp(_color_locator_spec(), for_port=True)
        # attr created as a color, with the spec default applied
        self.assertIn('nAttr.createColor("defaultColor"', cpp)
        self.assertIn("nAttr.setDefault(", cpp)
        # DrawInputs carries the rgb triple
        self.assertIn("in_defaultColor[3]", cpp)
        # exposed to the (AI-ported) draw expression as an MColor local
        self.assertIn("MColor in_defaultColor(", cpp)
        # read off the plug's 3 children on the plugin side
        self.assertIn(".child(0).asFloat()", cpp)
        self.assertIn("a_in_defaultColor", cpp)


class TestLocatorOrderedDrawTransport(unittest.TestCase):
    """The compiled locator carries the drawing as an ORDERED command list --
    one record per authored DrawItem -- exactly like draw_types.to_commands().
    The old shape (per-type SoA replayed in a fixed type order, plus ONE
    polygon soup gated by ``hasPoly``) could not express two DrawMeshes with
    different styles, and drew types in a different order than the interpreted
    renderer. Both are structural; pin them."""

    def _cpp(self, for_port=True):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp(_color_locator_spec(),
                                             for_port=for_port)

    def test_draw_data_holds_an_ordered_command_list(self):
        cpp = self._cpp()
        self.assertIn("struct DrawCmd {", cpp)
        self.assertIn("std::vector<DrawCmd>  cmds;", cpp)

    def test_polygons_are_a_vector_not_a_single_soup(self):
        cpp = self._cpp()
        self.assertIn("struct DrawPoly {", cpp)
        self.assertIn("std::vector<DrawPoly> polys;", cpp)
        # the single-soup members are GONE (they forced a one-mesh-per-frame cap)
        for dead in ("hasPoly", "polyPts", "polyIdx", "polyCnt",
                     "polyColorMode", "polyWorldSpace"):
            self.assertNotIn(dead, cpp, "%s survived the ordered-transport port"
                             % dead)

    def test_every_slot_has_an_emit_helper(self):
        cpp = self._cpp()
        for helper in ("void emitLine(", "void emitPoint(", "void emitText(",
                       "void emitShape(", "DrawPoly& emitPoly()"):
            self.assertIn(helper, cpp, "missing %s" % helper)

    def test_emit_helpers_append_to_the_command_list(self):
        # a payload push that does NOT record a DrawCmd draws nothing
        cpp = self._cpp()
        for slot in range(5):
            self.assertIn("cmds.push_back(DrawCmd(%d," % slot, cpp)

    def test_add_ui_drawables_replays_the_commands_in_order(self):
        cpp = self._cpp()
        self.assertIn("for (size_t ci = 0; ci < d->cmds.size(); ++ci) {", cpp)
        self.assertIn("switch (d->cmds[ci].slot) {", cpp)
        # the polygon body moved into a per-record helper the loop dispatches to
        self.assertIn("_drawPoly(dm, *d, d->polys[i], wInv);", cpp)

    def test_lines_honour_world_space(self):
        # world-space lines were only reachable through the removed dict slot.
        # DrawLines/DrawCurve carry the flag now, so the compiled renderer must
        # rebase them like world-space polygons.
        cpp = self._cpp()
        self.assertIn("std::vector<char>     lineWorld;", cpp)
        self.assertIn("if (d->lineWorld[i]) { a = a * wInv; b = b * wInv; }", cpp)

    def test_hover_soup_gathers_across_every_precise_polygon(self):
        from mpynode.native import compiler as codegen
        spec = _color_locator_spec()
        spec["compute"] += "self.precise_hover = True\n"
        spec["needs_hover"] = True
        cpp = codegen._generate_locator_cpp(spec, for_port=True)
        self.assertIn("for (size_t pi = 0; pi < d.polys.size(); ++pi) {", cpp)
        self.assertIn("if (!(d.preciseHover || pg.preciseHover)) continue;", cpp)


class TestFlattenHelperIsNoOpForNonProbeNodes(unittest.TestCase):
    """A node .cpp with no MPYNODE_PROBE guard is returned byte-identical."""

    def test_flatten_no_op(self):
        from mpynode.native.compiler import bundler
        src = ("#include <maya/MPxNode.h>\n\nclass Foo {};\n"
               "MStatus initializePlugin(MObject o){ return MS::kSuccess; }\n"
               "MStatus uninitializePlugin(MObject o){ return MS::kSuccess; }\n")
        self.assertEqual(bundler._flatten_probe_guards(src), src)


# ===================== from test_codegen_metadata.py =====================
import copy
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__codegen_metadata():
    standalone_init()
    ensure_plugins_loaded()


_INIT_RE = re.compile(
    r'MFnPlugin plugin\(obj, "(?P<vendor>[^"]*)", '
    r'"(?P<version>[^"+]+)\+(?P<hash>[0-9a-f]{12})", "Any"\);')


def _base_spec(node_type_name="metaCgNode"):
    from mpynode.native.spec import spec_extractor
    from mpynode import MPyNode
    import maya.cmds as cmds

    cmds.file(new=True, force=True)
    w = MPyNode.create(name="metaCgSrc#")
    w.add_input_attr("uIn", "float")
    w.add_output_attr("outVal", "float")
    w.set_compute_expression("self.outVal = self.uIn * 2.0")
    spec = spec_extractor.extract_spec(w.get_name())
    spec["suggested"]["node_type_name"] = node_type_name
    return spec


def _locator_spec__codegen_metadata(node_type_name="metaCgLoc"):
    from mpynode.native.spec import spec_extractor
    from mpynode.wrappers.mpy_locator import MPyLocator
    import maya.cmds as cmds

    cmds.file(new=True, force=True)
    loc = MPyLocator.create(name="metaCgLocSrc#")
    loc.set_compute_expression("self.polygons = None\n")
    spec = spec_extractor.extract_spec(loc.get_name())
    spec["suggested"]["node_type_name"] = node_type_name
    return spec


class TestCodegenMetadataEmbedding(unittest.TestCase):
    def test_banner_and_version_with_metadata(self):
        from mpynode.native import compiler as codegen

        spec = _base_spec()
        spec["metadata"] = {
            "authors": ["Jane Doe <jane@acme.io>"],
            "version": "2.3.1",
            "license": "(c) 2026 Acme Studios\nMIT",
        }
        cpp = codegen.generate_cpp(spec, for_port=False)

        # banner present at the very top, before any #include
        head = cpp[: cpp.index("#include")]
        self.assertIn("Jane Doe <jane@acme.io>", head)
        self.assertIn("(c) 2026 Acme Studios", head)
        self.assertIn("2.3.1", head)
        self.assertIn("MIT", head)

        # placeholder fully substituted everywhere
        from mpynode._common.lifecycle import metadata_registry as M
        self.assertNotIn(M.BUILD_HASH_PLACEHOLDER, cpp)

        # MFnPlugin init line carries vendor + version + hash
        m = _INIT_RE.search(cpp)
        self.assertIsNotNone(m, "no stamped MFnPlugin init line found")
        # the vendor is the AUTHORS now -- a license block leads with a term,
        # not a party, so it is deliberately not consulted.
        self.assertEqual(m.group("vendor"), "Jane Doe <jane@acme.io>")
        self.assertEqual(m.group("version"), "2.3.1")
        # banner build hash == version hash
        self.assertIn("build: " + m.group("hash"), cpp)

    def test_no_metadata_still_emits_hash_and_default(self):
        from mpynode.native import compiler as codegen
        from mpynode._common.lifecycle import metadata_registry as M

        spec = _base_spec("metaCgPlain")
        self.assertNotIn("metadata", spec)
        cpp = codegen.generate_cpp(spec, for_port=False)
        self.assertNotIn(M.BUILD_HASH_PLACEHOLDER, cpp)
        m = _INIT_RE.search(cpp)
        self.assertIsNotNone(m)
        self.assertEqual(m.group("vendor"), M.DEFAULT_VENDOR)
        self.assertEqual(m.group("version"), M.DEFAULT_VERSION)

    def test_hash_deterministic_for_same_spec(self):
        from mpynode.native import compiler as codegen

        spec = _base_spec("metaCgDet")
        spec["metadata"] = {"license": "(c) X"}
        a = codegen.generate_cpp(spec, for_port=False)
        b = codegen.generate_cpp(spec, for_port=False)
        self.assertEqual(a, b)

    def test_different_specs_differ_in_hash(self):
        from mpynode.native import compiler as codegen

        spec1 = _base_spec("metaCgA")
        spec2 = _base_spec("metaCgB")  # different node type name -> different cpp
        h1 = _INIT_RE.search(codegen.generate_cpp(spec1)).group("hash")
        h2 = _INIT_RE.search(codegen.generate_cpp(spec2)).group("hash")
        self.assertNotEqual(h1, h2)

    def test_metadata_change_changes_hash(self):
        # the hash must react to a METADATA change, not just the node type.
        # Varying a BANNER-ONLY field exercises stamp_build_hash(banner + cpp).
        from mpynode.native import compiler as codegen

        base = _base_spec("metaCgHashSens")
        s1 = copy.deepcopy(base); s1["metadata"] = {"description": "alpha"}
        s2 = copy.deepcopy(base); s2["metadata"] = {"description": "beta"}
        h1 = _INIT_RE.search(codegen.generate_cpp(s1)).group("hash")
        h2 = _INIT_RE.search(codegen.generate_cpp(s2)).group("hash")
        self.assertNotEqual(h1, h2)

    def test_version_with_plus_is_sanitized(self):
        # a '+' in a user version would make '<version>+<hash>' ambiguous, so it
        # is sanitized: the build hash stays the single trailing '+<hash12>'.
        from mpynode.native import compiler as codegen

        spec = _base_spec("metaCgPlus")
        spec["metadata"] = {"version": "2.0+rc1"}
        cpp = codegen.generate_cpp(spec)
        m = _INIT_RE.search(cpp)
        self.assertIsNotNone(m, "version+hash not parseable after a '+' version")
        self.assertEqual(m.group("version"), "2.0-rc1")

    def test_uninitialize_plugin_line_untouched(self):
        from mpynode.native import compiler as codegen

        spec = _base_spec("metaCgUninit")
        spec["metadata"] = {"license": "(c) Y"}
        cpp = codegen.generate_cpp(spec, for_port=False)
        self.assertIn("MFnPlugin plugin(obj);", cpp)  # deregister form intact

    def test_locator_path_also_embeds(self):
        from mpynode.native import compiler as codegen
        from mpynode._common.lifecycle import metadata_registry as M

        spec = _locator_spec__codegen_metadata()
        spec["metadata"] = {"authors": ["Loc Author"], "version": "5.0"}
        cpp = codegen.generate_cpp(spec, for_port=False)
        self.assertNotIn(M.BUILD_HASH_PLACEHOLDER, cpp)
        m = _INIT_RE.search(cpp)
        self.assertIsNotNone(m, "locator path did not embed a stamped version")
        self.assertEqual(m.group("vendor"), "Loc Author")
        self.assertEqual(m.group("version"), "5.0")

    def test_cpp_string_special_chars_escaped(self):
        from mpynode.native import compiler as codegen

        spec = _base_spec("metaCgEsc")
        spec["metadata"] = {"authors": ['He said "hi"\nback']}
        cpp = codegen.generate_cpp(spec, for_port=False)
        # the vendor string literal must be a valid single-line C++ literal:
        # quotes escaped, newline collapsed.
        self.assertIn(r'MFnPlugin plugin(obj, "He said \"hi\" back",', cpp)


# ===================== from test_locator_hover_codegen.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init


def _setUpModule__locator_hover_codegen():
    standalone_init()


def _locator_spec__locator_hover_codegen(needs_hover):
    spec = {
        "schema_version": 1,
        "source_node": "gizmoCube",
        "mpy_type": "mPyLocator",
        "suggested": {
            "node_type_name": "gizmoCube", "class_name": "GizmoCube",
            "type_id": "0x00070123", "mpx_base": "MPxLocatorNode",
            "note": "viewport draw override", "heaviness": "hard",
        },
        "inputs": {
            "wire_width": {"type": "float", "is_array": False,
                           "default_value": 2.0, "portable": True},
        },
        "outputs": {},
        "variables": {
            "prev_hovered": {"kind": "bool", "value": False, "bake": False},
            "anim_start_t": {"kind": "float", "value": 0.0, "bake": False},
        },
        "compute": ("scale = 1.0 if self.hovered else 0.5\n"
                    "self.auto_refresh = True\n"
                    "self.polygons = None\n"),
        "init": "",
        "affects": "all",
    }
    if needs_hover:
        spec["needs_hover"] = True
    return spec


class TestNonHoverLocatorUnchanged(unittest.TestCase):
    """Zero blast radius: a locator without needs_hover keeps today's output."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(_locator_spec__locator_hover_codegen(False))

    def test_keeps_hardcoded_hover_and_wallclock(self):
        self.assertIn("inp.hovered = false;", self.cpp)
        self.assertIn("inp.wallClock = 0.0;", self.cpp)

    def test_no_qt_or_hover_service(self):
        for tok in ("QtGui/QCursor", "MTimerMessage", "steady_clock",
                    "setGeometryDrawDirty"):
            self.assertNotIn(tok, self.cpp,
                             "%s must not appear for a non-hover locator" % tok)


class TestHoverLocatorCodegen(unittest.TestCase):
    """A needs_hover locator gains the live hover/clock/persistence machinery."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(_locator_spec__locator_hover_codegen(True))

    def test_hover_no_longer_hardcoded_false(self):
        self.assertNotIn("inp.hovered = false;", self.cpp)
        self.assertNotIn("inp.wallClock = 0.0;", self.cpp)

    def test_emits_qt_cursor_hover_service(self):
        self.assertIn("QtGui/QCursor", self.cpp)
        self.assertIn("MTimerMessage", self.cpp)
        self.assertIn("viewToWorld", self.cpp)
        self.assertIn("setGeometryDrawDirty", self.cpp)

    def test_live_wall_clock(self):
        self.assertIn("steady_clock", self.cpp)

    def test_qt_is_inside_probe_guard(self):
        # Qt + the hover service must be plugin-only so the probe stays Qt-free.
        self.assertIn("#ifndef MPYNODE_PROBE", self.cpp)
        self.assertLess(self.cpp.index("#ifndef MPYNODE_PROBE"),
                        self.cpp.index("QtGui/QCursor"),
                        "Qt include must be inside the plugin-only guard")

    def test_cross_frame_persistence_is_file_static_not_muserdata(self):
        # A file-static per-node tween map (keyed by node hash): stored vars are
        # seeded once and persist across frames here, not in MUserData.
        self.assertIn("MObjectHandle", self.cpp)
        # the mutated stored-var locals are written back out of computeBuffers
        self.assertIn("data.sv_prev_hovered = prev_hovered;", self.cpp)
        self.assertIn("data.sv_anim_start_t = anim_start_t;", self.cpp)

    def test_data_has_stored_var_conduit_members(self):
        # computeBuffers writes the mutated locals into Data's sv_* conduit
        # members; prepareForDraw then persists them to the static map.
        self.assertIn("sv_prev_hovered", self.cpp)
        self.assertIn("sv_anim_start_t", self.cpp)

    def test_probe_main_still_present_and_buildable_region(self):
        # The probe path is untouched (still emitted) -- numerical parity stays.
        self.assertIn("#ifdef MPYNODE_PROBE", self.cpp)
        self.assertIn("_readFrames", self.cpp)


class TestHoverReviewFixes(unittest.TestCase):
    """Adversarial-review hardening (2026-06-19): per-node teardown + a
    write-back that survives an early return in the AI-ported body."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(_locator_spec__locator_hover_codegen(True))

    def test_per_node_removal_callback_evicts_state(self):
        # Review #1: without a per-node delete callback g_tween/g_handles leak,
        # and a reused node hash hands a new locator a dead node's tween.
        self.assertIn("addNodePreRemovalCallback", self.cpp)
        self.assertIn("g_tween.erase", self.cpp)
        self.assertIn("g_handles.erase", self.cpp)
        self.assertIn("g_hoverTris.erase", self.cpp)
        self.assertIn("g_autoRefresh.erase", self.cpp)

    def test_removal_callbacks_torn_down_on_scene_event(self):
        # The per-node callback ids must be removed on file-new / unload, not leak.
        self.assertIn("g_removalCbs", self.cpp)

    def test_writeback_survives_early_return_in_ported_body(self):
        # Review #2: the ported body is an IIFE, so a bare `return;` exits only
        # the body and the sv_* write-back still runs.
        from mpynode.native import compiler as codegen
        lam = self.cpp.index("[&]() {")
        pb = self.cpp.index(codegen.PORT_BEGIN)
        pe = self.cpp.index(codegen.PORT_END)
        wb = self.cpp.index("data.sv_prev_hovered = prev_hovered;")
        self.assertLess(lam, pb, "IIFE must open before the ported body")
        self.assertLess(pe, wb, "write-back must come after the ported body")
        # and after the lambda closes
        self.assertIn("}();", self.cpp)

    def test_g_started_latched_only_on_timer_success(self):
        # Review #5: a transient timer-registration failure must not be
        # permanent -- undo the half-registered scene callbacks and retry.
        self.assertIn("registration failed", self.cpp)


class TestStoredVarSeedLockstep(unittest.TestCase):
    """The persisted Tween seed and the Inputs sv_* default must come from the
    same spec value, or rest-state plugin-vs-probe parity would drift."""

    def test_inputs_default_and_persist_seed_agree(self):
        from mpynode.native import compiler as codegen
        cpp = codegen._generate_locator_cpp(_locator_spec__locator_hover_codegen(True))
        # Inputs seeds sv_anim_start_t from the stored-var value 0.0; the
        # persistence seed must use the same literal.
        self.assertIn("sv_anim_start_t = 0.0", cpp)


class TestShapeSwitchMatchesInterpreted(unittest.TestCase):
    """addUIDrawables' shape switch must cover every kind the lowering emits.
    Kind 4 (DrawCylinder) used to fall through to ``default: dm.circle()``,
    so a compiled cylinder drew a flat circle."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(
            _locator_spec__locator_hover_codegen(False))

    def test_cylinder_geometry_matches_interpreted(self):
        # _api2/mpy_locator.py: dm.cylinder(center, axis, r, r * 2.0, 16, f)
        self.assertIn(
            "case 4: dm.cylinder(d->shapeCenter[i], d->shapeAxis[i], "
            "d->shapeRadius[i], d->shapeRadius[i]*2.0, 16, fl); break;",
            self.cpp)

    def test_every_lowered_shape_kind_has_its_own_case(self):
        # lockstep with the lowering's kind table -- a kind with no case falls
        # through to the circle default and silently draws the wrong shape.
        from mpynode.native.compiler.kernels import locator_draw_cpp
        for ctor, kind in locator_draw_cpp._SHAPE_KINDS.items():
            self.assertIn("case %d: dm." % kind, self.cpp,
                          "%s lowers to kind %d with no draw case" % (ctor, kind))


class TestAutoHighlightWiredIntoDraw(unittest.TestCase):
    """self.auto_highlight gates the selection tint (the framework's
    MPyLocatorDrawOverride passes override_color when selected AND
    auto_highlight); polygons resolve it per aspect."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(
            _locator_spec__locator_hover_codegen(False))

    def test_hl_all_is_selected_and_auto_highlight(self):
        self.assertIn("const bool hlAll = (d->selected && d->autoHighlight);",
                      self.cpp)

    def test_every_non_poly_slot_tints_through_hl_all(self):
        for buf in ("lineColor", "pointColor", "textColor", "shapeColor"):
            self.assertIn("dm.setColor(hlAll ? d->selColor : d->%s[i]);" % buf,
                          self.cpp)

    def test_poly_highlight_flags_inherit_via_minus_one_sentinel(self):
        # -1 == unset -> inherit the node-wide auto_highlight (interpreted
        # buf.get("highlight_fill", auto_highlight)); 0/1 == set explicitly.
        self.assertIn("int    highlightFill = -1;", self.cpp)
        self.assertIn("int    highlightWire = -1;", self.cpp)
        self.assertIn("const bool hlFill = (pg.highlightFill < 0) ? d.autoHighlight",
                      self.cpp)
        self.assertIn("const bool hlWire = (pg.highlightWire < 0) ? d.autoHighlight",
                      self.cpp)

    def test_poly_tint_consumes_the_resolved_flags(self):
        self.assertIn("const bool tintFill = (selOK && hlFill);", self.cpp)
        self.assertIn("(selOK && hlWire) ? d.selColor : pg.wireColor", self.cpp)


class TestNonHoverStoredVarsPersist(unittest.TestCase):
    """A locator that only mutates stored vars still gets the cross-frame
    g_tween map: the interpreted node commits stored vars back on EVERY draw
    evaluation, hover or not."""

    def setUp(self):
        from mpynode.native import compiler as codegen
        self.cpp = codegen._generate_locator_cpp(
            _locator_spec__locator_hover_codegen(False))

    def test_tween_map_emitted_without_hover(self):
        self.assertIn("static std::map<unsigned, GizmoCubeTween> g_tween;",
                      self.cpp)

    def test_stored_vars_seeded_from_last_frame(self):
        self.assertIn("inp.sv_prev_hovered = _tw.prev_hovered;", self.cpp)
        self.assertIn("inp.sv_anim_start_t = _tw.anim_start_t;", self.cpp)

    def test_mutated_stored_vars_written_back(self):
        self.assertIn("_tw.prev_hovered = data->sv_prev_hovered;", self.cpp)
        self.assertIn("_tw.anim_start_t = data->sv_anim_start_t;", self.cpp)

    def test_per_node_teardown_without_the_hover_only_maps(self):
        # same delete-callback eviction (a reused node hash must not inherit a
        # dead node's tween), minus the hover maps this node has no use for.
        self.assertIn("addNodePreRemovalCallback", self.cpp)
        self.assertIn("g_tween.erase(hash);", self.cpp)
        self.assertNotIn("g_handles", self.cpp)


# ===================== from test_euler_support.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__euler_support():
    standalone_init()
    ensure_plugins_loaded()  # live MPyNode.create needs the api plugins


class TestEulerTypeTables(unittest.TestCase):
    """Pure table membership -- no Maya needed."""

    def test_euler_is_supported(self):
        from mpynode.native import compiler as codegen
        self.assertIn("euler", codegen._SUPPORTED)

    def test_euler_array_is_supported(self):
        from mpynode.native import compiler as codegen
        self.assertIn("euler", codegen._ARRAY_OK)

    def test_euler_has_cpp_element_type(self):
        from mpynode.native import compiler as codegen
        self.assertIn("euler", codegen._CPP)


class TestEulerGeneratedVerifyScripts(unittest.TestCase):
    """The standalone ``verify_in_maya.py`` scripts that ship beside each ported
    node must SAMPLE + SET a euler input as a double3 triple, exactly like
    vector. Pre-fix ``_sample``/``_set`` handled only ``vector`` (``if t ==
    "vector"``), so a euler input fell through to the scalar path -> a single
    random float fed to ``setAttr`` on a double3 compound (wrong/raises). Mirrors
    the in-process fix in ``compile_controller._verify_one`` (setv/smp).
    These generators are pure spec->str (no Maya needed)."""

    def _scalar_spec(self):
        return {
            "suggested": {"node_type_name": "eulerVScalar", "mpx_base": "MPxNode"},
            "source_node": "eulerVScalarSrc1",
            "mpy_type": "mPyNode",
            "inputs": {"rin": {"type": "euler"}},
            "outputs": {"rout": {"type": "euler"}},
        }

    def _deformer_spec(self):
        return {
            "suggested": {"node_type_name": "eulerVDef",
                          "mpx_base": "MPxDeformerNode"},
            "source_node": "eulerVDefSrc1",
            "mpy_type": "mPyDeformer",
            "compute": "", "init": "",
            "inputs": {"rin": {"type": "euler"}},
            "outputs": {},
        }

    def test_scalar_verify_script_samples_and_sets_euler_like_vector(self):
        from mpynode.native.ai import porter
        script = porter._verify_script_scalar(self._scalar_spec())
        # euler joins vector in BOTH _sample (triple) and _set (type=double3).
        self.assertIn('if t in ("vector", "euler")', script)
        self.assertGreaterEqual(script.count('"vector", "euler"'), 2,
                                "euler must be handled in both _sample and _set")
        # The old vector-only form must be gone (else euler still falls through).
        self.assertNotIn('if t == "vector"', script)

    def test_deformer_verify_script_samples_and_sets_euler_like_vector(self):
        from mpynode.native.ai import porter
        script = porter._verify_script_deformer(self._deformer_spec())
        self.assertIn('if t in ("vector", "euler")', script)
        self.assertGreaterEqual(script.count('"vector", "euler"'), 2,
                                "euler must be handled in both _sample and _set")
        self.assertNotIn('if t == "vector"', script)


class TestEulerCodegen(unittest.TestCase):
    """A euler attr must now generate C++ instead of raising UnsupportedSpec."""

    def _spec(self, *, array=False):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="eulerSrc#")
        w.add_input_attr("rotIn", "euler", is_array=array)
        w.add_output_attr("rotOut", "euler", is_array=array)
        w.set_compute_expression("self.rotOut = self.rotIn")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "eulerTestNode"
        return spec

    def test_scalar_euler_generates_cpp(self):
        from mpynode.native import compiler as codegen

        spec = self._spec(array=False)
        # Pre-fix this raised codegen.UnsupportedSpec.
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Children are doubleAngle (MFnUnitAttribute kAngle), not plain kDouble.
        self.assertIn("MFnUnitAttribute::kAngle", cpp)
        # Read as a double3 of radians (mirrors the verified single 'angle').
        self.assertIn("asDouble3", cpp)
        # Named X/Y/Z children + a numeric compound parent (like vector).
        self.assertIn("rotInX", cpp)

    def test_array_euler_generates_cpp(self):
        from mpynode.native import compiler as codegen

        spec = self._spec(array=True)
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Array machinery present (element loop) and still angle children.
        self.assertIn("MFnUnitAttribute::kAngle", cpp)
        self.assertIn("setArray(true)", cpp)

    def test_euler_was_the_only_change_vector_still_works(self):
        """Guard: adding euler must not break the sibling vector path."""
        from mpynode.native.spec import spec_extractor
        from mpynode.native import compiler as codegen
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="vecSrc#")
        w.add_input_attr("v", "vector")
        w.add_output_attr("o", "vector")
        w.set_compute_expression("self.o = self.v")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "vecTestNode"
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("MFnNumericData::kDouble", cpp)  # vector keeps kDouble kids


class TestQuaternionCodegen(unittest.TestCase):
    """A quaternion attr generates C++ as a generic 4-double compound (X/Y/Z/W).

    Unlike vector/euler (numeric double3 parents read via asDouble3), a
    quaternion is a generic compound -- children are accessed through
    MFnCompoundAttribute in initialize() + compute()."""

    def _spec(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="quatSrc#")
        w.add_input_attr("qIn", "quaternion")
        w.add_output_attr("qOut", "quaternion")
        w.set_compute_expression("self.qOut = self.qIn")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "quatTestNode"
        return spec

    def test_quaternion_is_supported(self):
        from mpynode.native import compiler as codegen

        self.assertIn("quaternion", codegen._SUPPORTED)

    def test_scalar_quaternion_generates_cpp(self):
        from mpynode.native import compiler as codegen

        spec = self._spec()
        cpp = codegen.generate_cpp(spec, for_port=True)
        # Generic compound built via MFnCompoundAttribute with X/Y/Z/W children.
        self.assertIn("MFnCompoundAttribute", cpp)
        self.assertIn("qInX", cpp)
        self.assertIn("qInW", cpp)
        # Children are plain kDouble.
        self.assertIn("MFnNumericData::kDouble", cpp)

    def test_quaternion_array_is_now_supported(self):
        # quaternion is in _ARRAY_OK (was rejected): the array input reads into
        # std::vector<MQuaternion>, addressing each element's 4 compound
        # children through an MFnCompoundAttribute (_qf).
        from mpynode.native.spec import spec_extractor
        from mpynode.native import compiler as codegen
        from mpynode import MPyNode
        import maya.cmds as cmds

        self.assertIn("quaternion", codegen._ARRAY_OK)
        cmds.file(new=True, force=True)
        w = MPyNode.create(name="quatArrSrc#")
        w.add_input_attr("qIn", "quaternion", is_array=True)
        w.add_output_attr("qOut", "quaternion", is_array=True)
        w.set_compute_expression("pass")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "quatArrNode"
        cpp = codegen.generate_cpp(spec, for_port=False)  # complete stub
        self.assertIn("std::vector<MQuaternion>", cpp)
        self.assertIn("MFnCompoundAttribute _qf(", cpp)
        self.assertIn("MQuaternion(eh.child(_qf.child(0)).asDouble()", cpp)


class TestHexCodegen(unittest.TestCase):
    """A `hex` attr must transcode in generated C++ exactly like the interpreter:
    DECODE the stored space-separated UTF-8 hex on READ (so the ported compute
    sees plain text) and hex-ENCODE the plain-text output buffer on WRITE."""

    def _spec(self, compute="self.labelOut = self.labelIn"):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="hexSrc#")
        w.add_input_attr("labelIn", "hex")
        w.add_output_attr("labelOut", "hex")
        w.set_compute_expression(compute)
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "hexTestNode"
        return spec

    def test_hex_is_supported(self):
        from mpynode.native import compiler as codegen

        self.assertIn("hex", codegen._SUPPORTED)

    def test_emits_transcode_helpers_and_string_include(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        # Maya-free std::string core + MString adapters, emitted above the class.
        self.assertIn("nd_hex_encode_str", cpp)
        self.assertIn("nd_hex_decode_str", cpp)
        self.assertIn("MString nd_hex_encode(", cpp)
        self.assertIn("MString nd_hex_decode(", cpp)
        # the core uses std::string -> the include must be present.
        self.assertIn("#include <string>", cpp)
        # the helpers must be defined BEFORE the class that calls them.
        self.assertLess(cpp.index("nd_hex_decode_str"),
                        cpp.index("class "))

    def test_hex_input_is_decoded(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        # the input read decodes the stored hex, not a bare asString().
        self.assertIn("in_aLabelIn = nd_hex_decode(", cpp)
        self.assertIn("data.inputValue(aLabelIn).asString()", cpp)
        # the raw-asString form (what a plain `string` would emit) must be gone
        # for the hex input.
        self.assertNotIn("const MString in_aLabelIn = data.inputValue(aLabelIn).asString();",
                         cpp)

    def test_hex_output_uses_plaintext_buffer_then_encodes(self):
        from mpynode.native import compiler as codegen

        # This covers the AI-PORT hex path, so the compute must be one the
        # transpiler does NOT lower (a pass-through lowers deterministically --
        # see test_hex_output_deterministic_encodes).
        cpp = codegen.generate_cpp(
            self._spec("self.labelOut = self.labelIn.upper()"), for_port=True)
        # the ported body writes a PLAIN-text MString buffer...
        self.assertIn("MString out_aLabelOut;", cpp)
        # ...which codegen hex-encodes into the handle at finalize.
        self.assertIn("h_aLabelOut.setString(nd_hex_encode(out_aLabelOut));", cpp)
        # the hint tells the porter to write plain text.
        self.assertIn("write PLAIN text", cpp)
        # no raw setString("") seed in the handles section -- the hex output's
        # handle is fetched only at finalize.
        self.assertNotIn('h_aLabelOut.setString("");', cpp)

    def test_hex_output_deterministic_encodes(self):
        """A hex pass-through lowers to pure C++ (no PORT region) and still
        hex-ENCODES on the way out -- the deterministic sibling of the test
        above."""
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("nd_hex_encode(", cpp)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)

    def test_plain_string_attr_is_not_transcoded(self):
        """A `string` attr must NOT be routed through the hex transcode (guards
        against the change leaking onto the sibling string type)."""
        from mpynode.native.spec import spec_extractor
        from mpynode.native import compiler as codegen
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="strSrc#")
        w.add_input_attr("sIn", "string")
        w.add_output_attr("sOut", "string")
        w.set_compute_expression("self.sOut = self.sIn")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "strTestNode"
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertNotIn("nd_hex_encode", cpp)
        self.assertNotIn("nd_hex_decode", cpp)
        # plain string keeps the raw asString read + setString write.
        self.assertIn("const MString in_aSIn = data.inputValue(aSIn).asString();",
                      cpp)


class TestNurbsCurveInputCodegen(unittest.TestCase):
    """A nurbsCurve INPUT attr must (1) be created as a kNurbsCurve typed attr,
    (2) be read into a ready-to-use MFnNurbsCurve local, and (3) pull in the
    curve/point/xform headers -- so the AI porter can translate MFnNurbsCurve
    queries (spine's findParamFromLength/getPointAtParam/tangent + the
    om.MTransformationMatrix euler decomposition) to pure C++."""

    def _spec(self):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="crvSrc#")
        w.add_input_attr("inCrv", "nurbsCurve")
        w.add_output_attr("outP", "vector")
        # Reference self.inCrv so the input survives into the port spec.
        w.set_compute_expression("c = self.inCrv\nself.outP = [0.0, 0.0, 0.0]\n")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "crvTestNode"
        return spec

    def test_attr_created_as_knurbscurve(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn('tAttr.create("inCrv", "inCrv", MFnData::kNurbsCurve);', cpp)

    def test_read_builds_mfnnurbscurve(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn(".asNurbsCurve()", cpp)
        self.assertIn("MFnNurbsCurve in_aInCrv(", cpp)

    def test_curve_headers_included(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("#include <maya/MFnNurbsCurve.h>", cpp)
        self.assertIn("#include <maya/MPoint.h>", cpp)
        self.assertIn("#include <maya/MTransformationMatrix.h>", cpp)


class TestPhase0HonestRejectGuard(unittest.TestCase):
    """A plain-MPxNode compute that READS a ``self.<attr>`` which is neither a
    declared input/output nor assigned anywhere (compute/init) pulls a value from
    OUTSIDE the compiled node (a stored var set by external setup, or a live scene
    query) -- the AI port would compile but silently no-op. ``generate_cpp`` must
    honestly reject it (UnsupportedSpec -> build_status "dropped") instead. This
    is the keystone guard that catches procrustes_cluster/tags. It must NOT fire
    for nodes that read only declared attrs, nor for stateful nodes whose member
    state is WRITTEN in-source (spring_chain velocity, dnet previous)."""

    def _node(self, compute, init=""):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="p0Src#")
        w.add_input_attr("a", "float")
        w.add_output_attr("out", "float")
        if init.strip():
            w.set_init_expression(init)
        w.set_compute_expression(compute)
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "p0TestNode"
        return spec

    def test_undeclared_self_read_rejects(self):
        from mpynode.native import compiler as codegen
        # `someStored` is read but never declared and never written -> orphan.
        spec = self._node("self.out = self.a + self.someStored\n")
        with self.assertRaises(codegen.UnsupportedSpec) as cm:
            codegen.generate_cpp(spec, for_port=True)
        self.assertIn("someStored", str(cm.exception))

    def test_declared_only_does_not_reject(self):
        from mpynode.native import compiler as codegen
        # Reads only the declared input; NOT deterministically lowerable (str())
        # so the guard IS reached -- it must pass and emit the AI PORT region.
        spec = self._node("self.out = float(str(self.a)) + 1.0\n")
        cpp = codegen.generate_cpp(spec, for_port=True)  # must NOT raise
        self.assertIn(codegen.PORT_BEGIN, cpp)

    def test_written_state_does_not_reject(self):
        from mpynode.native import compiler as codegen
        # `velocity` is persistent state: WRITTEN (and read) in-source, so the
        # port models it as a member -- it is NOT an unbound external read.
        spec = self._node(
            "self.velocity = self.velocity * 0.9\n"
            "self.out = self.a + self.velocity\n",
            init="self.velocity = 0.0\n")
        codegen.generate_cpp(spec, for_port=True)  # must NOT raise

    def test_lowerable_clean_node_unaffected(self):
        from mpynode.native import compiler as codegen
        # A fully deterministic compute returns before the guard (no orphans
        # possible) -- byte-for-byte the pre-guard behaviour.
        spec = self._node("self.out = self.a * 2.0 + 1.0\n")
        cpp = codegen.generate_cpp(spec, for_port=True)  # must NOT raise
        self.assertNotIn(codegen.PORT_BEGIN, cpp)  # lowered, no AI region


def setUpModule():
    _setUpModule__hypershade_classification()
    _setUpModule__bundler_locator_probe()
    _setUpModule__codegen_metadata()
    _setUpModule__locator_hover_codegen()
    _setUpModule__euler_support()


if __name__ == "__main__":
    import unittest
    unittest.main()
