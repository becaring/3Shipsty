"""Startup boundary evidence; deliberately does not claim full application coverage."""
import hashlib
import json
import runpy
import struct
import subprocess
import unittest
from prepare_application import ROOT, OUT, OWN, prepare, probe, boundary_probe, function
from cpp_ast import PARSER, walk

ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))

class ApplicationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare()

    def test_all_application_functions_retained(self):
        def names(text):
            return [n.child_by_field_name('declarator').text.decode().split('(')[0].strip()
                    for n in walk(PARSER.parse(text.encode()).root_node)
                    if n.type=='function_definition' and n.child_by_field_name('declarator') is not None]
        original=(ROOT/'soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        projected=(OUT/'generated/soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        generated_helpers=['MakeItemIDtoGetItemIDMap','MakeItemIDtoRandomizerGetMap']
        self.assertEqual(names(original),[n for n in names(projected) if n not in generated_helpers])
        # Compare actual resource-registration expressions independently of
        # surrounding platform lifetime and container-construction lowering.
        def registrations(text):
            body=function(text,'OTRGlobals::Initialize')
            return [n.text for n in walk(body) if n.type=='call_expression' and
                    n.child_by_field_name('function').text.endswith(b'RegisterResourceFactory')]
        self.assertGreater(len(registrations(original)),20)
        self.assertEqual(registrations(original),registrations(projected))
        # All application initializers retain their order; platform lifetime
        # surrounds them and value construction keeps Anchor's upstream zeros.
        init=function(projected,'InitOTR').text.decode()
        init=init.replace('    xbox_compat::filesystem::InitWorkingDirectory("game:/");\n','')
        init=init.replace('    if (SDLNet_Init() != 0) throw std::runtime_error(SDLNet_GetError());\n    try { Shipyard::Storage::Mount(); }\n    catch (...) { SDLNet_Quit(); throw; }\n','')
        init=init.replace('new Anchor(Shipyard::SohUI::ValueInit())','new Anchor()')
        xbox_selection='#if defined(_XBOX)\n    SpeechSynthesizer::Instance = new XboxSpeechSynthesizer();\n#elif defined(__APPLE__)'
        self.assertIn(xbox_selection,init)
        init=init.replace(xbox_selection,'#ifdef __APPLE__')
        expected=function(original,'InitOTR').text.decode().replace('#ifdef ENABLE_REMOTE_CONTROL\n    SDLNet_Init();\n#endif','')
        self.assertEqual(expected,init)
        self.assertEqual(function(original,'ReadPortVersionFromOTR').text,
                         function(projected,'ReadPortVersionFromOTR').text)

    def test_generation_is_repeatable(self):
        def snapshot():return {p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'generated').rglob('*') if p.is_file()}
        first=snapshot();prepare();self.assertEqual(first,snapshot())

    def test_initialize_keeps_real_randomizer_order(self):
        projected=(OUT/'generated/soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        body=function(projected,'OTRGlobals::Initialize').text.decode()
        landmarks=[
            'gSaveStateMgr = std::make_shared<SaveStateMgr>();',
            'gRandoContext->InitStaticData();',
            'gRandoContext = Rando::Context::CreateInstance();',
            'Rando::StaticData::InitItemTable();',
            'gRandomizer = std::make_shared<Randomizer>();',
            'GetGameVersions();',
        ]
        locations=[body.index(mark) for mark in landmarks]
        self.assertEqual(locations,sorted(locations))
        for mark in landmarks:
            self.assertEqual(body.count(mark),1)

    def test_preflight_conditions_match_upstream(self):
        folder=OUT/'host';folder.mkdir(exist_ok=True)
        original=(ROOT/'soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        verify=function(original,'VerifyArchiveVersion').text.decode()
        source='''#include "application/archive_preflight.h"
#include <stdint.h>
#include <climits>
#include <cassert>
#include <cstdio>
struct OTRVersion { uint16_t major, minor, patch; };
uint16_t gBuildVersionMajor = 9;
'''+verify+'''
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
'''
        path=folder/'archive_contract.cpp';path.write_text(source)
        compiler,env=ENV['host_environment']()
        command=[compiler,'/nologo','/std:c++20','/EHsc','/MD','/I'+str(ROOT/'platform/shipyard'),path,'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'archive_contract.exe')]
        ENV['invoke'](command,folder,'compile',env)
        result=ENV['invoke']([folder/'archive_contract.exe'],folder,'run',env)
        self.assertIn('65536',result['stdout'])

    def test_writable_app_path_is_crt_safe(self):
        """The Context string join must not emit ``shipyard:\\/...``."""
        folder=OUT/'host-app-path';folder.mkdir(exist_ok=True)
        source=r'''#include "context/platform.h"
#include "save-storage/storage.h"
#include <cassert>
#include <string>
namespace Shipyard { namespace Storage {
std::string SaveDirectory() { return "shipyard:\\Save"; }
}}
int main() {
    const std::string root=Shipyard::Platform::ApplicationDirectory();
    const std::string config=root+"/shipofharkinian.json";
    assert(root=="shipyard:");
    assert(config=="shipyard:/shipofharkinian.json");
    assert(config.find("\\/")==std::string::npos);
}
'''
        path=folder/'app_path_contract.cpp';path.write_text(source)
        compiler,env=ENV['host_environment']()
        command=[compiler,'/nologo','/std:c++20','/EHsc','/MD','/DNOMINMAX',
                 '/I'+str(ROOT/'platform/shipyard'),path,
                 ROOT/'platform/shipyard/context/platform.cpp',
                 ROOT/'platform/shipyard/filesystem/filesystem.cpp',
                 ROOT/'platform/shipyard/async/native.cpp','user32.lib',
                 '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'app_path_contract.exe')]
        ENV['invoke'](command,folder,'compile',env)
        ENV['invoke']([folder/'app_path_contract.exe'],folder,'run',env)

    def test_native_real_boundary_methods(self):
        probe();boundary_probe()
        obj=OUT/'xdk/startup_boundaries.obj'
        self.assertEqual(struct.unpack_from('<H',obj.read_bytes())[0],0x1f2)
        self.assertFalse(json.loads((OUT/'xdk/boundary-probe.json').read_text())['production_unit'])
        self.assertNotIn(b'Extractor',obj.read_bytes())
        self.assertIn(b'O2rArchive',obj.read_bytes())

    def test_audio_and_shutdown_ownership(self):
        source=(OUT/'generated/soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        audio=function(source,'OTRAudio_Thread').text.decode()
        self.assertNotIn('while (audio.running)',audio)
        self.assertLess(audio.index('Lock(audio.mutex)'),audio.index('if (!audio.running)'))
        self.assertIn('AudioMgr_CreateNextAudioBuffer(',audio)
        self.assertIn('AudioPlayer_Play(',audio)
        stop=function(source,'DeinitOTR').text.decode()
        start=function(source,'InitOTR').text.decode()
        self.assertLess(start.index('SDLNet_Init()'),start.index('new OTRGlobals()'))
        self.assertLess(start.index('Storage::Mount()'),start.index('new OTRGlobals()'))
        self.assertIn('xbox_compat::filesystem::InitWorkingDirectory("game:/");',start)
        self.assertLess(start.index('InitWorkingDirectory('),start.index('Storage::Mount()'))
        for remote in ('CrowdControl','Sail','Anchor'):
            self.assertLess(stop.index(remote+'::Instance->Disable();'),stop.index('OTRAudio_Exit();'))
        self.assertLess(stop.index('OTRAudio_Exit();'),stop.index('Shipyard::Libultra::StopTimers();'))
        order=['JoinRandoGenerationThread();','Shipyard::Libultra::StopTimers();','SaveManager_ThreadPoolWait();','delete SaveManager::Instance;',
               'DestroyXboxSpeechSynthesizer(SpeechSynthesizer::Instance);','SpeechSynthesizer::Instance = nullptr;',
               'SohGui::Destroy();','WaitForPendingTasks();','wait_for_detached();','context = nullptr',
               'Storage::Shutdown();','SDLNet_Quit();']
        positions=[stop.index(s) for s in order]
        self.assertEqual(sorted(positions),positions)

if __name__=='__main__':unittest.main()
