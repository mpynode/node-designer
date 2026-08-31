"""Baked hex-attr transcode C++ snippets."""
from __future__ import annotations



_HEX_CORE_CPP = r"""// ---- hex attr transcode core (Maya-free; parity-tested vs _api2/helpers.py) --
// encode: " ".join("%02x" % b for b in str(value).encode("utf-8"))   (None -> "")
// decode: bytes.fromhex(raw.replace(" ","")).decode("utf-8","replace")
//         empty / all-whitespace -> "";  any parse failure -> raw unchanged.
// A successfully-parsed byte string is re-encoded exactly like CPython's
// "replace" handler: one U+FFFD (EF BF BD) per maximal ill-formed subpart
// (nd_utf8_replace, Unicode Table 3-7 ranges). Valid UTF-8 -- which is all the
// codec ever writes -- passes through byte-for-byte, so a codec round-trip is
// identical whether interpreted or compiled.
static std::string nd_hex_encode_str(const std::string& s) {
    static const char* H = "0123456789abcdef";
    std::string out;
    if (!s.empty()) out.reserve(s.size() * 3 - 1);
    for (std::size_t i = 0; i < s.size(); ++i) {
        if (i) out.push_back(' ');
        unsigned char b = static_cast<unsigned char>(s[i]);
        out.push_back(H[(b >> 4) & 0xF]);
        out.push_back(H[b & 0xF]);
    }
    return out;
}
static int nd_hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static std::string nd_utf8_replace(const std::string& s) {
    // Re-encode `s` as valid UTF-8 exactly like Python str.decode("utf-8",
    // "replace"): substitute one U+FFFD (EF BF BD) per MAXIMAL ill-formed subpart
    // (Unicode 3.9 / Table 3-7 well-formed byte ranges), then resume at the first
    // byte not part of that subpart. Valid UTF-8 (incl. interior NUL = U+0000)
    // is copied through unchanged.
    static const char R0 = (char)0xEF, R1 = (char)0xBF, R2 = (char)0xBD;
    std::string out;
    out.reserve(s.size());
    std::size_t i = 0, n = s.size();
    while (i < n) {
        unsigned char b0 = (unsigned char)s[i];
        if (b0 < 0x80) { out.push_back((char)b0); i += 1; continue; } // ASCII
        std::size_t need = 0;                 // # continuation bytes expected
        unsigned char lo2 = 0x80, hi2 = 0xBF; // allowed range of the 2nd byte
        if (b0 >= 0xC2 && b0 <= 0xDF)      { need = 1; }
        else if (b0 == 0xE0)               { need = 2; lo2 = 0xA0; }
        else if (b0 >= 0xE1 && b0 <= 0xEC) { need = 2; }
        else if (b0 == 0xED)               { need = 2; hi2 = 0x9F; }
        else if (b0 >= 0xEE && b0 <= 0xEF) { need = 2; }
        else if (b0 == 0xF0)               { need = 3; lo2 = 0x90; }
        else if (b0 >= 0xF1 && b0 <= 0xF3) { need = 3; }
        else if (b0 == 0xF4)               { need = 3; hi2 = 0x8F; }
        else {                                // C0,C1,80..BF,F5..FF: invalid lead
            out.push_back(R0); out.push_back(R1); out.push_back(R2);
            i += 1;
            continue;
        }
        std::size_t consumed = 1;             // lead + the valid continuations
        bool ok = true;
        for (std::size_t k = 0; k < need; ++k) {
            std::size_t j = i + 1 + k;
            if (j >= n) { ok = false; break; }            // truncated
            unsigned char bc = (unsigned char)s[j];
            unsigned char lo = (k == 0) ? lo2 : 0x80;
            unsigned char hi = (k == 0) ? hi2 : 0xBF;
            if (bc < lo || bc > hi) { ok = false; break; } // out of range
            consumed += 1;
        }
        if (ok) {
            for (std::size_t k = 0; k < consumed; ++k) out.push_back(s[i + k]);
            i += consumed;
        } else {
            out.push_back(R0); out.push_back(R1); out.push_back(R2);
            i += consumed;                    // skip the maximal ill-formed subpart
        }
    }
    return out;
}
static std::string nd_hex_decode_str(const std::string& s) {
    // Step 1: drop ASCII spaces (0x20) -- Python raw.replace(" ", "").
    std::string r;
    r.reserve(s.size());
    for (std::size_t i = 0; i < s.size(); ++i)
        if (s[i] != ' ') r.push_back(s[i]);
    // Step 2: mirror bytes.fromhex(r): skip the remaining ASCII whitespace only
    // BETWEEN byte pairs (never within a pair), two hex nibbles per byte.
    std::string out;
    out.reserve(r.size() / 2);
    std::size_t i = 0, n = r.size();
    while (i < n) {
        unsigned char c = static_cast<unsigned char>(r[i]);
        if (c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v') {
            ++i;
            continue;
        }
        if (i + 1 >= n) return s;                 // trailing single nibble -> raw
        int hi = nd_hex_nibble(r[i]);
        int lo = nd_hex_nibble(r[i + 1]);
        if (hi < 0 || lo < 0) return s;           // non-hex digit -> raw
        out.push_back(static_cast<char>((hi << 4) | lo));
        i += 2;
    }
    return nd_utf8_replace(out);                  // empty / all-ws -> ""; else UTF-8-replace
}
"""

_HEX_MSTRING_CPP = r"""// ---- hex attr transcode MString adapters (used by the generated node) -------
// asChar() returns a NUL-terminated const char*, and the MString(const char*)
// ctor reads up to the first NUL -- so an interior NUL byte (U+0000, which IS
// valid UTF-8) would be clipped here. That path is unreachable: the hex codec
// only decodes what it encoded, and Maya's api2 MDataHandle::setString itself
// rejects an embedded NUL, so a hex attr never carries one. The Maya-free core
// (nd_hex_decode_str / nd_utf8_replace) DOES preserve interior NULs; only these
// thin MString adapters clip them.
static MString nd_hex_encode(const MString& s) {
    std::string out = nd_hex_encode_str(std::string(s.asChar()));
    return MString(out.c_str());
}
static MString nd_hex_decode(const MString& s) {
    std::string out = nd_hex_decode_str(std::string(s.asChar()));
    return MString(out.c_str());
}
"""

_HEX_CPP = _HEX_CORE_CPP + "\n" + _HEX_MSTRING_CPP
