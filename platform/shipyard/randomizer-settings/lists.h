#pragma once
#include <set>
#include <vector>
#include <utility>
namespace Shipyard { namespace RandomizerSettings {
// Preserve initializer-list evaluation order and owned container values.
template<class T> class Vector {
    std::vector<T> values;
  public:
    explicit Vector(size_t count) { values.reserve(count); }
    Vector& Add(const T& value) { values.push_back(value); return *this; }
    std::vector<T> Take() { return std::move(values); }
};
template<class T> class Set {
    std::set<T> values;
  public:
    Set& Add(const T& value) { values.insert(value); return *this; }
    std::set<T> Take() { return std::move(values); }
};
} }
