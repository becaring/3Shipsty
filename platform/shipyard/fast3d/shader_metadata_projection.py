"""Bind Modern's shader-state block to the shared immutable metadata cache.

Clip parameters and shader failure behavior retain Modern's current policy.
The cache is invalidated after every backend Init, even at the same address.
"""


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Modern shader metadata boundary changed: ' + old[:80])
    return text.replace(old, new, 1)


def header(text):
    text = '#include "fast3d/shader_metadata_cache.h"\n' + text
    return once(text, '    struct ShaderProgram* prg[16];',
                '    struct ShaderProgram* prg[16];\n'
                '    Shipyard::Fast3D::ShaderMetadataCache<16> xboxShaderMetadata;')


def transform(text):
    text = once(text, '    mRapi->Init();', '''    mRapi->Init();
    for (std::map<ColorCombinerKey, ColorCombiner>::iterator entry = mColorCombinerPool.begin();
         entry != mColorCombinerPool.end(); ++entry) {
        entry->second.xboxShaderMetadata.Invalidate();
    }''')
    return once(text, '''    mRapi->ShaderGetInfo(prg, &numInputs, usedTextures);

    struct GfxClipParameters clip_parameters = mRapi->GetClipParameters();''',
                '''    Shipyard::Fast3D::ShaderMetadata xboxMetadata;
    if (!comb->xboxShaderMetadata.Lookup(tm, mRapi, prg, xboxMetadata)) {
        mRapi->ShaderGetInfo(prg, &xboxMetadata.numInputs, xboxMetadata.usedTextures);
        comb->xboxShaderMetadata.Store(tm, mRapi, prg, xboxMetadata);
    }
    numInputs = xboxMetadata.numInputs;
    usedTextures[0] = xboxMetadata.usedTextures[0];
    usedTextures[1] = xboxMetadata.usedTextures[1];

    struct GfxClipParameters clip_parameters = mRapi->GetClipParameters();''')
