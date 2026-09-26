"""Consumer-owned, opt-in frame boundaries; no changes to upstream scheduling."""
from prepare_configuration import once


def application(source):
    source = '#include "application/frame_profile.h"\n' + source
    source = once(source, '    static bool firstFrame = true;', '''    const bool profileFrame = CVarGetInteger(CVAR_SETTING("XboxFrameProfile"), 0) != 0;
    ModernFrameProfile::BeginFrame(profileFrame);
    static bool firstFrame = true;''')
    source = once(source, '    int next_original_frame = fps;', '''    if (profileFrame) ModernFrameProfile::Settings(
        CVarGetInteger(CVAR_SETTING("InterpolationFPS"), 20), fps, original_fps, R_UPDATE_RATE,
        wnd->GetCurrentRefreshRate(), CVarGetInteger(CVAR_LOW_RES_MODE, 0),
        CVarGetInteger(CVAR_PREFIX_ADVANCED_RESOLUTION ".Enabled", 0), CVarGetInteger(CVAR_VSYNC_ENABLED, 1));
    ModernFrameProfile::Begin(ModernFrameProfile::Interpolation);
    int next_original_frame = fps;''')
    source = once(source, '    time -= fps;', '    time -= fps;\n    ModernFrameProfile::End(ModernFrameProfile::Interpolation);')
    source = once(source, '    RunCommands(commands, mtx_replacements);', '''    if (profileFrame) {
        unsigned nonempty = 0, replacements = 0;
        for (const auto& batch : mtx_replacements) {
            if (!batch.empty()) ++nonempty;
            replacements += static_cast<unsigned>(batch.size());
        }
        ModernFrameProfile::Batch(static_cast<unsigned>(mtx_replacements.size()), nonempty, replacements);
    }
    ModernFrameProfile::Begin(ModernFrameProfile::Graphics);
    RunCommands(commands, mtx_replacements);
    ModernFrameProfile::End(ModernFrameProfile::Graphics);''')
    source = once(source, '    last_update_rate = R_UPDATE_RATE;', '    last_update_rate = R_UPDATE_RATE;\n    ModernFrameProfile::Begin(ModernFrameProfile::AudioWait);')
    source = once(source, '    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-audio-complete", false);',
                  '    ModernFrameProfile::End(ModernFrameProfile::AudioWait);\n    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-audio-complete", false);')
    source = once(source, '    // OTRTODO: FIGURE OUT END FRAME POINT', '    ModernFrameProfile::EndFrame();\n    // OTRTODO: FIGURE OUT END FRAME POINT')
    source = once(source, '        int samples_left = AudioPlayer_Buffered();',
                  '        ModernFrameProfile::Begin(ModernFrameProfile::AudioGenerate);\n        int samples_left = AudioPlayer_Buffered();')
    source = once(source, '        AudioPlayer_Play((u8*)audio_buffer,',
                  '        ModernFrameProfile::End(ModernFrameProfile::AudioGenerate);\n        ModernFrameProfile::Begin(ModernFrameProfile::AudioSubmit);\n        AudioPlayer_Play((u8*)audio_buffer,')
    source = once(source, '        audio.processing = false;',
                  '        ModernFrameProfile::End(ModernFrameProfile::AudioSubmit);\n        audio.processing = false;')
    return source


def presentation(source):
    source = '#include "application/frame_profile.h"\n' + source
    begin = source.index('bool Fast3dWindow::DrawAndRunGraphicsCommands(')
    end = source.index('\n}', begin) + 2
    prefix, suffix = source[:begin], source[end:]
    source = source[begin:end]
    source = once(source, '    if (!wnd->IsFrameReady()) {', '''    ModernFrameProfile::Begin(ModernFrameProfile::Readiness);
    const bool ready = wnd->IsFrameReady();
    ModernFrameProfile::End(ModernFrameProfile::Readiness);
    if (!ready) {''')
    for statement, phase in [('gui->StartDraw();', 'GuiStart'),
                             ('mInterpreter->StartFrame();', 'Framebuffer'),
                             ('mInterpreter->Run(commands, mtxReplacements);', 'Interpreter'),
                             ('gui->EndDraw();', 'GuiEnd'), ('mInterpreter->EndFrame();', 'Present')]:
        source = once(source, '    ' + statement,
                      '    ModernFrameProfile::Begin(ModernFrameProfile::' + phase + ');\n    ' + statement +
                      '\n    ModernFrameProfile::End(ModernFrameProfile::' + phase + ');')
    source = once(source, '    // Execute the games gfx commands', '''    ModernFrameProfile::Dimensions(mInterpreter->mCurDimensions.width, mInterpreter->mCurDimensions.height,
        mInterpreter->mGameWindowViewport.width, mInterpreter->mGameWindowViewport.height,
        mInterpreter->mGfxCurrentWindowDimensions.width, mInterpreter->mGfxCurrentWindowDimensions.height,
        mInterpreter->mMsaaLevel, mInterpreter->mCurDimensions.internal_mul);
    // Execute the games gfx commands''')
    return prefix + source + suffix
