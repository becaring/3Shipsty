"""Reproducibility and fail-closed checks for full current resource projection."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
import prepare_resource_manager as projection


class GenerationTests(unittest.TestCase):
    def test_reproducible_complete_tus(self):
        projection.prepare()
        manifest=(projection.OUT/'manifest.json').read_bytes()
        projection.prepare()
        self.assertEqual(manifest,(projection.OUT/'manifest.json').read_bytes())
        for unit in projection.UNITS:
            self.assertTrue((projection.OUT/'generated/src/ship'/unit).is_file())

    def test_source_drift_rejected_before_output(self):
        before=(projection.OUT/'manifest.json').read_bytes()
        original=Path.read_text
        source=ROOT/'libultraship/include/ship/Context.h'
        def changed(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            return value+'\n// changed input\n' if path==source else value
        with patch.object(Path,'read_text',changed):
            with self.assertRaisesRegex(ValueError,'Source drift'):projection.prepare()
        self.assertEqual(before,(projection.OUT/'manifest.json').read_bytes())


if __name__=='__main__':unittest.main()
