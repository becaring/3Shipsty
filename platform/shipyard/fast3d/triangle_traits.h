#pragma once

struct XboxTrianglePipelineTraits {
    template<class Owner> static bool ShaderPresent(const Owner& owner) {
        return owner.mRdp->current_shader.enabled;
    }
    template<class Owner> static int64_t ShaderIdentity(const Owner& owner) {
        const ShaderMod& shader = owner.mRdp->current_shader;
        return (int64_t(uint16_t(shader.id)) << 8) | shader.type;
    }
    template<class Owner> static bool Redirect(const Owner&) {
        return false;
    }
    template<class Owner> static GfxClipParameters Clip(const Owner& owner) {
        return owner.mXboxClipParameters;
    }
    template<class Owner> static unsigned EffectiveTile(const Owner& owner, unsigned slot) {
        return unsigned(owner.mRdp->first_tile_index) + slot;
    }
    // ImportTexture keys only on the loaded entry's address, sizes and flags,
    // the render tile, and palette pointers for CI formats; this consumer has
    // no framebuffer-mirror import. An identical reload therefore finds the
    // node already bound, as in the SoH 4.0.5 Xbox renderer.
    template<class Owner> static bool RestoresReloadedTextures(const Owner&) {
        return true;
    }
    // CI import keys use the palette pointers themselves.
    template<class Owner> static const void* PaletteIdentity(const Owner& owner, unsigned half) {
        return owner.mRdp->palettes[half];
    }
};
