"""Boundaries for sampled Modern Fast3D cold-pipeline timing."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_phase_profile_projection import transform, remove_instrumentation, METHOD_START, METHOD_END
from profile_caller_guard_projection import remove_instrumentation as remove_caller_guards


class PipelinePhaseProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generated = (ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp').read_text()
        cls.source = remove_instrumentation(remove_caller_guards(generated))

    def test_stage_boundaries_and_roundtrip(self):
        changed = transform(self.source)
        self.assertEqual(remove_instrumentation(changed), self.source)
        method = changed.split(METHOD_START, 1)[1].split(METHOD_END, 1)[0]
        self.assertEqual(method.count('BeginPipelinePreparation(xboxPrepSample)'), 1)
        self.assertEqual(method.count('EnterPipelineTextureImport(xboxPrepSample)'), 1)
        self.assertEqual(method.count('ExitPipelineTextureImport(xboxPrepSample)'), 1)
        self.assertEqual(method.count('EndPipelinePreparation(xboxPrepSample)'), 1)
        self.assertLess(method.index('BeginPipelinePreparation(xboxPrepSample)'),
                        method.index('mXboxPipelineKey.valid=false;'))
        self.assertLess(method.index('LookupOrCreateColorCombiner(key);'),
                        method.index('PipelineGeometrySampler'))
        self.assertLess(method.index('PipelineGeometrySampler'),
                        method.index('if (mRdp->textures_changed[i]) {'))
        self.assertLess(method.index('EnterPipelineTextureImport(xboxPrepSample)'),
                        method.index('ImportTexture(i, tile, false);'))
        self.assertLess(method.index('mRdp->textures_changed[i] = false;'),
                        method.index('ExitPipelineTextureImport(xboxPrepSample)'))
        self.assertLess(method.index('PipelineShaderTransitions'),
                        method.index('struct ShaderProgram* prg = comb->prg[tm];'))
        self.assertLess(method.index('PipelineFinalCapture'),
                        method.index('XboxTrianglePipelineResult& p=mXboxPipelineResult;'))
        self.assertLess(method.index('mXboxPipelineKey.Capture(*this,p);'),
                        method.index('EndPipelinePreparation(xboxPrepSample)'))

    def test_idempotence_and_fail_closed_anchor(self):
        once = transform(self.source)
        self.assertEqual(transform(once), once)
        with self.assertRaises(ValueError):
            transform(self.source.replace('LookupOrCreateColorCombiner(key);',
                                          'LookupOrCreateColorCombiner(changed);'))


if __name__ == '__main__':
    unittest.main()
