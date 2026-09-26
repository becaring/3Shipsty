"""The game framebuffer owns 1080p depth; the presentation target does not."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INTERPRETER = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'


class ModernPresentationDepthTests(unittest.TestCase):
    def test_endframe_discard_only_when_game_has_separate_framebuffer(self):
        source = INTERPRETER.read_text(encoding='utf-8', errors='replace')
        end = source.split('void Interpreter::EndFrame() {', 1)[1].split('\nvoid Interpreter::', 1)[0]
        self.assertIn('if (mRendersToFb)', end)
        self.assertIn('Fast::ShipyardXenos::DiscardPresentationDepthOnEnd();', end)
        self.assertLess(end.index('DiscardPresentationDepthOnEnd();'), end.index('mRapi->EndFrame()'))


if __name__ == '__main__':
    unittest.main()
