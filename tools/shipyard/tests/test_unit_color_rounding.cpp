#include <float.h>
#include <stdio.h>
#include <string.h>
#include "fast3d/projection_cache.h"
#include "fast3d/unit_color_rounding.h"

// Volatile operands and noinline ensure the reference executes division
// in the requested mode instead of folding it at compile time.
__declspec(noinline) float Reference(unsigned char color) {
    volatile float numerator = (float)color;
    volatile float denominator = 255.0f;
    return numerator / denominator;
}

int main() {
    const unsigned previous = _controlfp(0, 0);
    const unsigned modes[] = {_RC_NEAR, _RC_DOWN, _RC_UP, _RC_CHOP};
    for (unsigned m = 0; m < 4; ++m) {
        _controlfp(modes[m], _MCW_RC);
        const float* table = Shipyard::Fast3D::UnitColorTable(Shipyard::Fast3D::ProjectionRoundingMode());
        for (unsigned c = 0; c < 256; ++c) {
            const float original = Reference((unsigned char)c);
            if (memcmp(&original, table + c, sizeof(float))) {
                printf("FAIL UnitColor rounding=%u byte=%u\n", m, c);
                _controlfp(previous, _MCW_RC);
                return 1;
            }
        }
    }
    _controlfp(previous, _MCW_RC);
    puts("PASS UnitColor all 256 bytes in all four rounding modes");
    return 0;
}
