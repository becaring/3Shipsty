#pragma once
#include <nlohmann/json.hpp>
#include <iterator>
// Test-host declaration only: XDK std::find does not require these metadata,
// while current MSVC's optimized algorithm selects on iterator_traits. Describe
// the JSON iterator's forward operations; add no implementation.
namespace std {
template<class T> struct iterator_traits<nlohmann::detail::iter_impl<T>> {
    typedef input_iterator_tag iterator_category;
    typedef nlohmann::json value_type;
    typedef ptrdiff_t difference_type;
    typedef T* pointer;
    typedef T& reference;
};
}
