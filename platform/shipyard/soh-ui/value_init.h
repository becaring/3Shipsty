#pragma once
#include <libultraship/color.h>
#include "math/color.h"
namespace Shipyard { namespace SohUI {
// Distinguishes upstream empty/value initialization from default initialization
// when XDK requires an explicitly written default constructor.
struct ValueInit {};
inline Color_RGBA8 Rgba8(unsigned char r,unsigned char g,unsigned char b,unsigned char a) {
    Color_RGBA8 value={r,g,b,a};return value;
}
} }
