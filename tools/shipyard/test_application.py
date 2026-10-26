"""Startup boundary evidence; deliberately does not claim full application coverage."""

import hashlib
import json
import re
import runpy
import struct
import subprocess
import unittest
from prepare_application import ROOT, OUT, OWN, prepare, probe, boundary_probe, function
from prepare_application import mount_archives_once
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from cpp_ast import PARSER, walk

ENV = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))


class ApplicationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare()

    def test_audio_mixer_keeps_native_hardware_placement(self):
        projected = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(
            encoding="utf-8"
        )
        original = (ROOT / "soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        self.assertIn("audio.thread = std::thread(OTRAudio_Thread);", original)
        init = function(projected, "OTRAudio_Init").text.decode()
        self.assertIn(
            "audio.thread = Shipyard::Async::make_thread_on_processor(OTRAudio_Thread, 2);",
            init,
        )
        self.assertIn('ResourceMgr_LoadDirectory("audio");', init)
        self.assertEqual(
            projected.count("make_thread_on_processor(OTRAudio_Thread, 2)"), 1
        )

    def test_all_application_functions_retained(self):
        def names(text):
            return [
                n.child_by_field_name("declarator").text.decode().split("(")[0].strip()
                for n in walk(PARSER.parse(text.encode()).root_node)
                if n.type == "function_definition"
                and n.child_by_field_name("declarator") is not None
            ]

        original = (ROOT / "soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        projected = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(
            encoding="utf-8"
        )
        generated_helpers = [
            "MakeItemIDtoGetItemIDMap",
            "MakeItemIDtoRandomizerGetMap",
            "Shipyard_ReportStartupFailure",
            "Shipyard_TryInitOTR",
            "XboxRunDeferredDepthRead",
            "ShipyardNative_Gfx_RegisterBlendedTexture",
            "ShipyardNative_Gfx_UnregisterBlendedTexture",
            "ShipyardNative_Gfx_TextureCacheDelete",
            "Shipyard_OverlapCaptureGraphics",
            "Run",
        ]
        self.assertEqual(names(projected).count("Run"), 3)
        for helper in generated_helpers[-5:-1]:
            self.assertEqual(names(projected).count(helper), 1)
        self.assertEqual(names(projected).count("XboxRunDeferredDepthRead"), 1)
        # The overlap runtime is inlined ahead of Graph_ProcessGfxCommands.
        start = projected.index("// Included by the projected OTR bridge")
        end = projected.index('extern "C" void Graph_ProcessGfxCommands(', start)
        self.assertEqual(
            names(original),
            [n for n in names(projected[:start] + projected[end:]) if n not in generated_helpers],
        )

        # Compare actual resource-registration expressions independently of
        # surrounding platform lifetime and container-construction lowering.
        def registrations(text):
            body = function(text, "OTRGlobals::Initialize")
            return [
                n.text
                for n in walk(body)
                if n.type == "call_expression"
                and n.child_by_field_name("function").text.endswith(
                    b"RegisterResourceFactory"
                )
            ]

        self.assertGreater(len(registrations(original)), 20)
        self.assertEqual(registrations(original), registrations(projected))
        # All application initializers retain their order; platform lifetime
        # surrounds them and value construction keeps Anchor's upstream zeros.
        init = function(projected, "InitOTR").text.decode()
        init = re.sub(
            r'^    Shipyard::Platform::RecordBootStage\("[a-z-]+", (?:true|false)\);\n',
            "",
            init,
            flags=re.MULTILINE,
        )
        init = init.replace(
            '    xbox_compat::filesystem::InitWorkingDirectory("game:/");\n', ""
        )
        init = init.replace("    ShipyardAudioSetProcessor(1u << 3);\n", "")
        init = init.replace(
            "    // Migration v2 reloads CVars and drops defaults registered before it.\n    CVarRegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);\n",
            "",
        )
        init = init.replace(
            """    if (SDLNet_Init() != 0) throw std::runtime_error(SDLNet_GetError());
    try { Shipyard::Storage::Mount(); }
    catch (...) { SDLNet_Quit(); throw; }
""",
            "",
        )
        init = init.replace("new Anchor(Shipyard::SohUI::ValueInit())", "new Anchor()")
        xbox_selection = "#if defined(_XBOX)\n    SpeechSynthesizer::Instance = new XboxSpeechSynthesizer();\n#elif defined(__APPLE__)"
        self.assertIn(xbox_selection, init)
        init = init.replace(xbox_selection, "#ifdef __APPLE__")
        expected = (
            function(original, "InitOTR")
            .text.decode()
            .replace("#ifdef ENABLE_REMOTE_CONTROL\n    SDLNet_Init();\n#endif", "")
        )
        self.assertEqual(expected, init)
        self.assertEqual(
            function(mount_archives_once(original), "ReadPortVersionFromOTR").text,
            function(projected, "ReadPortVersionFromOTR").text,
        )

    def test_generation_is_repeatable(self):
        def snapshot():
            return {
                p.relative_to(OUT)
                .as_posix(): hashlib.sha256(p.read_bytes())
                .hexdigest()
                for p in (OUT / "generated").rglob("*")
                if p.is_file()
            }

        first = snapshot()
        prepare()
        self.assertEqual(first, snapshot())

    def test_initialize_keeps_real_randomizer_order(self):
        projected = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(
            encoding="utf-8"
        )
        body = function(projected, "OTRGlobals::Initialize").text.decode()
        self.assertLess(
            body.index("if (!context->InitLogging("),
            body.index("GetLogger()->set_pattern("),
        )
        initialize_stages = [
            "logging-ready",
            "audio-ready",
            "factories-ready",
            "randomizer-ready",
        ]
        stage_positions = [
            body.index('RecordBootStage("' + stage + '"') for stage in initialize_stages
        ]
        self.assertEqual(stage_positions, sorted(stage_positions))
        self.assertEqual(body.count("RecordBootStage("), len(initialize_stages))
        landmarks = [
            "gSaveStateMgr = std::make_shared<SaveStateMgr>();",
            "gRandoContext->InitStaticData();",
            "gRandoContext = Rando::Context::CreateInstance();",
            "Rando::StaticData::InitItemTable();",
            "gRandomizer = std::make_shared<Randomizer>();",
            "GetGameVersions();",
        ]
        locations = [body.index(mark) for mark in landmarks]
        self.assertEqual(locations, sorted(locations))
        for mark in landmarks:
            self.assertEqual(body.count(mark), 1)

    def test_preflight_conditions_match_upstream(self):
        folder = OUT / "host"
        folder.mkdir(exist_ok=True)
        original = (ROOT / "soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        verify = function(original, "VerifyArchiveVersion").text.decode()
        source = (
            """#include "application/archive_preflight.h"
#include <stdint.h>
#include <climits>
#include <cassert>
#include <cstdio>
struct OTRVersion { uint16_t major, minor, patch; };
uint16_t gBuildVersionMajor = 9;
"""
            + verify
            + """
int main() {
    for (unsigned major=0;major<=65535;++major) {
        OTRVersion v={static_cast<uint16_t>(major),0,0};
        assert(VerifyArchiveVersion(v)==(major!=32767 && major!=9));
    }
    for (unsigned mask=0;mask<32;++mask) {
        bool port=(mask&1)!=0, vanillaBad=(mask&2)!=0, mqBad=(mask&4)!=0;
        bool vanilla=(mask&8)!=0, mq=(mask&16)!=0;
        const bool expected=port && !(vanillaBad || mqBad) && (vanilla || mq);
        assert((Shipyard::Application::CheckArchives(port,vanillaBad,mqBad,vanilla,mq)==
                Shipyard::Application::ArchivesReady)==expected);
    }
    puts("65536 real version-major comparisons and 32 archive availability combinations passed");
}
"""
        )
        path = folder / "archive_contract.cpp"
        path.write_text(source)
        compiler, env = ENV["host_environment"]()
        command = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/MD",
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE / "sources"),
            path,
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "archive_contract.exe"),
        ]
        ENV["invoke"](command, folder, "compile", env)
        result = ENV["invoke"]([folder / "archive_contract.exe"], folder, "run", env)
        self.assertIn("65536", result["stdout"])

    def test_writable_app_path_is_crt_safe(self):
        """Context uses the executable directory without a mixed separator join."""
        folder = OUT / "host-app-path"
        folder.mkdir(exist_ok=True)
        source = r"""#include "context/platform.h"
#include "save-storage/storage.h"
#include <cassert>
#include <string>
namespace Shipyard { namespace Storage {
std::string SaveDirectory() { return "shipyard:\\Save"; }
}}
int main() {
    const std::string root=Shipyard::Platform::ApplicationDirectory();
    const std::string config=root+"/shipofharkinian.json";
    assert(root=="game:");
    assert(config=="game:/shipofharkinian.json");
    assert(config.find("\\/")==std::string::npos);
}
"""
        path = folder / "app_path_contract.cpp"
        path.write_text(source)
        compiler, env = ENV["host_environment"]()
        command = [
            compiler,
            "/nologo",
            "/std:c++20",
            "/EHsc",
            "/MD",
            "/DNOMINMAX",
            "/I" + str(ROOT / "platform/shipyard"),
            "/I" + str(PLATFORM_BASE),
            "/I" + str(PLATFORM_BASE / "sources"),
            path,
            ROOT / "platform/shipyard/context/platform.cpp",
            PLATFORM_BASE / "sources/filesystem/filesystem.cpp",
            PLATFORM_BASE / "sources/async/native.cpp",
            "user32.lib",
            "/Fo:" + str(folder) + "/",
            "/Fe:" + str(folder / "app_path_contract.exe"),
        ]
        ENV["invoke"](command, folder, "compile", env)
        ENV["invoke"]([folder / "app_path_contract.exe"], folder, "run", env)

    def test_native_real_boundary_methods(self):
        probe()
        boundary_probe()
        obj = OUT / "xdk/startup_boundaries.obj"
        self.assertEqual(struct.unpack_from("<H", obj.read_bytes())[0], 0x1F2)
        self.assertFalse(
            json.loads((OUT / "xdk/boundary-probe.json").read_text())["production_unit"]
        )
        self.assertNotIn(b"Extractor", obj.read_bytes())
        self.assertIn(b"O2rArchive", obj.read_bytes())

    def test_audio_and_shutdown_ownership(self):
        source = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        audio = function(source, "OTRAudio_Thread").text.decode()
        self.assertNotIn("while (audio.running)", audio)
        self.assertLess(
            audio.index("Lock(audio.mutex)"), audio.index("if (!audio.running)")
        )
        self.assertIn("AudioMgr_CreateNextAudioBuffer(", audio)
        self.assertIn("AudioPlayer_Play(", audio)
        stop = function(source, "DeinitOTR").text.decode()
        start = function(source, "InitOTR").text.decode()
        self.assertLess(start.index("SDLNet_Init()"), start.index("new OTRGlobals()"))
        self.assertLess(
            start.index("Storage::Mount()"), start.index("new OTRGlobals()")
        )
        self.assertIn('xbox_compat::filesystem::InitWorkingDirectory("game:/");', start)
        self.assertLess(
            start.index("InitWorkingDirectory("), start.index("Storage::Mount()")
        )
        self.assertLess(
            start.index("conf->RunVersionUpdates();"),
            start.index("CVarRegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);"),
        )
        self.assertLess(
            start.index("CVarRegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);"),
            start.index("SohGui::SetupGuiElements();"),
        )
        # Version 2's ClearBlock reloads CVars, erasing the pre-migration
        # Xbox default on a fresh profile; the post-migration register restores it.
        updater = (ROOT / "soh/soh/config/ConfigUpdaters.cpp").read_text()
        console = (
            ROOT / "libultraship/src/ship/config/ConsoleVariable.cpp"
        ).read_text()
        self.assertIn('CVarClearBlock("gAudioEditor.ReplacedSequences")', updater)
        self.assertIn("void ConsoleVariable::ClearBlock(const char* name)", console)
        self.assertIn(
            "    Load();\n}",
            console[console.index("void ConsoleVariable::ClearBlock(") :],
        )
        for remote in ("CrowdControl", "Sail", "Anchor"):
            self.assertLess(
                stop.index(remote + "::Instance->Disable();"),
                stop.index("OTRAudio_Exit();"),
            )
        self.assertLess(
            stop.index("OTRAudio_Exit();"),
            stop.index("Shipyard::Libultra::StopTimers();"),
        )
        order = [
            "JoinRandoGenerationThread();",
            "Shipyard::Libultra::StopTimers();",
            "SaveManager_ThreadPoolWait();",
            "delete SaveManager::Instance;",
            "DestroyXboxSpeechSynthesizer(SpeechSynthesizer::Instance);",
            "SpeechSynthesizer::Instance = nullptr;",
            "SohGui::Destroy();",
            "WaitForPendingTasks();",
            "wait_for_detached();",
            "context = nullptr",
            "Storage::Shutdown();",
            "SDLNet_Quit();",
        ]
        positions = [stop.index(s) for s in order]
        self.assertEqual(sorted(positions), positions)

    def test_native_startup_failure_boundary(self):
        source = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        wrapper = function(source, "Shipyard_TryInitOTR").text.decode()
        self.assertIn("InitOTR(argc, argv);", wrapper)
        self.assertIn("catch (const Shipyard::Async::native_error& error)", wrapper)
        self.assertIn("error.native_code()", wrapper)
        self.assertIn("catch (const std::system_error& error)", wrapper)
        self.assertIn("catch (const std::exception& error)", wrapper)
        self.assertIn("Shipyard::Platform::RecordStartupFailure(message);", source)
        self.assertIn("Shipyard::Platform::ShowError", source)
        self.assertLess(
            source.index('extern "C" void InitOTR('),
            source.index('extern "C" int Shipyard_TryInitOTR('),
        )

    def test_hardware_fault_receipt_has_dual_sink_and_bounded_boot_checkpoints(self):
        platform = (ROOT / "platform/shipyard/context/platform.cpp").read_text()
        recorder = platform[
            platform.index("void RecordNativeFault(") : platform.index(
                "LONG WINAPI ShipyardUnhandledFault("
            )
        ]
        installer = platform[
            platform.index(
                'extern "C" void Shipyard_InstallStartupFaultHandler()'
            ) : platform.index("namespace Shipyard { namespace Platform")
        ]
        self.assertIn("OutputDebugStringA(line);", recorder)
        self.assertIn('CreateDirectoryA("game:\\\\logs", NULL);', recorder)
        self.assertEqual(
            recorder.count(
                'WriteFlushedFile("game:\\\\logs\\\\startup-fault.txt", line, false);'
            ),
            1,
        )
        self.assertLess(
            recorder.index("CreateDirectoryA("), recorder.index("WriteFlushedFile(")
        )
        self.assertIn("FlushFileBuffers(file)", platform)
        self.assertIn("SetUnhandledExceptionFilter(ShipyardUnhandledFault)", installer)
        self.assertIn("std::set_terminate(ShipyardTerminated)", installer)
        self.assertIn("signal(SIGABRT, ShipyardAborted)", installer)
        self.assertNotIn("RecordNativeFault(", installer)
        source = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(encoding="utf-8")
        start = function(source, "InitOTR").text.decode()
        stages = [
            "entry",
            "mounted",
            "constructor-ready",
            "pre-context",
            "context-ready",
            "save-worker-ready",
            "config-updaters-ready",
            "config-ready",
            "gui-windows-ready",
            "gui-ready",
            "speech-ready",
            "init-complete",
        ]
        positions = [start.index('RecordBootStage("' + stage + '"') for stage in stages]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(start.count("RecordBootStage("), len(stages))
        self.assertIn('RecordBootStage("mounted", true)', start)
        self.assertIn('RecordBootStage("pre-context", true)', start)
        self.assertEqual(start.count(", true)"), 2)
        for path in (
            "platform/shipyard/xenos/services.cpp",
            "platform/shipyard/audio/audio_log.cpp",
        ):
            fatal = (ROOT / path).read_text()
            self.assertLess(
                fatal.index("RecordStartupFatal("), fatal.index("std::abort()")
            )

    def test_native_startup_failure_returns_and_reports_code(self):
        projected = (OUT / "generated/soh/soh/OTRGlobals.cpp").read_text(
            encoding="utf-8"
        )
        folder = OUT / "host-startup-failure"
        folder.mkdir(exist_ok=True)
        harness = (
            """#include <cstdio>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <string>
#include <system_error>
typedef unsigned long DWORD;
namespace Shipyard { namespace Async {
class native_error : public std::runtime_error {
public:
    native_error(const char* message, DWORD code) : std::runtime_error(message), code_(code) {}
    DWORD native_code() const { return code_; }
private: DWORD code_;
};
} namespace Platform {
std::wstring shown;
void ShowError(const wchar_t*, const wchar_t* message) { shown=message; }
void RecordStartupFailure(const char*) {}
} }
void OutputDebugStringA(const char*) {}
int failure;
extern "C" void InitOTR(int, char*[]) {
    if (failure==1) throw Shipyard::Async::native_error("XContentCreate", 123);
    if (failure==2) throw std::system_error(std::error_code(5, std::system_category()), "filesystem");
    if (failure==3) throw std::runtime_error("logger");
    if (failure==4) throw 42;
}
"""
            + function(projected, "Shipyard_ReportStartupFailure").text.decode()
            + "\n"
            + function(projected, "Shipyard_TryInitOTR").text.decode()
            + """
int main() {
    for (failure=0; failure<=4; ++failure) {
        Shipyard::Platform::shown.clear();
        int result=Shipyard_TryInitOTR(0, nullptr);
        if (failure==0) { if (result!=1 || !Shipyard::Platform::shown.empty()) return 1; }
        else if (result!=0 || Shipyard::Platform::shown.empty()) return 2;
        if (failure==1 && Shipyard::Platform::shown.find(L"XContentCreate (Xbox error 123)")==std::wstring::npos) return 3;
        if (failure==2 && Shipyard::Platform::shown.find(L"Xbox error 5")==std::wstring::npos) return 4;
        if (failure==3 && Shipyard::Platform::shown.find(L"logger")==std::wstring::npos) return 5;
        if (failure==4 && Shipyard::Platform::shown.find(L"unknown native exception")==std::wstring::npos) return 6;
    }
    puts("native startup failure boundary passed");
}
"""
        )
        path = folder / "startup_failure_contract.cpp"
        path.write_text(harness)
        compiler, env = ENV["host_environment"]()
        ENV["invoke"](
            [
                compiler,
                "/nologo",
                "/EHsc",
                "/MD",
                path,
                "/Fo:" + str(folder) + "/",
                "/Fe:" + str(folder / "startup_failure_contract.exe"),
            ],
            folder,
            "compile",
            env,
        )
        result = ENV["invoke"](
            [folder / "startup_failure_contract.exe"], folder, "run", env
        )
        self.assertIn("native startup failure boundary passed", result["stdout"])


if __name__ == "__main__":
    unittest.main()
