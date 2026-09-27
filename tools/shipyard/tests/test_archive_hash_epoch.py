"""Keep the projected archive hash epoch tied to every map mutation."""
from pathlib import Path
import ast
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
PROJECTOR = ROOT / 'tools/shipyard/prepare_resource_manager.py'


def epoch_helpers():
    # The selected Shipyard lock can advance independently while this Modern
    # projection is developed. Execute only these pure projector functions.
    tree = ast.parse(PROJECTOR.read_text())
    names = {'once', 'archive_hash_epoch_header', 'archive_hash_epoch_source'}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PROJECTOR), 'exec'), namespace)
    return namespace


class ArchiveHashEpoch(unittest.TestCase):
    def setUp(self):
        self.header = (ROOT / 'libultraship/include/ship/resource/archive/ArchiveManager.h').read_text()
        self.source = (ROOT / 'libultraship/src/ship/resource/archive/ArchiveManager.cpp').read_text()
        self.helpers = epoch_helpers()

    def test_all_hash_map_mutations_advance_epoch(self):
        header = self.helpers['archive_hash_epoch_header'](self.header)
        source = self.helpers['archive_hash_epoch_source'](self.source)
        self.assertIn('unsigned GetXboxHashEpoch() const;', header)
        self.assertIn('volatile long mXboxHashEpoch;', header)
        self.assertIn('ArchiveManager::ArchiveManager() : mXboxHashEpoch(1)', source)
        self.assertIn('unsigned ArchiveManager::GetXboxHashEpoch() const', source)
        self.assertEqual(source.count('InterlockedIncrement(&mXboxHashEpoch);'), 3)
        self.assertIn('InterlockedIncrement(&mXboxHashEpoch);\n    mHashes.clear();', source)
        self.assertIn('InterlockedIncrement(&mXboxHashEpoch);\n            mHashes[hash] = filePath;', source)
        self.assertIn('InterlockedIncrement(&mXboxHashEpoch);\n    for (auto& [hash, filename]', source)

    def test_unknown_hash_map_mutation_fails_closed(self):
        changed = self.source.replace('    mHashes.clear();', '    mHashes[999] = "new";\n    mHashes.clear();')
        with self.assertRaisesRegex(ValueError, 'hash map mutation inventory'):
            self.helpers['archive_hash_epoch_source'](changed)

    def test_full_archive_projection_exposes_epoch(self):
        sys.path.insert(0, str(ROOT / 'tools/shipyard'))
        import prepare_resource_manager
        header = prepare_resource_manager.transform(
            'include/ship/resource/archive/ArchiveManager.h', self.header)
        source = prepare_resource_manager.transform(
            'src/ship/resource/archive/ArchiveManager.cpp', self.source)
        self.assertIn('unsigned GetXboxHashEpoch() const;', header)
        self.assertIn('unsigned ArchiveManager::GetXboxHashEpoch() const', source)
        self.assertEqual(source.count('InterlockedIncrement(&mXboxHashEpoch);'), 3)

    def test_fast3d_uses_epoch_only_after_existing_owner_and_profile_projection(self):
        projector = (ROOT / 'tools/shipyard/prepare_fast3d.py').read_text()
        self.assertIn('texture_hash_epoch_handler)', projector)
        self.assertLess(projector.index('    text=profile_interpreter(text)'),
                        projector.index('    text=texture_hash_borrowed_handler(text)'))
        self.assertLess(projector.index('    text=texture_hash_borrowed_handler(text)'),
                        projector.index('    text=texture_hash_epoch_handler(text)'))


if __name__ == '__main__':
    unittest.main()
