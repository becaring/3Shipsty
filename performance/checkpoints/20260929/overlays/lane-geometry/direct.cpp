// Adapted from SoH360/platform/xbox360/fast3d_transform.cpp.
// Recorded donor SHA256: 5f0968d08160776db6c0c501f29e1a79879e5d22860fed2241db93aefdd2c29a.
#include "fast3d/vertex_transform.h"
#include "fast3d/vmx_load.h"

namespace Shipyard {
namespace Fast3D {

static __forceinline __vector4 TransformInvalid(__vector4 bits, __vector4 sign, __vector4 lower,
                                                __vector4 upper, __vector4 zero) {
    const __vector4 magnitude = __vandc(bits, sign);
    return __vor(__vcmpgtuw(magnitude, upper),
                 __vandc(__vcmpgtuw(lower, magnitude), __vcmpequw(magnitude, zero)));
}

// Explicit VMX multiply/add pairs retain the scalar operation order.
#pragma fp_contract(off)
bool CampaignTransformDirect(const void* vertices, size_t count, const float matrix[4][4], void* output,
                        bool normalAspect, size_t outputStride) {
    // VMX flushes subnormals. Integer inputs and bounded coefficients keep
    // nonzero products normal and four-term sums finite; all other matrices
    // retain the scalar path. normalAspect tightens the lower bound.
    static const __declspec(align(16)) uint32_t limits[4][4] = {
        {0x80000000u, 0x80000000u, 0x80000000u, 0x80000000u},
        {0x0c000000u, 0x0c000000u, 0x0c000000u, 0x0c000000u},
        {0x75ffffffu, 0x75ffffffu, 0x75ffffffu, 0x75ffffffu},
        {0x12800000u, 0x12800000u, 0x12800000u, 0x12800000u}};
    const __vector4 sign = __lvx(limits, 0), lower = __lvx(limits, normalAspect ? 48 : 16),
                    upper = __lvx(limits, 32), zero = __vspltisw(0);
    const __vector4 m0 = Detail::LoadUnaligned(matrix[0]), m1 = Detail::LoadUnaligned(matrix[1]);
    const __vector4 m2 = Detail::LoadUnaligned(matrix[2]), m3 = Detail::LoadUnaligned(matrix[3]);
    const __vector4 invalid = __vor(__vor(TransformInvalid(m0, sign, lower, upper, zero),
                                          TransformInvalid(m1, sign, lower, upper, zero)),
                                    __vor(TransformInvalid(m2, sign, lower, upper, zero),
                                          TransformInvalid(m3, sign, lower, upper, zero)));
    unsigned condition;
    __vcmpequwR(invalid, zero, &condition);
    if (!(condition & 0x80))
        return false;
    for (size_t i = 0; i < count; ++i) {
        const __vector4 position =
            __vcfsx(__vupkhsh(Detail::LoadUnaligned((const unsigned char*)vertices + i * 16)), 0);
        const __vector4 x = __vmulfp(__vspltw(position, 0), m0);
        const __vector4 y = __vmulfp(__vspltw(position, 1), m1);
        const __vector4 z = __vmulfp(__vspltw(position, 2), m2);
        const __vector4 result = __vaddfp(__vaddfp(__vaddfp(x, y), z), m3);
        __stvlx(result, output, (int)(i * outputStride));
        __stvrx(result, output, (int)(i * outputStride + 16));
    }
    return true;
}

bool CampaignTransformThree(const void* vertices, size_t count, const float matrix[3][4][4], void* const output[3],size_t outputStride) {
    // VMX flushes subnormals. Integer inputs and bounded coefficients keep
    // nonzero products normal and four-term sums finite; all other matrices
    // retain the scalar path. normalAspect tightens the lower bound.
    static const __declspec(align(16)) uint32_t limits[4][4] = {
        {0x80000000u, 0x80000000u, 0x80000000u, 0x80000000u},
        {0x0c000000u, 0x0c000000u, 0x0c000000u, 0x0c000000u},
        {0x75ffffffu, 0x75ffffffu, 0x75ffffffu, 0x75ffffffu},
        {0x12800000u, 0x12800000u, 0x12800000u, 0x12800000u}};
    const __vector4 sign = __lvx(limits, 0), lower = __lvx(limits, 16),
                    upper = __lvx(limits, 32), zero = __vspltisw(0);
    const __vector4 m00=Detail::LoadUnaligned(matrix[0][0]);
    const __vector4 m01=Detail::LoadUnaligned(matrix[0][1]);
    const __vector4 m02=Detail::LoadUnaligned(matrix[0][2]);
    const __vector4 m03=Detail::LoadUnaligned(matrix[0][3]);
    const __vector4 m10=Detail::LoadUnaligned(matrix[1][0]);
    const __vector4 m11=Detail::LoadUnaligned(matrix[1][1]);
    const __vector4 m12=Detail::LoadUnaligned(matrix[1][2]);
    const __vector4 m13=Detail::LoadUnaligned(matrix[1][3]);
    const __vector4 m20=Detail::LoadUnaligned(matrix[2][0]);
    const __vector4 m21=Detail::LoadUnaligned(matrix[2][1]);
    const __vector4 m22=Detail::LoadUnaligned(matrix[2][2]);
    const __vector4 m23=Detail::LoadUnaligned(matrix[2][3]);
    __vector4 invalid=zero;
    invalid=__vor(invalid,TransformInvalid(m00,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m01,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m02,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m03,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m10,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m11,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m12,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m13,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m20,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m21,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m22,sign,lower,upper,zero));
    invalid=__vor(invalid,TransformInvalid(m23,sign,lower,upper,zero));
    unsigned condition;__vcmpequwR(invalid,zero,&condition);if(!(condition&0x80))return false;
    for (size_t i = 0; i < count; ++i) {
        const __vector4 position =
            __vcfsx(__vupkhsh(Detail::LoadUnaligned((const unsigned char*)vertices + i * 16)), 0);
        const __vector4 px=__vspltw(position,0),py=__vspltw(position,1),pz=__vspltw(position,2);
        const __vector4 r0=__vaddfp(__vaddfp(__vaddfp(__vmulfp(px,m00),__vmulfp(py,m01)),__vmulfp(pz,m02)),m03);
        __stvlx(r0,output[0],int(i*outputStride));__stvrx(r0,output[0],int(i*outputStride+16));
        const __vector4 r1=__vaddfp(__vaddfp(__vaddfp(__vmulfp(px,m10),__vmulfp(py,m11)),__vmulfp(pz,m12)),m13);
        __stvlx(r1,output[1],int(i*outputStride));__stvrx(r1,output[1],int(i*outputStride+16));
        const __vector4 r2=__vaddfp(__vaddfp(__vaddfp(__vmulfp(px,m20),__vmulfp(py,m21)),__vmulfp(pz,m22)),m23);
        __stvlx(r2,output[2],int(i*outputStride));__stvrx(r2,output[2],int(i*outputStride+16));

    }
    return true;
}


// Kept separate from CampaignTransformDirect: a possible callback in that hot
// function forces the Xenon compiler to save VMX registers even when disabled.
bool CampaignTransformDirectProfiled(const void* vertices, size_t count, const float matrix[4][4], void* output,
                                bool normalAspect, size_t outputStride, const TransformPhaseHook* phaseHook) {
    static const __declspec(align(16)) uint32_t limits[4][4] = {
        {0x80000000u, 0x80000000u, 0x80000000u, 0x80000000u},
        {0x0c000000u, 0x0c000000u, 0x0c000000u, 0x0c000000u},
        {0x75ffffffu, 0x75ffffffu, 0x75ffffffu, 0x75ffffffu},
        {0x12800000u, 0x12800000u, 0x12800000u, 0x12800000u}};
    const __vector4 sign = __lvx(limits, 0), lower = __lvx(limits, normalAspect ? 48 : 16),
                    upper = __lvx(limits, 32), zero = __vspltisw(0);
    const __vector4 m0 = Detail::LoadUnaligned(matrix[0]), m1 = Detail::LoadUnaligned(matrix[1]);
    const __vector4 m2 = Detail::LoadUnaligned(matrix[2]), m3 = Detail::LoadUnaligned(matrix[3]);
    const __vector4 invalid = __vor(__vor(TransformInvalid(m0, sign, lower, upper, zero),
                                          TransformInvalid(m1, sign, lower, upper, zero)),
                                    __vor(TransformInvalid(m2, sign, lower, upper, zero),
                                          TransformInvalid(m3, sign, lower, upper, zero)));
    unsigned condition;
    __vcmpequwR(invalid, zero, &condition);
    if (!(condition & 0x80))
        return false;
    phaseHook->enterVertices(phaseHook->context);
    for (size_t i = 0; i < count; ++i) {
        const __vector4 position =
            __vcfsx(__vupkhsh(Detail::LoadUnaligned((const unsigned char*)vertices + i * 16)), 0);
        const __vector4 x = __vmulfp(__vspltw(position, 0), m0);
        const __vector4 y = __vmulfp(__vspltw(position, 1), m1);
        const __vector4 z = __vmulfp(__vspltw(position, 2), m2);
        const __vector4 result = __vaddfp(__vaddfp(__vaddfp(x, y), z), m3);
        __stvlx(result, output, (int)(i * outputStride));
        __stvrx(result, output, (int)(i * outputStride + 16));
    }
    return true;
}

} // namespace Fast3D
} // namespace Shipyard
