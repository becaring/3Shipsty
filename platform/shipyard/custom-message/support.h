#pragma once
#include <string>
#include <cstdio>
#include "resources/runtime_support.h"
namespace Shipyard { namespace CustomMessages {
inline std::string decimal(unsigned int n) {
    char text[32];
#ifdef _XBOX
    _snprintf(text, sizeof(text), "%u", n);
#else
    std::snprintf(text, sizeof(text), "%u", n);
#endif
    return std::string(text);
}
} }
