#pragma once
#include <array>
#include <string>
#include <vector>
#include "soh-ui/value_init.h"
#include "binary/compat.h"
#include "resources/runtime_support.h"

namespace Shipyard { namespace RandomizerOptions {
inline std::vector<std::string> StringOptions(const char* first, const char* second) {
    const std::string values[] = { first, second };
    return std::vector<std::string>(values, values + 2);
}
// The upstream std::array DMI is {}, which value-initializes every element.
// Fill the already constructed actual array in place, avoiding a large returned
// array on the Xenon stack. This runs before the original Settings ctor body.
template<class T, size_t N> void ValueInitializeArray(std::array<T,N>& values) {
    for (size_t i=0;i<N;++i) values[i]=T(Shipyard::SohUI::ValueInit());
}
} }
