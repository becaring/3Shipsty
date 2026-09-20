"""Selection tests protect real application ownership and reproducibility."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'tools/shipyard/source_inventory.py'

class SelectionTests(unittest.TestCase):
    def load_inventory(self):
        self.assertTrue(SCRIPT.is_file(), 'source inventory generator is missing')
        spec = importlib.util.spec_from_file_location('source_inventory', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.inventory(ROOT)

    def test_actual_main_and_modern_features_are_selected(self):
        rows = {r['path']: r for r in self.load_inventory()['files']}
        for path in ('soh/src/code/main.c', 'soh/src/code/graph.c',
                     'soh/soh/OTRGlobals.cpp', 'soh/soh/SaveManager.cpp'):
            self.assertEqual(rows[path]['role'], 'application')
        for folder in ('soh/soh/Enhancements/randomizer/', 'soh/soh/SohGui/'):
            members = [r for p, r in rows.items() if p.startswith(folder)]
            self.assertTrue(members, folder)
            self.assertTrue(all(r['role'] == 'application' for r in members), folder)

    def test_upstream_exclusions_and_host_tools_remain_explicit(self):
        rows = {r['path']: r for r in self.load_inventory()['files']}
        self.assertEqual(rows['soh/src/libultra/gu/cosf.c']['role'], 'upstream-excluded')
        self.assertEqual(rows['soh/src/libultra/libc/sprintf.c']['role'], 'application')
        self.assertTrue(any(r['role'] == 'host-tool' for r in rows.values()))
        self.assertTrue(all(r['reason'] and len(r['sha256']) == 64 for r in rows.values()))

    def test_output_deterministic_and_paths_unique(self):
        a, b = self.load_inventory(), self.load_inventory()
        self.assertEqual(a, b)
        paths = [r['path'] for r in a['files']]
        self.assertEqual(paths, sorted(set(paths)))

if __name__ == '__main__':
    unittest.main()
