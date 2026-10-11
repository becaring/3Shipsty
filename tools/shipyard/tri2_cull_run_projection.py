"""Certify unchanged cull inputs and rounding only inside adjacent TRI2 runs.

Reconciliation and Flush invalidate before renderer callbacks; vertex writes,
state changes, debugger steps, and display-list branches terminate the run.
Apply after the UnitColor rounding projection has exposed the shared token.
"""


def _once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Modern TRI2 cull run anchor changed: ' + old[:100])
    return source.replace(old, new, 1)


def transform(source):
    if '// MODERN TRI2 CULL RUN BEGIN' in source:
        return source
    source = _once(source, '#include "application/command_profile.h"\n',
                   '#include "application/command_profile.h"\n'
                   '#include "fast3d/tri2_cull_run.h"\n'
                   'static __declspec(thread) ModernTri2CullRunCache sModernTri2CullRun;\n')
    for signature in ('void Interpreter::Flush() {',
                      '__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {'):
        source = _once(source, signature, signature + '\n    sModernTri2CullRun.Reset();')
    reset = '            owner->mXboxPairPacked.Reset();'
    if source.count(reset) != 2:
        raise ValueError('Modern TRI2 run scope boundaries changed')
    source = source.replace(reset, reset + '\n            sModernTri2CullRun.Reset();')
    start = source.index('void Interpreter::GfxSpTri1(')
    end = source.index('\n}', start)
    cull = source[start:end]
    cull = _once(cull,
                 '    const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();',
                 '''    // MODERN TRI2 CULL RUN BEGIN
    uint32_t projectionRounding;
    if (mXboxTrianglePairActive) {
        if (!sModernTri2CullRun.roundingValid) {
            sModernTri2CullRun.rounding = Shipyard::Fast3D::ProjectionRoundingMode();
            sModernTri2CullRun.roundingValid = true;
        }
        projectionRounding = sModernTri2CullRun.rounding;
    } else {
        projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();
    }
    // MODERN TRI2 CULL RUN END''')
    loads = '\n'.join(
        f'        p{i}.Load(v{i}->x, v{i}->y, v{i}->w, projectionRounding);' for i in (1, 2, 3))
    cached = '\n'.join(
        f'            if (!sModernTri2CullRun.Contains(vtx{i}_idx))\n'
        f'                sModernTri2CullRun.Load(vtx{i}_idx, p{i}, *v{i}, projectionRounding);'
        for i in (1, 2, 3))
    cull = _once(cull, loads,
                 '        if (mXboxTrianglePairActive) {\n' + cached + '\n'
                 '        } else {\n' + loads + '\n        }')
    return source[:start] + cull + source[end:]
