"""Adapt current 9.x Fast3D reconciliation to Shipyard's triangle certificate."""

import re
from xbox360_platform.fast3d_triangle_certificate import call_end, invalidate_native_calls


BEGIN = '    bool depth_test = (mRsp->geometry_mode & G_ZBUFFER) == G_ZBUFFER;'
END = '    float* shipyardVertexOutput = mBufVbo + mBufVboLen;'


def remove_invalidations(text):
    matches = list(re.finditer(r'\((?:gfx->)?mXboxPipelineKey\.valid=false, (?:gfx->)?mRapi->\w+\(', text))
    for match in reversed(matches):
        end = call_end(text, match.end() - 1)
        if text[end + 1] != ')':
            raise ValueError('Changed native invalidation expression')
        call = text[match.start():match.end()].split(', ', 1)[1]
        text = text[:end + 1] + text[end + 2:]
        text = text[:match.start()] + call + text[match.end():]
    return text


def transform(text):
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError('Modern triangle reconciliation boundary changed')
    start = text.index(BEGIN)
    end = text.index(END, start)
    cold = text[start:end]
    if any(token in cold for token in ('v_arr', 'v1->', 'v2->', 'v3->', 'is_rect')):
        raise ValueError('Per-triangle geometry entered reconciliation')
    publish = '''    XboxTrianglePipelineResult& p=mXboxPipelineResult;
    p.comb=comb;p.ccId=cc_id;p.tm=tm;
    p.alpha=use_alpha;p.fog=use_fog;p.grayscale=use_grayscale;
    p.blendColor=false;p.redirect=false;p.numInputs=numInputs;p.clip=clip_parameters;
    for(unsigned i=0;i<2;++i) {
        p.usedTextures[i]=usedTextures[i];
        p.effectiveTile[i]=mRdp->first_tile_index+i;
        if(comb->usedTextures[i]) {
            p.width[i]=tex_width[i];p.height[i]=tex_height[i];
            p.boundWidth[i]=tex_width2[i];p.boundHeight[i]=tex_height2[i];
        } else {
            p.width[i]=p.height[i]=p.boundWidth[i]=p.boundHeight[i]=0;
        }
        p.widthFloat[i]=p.heightFloat[i]=p.boundWidthFloat[i]=p.boundHeightFloat[i]=0;
    }
    mXboxPipelineKey.Capture(*this,p);
}

'''
    method = '''__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {
    mXboxPipelineKey.valid=false;
// SHIPYARD ORIGINAL RECONCILIATION BEGIN
''' + cold + '// SHIPYARD ORIGINAL RECONCILIATION END\n' + publish
    warm = '''    if(!mXboxPipelineKey.Matches(*this))XboxPrepareTrianglePipeline();
    const XboxTrianglePipelineResult& p=mXboxPipelineResult;
    ColorCombiner* comb=p.comb;
    const bool use_alpha=p.alpha;
    const uint32_t tm=p.tm;
    const uint32_t* tex_width=p.width;const uint32_t* tex_height=p.height;
    const uint32_t* tex_width2=p.boundWidth;const uint32_t* tex_height2=p.boundHeight;
    const bool use_fog=p.fog,use_grayscale=p.grayscale;
    const uint8_t numInputs=p.numInputs;
    const bool* usedTextures=p.usedTextures;
    const GfxClipParameters& clip_parameters=p.clip;

'''
    text = text[:start] + warm + text[end:]
    signature = '__declspec(noinline) void Interpreter::XboxEmitTriangle('
    if text.count(signature) != 1:
        raise ValueError('Modern triangle emission boundary changed')
    text = text.replace(signature, method + signature)
    binding = re.compile(r'(?<!\w)(gfx->)?mXboxTextureBindings\.Invalidate\(\);')
    text, count = binding.subn(lambda match: '(' + (match[1] or '') +
                               'mXboxTextureBindings.Invalidate(), ' + (match[1] or '') +
                               'mXboxPipelineKey.valid=false);', text)
    if count != 7:
        raise ValueError('Modern texture-binding invalidation inventory changed')
    return invalidate_native_calls(text, 'mXboxPipelineKey.valid=false', minimum=30)
