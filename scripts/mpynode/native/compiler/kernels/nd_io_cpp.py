"""nd_io -- runtime ARRAY file IO for compiled nodes (read + write).

The transpiler has no dict/list kind, so a document-shaped reader can never be
lowered. What it DOES have is ``nd::Array<T>`` -- and every entry point here
returns exactly that, so ``np.fromfile`` / ``np.load`` / ``ndio.read`` lower with
NO change to the type lattice. That is the whole design: the format is chosen so
the result is already representable.

Four backends, sniffed from the leading bytes so one cache serves all of them:

  * RAW    -- headerless; the caller supplies the dtype (``np.fromfile``).
  * NPY    -- numpy's own ``.npy`` (magic ``\\x93NUMPY``); self-describing.
  * NDIO   -- our container (magic ``NDIO\\x01``): many NAMED arrays in one file,
              which is what replaces ``.npz`` / JSON without needing a dict type.
  * JSON   -- a flat object of number arrays. Schema-narrow on purpose; it exists
              so existing JSON assets keep working, not as a general parser.

Everything is little-endian, matching numpy's default on every platform this
ships to. Binary formats have NO locale hazard -- the ``strtod_l`` trap only
applies to the JSON backend, which pins the C locale for exactly that reason.
"""

from __future__ import annotations

import re

# Source spellings that lower to an nd_io call (see py_to_cpp._call_ndio,
# _call_numpy, _call_method). Gates kernel + member emission in EVERY emitter,
# so it is biased to over-detect: a false positive emits an unused static
# kernel, a false negative is a link error.
_NDIO_USE_RE = re.compile(
    r"\bndio\s*\.\s*(?:read|read_raw|write|write_raw|frame_path)\s*\("
    r"|\b\w+\s*\.\s*(?:fromfile|save)\s*\("
    r"|\.\s*tofile\s*\(")


def spec_uses_ndio(spec) -> bool:
    """True if the node's compute or init calls a lowered file-IO form.

    Matched on SOURCE, not on transpiler state, because the include list and the
    class members are emitted before/independently of the compute lowering.
    """
    src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    return bool(_NDIO_USE_RE.search(src))


def reject_unlowered_io(spec, lowered, what: str) -> None:
    """Hard-fail a compute that does file IO but did NOT deterministically lower.

    Without this, an unlowerable IO compute falls through to the AI porter, which
    emits a ``// TODO: fill the buffers`` PORT region -- a node that COMPILES,
    LOADS, and silently outputs nothing. That failure mode is worse than not
    compiling at all, because the read looks like it happened.

    ``lowered`` is the ``nd_lower.try_lower_*`` result (``None`` == fell back).
    Pass ``None`` unconditionally from an emitter that has no deterministic path.
    """
    if lowered is not None or not spec_uses_ndio(spec):
        return
    from mpynode.native.compiler.errors import UnsupportedSpec
    raise UnsupportedSpec(
        "this %s does file I/O (ndio.read/write, np.fromfile/np.save, .tofile) "
        "but its compute did not lower deterministically, so there is nothing to "
        "attach the reads to. The AI porter is NOT allowed to guess here -- it "
        "would emit a node that loads and silently produces nothing. Simplify the "
        "compute until it lowers (the file calls themselves are supported)." % what)


# Includes the kernel needs on top of the usual codegen set (bare form, matching
# codegen's `#include <%s>` emission).
NDIO_INCLUDES = ("string", "vector", "map", "mutex", "fstream", "cstdio",
                 "cstdlib", "cstring", "cstdint", "locale.h", "sys/types.h",
                 "sys/stat.h")

# Per-instance member declarations emitted into the node class body. A cache is
# per-INSTANCE (not static) so two nodes reading different files don't evict
# each other, and mutex-guarded because Maya pulls compute() on worker threads.
NDIO_MEMBERS = "    NdIoCache _ndioCache;\n    std::mutex _ndioMutex;\n"


NDIO_CPP = r"""// ===== nd_io: runtime array file IO (raw / npy / ndio / json) =====
#ifndef ND_IO_KERNEL_INCLUDED
#define ND_IO_KERNEL_INCLUDED

// Locale-pinned strtod for the JSON backend. If anything in the Maya process
// sets LC_NUMERIC to a comma-decimal locale, a bare strtod() parses "1.92" as 1.
#ifdef _MSC_VER
static _locale_t nd_io_cloc() {
    static _locale_t L = _create_locale(LC_NUMERIC, "C");
    return L;
}
#define ND_IO_STRTOD(p, e) _strtod_l((p), (e), nd_io_cloc())
#else
static locale_t nd_io_cloc() {
    static locale_t L = newlocale(LC_NUMERIC_MASK, "C", (locale_t)0);
    return L;
}
#define ND_IO_STRTOD(p, e) strtod_l((p), (e), nd_io_cloc())
#endif

// dtype codes mirror numpy's char/size pair: 'f'/'i'/'u' + itemsize.
struct NdIoDtype {
    char kind;      // 'f' | 'i' | 'u'
    int  size;      // bytes per element
    NdIoDtype() : kind('f'), size(8) {}
    NdIoDtype(char k, int s) : kind(k), size(s) {}
};

struct NdIoArray {
    NdIoDtype             dt;
    std::vector<int64_t>  shape;
    std::vector<char>     bytes;   // raw little-endian payload
    int64_t count() const {
        int64_t n = 1;
        for (size_t i = 0; i < shape.size(); ++i) n *= shape[i];
        return shape.empty() ? 0 : n;
    }
};

struct NdIoDoc {
    std::map<std::string, NdIoArray> arrays;
    bool ok = false;
};

struct NdIoCache {
    std::string key;       // path | mtime | size  -> re-reads when the file changes
    NdIoDoc     doc;
    bool        loaded = false;
};

// ---- little-endian scalar decode -----------------------------------------
static double nd_io_elem_f(const char* p, const NdIoDtype& dt) {
    if (dt.kind == 'f') {
        if (dt.size == 4) { float v; std::memcpy(&v, p, 4); return (double)v; }
        double v; std::memcpy(&v, p, 8); return v;
    }
    if (dt.kind == 'u') {
        if (dt.size == 1) { uint8_t v;  std::memcpy(&v, p, 1); return (double)v; }
        if (dt.size == 2) { uint16_t v; std::memcpy(&v, p, 2); return (double)v; }
        if (dt.size == 4) { uint32_t v; std::memcpy(&v, p, 4); return (double)v; }
        uint64_t v; std::memcpy(&v, p, 8); return (double)v;
    }
    if (dt.size == 1) { int8_t v;  std::memcpy(&v, p, 1); return (double)v; }
    if (dt.size == 2) { int16_t v; std::memcpy(&v, p, 2); return (double)v; }
    if (dt.size == 4) { int32_t v; std::memcpy(&v, p, 4); return (double)v; }
    int64_t v; std::memcpy(&v, p, 8); return (double)v;
}

// ---- whole-file read ------------------------------------------------------
static bool nd_io_slurp(const std::string& path, std::vector<char>& out) {
    std::ifstream fh(path.c_str(), std::ios::in | std::ios::binary);
    if (!fh) return false;
    fh.seekg(0, std::ios::end);
    std::streamoff n = fh.tellg();
    if (n < 0) return false;
    fh.seekg(0, std::ios::beg);
    out.resize((size_t)n);
    if (n > 0) fh.read(out.data(), n);
    return fh.good() || fh.eof();
}

static std::string nd_io_stat_key(const std::string& path) {
    // mtime+size in the cache key: a file rewritten under the SAME name is
    // picked up, which a path-only key would silently miss. stat() is ~micro-
    // seconds, far below the mesh rebuild it guards.
    //
    // NANOSECONDS matter here. st_mtime alone is 1-second resolution, so a file
    // rewritten within the same second at the SAME size -- exactly what a
    // simulation writing frame after frame does -- would keep hitting a stale
    // cache entry. Where the platform exposes sub-second mtime, use it.
    struct stat st;
    char buf[128];
    if (stat(path.c_str(), &st) != 0) return path + "|missing";
    long long nsec = 0;
#if defined(__APPLE__)
    nsec = (long long)st.st_mtimespec.tv_nsec;
#elif defined(__linux__)
    nsec = (long long)st.st_mtim.tv_nsec;
#endif
    std::snprintf(buf, sizeof(buf), "|%lld|%lld|%lld",
                  (long long)st.st_mtime, nsec, (long long)st.st_size);
    return path + buf;
}

// ---- frame -> filename ----------------------------------------------------
// "mesh.####.json" + 7 -> "mesh.0007.json"; no '#' -> unchanged. The FIRST run
// of '#' wins. This exists because a compiled compute cannot format an int into
// a string (no str(), no %, no f-string in the lowerable surface), so without it
// a file-per-frame sequence could never compile.
//
// Must match mpynode/ndio.py::frame_path EXACTLY, including negatives: the cast
// truncates toward zero like Python's int(), and "%0*lld" pads like zfill
// (-7 at pad 4 -> "-007" in both).
static std::string nd_io_frame_path(const std::string& tmpl, double frame) {
    const size_t a = tmpl.find('#');
    if (a == std::string::npos) return tmpl;
    size_t b = a;
    while (b < tmpl.size() && tmpl[b] == '#') ++b;
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%0*lld", (int)(b - a),
                  (long long)frame);
    return tmpl.substr(0, a) + buf + tmpl.substr(b);
}

// ---- NPY ------------------------------------------------------------------
static bool nd_io_parse_npy(const std::vector<char>& b, NdIoDoc& doc) {
    static const char MAGIC[6] = { '\x93', 'N', 'U', 'M', 'P', 'Y' };
    if (b.size() < 10 || std::memcmp(b.data(), MAGIC, 6) != 0) return false;
    const unsigned char major = (unsigned char)b[6];
    size_t hlen = 0, off = 0;
    if (major == 1) {
        uint16_t h; std::memcpy(&h, b.data() + 8, 2);
        hlen = h; off = 10;
    } else {
        if (b.size() < 12) return false;
        uint32_t h; std::memcpy(&h, b.data() + 8, 4);
        hlen = h; off = 12;
    }
    if (off + hlen > b.size()) return false;
    const std::string hdr(b.data() + off, hlen);

    // The header is a Python dict LITERAL. It is parsed here, at runtime, in
    // C++ -- the transpiler never sees a dict, which is why .npy is cheap.
    NdIoArray a;
    size_t d = hdr.find("'descr'");
    if (d == std::string::npos) return false;
    size_t q1 = hdr.find('\'', hdr.find(':', d));
    size_t q2 = (q1 == std::string::npos) ? std::string::npos : hdr.find('\'', q1 + 1);
    if (q2 == std::string::npos) return false;
    std::string descr = hdr.substr(q1 + 1, q2 - q1 - 1);
    if (descr.size() < 3) return false;
    if (descr[0] == '>') return false;                 // big-endian: unsupported
    a.dt = NdIoDtype(descr[1], std::atoi(descr.c_str() + 2));
    if (a.dt.size <= 0 || a.dt.size > 8) return false;
    if (a.dt.kind != 'f' && a.dt.kind != 'i' && a.dt.kind != 'u') return false;
    if (hdr.find("'fortran_order': True") != std::string::npos) return false;

    size_t s = hdr.find("'shape'");
    if (s == std::string::npos) return false;
    size_t lp = hdr.find('(', s), rp = hdr.find(')', lp);
    if (lp == std::string::npos || rp == std::string::npos) return false;
    const std::string shp = hdr.substr(lp + 1, rp - lp - 1);
    for (size_t i = 0; i < shp.size();) {
        while (i < shp.size() && (shp[i] == ' ' || shp[i] == ',')) ++i;
        if (i >= shp.size()) break;
        char* end = 0;
        long long v = std::strtoll(shp.c_str() + i, &end, 10);
        if (end == shp.c_str() + i) break;
        a.shape.push_back((int64_t)v);
        i = (size_t)(end - shp.c_str());
    }
    if (a.shape.empty()) a.shape.push_back(0);
    const size_t need = (size_t)a.count() * (size_t)a.dt.size;
    if (off + hlen + need > b.size()) return false;
    a.bytes.assign(b.begin() + off + hlen, b.begin() + off + hlen + need);
    doc.arrays[""] = a;
    doc.ok = true;
    return true;
}

// ---- NDIO container -------------------------------------------------------
// magic "NDIO\x01" | u32 count | per array: u16 namelen, name, dtype[2],
// u8 ndim, i64 shape[ndim], u64 nbytes, payload
static bool nd_io_parse_ndio(const std::vector<char>& b, NdIoDoc& doc) {
    static const char MAGIC[5] = { 'N', 'D', 'I', 'O', '\x01' };
    if (b.size() < 9 || std::memcmp(b.data(), MAGIC, 5) != 0) return false;
    size_t p = 5;
    uint32_t n = 0; std::memcpy(&n, b.data() + p, 4); p += 4;
    for (uint32_t k = 0; k < n; ++k) {
        if (p + 2 > b.size()) return false;
        uint16_t nl; std::memcpy(&nl, b.data() + p, 2); p += 2;
        if (p + nl + 3u > b.size()) return false;
        std::string name(b.data() + p, nl); p += nl;
        NdIoArray a;
        a.dt = NdIoDtype(b[p], (int)(b[p + 1] - '0')); p += 2;
        if (a.dt.size <= 0 || a.dt.size > 8) return false;
        uint8_t nd = (uint8_t)b[p]; p += 1;
        if (p + (size_t)nd * 8 + 8 > b.size()) return false;
        for (uint8_t i = 0; i < nd; ++i) {
            int64_t d; std::memcpy(&d, b.data() + p, 8); p += 8;
            a.shape.push_back(d);
        }
        uint64_t nb; std::memcpy(&nb, b.data() + p, 8); p += 8;
        if (p + nb > b.size()) return false;
        a.bytes.assign(b.begin() + p, b.begin() + p + (size_t)nb); p += (size_t)nb;
        doc.arrays[name] = a;
    }
    doc.ok = true;
    return true;
}

// ---- JSON (flat object of number arrays) ----------------------------------
static void nd_io_json_ws(const char* s, size_t n, size_t& i) {
    while (i < n && (s[i]==' '||s[i]=='\t'||s[i]=='\n'||s[i]=='\r'||s[i]==',')) ++i;
}

static bool nd_io_json_str(const char* s, size_t n, size_t& i, std::string& out) {
    if (i >= n || s[i] != '"') return false;
    ++i; out.clear();
    while (i < n) {
        char c = s[i];
        if (c == '\\') {
            if (i + 1 >= n) return false;
            char e = s[i + 1];
            out.push_back(e == 'n' ? '\n' : e == 't' ? '\t' : e == 'r' ? '\r' : e);
            i += 2; continue;
        }
        if (c == '"') { ++i; return true; }
        out.push_back(c); ++i;
    }
    return false;
}

static bool nd_io_parse_json(const std::vector<char>& b, NdIoDoc& doc) {
    const char* s = b.data();
    const size_t n = b.size();
    size_t i = 0;
    nd_io_json_ws(s, n, i);
    if (i >= n || s[i] != '{') return false;
    ++i;
    while (i < n) {
        nd_io_json_ws(s, n, i);
        if (i < n && s[i] == '}') { ++i; break; }
        std::string key;
        if (!nd_io_json_str(s, n, i, key)) return false;
        nd_io_json_ws(s, n, i);
        if (i >= n || s[i] != ':') return false;
        ++i;
        nd_io_json_ws(s, n, i);
        if (i >= n) return false;
        if (s[i] == '[') {
            // Flatten to the matching close bracket, so [[x,y,z],...] and
            // [x,y,z,...] are both legal spellings. Rows are counted so the
            // nested form recovers its (N, cols) shape.
            int depth = 0;
            int64_t rows = 0, cols = 0, cur = 0;
            std::vector<double> vals;
            while (i < n) {
                char c = s[i];
                if (c == '[') {
                    ++depth; ++i;
                    if (depth == 2) cur = 0;
                    continue;
                }
                if (c == ']') {
                    --depth; ++i;
                    if (depth == 1) { ++rows; if (cols == 0) cols = cur; else if (cols != cur) cols = -1; }
                    if (depth == 0) break;
                    continue;
                }
                if (c==' '||c=='\t'||c=='\n'||c=='\r'||c==',') { ++i; continue; }
                const char* st = s + i;
                char* end = 0;
                double v = ND_IO_STRTOD(st, &end);
                if (end == st) return false;
                vals.push_back(v); ++cur;
                i += (size_t)(end - st);
            }
            NdIoArray a;
            a.dt = NdIoDtype('f', 8);
            if (rows > 0 && cols > 0 && rows * cols == (int64_t)vals.size()) {
                a.shape.push_back(rows); a.shape.push_back(cols);
            } else {
                a.shape.push_back((int64_t)vals.size());
            }
            a.bytes.resize(vals.size() * sizeof(double));
            if (!vals.empty())
                std::memcpy(a.bytes.data(), vals.data(), a.bytes.size());
            doc.arrays[key] = a;
        } else if (s[i] == '"') {
            std::string sv;
            if (!nd_io_json_str(s, n, i, sv)) return false;   // strings ignored
        } else if (s[i] == '{') {
            int depth = 0;                                    // nested obj: skip
            while (i < n) {
                if (s[i] == '{') ++depth;
                else if (s[i] == '}') { --depth; if (!depth) { ++i; break; } }
                ++i;
            }
        } else {
            const char* st = s + i;
            char* end = 0;
            double v = ND_IO_STRTOD(st, &end);
            if (end == st) {
                if (n - i >= 4 && !std::strncmp(s + i, "true", 4))  { v = 1; end = (char*)(s+i+4); }
                else if (n - i >= 5 && !std::strncmp(s + i, "false", 5)) { v = 0; end = (char*)(s+i+5); }
                else if (n - i >= 4 && !std::strncmp(s + i, "null", 4))  { v = 0; end = (char*)(s+i+4); }
                else return false;
            }
            NdIoArray a;
            a.dt = NdIoDtype('f', 8);
            a.shape.push_back(1);
            a.bytes.resize(sizeof(double));
            std::memcpy(a.bytes.data(), &v, sizeof(double));
            doc.arrays[key] = a;
            i += (size_t)(end - st);
        }
    }
    doc.ok = true;
    return true;
}

// ---- cached load ----------------------------------------------------------
// Returns a COPY of the doc: handing out a const& to a container tree that the
// next compute() may reallocate is not safe on a Maya worker thread.
static NdIoDoc nd_io_load(NdIoCache& c, std::mutex& mtx, const std::string& path,
                          bool raw, char rawKind, int rawSize) {
    char rk[24];
    std::snprintf(rk, sizeof(rk), "|%d%c%d", raw ? 1 : 0, rawKind, rawSize);
    const std::string key = nd_io_stat_key(path) + rk;
    {
        std::lock_guard<std::mutex> lk(mtx);
        if (c.loaded && c.key == key) return c.doc;
    }
    NdIoDoc doc;
    std::vector<char> b;
    if (!path.empty() && nd_io_slurp(path, b)) {
        if (raw) {
            NdIoArray a;
            a.dt = NdIoDtype(rawKind, rawSize);
            const int64_t nEl = (int64_t)(b.size() / (size_t)(rawSize > 0 ? rawSize : 1));
            a.shape.push_back(nEl);
            a.bytes.assign(b.begin(), b.begin() + (size_t)nEl * (size_t)rawSize);
            doc.arrays[""] = a;
            doc.ok = true;
        } else if (!nd_io_parse_npy(b, doc)) {
            NdIoDoc d2;
            if (nd_io_parse_ndio(b, d2)) doc = d2;
            else { NdIoDoc d3; if (nd_io_parse_json(b, d3)) doc = d3; }
        }
    }
    {
        std::lock_guard<std::mutex> lk(mtx);
        c.key = key; c.doc = doc; c.loaded = true;
        return c.doc;
    }
}

// ---- typed accessor -------------------------------------------------------
// ALWAYS returns a well-formed array: a missing key or malformed file yields an
// EMPTY array, never a partially-filled one. Callers downstream (the geo
// writers) size themselves off shape[0], so empty degrades to empty geometry.
template <class T>
static nd::Array<T> nd_io_get(const NdIoDoc& doc, const std::string& name) {
    std::map<std::string, NdIoArray>::const_iterator it = doc.arrays.find(name);
    if (it == doc.arrays.end()) return nd::zeros<T>(nd::Shape{0});
    const NdIoArray& a = it->second;
    const int64_t n = a.count();
    if (n <= 0 || (size_t)(n * a.dt.size) > a.bytes.size())
        return nd::zeros<T>(nd::Shape{0});
    std::vector<T> flat((size_t)n);
    const char* p = a.bytes.data();
    for (int64_t i = 0; i < n; ++i)
        flat[(size_t)i] = (T)nd_io_elem_f(p + i * a.dt.size, a.dt);
    return nd::from_data(flat, a.shape);
}

template <class T>
static nd::Array<T> nd_io_read_raw(NdIoCache& c, std::mutex& mtx,
                                   const std::string& path,
                                   char kind, int size) {
    return nd_io_get<T>(nd_io_load(c, mtx, path, true, kind, size), "");
}

template <class T>
static nd::Array<T> nd_io_read_named(NdIoCache& c, std::mutex& mtx,
                                     const std::string& path,
                                     const std::string& name) {
    return nd_io_get<T>(nd_io_load(c, mtx, path, false, 'f', 8), name);
}

// ---- writers --------------------------------------------------------------
template <class T>
static void nd_io_pack(const nd::Array<T>& a, std::vector<char>& out,
                       char& kind, int& size) {
    nd::Array<T> c = (a.offset != 0 || !a.is_contiguous()) ? a.copy() : a;
    const size_t n = c.data ? c.data->size() : 0;
    kind = (sizeof(T) == 8 && !std::numeric_limits<T>::is_integer) ? 'f'
         : (std::numeric_limits<T>::is_integer ? 'i' : 'f');
    size = (int)sizeof(T);
    // std::vector<bool> is bit-packed and exposes no .data(), so the memcpy
    // below does not compile for T = bool. numpy writes one BYTE per element
    // (np.bool_.itemsize == 1), so unpack explicitly to match .tofile().
    if constexpr (std::is_same<T, bool>::value) {
        out.resize(n);
        for (size_t i = 0; i < n; ++i) out[i] = (char)((*c.data)[i] ? 1 : 0);
        return;
    } else {
        out.resize(n * sizeof(T));
        if (n) std::memcpy(out.data(), c.data->data(), out.size());
    }
}

template <class T>
static bool nd_io_write_raw(const std::string& path, const nd::Array<T>& a) {
    if (path.empty()) return false;
    std::vector<char> buf; char k; int s;
    nd_io_pack(a, buf, k, s);
    std::ofstream fh(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
    if (!fh) return false;
    if (!buf.empty()) fh.write(buf.data(), (std::streamsize)buf.size());
    return fh.good();
}

// numpy's np.save APPENDS ".npy" when the path lacks it. Replicated here so a
// compiled np.save writes the same FILENAME as the interpreted one -- without
// this, `np.save("/tmp/pts", a)` would write /tmp/pts.npy interpreted and
// /tmp/pts compiled, and a downstream reader would find nothing.
static std::string nd_io_npy_path(const std::string& p) {
    if (p.size() >= 4 && p.compare(p.size() - 4, 4, ".npy") == 0) return p;
    return p + ".npy";
}

template <class T>
static bool nd_io_write_npy(const std::string& path, const nd::Array<T>& a) {
    if (path.empty()) return false;
    std::vector<char> buf; char k; int s;
    nd_io_pack(a, buf, k, s);
    std::string shp;
    char tmp[48];
    for (size_t i = 0; i < a.shape.size(); ++i) {
        std::snprintf(tmp, sizeof(tmp), "%lld,", (long long)a.shape[i]);
        shp += tmp;
    }
    if (a.shape.empty()) shp = "0,";
    std::snprintf(tmp, sizeof(tmp), "'<%c%d'", k, s);
    std::string hdr = std::string("{'descr': ") + tmp +
                      ", 'fortran_order': False, 'shape': (" + shp + "), }";
    while ((10 + hdr.size() + 1) % 64) hdr += ' ';   // numpy wants 64B alignment
    hdr += '\n';
    std::ofstream fh(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
    if (!fh) return false;
    const char magic[8] = { '\x93','N','U','M','P','Y','\x01','\x00' };
    fh.write(magic, 8);
    uint16_t hl = (uint16_t)hdr.size();
    fh.write((const char*)&hl, 2);
    fh.write(hdr.data(), (std::streamsize)hdr.size());
    if (!buf.empty()) fh.write(buf.data(), (std::streamsize)buf.size());
    return fh.good();
}

// Incremental NDIO container writer: begin, append N arrays, finish.
struct NdIoWriter {
    std::vector<char> body;
    uint32_t          n = 0;
};

template <class T>
static void nd_io_writer_add(NdIoWriter& w, const std::string& name,
                             const nd::Array<T>& a) {
    std::vector<char> buf; char k; int s;
    nd_io_pack(a, buf, k, s);
    uint16_t nl = (uint16_t)name.size();
    const char* p = (const char*)&nl;
    w.body.insert(w.body.end(), p, p + 2);
    w.body.insert(w.body.end(), name.begin(), name.end());
    w.body.push_back(k);
    w.body.push_back((char)('0' + s));
    w.body.push_back((char)a.shape.size());
    for (size_t i = 0; i < a.shape.size(); ++i) {
        int64_t d = a.shape[i];
        const char* q = (const char*)&d;
        w.body.insert(w.body.end(), q, q + 8);
    }
    uint64_t nb = (uint64_t)buf.size();
    const char* r = (const char*)&nb;
    w.body.insert(w.body.end(), r, r + 8);
    w.body.insert(w.body.end(), buf.begin(), buf.end());
    ++w.n;
}

static bool nd_io_writer_finish(NdIoWriter& w, const std::string& path) {
    if (path.empty()) return false;
    std::ofstream fh(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
    if (!fh) return false;
    fh.write("NDIO\x01", 5);
    fh.write((const char*)&w.n, 4);
    if (!w.body.empty()) fh.write(w.body.data(), (std::streamsize)w.body.size());
    return fh.good();
}
#endif  // ND_IO_KERNEL_INCLUDED
// ===== end nd_io =====
"""
