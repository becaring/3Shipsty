#pragma once
#include <stdio.h>
#include <stdarg.h>
// Preserve C99's full required-length result and bounded NUL termination.
// XDK va_list is a pointer; use independent copies for each consuming CRT call.
static __inline int ShipyardGfxdVsnprintf(char* dst,size_t capacity,const char* format,va_list arguments){
#ifdef _XBOX
    va_list measure=arguments,write=arguments;
    int length=_vscprintf(format,measure);
    if(capacity){int result=_vsnprintf_s(dst,capacity,_TRUNCATE,format,write);(void)result;}
    return length;
#else
    return vsnprintf(dst,capacity,format,arguments);
#endif
}
