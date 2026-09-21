#pragma once
#include <stdint.h>
#include <cstddef>
#include <type_traits>

namespace Shipyard { namespace Utils {
// Unevaluated only. Preserves reference, cv qualifiers and raw-array indexing;
// no substitute container or extra storage is introduced.
template<class T> T& unevaluated();
template<class C> struct IndexedValue {
    typedef typename std::remove_reference<decltype(unevaluated<C>()[uint32_t()])>::type type;
};
template<class C> decltype(unevaluated<const C>().size()) size(const C& container) {
    return container.size();
}
template<class T, size_t N> size_t size(const T (&array)[N]) {
    return N;
}
inline uint32_t RotateRight(uint32_t value, uint32_t rotation) {
    const uint32_t shift = rotation & 31;
    return (value >> shift) | (value << ((32 - shift) & 31));
}
uint32_t DeviceRandom();
} }
