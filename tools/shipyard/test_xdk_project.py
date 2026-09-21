"""Deterministic inventory, omission guards, and optional real MSBuild XDK smoke build."""
import argparse
import copy
import hashlib
import json
import struct
import subprocess
import unittest
import xml.etree.ElementTree as ET

import generate_xdk_project as gen


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = gen.collect()

    def test_reproducible_project(self):
        self.assertEqual(gen.project(self.manifest), gen.project(copy.deepcopy(self.manifest)))
        xml = ET.fromstring(gen.project(self.manifest))
        items = xml.findall('.//{'+gen.NS+'}ClCompile[@Include]')
        self.assertEqual(len(items), len(self.manifest['sources']))
        self.assertEqual(len({r['object'] for r in self.manifest['sources']}), len(items))

    def test_complete_application_inventory(self):
        app = [r for r in self.manifest['coverage'] if r['role']=='application']
        self.assertEqual(len(app), 1094)
        self.assertEqual(sum(r['path'].endswith('.c') for r in app), 696)
        self.assertEqual(sum(r['path'].endswith('.cpp') for r in app), 398)
        self.assertTrue(any(r['status']=='pending' for r in app))
        self.assertFalse(any(r['status']=='excluded' for r in app))
        self.assertFalse(self.manifest['final_application_ready'])

    def test_new_source_is_pending_and_removed_projection_detectable(self):
        files = self.manifest['coverage'] + [dict(path='soh/soh/NewFeature.cpp',role='application')]
        updated = gen.coverage(files, self.manifest['sources'])
        self.assertEqual(updated[-1]['status'], 'pending')
        existing = next(r for r in self.manifest['sources'] if r['upstream_source'] and r['subsystem']=='game')
        updated = gen.coverage(files, [r for r in self.manifest['sources'] if r is not existing])
        self.assertEqual(next(r for r in updated if r['path']==existing['upstream_source'])['status'], 'pending')

    def test_compile_contract(self):
        self.assertNotIn('scratch/graphics-xdk/cc_features.cpp', {r['source'] for r in self.manifest['sources']})
        for r in self.manifest['sources']:
            self.assertTrue(r['requires_fresh_build'])
            self.assertNotIn('/tests/', r['source'])
            self.assertFalse(r['source'].startswith('tools/'))
            self.assertFalse(r['source'].endswith(('contract.cpp','xdk_abi.cpp')))
            if r['language']=='cpp':
                self.assertIn('/GR',r['options']);self.assertIn('/TP',r['options'])
                self.assertNotIn('/TC',r['options'])
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
