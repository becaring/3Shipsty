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
};
