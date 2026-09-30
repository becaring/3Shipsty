"""Actual preset, config mutation, CVar reload and menu selection contracts.

Persistence is a serialized JSON boundary here; filesystem error/atomic-write
behavior belongs to the configuration contract. No game/renderer is required.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment
from prepare_application_extras import prepare
from prepare_console_variables import prepare as prepare_cvars
from prepare_configuration import prepare as prepare_config


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


class PresetRuntimeTests(unittest.TestCase):
    def test_apply_reload_hooks_menu_and_restart(self):
        prepare(); prepare_cvars(); prepare_config()
        preset = (ROOT / 'scratch/application-extras-xdk/generated/soh/soh/Enhancements/Presets/Presets.cpp').read_text()
        config = (ROOT / 'scratch/configuration-xdk/generated/src/ship/config/Config.cpp').read_text()
        cvars = (ROOT / 'scratch/console-variables-xdk/generated/src/ship/config/ConsoleVariable.cpp').read_text()
        menu = (ROOT / 'soh/soh/SohGui/Menu.cpp').read_text()
        replacements = {
            '@APPLY@': between(preset, 'void applyPreset(', '\nvoid DrawPresetSelector('),
            '@SET_BLOCK@': between(config, 'void Config::SetBlock(', '\nvoid Config::EraseBlock('),
            '@ERASE_BLOCK@': between(config, 'void Config::EraseBlock(', '\nvoid Config::Copy('),
            '@LOAD@': between(cvars, 'void ConsoleVariable::Load()', '\nvoid ConsoleVariable::LoadLegacy()'),
            '@HEADER@': next(line.strip() for line in menu.splitlines() if 'std::string headerIndex = CVarGetString' in line),
            '@SIDEBAR@': between(menu, '    std::string sectionIndex = CVarGetString(sidebarCvar', '    float sectionCenterX'),
        }
        code = (Path(__file__).with_name('test_preset_runtime_contract.cpp')).read_text()
        for key, value in replacements.items():
            code = code.replace(key, value)
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as folder:
            folder = Path(folder)
            source = folder / 'preset.cpp'
            source.write_text(code)
            exe = folder / 'preset.exe'
            result = subprocess.run([str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD',
                '/I' + str(ROOT / 'platform/shipyard/json/upstream/include'),
                '/I' + str(ROOT / 'soh'), str(source), '/Fe:' + str(exe)],
                cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe), str(ROOT / 'soh/assets/custom/presets/Enhancements - Curated First Time Vanilla.json')],
                cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('preset runtime PASS', result.stdout)
