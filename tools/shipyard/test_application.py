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
        self.assertEqual(names(original),names(projected))
        # Resource registrations and all modern application initializers stay
        # byte-for-byte; only the coupled font defaults change the constructor.
        self.assertEqual(function(original,'OTRGlobals::Initialize').text,
                         function(projected,'OTRGlobals::Initialize').text.replace(b'xbox_compat::filesystem::',b'std::filesystem::'))
        self.assertEqual(function(original,'InitOTR').text,function(projected,'InitOTR').text)
        self.assertEqual(function(original,'ReadPortVersionFromOTR').text,
                         function(projected,'ReadPortVersionFromOTR').text)

    def test_generation_is_repeatable(self):
        def snapshot():return {p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'generated').rglob('*') if p.is_file()}
        first=snapshot();prepare();self.assertEqual(first,snapshot())

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
        self.assertLess(stop.index('SaveManager_ThreadPoolWait();'),stop.index('OTRAudio_Exit();'))
        self.assertLess(stop.index('OTRAudio_Exit();'),stop.index('Shipyard::Libultra::StopTimers();'))
        self.assertLess(stop.index('Shipyard::Libultra::StopTimers();'),stop.index('context = nullptr'))

if __name__=='__main__':unittest.main()
