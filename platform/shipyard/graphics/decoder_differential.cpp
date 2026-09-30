// Two independently compiled source views of the *current* decoder: original
// scoped-enum definitions and the XDK definitions, both using its exact body.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include "shader_lower.h"
namespace original {
#include "decoder_original.inc"
}
namespace projected {
#include "decoder_projected.inc"
}

static_assert(sizeof(original::CCFeatures) == sizeof(projected::CCFeatures), "CCFeatures size drift");
static_assert(alignof(original::CCFeatures) == alignof(projected::CCFeatures), "CCFeatures alignment drift");
#define CHECK_MEMBER(member)                                                                                           \
    static_assert(offsetof(original::CCFeatures, member) == offsetof(projected::CCFeatures, member),                   \
                  "CCFeatures offset drift: " #member)
CHECK_MEMBER(c);
CHECK_MEMBER(opt_alpha);
CHECK_MEMBER(opt_fog);
CHECK_MEMBER(opt_texture_edge);
CHECK_MEMBER(opt_noise);
CHECK_MEMBER(opt_2cyc);
CHECK_MEMBER(opt_alpha_threshold);
CHECK_MEMBER(opt_invisible);
CHECK_MEMBER(opt_grayscale);
CHECK_MEMBER(usedTextures);
CHECK_MEMBER(used_masks);
CHECK_MEMBER(used_blend);
CHECK_MEMBER(clamp);
CHECK_MEMBER(numInputs);
CHECK_MEMBER(do_single);
CHECK_MEMBER(do_multiply);
CHECK_MEMBER(do_mix);
CHECK_MEMBER(color_alpha_same);
CHECK_MEMBER(shader_id);
#undef CHECK_MEMBER

int main() {
    uint64_t state = UINT64_C(0x762ae471db8c219f);
    unsigned cases = 0;
    // Every defined option combination, with all 16 combiner nibble values
    // and unrelated upper ID bits exercised. A stable PRNG also tests mixed
    // terms in both cycles. Fields intentionally untouched upstream retain
    // the same sentinel; this does not introduce a decoder initialization fix.
    for (uint32_t options = 0; options < (1u << 17); ++options) {
        for (unsigned nibble = 0; nibble < 16; ++nibble) {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            const uint64_t id0 = (options & 1) ? state : UINT64_C(0x1111111111111111) * nibble;
            const uint32_t id1 = options | (static_cast<uint32_t>(state) & 0xfffe0000u);
            original::CCFeatures a;
            projected::CCFeatures b;
            memset(&a, 0xa5, sizeof(a));
            memset(&b, 0xa5, sizeof(b));
            original::gfx_cc_get_features(id0, id1, &a);
            projected::gfx_cc_get_features(id0, id1, &b);
            if (memcmp(&a, &b, sizeof(a)) != 0) {
                fprintf(stderr, "Decoder mismatch: options=%u nibble=%u\n", options, nibble);
                return 1;
            }
            ++cases;
        }
    }
    std::string lowered, error;
    if (Shipyard_LowerShader("@prism(type='hlsl')", lowered, error) || error.empty()) {
        fprintf(stderr, "Unexpanded Prism input was accepted\n");
        return 2;
    }
    if (Shipyard_LowerShader("Texture2D unsupported;", lowered, error) || error.empty()) {
        fprintf(stderr, "Missing authoritative cbuffer contract was accepted\n");
        return 3;
    }
    printf("PASS %u current-decoder differential cases; CCFeatures size=%zu; original/projected field layout "
           "identical; shader lowerer rejects unexpanded/missing-contract source\n",
           cases, sizeof(original::CCFeatures));
    return 0;
}
