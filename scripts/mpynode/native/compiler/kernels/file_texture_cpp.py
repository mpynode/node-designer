"""Verified C++ for the native mPyFile full-parity port (Route 2).

The exotic file-texture math (transfer functions, gamut matrices, prefilter
kernels + separable blur, 25-colour-space dispatch, bilinear + 4 wrap modes) is
ported 1:1 from ``mpynode/_defaults/file_defaults.py`` and emitted by codegen
DETERMINISTICALLY for a ``reads_image_file`` mPyFile -- so parity is guaranteed
by construction, not by hoping the LLM reproduces S-Log3.

Three blocks:

* ``MATH_CPP``  -- Maya-FREE pure functions (``nd_tex_*``). Standalone-compilable
  so the math can be parity-tested against the Python helpers WITHOUT Maya
  (see test_file_texture_cpp.py).
* ``PNG_CPP``   -- Maya-FREE exact PNG decoder (``nd_png_*``), straight alpha.
  Emitted ahead of ``CACHE_CPP``, which is its only caller today; it is
  self-contained so any other pixel-reading site can adopt it.
* ``CACHE_CPP`` -- the per-instance, mutex-guarded load + linearize + prefilter
  cache (needs Maya). Calls into ``MATH_CPP`` and ``PNG_CPP``.

``float`` throughout, matching numpy ``float32``. ``nearbyintf`` is used for the
``int(round(x))`` calls so C++ matches Python's round-half-to-even.
"""

from __future__ import annotations

import ast
import re

from mpynode._common.osl.osl_convert import extract_simple_consts
from mpynode._common.interface import method_registry
from mpynode._common.interface.api_methods import CppKernel
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.py_to_cpp import scalar_t, Val, CppType


# ---- Maya-free pure math. Mirrors file_defaults.py line-for-line. ----------
MATH_CPP = r"""// ===== mPyFile verified texture math (ported 1:1 from file_defaults.py) =====
// nd_tex_* helpers: float32 throughout to match numpy.

// ---- gamut matrices (source primaries -> Rec.709 / sRGB linear, D65) ----
static const float ND_TEX_M_AdobeRGB[9] = {
    1.39838f, -0.39838f, 0.00000f,
    0.00000f,  1.00000f, 0.00000f,
    0.00000f, -0.04293f, 1.04293f};
static const float ND_TEX_M_P3D65[9] = {
    1.22494f, -0.22494f, 0.00000f,
   -0.04205f,  1.04205f, 0.00000f,
   -0.01964f, -0.07857f, 1.09821f};
static const float ND_TEX_M_Rec2020[9] = {
    1.66049f, -0.58764f, -0.07286f,
   -0.12455f,  1.13284f, -0.00829f,
   -0.01815f, -0.10058f,  1.11873f};
static const float ND_TEX_M_AP0[9] = {
    2.52169f, -1.13413f, -0.38756f,
   -0.27648f,  1.37272f, -0.09624f,
   -0.01538f, -0.15298f,  1.16835f};
static const float ND_TEX_M_AP1[9] = {
    1.70505f, -0.62179f, -0.08326f,
   -0.13026f,  1.14080f, -0.01055f,
   -0.02400f, -0.12897f,  1.15297f};
static const float ND_TEX_M_AlexaWide[9] = {
    1.617523f, -0.537366f, -0.080156f,
   -0.070573f,  1.334613f, -0.264040f,
   -0.021102f, -0.226858f,  1.247961f};
static const float ND_TEX_M_REDWide[9] = {
    1.412341f, -0.241346f, -0.171015f,
   -0.011936f,  1.045283f, -0.033347f,
   -0.022867f, -0.030676f,  1.053542f};
static const float ND_TEX_M_SGamut3[9] = {
    1.628691f, -0.764773f,  0.136082f,
   -0.085391f,  1.236164f, -0.150774f,
    0.028601f, -0.275313f,  1.246712f};

// ---- transfer functions (per channel; numpy vectorizes, we loop) ----
static inline float nd_tex_srgb_eotf(float x) {
    return x <= 0.04045f ? x / 12.92f : powf((x + 0.055f) / 1.055f, 2.4f);
}
static inline float nd_tex_gamma_eotf(float x, float g) {
    return powf(x > 0.0f ? x : 0.0f, g);
}
static inline float nd_tex_acescct_eotf(float x) {
    if (x <= 0.155251141552511f)
        return (x - 0.0729055341958355f) / 10.5402377416545f;
    return powf(2.0f, x * 17.52f - 9.72f);
}
static inline float nd_tex_logc_v3_ei800_eotf(float x) {
    const float cut = 0.149658f;
    if (x > cut)
        return (powf(10.0f, (x - 0.385537f) / 0.247190f) - 0.052272f) / 5.555556f;
    return (x - 0.092809f) / 5.367655f;
}
static inline float nd_tex_red_log3g10_eotf(float x) {
    return (powf(10.0f, x / 0.224282f) - 1.0f) / 155.975327f - 0.01f;
}
static inline float nd_tex_slog3_eotf(float x) {
    const float th = 171.2102946929f / 1023.0f;
    if (x >= th)
        return powf(10.0f, (x * 1023.0f - 420.0f) / 261.5f) * 0.19f - 0.01f;
    return (x * 1023.0f - 95.0f) * 0.01125f / (171.2102946929f - 95.0f);
}
static inline float nd_tex_adx10_eotf(float x) {
    float density = (x * 1023.0f - 95.0f) * (2.0f / 928.0f);
    return 0.18f * powf(10.0f, 1.6056f - density);
}

// ---- 25-colour-space dispatch (mirrors _linearize) ----
enum { ND_TF_IDENT, ND_TF_SRGB, ND_TF_G18, ND_TF_G22, ND_TF_G24,
       ND_TF_G26, ND_TF_ACESCCT, ND_TF_LOGC, ND_TF_RED, ND_TF_SLOG3, ND_TF_ADX10 };

static int nd_tex_tf_for(int cs) {
    switch (cs) {
    case 19: case 8: case 9: case 10: case 11: case 12: case 13: return ND_TF_IDENT;
    case 0: case 4: case 6: case 14: return ND_TF_SRGB;
    case 1: return ND_TF_G18;
    case 2: case 5: case 7: case 15: case 17: return ND_TF_G22;
    case 3: case 16: return ND_TF_G24;
    case 18: return ND_TF_G26;
    case 20: return ND_TF_ACESCCT;
    case 21: return ND_TF_LOGC;
    case 22: return ND_TF_RED;
    case 23: return ND_TF_SLOG3;
    case 24: return ND_TF_ADX10;
    default: return ND_TF_IDENT;
    }
}
static const float* nd_tex_mat_for(int cs) {
    switch (cs) {
    case 7: case 12: case 17: return ND_TEX_M_AdobeRGB;
    case 6: case 11: case 18: return ND_TEX_M_P3D65;
    case 13: return ND_TEX_M_Rec2020;
    case 10: case 24: return ND_TEX_M_AP0;
    case 9: case 4: case 5: case 20: return ND_TEX_M_AP1;
    case 21: return ND_TEX_M_AlexaWide;
    case 22: return ND_TEX_M_REDWide;
    case 23: return ND_TEX_M_SGamut3;
    default: return nullptr;
    }
}
static inline float nd_tex_apply_tf(int tf, float x) {
    switch (tf) {
    case ND_TF_SRGB:    return nd_tex_srgb_eotf(x);
    case ND_TF_G18:     return nd_tex_gamma_eotf(x, 1.8f);
    case ND_TF_G22:     return nd_tex_gamma_eotf(x, 2.2f);
    case ND_TF_G24:     return nd_tex_gamma_eotf(x, 2.4f);
    case ND_TF_G26:     return nd_tex_gamma_eotf(x, 2.6f);
    case ND_TF_ACESCCT: return nd_tex_acescct_eotf(x);
    case ND_TF_LOGC:    return nd_tex_logc_v3_ei800_eotf(x);
    case ND_TF_RED:     return nd_tex_red_log3g10_eotf(x);
    case ND_TF_SLOG3:   return nd_tex_slog3_eotf(x);
    case ND_TF_ADX10:   return nd_tex_adx10_eotf(x);
    default:            return x;  // identity
    }
}

// ---- linearize a top-down uint8 RGBA image (W*H*4) into float W*H*4 ----
// `unpremult` undoes an ASSOCIATED-alpha decode. A PNG stores colour and alpha
// separately, and that is what the compositing math downstream assumes -- but
// MImage hands back colour already multiplied by alpha, so feeding it straight
// through applies alpha a second time and every soft edge comes out too dark.
// It has to be undone HERE, before the transfer function, because the EOTF is
// non-linear: eotf(c*a) != eotf(c)*a. Callers that decoded straight alpha (the
// exact PNG path, and the drift harness, which feeds synthetic buffers) leave
// it false, so this function stays the exact twin of file_texture_ops.linearize.
static void nd_tex_linearize(const unsigned char* rgba, unsigned W, unsigned H,
                             int cs, std::vector<float>& out,
                             bool unpremult = false) {
    out.resize((size_t)W * H * 4);
    int tf = nd_tex_tf_for(cs);
    const float* M = nd_tex_mat_for(cs);
    const float inv255 = 1.0f / 255.0f;
    for (size_t i = 0, n = (size_t)W * H; i < n; ++i) {
        float r = rgba[i * 4 + 0] * inv255;
        float g = rgba[i * 4 + 1] * inv255;
        float b = rgba[i * 4 + 2] * inv255;
        float a = rgba[i * 4 + 3] * inv255;  // alpha: passthrough (not linearized)
        // a == 0 carries no recoverable colour and contributes nothing; a == 1
        // is already straight. Only the partial-alpha edge texels need dividing.
        if (unpremult && a > 0.0f && a < 1.0f) {
            const float ia = 1.0f / a;
            r *= ia; if (r > 1.0f) r = 1.0f;
            g *= ia; if (g > 1.0f) g = 1.0f;
            b *= ia; if (b > 1.0f) b = 1.0f;
        }
        float lr = nd_tex_apply_tf(tf, r);
        float lg = nd_tex_apply_tf(tf, g);
        float lb = nd_tex_apply_tf(tf, b);
        if (M) {
            float mr = M[0] * lr + M[1] * lg + M[2] * lb;
            float mg = M[3] * lr + M[4] * lg + M[5] * lb;
            float mb = M[6] * lr + M[7] * lg + M[8] * lb;
            lr = mr; lg = mg; lb = mb;
        }
        out[i * 4 + 0] = lr;
        out[i * 4 + 1] = lg;
        out[i * 4 + 2] = lb;
        out[i * 4 + 3] = a;
    }
}

// ---- prefilter kernels (int(round()) -> nearbyintf = round-half-to-even) ----
static inline int nd_tex_iround(float x) { return (int)nearbyintf(x); }

static std::vector<float> nd_tex_gaussian_kernel(float radius) {
    float sigma = radius / 2.0f; if (sigma < 0.5f) sigma = 0.5f;
    int half = (int)ceilf(3.0f * sigma);
    std::vector<float> k; float sum = 0.0f;
    for (int x = -half; x <= half; ++x) {
        float v = expf(-(float)(x * x) / (2.0f * sigma * sigma));
        k.push_back(v); sum += v;
    }
    for (float& v : k) v /= sum;
    return k;
}
static std::vector<float> nd_tex_box_kernel(float radius) {
    int half = nd_tex_iround(radius); if (half < 1) half = 1;
    int n = 2 * half + 1;
    return std::vector<float>(n, 1.0f / (float)n);
}
static std::vector<float> nd_tex_quadratic_kernel(float radius) {
    int half = nd_tex_iround(radius); if (half < 1) half = 1;
    std::vector<float> k; float sum = 0.0f;
    for (int x = -half; x <= half; ++x) {
        float v = 1.0f - fabsf((float)x) / (float)(half + 1);
        if (v < 0.0f) v = 0.0f;
        k.push_back(v); sum += v;
    }
    for (float& v : k) v /= sum;
    return k;
}
static std::vector<float> nd_tex_convolve_full(const std::vector<float>& a,
                                               const std::vector<float>& b) {
    std::vector<float> out(a.size() + b.size() - 1, 0.0f);
    for (size_t i = 0; i < a.size(); ++i)
        for (size_t j = 0; j < b.size(); ++j)
            out[i + j] += a[i] * b[j];
    return out;
}
static std::vector<float> nd_tex_quartic_kernel(float radius) {
    std::vector<float> base = {0.25f, 0.5f, 0.25f};
    int n_iter = nd_tex_iround(radius) * 2; if (n_iter < 1) n_iter = 1;
    std::vector<float> k = base;
    for (int i = 0; i < n_iter - 1; ++i) k = nd_tex_convolve_full(k, base);
    float sum = 0.0f; for (float v : k) sum += v;
    for (float& v : k) v /= sum;
    return k;
}
static bool nd_tex_kernel_for(int kernel, float radius, std::vector<float>& k) {
    if (kernel == 3)      k = nd_tex_gaussian_kernel(radius);
    else if (kernel == 0) k = nd_tex_box_kernel(radius);
    else if (kernel == 1) k = nd_tex_quadratic_kernel(radius);
    else if (kernel == 2) k = nd_tex_quartic_kernel(radius);
    else return false;
    return true;
}

// ---- separable blur (scipy convolve1d, mode='reflect' = half-sample symmetric) ----
static inline int nd_tex_reflect_idx(int i, int n) {
    if (n == 1) return 0;
    while (i < 0 || i >= n) {
        if (i < 0)  i = -i - 1;
        if (i >= n) i = 2 * n - i - 1;
    }
    return i;
}
static void nd_tex_blur_separable(std::vector<float>& img, unsigned W, unsigned H,
                                  const std::vector<float>& k) {
    int kl = (int)k.size();
    int half = (kl - 1) / 2;
    std::vector<float> tmp(img.size());
    // axis 0 (y / rows)
    for (unsigned x = 0; x < W; ++x)
        for (int c = 0; c < 4; ++c)
            for (unsigned y = 0; y < H; ++y) {
                float acc = 0.0f;
                for (int t = 0; t < kl; ++t) {
                    int yy = nd_tex_reflect_idx((int)y + t - half, (int)H);
                    acc += img[((size_t)yy * W + x) * 4 + c] * k[t];
                }
                tmp[((size_t)y * W + x) * 4 + c] = acc;
            }
    // axis 1 (x / cols)
    for (unsigned y = 0; y < H; ++y)
        for (int c = 0; c < 4; ++c)
            for (unsigned x = 0; x < W; ++x) {
                float acc = 0.0f;
                for (int t = 0; t < kl; ++t) {
                    int xx = nd_tex_reflect_idx((int)x + t - half, (int)W);
                    acc += tmp[((size_t)y * W + xx) * 4 + c] * k[t];
                }
                img[((size_t)y * W + x) * 4 + c] = acc;
            }
}
static void nd_tex_prefilter(std::vector<float>& lin, unsigned W, unsigned H,
                             bool enabled, int kernel, float radius) {
    if (!enabled || radius <= 0.0f || lin.empty()) return;
    std::vector<float> k;
    if (!nd_tex_kernel_for(kernel, radius, k)) return;
    nd_tex_blur_separable(lin, W, H, k);
}

// ---- UV wrap policy + bilinear sampler ----
static float nd_tex_apply_wrap(float coord, int mode, bool& oob) {
    oob = false;
    if (mode == 1) {  // clamp
        if (coord < 0.0f) return 0.0f;
        if (coord > 1.0f) return 1.0f - 1e-6f;
        return coord;
    }
    if (mode == 2) {  // mirror
        int n = (int)floorf(coord);
        float frac = coord - (float)n;
        if (n % 2 != 0) frac = 1.0f - frac;
        if (frac >= 1.0f) frac = 1.0f - 1e-6f;
        if (frac < 0.0f) frac = 0.0f;
        return frac;
    }
    if (mode == 3) {  // border
        if (coord < 0.0f || coord > 1.0f) { oob = true; return 0.0f; }
        return coord;
    }
    float m = fmodf(coord, 1.0f);  // wrap (0)
    if (m < 0.0f) m += 1.0f;
    return m;
}
// `miss` is the no-image substitute -- the twin of sample()'s ``missing``
// argument in _common/methods/file_texture_ops.py. Callers bake the magenta
// sentinel {1,0,1,1} in unless the compute passed an explicit missing=.
static void nd_tex_sample(const float* lin, unsigned W, unsigned H,
                          float u, float v, int wrapU, int wrapV,
                          const float border[3], const float miss[4],
                          float out[4]) {
    if (!lin) { out[0] = miss[0]; out[1] = miss[1]; out[2] = miss[2]; out[3] = miss[3]; return; }
    bool uoob = false, voob = false;
    float uu = nd_tex_apply_wrap(u, wrapU, uoob);
    float vvraw = nd_tex_apply_wrap(v, wrapV, voob);
    if (uoob || voob) {
        out[0] = border[0]; out[1] = border[1]; out[2] = border[2]; out[3] = 1.0f;
        return;
    }
    float vv = 1.0f - vvraw;  // Maya V is bottom-up; image V is top-down
    float fx = uu * (float)(W - 1);
    float fy = vv * (float)(H - 1);
    int x0 = (int)fx, y0 = (int)fy;
    float tx = fx - (float)x0, ty = fy - (float)y0;
    const float* p00 = lin + ((size_t)y0 * W + x0) * 4;
    // EXACT-TEXEL FAST PATH. On the VP2 bake's CORNER grid the coordinate lands
    // on a source texel, so the bilinear weights collapse and three quarters of
    // the blend is multiplication by zero. Measured over a real 1024x1024
    // corner-grid bake: tx == 0 for 100% of texels (256/512/1024/2048 all
    // agree) and ty == 0 for ~58% of rows -- ty is the one that misses, because
    // v makes the extra `1.0 - py/(H-1)` and `1.0f - vvraw` trip and those two
    // subtractions are not exact. Skipping the zero-weight taps also skips
    // loading p01/p11, which sit a full row (4 KB) away: a second cache line
    // per texel. Same benchmark, one thread: 4.507 ms -> 2.228 ms, 2.02x, with
    // ZERO bit-differing floats out of 4,194,304.
    //
    // This is arithmetic identity, not an approximation, so the interpreted
    // tier needs no mirror change -- `file_texture_ops.sample` keeps doing the
    // full blend and both tiers still produce the same bytes. The two inputs
    // that would NOT be identity are pixel values this codebase cannot decode:
    // a -0.0f channel (`-0.0 + 0.0` is `+0.0`, so the `+ 0.0f` below reproduces
    // the shipped result rather than dropping it) and an inf/NaN NEIGHBOUR
    // (`0 * inf` is NaN, which the full blend would propagate and this does
    // not). Every decode path here is 8-bit-per-channel -> [0, 1], and the
    // missing-texture sentinel is {1, 0, 1, 1}.
    if (tx == 0.0f) {
        if (ty == 0.0f) {
            out[0] = p00[0] + 0.0f; out[1] = p00[1] + 0.0f;
            out[2] = p00[2] + 0.0f; out[3] = p00[3] + 0.0f;
            return;
        }
        const int y1e = (y0 + 1 < (int)H) ? y0 + 1 : (int)H - 1;
        const float* p01e = lin + ((size_t)y1e * W + x0) * 4;
        for (int c = 0; c < 4; ++c)
            out[c] = (p00[c] + 0.0f) * (1.0f - ty) + (p01e[c] + 0.0f) * ty;
        return;
    }
    int x1 = (x0 + 1 < (int)W) ? x0 + 1 : (int)W - 1;
    int y1 = (y0 + 1 < (int)H) ? y0 + 1 : (int)H - 1;
    const float* p10 = lin + ((size_t)y0 * W + x1) * 4;
    const float* p01 = lin + ((size_t)y1 * W + x0) * 4;
    const float* p11 = lin + ((size_t)y1 * W + x1) * 4;
    for (int c = 0; c < 4; ++c) {
        float top = p00[c] * (1.0f - tx) + p10[c] * tx;
        float bot = p01[c] * (1.0f - tx) + p11[c] * tx;
        out[c] = top * (1.0f - ty) + bot * ty;
    }
}
// ===== end mPyFile verified texture math =====
"""


# ---- Maya-free EXACT PNG decode, straight (unassociated) alpha. -----------
# MImage decodes with ASSOCIATED alpha and quantises the product to 8 bits, so
# only round(colour * alpha) survives and the straight colour the compositing
# math wants cannot be recovered. Undoing the association afterwards (the
# `unpremult` flag on nd_tex_linearize) is close but permanently lossy on every
# partial-alpha texel -- i.e. on every antialiased edge. Decoding the PNG
# directly avoids the round trip entirely, and the interpreted tier's decoder
# (PIL / QImage / mpynode's own png_decode) produces the same bytes by spec.
#
# Written out rather than vendored because the result has to compile inside ONE
# generated translation unit on macOS / Linux / Windows with no link-time
# dependency: Maya ships libz but exposes no zlib headers, and the plugin links
# nothing beyond the Maya libraries.
#
# Scope is deliberately narrow -- see nd_png_supported. Anything it declines
# falls back to MImage, and the INTERPRETED tier applies the identical test to
# the identical header bytes, so the two tiers always pick the same decoder for
# a given file and can never disagree about which one ran.
PNG_CPP = r"""// ===== exact PNG decode (straight / unassociated alpha) =====
namespace nd_png_detail {

struct BitReader {
    const unsigned char* d;
    size_t               n;
    size_t               pos;
    unsigned int         buf;
    int                  cnt;
    bool                 bad;

    BitReader(const unsigned char* data, size_t len)
        : d(data), n(len), pos(0), buf(0u), cnt(0), bad(false) {}

    int bits(int need) {
        while (cnt < need) {
            if (pos >= n) { bad = true; return 0; }
            buf |= (unsigned int)d[pos++] << cnt;
            cnt += 8;
        }
        const int v = (int)(buf & ((1u << need) - 1u));
        buf >>= need;
        cnt -= need;
        return v;
    }
    void align() { buf = 0u; cnt = 0; }
};

// Canonical Huffman: the count of codes at each length plus the symbols in
// canonical order is enough to decode shortest-length-first, with no table
// build beyond the counts.
struct Huff {
    int              count[16];
    std::vector<int> symbol;
};

static bool nd_huff_build(Huff& h, const unsigned char* lengths, int n) {
    for (int i = 0; i < 16; ++i) h.count[i] = 0;
    for (int i = 0; i < n; ++i) h.count[lengths[i]]++;
    if (h.count[0] == n) return false;                 // no codes at all
    int left = 1;
    for (int len = 1; len < 16; ++len) {               // over-subscribed?
        left <<= 1;
        left -= h.count[len];
        if (left < 0) return false;
    }
    int offs[16];
    offs[0] = 0; offs[1] = 0;
    for (int len = 1; len < 15; ++len) offs[len + 1] = offs[len] + h.count[len];
    h.symbol.assign((size_t)n, 0);
    for (int i = 0; i < n; ++i)
        if (lengths[i]) h.symbol[(size_t)offs[lengths[i]]++] = i;
    return true;
}

static int nd_huff_decode(BitReader& br, const Huff& h) {
    int code = 0, first = 0, index = 0;
    for (int len = 1; len < 16; ++len) {
        code |= br.bits(1);
        if (br.bad) return -1;
        const int count = h.count[len];
        if (code - count < first) return h.symbol[(size_t)(index + (code - first))];
        index += count;
        first += count;
        first <<= 1;
        code <<= 1;
    }
    return -1;
}

static const int kLenBase[29] = {
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59,
    67, 83, 99, 115, 131, 163, 195, 227, 258 };
static const int kLenExtra[29] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
    4, 4, 4, 4, 5, 5, 5, 5, 0 };
static const int kDistBase[30] = {
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513,
    769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577 };
static const int kDistExtra[30] = {
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8,
    9, 9, 10, 10, 11, 11, 12, 12, 13, 13 };

static bool nd_inflate_block(BitReader& br, const Huff& lit, const Huff& dist,
                             std::vector<unsigned char>& out) {
    for (;;) {
        const int sym = nd_huff_decode(br, lit);
        if (sym < 0) return false;
        if (sym < 256) {
            out.push_back((unsigned char)sym);
        } else if (sym == 256) {
            return true;                               // end of block
        } else {
            const int s = sym - 257;
            if (s >= 29) return false;
            const int len = kLenBase[s] + br.bits(kLenExtra[s]);
            const int ds = nd_huff_decode(br, dist);
            if (ds < 0 || ds >= 30) return false;
            const size_t d = (size_t)(kDistBase[ds] + br.bits(kDistExtra[ds]));
            if (br.bad || d > out.size()) return false;
            const size_t from = out.size() - d;
            // Copied one byte at a time ON PURPOSE: an overlapping back-
            // reference (d < len) is legal and is how DEFLATE encodes runs.
            for (int i = 0; i < len; ++i) out.push_back(out[from + (size_t)i]);
        }
        if (br.bad) return false;
    }
}

static bool nd_inflate_fixed(BitReader& br, std::vector<unsigned char>& out) {
    unsigned char ll[288], dl[30];
    for (int i = 0; i < 144; ++i) ll[i] = 8;
    for (int i = 144; i < 256; ++i) ll[i] = 9;
    for (int i = 256; i < 280; ++i) ll[i] = 7;
    for (int i = 280; i < 288; ++i) ll[i] = 8;
    for (int i = 0; i < 30; ++i) dl[i] = 5;
    Huff lit, dist;
    if (!nd_huff_build(lit, ll, 288) || !nd_huff_build(dist, dl, 30)) return false;
    return nd_inflate_block(br, lit, dist, out);
}

static bool nd_inflate_dynamic(BitReader& br, std::vector<unsigned char>& out) {
    static const int kOrder[19] = {
        16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15 };
    const int nlen = br.bits(5) + 257;
    const int ndist = br.bits(5) + 1;
    const int ncode = br.bits(4) + 4;
    if (br.bad || nlen > 286 || ndist > 30) return false;
    unsigned char clen[19];
    std::memset(clen, 0, sizeof(clen));
    for (int i = 0; i < ncode; ++i) clen[kOrder[i]] = (unsigned char)br.bits(3);
    if (br.bad) return false;
    Huff cl;
    if (!nd_huff_build(cl, clen, 19)) return false;

    unsigned char lengths[286 + 30];
    std::memset(lengths, 0, sizeof(lengths));
    int i = 0;
    while (i < nlen + ndist) {
        const int sym = nd_huff_decode(br, cl);
        if (sym < 0) return false;
        if (sym < 16) {
            lengths[i++] = (unsigned char)sym;
        } else {
            int rep = 0;
            unsigned char val = 0;
            if (sym == 16) {
                if (i == 0) return false;
                val = lengths[i - 1];
                rep = 3 + br.bits(2);
            } else if (sym == 17) {
                rep = 3 + br.bits(3);
            } else {
                rep = 11 + br.bits(7);
            }
            if (br.bad || i + rep > nlen + ndist) return false;
            while (rep--) lengths[i++] = val;
        }
    }
    if (lengths[256] == 0) return false;                // no end-of-block code
    Huff lit, dist;
    if (!nd_huff_build(lit, lengths, nlen)) return false;
    // A stream with a single distance code is legal, and nd_huff_build reports
    // that as incomplete. Only a genuinely EMPTY distance table is fatal, and
    // that is unreachable unless the stream also never emits a length symbol --
    // which nd_inflate_block catches via the ds < 0 test.
    nd_huff_build(dist, lengths + nlen, ndist);
    return nd_inflate_block(br, lit, dist, out);
}

// zlib wrapper (RFC 1950) around the raw DEFLATE stream (RFC 1951).
static bool nd_zlib_inflate(const unsigned char* d, size_t n,
                            std::vector<unsigned char>& out) {
    if (n < 2) return false;
    const unsigned cmf = d[0], flg = d[1];
    if ((cmf & 0x0f) != 8) return false;                // not deflate
    if (((cmf << 8) | flg) % 31u != 0u) return false;   // header check bits
    if (flg & 0x20) return false;                       // preset dictionary
    BitReader br(d + 2, n - 2);
    for (;;) {
        const int final_block = br.bits(1);
        const int type = br.bits(2);
        if (br.bad) return false;
        if (type == 0) {                                // stored
            br.align();
            if (br.pos + 4 > br.n) return false;
            const unsigned len = (unsigned)br.d[br.pos] |
                                 ((unsigned)br.d[br.pos + 1] << 8);
            br.pos += 4;
            if (br.pos + len > br.n) return false;
            out.insert(out.end(), br.d + br.pos, br.d + br.pos + len);
            br.pos += len;
        } else if (type == 1) {
            if (!nd_inflate_fixed(br, out)) return false;
        } else if (type == 2) {
            if (!nd_inflate_dynamic(br, out)) return false;
        } else {
            return false;
        }
        if (final_block) return true;
    }
}

static inline int nd_png_paeth(int a, int b, int c) {
    const int p = a + b - c;
    const int pa = p > a ? p - a : a - p;
    const int pb = p > b ? p - b : b - p;
    const int pc = p > c ? p - c : c - p;
    if (pa <= pb && pa <= pc) return a;
    if (pb <= pc) return b;
    return c;
}

static inline unsigned int nd_png_be32(const unsigned char* p) {
    return ((unsigned int)p[0] << 24) | ((unsigned int)p[1] << 16) |
           ((unsigned int)p[2] << 8) | (unsigned int)p[3];
}

// Pull sample `si` out of an unfiltered scanline as an 8-bit value, narrowing
// exactly the way the interpreted tier narrows:
//   depth 16 -> the HIGH byte (truncate; measured -- it is NOT round(v/257))
//   depth  8 -> the byte itself
//   depth <8 -> the packed field, MSB-first, UNSCALED (greyscale callers scale
//               it; palette indices have to stay raw)
static inline unsigned nd_png_sample(const unsigned char* row, size_t si,
                                     unsigned depth) {
    if (depth == 8u) return row[si];
    if (depth == 16u) return row[si * 2u];
    const unsigned per = 8u / depth;
    const unsigned shift = (per - 1u - (unsigned)(si % per)) * depth;
    return (unsigned)((row[si / per] >> shift) & ((1u << depth) - 1u));
}

}  // namespace nd_png_detail

// Does this decoder handle *this* file? Reads only the IHDR (plus a tRNS scan,
// which is supported on palette images alone). The interpreted tier runs the
// identical test on the identical bytes -- that agreement is what keeps the two
// tiers from silently picking different decoders for the same texture.
static bool nd_png_supported(const unsigned char* d, size_t n) {
    static const unsigned char kSig[8] = { 137, 80, 78, 71, 13, 10, 26, 10 };
    if (n < 33 || std::memcmp(d, kSig, 8) != 0) return false;
    if (std::memcmp(d + 12, "IHDR", 4) != 0) return false;
    const unsigned bitDepth = d[24];
    const unsigned colour = d[25];
    const unsigned comp = d[26];
    const unsigned filt = d[27];
    const unsigned interlace = d[28];
    // Adam7 is declined outright: it re-orders the image into seven sub-passes,
    // and the interpreted tier's encoder will not emit it, so there is no way
    // to build a reference corpus proving the two agree.
    if (comp != 0 || filt != 0 || interlace != 0) return false;
    switch (colour) {
    case 0:
        // 16-bit greyscale is DECLINED even though the spec allows it: the
        // reference decoder opens it as a 32-bit integer image and CLIPS to
        // 0..255 instead of scaling, so there is no narrowing rule to match.
        if (bitDepth != 1 && bitDepth != 2 && bitDepth != 4 && bitDepth != 8)
            return false;
        break;
    case 3:
        if (bitDepth != 1 && bitDepth != 2 && bitDepth != 4 && bitDepth != 8)
            return false;
        break;
    case 2:
    case 4:
    case 6:
        if (bitDepth != 8 && bitDepth != 16) return false;
        break;
    default:
        return false;
    }
    if (colour == 0 || colour == 2) {
        // tRNS on greyscale / truecolour marks ONE colour transparent. Rare,
        // and the reference behaviour for it is not pinned, so decline rather
        // than guess -- both tiers then fall back together.
        size_t off = 8;
        while (off + 8 <= n) {
            const unsigned int ln = nd_png_detail::nd_png_be32(d + off);
            if (std::memcmp(d + off + 4, "tRNS", 4) == 0) return false;
            if (std::memcmp(d + off + 4, "IDAT", 4) == 0) break;
            off += 12 + (size_t)ln;
        }
    }
    return true;
}

// Decode to top-down uint8 RGBA with STRAIGHT alpha. Returns false for anything
// nd_png_supported declines and for any malformed stream, so the caller falls
// back to MImage.
static bool nd_png_decode(const unsigned char* d, size_t n,
                          unsigned int& outW, unsigned int& outH,
                          std::vector<unsigned char>& rgba) {
    using namespace nd_png_detail;
    if (!nd_png_supported(d, n)) return false;
    const unsigned int W = nd_png_be32(d + 16), H = nd_png_be32(d + 20);
    const unsigned depth = d[24];
    const unsigned colour = d[25];
    if (W == 0u || H == 0u || W > 65535u || H > 65535u) return false;

    static const int kChan[7] = { 1, 0, 3, 1, 2, 0, 4 };
    const int chan = kChan[colour];
    // Scanlines are bit-packed, so the byte stride rounds UP; the filter offset
    // is "bytes per complete pixel, at least 1" per the spec, which stops being
    // the channel count as soon as the depth stops being 8.
    const size_t stride = ((size_t)W * (size_t)chan * (size_t)depth + 7u) / 8u;
    const size_t fbpp = (size_t)((chan * (int)depth + 7) / 8);

    std::vector<unsigned char> idat, plte, trns;
    size_t off = 8;
    while (off + 8 <= n) {
        const unsigned int ln = nd_png_be32(d + off);
        const char* typ = (const char*)(d + off + 4);
        if (off + 12 + (size_t)ln > n) return false;
        const unsigned char* body = d + off + 8;
        if (std::memcmp(typ, "IDAT", 4) == 0)
            idat.insert(idat.end(), body, body + ln);   // IDAT may be split
        else if (std::memcmp(typ, "PLTE", 4) == 0)
            plte.assign(body, body + ln);
        else if (std::memcmp(typ, "tRNS", 4) == 0)
            trns.assign(body, body + ln);
        else if (std::memcmp(typ, "IEND", 4) == 0)
            break;
        off += 12 + (size_t)ln;
    }
    if (idat.empty()) return false;
    if (colour == 3 && plte.size() < 3) return false;

    std::vector<unsigned char> raw;
    raw.reserve((stride + 1) * (size_t)H);
    if (!nd_zlib_inflate(idat.data(), idat.size(), raw)) return false;
    if (raw.size() < (stride + 1) * (size_t)H) return false;

    std::vector<unsigned char> img((size_t)H * stride, 0);
    for (unsigned int y = 0; y < H; ++y) {
        const unsigned char  ft = raw[(size_t)y * (stride + 1)];
        const unsigned char* src = &raw[(size_t)y * (stride + 1) + 1];
        unsigned char*       cur = &img[(size_t)y * stride];
        const unsigned char* prev = y ? &img[(size_t)(y - 1) * stride] : 0;
        for (size_t i = 0; i < stride; ++i) {
            const int a = (i >= fbpp) ? cur[i - fbpp] : 0;
            const int b = prev ? prev[i] : 0;
            const int c = (prev && i >= fbpp) ? prev[i - fbpp] : 0;
            int v = src[i];
            switch (ft) {
            case 0: break;
            case 1: v += a; break;
            case 2: v += b; break;
            case 3: v += (a + b) >> 1; break;
            case 4: v += nd_png_paeth(a, b, c); break;
            default: return false;
            }
            cur[i] = (unsigned char)(v & 0xff);
        }
    }

    // Sub-byte GREYSCALE stretches to the full 0..255 range by an exact integer
    // factor (255/1, 255/3, 255/15); palette indices are never scaled.
    const unsigned gscale = (depth < 8u) ? (255u / ((1u << depth) - 1u)) : 1u;

    rgba.assign((size_t)W * (size_t)H * 4u, 255);
    for (unsigned int y = 0; y < H; ++y) {
        const unsigned char* row = &img[(size_t)y * stride];
        unsigned char* orow = &rgba[(size_t)y * (size_t)W * 4u];
        for (unsigned int x = 0; x < W; ++x) {
            unsigned char* o = &orow[(size_t)x * 4u];
            const size_t s0 = (size_t)x * (size_t)chan;
            if (colour == 0) {
                o[0] = o[1] = o[2] =
                    (unsigned char)(nd_png_sample(row, s0, depth) * gscale);
            } else if (colour == 2) {
                o[0] = (unsigned char)nd_png_sample(row, s0 + 0, depth);
                o[1] = (unsigned char)nd_png_sample(row, s0 + 1, depth);
                o[2] = (unsigned char)nd_png_sample(row, s0 + 2, depth);
            } else if (colour == 3) {
                const size_t idx = (size_t)nd_png_sample(row, s0, depth);
                if (idx * 3u + 2u >= plte.size()) return false;
                o[0] = plte[idx * 3 + 0];
                o[1] = plte[idx * 3 + 1];
                o[2] = plte[idx * 3 + 2];
                o[3] = (idx < trns.size()) ? trns[idx] : 255;
            } else if (colour == 4) {
                o[0] = o[1] = o[2] =
                    (unsigned char)nd_png_sample(row, s0 + 0, depth);
                o[3] = (unsigned char)nd_png_sample(row, s0 + 1, depth);
            } else {
                o[0] = (unsigned char)nd_png_sample(row, s0 + 0, depth);
                o[1] = (unsigned char)nd_png_sample(row, s0 + 1, depth);
                o[2] = (unsigned char)nd_png_sample(row, s0 + 2, depth);
                o[3] = (unsigned char)nd_png_sample(row, s0 + 3, depth);
            }
        }
    }
    outW = W;
    outH = H;
    return true;
}

// Read the file, then decode. Split out so the decoder itself stays testable on
// an in-memory buffer.
static bool nd_png_decode_file(const char* path, unsigned int& outW,
                               unsigned int& outH,
                               std::vector<unsigned char>& rgba) {
    if (!path || !path[0]) return false;
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    const long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz <= 0) { fclose(f); return false; }
    std::vector<unsigned char> buf((size_t)sz);
    const size_t got = fread(&buf[0], 1, (size_t)sz, f);
    fclose(f);
    if (got != (size_t)sz) return false;
    return nd_png_decode(&buf[0], buf.size(), outW, outH, rgba);
}
// ===== end exact PNG decode =====
"""


# ---- Maya-side per-instance cache + image load. Calls into MATH_CPP/PNG_CPP.
CACHE_CPP = PNG_CPP + r"""// ===== mPyFile per-instance linearized-pixel cache =====
// Keyed by (path, colorSpace, prefilter settings), one entry per distinct
// image -- the same shape as the interpreted twin's ``_LINEAR_CACHE`` dict in
// _common/methods/file_texture_ops.py, so a node that reads SEVERAL images
// (compositing, an atlas) caches them all instead of thrashing one slot.
//
// std::map is deliberate: it is node-based, so inserting a new entry never
// moves an existing one. nd_tex_load_linear hands back a raw pointer INTO an
// entry's buffer, and a compute() that loads layer A then layer B still holds
// A's pointer when it samples. A single-slot cache (or any container that
// reallocates) would leave that pointer dangling.
struct NdTexEntry {
    std::vector<float> lin;
    unsigned           w = 0, h = 0;
    bool               ok = false;
};
// Monotonic, never reused. The memo in nd_tex_load_linear is thread_local and
// therefore shared by every node instance on that thread, so it has to be able
// to tell two caches apart. An ADDRESS cannot do that -- a destroyed node's
// allocation can be handed straight back to the next one -- but an id that is
// never reused can, so a stale memo row simply stops matching.
static unsigned long long nd_tex_next_cache_id() {
    static std::atomic<unsigned long long> n(1ull);
    return n.fetch_add(1ull, std::memory_order_relaxed);
}
struct NdTexCache {
    std::map<std::string, NdTexEntry> entries;
    const unsigned long long          id = nd_tex_next_cache_id();
};

// Load + linearize + prefilter, cached. Thread-safe: Hypershade's swatch
// generator pulls compute() on a worker thread, so the cache is mutex-guarded.
// Returns the linearized buffer (or nullptr on miss) and sets outW/outH.
static const float* nd_tex_load_linear_uncached(NdTexCache& cache, std::mutex& mtx,
                                       const MString& path, int cs, bool prefilter,
                                       int kernel, float radius,
                                       unsigned& outW, unsigned& outH) {
    float rq = (radius != 0.0f) ? (nearbyintf(radius * 10.0f) / 10.0f) : 0.0f;
    char buf[96];
    snprintf(buf, sizeof(buf), "|cs=%d|pf=%d:%d:%.1f",
             cs, prefilter ? 1 : 0, kernel, rq);
    std::string key = std::string(path.asChar()) + buf;
    {
        std::lock_guard<std::mutex> lk(mtx);
        std::map<std::string, NdTexEntry>::const_iterator it = cache.entries.find(key);
        if (it != cache.entries.end()) {
            if (it->second.ok) {
                outW = it->second.w; outH = it->second.h;
                return it->second.lin.data();
            }
            outW = 0; outH = 0; return nullptr;  // negative cache
        }
    }
    std::vector<float> lin;
    unsigned W = 0, H = 0;
    bool ok = false;
    if (path.length() > 0) {
        // Exact decode FIRST: it yields straight alpha, so no un-premultiply is
        // needed and nothing is lost on partial-alpha texels. nd_png_supported
        // decides, and the interpreted tier asks the same question of the same
        // bytes -- so whichever branch runs here, the other tier runs its twin.
        std::vector<unsigned char> px8;
        if (nd_png_decode_file(path.asChar(), W, H, px8) && W > 0 && H > 0) {
            nd_tex_linearize(&px8[0], W, H, cs, lin, /*unpremult=*/false);
            nd_tex_prefilter(lin, W, H, prefilter, kernel, rq);
            ok = !lin.empty();
        } else {
            W = 0; H = 0;
            MImage img;
            if (img.readFromFile(path) == MS::kSuccess) {
                img.verticalFlip();  // MImage is bottom-up; make it top-down (numpy/PIL)
                img.getSize(W, H);
                const unsigned char* px = img.pixels();
                if (px && W > 0 && H > 0) {
                    // MImage decodes with associated alpha -- see nd_tex_linearize.
                    nd_tex_linearize(px, W, H, cs, lin, /*unpremult=*/true);
                    nd_tex_prefilter(lin, W, H, prefilter, kernel, rq);
                    ok = !lin.empty();
                }
            }
        }
    }
    {
        std::lock_guard<std::mutex> lk(mtx);
        NdTexEntry& e = cache.entries[key];
        // Another thread may have filled this entry while we were loading
        // outside the lock. Only populate a still-empty one: overwriting a
        // populated buffer would invalidate the pointer that thread returned.
        if (!e.ok) {
            e.w = W; e.h = H; e.ok = ok;
            e.lin.swap(lin);
        }
        if (e.ok) { outW = e.w; outH = e.h; return e.lin.data(); }
        outW = 0; outH = 0; return nullptr;
    }
}

// Small per-thread memo in FRONT of the map. Both callers probe the SAME handful
// of keys enormously often -- a VP2 bake of a 4-layer composite asks 4 x W x H
// times, and a render asks once per layer per sample -- and the lookup above
// costs a snprintf, a std::string allocation, a mutex and a tree search, which
// together outweigh the bilinear sample they guard. Entries are never
// overwritten once populated (see the note above) and std::map never moves a
// node, so a resolved pointer stays valid for the life of its cache; the id
// check is what keeps a row from outliving the cache it came from.
static const float* nd_tex_load_linear(NdTexCache& cache, std::mutex& mtx,
                                       const MString& path, int cs, bool prefilter,
                                       int kernel, float radius,
                                       unsigned& outW, unsigned& outH) {
    struct NdTexMemo {
        std::string        path;
        unsigned long long cacheId = 0ull;
        int                cs = -1, pf = -1, kernel = -1;
        float              rq = -1.0f;
        const float*       lin = nullptr;
        unsigned           w = 0, h = 0;
        bool               valid = false;
    };
    // 8 rows: deeper than any shipped layer stack, so a composite never evicts
    // a row it is about to ask for again on the next texel.
    static thread_local NdTexMemo memo[8];
    static thread_local unsigned  memoNext = 0u;
    const float rq = (radius != 0.0f) ? (nearbyintf(radius * 10.0f) / 10.0f) : 0.0f;
    const char* pc = path.asChar();
    if (!pc) pc = "";
    const int pf = prefilter ? 1 : 0;
    for (unsigned i = 0u; i < 8u; ++i) {
        const NdTexMemo& m = memo[i];
        if (m.valid && m.cacheId == cache.id && m.cs == cs && m.pf == pf
                && m.kernel == kernel && m.rq == rq && m.path.compare(pc) == 0) {
            outW = m.w; outH = m.h; return m.lin;
        }
    }
    const float* lin = nd_tex_load_linear_uncached(cache, mtx, path, cs, prefilter,
                                                   kernel, radius, outW, outH);
    NdTexMemo& m = memo[memoNext++ & 7u];
    m.path.assign(pc);
    m.cacheId = cache.id; m.cs = cs; m.pf = pf; m.kernel = kernel; m.rq = rq;
    m.lin = lin; m.w = outW; m.h = outH; m.valid = true;
    return lin;
}

// ---- blessed composite_layers: alpha-over a stack at ONE (u, v) ------------
// Statement-for-statement twin of file_methods.composite_layers. Keeping the
// stack math in ONE kernel (rather than letting each template's compute spell
// its own loop) is what stops the compiled node and the interpreted node from
// drifting apart -- which is how the viewport and the swatch ended up
// disagreeing about opacity <= 0 in the first place.
//
// Opacity is a WEIGHT, not a switch: it scales the layer's alpha, so 0 removes
// a layer exactly and a NEGATIVE value subtracts. Nothing here skips a layer,
// because skipping and weighting differ for negative and NaN weights and the
// interpreted twin does not skip either.
//
// Accumulates in double while sampling in float, exactly as the previously
// inlined loop did, so the numbers do not move.
static void nd_tex_composite_layers(
        const std::vector<std::string>& paths,
        const double* ops, size_t nOps,
        float u, float v,
        int cs, bool prefilter, int kernel, float radius,
        int wrapU, int wrapV, const float* border, const float* missing,
        NdTexCache& cache, std::mutex& mtx, float* out) {
    double cr = 0.0, cg = 0.0, cb = 0.0, ca = 0.0;
    for (size_t i = 0; i < paths.size(); ++i) {
        unsigned lw = 0, lh = 0;
        const float* lin = nd_tex_load_linear(cache, mtx,
                                              MString(paths[i].c_str()), cs,
                                              prefilter, kernel, radius, lw, lh);
        float s[4];
        nd_tex_sample(lin, lw, lh, u, v, wrapU, wrapV, border, missing, s);
        const double op = (i < nOps) ? ops[i] : 1.0;
        const double a = (double)s[3] * op;
        const double ia = 1.0 - a;
        cr = (double)s[0] * a + cr * ia;
        cg = (double)s[1] * a + cg * ia;
        cb = (double)s[2] * a + cb * ia;
        ca = a + ca * ia;
    }
    out[0] = (float)cr; out[1] = (float)cg;
    out[2] = (float)cb; out[3] = (float)ca;
}
// ===== end mPyFile cache =====
"""


# Includes the cache block needs on top of the usual codegen set (bare form,
# matching codegen's `#include <%s>` emission).
CACHE_INCLUDES = ("string", "vector", "map", "mutex", "atomic", "cstdio",
                  "cstring", "maya/MImage.h")

# Per-instance member declarations emitted into the MPxNode subclass body.
CACHE_MEMBERS = "    NdTexCache _texCache;\n    std::mutex _texMutex;\n"


# ---- Blessed write_texture: bake an RGBA buffer to an 8-bit PNG.
# The compiled twin of file_methods.write_texture. A stateful node (a simulation
# the OSL tier cannot evaluate from (u, v, t) alone) bakes its current frame here
# and the shader samples the file. Uses the SAME MImage API the Python does, so
# the two tiers produce byte-identical images: clamp to [0,1], scale by 255,
# round-to-zero via the uint8 cast, and flip rows (MImage stores bottom-up).
WRITE_CPP = r"""// ===== blessed write_texture -> 8-bit RGBA PNG bake =====
// Mirrors _common/methods/file_methods.py:write_texture 1:1. Returns false
// instead of throwing so the call lowers as a plain expression.
template <class T>
static bool nd_tex_write(const std::string& path, const nd::Array<T>& rgba) {
    if (path.empty()) return false;
    if (rgba.shape.size() != 3 || rgba.shape[2] != 4) return false;
    const int64_t H = rgba.shape[0], W = rgba.shape[1];
    if (H <= 0 || W <= 0) return false;
    std::vector<unsigned char> buf((size_t)W * (size_t)H * 4u);
    for (int64_t y = 0; y < H; ++y) {
        // MImage is bottom-up: buffer row 0 must land on the LAST image row.
        const int64_t dst = (H - 1 - y) * W * 4;
        for (int64_t x = 0; x < W; ++x) {
            for (int64_t c = 0; c < 4; ++c) {
                double v = nd::at3(rgba, y, x, c);
                if (v < 0.0) v = 0.0;
                if (v > 1.0) v = 1.0;
                buf[(size_t)(dst + x * 4 + c)] = (unsigned char)(v * 255.0);
            }
        }
    }
    MImage img;
    img.create((unsigned)W, (unsigned)H, 4u, MImage::kByte);
    img.setPixels(buf.data(), (unsigned)W, (unsigned)H);
    // Serialized + published atomically, mirroring the Python twin. compute()
    // now runs from the VP2 override bake and the Hypershade swatch worker as
    // well as the main thread, and a stateful node rewrites ONE fixed path every
    // frame -- the same path the OSL/Arnold tier samples. writeToFile is not
    // atomic, so a reader can otherwise catch a half-written PNG. The temp sits
    // beside the target because rename() is only atomic within a filesystem.
    static std::mutex _ndWriteMutex;
    std::lock_guard<std::mutex> _ndWriteLock(_ndWriteMutex);
    const std::string tmp = path + ".tmp.png";
    if (img.writeToFile(MString(tmp.c_str()), "png") != MS::kSuccess) {
        std::remove(tmp.c_str());
        return false;
    }
    // POSIX rename() replaces an existing target atomically; MSVC's fails when
    // the target exists. Retrying after a remove keeps ONE portable code path
    // (no _WIN32 conditional, which the portability gate would flag): atomic
    // where the platform offers it, correct where it does not.
    if (std::rename(tmp.c_str(), path.c_str()) != 0) {
        std::remove(path.c_str());
        if (std::rename(tmp.c_str(), path.c_str()) != 0) {
            std::remove(tmp.c_str());
            return false;
        }
    }
    return true;
}

// Frame-stamped overload: "/tmp/x.png" + 7 -> "/tmp/x.0007.png". Mirrors
// _common/methods/file_methods.py:_stamped_bake_path (which is os.path.splitext)
// EXACTLY -- the OSL/Arnold tier rebuilds this same name at shade time from the
// base path plus its bakeFrame param, so a one-character disagreement between
// the tiers is a texture that silently fails to resolve. Arnold's texture system
// caches by filename and never re-stats, so a stateful node that bakes to one
// fixed path renders its FIRST frame forever; a new name per frame is what makes
// an Arnold render animate.
static std::string nd_tex_stamp(const std::string& path, int64_t frame) {
    // splitext: the extension starts at the last '.' of the LAST path
    // component, and a leading dot (".hidden") is not an extension.
    const size_t slash = path.find_last_of("/\\");
    const size_t dot = path.find_last_of('.');
    std::string stem = path, ext;
    if (dot != std::string::npos
            && (slash == std::string::npos || dot > slash + 1)) {
        stem = path.substr(0, dot);
        ext = path.substr(dot);
    }
    char stamp[32];
    std::snprintf(stamp, sizeof(stamp), ".%04d", (int)frame);
    return stem + stamp + ext;
}

template <class T>
static bool nd_tex_write(const std::string& path, const nd::Array<T>& rgba,
                         int64_t frame) {
    if (path.empty()) return false;
    return nd_tex_write(nd_tex_stamp(path, frame), rgba);
}
// ===== end write_texture =====
"""

# On top of the usual codegen set (MImage.h is added by the reads_image_file /
# blessed-texture gate; a write-only node still needs it, plus the containers).
# <mutex> + <cstdio> are for the atomic publish (lock, std::rename/std::remove);
# a bake-only node pulls in none of the cache machinery that would supply them.
WRITE_INCLUDES = ("string", "vector", "mutex", "cstdio", "maya/MImage.h")


# ---- Lightweight RAW-image cache for the custom-compute (AI-port) path.
# A reads_image_file node whose compute does its OWN pixel math (e.g. the
# scanline demo) gets the raw RGBA8 buffer, NOT the full linearize/sample
# pipeline. The decode (MImage::readFromFile) is still expensive, so it MUST be
# cached: per compute() = per shading sample makes a software/Arnold render
# thousands of times slower than the Python node (which loads once into
# _GRID_CACHE). Read ONCE; re-read only when the path changes. Mutex-guarded for
# the Hypershade swatch / render worker thread, like the full-parity NdTexCache.
RAW_CACHE_CPP = r"""// ===== reads_image_file raw RGBA8 per-instance cache (decode once) =====
struct NdImgRawCache {
    MString               key;
    MImage                img;
    unsigned int          w = 0, h = 0;
    const unsigned char*  pixels = nullptr;
    bool                  ok = false;
    bool                  loaded = false;
};

// MImage::readFromFile decodes the whole file; per-compute() (per-sample) decode
// is the difference between a sub-second and a many-minute render. Decode once,
// re-read only when the path changes. Thread-safe (swatch/render worker thread).
static bool nd_img_load_raw(NdImgRawCache& c, std::mutex& mtx, const MString& path,
                            unsigned int& outW, unsigned int& outH,
                            const unsigned char*& outPixels) {
    std::lock_guard<std::mutex> lk(mtx);
    if (!c.loaded || c.key != path) {
        c.loaded = true;
        c.key = path;
        c.w = 0; c.h = 0; c.pixels = nullptr; c.ok = false;
        if (path.length() > 0 && c.img.readFromFile(path) == MS::kSuccess) {
            c.img.getSize(c.w, c.h);
            c.pixels = c.img.pixels();
            c.ok = (c.pixels != nullptr && c.w > 0 && c.h > 0);
        }
    }
    outW = c.w; outH = c.h; outPixels = c.pixels;
    return c.ok;
}
// ===== end raw RGBA8 cache =====
"""

# std headers the raw cache needs beyond the usual set (maya/MImage.h is already
# added by the reads_image_file branch; MString is in the base includes).
RAW_CACHE_INCLUDES = ("mutex",)

# Per-instance members emitted into the MPxNode subclass body.
RAW_CACHE_MEMBERS = "    NdImgRawCache _imgRawCache;\n    std::mutex _imgRawMutex;\n"


# ---- Multi-file COMPOSITE cache for a reads_image_file mPyFile whose path
# input is a string ARRAY (a list of file paths).
# The single-file glue (nd_img_load_raw) reads exactly one path into one slot;
# an array of paths needs a decode-once composite. This helper mirrors the
# interpreted Init helper (_build_composite in the composite template) BYTE FOR
# BYTE so interpreted<->compiled parity holds by construction:
#   * skip blank strings and paths that don't decode,
#   * Pass 1: scan every valid file for the maximum width + height,
#   * Pass 2: nearest-neighbour resize each to (maxW,maxH) with integer index
#     mapping, premultiplied-alpha composite in order
#     (acc = src_pre + acc*(1-src_a); a file with no alpha is opaque),
#   * un-premultiply + quantize floor(x*255+0.5) into an 8-bit RGBA buffer.
# The result is exposed through the SAME _imgPixels / _imgW / _imgH / _imgOK
# interface as the single-file path (and _imgW/_imgH ARE the maximum size).
# float32 throughout to match numpy; MImage is verticalFlip'd to top-down so its
# rows match PIL/numpy (same as the full-parity NdTexCache load).
COMPOSITE_CACHE_CPP = r"""// ===== reads_image_file multi-file composite cache (build once) =====
struct NdImgCompositeCache {
    std::string                key;
    std::vector<unsigned char> buf;   // composite RGBA8, maxH*maxW*4, top-down
    unsigned int               w = 0, h = 0;
    bool                       ok = false;
    bool                       loaded = false;
};

static inline unsigned char nd_comp_quant(float x) {
    float y = floorf(x * 255.0f + 0.5f);   // round-half-up, matches numpy floor(x*255+0.5)
    if (y < 0.0f)   y = 0.0f;
    if (y > 255.0f) y = 255.0f;
    return (unsigned char)y;
}

// Build (or reuse) the composite for a list of paths. Rebuilds only when the
// path list changes. Thread-safe (Hypershade swatch / render worker thread).
static bool nd_img_composite(NdImgCompositeCache& c, std::mutex& mtx,
                             const std::vector<MString>& paths,
                             unsigned int& outW, unsigned int& outH,
                             const unsigned char*& outPixels) {
    std::lock_guard<std::mutex> lk(mtx);
    std::string key;
    for (size_t i = 0; i < paths.size(); ++i) { key += paths[i].asChar(); key += '\n'; }
    if (!c.loaded || c.key != key) {
        c.loaded = true;
        c.key = key;
        c.buf.clear();
        c.w = 0; c.h = 0; c.ok = false;

        // Pass 1 -- decode every valid file (skip blank/missing), track max size.
        struct NdLayer { std::vector<unsigned char> px; unsigned int w, h; };
        std::vector<NdLayer> layers;
        unsigned int maxW = 0, maxH = 0;
        for (size_t i = 0; i < paths.size(); ++i) {
            const MString& p = paths[i];
            if (p.length() == 0) continue;                 // blank -> skip
            MImage img;
            if (img.readFromFile(p) != MS::kSuccess) continue;  // missing/bad -> skip
            img.verticalFlip();                            // bottom-up -> top-down (PIL/numpy)
            unsigned int w = 0, h = 0;
            img.getSize(w, h);
            const unsigned char* px = img.pixels();
            if (!px || w == 0 || h == 0) continue;
            NdLayer L;
            L.w = w; L.h = h;
            L.px.assign(px, px + (size_t)w * h * 4);
            layers.push_back(std::move(L));
            if (w > maxW) maxW = w;
            if (h > maxH) maxH = h;
        }

        if (!layers.empty()) {
            // Pass 2 -- resize-to-max (nearest) + premultiplied-alpha composite.
            std::vector<float> acc((size_t)maxW * maxH * 4, 0.0f);
            bool first = true;
            for (size_t li = 0; li < layers.size(); ++li) {
                const NdLayer& L = layers[li];
                for (unsigned int y = 0; y < maxH; ++y) {
                    unsigned int sy = (y * L.h) / maxH;    // nearest, integer map
                    for (unsigned int x = 0; x < maxW; ++x) {
                        unsigned int sx = (x * L.w) / maxW;
                        const unsigned char* s = &L.px[((size_t)sy * L.w + sx) * 4];
                        float sr = s[0] / 255.0f, sg = s[1] / 255.0f,
                              sb = s[2] / 255.0f, sa = s[3] / 255.0f;
                        float* d = &acc[((size_t)y * maxW + x) * 4];
                        float pr = sr * sa, pg = sg * sa, pb = sb * sa;
                        if (first) {
                            d[0] = pr; d[1] = pg; d[2] = pb; d[3] = sa;
                        } else {
                            float ia = 1.0f - sa;
                            d[0] = pr + d[0] * ia;
                            d[1] = pg + d[1] * ia;
                            d[2] = pb + d[2] * ia;
                            d[3] = sa + d[3] * ia;
                        }
                    }
                }
                first = false;
            }
            // Un-premultiply (safe divide) + quantize to the 8-bit buffer.
            c.buf.resize((size_t)maxW * maxH * 4);
            for (size_t i = 0, n = (size_t)maxW * maxH; i < n; ++i) {
                float* d = &acc[i * 4];
                float a = d[3];
                float safe = (a > 1e-6f) ? a : 1.0f;
                c.buf[i * 4 + 0] = nd_comp_quant(d[0] / safe);
                c.buf[i * 4 + 1] = nd_comp_quant(d[1] / safe);
                c.buf[i * 4 + 2] = nd_comp_quant(d[2] / safe);
                c.buf[i * 4 + 3] = nd_comp_quant(a);
            }
            c.w = maxW; c.h = maxH; c.ok = true;
        }
    }
    outW = c.w; outH = c.h;
    outPixels = c.ok ? c.buf.data() : nullptr;
    return c.ok;
}
// ===== end multi-file composite cache =====
"""

# std headers beyond the usual set: std::string for the path-list key, <mutex>
# for the guard (vector/cmath are in the base includes; MImage.h via the
# reads_image_file branch).
COMPOSITE_CACHE_INCLUDES = ("string", "mutex")

# Per-instance members emitted into the MPxNode subclass body.
COMPOSITE_CACHE_MEMBERS = (
    "    NdImgCompositeCache _imgCompCache;\n    std::mutex _imgCompMutex;\n")


# ---- Embedded-image fallback (#98).
# The Python mPyFile ``read_texture()`` reads ``fileName`` first and, when blank /
# unreadable, falls back to a baked ``embeddedImage`` BYTE buffer:
# ``file_methods._embedded_path`` stages the bytes to a temp file and hands it to
# the loader. Maya's MImage has NO readFromMemory, so the port mirrors this exactly:
# the bytes are BAKED in as a static array, staged to a temp file ONCE
# (content-hashed name, write skipped if it exists), and read through a SEPARATE
# cache slot so the decode happens once, never per shading sample. The ported
# compute is unchanged -- it still samples ``_imgPixels`` -- because the fallback
# is resolved in the image-load glue (see emit_attr._image_read_lines).
EMBEDDED_STAGE_INCLUDES = ("fstream", "cstdlib", "cstdio", "string", "mutex")

# A second raw cache slot dedicated to the (constant) staged embedded image so it
# decodes ONCE and never thrashes with the fileName cache.
EMBEDDED_STAGE_MEMBERS = ("    NdImgRawCache _imgEmbedCache;\n"
                          "    std::mutex _imgEmbedMutex;\n")


def _ext_for_bytes(data: bytes) -> str:
    """Sniff an image extension from magic bytes (mirrors the Python
    ``_ext_for_bytes``) so the staged temp file has a suffix MImage keys off."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:2] == b"BM":
        return ".bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tif"
    return ".png"


def make_embedded_stage_cpp(img_bytes: bytes) -> str:
    """C++ for the baked embedded-image byte array + ``nd_img_embedded_path()``
    (stage-to-temp-once, return the path). Emitted above the class when a spec
    carries ``embedded_image_b64``. A byte-ARRAY initializer (not a string
    literal) so an arbitrarily large image is not capped by the MSVC ~64 KB
    single-literal limit."""
    import hashlib

    data = bytes(img_bytes)
    key = hashlib.md5(data).hexdigest()[:16]
    ext = _ext_for_bytes(data)
    # bytes, 20 per line, as an unsigned char initializer list.
    rows = [", ".join(str(b) for b in data[i:i + 20])
            for i in range(0, len(data), 20)]
    arr = ",\n    ".join(rows) if rows else ""
    return r"""// ===== mPyFile embedded-image fallback (baked bytes, staged for MImage) =====
static const unsigned char nd_embed_img[] = {
    %(arr)s
};
static const size_t nd_embed_img_len = sizeof(nd_embed_img);

// Stage the baked embedded bytes to a temp file ONCE (MImage has no
// readFromMemory) and return its path. Content-hashed name -> instances of the
// same plugin share the staged file; the write is skipped if it already exists.
static MString nd_img_embedded_path() {
    static std::mutex _m;
    static MString _staged;
    static bool _done = false;
    std::lock_guard<std::mutex> _lk(_m);
    if (_done) return _staged;
    _done = true;
    if (nd_embed_img_len == 0) return _staged;
    const char* _dir = getenv("TMPDIR");
    if (!_dir || !*_dir) _dir = getenv("TEMP");
    if (!_dir || !*_dir) _dir = getenv("TMP");
    if (!_dir || !*_dir) _dir = "/tmp";
    char _name[1024];
    snprintf(_name, sizeof(_name), "%%s/mpy_embed_%(key)s%(ext)s", _dir);
    std::string _p(_name);
    {
        std::ifstream _chk(_p.c_str(), std::ios::binary);
        if (!_chk.good()) {
            std::ofstream _f(_p.c_str(), std::ios::binary);
            if (_f.good())
                _f.write((const char*)nd_embed_img, (std::streamsize)nd_embed_img_len);
        }
    }
    _staged = MString(_p.c_str());
    return _staged;
}
// ===== end embedded-image fallback =====
""" % {"arr": arr, "key": key, "ext": ext}


# ---- Image-SEQUENCE path resolver.
# A mPyFile can drive an image SEQUENCE by substituting a per-frame number into
# its path pattern: 'render.####.png' at frame 42 -> 'render.0042.png'. This C++
# mirror is byte-identical to the Python ``_resolve_seq_path(pattern, frame)``
# Init helper (same '#'-run token, same sign-aware zero-pad = str(frame).zfill,
# same "no token -> pattern unchanged"). The load caches are keyed by the
# RESOLVED path, so a per-frame change busts the cache and reloads automatically.
# ``frame`` is an int from a numeric input, matching Python ``int(self.<t>)``.
SEQ_CPP = r"""// ===== mPyFile image-sequence path resolver (matches _resolve_seq_path) =====
static MString nd_tex_resolve_seq(const MString& pattern, int frame) {
    std::string p(pattern.asChar());
    size_t start = std::string::npos, end = std::string::npos;
    for (size_t i = 0; i < p.size(); ) {
        if (p[i] == '#') {
            size_t j = i;
            while (j < p.size() && p[j] == '#') ++j;
            start = i; end = j;   // keep the LAST '#'-run (Maya's padding token)
            i = j;
        } else { ++i; }
    }
    if (start == std::string::npos) return pattern;   // no token -> unchanged
    int width = (int)(end - start);
    bool neg = frame < 0;
    long long mag = neg ? -(long long)frame : (long long)frame;
    std::string digits = std::to_string(mag);
    std::string num;
    if (neg) num += '-';
    for (int k = (int)digits.size() + (neg ? 1 : 0); k < width; ++k) num += '0';
    num += digits;
    return MString((p.substr(0, start) + num + p.substr(end)).c_str());
}
// ===== end image-sequence path resolver =====
"""

# The resolver needs std::string / std::to_string (MString is in the base
# includes). CACHE_INCLUDES already carries "string" for the full-parity path.
SEQ_INCLUDES = ("string",)


def is_full_parity_file_node(spec: dict) -> bool:
    """True for a ``reads_image_file`` mPyFile whose captured presets include the
    full customFileTexture surface (colorSpace + wrap + borderColor). Gates the
    deterministic verified-helper emission so a bare scanline file node (or any
    non-mPyFile texture) keeps the lightweight inline ``_imgPixels`` path."""
    sug = spec.get("suggested") or {}
    if not sug.get("reads_image_file"):
        return False
    inputs = spec.get("inputs") or {}
    needed = ("fileName", "uvCoord", "colorSpace", "wrapModeU", "wrapModeV",
              "borderColor")
    return all(n in inputs for n in needed)


# ---- Recognized compute shapes for the deterministic glue.
# The verified glue (compute_glue_lines) reproduces EXACTLY a default
# load -> linearize -> prefilter -> bilinear-sample -> write. It may ALSO apply a
# recognized post-sample modulation tail (the scrolling "scanline" look the demo
# ships) -- but ONLY a tail it can faithfully emit. Anything else falls back to
# the porter, so we never silently render a look the glue does not compute.

# The default compute ends with this exact write (load + sample already done).
_DEFAULT_WRITE = "self.outColor = (r, g, b)\nself.outAlpha = a\n"

# The canonical scanline modulation tail (single source of truth for the demo
# builder AND the detector). NUM_BANDS / SPEED / TWO_PI are NAMES resolved from
# the node's Init tier; tIn is a user input wired to time.
_SCANLINE_COMPUTE_TAIL = (
    "scan = 0.4 + 0.6 * (0.5 + 0.5 * math.sin("
    "(v * NUM_BANDS - self.tIn * SPEED) * TWO_PI))\n"
    "self.outColor = (r * scan, g * scan, b * scan)\n"
    "self.outAlpha = a\n"
)

_NUM = r"([-+]?\d+\.?\d*)"
_SCANLINE_RE = re.compile(
    r"^scan\s*=\s*" + _NUM + r"\s*\+\s*" + _NUM + r"\s*\*\s*\(\s*" + _NUM
    + r"\s*\+\s*" + _NUM + r"\s*\*\s*math\.sin\(\(\s*v\s*\*\s*(\w+)\s*-\s*"
    r"self\.(\w+)\s*\*\s*(\w+)\s*\)\s*\*\s*(\w+)\)\)\s*$")
_OUTCOLOR_RE = re.compile(
    r"^self\.outColor\s*=\s*\(\s*r\s*\*\s*scan\s*,\s*g\s*\*\s*scan\s*,\s*"
    r"b\s*\*\s*scan\s*\)\s*$")
_OUTALPHA_RE = re.compile(r"^self\.outAlpha\s*=\s*a\s*$")
# The plain (unmodulated) default colour write: outColor = (r, g, b).
_DEFAULT_OUTCOLOR_RE = re.compile(
    r"^self\.outColor\s*=\s*\(\s*r\s*,\s*g\s*,\s*b\s*\)\s*$")

# Numeric-scalar input types the scanline tail's tIn may have (read into a scalar
# C++ member that `(double)` can cast). Anything else falls back to the porter.
_SCALAR_TIN_TYPES = ("float", "double", "int", "bool", "enum")


def make_scanline_compute(default_compute: str) -> str:
    """Return *default_compute* with its trailing plain write swapped for the
    canonical scanline modulation tail. The single source of truth the demo uses
    so the build and the detector cannot drift. Raises if *default_compute* does
    not end with the standard ``self.outColor=(r,g,b); self.outAlpha=a`` write."""
    if _DEFAULT_WRITE not in default_compute:
        raise ValueError(
            "compute does not end with the default file-texture write "
            "(self.outColor=(r,g,b); self.outAlpha=a)")
    return default_compute.replace(_DEFAULT_WRITE, _SCANLINE_COMPUTE_TAIL, 1)


def _norm_lines(src: str):
    """Code lines of *src* with comment-only / blank lines dropped and each line
    stripped -- a structural fingerprint robust to comments + whitespace."""
    out = []
    for ln in (src or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _match_scanline_tail(tail_lines, init_src, inputs):
    """Recognize the 3-line scanline modulation tail. Returns a tail descriptor
    (coeffs + resolved NUM_BANDS/SPEED/TWO_PI values + the tIn plug) or None."""
    if len(tail_lines) != 3:
        return None
    m = _SCANLINE_RE.match(tail_lines[0])
    if not m:
        return None
    if not _OUTCOLOR_RE.match(tail_lines[1]):
        return None
    if not _OUTALPHA_RE.match(tail_lines[2]):
        return None
    c0, c1, c2, c3, bands, tin, speed, twopi = m.groups()
    # The look constants are NAMES; resolve their numeric values from Init. If a
    # name isn't a simple numeric const there, the C++ value is unknown -> bail.
    consts = extract_simple_consts(init_src)
    if not all(n in consts for n in (bands, speed, twopi)):
        return None
    # The time input must be a captured input AND a numeric scalar: the emitted
    # C++ casts it with ``(double)in_<tin>`` (invalid for a vector/array/matrix/
    # string member) and Python ``self.tIn * SPEED`` would be element-wise on a
    # non-scalar -- either way the look would not match. Fall back otherwise.
    tinfo = (inputs or {}).get(tin)
    if not tinfo or tinfo.get("type") not in _SCALAR_TIN_TYPES:
        return None
    return {
        "c0": float(c0), "c1": float(c1), "c2": float(c2), "c3": float(c3),
        "bands": float(consts[bands]), "speed": float(consts[speed]),
        "twopi": float(consts[twopi]), "tin": tin,
    }


def _blessed_names_by_kernel(spec):
    """Blessed method names for spec['mpy_type'], split by which nd_tex_* kernel
    each lowers to: ``(load_names, sample_names)``. Reads the registry SSOT so the
    detector never hardcodes ``read_texture``/``sample_texture`` -- a rename in the
    interface table flows through automatically. Empty sets for a non-mPyFile /
    unregistered spec (spec['mpy_type'] absent -> methods_for_type(None) -> ())."""
    load, sample = set(), set()
    for ms in method_registry.methods_for_type(spec.get("mpy_type")):
        low = ms.lower
        if not isinstance(low, CppKernel):
            continue
        if low.kernel == "nd_tex_load_linear":
            load.add(ms.name)
        elif low.kernel == "nd_tex_sample":
            sample.add(ms.name)
    return load, sample


def _has_texture_core(spec):
    """True when the compute performs the load+sample core -- via EITHER the Init
    helpers (``_load_linear_pixels(`` + ``_sample(``) OR the blessed methods
    (``self.read_texture()`` + ``self.sample_texture(...)``). The blessed side is
    name-agnostic: it requires BOTH a call to a method that lowers to
    ``nd_tex_load_linear`` AND one that lowers to ``nd_tex_sample`` (mirroring the
    Init-helper gate's "both must be present"). This is only the CORE gate; the
    output-write recognizers below decide the default/scanline variant, and the
    glue re-emits the pipeline from the captured presets, so the blessed and
    Init-helper spellings route through the IDENTICAL emitter."""
    compute = spec.get("compute") or ""
    if "_load_linear_pixels(" in compute and "_sample(" in compute:
        return True
    load, sample = _blessed_names_by_kernel(spec)
    if not (load and sample):
        return False
    called = _self_method_calls(compute)
    return bool(load & called) and bool(sample & called)


def _arg_uv_channel(node, chan_of, uv_aliases, assign_counts):
    """The uvCoord channel (0 or 1) a blessed sample-call coordinate argument
    reads verbatim, or None if it is anything else. Recognizes the three authored
    spellings of "sample at uvCoord":

    * a scalar unpack alias   -- ``u, v = self.uvCoord`` -> ``u`` is channel 0,
    * a 2-vector alias index  -- ``uv = self.uvCoord``   -> ``uv[0]`` is channel 0,
    * the direct index        -- ``self.uvCoord[0]``.

    An ALIAS that is reassigned elsewhere (assignment count != 1) is untrusted ->
    None, because its value is no longer the raw channel (e.g. ``u = u * 2`` after
    the unpack). The direct ``self.uvCoord[i]`` read is always trusted."""
    if isinstance(node, ast.Name):
        ch = chan_of.get(node.id)
        if ch is None:
            return None
        return ch if assign_counts.get(node.id, 0) == 1 else None
    if isinstance(node, ast.Subscript):
        base = node.value
        if (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                and base.value.id == "self" and base.attr == "uvCoord"):
            pass                                  # direct read -> always trusted
        elif (isinstance(base, ast.Name) and base.id in uv_aliases
              and assign_counts.get(base.id, 0) == 1):
            pass                                  # single-bound 2-vector alias
        else:
            return None
        sl = node.slice
        if isinstance(sl, ast.Index):             # py<3.9 wraps the constant
            sl = sl.value
        if isinstance(sl, ast.Constant) and sl.value in (0, 1):
            return sl.value
    return None


def _target_names(target):
    """Leaf ``ast.Name`` ids of an assignment target (recurses tuple/list unpack;
    a subscript/attribute target contributes its base name so ``u[0] = ...`` and
    ``u = ...`` both count as writing ``u``)."""
    out, stack = [], [target]
    while stack:
        t = stack.pop()
        if isinstance(t, ast.Name):
            out.append(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            stack.extend(t.elts)
        elif isinstance(t, (ast.Subscript, ast.Starred)):
            stack.append(t.value)
        elif isinstance(t, ast.Attribute):
            stack.append(t.value)
    return out


def _uv_alias_maps(tree):
    """The uvCoord alias analysis both sample-coordinate checks run on:
    ``(assign_counts, chan_of, uv_aliases)``.

    ``assign_counts`` counts every binding of a name (so a rebound alias can be
    distrusted), ``chan_of`` maps a scalar unpack alias to its channel
    (``u, v = self.uvCoord``) and ``uv_aliases`` holds the 2-vector aliases
    (``uv = self.uvCoord``). Feed all three to :func:`_arg_uv_channel`."""
    assign_counts = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for nm in _target_names(t):
                    assign_counts[nm] = assign_counts.get(nm, 0) + 1
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            for nm in _target_names(n.target):
                assign_counts[nm] = assign_counts.get(nm, 0) + 1

    def _is_uv(val):
        return (isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name)
                and val.value.id == "self" and val.attr == "uvCoord")

    chan_of, uv_aliases = {}, set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1
                and _is_uv(n.value)):
            continue
        tgt = n.targets[0]
        if isinstance(tgt, ast.Name):
            uv_aliases.add(tgt.id)
        elif (isinstance(tgt, (ast.Tuple, ast.List)) and len(tgt.elts) == 2
              and all(isinstance(e, ast.Name) for e in tgt.elts)):
            chan_of[tgt.elts[0].id] = 0
            chan_of[tgt.elts[1].id] = 1
    return assign_counts, chan_of, uv_aliases


def _unwrap_num_cast(node):
    """``float(x)`` / ``int(x)`` -> ``x``. The authored Init-helper spelling casts
    the unpacked uv before passing it (``_sample(linear, float(u), float(v), ...)``);
    the cast is value-preserving for a uv double, so it must not hide the channel
    from :func:`_arg_uv_channel`. Anything else is returned unchanged."""
    while (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
           and node.func.id in ("float", "int") and len(node.args) == 1
           and not node.keywords):
        node = node.args[0]
    return node


def _blessed_sample_uv_is_default(compute, sample_names):
    """True when EVERY blessed sample call in *compute* samples EXACTLY at
    ``uvCoord[0], uvCoord[1]`` (in that order) -- the coordinate the deterministic
    glue hardcodes (``compute_glue_lines`` emits ``_u = in_uvCoord[0], _v =
    in_uvCoord[1]``). A custom coordinate (swapped axes, scaled/tiled uv, a
    reassigned alias, a different source) means the glue would sample somewhere
    ELSE than the interpreted node, so such a compute must NOT use the glue -- it
    declines here and honest-rejects downstream (uses_blessed_texture). Returns
    False when no sample call is found or the source does not parse (caller then
    declines the glue). The Init-helper spelling is checked by its own twin,
    :func:`_inline_sample_uv_is_default`."""
    try:
        tree = ast.parse(compute or "")
    except SyntaxError:
        return False

    assign_counts, chan_of, uv_aliases = _uv_alias_maps(tree)

    found = False
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self" and n.func.attr in sample_names):
            continue
        found = True
        if n.keywords or len(n.args) != 3:        # not the canonical (buf, u, v)
            return False
        u_ch = _arg_uv_channel(n.args[1], chan_of, uv_aliases, assign_counts)
        v_ch = _arg_uv_channel(n.args[2], chan_of, uv_aliases, assign_counts)
        if u_ch != 0 or v_ch != 1:
            return False
    return found


def _inline_sample_uv_is_default(compute):
    """The INIT-HELPER twin of :func:`_blessed_sample_uv_is_default`.

    ``_has_texture_core`` admits the inline spelling on the bare substrings
    ``_load_linear_pixels(`` + ``_sample(`` with NO look at the coordinate, and the
    default/scanline recognizers only read the last two/three lines -- so a uv
    mutation spliced ABOVE the write (``u = u * 2``, a swapped ``_sample(px, v, u,
    ...)``) was invisible and the node shipped the glue's uvCoord[0]/[1] sample
    instead. Close that: every bare ``*_sample(...)`` call must read the raw
    uvCoord channels. The helper's signature is ``_sample(pixels, u, v, wrap_u,
    wrap_v, border_color)``, so the coordinate is args 1/2, and the authored
    spelling casts them (``float(u)``) -- unwrapped before the channel test.

    True when there is no inline sample CALL at all (that compute is the blessed
    check's business, and the substring may only have been a comment). False on a
    parse failure or any non-verbatim coordinate; the caller then declines the
    glue."""
    try:
        tree = ast.parse(compute or "")
    except SyntaxError:
        return False

    assign_counts, chan_of, uv_aliases = _uv_alias_maps(tree)

    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id.endswith("_sample")):
            continue
        if n.keywords or len(n.args) < 3:      # not the canonical (pixels, u, v, ...)
            return False
        u_ch = _arg_uv_channel(_unwrap_num_cast(n.args[1]), chan_of, uv_aliases,
                               assign_counts)
        v_ch = _arg_uv_channel(_unwrap_num_cast(n.args[2]), chan_of, uv_aliases,
                               assign_counts)
        if u_ch != 0 or v_ch != 1:
            return False
    return True


def classify_full_parity_compute(spec: dict):
    """Classify a compute against the deterministic glue's repertoire.

    The glue reproduces a load -> linearize -> prefilter -> bilinear-sample that
    writes outColor/outAlpha, optionally modulated by a recognized scanline tail.
    The CORE is recognized loosely (the compute calls the standard Init helpers),
    matching the long-standing gate intent and staying formatting-independent
    (a reformatted/round-tripped default still qualifies). The OUTPUT WRITE then
    decides the variant:

    * plain ``outColor = (r, g, b)``               -> ("default", None)
    * scanline ``outColor = (r*scan, g*scan, ...)`` -> ("scanline", tail)
    * anything else                                 -> (None, None)

    The last case is the safety net: a custom output the glue does not reproduce
    falls back to the porter path rather than silently rendering plain texture.
    BOTH spellings are additionally coordinate-checked below, so a compute that
    samples anywhere other than uvCoord[0]/[1] cannot slip into the
    uvCoord-hardcoded glue -- including a mutation spliced ABOVE an otherwise
    default write, which the last-two-lines write recognizer cannot see."""
    compute = spec.get("compute") or ""
    if not _has_texture_core(spec):
        return (None, None)
    # Blessed authoring path: the glue samples at in_uvCoord[0]/[1], so a blessed
    # compute that samples at ANY other coordinate would silently diverge from the
    # interpreted node. Only route it through the glue when its sample call(s)
    # read uvCoord[0], uvCoord[1] verbatim; anything else declines here (-> nd
    # lower declines uvCoord float2 -> blessed honest-reject).
    _load, _sample = _blessed_names_by_kernel(spec)
    _called = _self_method_calls(compute)
    if (_sample & _called) and not _blessed_sample_uv_is_default(compute, _sample):
        return (None, None)
    # Init-helper authoring path: same hazard, same rule. _has_texture_core admits
    # it on bare substrings, so the coordinate is only checked here.
    if not _inline_sample_uv_is_default(compute):
        return (None, None)
    # The write recognizers below read only the LAST 2-3 lines, so a compute that
    # REBINDS a sampled channel between the sample and the write -- a grade,
    # `r = min(1.0, max(0.0, (r * bright - 0.5) * contrast + 0.5))` -- still ends
    # in a verbatim default write, and the glue (a bare load+sample) would
    # silently render the UNGRADED texture. Require each channel name to be bound
    # exactly once, by the sample unpack: the same "a rebound alias is distrusted"
    # rule _uv_alias_maps already applies to the uv coordinate.
    try:
        counts = _uv_alias_maps(ast.parse(compute))[0]
    except SyntaxError:
        return (None, None)
    if any(counts.get(ch, 0) > 1 for ch in ("r", "g", "b", "a")):
        return (None, None)
    norm = _norm_lines(compute)
    # plain default write (outColor=(r,g,b); outAlpha=a) -- formatting-independent
    if (len(norm) >= 2 and _OUTALPHA_RE.match(norm[-1])
            and _DEFAULT_OUTCOLOR_RE.match(norm[-2])):
        return ("default", None)
    # recognized scanline modulation tail (3 trailing lines)
    if len(norm) >= 3:
        tail = _match_scanline_tail(norm[-3:], spec.get("init") or "",
                                    spec.get("inputs") or {})
        if tail is not None:
            return ("scanline", tail)
    return (None, None)


def full_parity_tail(spec: dict):
    """The modulation-tail descriptor for *spec* (None for the pure default)."""
    return classify_full_parity_compute(spec)[1]


def _seq_frame_expr(node):
    """From the 2nd arg of ``_resolve_seq_path(...)`` return ``(plug, mode)``.

    Recognizes ``int(self.<f>)`` -> ``(f, "trunc")`` and
    ``int(round(self.<f>))`` -> ``(f, "round")``. None for anything else."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "int" and len(node.args) == 1):
        return None
    inner = node.args[0]
    mode = "trunc"
    if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
            and inner.func.id == "round" and len(inner.args) == 1):
        mode = "round"
        inner = inner.args[0]
    if (isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name)
            and inner.value.id == "self"):
        return (inner.attr, mode)
    return None


def classify_seq_path(spec: dict):
    """Return an image-SEQUENCE descriptor for *spec*'s compute, or None.

    Recognizes the canonical per-frame path idiom (matched on the AST so it is
    formatting/whitespace-independent):

        _load_linear_pixels(_resolve_seq_path(self.fileName, int(self.<f>)), ...)

    Returns ``{"frame_plug": <f>, "mode": "trunc"|"round"}`` -- the frame input
    and how Python converts it to an int -- so the glue can emit a byte-matching
    C++ ``nd_tex_resolve_seq`` call keyed on the same input. A plain
    ``self.fileName`` first argument (a STATIC single-image path) -> None."""
    compute = spec.get("compute") or ""
    try:
        tree = ast.parse(compute)
    except SyntaxError:
        return None
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_load_linear_pixels" and n.args):
            continue
        first = n.args[0]
        if not (isinstance(first, ast.Call) and isinstance(first.func, ast.Name)
                and first.func.id == "_resolve_seq_path"
                and len(first.args) == 2):
            return None       # plain path (or an unrecognized wrapper) -> static
        base = first.args[0]
        if not (isinstance(base, ast.Attribute)
                and isinstance(base.value, ast.Name)
                and base.value.id == "self" and base.attr == "fileName"):
            return None
        fr = _seq_frame_expr(first.args[1])
        if fr is None:
            return None
        return {"frame_plug": fr[0], "mode": fr[1]}
    return None


def full_parity_seq(spec: dict):
    """The image-sequence descriptor for *spec* (None -> a static image path)."""
    return classify_seq_path(spec)


def use_full_parity_glue(spec: dict) -> bool:
    """True when codegen should emit the DETERMINISTIC verified-helper texture
    pipeline (load_linear + sample, optionally + a recognized modulation tail) as
    the compute body. Requires the full preset surface AND a compute the glue can
    faithfully reproduce (the shipped default, or default + a recognized tail). A
    user who hand-edited the compute into anything else falls back to the normal
    porter path -- the glue is NEVER emitted for a look it does not compute."""
    if not is_full_parity_file_node(spec):
        return False
    return classify_full_parity_compute(spec)[0] is not None


def _member_by_plug(items, plug):
    for m in items:
        if m.get("plug") == plug:
            return m["member"]
    return None


# ---- mPyFile BASE attribute surface ---------------------------------------
# The interpreted mPyFile registers its WHOLE preset interface in initializer();
# a compiled node only ever declared the attrs its SPEC captured -- the ones the
# compute textually references. Everything else (uvFilterSize, the sampler
# presets, the derived outputs, the hidden _timeIn, the osl shader output) simply
# did not exist on the compiled node, so `convert to c++` dropped every incoming
# connection to them: time1.outTime -> _timeIn and fileTexture.osl ->
# aiOslShader.codeCache were the two the swap dialog reported.
#
# These ride the SAME emit_attr._create_lines path as a spec attr -- one attribute
# emitter, not two -- and are appended AFTER ins/outs are frozen, so nd_lower and
# emit_compute see an unchanged input/output set and the ported / lowered compute
# body stays byte-identical.

# SSOT flag key -> MFnAttribute setter. Applied AFTER _create_lines' own _flags(),
# so a declared flag wins over the generic default: that is how uvFilterSize ends
# up hidden and _timeIn non-keyable without special-casing the create emitter.
_SSOT_FLAG_CALL = {
    "keyable": "setKeyable", "storable": "setStorable", "hidden": "setHidden",
    "writable": "setWritable", "readable": "setReadable",
    "connectable": "setConnectable",
    "used_as_color": "setUsedAsColor", "used_as_filename": "setUsedAsFilename",
}

# Base plugs that are NOT in the preset SSOT because they are not part of the
# texture interface -- MPyFile.initializer() registers them directly. BOTH are
# deliberately kept OUT of attributeAffects: a kTime or string plug on the source
# side makes Maya 2026's VP2 fragment compiler reject the texture-parameter
# binding (white viewport / black swatch). The per-frame refresh comes from the
# timeChanged callback instead.
_EXTRA_BASE_ATTRS = [
    # Hidden kTime input the wrapper auto-connects from time1.outTime so
    # ``self.time`` is always available to an image-sequence expression.
    {"plug": "_timeIn", "type": "time",
     "flags": {"storable": True, "keyable": False, "readable": False,
               "writable": True, "hidden": True}},
]

# Hidden string shader output(s) -- writable (set from the OSL tab) AND readable/
# connectable (a valid connection SOURCE into aiOslShader.codeCache).
_SHADER_OUT_FLAGS = {"storable": True, "writable": True, "readable": True,
                     "connectable": True, "keyable": False, "hidden": True}


def _managed_shader_outputs():
    try:
        from mpynode._common.osl.osl_registry import MANAGED_SHADER_OUTPUTS
        return tuple(MANAGED_SHADER_OUTPUTS)
    except Exception:
        return ("osl",)


def _flag_lines(fn, flags):
    return ["    %s.%s(%s);" % (fn, _SSOT_FLAG_CALL[k], "true" if v else "false")
            for k, v in (flags or {}).items() if k in _SSOT_FLAG_CALL]


def _ssot_meta(entry):
    """emit_attr meta for one SSOT descriptor.

    Mirrors ``file_texture_interface.build_porter_meta_table`` PLUS the numeric
    defaults that projection drops -- the porter does not need them, but a
    compiled node does: without them maxLOD registers 0 instead of 16.
    """
    from mpynode._common.interface import file_texture_interface as _iface
    t = entry["attr_type"]
    meta = {"type": t}
    if t == "enum":
        meta["enum_names"] = _iface.enum_labels(entry)
        meta["default_value"] = entry["default"]
    elif t == "float2":
        meta["children"] = [c["long"] for c in entry["children"]]
    elif t in ("float", "double", "int", "bool") and entry.get("default") is not None:
        meta["default_value"] = entry["default"]
    return meta


def base_attr_members(spec: dict, members) -> list:
    """The mPyFile base plugs this node is MISSING, as emit_attr member dicts.

    Every plug the interpreted mPyFile registers but the spec never captured, in
    SSOT declaration order, then ``_timeIn`` and the managed shader outputs. A
    plug the spec already carries is skipped (the user attr wins -- it is already
    emitted). Each dict carries ``extra_flags``: post-create MFn calls the generic
    ``_create_lines`` does not emit, and ``affects``: whether it belongs on the
    SOURCE side of attributeAffects. Empty list for any other ``mpy_type``.
    """
    if (spec or {}).get("mpy_type") != "mPyFile":
        return []
    from mpynode._common.interface import file_texture_interface as _iface
    from mpynode.native.compiler.emit_attr import _ident, _fn_for
    have = set()
    for kind in ("inputs", "outputs"):
        have |= set((spec.get(kind) or {}).keys())
    taken = {m["member"] for m in (members or [])}
    out = []

    def _add(plug, kind, meta, flags, affects):
        if plug in have:
            return
        ident = _ident(plug)
        base = "a" + ident[:1].upper() + ident[1:]
        mem, i = base, 1
        while mem in taken:
            i += 1
            mem = "%s%d" % (base, i)
        taken.add(mem)
        out.append({"plug": plug, "member": mem, "kind": kind, "meta": meta,
                    "extra_flags": _flag_lines(_fn_for(meta["type"]), flags),
                    "affects": affects})

    for e in _iface.FILE_TEXTURE_ATTRS:
        is_in = e["direction"] == "input"
        _add(e["long"], "inputs" if is_in else "outputs", _ssot_meta(e),
             e.get("flags"), bool(is_in and e.get("affects_output")))
    for e in _EXTRA_BASE_ATTRS:
        _add(e["plug"], "inputs", {"type": e["type"]}, e["flags"], False)
    for nm in _managed_shader_outputs():
        _add(nm, "inputs", {"type": "string"}, _SHADER_OUT_FLAGS, False)
    return out


def base_affects_lines(ins, outs, base_extra, color_children):
    """attributeAffects for the base surface, mirroring MPyFile.initializer().

    The generic ``ins x outs`` loop in node_scaffold already wires the SPEC attrs.
    This adds the two remaining quadrants -- every affecting input (spec + base)
    to the BASE outputs, and the affecting BASE inputs to the SPEC outputs --
    each including the compound's children, because Maya's legacy software
    swatch renderer pulls outColorR/G/B individually rather than the parent.
    """
    base_in = [m for m in base_extra if m["kind"] == "inputs" and m["affects"]]
    base_out = [m for m in base_extra if m["kind"] == "outputs"]
    if not base_in and not base_out:
        return []

    def _with_children(o):
        names = [o["member"]]
        if o["meta"]["type"] == "float2":
            names += [o["member"] + "X", o["member"] + "Y"]
        else:
            names += list(color_children.get(o["member"], ()))
        return names

    L = []
    for s in list(ins) + base_in:
        for o in base_out:
            L += ["    attributeAffects(%s, %s);" % (s["member"], d)
                  for d in _with_children(o)]
    for s in base_in:
        for o in outs:
            L += ["    attributeAffects(%s, %s);" % (s["member"], d)
                  for d in _with_children(o)]
    return L


def derived_output_lines(ins, outs, base_extra, spec):
    """compute() tail that fills the base outputs the compute never authors.

    ``outTransparency = 1 - outAlpha`` per channel and ``outSize`` = the pixel
    dimensions of the node's own ``fileName``, exactly the derivations the
    interpreted mPyFile applies. Emitted at the END of finalize, so it reads the
    alpha the body just wrote. Empty when the node has neither base output.
    """
    by_plug = {m["plug"]: m for m in base_extra if m["kind"] == "outputs"}
    ot, osz = by_plug.get("outTransparency"), by_plug.get("outSize")
    if not ot and not osz:
        return []
    L = ["    // --- mPyFile derived outputs (framework-owned, not authored by "
         "the compute) ---"]
    if ot:
        alpha = _member_by_plug(outs, "outAlpha")
        # No outAlpha at all -> fully opaque, which is what a colour-only texture
        # means; never leave the plug at an uninitialized value.
        src = ("h_%s.asFloat()" % alpha) if alpha else "1.0f"
        L += [
            "    {",
            "        float _ndA = %s;" % src,
            "        _ndA = (_ndA < 0.0f) ? 0.0f : ((_ndA > 1.0f) ? 1.0f : _ndA);",
            "        const float _ndT = 1.0f - _ndA;",
            "        MDataHandle _hOT = data.outputValue(%s);" % ot["member"],
            "        _hOT.set3Float(_ndT, _ndT, _ndT);",
            "        _hOT.setClean();",
            "    }",
        ]
    if osz:
        # The image size is a property of the FILE, not of the compute, so read it
        # through the SAME cached loader the body uses -- a hit, so it costs
        # nothing extra. Needs the whole preset argument list; a node without it
        # (the multi-layer composite has no single fileName) reports (0, 0).
        need = ("fileName", "colorSpace", "preFilter", "preFilterKernel",
                "preFilterRadius")
        got = {p: _member_by_plug(ins, p) for p in need}
        can_probe = (all(got.values())
                     and (use_full_parity_glue(spec) or uses_blessed_texture(spec)))
        L.append("    {")
        L.append("        float _ndW = 0.0f, _ndH = 0.0f;")
        if can_probe:
            L += [
                "        unsigned _ndPW = 0, _ndPH = 0;",
                "        if (nd_tex_load_linear(_texCache, _texMutex, in_%s, "
                "(int)in_%s, in_%s != 0, (int)in_%s, (float)in_%s, _ndPW, _ndPH)) {"
                % (got["fileName"], got["colorSpace"], got["preFilter"],
                   got["preFilterKernel"], got["preFilterRadius"]),
                "            _ndW = (float)_ndPW; _ndH = (float)_ndPH;",
                "        }",
            ]
        L += [
            "        MDataHandle _hOS = data.outputValue(%s);" % osz["member"],
            "        _hOS.set2Float(_ndW, _ndH);",
            "        _hOS.setClean();",
            "    }",
        ]
    return L


# ---- Blessed API-method lowering (Task 4.R): a compiled mPyFile custom compute
# may call self.read_texture() / self.sample_texture(buf, u, v) and have them
# lower DETERMINISTICALLY to the nd_tex_* kernels above -- no AI porter.
# method_registry is the SSOT for which methods a node type blesses and how each
# lowers (a CppKernel name). This layer turns those specs into the transpiler's
# blessed / blessed_unpack callables, wiring each preset from its captured
# `in_<member>` local exactly like compute_glue_lines / file_methods.py, so
# interpreted <-> compiled parity holds by construction.
# CppKernel names this emitter knows how to lower. composite_layers belongs with
# the read/sample pair rather than on its own: it CALLS both of them, so a node
# that only composites still needs the sampler and the cache block emitted.
_TEXTURE_KERNELS = frozenset({"nd_tex_load_linear", "nd_tex_sample",
                              "nd_tex_composite_layers"})
# write_texture lowers to its own kernel and gates its own block: a node may BAKE
# without ever sampling, and such a node must not drag in the sampler + cache.
_WRITE_KERNELS = frozenset({"nd_tex_write"})


def _blessed_texture_names(spec, kernels=_TEXTURE_KERNELS):
    """Blessed method names available for spec['mpy_type'] whose ``lower`` is a
    CppKernel in *kernels* -- the texture pair (read_texture / sample_texture) by
    default, or ``_WRITE_KERNELS`` for the bake."""
    names = set()
    for ms in method_registry.methods_for_type(spec.get("mpy_type")):
        low = ms.lower
        if isinstance(low, CppKernel) and low.kernel in kernels:
            names.add(ms.name)
    return names


def _self_method_calls(source):
    """Names called as ``self.<name>(`` in *source* (AST scan; SyntaxError -> set())."""
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self"):
            out.add(n.func.attr)
    return out


def uses_blessed_texture(spec):
    """True when spec['compute'] calls a blessed texture method for its node type
    (so codegen must emit the nd_tex_* kernels + cache, or honest-reject)."""
    return bool(_blessed_texture_names(spec)
                & _self_method_calls(spec.get("compute") or ""))


def blessed_write_names(spec):
    """Blessed method names for spec['mpy_type'] that lower to the bake kernel."""
    return _blessed_texture_names(spec, _WRITE_KERNELS)


def uses_blessed_write(spec):
    """True when spec['compute'] calls the blessed bake (so codegen must emit the
    WRITE_CPP block, or honest-reject). Independent of uses_blessed_texture: a
    simulation node bakes its board without ever sampling an image."""
    return bool(blessed_write_names(spec)
                & _self_method_calls(spec.get("compute") or ""))


def make_blessed_lowerings(ins, outs, spec):
    """Build ``(blessed, blessed_unpack)`` transpiler-callable dicts for the
    blessed texture methods available to spec['mpy_type']. Returns ``({}, {})``
    for a non-blessed / non-mPyFile spec (zero behaviour change elsewhere).

    Each callable wires the mPyFile presets from their ``in_<member>`` locals
    EXACTLY like the interpreted adapter (file_methods.py) + the full-parity glue
    (compute_glue_lines), so parity is guaranteed. Parity-or-reject: a required
    preset absent from the captured surface raises UnsupportedSpec (routed to the
    honest-reject path) rather than silently defaulting and diverging.
    """
    if not (_blessed_texture_names(spec)
            or _blessed_texture_names(spec, _WRITE_KERNELS)):
        return {}, {}

    def _emit_load(tp, node):
        fn = _member_by_plug(ins, "fileName")
        cs = _member_by_plug(ins, "colorSpace")
        pf = _member_by_plug(ins, "preFilter")
        pk = _member_by_plug(ins, "preFilterKernel")
        pr = _member_by_plug(ins, "preFilterRadius")
        # An explicit path argument replaces fileName as the SOURCE of the
        # image, so fileName need not be captured in that spelling; every other
        # preset is still read off the node and stays required.
        args = tp._pos_args(node)
        if len(args) > 1:
            raise UnsupportedSpec(
                "blessed read_texture: expected () or (path), got %d positional "
                "argument(s)" % len(args))
        required = (("colorSpace", cs), ("preFilter", pf),
                    ("preFilterKernel", pk), ("preFilterRadius", pr))
        if not args:
            required = (("fileName", fn),) + required
        for _nm, _mem in required:
            if _mem is None:
                raise UnsupportedSpec(
                    "blessed read_texture: mPyFile input %s not captured; "
                    "cannot lower at parity" % _nm)
        if args:
            pv = tp.expr(args[0])
            if pv.type.kind != "str":
                raise UnsupportedSpec(
                    "blessed read_texture: path argument must be a string, got "
                    "%s" % pv.type.kind)
            path_code = "MString((%s).c_str())" % pv.code
        else:
            path_code = "in_%s" % fn
        t = tp._new_tmp("tb")
        w, h = t + "_w", t + "_h"

        def _load(src):
            return ("nd_tex_load_linear(_texCache, _texMutex, %s, (int)in_%s, "
                    "in_%s != 0, (int)in_%s, (float)in_%s, %s, %s)"
                    % (src, cs, pf, pk, pr, w, h))

        tp.emit("unsigned %s = 0, %s = 0;" % (w, h))
        tp.emit("const float* %s = %s;" % (t, _load(path_code)))
        # Embedded-image fallback, the C++ twin of file_methods.read_texture():
        # a node that baked `embeddedImage` bytes stays renderable with no file
        # on disk. nd_tex_load_linear already returns nullptr on a miss, and
        # NdTexCache is a std::map keyed by path -- so the retry reuses the SAME
        # cache (no second member, and the node-based map keeps the pointer the
        # first call may have handed out valid).
        #
        # Suppressed when the call passed an explicit path, matching the
        # interpreted rule exactly: that spelling means "read THIS file", and a
        # compositor relies on a blank layer path yielding no buffer.
        if not args and (spec.get("suggested") or {}).get("embedded_image_b64"):
            e = t + "_emb"
            tp.emit("if (!%s) {" % t)
            tp.emit("    MString %s = nd_img_embedded_path();" % e)
            tp.emit("    if (%s.length() > 0) { %s = %s; }" % (e, t, _load(e)))
            tp.emit("}")
        return Val(t, CppType("texbuf", handle=(t, w, h)))

    def _emit_sample(tp, node):
        args = tp._pos_args(node)
        if len(args) != 3:
            raise UnsupportedSpec(
                "blessed sample_texture: expected (buf, u, v), got %d positional "
                "argument(s)" % len(args))
        a0 = args[0]
        if isinstance(a0, ast.Name):
            bt = tp.env.get(a0.id)
            if bt is None or bt.kind != "texbuf":
                raise UnsupportedSpec(
                    "blessed sample_texture: first arg must be a read_texture() "
                    "handle")
            ptr, w, h = bt.handle
        elif isinstance(a0, ast.Call):
            bv = tp.expr(a0)
            if bv.type.kind != "texbuf":
                raise UnsupportedSpec(
                    "blessed sample_texture: first arg must be a read_texture() "
                    "handle")
            ptr, w, h = bv.type.handle
        else:
            raise UnsupportedSpec(
                "blessed sample_texture: first arg must be a read_texture() "
                "handle")

        def _coerce(argnode):
            v = tp.expr(argnode)
            if v.type.is_scalar():
                return v.code
            if v.type.is_array() and v.type.rank in (0, None):
                return "(%s).item()" % v.code
            raise UnsupportedSpec(
                "blessed sample_texture: u/v must be a scalar (or 0-d array)")

        u_expr = _coerce(args[1])
        v_expr = _coerce(args[2])

        # missing= is baked into the emitted C++, so it must be a compile-time
        # constant: None (the magenta sentinel) or a literal RGBA 4-tuple. A
        # runtime-varying value cannot lower, and a blessed call that does not
        # lower is hard-rejected rather than AI-ported -- so say why.
        miss_node = tp._kw(node, "missing")
        miss = (1.0, 0.0, 1.0, 1.0)
        if miss_node is not None and not (
                isinstance(miss_node, ast.Constant) and miss_node.value is None):
            if (not isinstance(miss_node, (ast.Tuple, ast.List))
                    or len(miss_node.elts) != 4):
                raise UnsupportedSpec(
                    "blessed sample_texture: missing= must be None or a literal "
                    "(r, g, b, a) 4-tuple")
            vals = []
            for el in miss_node.elts:
                if (not isinstance(el, ast.Constant)
                        or isinstance(el.value, bool)
                        or not isinstance(el.value, (int, float))):
                    raise UnsupportedSpec(
                        "blessed sample_texture: missing= components must be "
                        "numeric literals")
                vals.append(float(el.value))
            miss = tuple(vals)

        wu = _member_by_plug(ins, "wrapModeU")
        wv = _member_by_plug(ins, "wrapModeV")
        bc = _member_by_plug(ins, "borderColor")
        for _nm, _mem in (("wrapModeU", wu), ("wrapModeV", wv),
                          ("borderColor", bc)):
            if _mem is None:
                raise UnsupportedSpec(
                    "blessed sample_texture: mPyFile input %s not captured; "
                    "cannot lower at parity" % _nm)
        k = tp._new_tmp("sm")
        tp.emit("float %s_bd[3] = { in_%s[0], in_%s[1], in_%s[2] };"
                % (k, bc, bc, bc))
        tp.emit("float %s_ms[4] = { %sf, %sf, %sf, %sf };"
                % ((k,) + tuple(repr(c) for c in miss)))
        tp.emit("float %s[4];" % k)
        tp.emit("nd_tex_sample(%s, %s, %s, (float)(%s), (float)(%s), (int)in_%s, "
                "(int)in_%s, %s_bd, %s_ms, %s);"
                % (ptr, w, h, u_expr, v_expr, wu, wv, k, k, k))
        return [Val("(double)%s[%d]" % (k, i), scalar_t("double"))
                for i in range(4)]

    def _emit_composite(tp, node):
        """self.composite_layers(layers, opacities, u, v[, missing=]) -> 4 Vals.

        Unpack-kind, like sample_texture: the call sites destructure it into
        (r, g, b, a)."""
        args = tp._pos_args(node)
        if len(args) != 4:
            raise UnsupportedSpec(
                "blessed composite_layers: expected (layers, opacities, u, v), "
                "got %d positional argument(s)" % len(args))
        lv = tp.expr(args[0])
        if lv.type.kind != "strv":
            raise UnsupportedSpec(
                "blessed composite_layers: layers must be a string ARRAY input, "
                "got %s" % lv.type.kind)
        ov = tp.expr(args[1])
        if not ov.type.is_array():
            raise UnsupportedSpec(
                "blessed composite_layers: opacities must be a numeric ARRAY "
                "input, got %s" % ov.type.kind)

        def _coerce(argnode):
            val = tp.expr(argnode)
            if val.type.is_scalar():
                return val.code
            if val.type.is_array() and val.type.rank in (0, None):
                return "(%s).item()" % val.code
            raise UnsupportedSpec(
                "blessed composite_layers: u/v must be a scalar (or 0-d array)")

        u_expr = _coerce(args[2])
        v_expr = _coerce(args[3])

        # missing= is baked into the emitted C++, so it has to be a compile-time
        # constant -- same rule (and same reason) as sample_texture. The default
        # differs though: a composite wants an unresolvable layer to DROP OUT,
        # not to cover the stack with the magenta sentinel.
        miss_node = tp._kw(node, "missing")
        miss = (0.0, 0.0, 0.0, 0.0)
        if miss_node is not None and not (
                isinstance(miss_node, ast.Constant) and miss_node.value is None):
            if (not isinstance(miss_node, (ast.Tuple, ast.List))
                    or len(miss_node.elts) != 4):
                raise UnsupportedSpec(
                    "blessed composite_layers: missing= must be None or a "
                    "literal (r, g, b, a) 4-tuple")
            vals = []
            for el in miss_node.elts:
                if (not isinstance(el, ast.Constant)
                        or isinstance(el.value, bool)
                        or not isinstance(el.value, (int, float))):
                    raise UnsupportedSpec(
                        "blessed composite_layers: missing= components must be "
                        "numeric literals")
                vals.append(float(el.value))
            miss = tuple(vals)

        cs = _member_by_plug(ins, "colorSpace")
        pf = _member_by_plug(ins, "preFilter")
        pk = _member_by_plug(ins, "preFilterKernel")
        pr = _member_by_plug(ins, "preFilterRadius")
        wu = _member_by_plug(ins, "wrapModeU")
        wv = _member_by_plug(ins, "wrapModeV")
        bc = _member_by_plug(ins, "borderColor")
        for _nm, _mem in (("colorSpace", cs), ("preFilter", pf),
                          ("preFilterKernel", pk), ("preFilterRadius", pr),
                          ("wrapModeU", wu), ("wrapModeV", wv),
                          ("borderColor", bc)):
            if _mem is None:
                raise UnsupportedSpec(
                    "blessed composite_layers: mPyFile input %s not captured; "
                    "cannot lower at parity" % _nm)

        k = tp._new_tmp("cl")
        # The opacities array is contiguous double data; hand the kernel a bare
        # pointer + count so it can apply the same "past the end -> 1.0" rule
        # the interpreted twin applies.
        tp.emit("nd::Array<double> %s_op = %s;" % (k, ov.code))
        tp.emit("if (%s_op.offset != 0 || !%s_op.is_contiguous()) "
                "%s_op = %s_op.copy();" % (k, k, k, k))
        tp.emit("float %s_bd[3] = { in_%s[0], in_%s[1], in_%s[2] };"
                % (k, bc, bc, bc))
        tp.emit("float %s_ms[4] = { %sf, %sf, %sf, %sf };"
                % ((k,) + tuple(repr(c) for c in miss)))
        tp.emit("float %s[4];" % k)
        tp.emit("nd_tex_composite_layers(%s, (*%s_op.data).data(), "
                "(size_t)%s_op.size(), (float)(%s), (float)(%s), (int)in_%s, "
                "in_%s != 0, (int)in_%s, (float)in_%s, (int)in_%s, (int)in_%s, "
                "%s_bd, %s_ms, _texCache, _texMutex, %s);"
                % (lv.code, k, k, u_expr, v_expr, cs, pf, pk, pr, wu, wv,
                   k, k, k))
        return [Val("(double)%s[%d]" % (k, i), scalar_t("double"))
                for i in range(4)]

    def _emit_write(tp, node):
        args = tp._pos_args(node)
        if len(args) not in (2, 3):
            raise UnsupportedSpec(
                "blessed write_texture: expected (path, rgba[, frame]), got %d "
                "positional argument(s)" % len(args))
        pv = tp.expr(args[0])
        if pv.type.kind != "str":
            raise UnsupportedSpec(
                "blessed write_texture: path argument must be a string, got %s"
                % pv.type.kind)
        bv = tp.expr(args[1])
        if not bv.type.is_array() or bv.type.rank not in (3, None):
            raise UnsupportedSpec(
                "blessed write_texture: rgba must be an (H, W, 4) array")
        if len(args) == 2:
            return Val("nd_tex_write(%s, %s)" % (pv.code, bv.code),
                       scalar_t("bool"))
        # Frame-stamped bake. The overload takes int64_t, matching the Python
        # twin's int(frame) truncation, so both tiers name the same file.
        fv = tp.expr(args[2])
        if fv.type.is_array() or fv.type.kind == "str":
            raise UnsupportedSpec(
                "blessed write_texture: frame must be a numeric scalar, got %s"
                % fv.type.kind)
        return Val("nd_tex_write(%s, %s, (int64_t)(%s))"
                   % (pv.code, bv.code, fv.code), scalar_t("bool"))

    blessed, blessed_unpack = {}, {}
    for ms in method_registry.methods_for_type(spec.get("mpy_type")):
        low = ms.lower
        if not isinstance(low, CppKernel):
            continue                      # Transpile-lower (future) -> not here
        if low.kernel == "nd_tex_load_linear":
            blessed[ms.name] = _emit_load
        elif low.kernel == "nd_tex_sample":
            blessed_unpack[ms.name] = _emit_sample
        elif low.kernel == "nd_tex_composite_layers":
            blessed_unpack[ms.name] = _emit_composite
        elif low.kernel == "nd_tex_write":
            blessed[ms.name] = _emit_write
        else:
            # A blessed method lowered to a C++ kernel this emitter does not
            # know -- a blessing bug. Fail loud rather than silently drop it.
            raise UnsupportedSpec(
                "blessed method %r lowers to unknown C++ kernel %r; refusing to "
                "silently drop a blessed call" % (ms.name, low.kernel))
    return blessed, blessed_unpack


def compute_glue_lines(ins, outs, tail=None, seq=None):
    """Deterministic C++ compute body for a full-parity mPyFile: cache-load the
    linearized pixels, bilinear-sample at uvCoord, write outColor/outAlpha.

    Spec-driven (looks up each preset's emitted member), so it does not hardcode
    member names. Inputs are already read into ``in_<member>`` by the caller.

    *tail* (optional) is a recognized post-sample modulation descriptor from
    ``classify_full_parity_compute``. When present (the scanline look), outColor
    is modulated by ``scan`` -- derived from uvCoord's v and the tIn input -- so
    the compiled node reproduces the demo's scrolling band at parity.

    *seq* (optional) is an image-SEQUENCE descriptor from ``classify_seq_path``.
    When present, the load path is resolved per frame via ``nd_tex_resolve_seq``
    (``{"frame_plug", "mode"}``) instead of the raw ``fileName`` -- the frame
    number is substituted into the ``#``-padded pattern and the path-keyed cache
    reloads the new file automatically.
    """
    fn = _member_by_plug(ins, "fileName")
    uv = _member_by_plug(ins, "uvCoord")
    cs = _member_by_plug(ins, "colorSpace")
    pf = _member_by_plug(ins, "preFilter")
    pk = _member_by_plug(ins, "preFilterKernel")
    pr = _member_by_plug(ins, "preFilterRadius")
    wu = _member_by_plug(ins, "wrapModeU")
    wv = _member_by_plug(ins, "wrapModeV")
    bc = _member_by_plug(ins, "borderColor")
    oc = _member_by_plug(outs, "outColor")
    oa = _member_by_plug(outs, "outAlpha")
    # preFilter knobs are optional in the captured surface; default to off/0 if a
    # particular preset was not referenced by the compute (and thus not captured).
    cs_e = "(int)in_%s" % cs if cs else "0"
    pf_e = "in_%s != 0" % pf if pf else "false"
    pk_e = "(int)in_%s" % pk if pk else "0"
    pr_e = "(float)in_%s" % pr if pr else "0.0f"
    # image sequence: resolve the per-frame path from the '#'-padded pattern +
    # the frame input, byte-identical to _resolve_seq_path. The path-keyed cache
    # then reloads whenever the resolved path changes (i.e. every frame).
    path_expr = "in_%s" % fn
    seq_lines = []
    fm = _member_by_plug(ins, seq["frame_plug"]) if seq else None
    if fm:
        frame_cpp = ("(int)nearbyint((double)in_%s)" % fm
                     if seq.get("mode") == "round" else "(int)in_%s" % fm)
        seq_lines = [
            "    // image sequence: per-frame path (reloads on change)",
            "    MString _seqPath = nd_tex_resolve_seq(in_%s, %s);"
            % (fn, frame_cpp),
        ]
        path_expr = "_seqPath"
    L = seq_lines + [
        "    unsigned _linW = 0, _linH = 0;",
        "    const float* _lin = nd_tex_load_linear(_texCache, _texMutex, %s,"
        % path_expr,
        "        %s, %s, %s, %s, _linW, _linH);" % (cs_e, pf_e, pk_e, pr_e),
        "    float _u = in_%s[0], _v = in_%s[1];" % (uv, uv),
        "    float _border[3] = { in_%s[0], in_%s[1], in_%s[2] };" % (bc, bc, bc),
        "    float _miss[4] = { 1.0f, 0.0f, 1.0f, 1.0f };",
        "    float _outc[4];",
        "    nd_tex_sample(_lin, _linW, _linH, _u, _v, (int)in_%s, (int)in_%s, "
        "_border, _miss, _outc);" % (wu, wv),
    ]
    if tail is None:
        L += [
            "    h_%s.set3Float(_outc[0], _outc[1], _outc[2]);" % oc,
            "    h_%s.setFloat(_outc[3]);" % oa,
        ]
        return L

    # Recognized scanline modulation: scan = c0 + c1 * (c2 + c3 * sin((v*bands -
    # tIn*speed) * twopi)); outColor *= scan (alpha passes through). _v is already
    # declared above (the bilinear-sample u/v). std::sin in <cmath> (base include).
    tin = _member_by_plug(ins, tail["tin"])
    L += [
        "    // scanline modulation (scrolling band; reads %s + uvCoord v)"
        % tail["tin"],
        "    double _s = %r + %r * std::sin((_v * %r - (double)in_%s * %r) * %r);"
        % (tail["c2"], tail["c3"], tail["bands"], tin, tail["speed"],
           tail["twopi"]),
        "    double _scan = %r + %r * _s;" % (tail["c0"], tail["c1"]),
        "    h_%s.set3Float((float)(_outc[0] * _scan), (float)(_outc[1] * _scan), "
        "(float)(_outc[2] * _scan));" % oc,
        "    h_%s.setFloat(_outc[3]);" % oa,
    ]
    return L
