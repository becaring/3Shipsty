"""Modern Xbox columnar triangle packing; the pair-copy path stays unchanged."""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern column pack anchor drift: ' + old[:100])
    return source.replace(old, new, 1)


COLUMN = r'''    // MODERN COLUMN PACK BEGIN
    // Layout and material branches are shared by the three output rows.
    // The paired TRI2 copy path below retains its original byte-copy logic.
    size_t xboxColumnStride = 0;
    size_t xboxTextureOffset[2] = {0, 0};
    size_t xboxFogOffset = 0, xboxGrayOffset = 0, xboxInputOffset = 0;
    if (!xboxPairPackReuse) {
        xboxColumnStride = 4;
        for (int t = 0; t < 2; ++t) {
            if (!usedTextures[t]) continue;
            xboxTextureOffset[t] = xboxColumnStride;
            xboxColumnStride += 2 + unsigned((tm & (1 << (2 * t))) != 0) +
                unsigned((tm & (1 << (2 * t + 1))) != 0);
        }
        xboxFogOffset = use_fog ? xboxColumnStride : 0;
        if (use_fog) xboxColumnStride += 4;
        xboxGrayOffset = use_grayscale ? xboxColumnStride : 0;
        if (use_grayscale) xboxColumnStride += 4;
        xboxInputOffset = xboxColumnStride;
        xboxColumnStride += size_t(numInputs) * (use_alpha ? 4 : 3);
    }
    if (!xboxPairPackReuse && xboxColumnStride <= 32) {
        float* const xboxRows[3] = {
            shipyardVertexOutput,
            shipyardVertexOutput + xboxColumnStride,
            shipyardVertexOutput + 2 * xboxColumnStride
        };
        if (xboxPairPackFirst) {
            for (int i = 0; i < 3; ++i)
                xboxPairStarts[i] = size_t(xboxRows[i] - mBufVbo);
        }
        for (int i = 0; i < 3; ++i) {
            const LoadedVertex& v = *v_arr[i];
            float z = v.z;
            if (clip_parameters.z_is_from_0_to_1) z = (z + v.w) / 2.0f;
            xboxRows[i][0] = v.x;
            xboxRows[i][1] = clip_parameters.invertY ? -v.y : v.y;
            xboxRows[i][2] = z;
            xboxRows[i][3] = v.w;
        }
        const bool xboxHalfTexel = !is_rect &&
            (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
        for (int t = 0; t < 2; ++t) {
            if (!usedTextures[t]) continue;
            size_t offset = xboxTextureOffset[t];
            const auto& tile = mRdp->texture_tile[mRdp->first_tile_index + t];
            for (int i = 0; i < 3; ++i) {
                xboxRows[i][offset] = Shipyard::Fast3D::Coordinate(
                    v_arr[i]->u, tile.shifts, tile.uls, xboxHalfTexel, tex_width[t]);
                xboxRows[i][offset + 1] = Shipyard::Fast3D::Coordinate(
                    v_arr[i]->v, tile.shiftt, tile.ult, xboxHalfTexel, tex_height[t]);
            }
            offset += 2;
            if (tm & (1 << 2 * t)) {
                for (int i = 0; i < 3; ++i) xboxRows[i][offset] = shipyardClampS[t];
                ++offset;
            }
            if (tm & (1 << (2 * t + 1)))
                for (int i = 0; i < 3; ++i) xboxRows[i][offset] = shipyardClampT[t];
        }
        if (use_fog) {
            for (int i = 0; i < 3; ++i) {
                xboxRows[i][xboxFogOffset] = shipyardFog[0];
                xboxRows[i][xboxFogOffset + 1] = shipyardFog[1];
                xboxRows[i][xboxFogOffset + 2] = shipyardFog[2];
                xboxRows[i][xboxFogOffset + 3] =
                    Shipyard::Fast3D::UnitColor(v_arr[i]->color.a);
            }
        }
        if (use_grayscale) {
            for (int i = 0; i < 3; ++i)
                for (int c = 0; c < 4; ++c)
                    xboxRows[i][xboxGrayOffset + c] = shipyardGrayscale[c];
        }
        for (int j = 0; j < numInputs; ++j) {
            for (int k = 0; k < 1 + (use_alpha ? 1 : 0); ++k) {
                const size_t offset = xboxInputOffset + size_t(j) * (use_alpha ? 4 : 3) +
                    (k ? 3 : 0);
                shipyardMaterialInputs[k][j] = xboxRows[0] + offset;
                const unsigned mapping = comb->shader_input_mapping[k][j];
                if (mapping == G_CCMUX_SHADE) {
                    for (int i = 0; i < 3; ++i) {
                        const RGBA& shade = v_arr[i]->color;
                        if (k == 0) {
                            xboxRows[i][offset] = Shipyard::Fast3D::UnitColor(shade.r);
                            xboxRows[i][offset + 1] = Shipyard::Fast3D::UnitColor(shade.g);
                            xboxRows[i][offset + 2] = Shipyard::Fast3D::UnitColor(shade.b);
                        } else {
                            xboxRows[i][offset] = use_fog ? 1.0f :
                                Shipyard::Fast3D::UnitColor(shade.a);
                        }
                    }
                    continue;
                }
                const RGBA* color;
                RGBA tmp;
                switch (mapping) {
                case G_CCMUX_PRIMITIVE: color = &mRdp->prim_color; break;
                case G_CCMUX_ENVIRONMENT: color = &mRdp->env_color; break;
                case G_CCMUX_PRIMITIVE_ALPHA:
                    tmp.r = tmp.g = tmp.b = mRdp->prim_color.a; color = &tmp; break;
                case G_CCMUX_ENV_ALPHA:
                    tmp.r = tmp.g = tmp.b = mRdp->env_color.a; color = &tmp; break;
                case G_CCMUX_PRIM_LOD_FRAC:
                    tmp.r = tmp.g = tmp.b = mRdp->prim_lod_fraction; color = &tmp; break;
                case G_CCMUX_LOD_FRACTION:
                    if (mRdp->other_mode_l & G_TL_LOD) {
                        float distance_frac = (v1->w - 3000.0f) / 3000.0f;
                        if (distance_frac < 0.0f) distance_frac = 0.0f;
                        if (distance_frac > 1.0f) distance_frac = 1.0f;
                        tmp.r = tmp.g = tmp.b = tmp.a = distance_frac * 255.0f;
                    } else {
                        tmp.r = tmp.g = tmp.b = tmp.a = 255.0f;
                    }
                    color = &tmp;
                    break;
                case G_ACMUX_PRIM_LOD_FRAC:
                    tmp.a = mRdp->prim_lod_fraction; color = &tmp; break;
                default:
                    memset(&tmp, 0, sizeof(tmp)); color = &tmp; break;
                }
                if (k == 0) {
                    const float r = Shipyard::Fast3D::UnitColor(color->r);
                    const float g = Shipyard::Fast3D::UnitColor(color->g);
                    const float b = Shipyard::Fast3D::UnitColor(color->b);
                    for (int i = 0; i < 3; ++i) {
                        xboxRows[i][offset] = r;
                        xboxRows[i][offset + 1] = g;
                        xboxRows[i][offset + 2] = b;
                    }
                } else {
                    const float alpha = Shipyard::Fast3D::UnitColor(color->a);
                    for (int i = 0; i < 3; ++i) xboxRows[i][offset] = alpha;
                }
            }
        }
        shipyardVertexOutput += 3 * xboxColumnStride;
    } else {
    // MODERN COLUMN PACK FALLBACK BEGIN'''


def transform(source):
    if '// MODERN COLUMN PACK BEGIN' in source:
        return source
    start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    end = source.index('\n}', start)
    emitter = source[start:end]
    emitter = _once(emitter, '    for (int i = 0; i < 3; i++) {\n        if (xboxPairPackFirst)',
                    COLUMN + '\n    for (int i = 0; i < 3; i++) {\n        if (xboxPairPackFirst)')
    emitter = _once(emitter,
                    '    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);',
                    '    }\n    // MODERN COLUMN PACK END\n'
                    '    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);')
    return source[:start] + emitter + source[end:]
