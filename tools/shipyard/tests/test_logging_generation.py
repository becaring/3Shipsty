from pathlib import Path
import importlib.util,sys,unittest,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('prepare_logging',ROOT/'tools/shipyard/prepare_logging.py')
projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)

class Generation(unittest.TestCase):
    def test_dependency_source_locks(self):
        projection.validate_inputs()
    def test_repeated_generation(self):
        def generate():
            subprocess.run([sys.executable,'-B',str(ROOT/'tools/shipyard/prepare_logging.py')],check=True,capture_output=True)
            files=[]
            for name in ('core-include','include'):
                files.extend((ROOT/'scratch/logging-xdk'/name).rglob('*'))
            return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
        self.assertEqual(generate(),generate())
    def test_source_changed_rejected_before_generation(self):
        # Supply an altered byte reader, never modify even the owned dependency.
        from unittest.mock import patch
        read=Path.read_bytes
        def changed(path):
            data=read(path)
            return data+b'\n' if path.name=='logger.h' else data
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'Pinned spdlog source changed'):
                projection.validate_inputs()
    def test_modern_float_source_changed_rejected(self):
        from unittest.mock import patch
        read=Path.read_bytes
        def changed(path):
            data=read(path)
            return data+b'\n' if path.name=='format-inl.h' else data
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'Pinned float source changed'):
                projection.validate_inputs()
    def test_float_cache_is_constant_pod_and_float_keeps_its_type(self):
        subprocess.run([sys.executable,'-B',str(ROOT/'tools/shipyard/prepare_logging.py')],check=True,capture_output=True)
        base=ROOT/'scratch/logging-xdk/include'
        algorithm=(base/'shipyard_fmt_float.h').read_text()
        formatter=(base/'fmt/format.h').read_text()
        self.assertIn('static const uint64_t pow10_significands[][2]',algorithm)
        self.assertNotIn('static const uint128_fallback pow10_significands',algorithm)
        self.assertIn('FMT_MAKE_VALUE(float, float_value, FLOAT)',formatter)
        self.assertIn('# include <fmt/format.cc>',formatter)

if __name__=='__main__':unittest.main()
