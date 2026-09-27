"""Skip the second pipeline certificate in an unchanged TRI2 command pair."""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern TRI2 pair projection anchor changed: ' + old[:100])
    return source.replace(old, new, 1)


def header(source):
    if 'mXboxTrianglePairActive' in source:
        return source
    return _once(source, '    XboxTrianglePipelineResult mXboxPipelineResult;',
                 '    XboxTrianglePipelineResult mXboxPipelineResult;\n'
                 '    bool mXboxTrianglePairActive;\n'
                 '    bool mXboxTrianglePairPrepared;')


def _pair_transform(source):
    if '// MODERN TRI2 PAIR CERTIFICATE BEGIN' in source:
        return source
    ctor = source.index('Interpreter::Interpreter() :')
    brace = source.index('{', ctor)
    source = source[:brace + 1] + '\n    mXboxTrianglePairActive = false;\n' + \
             '    mXboxTrianglePairPrepared = false;' + source[brace + 1:]
    handler_start = source.index('bool gfx_tri2_handler_f3dex(')
    handler_end = source.index('\n}', handler_start)
    handler = source[handler_start:handler_end]
    handler = _once(handler, '    F3DGfx* cmd = *cmd0;',
                    '''    F3DGfx* cmd = *cmd0;
    // MODERN TRI2 PAIR CERTIFICATE BEGIN
    struct PairScope {
        Interpreter* owner;
        explicit PairScope(Interpreter* p) : owner(p) {
            owner->mXboxTrianglePairActive = true;
            owner->mXboxTrianglePairPrepared = false;
        }
        ~PairScope() {
            owner->mXboxTrianglePairActive = false;
            owner->mXboxTrianglePairPrepared = false;
        }
    } scope(gfx);
    // MODERN TRI2 PAIR CERTIFICATE END''')
    source = source[:handler_start] + handler + source[handler_end:]
    emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    emitter_end = source.index('\n}', emitter_start)
    emitter = source[emitter_start:emitter_end]
    emitter = _once(emitter, 'const bool xboxPipelineHit=mXboxPipelineKey.Matches(*this);',
                    'const bool xboxPipelineHit=(mXboxTrianglePairActive && mXboxTrianglePairPrepared && '
                    'mXboxPipelineKey.valid) || mXboxPipelineKey.Matches(*this);')
    emitter = _once(emitter, '    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();',
                    '    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();\n'
                    '    mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;')
    emitter = _once(emitter, '        Flush();\n    }',
                    '        Flush();\n        mXboxTrianglePairPrepared = false;\n    }')
    return source[:emitter_start] + emitter + source[emitter_end:]


def _phase_profile(source):
    marker = '// MODERN TRI2 PHASE PROFILE BEGIN'
    if marker in source:
        return source
    source = _once(source, 'void Interpreter::GfxSpTri1(',
                   'static __declspec(thread) ModernFrameProfile::Tri2Sample* '
                   'sModernTri2Sample = NULL;\n\n'
                   'void Interpreter::GfxSpTri1(')
    handler_start = source.index('bool gfx_tri2_handler_f3dex(')
    handler_end = source.index('\n}', handler_start)
    handler = source[handler_start:handler_end]
    handler = _once(handler, '        Interpreter* owner;\n',
                    '        Interpreter* owner;\n'
                    '        ModernFrameProfile::Tri2Sample sample;\n'
                    '        ModernFrameProfile::Tri2Sample* previous;\n')
    handler = _once(handler, '        explicit PairScope(Interpreter* p) : owner(p) {',
                    '        explicit PairScope(Interpreter* p) : owner(p) {\n'
                    '            // MODERN TRI2 PHASE PROFILE BEGIN\n'
                    '            previous = sModernTri2Sample;\n'
                    '            ModernFrameProfile::BeginTri2(sample);\n'
                    '            sModernTri2Sample = sample.sampled ? &sample : NULL;')
    handler = _once(handler, '        ~PairScope() {',
                    '        ~PairScope() {\n'
                    '            ModernFrameProfile::EndTri2(sample);\n'
                    '            sModernTri2Sample = previous;\n'
                    '            // MODERN TRI2 PHASE PROFILE END')
    source = source[:handler_start] + handler + source[handler_end:]
    cull_start = source.index('void Interpreter::GfxSpTri1(')
    cull_end = source.index('\n}', cull_start)
    cull = source[cull_start:cull_end]
    cull = _once(cull, '    XboxMaterializeVertex(vtx1_idx);',
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Materialize);\n'
                 '    XboxMaterializeVertex(vtx1_idx);')
    cull = _once(cull, '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);',
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Pipeline);\n'
                 '    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);\n'
                 '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                 '        *sModernTri2Sample, ModernFrameProfile::Tri2Cull);')
    source = source[:cull_start] + cull + source[cull_end:]
    emitter_start = source.index('__declspec(noinline) void Interpreter::XboxEmitTriangle(')
    emitter_end = source.index('\n}', emitter_start)
    emitter = source[emitter_start:emitter_end]
    emitter = _once(emitter, '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;',
                    '    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '        *sModernTri2Sample, ModernFrameProfile::Tri2Pack);\n'
                    '    const XboxTrianglePipelineResult& p=mXboxPipelineResult;')
    emitter = _once(emitter, '        Flush();\n        mXboxTrianglePairPrepared = false;',
                    '        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '            *sModernTri2Sample, ModernFrameProfile::Tri2Flush);\n'
                    '        Flush();\n'
                    '        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(\n'
                    '            *sModernTri2Sample, ModernFrameProfile::Tri2Pack);\n'
                    '        mXboxTrianglePairPrepared = false;')
    return source[:emitter_start] + emitter + source[emitter_end:]


def transform(source):
    return _phase_profile(_pair_transform(source))
