import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
SPEC = importlib.util.spec_from_file_location('filesystem_projection', Path(__file__).parents[1] / 'prepare_filesystem.py')
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)


class ProjectionTests(unittest.TestCase):
    def test_deterministic(self):
        with tempfile.TemporaryDirectory(dir=MODULE.OUT) as folder:
            out = Path(folder)
            MODULE.generate(out)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            MODULE.generate(out)
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})

    def test_source_drift_fails_closed(self):
        original = MODULE.normalized
        def changed(path):
            return original(path) + ('\n// drift' if path.as_posix().endswith(MODULE.DIRECTORY) else '')
        with patch.object(MODULE, 'normalized', changed), self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            MODULE.generate()

    def test_helper_drift_fails_closed(self):
        original = MODULE.normalized
        def changed(path):
            return original(path) + ('\n// drift' if path.name == 'filesystem.cpp' else '')
        with patch.object(MODULE, 'normalized', changed), self.assertRaisesRegex(ValueError, 'helper hash mismatch'):
            MODULE.generate()

    def test_output_boundary(self):
        with self.assertRaisesRegex(ValueError, 'owned scratch'):
            MODULE.generate(MODULE.ROOT / 'libultraship')

    def test_consumer_contracts_and_line_mapping(self):
        locks = json.loads((MODULE.OWN / 'sources.lock.json').read_text())
        self.assertIn('soh/soh/SaveManager.cpp', locks['sources'])
        self.assertIn('soh/soh/Enhancements/randomizer/randomizer.cpp', locks['sources'])
        self.assertIn('soh/soh/Enhancements/mod_menu.cpp', locks['sources'])
        projected = MODULE.transform(MODULE.normalized(MODULE.ROOT / MODULE.DIRECTORY))
        self.assertIn('#line', projected)
        self.assertIn('namespace fs = xbox_compat::filesystem;', projected)
        self.assertIn('catch (...) {}', projected)  # Preserve upstream behavior explicitly.
        self.assertNotIn('for (auto&', projected)

    def test_actual_runtime_namespace_hooks(self):
        for path in ['soh/soh/SaveManager.cpp', 'soh/soh/Enhancements/randomizer/randomizer.cpp',
                     'soh/soh/Enhancements/mod_menu.cpp']:
            original = MODULE.normalized(MODULE.ROOT / path)
            hooks = MODULE.projection_hooks(path, original)
            self.assertTrue(hooks['ready'])
            projected = MODULE.project_boundary(path, original)
            self.assertNotIn('std::filesystem', MODULE.code_mask(projected))
            for edit in hooks['edits']:
                self.assertEqual(original[edit['start']:edit['end']], edit['expected'])
                self.assertEqual(original.count('\n', 0, edit['start']) + 1, edit['line'])
        self.assertIn('xbox_compat::filesystem::directory_options::follow_directory_symlink', projected)

    def test_host_extraction_requires_explicit_routing(self):
        for path in ['soh/soh/Extractor/Extract.cpp', 'soh/soh/OTRGlobals.cpp']:
            original = MODULE.normalized(MODULE.ROOT / path)
            hooks = MODULE.projection_hooks(path, original)
            self.assertFalse(hooks['ready'])
            self.assertTrue(any(u['classification'] == 'host-extraction' for u in hooks['uses']))
            with self.assertRaisesRegex(ValueError, 'explicit routing'):
                MODULE.project_boundary(path, original)

    def test_comments_and_literals_are_not_rewritten(self):
        original = '// std::filesystem::copy\n"std::filesystem::path"; std::filesystem::exists(p);'
        masked = MODULE.code_mask(original)
        self.assertEqual(len(original), len(masked))
        self.assertNotIn('filesystem::copy', masked)
        self.assertNotIn('filesystem::path', masked)
        self.assertIn('filesystem::exists', masked)


if __name__ == '__main__': unittest.main()
