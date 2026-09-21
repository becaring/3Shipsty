#pragma once
#include <stdarg.h>
#if defined(_XBOX) || defined(SHIPYARD_TEST_VA_COPY)
// XDK vadefs.h defines va_list as char*. Each cursor is independent; the
// compiler's va_arg macro retains its own Xenon alignment and promotion rules.
namespace Shipyard { inline void CopyVaList(va_list& destination,va_list source){destination=source;} }
#ifndef va_copy
#define va_copy(destination,source) Shipyard::CopyVaList(destination,source)
#endif
#endif
