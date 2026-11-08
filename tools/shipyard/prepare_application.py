"""Generate and compile the pinned OTRGlobals application translation unit.

Generation records source identity; --build records native compilation separately.
Neither step runs the application.
"""

import argparse
import hashlib
import json
import re
import subprocess
import struct
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import includes as enhancement_includes
from prepare_resource_manager import syntax
from prepare_binary import strong_enum
from cpp_ast import PARSER, walk
from prepare_network import value_expressions as network_values
from prepare_soh_ui import common, maps
from prepare_soh_menus import contains

OWN = ROOT / "platform/shipyard/application"
OUT = ROOT / "scratch/application-xdk"


def application_syntax(source):
    source = once(source, "ItemIDtoGetItemIDMap{", "ItemIDtoGetItemIDMap = {")
    source = once(source, "ItemIDtoRandomizerGetMap{", "ItemIDtoRandomizerGetMap = {")
    pattern = r"std::vector<CONTROLLERBUTTONS_T>\((\{[\s\S]*?\})\)"
    match = re.search(pattern, source)
    assert match
    source = source.replace(
        "    auto controlDeck =",
        "    const CONTROLLERBUTTONS_T buttonMasks[]="
        + match[1]
        + ";\n    auto controlDeck =",
        1,
    )
    source = re.sub(
        pattern,
        "std::vector<CONTROLLERBUTTONS_T>(buttonMasks,"
        " buttonMasks+sizeof(buttonMasks)/sizeof(buttonMasks[0]))",
        source,
        count=1,
    )
    source = once(
        source,
        "context->InitResourceManager({ portArchivePath }, {}, 3, true);",
        "context->InitResourceManager(std::vector<std::string>(1,portArchivePath),"
        " std::unordered_set<uint32_t>(), 3, true);",
    )
    source = once(
        source,
        "std::vector<std::shared_ptr<Ship::GuiWindow>>({ sohInputEditorWindow })",
        "std::vector<std::shared_ptr<Ship::GuiWindow>>(1,sohInputEditorWindow)",
    )
    source = once(
        source,
        "context->InitAudio({ .SampleRate = 32000, .SampleLength = 1024, .DesiredBuffered ="
        " 1680 });",
        "Ship::AudioSettings audioSettings; audioSettings.SampleRate=32000;"
        " audioSettings.SampleLength=1024; audioSettings.DesiredBuffered=1680;\n   "
        " context->InitAudio(audioSettings);",
    )
    source, count = re.subn(
        r"std::unordered_set<uint32_t> ValidHashes = (\{[\s\S]*?\});",
        r"const uint32_t validHashValues[]=\1;\n    std::unordered_set<uint32_t>"
        r" ValidHashes(validHashValues,validHashValues+sizeof(validHashValues)/sizeof(validHashValues[0]));",
        source,
    )
    assert count == 1
    source, count = re.subn(
        r"const std::vector<uint32_t> (hira1|hira2|kata1|kata2) = (\{[\s\S]*?\});",
        lambda m: "static const uint32_t " + m[1] + "[] = " + m[2] + ";",
        source,
    )
    assert count == 4
    for name in ("hira1", "hira2", "kata1", "kata2"):
        assert source.count(name + ".begin()") == 2
        assert source.count(name + ".end()") == 2
        source = source.replace(name + ".begin()", name)
        source = source.replace(
            name + ".end()", name + " + sizeof(" + name + ")/sizeof(" + name + "[0])"
        )
    source = re.sub(r"u'(.)'", lambda m: hex(ord(m[1])), source)
    source = once(
        source,
        "for (auto& [key, value] : cvars.items()) {",
        "for (nlohmann::json::iterator it=cvars.begin(); it!=cvars.end(); ++it) {\n           "
        " const std::string key=it.key(); nlohmann::json& value=it.value();",
    )
    source = source.replace("[[unlikely]]", "")
    source = re.sub(
        r"(?<![\w:])(static_pointer_cast|dynamic_pointer_cast)<", r"std::\1<", source
    )
    for kind in ["SAVE", "LOAD"]:
        source = once(
            source,
            "AddRequest({ slot, RequestType::" + kind + " })",
            "AddRequest(SaveStateRequest(slot, RequestType::" + kind + "))",
        )
    source = source.replace("switch (stateReturn)", "switch (stateReturn.GetValue())")
    source = source.replace(
        "mtx_replacements.emplace_back();",
        "mtx_replacements.push_back(std::unordered_map<Mtx*, MtxF>());",
    )
    source = once(
        source,
        "return GET_ITEM_MYSTERY;",
        "const GetItemEntry entry = GET_ITEM_MYSTERY; return entry;",
    )
    source = once(
        source,
        'CVarGetColor24(CVAR_SETTING("LEDPort1Color"), { 255, 255, 255 })',
        'CVarGetColor24(CVAR_SETTING("LEDPort1Color"), Shipyard::GuiCompat::Rgb(255,255,255))',
    )
    source = re.sub(
        r"color = \{([^{};]+)\};", r"color = Shipyard::GuiCompat::Rgb(\1);", source
    )
    source = once(
        source,
        '            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Invalid OTR File",\n          '
        '                           "Attempted to load an invalid OTR file. Try regenerating.",'
        " nullptr);",
        '            Shipyard::Platform::ShowError(L"Invalid OTR File", L"Attempted to load an'
        ' invalid OTR file. Try regenerating.");',
    )
    return common(contains(maps(source)))


def function(text, name):
    matches = [
        n
        for n in walk(PARSER.parse(text.encode()).root_node)
        if n.type == "function_definition"
        and n.child_by_field_name("declarator") is not None
        and n.child_by_field_name("declarator").text.decode().split("(")[0].strip()
        == name
    ]
    if len(matches) != 1:
        raise ValueError("Application function inventory changed: " + name)
    return matches[0]


def platform_source(source):
    source = once(source, '"shipofharkinian.json"', '"config/shipofharkinian.json"')
    # Retain the desktop extraction body behind the explicit PC boundary.
    node = function(source, "OTRGlobals::RunExtract")
    body = node.child_by_field_name("body")
    raw = source.encode()
    start = body.start_byte + 1
    end = body.end_byte - 1
    source = (
        raw[:start]
        + (
            "\n#ifdef _XBOX\n"
            + (OWN / "runtime_preflight.inc").read_text()
            + "\n#else\n"
        ).encode()
        + raw[start:end]
        + b"\n#endif\n"
        + raw[end:]
    ).decode()
    source = once(
        source,
        '#if not defined(__SWITCH__) && not defined(__WIIU__)\n#include "Extractor/Extract.h"',
        "#ifdef _XBOX\n#include <rom/rom.h>\n#include <zapd/extract.h>\n#endif\n"
        "#if !defined(_XBOX) && !defined(__SWITCH__) && !defined(__WIIU__)\n#include"
        ' "Extractor/Extract.h"',
    )
    for include in ("atomic", "optional"):
        source = once(
            source,
            "#include <" + include + ">",
            "#ifndef _XBOX\n#include <" + include + ">\n#endif",
        )
    source = once(source, "#include <filesystem>", '#include "filesystem/filesystem.h"')
    source = once(source, "#include <chrono>", '#include "logging/chrono/chrono.h"')
    source = once(source, "#include <Windows.h>", "#include <xtl.h>")
    source = once(
        source,
        "#include <libultraship/libultraship.h>",
        '''#include "soh/SohGui/UIWidgets.hpp"
#include <ship/resource/archive/O2rArchive.h>
#include <ship/utils/binarytools/MemoryStream.h>
#include <ship/utils/binarytools/BinaryReader.h>
#include <ship/resource/ResourceManager.h>
#include <ship/resource/ResourceLoader.h>
#include <ship/window/gui/GameOverlay.h>
#include <ship/window/gui/IconsFontAwesome4.h>
#include "gui/compat.h"''',
    )
    source = once(
        source,
        "#ifdef __APPLE__\n#include <SDL_scancode.h>\n#else\n#include"
        " <SDL2/SDL_scancode.h>\n#endif",
        "#include <ship/controller/controldevice/controller/mapping/keyboard/KeyboardScancodes.h>",
    )
    clock = function(source, "GetUnixTimestamp")
    raw = source.encode()
    source = (
        raw[: clock.start_byte]
        + clock.text.replace(b"std::chrono::", b"Shipyard::Logging::chrono::")
        + raw[clock.end_byte :]
    ).decode()
    source = source.replace("std::filesystem::", "xbox_compat::filesystem::")
    # IsSubpath and the temporary permission test belong solely to PC extraction.
    for name in ("IsSubpath", "PathTestCleanup"):
        node = function(source, name)
        raw = source.encode()
        source = (
            raw[: node.start_byte]
            + b"#ifndef _XBOX\n"
            + node.text
            + b"\n#endif"
            + raw[node.end_byte :]
        ).decode()
    source = source.replace(
        "std::unique_lock<std::mutex>",
        "Shipyard::Async::unique_lock<Shipyard::Async::mutex>",
    )
    source = once(
        source,
        "audio.thread = std::thread(OTRAudio_Thread);",
        "audio.thread = Shipyard::Async::make_thread_on_processor(OTRAudio_Thread, 2);",
    )
    source = once(
        source,
        "    while (audio.running) {",
        "    while (true) { // running is checked under audio.mutex below. No unlocked cross-thread"
        " read.",
    )
    source = once(
        source,
        "return { INT16_MAX, INT16_MAX, INT16_MAX };",
        "OTRVersion absent = { INT16_MAX, INT16_MAX, INT16_MAX }; return absent;",
    )
    # Stop libultra timer callbacks before Context/game queues can be torn down.
    source = once(
        source,
        "    OTRAudio_Exit();",
        "    OTRAudio_Exit();\n    Shipyard::Libultra::StopTimers();",
    )
    source = once(
        source, "#ifdef ENABLE_REMOTE_CONTROL\n    SDLNet_Init();\n#endif", ""
    )
    source = once(
        source,
        'extern "C" void InitOTR(int argc, char* argv[]) {',
        """extern "C" void InitOTR(int argc, char* argv[]) {
    ShipyardAudioSetProcessor(1u << 3);
    Shipyard::Platform::RecordBootStage("entry", false);
    xbox_compat::filesystem::InitWorkingDirectory("game:/");
    if (SDLNet_Init() != 0) throw std::runtime_error(SDLNet_GetError());
    try { Shipyard::Storage::Mount(); }
    catch (...) { SDLNet_Quit(); throw; }
    Shipyard::Platform::RecordBootStage("mounted", true);
""".rstrip(),
    )
    source = once(
        source,
        "    OTRGlobals::Instance = new OTRGlobals();",
        "    OTRGlobals::Instance = new OTRGlobals();\n   "
        ' Shipyard::Platform::RecordBootStage("constructor-ready", false);',
    )
    source = once(
        source,
        "    OTRGlobals::Instance->RunExtract(argc, argv);",
        "    OTRGlobals::Instance->RunExtract(argc, argv);\n   "
        ' Shipyard::Platform::RecordBootStage("pre-context", true);',
    )
    source = once(
        source,
        "    OTRGlobals::Instance->Initialize();",
        "    OTRGlobals::Instance->Initialize();\n   "
        ' Shipyard::Platform::RecordBootStage("context-ready", false);',
    )
    source = once(
        source,
        "    SaveManager::Instance = new SaveManager();",
        "    SaveManager::Instance = new SaveManager();\n   "
        ' Shipyard::Platform::RecordBootStage("save-worker-ready", false);',
    )
    source = once(
        source,
        "    conf->RunVersionUpdates();",
        '    Shipyard::Platform::RecordBootStage("config-updaters-ready", false);\n   '
        ' conf->RunVersionUpdates();\n    Shipyard::Platform::RecordBootStage("config-ready",'
        " false);\n    // Migration v2 reloads CVars and drops defaults registered before it.\n   "
        " CVarRegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);",
    )
    source = once(
        source,
        "    SohGui::SetupGuiElements();",
        "    SohGui::SetupGuiElements();\n   "
        ' Shipyard::Platform::RecordBootStage("gui-windows-ready", false);',
    )
    source = once(
        source,
        "    SohGui::SetupMenuElements();",
        '    SohGui::SetupMenuElements();\n    Shipyard::Platform::RecordBootStage("gui-ready",'
        " false);",
    )
    source = once(
        source,
        "    SpeechSynthesizer::Instance->Init();",
        "    SpeechSynthesizer::Instance->Init();\n   "
        ' Shipyard::Platform::RecordBootStage("speech-ready", false);',
    )
    # Mod archives and alternate assets load in this stretch; free memory per step shows which one costs it.
    for call, stage in (
        ("    InitMods();", "mods-ready"),
        ("    RegisterImGuiItemIcons();", "item-icons-ready"),
        ("    ShipInit::InitAll();", "ship-init-ready"),
    ):
        source = once(source, call, call + '\n    Shipyard::Platform::RecordBootStage("' + stage + '", false);')
    source = once(
        source,
        "    OTRGlobals::Instance->gRandoContext->AddExcludedOptions();",
        "    OTRGlobals::Instance->gRandoContext->AddExcludedOptions();\n   "
        ' Shipyard::Platform::RecordBootStage("init-complete", false);',
    )
    source = once(
        source,
        "    context->InitLogging(logLevel, logLevel);",
        """    if (!context->InitLogging(logLevel, logLevel)) {
        throw std::runtime_error("Xbox log directory initialization failed");
    }
    Shipyard::Platform::RecordBootStage("logging-ready", false);""",
    )
    source = once(
        source,
        "    context->InitAudio({ .SampleRate = 32000, .SampleLength = 1024, .DesiredBuffered ="
        " 1680 });",
        "    context->InitAudio({ .SampleRate = 32000, .SampleLength = 1024, .DesiredBuffered ="
        ' 1680 });\n    Shipyard::Platform::RecordBootStage("audio-ready", false);',
    )
    source = once(
        source,
        "    gSaveStateMgr = std::make_shared<SaveStateMgr>();",
        '    Shipyard::Platform::RecordBootStage("factories-ready", false);\n    gSaveStateMgr ='
        " std::make_shared<SaveStateMgr>();",
    )
    source = once(
        source,
        "    gRandomizer = std::make_shared<Randomizer>();",
        "    gRandomizer = std::make_shared<Randomizer>();\n   "
        ' Shipyard::Platform::RecordBootStage("randomizer-ready", false);',
    )
    # Record each startup boundary through the first presentation and audio wait, once, on the game thread;
    # never log ongoing frame work.
    source = once(
        source,
        'extern "C" void Graph_ProcessGfxCommands(Gfx* commands) {',
        """extern "C" void Graph_ProcessGfxCommands(Gfx* commands) {
    static bool firstFrame = true;
    const bool traceFirstFrame = firstFrame;
    firstFrame = false;""",
    )
    source = once(
        source,
        "    RunCommands(commands, mtx_replacements);",
        """    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-graphics-begin", false);
    RunCommands(commands, mtx_replacements);
    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-graphics-returned", false);""",
    )
    source = once(
        source,
        '    bool curAltAssets = CVarGetInteger(CVAR_SETTING("AltAssets"), 1);',
        """    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-audio-complete", false);
    bool curAltAssets = CVarGetInteger(CVAR_SETTING("AltAssets"), 1);""",
    )
    source = once(
        source,
        "    int next_original_frame = fps;",
        """    int next_original_frame = fps;
    // The loop emits this many maps before any presentation consumes them.
    if (original_fps > 0 && time + original_fps <= next_original_frame) {
        mtx_replacements.reserve((next_original_frame - time) / original_fps);
    }""",
    )
    # Texture resolutions persist until the resource manager's lookup
    # generation moves, instead of being re-resolved every batch.
    source = once(
        source,
        "    intp->mInterpolationIndex = 0;",
        "    intp->mInterpolationIndex = 0;\n    intp->mXboxTextureHashCache.Retire(\n"
        "        Ship::Context::GetInstance()->GetResourceManager()->GetXboxLookupGeneration());\n"
        "    // A lone replay is also the final one; its depth resolve would copy\n"
        "    // the published depth. Read before it, in submission order.\n"
        "    if (mtx_replacements.size() < 2) XboxRunDeferredDepthRead(intp);",
    )
    source = once(
        source,
        "        wnd->DrawAndRunGraphicsCommands(Commands, m);",
        """        // Only the final render supplies depth to the next game update.
        intp->mXboxDiscardGameDepth =
            static_cast<size_t>(intp->mInterpolationIndex + 1) < mtx_replacements.size();
        wnd->DrawAndRunGraphicsCommands(Commands, m);
        // The update's depth read waits for the previous final replay. Once
        // this first replay is submitted, the GPU has work during that wait.
        if (intp->mInterpolationIndex == 0) XboxRunDeferredDepthRead(intp);""",
    )
    # The depth read sees the previous update's final replay through the
    # backend publication, so its values match the read at task submission.
    source = once(
        source,
        "void RunCommands(Gfx* Commands, const std::vector<std::unordered_map<Mtx*, MtxF>>&"
        " mtx_replacements) {",
        """extern "C" void Graph_RunDeferredCallback(void);

static void XboxRunDeferredDepthRead(Fast::Interpreter* intp) {
    Graph_RunDeferredCallback();
    intp->XboxRetireGameDepth();
}

void RunCommands(Gfx* Commands, const std::vector<std::unordered_map<Mtx*, MtxF>>& mtx_replacements) {""",
    )
    source = once(
        source,
        "    ImGui::PopStyleColor();\n}",
        """    ImGui::PopStyleColor();
    XboxRunDeferredDepthRead(intp); // No replay ran this update.
    // This update's final replay is what the next update's read observes.
    intp->XboxPublishGameDepth();
}""",
    )
    source = once(
        source,
        '    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-graphics-returned",'
        " false);",
        """    if (traceFirstFrame) Shipyard::Platform::RecordBootStage("first-graphics-returned", false);
    Graph_RunDeferredCallback(); // RunCommands had no window.""",
    )
    from frame_profile_projection import application as profile_application

    source = profile_application(source)
    # Retired replay maps return to the pool in interpolation_replay.recycle_maps.
    source = once(
        source,
        "    RunCommands(commands, mtx_replacements);",
        """    RunCommands(commands, mtx_replacements);
    for (size_t i = 0; i < mtx_replacements.size(); ++i)
        FrameInterpolation_Recycle(mtx_replacements[i]);""",
    )
    from overlap_audio_projection import source as overlap_audio_source

    source = overlap_audio_source(source)
    from audio_cpu_projection import application as audio_cpu

    source = audio_cpu(source)
    source = '#include "audio/services.h"\n' + source
    source = once(
        source,
        'extern "C" void Graph_ProcessGfxCommands(Gfx* commands) {',
        '#include "application/overlap_runtime.inc"\n\n'
        'extern "C" void Graph_ProcessGfxCommands(Gfx* commands) {\n'
        "    if (ModernOverlap::PublishCommands(commands)) return;",
    )
    from overlap_lifetime_projection import project as overlap_lifetime

    source = overlap_lifetime("soh/soh/OTRGlobals.cpp", source)
    from overlap_resource_cpu_projection import application as resource_owners

    source = resource_owners(source)
    from overlap_audio_barrier_projection import runtime as audio_barrier

    source = audio_barrier(source)
    from overlap_lifetime_projection import shadow_runtime

    source = shadow_runtime(source)
    from overlap_depth_runtime_projection import runtime as deferred_depth

    source = deferred_depth(source)
    source = (
        '#include "ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.h"\n'
        + source
    )
    source = once(
        source,
        'extern "C" void DeinitOTR() {\n    SaveManager_ThreadPoolWait();',
        'extern "C" void DeinitOTR() {',
    )
    source = once(
        source,
        'extern "C" void SaveManager_ThreadPoolWait() {',
        """// Keep the genuine InitOTR body, but do not let a recoverable Xbox startup
// failure escape through the C game entry before its crash handler exists.
static void Shipyard_ReportStartupFailure(const char* operation, DWORD code, bool hasCode) {
    char message[256];
    if (hasCode) {
        _snprintf_s(message, sizeof(message), _TRUNCATE,
                    "Startup failed: %s (Xbox error %lu)", operation, code);
    } else {
        _snprintf_s(message, sizeof(message), _TRUNCATE,
                    "Startup failed: %s", operation);
    }
    OutputDebugStringA(message);
    OutputDebugStringA("\\n");
    wchar_t wide[256];
    unsigned i = 0;
    for (; i < sizeof(wide) / sizeof(wide[0]) - 1 && message[i]; ++i)
        wide[i] = static_cast<unsigned char>(message[i]);
    wide[i] = 0;
    Shipyard::Platform::RecordStartupFailure(message);
    Shipyard::Platform::ShowError(L"Ship of Harkinian", wide);
}

extern "C" int Shipyard_TryInitOTR(int argc, char* argv[]) {
    try {
        InitOTR(argc, argv);
        return 1;
    } catch (const Shipyard::Async::native_error& error) {
        Shipyard_ReportStartupFailure(error.what(), error.native_code(), true);
    } catch (const std::system_error& error) {
        Shipyard_ReportStartupFailure(error.what(), error.code().value(), true);
    } catch (const std::exception& error) {
        Shipyard_ReportStartupFailure(error.what(), 0, false);
    } catch (...) {
        Shipyard_ReportStartupFailure("unknown native exception", 0, false);
    }
    return 0;
}

extern "C" void SaveManager_ThreadPoolWait() {""",
    )
    source = once(
        source,
        "#ifdef __APPLE__\n    SpeechSynthesizer::Instance = new DarwinSpeechSynthesizer();",
        "#if defined(_XBOX)\n    SpeechSynthesizer::Instance = new XboxSpeechSynthesizer();\n#elif"
        " defined(__APPLE__)\n    SpeechSynthesizer::Instance = new DarwinSpeechSynthesizer();",
    )
    # Generation may still use Context, settings and resources during shutdown.
    # Join before any of those owners or callback consumers are destroyed.
    source = once(
        source,
        'extern "C" void DeinitOTR() {',
        'extern "C" void DeinitOTR() {\n    JoinRandoGenerationThread();',
    )
    # Teardown after Quit left a black screen on hardware. The next title reclaims memory,
    # threads and the GPU, so persist saves, settings and the log, then launch it.
    source = once(
        source,
        'extern "C" void DeinitOTR() {\n    JoinRandoGenerationThread();',
        """extern "C" void DeinitOTR() {
    JoinRandoGenerationThread();
#ifdef _XBOX
    SaveManager_ThreadPoolWait();
    Ship::Context::GetInstance()->GetConsoleVariables()->Save();
    Shipyard::Storage::Shutdown();
    if (auto logger = spdlog::default_logger()) logger->flush();
    Shipyard::Platform::ExitTitle();
#endif""",
    )
    source = once(
        source,
        "    SohGui::Destroy();",
        "    DestroyXboxSpeechSynthesizer(SpeechSynthesizer::Instance);\n   "
        " SpeechSynthesizer::Instance = nullptr;\n    SohGui::Destroy();",
    )
    for remote, cvar in [
        ("CrowdControl", "CROWD_CONTROL"),
        ("Sail", "SAIL"),
        ("Anchor", "ANCHOR"),
    ]:
        # The shutdown condition follows the worker state. A changed CVar
        # cannot strand an enabled worker while its dependencies are destroyed.
        source = once(
            source,
            "if (CVarGetInteger(CVAR_REMOTE_"
            + cvar
            + '("Enabled"), 0)) {\n        '
            + remote
            + "::Instance->Disable();",
            "if ("
            + remote
            + "::Instance && "
            + remote
            + "::Instance->isEnabled) {\n        "
            + remote
            + "::Instance->Disable();",
        )
    source = once(
        source,
        "#ifdef ENABLE_REMOTE_CONTROL\n    SDLNet_Quit();\n#endif",
        "    SaveManager_ThreadPoolWait();\n    delete SaveManager::Instance;\n   "
        " SaveManager::Instance = nullptr;",
    )
    source = once(
        source, "    OTRAudio_Exit();\n    Shipyard::Libultra::StopTimers();\n", ""
    )
    source = once(
        source,
        "    SaveManager_ThreadPoolWait();\n    delete SaveManager::Instance;",
        "    OTRAudio_Exit();\n    Shipyard::Libultra::StopTimers();\n   "
        " SaveManager_ThreadPoolWait();\n    delete SaveManager::Instance;",
    )
    source = once(
        source,
        "    OTRGlobals::Instance->context = nullptr;",
        """    OTRGlobals::Instance->context->GetResourceManager()->WaitForPendingTasks();
    Shipyard::Async::wait_for_detached();
    OTRGlobals::Instance->context = nullptr;
    Shipyard::Storage::Shutdown();
    SDLNet_Quit();""",
    )
    source = network_values(source)
    source = once(
        source,
        "    Extractor::ShowErrorBox(title, body);",
        "    Shipyard::Platform::ShowError(StringToU16(title).c_str(), StringToU16(body).c_str());",
    )
    source = once(
        source,
        'extern "C" void Messagebox_ShowErrorBox',
        'std::wstring StringToU16(const std::string& s);\nextern "C" void Messagebox_ShowErrorBox',
    )
    return (
        '#include "application/archive_preflight.h"\n#include "context/platform.h"\n#include'
        ' "libultra/platform.h"\n#include "network/transport.h"\n#include'
        ' "save-storage/storage.h"\n#include "async/native.h"\n#include'
        ' "async/detached.h"\n#include <exception>\n#include <system_error>\n' + source
    )


ARCHIVE_MOUNTS = """    std::string mqPath = Ship::Context::LocateFileAcrossAppDirs("oot-mq.o2r", appShortName);
    if (std::filesystem::exists(mqPath)) {
        context->GetResourceManager()->GetArchiveManager()->AddArchive(mqPath);
    }
    std::string ootPath = Ship::Context::LocateFileAcrossAppDirs("oot.o2r", appShortName);
    if (std::filesystem::exists(ootPath)) {
        context->GetResourceManager()->GetArchiveManager()->AddArchive(ootPath);
    }
"""


def mount_archives_once(source):
    # Opening an O2R parses its zip directory and hashes every entry. Version
    # checks read the mounted archives instead of opening temporary copies:
    # soh.o2r is checked after InitResourceManager mounts it, and the Xbox
    # preflight (runtime_preflight.inc) mounts the ROM archives Initialize() did.
    version = """    OTRVersion portArchiveVersion = DetectOTRVersion("soh.o2r", false);
    sohArchiveVersionMatch = portArchiveVersion.major == gBuildVersionMajor &&
                             portArchiveVersion.minor == gBuildVersionMinor &&
                             portArchiveVersion.patch == gBuildVersionPatch;
"""
    source = once(source, version, "")
    mount = "    context->InitResourceManager({ portArchivePath }, {}, 3, true);\n"
    source = once(source, mount, mount + version)
    source = once(
        source,
        "void OTRGlobals::Initialize() {\n" + ARCHIVE_MOUNTS,
        "void OTRGlobals::Initialize() {\n#ifndef _XBOX\n" + ARCHIVE_MOUNTS + "#endif\n",
    )
    return once(
        source,
        """    // Use a temporary archive instance to load the otr and read the version file
    auto archive = std::make_shared<Ship::O2rArchive>(otrPath);
    if (archive->Open()) {""",
        """    // Opening an archive indexes every entry; prefer the mounted instance.
    std::shared_ptr<Ship::Archive> archive;
    const auto mounted = Ship::Context::GetInstance()->GetResourceManager()->GetArchiveManager()->GetArchives();
    for (size_t i = 0; i < mounted->size() && !archive; ++i)
        if ((*mounted)[i]->IsLoaded() && (*mounted)[i]->GetPath() == otrPath) archive = (*mounted)[i];
    if (!archive) {
        archive = std::make_shared<Ship::O2rArchive>(otrPath);
        if (!archive->Open()) archive = nullptr;
    }
    if (archive) {""",
    )


def scan_extensions_once(source):
    # Same keys and entries, without copying the archive file list or splitting
    # every path into a vector of parts.
    return once(
        source,
        """    auto lst = *Ship::Context::GetInstance()->GetResourceManager()->GetArchiveManager()->ListFiles().get();

    for (auto& rPath : lst) {
        std::vector<std::string> raw = StringHelper::Split(rPath, ".");
        std::string ext = raw[raw.size() - 1];
        std::string nPath = rPath.substr(0, rPath.size() - (ext.size() + 1));
        replace(nPath.begin(), nPath.end(), '\\\\', '/');

        ExtensionCache[nPath] = { rPath, ext };
    }""",
        """    const auto files = Ship::Context::GetInstance()->GetResourceManager()->GetArchiveManager()->ListFiles();
    ExtensionCache.rehash(files->size());
    for (size_t i = 0; i < files->size(); ++i) {
        const std::string& rPath = (*files)[i];
        const size_t dot = rPath.rfind('.');
        std::string nPath = dot == std::string::npos ? rPath : rPath.substr(0, dot);
        replace(nPath.begin(), nPath.end(), '\\\\', '/');
        ExtensionEntry value;
        value.path = rPath;
        value.ext = dot == std::string::npos ? rPath : rPath.substr(dot + 1);
        ExtensionCache[nPath] = value;
    }""",
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    for name, expected in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("Application source drift " + name)
        texts[name] = text
    header = texts["soh/soh/OTRGlobals.h"]
    source = texts["soh/soh/OTRGlobals.cpp"]
    defaults = re.findall(r"    ImFont\* (\w+) = nullptr;", header)
    if len(defaults) != 8:
        raise ValueError("OTRGlobals font default inventory changed")
    for member in defaults:
        header = once(
            header, "ImFont* " + member + " = nullptr;", "ImFont* " + member + ";"
        )
    header = once(header, '#include "Enhancements/savestates.h"', "class SaveStateMgr;")
    header = once(
        header,
        '#include "Enhancements/randomizer/randomizer.h"',
        "class Randomizer;\nnamespace Rando {class Context;}\nstruct ImFont;",
    )
    header = once(
        header,
        '#include "Enhancements/randomizer/settings.h"',
        "// Only the forward-declared randomizer owner is used by this class declaration.",
    )
    source = once(
        source,
        '#include "OTRGlobals.h"',
        '#include "OTRGlobals.h"\n#include "Enhancements/savestates.h"\n#include'
        ' "Enhancements/randomizer/settings.h"',
    )
    source = once(
        source,
        "OTRGlobals::OTRGlobals() {",
        "OTRGlobals::OTRGlobals() : "
        + ", ".join(member + "(nullptr)" for member in defaults)
        + " {",
    )
    audio = syntax(texts["soh/soh/OTRAudio.h"]).replace(
        "#include <condition_variable>", '#include "async/native.h"'
    )
    audio = audio.replace(
        "std::thread thread", "Shipyard::Async::joining_thread thread"
    ).replace("std::condition_variable", "Shipyard::Async::condition_variable")
    # SaveStateMgr locks this same state from another translation unit. The
    # upstream header's internal-linkage instance silently gives it another lock.
    audio = once(audio, "static struct {", "struct OTRAudioState {")
    audio = once(audio, "} audio;", "};\nextern OTRAudioState audio;")
    from overlap_audio_projection import header as overlap_audio_header

    audio = overlap_audio_header(audio)
    source = once(
        source,
        "OTRGlobals* OTRGlobals::Instance;",
        "OTRAudioState audio;\nOTRGlobals* OTRGlobals::Instance;",
    )
    stable(OUT / "generated/soh/soh/OTRAudio.h", audio)
    states = syntax(texts["soh/soh/Enhancements/savestates.h"])
    states = re.sub(
        r"enum class (SaveStateReturn|RequestType) \{(.*?)\};",
        lambda m: strong_enum(m[1], m[2]),
        states,
        flags=re.S,
    )
    states = once(
        states,
        "typedef struct SaveStateRequest {",
        "typedef struct SaveStateRequest {\n    SaveStateRequest() {}\n   "
        " SaveStateRequest(unsigned int slot_, RequestType type_) : slot(slot_), type(type_) {}",
    )
    states = once(
        states,
        "    SaveStateMgr& operator=(const SaveStateMgr& rhs) = delete;\n    SaveStateMgr(const"
        " SaveStateMgr& rhs) = delete;",
        "  private:\n    SaveStateMgr& operator=(const SaveStateMgr& rhs);\n    SaveStateMgr(const"
        " SaveStateMgr& rhs);\n  public:",
    )
    states = '#include "binary/compat.h"\n' + states
    stable(OUT / "generated/soh/soh/Enhancements/savestates.h", states)
    stable(OUT / "generated/soh/soh/OTRGlobals.h", header)
    # fontJapanese has one user, the debug save editor. Rasterizing the full
    # Japanese glyph range into the ImGui atlas cost boot time and atlas memory
    # on every boot; the editor uses the largest standard font instead.
    source = once(
        source,
        '        fontJapanese = CreateFontWithSize(24.0f, "fonts/NotoSansJP-Regular.ttf", true);',
        "        fontJapanese = fontStandardLargest;",
    )
    source = scan_extensions_once(mount_archives_once(source))
    source = application_syntax(platform_source(source))
    stable(OUT / "generated/soh/soh/OTRGlobals.cpp", source)
    generated = {
        p.relative_to(OUT / "generated")
        .as_posix(): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in (OUT / "generated").rglob("*")
        if p.is_file()
    }
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                constructor_default_members=defaults,
                generated_sha256=generated,
                helpers={
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in OWN.iterdir()
                    if p.suffix in (".h", ".inc")
                },
                compilation_evidence="xdk/build.json",
                boundary_probes_are_production_units=False,
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return [OUT / "generated/soh"] + enhancement_includes()


def probe():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    source = folder / "declaration.cpp"
    stable(
        source,
        '#include "soh/OTRGlobals.h"\ntypedef char owner_layout[(sizeof(OTRGlobals)==80)?1:-1];\n',
    )
    recipe = json.loads(
        (ROOT / "scratch/game-interactor-xdk/xdk/build.json").read_text()
    )[0]["command"][:-2]
    recipe.insert(1, "/I" + str(OUT / "generated/soh"))
    obj = folder / "declaration.obj"
    command = recipe + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(folder / "declaration.log", result.stdout + result.stderr)
    stable(
        folder / "declaration.json",
        json.dumps(
            dict(
                command=command,
                exit=result.returncode,
                production_application_compiled=False,
            ),
            indent=2,
        )
        + "\n",
    )
    if result.returncode:
        print(result.stdout)
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    print(
        "Complete OTRGlobals class declaration: 80-byte Xenon layout; declaration probe only"
    )


def boundary_probe():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    source = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
    version = re.search(
        r"typedef struct \{\s*uint16_t major;\s*uint16_t minor;\s*uint16_t patch;\s*\} OTRVersion;",
        source,
    )
    if version is None:
        raise ValueError("Version record inventory changed")
    names = [
        "CheckAndCreateModFolder",
        "ReadPortVersionFromOTR",
        "DetectOTRVersion",
        "VerifyArchiveVersion",
        "OTRGlobals::RunExtract",
        "OTRAudio_Thread",
        "OTRAudio_Init",
        "OTRAudio_Exit",
    ]
    prelude = """#include "soh/OTRGlobals.h"
#include "application/frame_profile.h"
#include "soh/OTRAudio.h"
#include "soh/Enhancements/savestates.h"
#include <ship/resource/archive/O2rArchive.h>
#include <ship/resource/archive/ArchiveManager.h>
#include <ship/resource/ResourceManager.h>
#include <ship/utils/binarytools/MemoryStream.h>
#include <ship/utils/binarytools/BinaryReader.h>
#include "filesystem/filesystem.h"
#include "application/archive_preflight.h"
#include "context/platform.h"
#include <fstream>
#include <climits>
#include "z64.h"
#include "macros.h"
#include "variables.h"
#include "functions.h"
#include "soh/ResourceManagerHelpers.h"
extern "C" void AudioPlayer_Play(const uint8_t*, uint32_t);
extern "C" void AudioMgr_CreateNextAudioBuffer(s16*, u32);
extern "C" int AudioPlayer_Buffered(void);
extern "C" int AudioPlayer_GetDesiredBuffered(void);
extern unsigned short gBuildVersionMajor;
extern bool sohArchiveVersionMatch;
"""
    prelude += (
        version[0]
        + "\nstatic OTRVersion DetectOTRVersion(std::string,bool);\nstatic bool"
        " VerifyArchiveVersion(OTRVersion);\n"
    )
    bodies = "\n".join(function(source, n).text.decode() for n in names)
    path = folder / "startup_boundaries.cpp"
    stable(path, prelude + bodies + "\n")
    flags = json.loads((ROOT / "scratch/soh-ui-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = [
        "/I" + str(OUT / "generated/soh"),
        "/I" + str(ROOT / "scratch/libzip-xdk/generated"),
    ]
    obj = path.with_suffix(".obj")
    command = flags + [str(path), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(path.with_suffix(".log"), result.stdout + result.stderr)
    stable(
        folder / "boundary-probe.json",
        json.dumps(
            dict(
                command=command,
                exit=result.returncode,
                methods=names,
                production_unit=False,
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                object_sha256=(
                    hashlib.sha256(obj.read_bytes()).hexdigest()
                    if not result.returncode
                    else None
                ),
            ),
            indent=2,
        )
        + "\n",
    )
    print(
        "Real startup archive boundaries and audio/save-state declarations:",
        result.returncode,
    )
    if result.returncode:
        print("\n".join(s for s in result.stdout.splitlines() if "error " in s)[:5000])
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads(
        (ROOT / "scratch/application-gui-xdk/xdk/build.json").read_text()
    )[0]["command"][:-2]
    from prepare_soh_input_editor import includes as editor_includes

    roots = (
        [OUT / "generated/soh"]
        + [
            ROOT / ("scratch/" + name + "-xdk/generated/soh")
            for name in [
                "speech",
                "application-gui",
                "network",
                "randomizer-item",
                "randomizer-options",
                "save-storage",
                "audio-collection",
                "soh-input-editor",
                "soh-resources",
            ]
        ]
        + editor_includes()
    )
    roots += [Path(f[2:]) for f in flags if f.startswith("/I")]
    roots += [
        ROOT / "scratch/libzip-xdk/generated",
        ROOT / "scratch/speech-xdk/generated/espeak-ng/src/include",
    ]
    # Application-local relative includes must resolve to the same canonical
    # generated headers as their soh/... spelling.
    roots = [p / "soh" for p in roots if p.name == "soh"] + roots + [ROOT / "soh/soh"]
    roots = list(dict.fromkeys(roots))
    # Original and C-staged headers are fallback paths, never allowed to shadow
    # a complete C++ projection from another subsystem.
    roots.sort(
        key=lambda p: (
            2
            if p.is_relative_to(ROOT / "soh")
            else 1 if p.is_relative_to(ROOT / "scratch/game-xdk") else 0
        )
    )
    flags = [f for f in flags if not f.startswith("/I")]
    flags[1:1] = ["/DSHIPYARD_ESPEAK_STATIC"] + ["/I" + str(p) for p in roots]
    source = OUT / "generated/soh/soh/OTRGlobals.cpp"
    obj = folder / "OTRGlobals.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), result.stdout + result.stderr)
    stable(
        folder / "build.json",
        json.dumps(
            [
                dict(
                    source=source.relative_to(ROOT).as_posix(),
                    command=command,
                    exit=result.returncode,
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    object_sha256=(
                        hashlib.sha256(obj.read_bytes()).hexdigest()
                        if result.returncode == 0
                        else None
                    ),
                )
            ],
            indent=2,
        )
        + "\n",
    )
    print("Complete OTRGlobals.cpp:", result.returncode)
    if result.returncode:
        print("\n".join(s for s in result.stdout.splitlines() if "error " in s)[:6000])
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe", action="store_true")
    p.add_argument("--boundary-probe", action="store_true")
    p.add_argument("--build", action="store_true")
    args = p.parse_args()
    if args.build:
        build()
    elif args.boundary_probe:
        boundary_probe()
    elif args.probe:
        probe()
    else:
        prepare()
