#include <stdio.h>
#include <stdarg.h>

#ifndef SHIPYARD_CRT_SNPRINTF
#define SHIPYARD_CRT_SNPRINTF snprintf
#endif

extern "C" int __cdecl SHIPYARD_CRT_SNPRINTF(char* buffer, size_t size, const char* format, ...) {
    va_list args;
    va_start(args, format);
    const int required = _vscprintf(format, args);
    va_end(args);
    if (size != 0) {
        // A separate va_start is necessary on PPC; a traversed va_list cannot
        // portably be reused. _TRUNCATE terminates even a one-byte destination.
        va_start(args, format);
        const int written = _vsnprintf_s(buffer, size, _TRUNCATE, format, args);
        va_end(args);
        // Truncation returns -1 from the secure CRT, but C99 returns the required
        // length. An actual encoding error in either traversal remains failure.
        if (written < 0 && required >= 0 && static_cast<size_t>(required) < size) return written;
    }
    return required;
}
