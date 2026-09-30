"""Exercise first-clone acquisition and preservation of modified checkouts."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_dependencies as setup


class DependencySetupTests(unittest.TestCase):
    def test_fresh_acquisition_and_modified_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            donor = root / 'donor'
            donor.mkdir()
            subprocess.run(['git', 'init', str(donor)], check=True, capture_output=True)
            (donor / 'source.txt').write_text('locked source\n')
            setup.git(donor, 'add', 'source.txt')
            setup.git(donor, '-c', 'user.name=Dependency fixture', '-c',
                      'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
            revision = setup.git(donor, 'rev-parse', 'HEAD')
            entry = dict(url=donor.as_uri(), commit=revision)
            with patch.object(setup, 'REPOSITORIES', root / 'repositories'), \
                    patch.object(setup, 'snapshot') as snapshot:
                setup.acquire('fixture', entry)
                checkout = root / 'repositories/fixture'
                self.assertEqual(setup.git(checkout, 'status', '--porcelain'), '')
                self.assertEqual((checkout / 'source.txt').read_text(), 'locked source\n')
                snapshot.assert_called_once_with(checkout, 'fixture', revision)
                (checkout / 'source.txt').write_text('local edit\n')
                with self.assertRaisesRegex(ValueError, 'Dependency checkout is modified'):
                    setup.acquire('fixture', entry)
                self.assertEqual((checkout / 'source.txt').read_text(), 'local edit\n')
                self.assertEqual(snapshot.call_count, 1)


if __name__ == '__main__':
    unittest.main()
