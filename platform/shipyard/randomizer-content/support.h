#pragma once
#include <vector>
#include <utility>
namespace Shipyard { namespace RandomizerContent {
template<class T> class Values {
    std::vector<T> values;
public:
    explicit Values(size_t count) { values.reserve(count); }
    Values& Add(const T& value) { values.push_back(value); return *this; }
    std::vector<T> Finish() { return std::move(values); }
};
} }
