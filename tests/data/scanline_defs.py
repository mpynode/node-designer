"""Single source of truth for the scanline-over-time mPyFile demo.

A file-texture node that loads the grid PNG and multiplies it by a horizontal
scanline band that SCROLLS with time (``tIn`` <- time1.outTime). Used to build:
  * a Python mPyFile scene  (mPyFile_scanline_python.ma)
  * a compiled-plugin scene (mPyFile_scanline_compiled.ma)

The Python compute and the deterministic C++ body are defined HERE together so
they stay in lock-step (verified at parity by 03_verify_parity.py). No LLM is
used to compile -- ``make_complete_fn()`` emits the C++ directly (Route 2).
"""
from __future__ import annotations

import os
import re

ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))

# The grid asset lives with the other demo data. The out/scene paths below feed
# the (retired) demo builder only; the gate reads just INIT_SRC / COMPUTE_SRC /
# ARNOLD_OSL_SRC and never these.
_DEMO_DATA = os.path.join(ROOT, "scripts", "mpynode", "_demos", "data")
_DEMO_OUT = os.path.join(ROOT, "scripts", "mpynode", "_demos", "output", "mpy_demos")
GRID_PNG = os.path.join(_DEMO_DATA, "test_grid.png")
NODE_TYPE = "scanlineOverTime"
OUT_DIR = os.path.join(ROOT, "scripts", "mpynode", "_demos", "output",
                       "scanline_overtime_build")
PLUGIN_COPY = os.path.join(ROOT, "plug-ins", NODE_TYPE + ".bundle")

SCENE_PY = os.path.join(_DEMO_OUT, "mPyFile_scanline_python.ma")
SCENE_NATIVE = os.path.join(_DEMO_OUT, "mPyFile_scanline_compiled.ma")

# Scanline look: NUM_BANDS horizontal bands, scrolling SPEED cycles/frame.
NUM_BANDS = 12.0
SPEED = 0.1
TWO_PI = 6.283185307179586

# MImage::readFromFile is bottom-up: verified marr[h-1-y] == PIL_arr[y], same RGBA
# channel order. So the C++ computes Python's TOP-DOWN row (py_pil) exactly, then
# maps it to MImage's bottom-up index as (h-1)-py_pil -- this reproduces the SAME
# texel as Python with no off-by-one (a naive v*(h-1) mismatches at .5 rounding).

# --------------------------------------------------------------------------
# The three tiers every vanilla mPyFile carries:
#
#   Init     -- once per file open. Defines the cached loader, the per-row
#               scanline baker and the GPU upload helper; ``omr`` / ``np`` /
#               ``math`` are imported here and merged into Compute + Viewport.
#   Compute  -- per DG compute() (Hypershade swatch + software render). Reads
#               the presets, samples the grid, writes outColor. This is also
#               the source the C++ port is generated from.
#   Viewport -- per VP2 updateShader(). Bakes the CURRENT frame's scanline and
#               uploads it to the mayaFileTexture fragment. Without this the
#               override binds no texture and the sphere renders black.
#
# Time: the wrapper auto-wires time1.outTime -> _timeIn, so ``self.time`` is
# live, and mPyFile's timeChanged callback dgdirty's outColor every frame ->
# compute() and updateShader() both re-run on scrub. Compute additionally reads
# ``self.tIn`` (a user attr wired to time1) so the C++ port has an explicit
# time input; tIn == self.time for the wired node.
# --------------------------------------------------------------------------

# Look constants, shared by Init/Compute (via the merged namespace) and the
# deterministic C++ emitter, so the Python node and the binary stay in sync.
_LOOK_CONSTS = (
    "NUM_BANDS = %s\n"
    "SPEED = %s\n"
    "TWO_PI = %s\n"
) % (repr(NUM_BANDS), repr(SPEED), repr(TWO_PI))

INIT_SRC = _LOOK_CONSTS + r'''import os
import numpy as np
import math
import maya.api.OpenMayaRender as omr
from PIL import Image

# Per-node cache: load the PNG once (raw RGBA in [0,1], no colour mgmt -- the
# demo wants the grid pattern verbatim, and this keeps the C++ port trivial).
_GRID_CACHE = {}


def _grid(path):
    a = _GRID_CACHE.get(path)
    if a is None:
        im = Image.open(path).convert('RGBA')
        a = np.asarray(im).astype('float32') / 255.0
        _GRID_CACHE[path] = a
    return a


def _scanline_rows(h, t):
    """Per-row scan multiplier (length-h float32). Image row ``py`` (top-down)
    maps to Maya v = 1 - py/(h-1), matching how the Compute tab samples, so the
    viewport bands line up with the swatch."""
    py = np.arange(h, dtype=np.float32)
    v = 1.0 - py / float(h - 1)
    s = 0.5 + 0.5 * np.sin((v * NUM_BANDS - float(t) * SPEED) * TWO_PI)
    return (0.4 + 0.6 * s).astype(np.float32)


def _bake_scanline(arr, t):
    """Return a NEW HxWx4 float32 with the scanline baked into RGB for frame
    ``t`` (alpha passed through)."""
    scan = _scanline_rows(arr.shape[0], t)
    out = arr.copy()
    out[:, :, 0] *= scan[:, None]
    out[:, :, 1] *= scan[:, None]
    out[:, :, 2] *= scan[:, None]
    return out


def _upload_scanline_texture(arr, fileName, t):
    """Upload a baked float32 HxWx4 buffer to the GPU via the VP2 texture
    manager. The frame is encoded into the texture name so each scrubbed frame
    forces a fresh upload -> the scanline animates in the viewport. Returns
    None headless (no renderer) so the Viewport source no-ops gracefully."""
    if arr is None:
        return None
    tmgr = omr.MRenderer.getTextureManager()
    if tmgr is None:
        return None
    h, w, c = arr.shape
    if c != 4:
        return None
    desc = omr.MTextureDescription()
    desc.setToDefault2DTexture()
    desc.fWidth = w
    desc.fHeight = h
    desc.fDepth = 1
    desc.fBytesPerRow = w * 4 * 4   # 4 channels * 4 bytes (float32)
    desc.fBytesPerSlice = desc.fBytesPerRow * h
    desc.fMipmaps = 1
    desc.fArraySlices = 1
    desc.fFormat = omr.MRenderer.kR32G32B32A32_FLOAT
    desc.fTextureType = omr.MTextureDescription.kImage2D
    desc.fEnvMapType = omr.MTextureDescription.kEnvNone
    if not arr.flags['C_CONTIGUOUS']:
        arr = np.ascontiguousarray(arr)
    # Key on the ACTUAL t value (not a rounded frame) so a manual tIn change --
    # not just a timeline scrub -- yields a fresh upload instead of returning the
    # cached texture for the same frame.
    tex_name = 'scanline::%s|t=%.4f' % (fileName, float(t))
    return tmgr.acquireTexture(tex_name, desc, arr.tobytes(), False)
'''

COMPUTE_SRC = (
    "arr = _grid(self.fileName)\n"
    "h = arr.shape[0]\n"
    "w = arr.shape[1]\n"
    "u, v = self.uvCoord\n"
    "px = int(u * (w - 1)) % w\n"
    "py = int((1.0 - v) * (h - 1)) % h\n"
    "rgb = arr[py, px]\n"
    "s = 0.5 + 0.5 * math.sin((v * NUM_BANDS - self.tIn * SPEED) * TWO_PI)\n"
    "scan = 0.4 + 0.6 * s\n"
    "self.outColor = (float(rgb[0]) * scan, float(rgb[1]) * scan, float(rgb[2]) * scan)\n"
    "self.outAlpha = 1.0\n"
)

# Viewport (VP2) source -- gold-standard shape (cf. DEFAULT_VIEWPORT_SOURCE):
# find the fragment's texture + sampler params, upload the baked pixels, bind.
VIEWPORT_SRC = r'''# Runs per VP2 updateShader(): upload the scanline-baked grid so the sphere
# shades the texture in the viewport and animates as the timeline scrubs.

# 1. Locate the mayaFileTexture fragment's texture + sampler parameters.
map_param = None
samp_param = None
for pname in self.shader.parameterList():
    try:
        ptype = self.shader.parameterType(pname)
    except Exception:
        continue
    if map_param is None and ptype == omr.MShaderInstance.kTexture2:
        map_param = pname
    elif samp_param is None and ptype == omr.MShaderInstance.kSampler:
        samp_param = pname
    if map_param and samp_param:
        break

# 2. Bake the scanline for the current frame and upload it. Reads self.tIn
#    (the user input, same as the Compute tab) so the two tiers stay in lock-step
#    and a change to tIn -- via the timeline OR a manual edit -- re-bakes here.
arr = _grid(self.fileName)
if arr is not None and map_param:
    baked = _bake_scanline(arr, float(self.tIn))
    texture = _upload_scanline_texture(baked, self.fileName, float(self.tIn))
    if texture is not None:
        assignment = omr.MTextureAssignment()
        assignment.texture = texture
        self.shader.setParameter(map_param, assignment)
        try:
            self.texture_manager.releaseTexture(texture)
        except Exception:
            pass

# 3. Default sampler state (linear filtering, wrap addressing).
if samp_param:
    desc = omr.MSamplerStateDesc()
    desc.setDefaults()
    desc.filter = omr.MSamplerState.kMinMagMipLinear
    desc.addressU = omr.MSamplerState.kTexWrap
    desc.addressV = omr.MSamplerState.kTexWrap
    self.shader.setParameter(
        samp_param, self.state_manager.acquireSamplerState(desc)
    )
'''


# --------------------------------------------------------------------------
# VP2 interactive-viewport shading override (Phase 2) -- GUI-confirmed.
#
# The batch/swatch path (2dTextureSwatchGen) samples compute() per-UV and
# already renders the grid, but the LIVE viewport needs an OGS fragment or VP2
# shows one flat colour. This is a C++ port of the Python MPyFileOverride:
# reuse Maya's "mayaFileTexture" fragment and, in updateShader, bake the
# current frame's scanline and bind it as the fragment's 2D texture.
#
# Kept HERE as the single source of truth (alongside Compute + OSL) and
# injected into the generated .cpp by inject_vp2_override(). NOT yet a general
# codegen feature.
# --------------------------------------------------------------------------
VP2_OVERRIDE_INCLUDES = (
    "// --- VP2 interactive-viewport shading override (Phase 2) ---\n"
    "#include <maya/MViewport2Renderer.h>\n"
    "#include <maya/MPxShadingNodeOverride.h>\n"
    "#include <maya/MShaderManager.h>\n"
    "#include <maya/MTextureManager.h>\n"
    "#include <maya/MStateManager.h>\n"
    "#include <maya/MDrawRegistry.h>\n"
    "#include <maya/MFnDependencyNode.h>\n"
    "#include <maya/MItDependencyNodes.h>\n"
    "#include <maya/MEventMessage.h>\n"
    "#include <maya/MMessage.h>\n"
    "#include <maya/MGlobal.h>\n"
    "#include <maya/MStringArray.h>\n"
    "#include <maya/MFn.h>\n"
)

_VP2_OVERRIDE_BLOCK_TMPL = r'''// ===========================================================================
// VP2 shading override -- interactive Viewport 2.0 shading.
// (Faithful C++ port of _api2/mpy_file.py MPyFileOverride.)
// ===========================================================================
namespace {

const double ND_NUM_BANDS = __BANDS__;
const double ND_SPEED     = __SPEED__;
const double ND_TWO_PI    = __TWOPI__;

const MString kDrawClassification("drawdb/shader/texture/2d/scanlineOverTime");
const MString kRegistrantId("scanlineOverTimeOverride");

class ScanlineOverTimeOverride : public MHWRender::MPxShadingNodeOverride {
public:
    static MHWRender::MPxShadingNodeOverride* creator(const MObject& obj) {
        return new ScanlineOverTimeOverride(obj);
    }
    ScanlineOverTimeOverride(const MObject& obj)
        : MHWRender::MPxShadingNodeOverride(obj), _node(obj) {}
    ~ScanlineOverTimeOverride() override {}

    MHWRender::DrawAPI supportedDrawAPIs() const override {
        return MHWRender::kAllDevices;
    }
    bool allowConnections() const override { return true; }
    MString fragmentName() const override { return MString("mayaFileTexture"); }
    bool valueChangeRequiresFragmentRebuild(const MPlug*) const override {
        return false;
    }
    void getCustomMappings(
            MHWRender::MAttributeParameterMappingList& mappings) override {
        MHWRender::MAttributeParameterMapping uv(
            "uvCoord", "uvCoord", true, true);
        mappings.append(uv);
    }

    void updateDG() override {
        MStatus st;
        MFnDependencyNode fn(_node, &st);
        if (!st) return;
        MPlug fp = fn.findPlug("fileName", false, &st);
        if (st) _fileName = fp.asString();
        MPlug tp = fn.findPlug("tIn", false, &st);
        if (st) _tIn = tp.asFloat();
    }

    void updateShader(
            MHWRender::MShaderInstance& shader,
            const MHWRender::MAttributeParameterMappingList&) override {
        MStringArray plist;
        shader.parameterList(plist);
        MString mapParam, sampParam;
        for (unsigned int i = 0; i < plist.length(); ++i) {
            MHWRender::MShaderInstance::ParameterType pt =
                shader.parameterType(plist[i]);
            if (mapParam.length() == 0 &&
                pt == MHWRender::MShaderInstance::kTexture2)
                mapParam = plist[i];
            else if (sampParam.length() == 0 &&
                     pt == MHWRender::MShaderInstance::kSampler)
                sampParam = plist[i];
        }

        MHWRender::MRenderer* renderer = MHWRender::MRenderer::theRenderer();
        if (!renderer) return;
        MHWRender::MTextureManager* tmgr = renderer->getTextureManager();
        if (!tmgr) return;

        if (mapParam.length() && _fileName.length()) {
            unsigned int w = 0, h = 0;
            const unsigned char* pix = nullptr;
            bool ok = nd_img_load_raw(_cache, _mtx, _fileName, w, h, pix);
            if (ok && w > 0 && h > 0 && pix) {
                std::vector<float> baked((size_t)w * h * 4);
                for (unsigned int py = 0; py < h; ++py) {
                    double vv = (h > 1)
                        ? 1.0 - (double)py / (double)(h - 1) : 0.0;
                    double s = 0.5 + 0.5 * std::sin(
                        (vv * ND_NUM_BANDS - (double)_tIn * ND_SPEED) * ND_TWO_PI);
                    double scan = 0.4 + 0.6 * s;
                    unsigned int src = h - 1 - py;
                    const unsigned char* srow = pix + (size_t)src * w * 4;
                    float* drow = &baked[(size_t)py * w * 4];
                    for (unsigned int x = 0; x < w; ++x) {
                        drow[x * 4 + 0] =
                            (float)((srow[x * 4 + 0] / 255.0) * scan);
                        drow[x * 4 + 1] =
                            (float)((srow[x * 4 + 1] / 255.0) * scan);
                        drow[x * 4 + 2] =
                            (float)((srow[x * 4 + 2] / 255.0) * scan);
                        drow[x * 4 + 3] = (float)(srow[x * 4 + 3] / 255.0);
                    }
                }
                MHWRender::MTextureDescription desc;
                desc.setToDefault2DTexture();
                desc.fWidth = w;
                desc.fHeight = h;
                desc.fDepth = 1;
                desc.fBytesPerRow = w * 4 * 4;
                desc.fBytesPerSlice = desc.fBytesPerRow * h;
                desc.fMipmaps = 1;
                desc.fArraySlices = 1;
                desc.fFormat = MHWRender::kR32G32B32A32_FLOAT;
                desc.fTextureType = MHWRender::kImage2D;
                desc.fEnvMapType = MHWRender::kEnvNone;
                // Key on the ACTUAL tIn value (not a rounded frame) so a manual
                // tIn change -- not just a timeline scrub -- yields a fresh
                // upload instead of the cached texture. updateDG reads tIn so
                // OGS already dirties the shader on that change.
                MString texName = MString("scanlineCpp::") + _fileName + "|t=";
                texName += (double)_tIn;
                MHWRender::MTexture* tex =
                    tmgr->acquireTexture(texName, desc, baked.data(), false);
                if (tex) {
                    MHWRender::MTextureAssignment assign;
                    assign.texture = tex;
                    shader.setParameter(mapParam, assign);
                    tmgr->releaseTexture(tex);
                }
            }
        }

        if (sampParam.length()) {
            MHWRender::MSamplerStateDesc sdesc;
            sdesc.setDefaults();
            sdesc.filter = MHWRender::MSamplerState::kMinMagMipLinear;
            sdesc.addressU = MHWRender::MSamplerState::kTexWrap;
            sdesc.addressV = MHWRender::MSamplerState::kTexWrap;
            const MHWRender::MSamplerState* ss =
                MHWRender::MStateManager::acquireSamplerState(sdesc);
            if (ss) shader.setParameter(sampParam, *ss);
        }
    }

private:
    MObject       _node;
    MString       _fileName;
    float         _tIn = 0.0f;
    NdImgRawCache _cache;
    std::mutex    _mtx;
};

MCallbackId g_timeChangedCb = 0;

void ndOnTimeChanged(void*) {
    MItDependencyNodes it(MFn::kInvalid);
    for (; !it.isDone(); it.next()) {
        MFnDependencyNode fn(it.thisNode());
        if (fn.typeId() == ScanlineOverTime::id) {
            MString cmd("dgdirty ");
            cmd += fn.name();
            cmd += ".outColor";
            MGlobal::executeCommand(cmd, false, false);
        }
    }
}

}  // namespace

'''

VP2_OVERRIDE_BLOCK = (
    _VP2_OVERRIDE_BLOCK_TMPL
    .replace("__BANDS__", repr(NUM_BANDS))
    .replace("__SPEED__", repr(SPEED))
    .replace("__TWOPI__", repr(TWO_PI)))

VP2_INIT_PLUGIN = (
    "MStatus initializePlugin(MObject obj) {\n"
    "    MFnPlugin plugin(obj, \"mpynode-native\", \"1.0\", \"Any\");\n"
    "    // The drawdb/shader segment binds the VP2 shading override (registered\n"
    "    // below) so the LIVE viewport shades the texture; texture/2d + swatch\n"
    "    // keep the Hypershade classification + swatch generator.\n"
    "    MString _classif(\"texture/2d:swatch/2dTextureSwatchGen:drawdb/shader/texture/2d/scanlineOverTime\");\n"
    "    MStatus st = plugin.registerNode(\"scanlineOverTime\", ScanlineOverTime::id,\n"
    "        ScanlineOverTime::creator, ScanlineOverTime::initialize,\n"
    "        MPxNode::kDependNode, &_classif);\n"
    "    if (!st) return st;\n"
    "    MHWRender::MDrawRegistry::registerShadingNodeOverrideCreator(\n"
    "        kDrawClassification, kRegistrantId, ScanlineOverTimeOverride::creator);\n"
    "    g_timeChangedCb = MEventMessage::addEventCallback(\"timeChanged\",\n"
    "                                                      ndOnTimeChanged);\n"
    "    return MS::kSuccess;\n"
    "}"
)

VP2_UNINIT_PLUGIN = (
    "MStatus uninitializePlugin(MObject obj) {\n"
    "    MFnPlugin plugin(obj);\n"
    "    if (g_timeChangedCb) {\n"
    "        MMessage::removeCallback(g_timeChangedCb);\n"
    "        g_timeChangedCb = 0;\n"
    "    }\n"
    "    MHWRender::MDrawRegistry::deregisterShadingNodeOverrideCreator(\n"
    "        kDrawClassification, kRegistrantId);\n"
    "    return plugin.deregisterNode(ScanlineOverTime::id);\n"
    "}"
)


def inject_vp2_override(cpp: str) -> str:
    """Splice the GUI-confirmed VP2 shading override into a freshly generated
    scanlineOverTime.cpp. Idempotent. Returns the modified source.

    Three edits: (1) extra includes after <mutex>; (2) the override class +
    timeChanged callback before initialize(); (3) replace initializePlugin /
    uninitializePlugin with the override-registering versions.
    """
    if "ScanlineOverTimeOverride" in cpp:
        return cpp  # already injected
    # (1) includes -- the raw-image cache always pulls in <mutex>.
    if "#include <mutex>\n" not in cpp:
        raise RuntimeError("inject_vp2_override: '#include <mutex>' anchor not "
                           "found (raw-image cache missing?)")
    cpp = cpp.replace("#include <mutex>\n",
                      "#include <mutex>\n" + VP2_OVERRIDE_INCLUDES, 1)
    # (2) override block immediately before initialize().
    m = re.search(r"\nMStatus \w+::initialize\(\) \{", cpp)
    if not m:
        raise RuntimeError("inject_vp2_override: initialize() anchor not found")
    cpp = cpp[:m.start()] + "\n\n" + VP2_OVERRIDE_BLOCK + cpp[m.start() + 1:]
    # (3) plugin entry points.
    cpp, n1 = re.subn(r"MStatus initializePlugin\(MObject obj\) \{.*?\n\}",
                      VP2_INIT_PLUGIN.replace("\\", "\\\\"), cpp, count=1,
                      flags=re.S)
    cpp, n2 = re.subn(r"MStatus uninitializePlugin\(MObject obj\) \{.*?\n\}",
                      VP2_UNINIT_PLUGIN.replace("\\", "\\\\"), cpp, count=1,
                      flags=re.S)
    if n1 != 1 or n2 != 1:
        raise RuntimeError("inject_vp2_override: init/uninit replace failed "
                           "(init=%d uninit=%d)" % (n1, n2))
    return cpp


def vp2_override_libs(base_libs):
    """The override pulls in OpenMayaRender; add it once."""
    libs = list(base_libs)
    if "OpenMayaRender" not in libs:
        libs.append("OpenMayaRender")
    return libs


def build_override_bundle(spec, maya=None):
    """Inject the VP2 override into the freshly generated cpp and (re)compile to
    a bundle (adds OpenMayaRender). Returns (ok, log, plugin_path).

    Run AFTER ``cc.compile_plugin`` (which writes the clean assembled cpp to
    OUT_DIR/build/source/<type>.cpp and proves the base codegen compiles).
    Reproducible: a clean rebuild regenerates the cpp without the override, then
    this re-injects. Requires ``mpynode.native`` on sys.path.
    """
    from mpynode.native.toolchain import toolchain
    from mpynode.native.ai import porter
    from mpynode.native import compiler as codegen
    cpp_path = os.path.join(OUT_DIR, "build", "source", NODE_TYPE + ".cpp")
    if not os.path.isfile(cpp_path):
        return False, "generated cpp not found: %s" % cpp_path, None
    with open(cpp_path) as fh:
        cpp = fh.read()
    cpp = inject_vp2_override(cpp)
    with open(cpp_path, "w") as fh:
        fh.write(cpp)

    compiler = toolchain.default_compiler()
    benv = toolchain.build_env(compiler)
    exe = toolchain.resolve_compiler(compiler, benv)
    if exe is None:
        return False, toolchain.compiler_missing_message(compiler), None
    maya = maya or porter._MAYA_DEFAULT
    out_plugin = os.path.join(OUT_DIR, NODE_TYPE + toolchain.plugin_ext())
    cmd = toolchain.compile_to_plugin_cmd(
        exe, cpp_path, out_plugin,
        include_dir=toolchain.maya_include_dir(maya),
        lib_dir=toolchain.maya_lib_dir(maya),
        libs=vp2_override_libs(codegen._libs_for(spec)),
        arch=toolchain.mac_arch())
    rc, log = toolchain.run_streaming(cmd, env=benv)
    ok = (rc == 0 and os.path.isfile(out_plugin))
    return ok, log, (out_plugin if ok else None)


def install_plugin(src, dest):
    """Install a freshly compiled Mach-O bundle to ``dest`` SAFELY on macOS.

    GOTCHA (Apple Silicon): overwriting a code-signed bundle IN PLACE
    (shutil.copy2 / cp -f) truncate-rewrites the SAME inode. The kernel can keep
    a stale cached page->signature binding for that inode, so the next
    ``loadPlugin`` dyld-maps a page whose hash no longer matches the cache and
    the process is SIGKILL'd with "Code Signature Invalid" / "Invalid Page"
    (looks like a hang or a crash). The on-disk signature still verifies fine --
    the staleness is in the kernel, not the file.

    Fix: stage to a sibling temp file (a NEW inode), ad-hoc re-sign it on darwin
    so its signature is self-consistent, then ``os.replace`` (atomic rename) so
    ``dest`` points at the fresh inode. The old inode is unlinked, taking its
    stale cache entry with it. Returns the dest path.
    """
    import shutil
    import subprocess
    import sys
    dest_dir = os.path.dirname(dest)
    if dest_dir and not os.path.isdir(dest_dir):
        os.makedirs(dest_dir)
    tmp = dest + ".incoming"
    if os.path.exists(tmp):
        os.remove(tmp)
    shutil.copy2(src, tmp)
    if sys.platform == "darwin":
        # Ad-hoc sign the staged copy; "-" is the ad-hoc identity. --force
        # replaces any inherited signature so the bytes+signature are consistent.
        subprocess.run(["codesign", "--force", "--sign", "-", tmp],
                       check=False, capture_output=True)
    os.replace(tmp, dest)  # atomic; dest now = the fresh inode
    return dest


# --------------------------------------------------------------------------
# Arnold render path (OSL) -- the renderer integration tier.
#
# WHY: Arnold (MtoA) has no per-sample translator for a custom mPyFile node and
# cannot call its compute per shading sample, so at export it evaluates
# outColor ONCE and bakes it into standard_surface.base_color as a CONSTANT ->
# the whole sphere shades one flat colour (the "shades red" bug).
#
# FIX: an aiOslShader reproducing the EXACT grid+scanline math runs natively in
# Arnold per-UV, wired through the shadingEngine's aiSurfaceShader override
# (Arnold-only) so the viewport still shades via the VP2 override / compiled
# node -- one scene, two render paths, no conflict.
#
# Single source of truth: the same NUM_BANDS / SPEED / TWO_PI and the same
# (1 - v) flip as COMPUTE_SRC and the C++ emitter. texture() filtering plus
# Arnold colour management mean the pixels are not bit-identical to the
# raw-RGBA viewport, but the grid and scanline render correctly per-UV.
# --------------------------------------------------------------------------
ARNOLD_OSL_SRC = (
    "shader scanline_overtime(\n"
    "    string filename = \"\",\n"
    "    float tIn = 0.0,\n"
    "    output color outColor = color(0))\n"
    "{\n"
    "    float NUM_BANDS = %s;\n"
    "    float SPEED = %s;\n"
    "    float TWO_PI = %s;\n"
    "    // grid: same top-down (1 - v) flip the Compute tab samples with.\n"
    "    color grid = texture(filename, u, 1.0 - v);\n"
    "    float s = 0.5 + 0.5 * sin((v * NUM_BANDS - tIn * SPEED) * TWO_PI);\n"
    "    float scan = 0.4 + 0.6 * s;\n"
    "    outColor = grid * scan;\n"
    "}\n"
) % (repr(NUM_BANDS), repr(SPEED), repr(TWO_PI))


# --------------------------------------------------------------------------
# Deterministic C++ body emitter (the "porter" -- no LLM).
# --------------------------------------------------------------------------
def make_complete_fn():
    """Return a complete_fn(system, user) -> C++ body for the PORT region.

    Parses the scaffold's actual member names (float2 uv input, float tIn input,
    color/alpha output handles) then emits the scanline body referencing the
    MImage scaffold's _imgPixels / _imgW / _imgH / _imgOK.
    """
    template = (
        "    double u = __UV__[0], v = __UV__[1];\n"
        "    float r = 1.0f, g = 0.0f, b = 1.0f;  // magenta fallback (no image)\n"
        "    if (_imgOK && _imgW > 0 && _imgH > 0) {\n"
        "        int px = ((int)(u * (double)(_imgW - 1))) % (int)_imgW;\n"
        "        if (px < 0) px += (int)_imgW;\n"
        "        // Python samples top-down row py_pil; MImage is bottom-up -> (h-1)-py_pil.\n"
        "        int py_pil = (((int)((1.0 - v) * (double)(_imgH - 1))) % (int)_imgH);\n"
        "        if (py_pil < 0) py_pil += (int)_imgH;\n"
        "        int py = (int)_imgH - 1 - py_pil;\n"
        "        const unsigned char* p = _imgPixels + ((size_t)py * _imgW + px) * 4;\n"
        "        double s = 0.5 + 0.5 * std::sin((v * __BANDS__ - (double)__TIN__ * __SPEED__) * __TWOPI__);\n"
        "        double scan = 0.4 + 0.6 * s;\n"
        "        r = (float)((p[0] / 255.0) * scan);\n"
        "        g = (float)((p[1] / 255.0) * scan);\n"
        "        b = (float)((p[2] / 255.0) * scan);\n"
        "    }\n"
        "    __HCOL__.set3Float(r, g, b);\n"
        "    __HALP__.setFloat(1.0f);\n"
    )

    def complete_fn(system, user):
        uv = re.search(r"const float2& (in_\w+)", user)
        tin = re.search(r"const float (in_\w+) = data", user)
        hcol = re.search(r"(h_\w+)\.set3Float", user)
        halp = re.search(r"(h_\w+)\.setFloat\(", user)
        if not (uv and tin and hcol and halp):
            raise RuntimeError(
                "scaffold missing expected members: uv=%s tin=%s hcol=%s halp=%s"
                % (bool(uv), bool(tin), bool(hcol), bool(halp)))
        body = template
        body = body.replace("__UV__", uv.group(1))
        body = body.replace("__TIN__", tin.group(1))
        body = body.replace("__HCOL__", hcol.group(1))
        body = body.replace("__HALP__", halp.group(1))
        body = body.replace("__BANDS__", repr(NUM_BANDS))
        body = body.replace("__SPEED__", repr(SPEED))
        body = body.replace("__TWOPI__", repr(TWO_PI))
        return body

    return complete_fn


# --------------------------------------------------------------------------
# Scene wiring (shared by both the Python and compiled scenes).
# --------------------------------------------------------------------------
def _make_shader(cmds, name):
    try:
        s = cmds.shadingNode("standardSurface", asShader=True, name=name)
        return s, s + ".baseColor"
    except Exception:
        s = cmds.shadingNode("lambert", asShader=True, name=name)
        return s, s + ".color"


def _ensure_node_osl(cmds, node, src):
    """Ensure ``node`` carries its OSL look as a connectable ``osl`` string
    output (matching OslSourceMixin: longName/shortName 'osl', dataType string),
    set to ``src``. Works on the Python mPyFile AND the compiled node (a plain
    dynamic string attr is legal on any node) so both demo scenes drive their
    Arnold shader from the SAME node-output feature."""
    if not cmds.attributeQuery("osl", node=node, exists=True):
        cmds.addAttr(node, longName="osl", shortName="osl", dataType="string")
    cmds.setAttr(node + ".osl", src, type="string")


def wire_arnold_osl(cmds, sg, tex_node=None, grid_path=GRID_PNG,
                    time_node="time1", label="scanline"):
    """Install the Arnold render path on shadingEngine ``sg``.

    The grid+scanline OSL (ARNOLD_OSL_SRC) is carried on the texture node itself
    as its connectable ``.osl`` output (the per-language shader-tab feature), and
    an ``aiOslShader`` is created from THAT output: the node's ``osl`` string is
    compiled to ``.code`` (via OSLSceneModel, which materializes the filename/tIn
    param attrs) and ``tex_node.osl`` is wired into ``aiOslShader.codeCache`` so
    the shader tracks the node. The shader is driven from ``filename`` (the grid)
    and ``tIn`` (<- ``time_node``) and routed through ``sg.aiSurfaceShader`` so
    ARNOLD renders per-UV while the regular ``surfaceShader`` (the mPyFile /
    compiled node) still drives the viewport. Best-effort: returns the osl node,
    or ``None`` if MtoA / the OSL machinery is unavailable (the viewport scene is
    still valid without it).
    """
    # MtoA must be loaded both for the node types and for OSLSceneModel (which
    # compiles the code in an Arnold universe to create the param attrs).
    try:
        if not cmds.pluginInfo("mtoa", q=True, loaded=True):
            cmds.loadPlugin("mtoa")
    except Exception:
        return None
    try:
        from mtoa.osl import OSLSceneModel
    except Exception:
        return None
    if not cmds.attributeQuery("aiSurfaceShader", node=sg, exists=True):
        return None

    # Carry the look on the texture node's connectable osl output, then source
    # the shader FROM that output (single source of truth: the node).
    src = ARNOLD_OSL_SRC
    if tex_node is not None:
        _ensure_node_osl(cmds, tex_node, ARNOLD_OSL_SRC)
        src = cmds.getAttr(tex_node + ".osl") or ARNOLD_OSL_SRC

    osl = cmds.createNode("aiOslShader", name=label + "_arnoldOsl")
    # codeCache + code mirror what the AE editor sets before compiling.
    cmds.setAttr(osl + ".codeCache", src, type="string")
    cmds.setAttr(osl + ".code", src, type="string")
    try:
        # Compiles the OSL and adds the param_* attrs (filename/tIn). Inputs are
        # created before the output step (buggy in some MtoA builds), so a raise
        # here still leaves filename/tIn in place.
        OSLSceneModel(src, osl)
    except Exception:
        pass
    if not (cmds.attributeQuery("filename", node=osl, exists=True)
            and cmds.attributeQuery("tIn", node=osl, exists=True)):
        # OSL didn't compile / params absent -> don't leave a dangling node.
        try:
            cmds.delete(osl)
        except Exception:
            pass
        return None

    # The feature wire: node's osl output -> shader's codeCache. Now the shader
    # SOURCE is driven by the node (edit the node's OSL tab, it flows here).
    if tex_node is not None:
        try:
            cmds.connectAttr(tex_node + ".osl", osl + ".codeCache", force=True)
        except Exception:
            pass

    cmds.setAttr(osl + ".filename", grid_path, type="string")
    try:
        cmds.connectAttr(time_node + ".outTime", osl + ".tIn", force=True)
    except Exception:
        pass

    amtl = cmds.shadingNode("aiStandardSurface", asShader=True,
                            name=label + "_arnoldMtl")
    try:
        cmds.setAttr(amtl + ".specular", 0.0)
    except Exception:
        pass
    cmds.connectAttr(osl + ".outColor", amtl + ".baseColor", force=True)
    cmds.connectAttr(amtl + ".outColor", sg + ".aiSurfaceShader", force=True)
    return osl


def verify_arnold_override(cmds, sg, time_node="time1"):
    """Return ``(ok, reason)`` for the Arnold render path on shadingEngine ``sg``.

    ``wire_arnold_osl`` is best-effort (it no-ops if MtoA is missing), so a
    deliverable build MUST check that the override actually formed before saving
    -- otherwise a scene with NO Arnold path saves silently and renders flat.
    Checks: aiSurfaceShader is driven, by an aiStandardSurface fed by an
    aiOslShader, whose codeCache is driven by the texture node's osl output (the
    shader-tab feature) and whose tIn is driven by time (so it animates).
    """
    if not cmds.attributeQuery("aiSurfaceShader", node=sg, exists=True):
        return False, "shadingEngine has no aiSurfaceShader (MtoA not loaded?)"
    mtl = cmds.listConnections(sg + ".aiSurfaceShader", s=True, d=False) or []
    if not mtl:
        return False, "SG.aiSurfaceShader is not connected (override missing)"
    osl_nodes = cmds.listConnections(mtl[0], s=True, d=False, type="aiOslShader") or []
    if not osl_nodes:
        return False, "aiSurfaceShader material is not fed by an aiOslShader"
    osl = osl_nodes[0]
    # The shader's source must be driven by the texture node's .osl output so
    # the look lives on the node, not as a constant pasted on out of band.
    code_src = cmds.listConnections(osl + ".codeCache", s=True, d=False,
                                    plugs=True) or []
    if not any(p.endswith(".osl") for p in code_src):
        return False, ("aiOslShader.codeCache is not driven by a node .osl "
                       "output (shader look is not carried on the node)")
    tin = cmds.listConnections(osl + ".tIn", s=True, d=False) or []
    # time1 -> tIn may pass through a unit-conversion node; trace one hop.
    driven_by_time = any(n == time_node for n in tin) or any(
        time_node in (cmds.listConnections(n, s=True, d=False) or [])
        for n in tin)
    if not driven_by_time:
        return False, "OSL tIn is not driven by %s (scanline won't animate)" % time_node
    return True, "ok"


def wire_scene(cmds, tex_node, label):
    """Wire an existing texture node (Python or compiled) into a shaded sphere
    with a scrolling scanline driven by the timeline. Returns the sphere xform.
    """
    # place2dTexture -> uvCoord (skip if already driven, e.g. asTexture auto-wire)
    incoming = cmds.listConnections(tex_node + ".uvCoord", s=True, d=False) or []
    if not incoming:
        p2d = cmds.shadingNode("place2dTexture", asUtility=True,
                               name=label + "_place2d")
        cmds.connectAttr(p2d + ".outUV", tex_node + ".uvCoord", force=True)

    # timeline -> tIn  (this is what animates the scanline on scrub)
    cmds.connectAttr("time1.outTime", tex_node + ".tIn", force=True)

    # texture.outColor -> material -> sphere
    shader, color_plug = _make_shader(cmds, label + "_mtl")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                   name=shader + "SG")
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    cmds.connectAttr(tex_node + ".outColor", color_plug, force=True)

    sph = cmds.polySphere(name=label + "_sphere", radius=5,
                          subdivisionsX=48, subdivisionsY=48)[0]
    cmds.sets(sph, edit=True, forceElement=sg)

    # Arnold render path (best-effort): without it MtoA bakes outColor to a flat
    # constant -> the sphere "shades red" in a render. The viewport path above
    # (surfaceShader) is untouched.
    try:
        wire_arnold_osl(cmds, sg, tex_node=tex_node, grid_path=GRID_PNG,
                        time_node="time1", label=label)
    except Exception:
        pass

    # A scrubbing range so the scanline visibly animates.
    cmds.playbackOptions(minTime=1, maxTime=48, animationStartTime=1,
                         animationEndTime=48)
    cmds.currentTime(1)
    return sph
