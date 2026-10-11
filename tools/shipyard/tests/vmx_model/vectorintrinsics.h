// Adapted from Smash360/tests/fast3d-xdk/vmx_model/vectorintrinsics.h for
// this Modern composition proof; only the store counter was added.
// Test-only lane model for the imported transform/clip source. This is not a
// production backend or evidence of native execution. Inputs use host layouts;
// stvebx explicitly models Xenon's big-endian byte selector.
#pragma once
#include <stdint.h>
#include <string.h>
#include <cmath>
struct __vector4 { uint32_t u[4]; };
inline float VF(uint32_t bits) { float f;memcpy(&f,&bits,4);return f; }
inline uint32_t VB(float f) { uint32_t bits;memcpy(&bits,&f,4);return bits; }
inline float Flush(float f) { uint32_t b=VB(f);return (b&0x7f800000u)?f:VF(b&0x80000000u); }
inline __vector4 __lvx(const void* p,int offset) { __vector4 r;memcpy(&r,(const char*)p+offset,16);return r; }
inline __vector4 __lvlx(const void* p,int offset) { return __lvx(p,offset); }
inline __vector4 __lvrx(const void*,int) { __vector4 r={{0,0,0,0}};return r; }
extern unsigned shipyard_test_vector_stores;
inline void __stvx(__vector4 v,void* p,int offset) { ++shipyard_test_vector_stores; memcpy((char*)p+offset,&v,16); }
// Partial stores: the left part fills to the next 16-byte boundary, the right part the bytes before it.
inline void __stvlx(__vector4 v,void* p,int offset) {
    ++shipyard_test_vector_stores;
    char* address=(char*)p+offset;
    memcpy(address,&v,16-((uintptr_t)address&15));
}
inline void __stvrx(__vector4 v,void* p,int offset) {
    char* address=(char*)p+offset;
    const unsigned before=(unsigned)((uintptr_t)address&15);
    memcpy(address-before,(const char*)&v+16-before,before);
}
inline void __stvebx(__vector4 v,void* p,int offset) {
    const unsigned selector=(unsigned)((uintptr_t)p+offset)&15;
    *((unsigned char*)p+offset)=(unsigned char)(v.u[selector/4]>>(24-(selector%4)*8));
}
#define V_BINARY(name,expr) inline __vector4 name(__vector4 a,__vector4 b) { __vector4 r;for(int i=0;i<4;++i)r.u[i]=(expr);return r; }
V_BINARY(__vor,a.u[i]|b.u[i])
V_BINARY(__vand,a.u[i]&b.u[i])
V_BINARY(__vandc,a.u[i]&~b.u[i])
V_BINARY(__vxor,a.u[i]^b.u[i])
V_BINARY(__vcmpequw,a.u[i]==b.u[i]?~0u:0u)
V_BINARY(__vcmpgtuw,a.u[i]>b.u[i]?~0u:0u)
V_BINARY(__vcmpgtsw,(int32_t)a.u[i]>(int32_t)b.u[i]?~0u:0u)
V_BINARY(__vsraw,(uint32_t)((int32_t)a.u[i]>>(b.u[i]&31)))
V_BINARY(__vslw,a.u[i]<<(b.u[i]&31))
V_BINARY(__vcmpgtfp,Flush(VF(a.u[i]))>Flush(VF(b.u[i]))?~0u:0u)
V_BINARY(__vcmpeqfp,Flush(VF(a.u[i]))==Flush(VF(b.u[i]))?~0u:0u)
V_BINARY(__vmulfp,VB(Flush(Flush(VF(a.u[i]))*Flush(VF(b.u[i])))))
V_BINARY(__vaddfp,VB(Flush(Flush(VF(a.u[i]))+Flush(VF(b.u[i])))))
#undef V_BINARY
inline __vector4 __vsel(__vector4 a,__vector4 b,__vector4 mask) {
    __vector4 r;for(int i=0;i<4;++i)r.u[i]=(a.u[i]&~mask.u[i])|(b.u[i]&mask.u[i]);return r;
}
inline __vector4 __vspltisw(int v) { __vector4 r;for(int i=0;i<4;++i)r.u[i]=(uint32_t)v;return r; }
inline __vector4 __vspltw(__vector4 v,int lane) { return __vspltisw((int)v.u[lane]); }
inline __vector4 __vpermwi(__vector4 v,int permutation) {
    __vector4 r;for(int i=0;i<4;++i)r.u[i]=v.u[(permutation>>(6-2*i))&3];return r;
}
inline __vector4 __vupkhsh(__vector4 v) {
    int16_t halves[8];memcpy(halves,&v,16);__vector4 r;
    for(int i=0;i<4;++i)r.u[i]=(uint32_t)(int32_t)halves[i];return r;
}
inline __vector4 __vcfsx(__vector4 v,int scale) {
    __vector4 r;for(int i=0;i<4;++i)r.u[i]=VB(std::ldexp((float)(int32_t)v.u[i],-scale));return r;
}
inline __vector4 __vctsxs(__vector4 v,int scale) {
    __vector4 r;for(int i=0;i<4;++i)r.u[i]=(uint32_t)(int32_t)std::ldexp(Flush(VF(v.u[i])),scale);return r;
}
inline __vector4 __vcmpequwR(__vector4 a,__vector4 b,unsigned* condition) {
    __vector4 r=__vcmpequw(a,b);*condition=0x80;
    for(int i=0;i<4;++i)if(!r.u[i])*condition=0;return r;
}
