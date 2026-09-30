#pragma once

#include <stdint.h>

namespace ModernFast3D {

// Coordinates are the exact U10.2 values passed to GfxDrawRectangle, after
// FILL's inclusive lower/right edge and the existing widescreen expansion.
inline bool FullGameFillCovers(uint32_t nativeWidth, uint32_t nativeHeight,
                              uint32_t targetWidth, uint32_t targetHeight,
                              int32_t ulx, int32_t uly, int32_t lrx, int32_t lry,
                              float scissorX, float scissorY,
                              float scissorWidth, float scissorHeight,
                              uint8_t clip0, uint8_t clip1,
                              uint8_t clip2, uint8_t clip3) {
    if (nativeWidth < 2 || nativeHeight < 2 || targetWidth == 0 || targetHeight == 0 ||
        targetWidth > 16384 || targetHeight > 16384)
        return false;
    // GfxSpTri1 tests these existing reserved-vertex rejection bits even for
    // rectangles. An omitted half would not overwrite the whole target.
    if ((clip0 & clip1 & clip3) || (clip1 & clip2 & clip3))
        return false;
    // SetScissor takes integers. Check the same truncated bounds it will use.
    if (!(scissorX >= -65536.0f && scissorX <= 65536.0f &&
          scissorY >= -65536.0f && scissorY <= 65536.0f &&
          scissorWidth >= 0.0f && scissorWidth <= 65536.0f &&
          scissorHeight >= 0.0f && scissorHeight <= 65536.0f))
        return false;
    const int sx = (int)scissorX, sy = (int)scissorY;
    const int sw = (int)scissorWidth, sh = (int)scissorHeight;
    if (sx > 0 || sy > 0 || sx + sw < (int)targetWidth ||
        sy + sh < (int)targetHeight)
        return false;

    // Match GfxDrawRectangle and AdjXForAspectRatio's operation order. Its
    // default rectangle viewport is the entire separate game framebuffer.
    const float targetAspect = (float)targetWidth / (float)targetHeight;
    const float left = ((ulx / (4.0f * (nativeWidth / 2)) - 1.0f) *
                        (4.0f / 3.0f)) / targetAspect;
    const float right = ((lrx / (4.0f * (nativeWidth / 2)) - 1.0f) *
                         (4.0f / 3.0f)) / targetAspect;
    const float top = -(uly / (4.0f * (nativeHeight / 2))) + 1.0f;
    const float bottom = -(lry / (4.0f * (nativeHeight / 2))) + 1.0f;
    return left <= -1.0f && right >= 1.0f && top >= 1.0f && bottom <= -1.0f;
}

} // namespace ModernFast3D
