#define SHIPYARD_TEST_VA_COPY
#include "game-interactor/varargs.h"
#include <cassert>
#include <cstdio>
#include <cstdint>
static void check(int marker,...){
    va_list source,one,two;va_start(source,marker);
#ifdef TEST_UPSTREAM
    va_copy(one,source);va_copy(two,source);
#else
    Shipyard::CopyVaList(one,source);Shipyard::CopyVaList(two,source);
#endif
    assert(va_arg(one,int)==-17);assert(va_arg(one,double)==3.5);
    int* value=va_arg(one,int*);assert(*value==91);
    assert(va_arg(one,uint64_t)==0x1122334455667788ULL);
    assert(va_arg(two,int)==-17&&va_arg(source,int)==-17);
    va_end(one);va_end(two);va_end(source);
}
int main(){int value=91;check(0,-17,3.5,&value,0x1122334455667788ULL);puts("Independent variadic cursors preserve promotions, pointers and 64-bit arguments");}
