"""Sparse, opt-in timing of the OTR vertex-hash command and its vertex load."""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern vertex-hash profile anchor changed: ' + old[:100])
    return source.replace(old, new, 1)


def _method(source, signature, edits):
    start = source.index(signature)
    end = source.index('\n}', start)
    body = source[start:end]
    for old, new in edits:
        body = _once(body, old, new)
    return source[:start] + body + source[end:]


def transform(source):
    if '// MODERN VTX HASH PHASE PROFILE BEGIN' in source:
        return source
    source = _once(source, 'bool Interpreter::XboxTryDeferVertices(',
                   '// MODERN VTX HASH PHASE PROFILE BEGIN\n'
                   'static __declspec(thread) ModernFrameProfile::VtxHashSample* '
                   'sModernVtxHashSample = NULL;\n'
                   '// MODERN VTX HASH PHASE PROFILE END\n\n'
                   'bool Interpreter::XboxTryDeferVertices(')
    source = _method(source, 'bool gfx_vtx_hash_handler_custom(F3DGfx** cmd0) {', [
        ('    Interpreter* gfx = XboxDispatchInterpreter();',
         '''    Interpreter* gfx = XboxDispatchInterpreter();
    ModernFrameProfile::VtxHashSample sample;
    ModernFrameProfile::BeginVtxHash(sample);
    struct ProfileScope {
        ModernFrameProfile::VtxHashSample* previous;
        ModernFrameProfile::VtxHashSample& sample;
        explicit ProfileScope(ModernFrameProfile::VtxHashSample& value)
            : previous(NULL), sample(value) {
            if (sample.sampled) {
                previous = sModernVtxHashSample;
                sModernVtxHashSample = &sample;
            }
        }
        ~ProfileScope() {
            if (sample.sampled) sModernVtxHashSample = previous;
            ModernFrameProfile::EndVtxHash(sample);
        }
    } profileScope(sample);'''),
        ('    if (offset > 0xFFFFF) {',
         '    if (offset > 0xFFFFF) {\n'
         '        if (sample.sampled) sample.route = ModernFrameProfile::VtxHashPointer;'),
        ('        F3DVtx* vtx = (F3DVtx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);',
         '        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashLookup);\n'
         '        F3DVtx* vtx = (F3DVtx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);\n'
         '        if (sample.sampled) sample.route = vtx ? ModernFrameProfile::VtxHashResolved : ModernFrameProfile::VtxHashMissing;'),
        ('        gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), (F3DVtx*)offset);',
         '        gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), (F3DVtx*)offset);\n'
         '        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);'),
        ('            gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), vtx);',
         '            gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), vtx);\n'
         '            ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);'),
    ])
    source = _method(source, 'bool Interpreter::XboxTryDeferVertices(', [
        ('        GfxSpVertex(n_vertices, dest_index, vertices);',
         '        if (sModernVtxHashSample) ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);\n'
         '        GfxSpVertex(n_vertices, dest_index, vertices);'),
        ('    for (size_t i = 0; i < n_vertices; ++i) {\n        XboxDeferredVertex& pending = mXboxDeferredVertices[dest_index + i];',
         '    if (sModernVtxHashSample) {\n'
         '        sModernVtxHashSample->deferred = true;\n'
         '        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashInsert);\n'
         '    }\n'
         '    for (size_t i = 0; i < n_vertices; ++i) {\n        XboxDeferredVertex& pending = mXboxDeferredVertices[dest_index + i];'),
    ])
    source = _method(source, 'void Interpreter::GfxSpVertex(', [
        ('    const bool shipyardVectorPositions = shipyardTransformBatch &&\n'
         '        Shipyard::Fast3D::NearestRounding() &&\n'
         '        Shipyard::Fast3D::TransformPositions(vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed);',
         '''    const bool shipyardVectorEligible = shipyardTransformBatch &&
        Shipyard::Fast3D::NearestRounding();
    Shipyard::Fast3D::TransformPhaseHook shipyardPhaseHook;
    if (shipyardVectorEligible && sModernVtxHashSample) {
        shipyardPhaseHook.enterVertices = ModernFrameProfile::EnterVtxTransformLoop;
        shipyardPhaseHook.context = sModernVtxHashSample;
        ModernFrameProfile::BeginVtxTransform(*sModernVtxHashSample, (unsigned)n_vertices);
    }
    const bool shipyardVectorPositions = shipyardVectorEligible &&
        (sModernVtxHashSample
             ? Shipyard::Fast3D::TransformPositionsProfiled(
                   vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed,
                   false, 16, &shipyardPhaseHook)
             : Shipyard::Fast3D::TransformPositions(
                   vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed));
    if (shipyardVectorEligible && sModernVtxHashSample)
        ModernFrameProfile::EndVtxTransform(*sModernVtxHashSample, shipyardVectorPositions);'''),
        ('    if (XboxTryDeferVertices(n_vertices, dest_index, vertices)) return;',
         '    if (sModernVtxHashSample && !mXboxDeferredReplay)\n'
         '        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashDeferred);\n'
         '    if (XboxTryDeferVertices(n_vertices, dest_index, vertices)) return;\n'
         '    if (sModernVtxHashSample && !mXboxDeferredReplay)\n'
         '        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);'),
        ('    bool shipyardAspectReady = false;',
         '    if (sModernVtxHashSample) sModernVtxHashSample->vmx = shipyardVectorPositions;\n'
         '    bool shipyardAspectReady = false;'),
    ])
    return source
