"""The optional game-frame clear must not alter GUI or explicit framebuffer draws."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_fast3d import OUT, prepare


def method(source, start, end):
    first = source.index(start)
    return source[first:source.index(end, first)]


class FullColorClearProfileTests(unittest.TestCase):
    def test_only_game_run_has_opt_in_full_color_clear(self):
        prepare()
        source = (OUT / 'generated/src/fast/interpreter.cpp').read_text()
        run = method(source, 'void Interpreter::Run(Gfx* commands,', '\nvoid Interpreter::EndFrame()')
        gui = method(source, 'void Interpreter::RunGuiOnly() {', '\nvoid Interpreter::Run(Gfx* commands,')
        transfer = method(source, 'void Interpreter::SetFrameBuffer(', '\nvoid Interpreter::CopyFrameBuffer(')

        self.assertEqual(source.count('CVarGetInteger("gSettings.XboxFullColorClearProfile", 0)'), 1)
        self.assertIn('const bool xboxFullColorClear =\n', run)
        self.assertIn('mRapi->ClearFramebuffer(xboxFullColorClear, true)', run)
        self.assertNotIn('mRapi->ClearFramebuffer(false, true)', run)
        self.assertEqual(gui.count('mRapi->ClearFramebuffer(false, true)'), 1)
        self.assertEqual(transfer.count('mRapi->ClearFramebuffer(false, true)'), 1)
        self.assertNotIn('xboxFullColorClear', gui + transfer)
        self.assertIn('#include "libultraship/bridge/consolevariablebridge.h"', source)

    def test_tiling_guard_trial_is_opt_in_on_render_thread(self):
        prepare()
        source = (OUT / 'generated/src/fast/interpreter.cpp').read_text()
        run = method(source, 'void Interpreter::Run(Gfx* commands,', '\nvoid Interpreter::EndFrame()')
        gui = method(source, 'void Interpreter::RunGuiOnly() {', '\nvoid Interpreter::Run(Gfx* commands,')

        self.assertEqual(source.count('CVarGetInteger("gSettings.XboxTilingGuardTrialProfile", 0)'), 1)
        self.assertIn('Fast::ShipyardXenos::SetTilingGuardTrialEnabled(', run)
        self.assertLess(run.index('SetTilingGuardTrialEnabled('), run.index('mRapi->StartFrame()'))
        self.assertNotIn('SetTilingGuardTrialEnabled', gui)


if __name__ == '__main__':
    unittest.main()
