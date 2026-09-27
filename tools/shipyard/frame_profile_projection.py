"""Consumer-owned, opt-in frame boundaries; no changes to upstream scheduling."""
from prepare_configuration import once
import re


def resource_lookup(source):
    signature='std::shared_ptr<IResource> ResourceManager::LoadResourceProcess(const char* filePath'
    start=source.index(signature)
    end=source.index('\n}',start)+2
    body=source[start:end]
    brace=body.index('{')+1
    body=body[:brace]+'''\n#ifdef _XBOX
    ModernFrameProfile::ResourceLookupScope lookupProfile(mAltAssetsEnabled);
#endif'''+body[brace:]
    pattern=r'(?m)^( +)const auto (altFound|found) = mResourceCache.find\((alternate|key)\);$'
    def probe(match):
        return '#ifdef _XBOX\n'+match[1]+'lookupProfile.Probe();\n#endif\n'+match[0]
    body,count=re.subn(pattern,probe,body)
    if count!=2 or body.count('return resource;')!=2:
        raise ValueError('Resource cache profiling boundary changed')
    body=body.replace('return resource;', '''{
#ifdef _XBOX
                    lookupProfile.Resolved();
#endif
                    return resource;
                }''')
    return source[:start]+body+source[end:]


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


def interpreter(source):
    source='#include "application/frame_profile.h"\n#include "application/command_profile.h"\n'+source
    source=once(source,
        '        gfx->mXboxTextureHashCache.Lookup(hash, fileName, lookupGeneration);',
        '        gfx->mXboxTextureHashCache.Lookup(hash, fileName, lookupGeneration);\n'
        '    if (ModernFrameProfile::CaptureResourceLookups())\n'
        '        ModernFrameProfile::ObserveTextureHashCache(texture != nullptr);')
    source=once(source,
        '                gfx->mXboxTextureHashCache.Lookup(cacheKey, imgData, lookupGeneration);',
        '                gfx->mXboxTextureHashCache.Lookup(cacheKey, imgData, lookupGeneration);\n'
        '            if (ModernFrameProfile::CaptureResourceLookups())\n'
        '                ModernFrameProfile::ObserveTexturePathCache(tex != nullptr);')
    start=source.index('void Interpreter::Run(Gfx* commands,')
    end=source.index('\nvoid Interpreter::EndFrame()',start)
    body=source[start:end]
    body=once(body,'    SpReset();','    ModernFrameProfile::Begin(ModernFrameProfile::InterpreterSetup);\n    SpReset();')
    body=once(body,'    g_exec_stack.start((F3DGfx*)commands);', '''    g_exec_stack.start((F3DGfx*)commands);
    ModernFrameProfile::End(ModernFrameProfile::InterpreterSetup);
    ModernFrameProfile::Begin(ModernFrameProfile::CommandWalk);''')
    body=once(body,'        gfx_step();', '''        if (ModernFrameProfile::commandSampler.enabled) {
            const ModernFrameProfile::CommandSampler::Token sample =
                ModernFrameProfile::commandSampler.Begin(static_cast<unsigned>(cmd->words.w0 >> 24),
                                                          static_cast<unsigned>(ucode_handler_index));
            gfx_step();
            ModernFrameProfile::commandSampler.End(sample);
        } else {
            gfx_step();
        }''')
    body=once(body,'    Flush();', '''    ModernFrameProfile::End(ModernFrameProfile::CommandWalk);
    ModernFrameProfile::Begin(ModernFrameProfile::InterpreterFinish);
    Flush();''')
    # Match the function's final brace, preserving both framebuffer completion paths.
    position=body.rfind('\n}')
    body=body[:position]+'\n    ModernFrameProfile::End(ModernFrameProfile::InterpreterFinish);'+body[position:]
    return source[:start]+body+source[end:]
