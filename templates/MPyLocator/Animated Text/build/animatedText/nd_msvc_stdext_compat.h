// nd_msvc_stdext_compat.h -- force-included (/FI) into every Windows Qt build.
//
// MSVC toolset 14.51 (VS 2026 18.6, _MSC_VER 1951, _MSVC_STL_UPDATE 202604L)
// removed stdext::checked_array_iterator / unchecked_array_iterator and their
// make_* factories from <iterator>; 14.50 (_MSC_VER 1950, STL 202508L) still
// ships them. Maya 2025's Qt 6.5.3 reaches them unconditionally on MSVC:
// qcompilerdetection.h defines QT_MAKE_CHECKED_ARRAY_ITERATOR(x, N) as
// stdext::make_checked_array_iterator(x, size_t(N)), and qvarlengtharray.h
// (lines 379 and 890) expands it, so any TU that includes QVarLengthArray dies
// with C3861/C2065 'stdext'. Qt's own non-MSVC fallback is the identity (x),
// and that is exactly what these two templates return.
//
// Self-gated: on 14.50 and older this header expands to nothing, so those
// toolsets keep the STL's own definitions. Do not lower the gate to 1950 --
// on 14.50 it would redefine a function template the STL still provides.
//
// Found by NAME beside the source file: a bare /FI resolves like
// #include "...", so the build scripts ship a copy next to the .cpp they
// compile. Keep the two together.
#pragma once
#if defined(_MSC_VER) && _MSC_VER >= 1951
#include <cstddef>
namespace stdext {
template <class It>
inline It make_checked_array_iterator(It it, std::size_t, std::size_t = 0) {
    return it;
}
template <class It>
inline It make_unchecked_array_iterator(It it) {
    return it;
}
}  // namespace stdext
#endif
