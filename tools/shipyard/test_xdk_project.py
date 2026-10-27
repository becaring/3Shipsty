"""Deterministic inventory, omission guards, and optional real MSBuild XDK smoke build."""
import argparse
import copy
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import generate_xdk_project as gen
import build_xdk_project as build


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = gen.collect()

    def test_shards_remain_until_success_receipt_verification(self):
        with tempfile.TemporaryDirectory(dir=gen.ROOT/'scratch') as directory:
            output = Path(directory)
            project = output/'ShipyardCompile.vcxproj'
            project.write_bytes(b'project')
            (output/'manifest.json').write_bytes(b'{}')
            planned = SimpleNamespace(project=project, output=output/'build/shards')
            manifest = {'missing_subsystem_recipes': [], 'sources': [], 'application_counts': {}}
            shared = {'builds': [], 'build_exit': 0, 'sources': [], 'headers': {}}
            events = []
            with (patch.object(gen, 'OUT', output),
                  patch.object(gen, 'collect', return_value=manifest),
                  patch.object(gen, 'write'),
                  patch.object(build, 'project_plan', return_value=planned),
                  patch.object(build.parallel_build, 'run', return_value=shared),
                  patch.object(build.parallel_build, 'verify_receipt',
                               side_effect=lambda *_: events.append('verify')),
                  patch.object(build.parallel_build, 'remove_shards',
                               side_effect=lambda *_: events.append('remove')),
                  patch.object(sys, 'argv', ['build_xdk_project.py'])):
                self.assertEqual(build.main(), 0)
            self.assertEqual(events, ['verify', 'remove'])

    def test_regeneration_preserves_unchanged_project_timestamp(self):
        with tempfile.TemporaryDirectory(dir=gen.ROOT/'scratch') as directory:
            with patch.object(gen, 'OUT', Path(directory)):
                gen.write(self.manifest)
                paths = (gen.OUT/'manifest.json', gen.OUT/'ShipyardCompile.vcxproj')
                for path in paths:
                    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
                gen.write(self.manifest)
                for path in paths:
                    self.assertEqual(path.stat().st_mtime_ns, 1_000_000_000)

    def test_reproducible_project(self):
        self.assertEqual(gen.project(self.manifest), gen.project(copy.deepcopy(self.manifest)))
        xml = ET.fromstring(gen.project(self.manifest))
        items = xml.findall('.//{'+gen.NS+'}ClCompile[@Include]')
        self.assertEqual(len(items), len(self.manifest['sources']))
        self.assertEqual(len({r['object'] for r in self.manifest['sources']}), len(items))

    def test_shared_shard_plan_keeps_canonical_objects(self):
        gen.write(self.manifest)
        planned = build.project_plan(self.manifest, jobs=8)
        self.assertEqual(len(planned.shards), 8)
        self.assertEqual(len(planned.sources), len(self.manifest['sources']))
        self.assertEqual(
            {str(row.object) for row in planned.sources},
            {str(gen.OUT/'build/obj'/row['object']) for row in self.manifest['sources']},
        )
        self.assertEqual(
            {str(row.source) for row in planned.sources if row.source.is_relative_to(gen.PLATFORM_BASE)},
            {str(gen.source_path(row['source'])) for row in self.manifest['sources']
             if row['source'].startswith('shipyard/')},
        )

    def test_shared_xbox_compiler_policy(self):
        xml = ET.fromstring(gen.project(self.manifest))
        definition = xml.find('.//{'+gen.NS+'}ItemDefinitionGroup/{'+gen.NS+'}ClCompile')
        self.assertEqual(definition.findtext('{'+gen.NS+'}FunctionLevelLinking'), 'true')
        self.assertEqual(definition.findtext('{'+gen.NS+'}FloatingPointModel'), 'Precise')

    def test_direct_shipyard_graphics_and_gamepad_inputs(self):
        selected={row['source']:row for row in self.manifest['sources']}
        shader='shipyard/sources/graphics/shader_lower.cpp'
        self.assertIn(shader,selected)
        self.assertNotIn('scratch/graphics-xdk/shader_lower.cpp',selected)
        self.assertEqual(gen.source_path(shader),gen.PLATFORM_BASE/'sources/graphics/shader_lower.cpp')
        xml=ET.fromstring(gen.project(self.manifest))
        includes={item.attrib['Include'] for item in xml.findall('.//{'+gen.NS+'}ClCompile[@Include]')}
        self.assertIn('$(ShipyardPlatformBase)/sources/graphics/shader_lower.cpp',includes)
        provider='shipyard/sources/graphics/shader_provider.cpp'
        self.assertIn(provider,selected)
        self.assertEqual(gen.source_path(provider),gen.PLATFORM_BASE/'sources/graphics/shader_provider.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/graphics/shader_provider.cpp',includes)
        self.assertIn('platform/shipyard/xenos/shader_provider.cpp',selected)
        xenos='shipyard/sources/xenos/core.cpp'
        self.assertIn(xenos,selected)
        self.assertEqual(gen.source_path(xenos),gen.PLATFORM_BASE/'sources/xenos/core.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/xenos/core.cpp',includes)
        self.assertIn('void GetPixelDepthSamples(', gen.source_path(xenos).read_text())
        surface='shipyard/sources/presentation/xenos_surface.cpp'
        self.assertIn(surface,selected)
        self.assertEqual(gen.source_path(surface),gen.PLATFORM_BASE/'sources/presentation/xenos_surface.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/presentation/xenos_surface.cpp',includes)
        self.assertIn('platform/shipyard/presentation/window_xenos.cpp',selected)
        window=(gen.ROOT/'platform/shipyard/presentation/window_xenos.cpp').read_text()
        self.assertIn('mSurface.Prepare(',window)
        self.assertNotIn('ApplyXenosPresentationInterval(',window)
        self.assertNotIn('mPacing.Next()',window)
        self.assertIn('platform/shipyard/xenos/api.cpp',selected)
        self.assertNotIn('scratch/xenos-xdk/generated/native.cpp',selected)
        self.assertFalse((gen.ROOT/'scratch/xenos-xdk/generated/native.cpp').exists())
        imgui='shipyard/sources/imgui/imgui_xenos.cpp'
        self.assertIn(imgui,selected)
        self.assertNotIn('scratch/native-imgui-xdk/generated/imgui_xenos.cpp',selected)
        self.assertEqual(gen.source_path(imgui),gen.PLATFORM_BASE/'sources/imgui/imgui_xenos.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/imgui/imgui_xenos.cpp',includes)
        frame=selected['shipyard/sources/imgui/platform_frame.cpp']
        self.assertIn('/I$(ShipyardPlatformBase)/sources/imgui',frame['options'])
        self.assertEqual(gen.source_path('shipyard/sources/imgui/platform_frame.cpp'),gen.PLATFORM_BASE/'sources/imgui/platform_frame.cpp')
        self.assertIn('platform/shipyard/native-imgui/platform_adapter.cpp',selected)
        self.assertNotIn('platform/shipyard/native-imgui/platform_frame.cpp',selected)
        self.assertFalse((gen.ROOT/'scratch/native-imgui-xdk/generated/gamepad_bindings.inc').exists())
        self.assertFalse((gen.ROOT/'scratch/native-imgui-xdk/generated/imgui_xenos.cpp').exists())
        for name in ('physical.cpp', 'xinput.cpp'):
            source='shipyard/sources/input/'+name
            self.assertIn(source, selected)
            self.assertEqual(gen.source_path(source), gen.PLATFORM_BASE/'sources/input'/name)
            self.assertIn('$(ShipyardPlatformBase)/sources/input/'+name, includes)
            self.assertFalse((gen.ROOT/'platform/shipyard/input'/name).exists())
        self.assertFalse((gen.ROOT/'platform/shipyard/input/physical.h').exists())
        self.assertFalse(any(row['source'].startswith('platform/shipyard/input/') and
                             row['source'].endswith(('physical.cpp','xinput.cpp'))
                             for row in self.manifest['sources']))
        for name in ('native.cpp', 'detached.cpp'):
            source='shipyard/sources/async/'+name
            self.assertIn(source, selected)
            self.assertEqual(gen.source_path(source), gen.PLATFORM_BASE/'sources/async'/name)
            self.assertIn('$(ShipyardPlatformBase)/sources/async/'+name, includes)
            self.assertFalse((gen.ROOT/'platform/shipyard/async'/name).exists())
        for name in ('native.h', 'future.h', 'detached.h'):
            self.assertFalse((gen.ROOT/'platform/shipyard/async'/name).exists())
        self.assertFalse((gen.ROOT/'platform/shipyard/thread-pool/native_support.h').exists())
        pool='shipyard/sources/audio/PcmBufferPool.cpp'
        self.assertIn(pool, selected)
        self.assertEqual(gen.source_path(pool), gen.PLATFORM_BASE/'sources/audio/PcmBufferPool.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/audio/PcmBufferPool.cpp', includes)
        self.assertFalse((gen.ROOT/'platform/shipyard/audio/PcmBufferPool.cpp').exists())
        self.assertFalse((gen.ROOT/'platform/shipyard/audio/PcmBufferPool.h').exists())
        sink='shipyard/sources/audio/XAudio2AudioPlayer.cpp'
        self.assertIn(sink, selected)
        self.assertEqual(gen.source_path(sink), gen.PLATFORM_BASE/'sources/audio/XAudio2AudioPlayer.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/audio/XAudio2AudioPlayer.cpp', includes)
        self.assertFalse((gen.ROOT/'platform/shipyard/audio/XAudio2AudioPlayer.cpp').exists())
        self.assertFalse((gen.ROOT/'platform/shipyard/audio/XAudio2AudioPlayer.h').exists())
        clock='shipyard/sources/clock/chrono.cpp'
        self.assertIn(clock, selected)
        self.assertEqual(gen.source_path(clock), gen.PLATFORM_BASE/'sources/clock/chrono.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/clock/chrono.cpp', includes)
        self.assertFalse((gen.ROOT/'platform/shipyard/logging/chrono/chrono.cpp').exists())
        storage='shipyard/sources/storage/device.cpp'
        self.assertIn(storage, selected)
        self.assertEqual(gen.source_path(storage), gen.PLATFORM_BASE/'sources/storage/device.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/storage/device.cpp', includes)
        self.assertIn('platform/shipyard/save-storage/storage.cpp', selected)
        self.assertNotIn('scratch/save-storage-xdk/generated/storage.cpp', selected)
        atomic='shipyard/sources/storage/atomic_file.cpp'
        self.assertIn(atomic, selected)
        self.assertEqual(gen.source_path(atomic), gen.PLATFORM_BASE/'sources/storage/atomic_file.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/storage/atomic_file.cpp', includes)
        self.assertFalse((gen.ROOT/'platform/shipyard/save-storage/atomic_file.cpp').exists())
        self.assertNotIn('platform/shipyard/save-storage/atomic_file.cpp', selected)
        filesystem='shipyard/sources/filesystem/filesystem.cpp'
        self.assertIn(filesystem, selected)
        self.assertEqual(gen.source_path(filesystem), gen.PLATFORM_BASE/'sources/filesystem/filesystem.cpp')
        self.assertIn('$(ShipyardPlatformBase)/sources/filesystem/filesystem.cpp', includes)
        self.assertFalse((gen.ROOT/'platform/shipyard/filesystem/filesystem.cpp').exists())
        self.assertNotIn('platform/shipyard/filesystem/filesystem.cpp', selected)

    def test_parallel_shards_cover_each_object_once(self):
        gen.write(self.manifest)
        planned=build.project_plan(self.manifest,jobs=8)
        objects=[];intermediates=set()
        for shard in planned.shards:
            xml=ET.fromstring(shard.contents)
            namespace='{'+gen.NS+'}'
            interim=xml.findtext('.//'+namespace+'IntDir')
            intermediates.add(interim)
            for item in xml.findall('.//'+namespace+'ClCompile[@Include]'):
                path=item.findtext(namespace+'ObjectFileName')
                self.assertTrue(path.startswith(str(gen.OUT/'build/obj')))
                objects.append(path)
        self.assertEqual(len(objects),len(self.manifest['sources']))
        self.assertEqual(len(set(objects)),len(objects))
        self.assertEqual(len(intermediates),8)

    def test_complete_application_inventory(self):
        app = [r for r in self.manifest['coverage'] if r['role']=='application']
        self.assertEqual(len(app), 1094)
        self.assertEqual(sum(r['path'].endswith('.c') for r in app), 696)
        self.assertEqual(sum(r['path'].endswith('.cpp') for r in app), 398)
        self.assertTrue(all(r['status']=='selected' for r in app))
        self.assertFalse(any(r['status']=='excluded' for r in app))
        self.assertFalse(self.manifest['final_application_ready'])

    def test_real_metadata_and_crt_providers(self):
        selected={r['source']:r for r in self.manifest['sources']}
        self.assertEqual(selected['scratch/build-metadata-xdk/build.c']['language'],'c')
        for name in ('float.cpp','format.cpp'):
            self.assertIn('shipyard/sources/crt/'+name,selected)
            self.assertNotIn('platform/shipyard/crt/'+name,selected)
            self.assertFalse((gen.ROOT/'platform/shipyard/crt'/name).exists())
        self.assertNotIn('platform/shipyard/crt/contract.cpp',selected)

    def test_new_source_is_pending_and_removed_projection_detectable(self):
        files = self.manifest['coverage'] + [dict(path='soh/soh/NewFeature.cpp',role='application')]
        updated = gen.coverage(files, self.manifest['sources'])
        self.assertEqual(updated[-1]['status'], 'pending')
        existing = next(r for r in self.manifest['sources'] if r['upstream_source'] and r['subsystem']=='game')
        updated = gen.coverage(files, [r for r in self.manifest['sources'] if r is not existing])
        self.assertEqual(next(r for r in updated if r['path']==existing['upstream_source'])['status'], 'pending')

    def test_platform_replacements_cannot_hide_application_sources(self):
        self.assertFalse([r['path'] for r in self.manifest['coverage'] if r['status']=='pending'])
        replacements=[r for r in self.manifest['coverage'] if r['status']=='platform-replaced']
        self.assertEqual(len(replacements),16)
        self.assertTrue(all(r['platform_decision']['reason'] and r['platform_decision']['evidence'] for r in replacements))
        app=next(r for r in self.manifest['coverage'] if r['role']=='application')
        with self.assertRaisesRegex(ValueError,'replace application'):
            gen.coverage([app],[],{app['path']:{'reason':'Invalid exclusion'}})
        self.assertTrue(any(r['upstream_source']=='libultraship/src/ship/utils/stox.cpp' for r in self.manifest['sources']))

    def test_complete_owner_headers_precede_earlier_declarations(self):
        policies=json.loads(gen.CONFIG.read_text())['canonical_header_providers']
        for row in self.manifest['sources']:
            if row['language']!='cpp':continue
            for policy in policies:
                a='/I$(ShipyardRoot)/'+policy['root'];b='/I$(ShipyardRoot)/'+policy['earlier_root']
                if b in row['options']:
                    self.assertIn(a,row['options'])
                    self.assertLess(row['options'].index(a),row['options'].index(b))

    def test_compile_contract(self):
        self.assertNotIn('scratch/graphics-xdk/cc_features.cpp', {r['source'] for r in self.manifest['sources']})
        for r in self.manifest['sources']:
            self.assertTrue(r['requires_fresh_build'])
            self.assertIn('/I$(ShipyardPlatformBase)/sources', r['options'])
            self.assertNotIn('/tests/', r['source'])
            self.assertFalse(r['source'].startswith('tools/'))
            self.assertFalse(r['source'].endswith(('contract.cpp','xdk_abi.cpp')))
            self.assertFalse(r['source'].endswith('/xdk/declarations.cpp'))
            if r['language']=='cpp':
                self.assertIn('/GR',r['options']);self.assertIn('/TP',r['options'])
                self.assertNotIn('/TC',r['options'])
                self.assertIn('/I$(ShipyardPlatformBase)/sources/json/include',r['options'])
                self.assertNotIn('/I$(ShipyardRoot)/platform/shipyard/json/include',r['options'])
            else:
                self.assertIn('/TC',r['options']);self.assertNotIn('/GR',r['options'])
        self.assertEqual(gen.project_option('/I$(XEDK)/include/xbox'), '"/I$(XEDK)/include/xbox"')
        self.assertNotEqual(gen.object_name('a/Json.cpp'),gen.object_name('b/json.cpp'))

    def test_default_cannot_link(self):
        xml = ET.fromstring(gen.project(self.manifest))
        guard = xml.find('{'+gen.NS+'}Target')
        self.assertIn('Lib',guard.attrib['BeforeTargets'])
        self.assertIn('Link',guard.attrib['BeforeTargets'])
        self.assertIsNotNone(guard.find('{'+gen.NS+'}Error'))

    def test_complete_logic_replaces_constructor_fragment(self):
        selected={r['source'] for r in self.manifest['sources']}
        self.assertIn('scratch/randomizer-logic-xdk/generated/soh/soh/Enhancements/randomizer/logic.cpp',selected)
        self.assertFalse(any(r.endswith('/LogicConstructor.cpp') for r in selected))
        self.assertEqual(sum(r['upstream_source']=='soh/soh/Enhancements/randomizer/logic.cpp' for r in self.manifest['sources']),1)

    def test_complete_save_and_settings_replace_fragments(self):
        selected={r['source'] for r in self.manifest['sources']}
        for name in ['SaveSerialization.cpp','LegacyConversion.cpp','SettingsConstructor.cpp','StaticHintInfo.cpp']:
            self.assertFalse(any(r.endswith('/'+name) for r in selected),name)
        for name in ['soh/soh/SaveManager.cpp','soh/soh/Enhancements/randomizer/settings.cpp']:
            self.assertEqual(sum(r['upstream_source']==name for r in self.manifest['sources']),1)
        self.assertIn('scratch/legacy-save-xdk/generated/LegacyDecode.cpp',selected)

    def test_preprocessed_probe_excluded_and_full_message_origin(self):
        source,language,options=gen.parse_command(dict(command=[str(gen.SDK/'bin/win32/cl.exe'),
            '/c','/TC',str(gen.ROOT/'scratch/ship-utils-xdk/xdk/c_abi.i'),'/Foignored.obj']))
        self.assertEqual(language,'c')
        self.assertEqual(source,'scratch/ship-utils-xdk/xdk/c_abi.i')
        selected={r['source'] for r in self.manifest['sources']}
        self.assertNotIn(source,selected)
        self.assertNotIn('scratch/custom-message-xdk/generated/literal_probe.cpp',selected)
        message=next(r for r in self.manifest['sources'] if r['subsystem']=='custom-message')
        self.assertEqual(message['upstream_source'],'soh/soh/Enhancements/custom-message/CustomMessageManager.cpp')

    def test_pinned_target_definitions_and_preprocessed_boundaries(self):
        binary=next(r for r in self.manifest['sources'] if r['subsystem']=='binary')
        self.assertIn('/DF3DEX_GBI_2',binary['options'])
        self.assertIn('/DGFX_DEBUG_DISASSEMBLER',binary['options'])
        game=next(r for r in self.manifest['sources'] if r['subsystem']=='game')
        self.assertTrue(all(c['action']=='regenerate_preprocessed_source' for c in game['target_definition_corrections']))
        self.assertNotIn('/DF3DEX_GBI_2',game['options'])  # Already applied before preprocessing.
        config=json.loads(gen.CONFIG.read_text())
        with self.assertRaisesRegex(ValueError,'Conflicting pinned target definition'):
            gen.target_definitions(config,'binary',dict(command=['/DCONTROLLERBUTTONS_T=uint16_t']),
                                   'scratch/binary.cpp',[])


def native():
    manifest=gen.collect()
    # Current binary classes, actual native support, and a genuine preprocessed C
    # game TU exercise /GR, path quoting, unique objects, and language separation.
    sources=[r for r in manifest['sources'] if r['subsystem'] in ('binary','logging')]
    sources += [next(r for r in manifest['sources'] if r['upstream_source']=='soh/src/code/sys_math.c')]
    sample=dict(manifest,sources=sources)
    gen.OUT.mkdir(parents=True,exist_ok=True)
    project=gen.OUT/'NativeValidation.vcxproj'
    project.write_bytes(gen.project(sample))
    command=['C:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe',str(project),
             '/p:Configuration=Release','/p:Platform=Xbox 360','/nologo','/verbosity:minimal']
    compile_result=subprocess.run(command+['/t:ClCompile'],cwd=gen.ROOT,capture_output=True,text=True)
    (gen.OUT/'native-validation.log').write_text(compile_result.stdout+compile_result.stderr,encoding='utf-8')
    if compile_result.returncode:
        raise RuntimeError('MSBuild compile failed; see scratch/project-xdk/native-validation.log')
    objects={}
    for source in sources:
        path=gen.OUT/'build/obj'/source['object']
        assert struct.unpack_from('<H',path.read_bytes())[0]==0x1f2
        objects[source['source']]=hashlib.sha256(path.read_bytes()).hexdigest()
    rejection=subprocess.run(command+['/t:Build'],cwd=gen.ROOT,capture_output=True,text=True)
    assert rejection.returncode and 'Compile-only port inventory' in rejection.stdout+rejection.stderr
    assert not list((gen.OUT/'build').glob('*.lib'))
    report=dict(compile_command=command+['/t:ClCompile'],compile_exit=compile_result.returncode,
        incomplete_build_rejected=True,object_sha256=objects,target_runtime_executed=False)
    (gen.OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Seven genuine C/C++ production TUs compiled via generated XDK project; incomplete Build rejected.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true');args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ProjectTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    if args.native:native()
