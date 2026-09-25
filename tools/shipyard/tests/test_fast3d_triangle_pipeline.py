import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve
BASE = resolve(ROOT)
from prepare_window import includes
from tools.shipyard.tests.test_binary import host_environment
import prepare_fast3d
PROJECTION = ROOT / 'platform/shipyard/fast3d/triangle_pipeline_projection.py'
INTERPRETER = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'


class TrianglePipelineTests(unittest.TestCase):
    def test_modern_trait_key_mutations(self):
        compiler, environment = host_environment()
        roots = [ROOT / 'scratch/fast3d-xdk/generated/include', ROOT / 'platform/shipyard',
                 BASE / 'sources', ROOT / 'scratch/gui-resources-xdk/generated/include', *includes()]
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as directory:
            executable = Path(directory) / 'triangle_key.exe'
            command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/DNOMINMAX']
            command += ['/I' + str(path) for path in roots]
            command += [str(Path(__file__).with_suffix('.cpp').with_name('test_fast3d_triangle_key.cpp')),
                        '/Fe:' + str(executable)]
            built = subprocess.run(command, cwd=directory, env=environment, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([str(executable)], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS modern triangle certificate trait/key mutations', result.stdout)

    def test_cold_reconciliation_and_live_geometry_are_preserved(self):
        projection = runpy.run_path(str(PROJECTION))
        original = (ROOT / 'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        original = runpy.run_path(str(ROOT / 'platform/shipyard/fast3d/vertex_packing.py'))['transform'](original)
        original = prepare_fast3d.triangle_split(original)
        original = prepare_fast3d.texture_bindings(original)
        start = original.index(projection['BEGIN'])
        end = original.index(projection['END'], start)
        changed = projection['transform'](original)
        cold = changed.split('// SHIPYARD ORIGINAL RECONCILIATION BEGIN\n', 1)[1]
        cold = cold.split('// SHIPYARD ORIGINAL RECONCILIATION END', 1)[0]
        cold = projection['remove_invalidations'](cold)
        self.assertEqual(cold, original[start:end])
        next_method = '\nvoid Interpreter::GfxSpGeometryMode('
        self.assertEqual(original[end:original.index(next_method, end)],
                         changed[changed.index(projection['END']):changed.index(next_method, changed.index(projection['END']))])

    def test_clip_snapshot_refreshes_after_every_backend_init(self):
        source = INTERPRETER.read_text()
        init = source[source.index('void Interpreter::Init('):source.index('\nvoid Interpreter::',source.index('void Interpreter::Init(')+1)]
        self.assertLess(init.index('mRapi->Init()'),init.index('mXboxClipParameters = mRapi->GetClipParameters()'))
        self.assertEqual(init.count('mXboxClipParameters = mRapi->GetClipParameters()'),1)
        cold = source[source.index('void Interpreter::XboxPrepareTrianglePipeline('):source.index('\nvoid Interpreter::',source.index('void Interpreter::XboxPrepareTrianglePipeline(')+1)]
        self.assertIn('clip_parameters = mXboxClipParameters;',cold)
        self.assertNotIn('mRapi->GetClipParameters()',cold)


if __name__ == '__main__':
    unittest.main()
