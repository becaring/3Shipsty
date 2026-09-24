"""Modern Prism preparation must use the canonical Shipyard projector."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
import prepare_prism
from xbox360_platform.prism import PrismProjector


class ProjectionOwner(unittest.TestCase):
    def test_modern_adapter_uses_reviewed_shared_projector(self):
        self.assertIsInstance(prepare_prism.PROJECTOR, PrismProjector)
        self.assertEqual(prepare_prism.PROJECTOR.revision,
                         'bbcbc7e3f890a5806b579361e7aa0336acd547e7')


if __name__ == '__main__':
    unittest.main()
