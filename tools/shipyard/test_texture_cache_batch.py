"""The owned texture lookup cache persists until the lookup generation moves."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INTERPRETER = ROOT / 'scratch/fast3d-xdk/generated/src/fast/interpreter.cpp'
APPLICATION = ROOT / 'scratch/application-xdk/generated/soh/soh/OTRGlobals.cpp'


def body_between(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


class TextureCacheBatchTests(unittest.TestCase):
    def test_cache_survives_replay_reset_but_not_gui_or_explicit_invalidation(self):
        source = INTERPRETER.read_text(encoding='utf-8', errors='replace')
        reset = body_between(source, 'void Interpreter::SpReset() {', '\nvoid Interpreter::')
        gui = body_between(source, 'void Interpreter::RunGuiOnly() {', '\nvoid Interpreter::')
        clear = body_between(source, 'void Interpreter::TextureCacheClear() {', '\nvoid Interpreter::')
        delete = body_between(source, 'void Interpreter::TextureCacheDelete(', '\nvoid Interpreter::')
        self.assertNotIn('mXboxTextureHashCache.Clear();', reset)
        self.assertLess(gui.index('mXboxTextureHashCache.Clear();'), gui.index('SpReset();'))
        self.assertIn('mXboxTextureHashCache.Clear();', clear)
        self.assertIn('mXboxTextureHashCache.Clear();', delete)

    def test_batch_boundary_retires_moved_generation_before_replays(self):
        source = APPLICATION.read_text(encoding='utf-8', errors='replace')
        batch = body_between(source, 'intp->mInterpolationIndex = 0;', '\n    ImGui::PopStyleColor();')
        self.assertNotIn('intp->mXboxTextureHashCache.Clear();', batch)
        self.assertLess(batch.index('intp->mXboxTextureHashCache.Retire('),
                        batch.index('for ('),
                        'retirement must precede the replay loop, which may skip a draw')


if __name__ == '__main__':
    unittest.main()
