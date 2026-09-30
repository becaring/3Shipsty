"""The Xbox GUI projection profiles only Gui::StartDraw's three coarse calls."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_gui import transform


class GuiStartProfileTests(unittest.TestCase):
    def test_start_draw_subphases(self):
        path = ROOT / 'libultraship/src/ship/window/gui/Gui.cpp'
        output = transform('ship/window/gui/Gui.cpp', path.read_text())
        start = output.split('void Gui::StartDraw() {', 1)[1].split('\n}\n', 1)[0]
        for call, phase in (
            ('StartFrame();', 'GuiStartFrame'),
            ('DrawMenu();', 'GuiDrawMenu'),
            ('CalculateGameViewport();', 'GuiViewport'),
        ):
            with self.subTest(phase=phase):
                begin = 'ModernFrameProfile::Begin(ModernFrameProfile::' + phase + ');'
                end = 'ModernFrameProfile::End(ModernFrameProfile::' + phase + ');'
                self.assertEqual(output.count(begin), 1)
                self.assertEqual(output.count(end), 1)
                self.assertLess(start.index(begin), start.index(call))
                self.assertLess(start.index(call), start.index(end))


if __name__ == '__main__':
    unittest.main()
