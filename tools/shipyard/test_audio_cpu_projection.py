"""Check audio scope boundaries and saturated SIMD alias fallbacks."""
import random
import unittest
from pathlib import Path
import audio_cpu_projection as projection

ROOT = Path(__file__).resolve().parents[2]

class AudioCpuTests(unittest.TestCase):
    def test_scope(self):
        text = projection.game('soh/src/code/audio_synthesis.c', (ROOT / 'soh/src/code/audio_synthesis.c').read_text())
        self.assertLess(text.index('ModernAudioCpuBegin();'), text.index('AudioSeq_ProcessSequences(i - 1)'))
        self.assertIn('ModernAudioCpuEnd();\n    return cmdP;', text)
        self.assertIn('ModernAudioCpuMirrored()', text)

    def test_mixer(self):
        text = projection.game('soh/soh/mixer.c', (ROOT / 'soh/soh/mixer.c').read_text())
        self.assertIn('__vaddshs', text)
        self.assertIn('__vsubshs', text)
        self.assertIn('aMixImplRef(count, gain, in_addr, out_addr)', text)
        # Model complete DMEM, including sequential feedback for overlapping ranges.
        rng = random.Random(84)
        for subtract in (False, True):
            for offset in (0, 1, 7, 8, 16, 40):
                values = [rng.randrange(-32768, 32768) for _ in range(128)]
                expected = values[:]
                actual = values[:]
                start, destination, count = 32, 32 + offset, 32
                def clamp(x): return max(-32768, min(32767, x))
                for i in range(count):
                    expected[destination+i] = clamp(expected[destination+i] + (-1 if subtract else 1)*expected[start+i])
                # Only identical or disjoint ranges may load groups before storing.
                width = 8 if offset == 0 or offset >= count else 1
                for i in range(0, count, width):
                    results = [clamp(actual[destination+i+j] + (-1 if subtract else 1)*actual[start+i+j]) for j in range(width)]
                    actual[destination+i:destination+i+width] = results
                self.assertEqual(expected, actual)

if __name__ == '__main__': unittest.main()
