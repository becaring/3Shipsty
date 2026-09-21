#pragma once
#include <stdio.h>
#include <stdarg.h>

namespace Shipyard { namespace SohResources {
// C99 snprintf boundary for XDK: required length and terminated truncation.
inline int snprintf(char* buffer, size_t size, const char* format, ...) {
    va_list args;
    va_start(args, format);
    int required = _vscprintf(format, args);
    va_end(args);
    if (size) {
        va_start(args, format);
        _vsnprintf_s(buffer, size, _TRUNCATE, format, args);
        va_end(args);
    }
    return required;
}
} }
