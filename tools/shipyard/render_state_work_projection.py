"""Avoid debugger path writes and redundant tile imports in normal rendering.

Debug path policy follows Run's debugger snapshot and is restored on exit.
Tile equality still requires the full import certificate after invalidation.
"""

from prepare_configuration import once


def transform(source):
    source = once(source, 'void GfxExecStack::start(F3DGfx* dlist) {', '''static __declspec(thread) bool sXboxTrackGfxPath = true;
struct XboxGfxPathScope {
    bool previous;
    explicit XboxGfxPathScope(bool enabled) : previous(sXboxTrackGfxPath) {
        sXboxTrackGfxPath = enabled;
    }
    ~XboxGfxPathScope() { sXboxTrackGfxPath = previous; }
};

void GfxExecStack::start(F3DGfx* dlist) {''')
    if source.count('    gfx_path.push_back(caller);') != 2:
        raise ValueError('Display-list debug path writers changed')
    source = source.replace('    gfx_path.push_back(caller);',
                            '    if (sXboxTrackGfxPath) gfx_path.push_back(caller);')
    source = once(source, '    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);',
                  '    XboxGfxPathScope gfxPathScope(xboxDebugging);\n'
                  '    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);')
    source = once(source, '''    mXboxTileTrialEnabled =
        CVarGetInteger("gSettings.XboxTileStateDedupTrialProfile", 0) != 0;''',
                  '    mXboxTileTrialEnabled = true;')
    if source.count('    const bool xboxTileTrial = mXboxTileTrialEnabled;') != 2:
        raise ValueError('Tile import policy changed')
    return source.replace('    const bool xboxTileTrial = mXboxTileTrialEnabled;',
                          '    const bool xboxTileTrial = true;')
