#pragma once
#include <stdio.h>
#include <stdarg.h>
static __inline int ShipyardSpeechSnprintf(char* buffer,size_t size,const char* format,...){
    int needed;va_list args;va_start(args,format);
#ifdef _XBOX
    needed=_vscprintf(format,args);va_end(args);
    if(size){va_start(args,format);_vsnprintf_s(buffer,size,_TRUNCATE,format,args);va_end(args);}
#else
    needed=vsnprintf(buffer,size,format,args);va_end(args);
#endif
    return needed;
}
