"""Sample disjoint phases of Modern's cold Fast3D triangle preparation.

The projector is isolated from the reconciliation owner. Its sampler API is
declared in application/frame_profile.h and implemented in xenos/services.cpp.
"""

METHOD_START = '__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {'
METHOD_END = '__declspec(noinline) void Interpreter::XboxEmitTriangle('
MARKER = '// MODERN PIPELINE PHASE PROFILE BEGIN'

_BEGIN = ('    ' + MARKER + '\n'
          '    ModernFrameProfile::PipelinePreparationSample xboxPrepSample;\n'
          '    ModernFrameProfile::BeginPipelinePreparation(xboxPrepSample);\n')
_GEOMETRY = ('    ModernFrameProfile::AdvancePipelinePreparation('
             'xboxPrepSample, ModernFrameProfile::PipelineGeometrySampler);\n')
_IMPORT_BEGIN = '                ModernFrameProfile::EnterPipelineTextureImport(xboxPrepSample);\n'
_IMPORT_END = '                ModernFrameProfile::ExitPipelineTextureImport(xboxPrepSample);\n'
_SHADER = ('    ModernFrameProfile::AdvancePipelinePreparation('
           'xboxPrepSample, ModernFrameProfile::PipelineShaderTransitions);\n')
_CAPTURE = ('    ModernFrameProfile::AdvancePipelinePreparation('
            'xboxPrepSample, ModernFrameProfile::PipelineFinalCapture);\n')
_END = ('    ModernFrameProfile::EndPipelinePreparation(xboxPrepSample);\n'
        '    // MODERN PIPELINE PHASE PROFILE END\n')
_ADDITIONS = (_BEGIN, _GEOMETRY, _IMPORT_BEGIN, _IMPORT_END, _SHADER, _CAPTURE, _END)


def _split_method(source):
    if source.count(METHOD_START) != 1 or source.count(METHOD_END) != 1:
        raise ValueError('Modern pipeline profile method boundary changed')
    start = source.index(METHOD_START)
    end = source.index(METHOD_END, start)
    return source[:start], source[start:end], source[end:]


def _once(source, anchor, addition, before=False):
    if source.count(anchor) != 1:
        raise ValueError('Modern pipeline profile anchor changed: ' + anchor[:90])
    if before:
        return source.replace(anchor, addition + anchor, 1)
    return source.replace(anchor, anchor + addition, 1)


def transform(source):
    prefix, method, suffix = _split_method(source)
    if MARKER in method:
        return source
    method = _once(method, METHOD_START + '\n', _BEGIN)
    method = _once(method, '    ColorCombiner* comb = LookupOrCreateColorCombiner(key);\n', _GEOMETRY)
    method = _once(method, '            if (mRdp->textures_changed[i]) {\n', _IMPORT_BEGIN)
    method = _once(method, '                mRdp->textures_changed[i] = false;\n', _IMPORT_END)
    method = _once(method, '    struct ShaderProgram* prg = comb->prg[tm];\n', _SHADER, before=True)
    method = _once(method, '    XboxTrianglePipelineResult& p=mXboxPipelineResult;\n', _CAPTURE, before=True)
    method = _once(method, '    mXboxPipelineKey.Capture(*this,p);\n', _END)
    return prefix + method + suffix


def remove_instrumentation(source):
    prefix, method, suffix = _split_method(source)
    if MARKER not in method:
        return source
    for addition in _ADDITIONS:
        if method.count(addition) != 1:
            raise ValueError('Modern pipeline profile instrumentation changed')
        method = method.replace(addition, '', 1)
    return prefix + method + suffix
