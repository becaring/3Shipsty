import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import prepare_imgui


class ImGuiGeneration(unittest.TestCase):
    def test_deterministic_current_release_library(self):
        first = prepare_imgui.prepare()
        self.assertEqual(first, prepare_imgui.prepare())
        self.assertEqual(len(first['units']), 5)
        for name in first['units']:
            self.assertIn(name + '.cpp', first['outputs'])

    def test_native_config_preserves_release_texture_abi(self):
        prepare_imgui.prepare()
        original = (prepare_imgui.OUT / 'original/imconfig.h').read_text()
        generated = (prepare_imgui.OUT / 'generated/imconfig.h').read_text()
        self.assertIn('#define ImTextureID void*', original)
        self.assertIn('#define IMGUI_DEFINE_MATH_OPERATORS', original)
        self.assertIn('#define ImTextureID void*', generated)
        self.assertNotRegex(generated, r'(?m)^\s*#define IMGUI_DISABLE_DEMO_WINDOWS')
        self.assertNotRegex(generated, r'(?m)^\s*#define IMGUI_DISABLE_OBSOLETE_FUNCTIONS')


if __name__ == '__main__': unittest.main()
