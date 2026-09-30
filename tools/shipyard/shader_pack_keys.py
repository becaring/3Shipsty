"""Exact Python port of the interpreter's shader-key derivation.

GfxSpTri1 derives combiner options from the RDP other modes, clears unused
alpha combiner fields, calls GenerateCC and ORs the clamp mask (tm) into the
second id. This module reproduces those steps for the offline shader pack;
tests/test_shader_pack.py checks generate_cc against the projected C++.
"""

# gbi.h
G_CCMUX_COMBINED, G_CCMUX_TEXEL0, G_CCMUX_TEXEL1, G_CCMUX_PRIMITIVE = 0, 1, 2, 3
G_CCMUX_SHADE, G_CCMUX_ENVIRONMENT, G_CCMUX_1, G_CCMUX_NOISE = 4, 5, 6, 7
G_CCMUX_COMBINED_ALPHA, G_CCMUX_TEXEL0_ALPHA, G_CCMUX_TEXEL1_ALPHA = 7, 8, 9
G_CCMUX_PRIMITIVE_ALPHA, G_CCMUX_ENV_ALPHA = 10, 12
G_CCMUX_LOD_FRACTION, G_CCMUX_PRIM_LOD_FRAC, G_CCMUX_0 = 13, 14, 31
G_ACMUX_COMBINED, G_ACMUX_TEXEL0, G_ACMUX_TEXEL1, G_ACMUX_PRIMITIVE = 0, 1, 2, 3
G_ACMUX_SHADE, G_ACMUX_ENVIRONMENT, G_ACMUX_1, G_ACMUX_0 = 4, 5, 6, 7
G_TX_MIRROR, G_TX_CLAMP = 1, 2

# interpreter.h
SHADER_0, SHADER_INPUT_1 = 0, 1
SHADER_TEXEL0, SHADER_TEXEL0A, SHADER_TEXEL1, SHADER_TEXEL1A = 8, 9, 10, 11
SHADER_1, SHADER_COMBINED, SHADER_NOISE = 12, 13, 14
OPT_ALPHA, OPT_FOG, OPT_TEXTURE_EDGE, OPT_NOISE = 1 << 0, 1 << 1, 1 << 2, 1 << 3
OPT_2CYC, OPT_ALPHA_THRESHOLD, OPT_INVISIBLE, OPT_GRAYSCALE = 1 << 4, 1 << 5, 1 << 6, 1 << 7
OPT_TEXEL0_CLAMP_S = 1 << 8

# Combined 64-bit other mode (H << 32 | L) bits that feed the options.
CYCLE_SHIFT = 32 + 20
RELEVANT_OTHER_MODE = 0x3 | 0x1000 | (0x3FF << 16) | (0x3 << 30) | (0x3 << CYCLE_SHIFT)
CYCLE_COPY, CYCLE_FILL = 2, 3


def color_comb(a, b, c, d):
    return (a & 0xf) | ((b & 0xf) << 4) | ((c & 0x1f) << 8) | ((d & 7) << 13)


def alpha_comb(a, b, c, d):
    return (a & 7) | ((b & 7) << 3) | ((c & 7) << 6) | ((d & 7) << 9)


def combine_mode(rgb, alpha, rgb2=0, alpha2=0):
    return rgb | (alpha << 16) | (rgb2 << 28) | (alpha2 << 44)


# GfxDpTextureRectangle (copy mode) and GfxDpFillRectangle (fill mode).
COPY_COMBINE = combine_mode(color_comb(0, 0, 0, G_CCMUX_TEXEL0), alpha_comb(0, 0, 0, G_ACMUX_TEXEL0))
FILL_COMBINE = combine_mode(color_comb(0, 0, 0, G_CCMUX_SHADE), alpha_comb(0, 0, 0, G_ACMUX_SHADE))


def cycle_type(other_mode):
    return (other_mode >> CYCLE_SHIFT) & 3


def options(other_mode, grayscale):
    """cc_options and whether alpha is used, from GfxSpTri1 (no custom shader,
    no texture masks or blends: those come only from replacement packs)."""
    l = other_mode & 0xFFFFFFFF
    h = other_mode >> 32
    use_alpha = (((l & (3 << 20)) == (1 << 20) and (l & (3 << 16)) == 0) or
                 ((l & (3 << 22)) == (1 << 22) and (l & (3 << 18)) == 0))
    use_fog = (l >> 30) == 3
    texture_edge = (l & 0x1000) == 0x1000
    use_noise = (l & 3) == 3
    use_2cyc = (h & (3 << 20)) == (1 << 20)
    alpha_threshold = (l & 3) == 1
    invisible = (l & (3 << 24)) == (3 << 24) and (l & (3 << 20)) == (1 << 20)
    if texture_edge:
        if use_alpha:
            alpha_threshold = True
            texture_edge = False
        use_alpha = True
    value = 0
    for flag, bit in ((use_alpha, OPT_ALPHA), (use_fog, OPT_FOG), (texture_edge, OPT_TEXTURE_EDGE),
                      (use_noise, OPT_NOISE), (use_2cyc, OPT_2CYC), (alpha_threshold, OPT_ALPHA_THRESHOLD),
                      (invisible, OPT_INVISIBLE), (grayscale, OPT_GRAYSCALE)):
        if flag:
            value |= bit
    return value, use_alpha


def generate_cc(combine, opts):
    """Interpreter::GenerateCC: returns (shader_id0, shader_id1, used0, used1)."""
    is2 = (opts & OPT_2CYC) != 0
    c = [[[0] * 4 for _ in range(2)] for _ in range(2)]
    used = [False, False]
    for i in range(2):
        if i == 1 and not is2:
            break
        base = i * 28
        rgb_a = (combine >> base) & 0xf
        rgb_b = (combine >> (base + 4)) & 0xf
        rgb_c = (combine >> (base + 8)) & 0x1f
        rgb_d = (combine >> (base + 13)) & 7
        alpha_a = (combine >> (base + 16)) & 7
        alpha_b = (combine >> (base + 19)) & 7
        alpha_c = (combine >> (base + 22)) & 7
        alpha_d = (combine >> (base + 25)) & 7
        if rgb_a >= 8:
            rgb_a = G_CCMUX_0
        if rgb_b >= 8:
            rgb_b = G_CCMUX_0
        if rgb_c >= 16:
            rgb_c = G_CCMUX_0
        if rgb_d == 7:
            rgb_d = G_CCMUX_0
        if rgb_a == rgb_b or rgb_c == G_CCMUX_0:
            rgb_a = rgb_b = rgb_c = G_CCMUX_0
        if alpha_a == alpha_b or alpha_c == G_ACMUX_0:
            alpha_a = alpha_b = alpha_c = G_ACMUX_0
        if i == 1:
            if G_CCMUX_COMBINED not in (rgb_a, rgb_b, rgb_c, rgb_d):
                c[0][0] = [G_CCMUX_0] * 4
            if (rgb_c != G_CCMUX_COMBINED_ALPHA and alpha_a != G_ACMUX_COMBINED and
                    alpha_b != G_ACMUX_COMBINED and alpha_d != G_ACMUX_COMBINED):
                c[0][1] = [G_ACMUX_0] * 4
        c[i][0] = [rgb_a, rgb_b, rgb_c, rgb_d]
        c[i][1] = [alpha_a, alpha_b, alpha_c, alpha_d]
    if not is2:
        c[1][0] = [G_CCMUX_0] * 4
        c[1][1] = [G_ACMUX_0] * 4

    shader_id0 = 0
    inputs = {}
    next_input = SHADER_INPUT_1
    for i in range(2 if is2 else 1):
        for j in range(4):
            mux = c[i][0][j]
            first, second = (0, 1) if i == 0 else (1, 0)
            if mux == G_CCMUX_0:
                val = SHADER_0
            elif mux == G_CCMUX_1:
                val = SHADER_1
            elif mux == G_CCMUX_TEXEL0:
                val = SHADER_TEXEL0
                used[first] = True
            elif mux == G_CCMUX_TEXEL1:
                val = SHADER_TEXEL1
                used[second] = True
            elif mux == G_CCMUX_TEXEL0_ALPHA:
                val = SHADER_TEXEL0A
                used[first] = True
            elif mux == G_CCMUX_TEXEL1_ALPHA:
                val = SHADER_TEXEL1A
                used[second] = True
            elif mux == G_CCMUX_NOISE:
                val = SHADER_NOISE
            elif mux in (G_CCMUX_PRIMITIVE, G_CCMUX_PRIMITIVE_ALPHA, G_CCMUX_PRIM_LOD_FRAC, G_CCMUX_SHADE,
                         G_CCMUX_ENVIRONMENT, G_CCMUX_ENV_ALPHA, G_CCMUX_LOD_FRACTION):
                if mux not in inputs:
                    inputs[mux] = next_input
                    next_input += 1
                val = inputs[mux]
            elif mux == G_CCMUX_COMBINED:
                val = SHADER_COMBINED
            else:
                val = 0
            shader_id0 |= val << (i * 32 + j * 4)
    inputs = {}
    next_input = SHADER_INPUT_1
    for i in range(2):
        for j in range(4):
            mux = c[i][1][j]
            first, second = (0, 1) if i == 0 else (1, 0)
            val = 0
            mapped = None
            if mux == G_ACMUX_0:
                val = SHADER_0
            elif mux == G_ACMUX_TEXEL0:
                val = SHADER_TEXEL0
                used[first] = True
            elif mux == G_ACMUX_TEXEL1:
                val = SHADER_TEXEL1
                used[second] = True
            elif mux == G_ACMUX_COMBINED:  # also G_ACMUX_LOD_FRACTION
                if j != 2:
                    val = SHADER_COMBINED
                else:
                    mapped = G_CCMUX_LOD_FRACTION
            elif mux == G_ACMUX_1:  # also G_ACMUX_PRIM_LOD_FRAC
                if j != 2:
                    val = SHADER_1
                else:
                    mapped = mux
            elif mux in (G_ACMUX_PRIMITIVE, G_ACMUX_SHADE, G_ACMUX_ENVIRONMENT):
                mapped = mux
            if mapped is not None:
                if mapped not in inputs:
                    inputs[mapped] = next_input
                    next_input += 1
                val = inputs[mapped]
            shader_id0 |= val << (i * 32 + 16 + j * 4)
    return shader_id0, opts, used[0], used[1]


def clamp_masks(used, first_tile, tiles):
    """Possible tm values. The runtime also compares texture and tile sizes,
    which are not known offline, so a clamped axis without mirroring yields
    both outcomes. Unknown tile modes likewise yield both."""
    masks = {0}
    for i in range(2):
        if not used[i]:
            continue
        mode = tiles.get((first_tile + i) & 7)
        for axis in range(2):
            bit = 1 << (2 * i + axis)
            if mode is None:
                choices = (0, bit)
            else:
                cm = mode[axis]
                if not cm & G_TX_CLAMP:
                    choices = (0,)
                elif cm & G_TX_MIRROR:
                    choices = (bit,)
                else:
                    choices = (0, bit)
            masks = {m | choice for m in masks for choice in choices}
    return masks


def shader_keys(combine, other_mode, grayscale, first_tile, tiles, kind='tri'):
    """All (shader_id0, shader_id1) the runtime can request for one draw."""
    cycle = cycle_type(other_mode)
    if kind == 'fillrect' and cycle == CYCLE_FILL:
        combine = FILL_COMBINE
    elif kind == 'texrect' and cycle == CYCLE_COPY:
        combine = COPY_COMBINE
    opts, use_alpha = options(other_mode, grayscale)
    if not use_alpha:
        combine &= ~((0xfff << 16) | (0xfff << 44))
    id0, id1, used0, used1 = generate_cc(combine, opts)
    return {(id0, id1 | tm * OPT_TEXEL0_CLAMP_S) for tm in clamp_masks((used0, used1), first_tile, tiles)}
