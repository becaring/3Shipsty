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


def transform(source):
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
