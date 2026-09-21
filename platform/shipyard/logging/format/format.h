#pragma once
// Explicit compiler dependency: official fmt 4.1.0, not a printf emulation.
// Default binary32/64 formatting uses the hash-locked fmt12 Dragonbox overlay.
// Explicit presentation/precision still has the CRT boundary in README.md.
#ifdef _XBOX
#include <ppcintrinsics.h>
namespace shipyard_fmt {
inline unsigned fmt_clz32(unsigned n) { return _CountLeadingZeros(n); }
inline unsigned fmt_clz64(unsigned __int64 n) {
    const unsigned high = static_cast<unsigned>(n >> 32);
    return high ? fmt_clz32(high) : 32 + fmt_clz32(static_cast<unsigned>(n));
}
}
#define FMT_BUILTIN_CLZ(n) shipyard_fmt::fmt_clz32(n)
#define FMT_BUILTIN_CLZLL(n) shipyard_fmt::fmt_clz64(n)
#endif
#define FMT_USE_WINDOWS_H 0
#define FMT_USE_VARIADIC_TEMPLATES 0
#define FMT_HEADER_ONLY 1
#include <fmt/format.h>
namespace fmt {
// Current callers use fmt::ptr to opt into pointer formatting explicitly.
template <class T> inline const void* ptr(T* value) { return static_cast<const void*>(value); }
inline const void* ptr(const void* value) { return value; }
}
