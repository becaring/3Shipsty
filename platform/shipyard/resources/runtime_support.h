#pragma once
#include <string>
#include <iterator>
#include <cstddef>

namespace Shipyard { namespace Resources {
template<class C, class K> bool contains(const C& container, const K& key) {
    return container.find(key) != container.end();
}
template<class C> typename C::iterator begin(C& value) { return value.begin(); }
template<class C> typename C::iterator end(C& value) { return value.end(); }
template<class C> typename C::const_iterator begin(const C& value) { return value.begin(); }
template<class C> typename C::const_iterator end(const C& value) { return value.end(); }
template<class T, size_t N> T* begin(T (&value)[N]) { return value; }
template<class T, size_t N> T* end(T (&value)[N]) { return value + N; }
inline bool starts_with(const std::string& value, const std::string& prefix) {
    return value.compare(0, prefix.size(), prefix) == 0;
}
} }
