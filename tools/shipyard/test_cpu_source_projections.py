"""CPU materialization preserves inputs, source hashes and public declarations."""
import hashlib
from pathlib import Path
import tempfile
import unittest

import cpu_source_projections as cpu
import generate_xdk_project as gen


class CpuSourceTests(unittest.TestCase):
    def test_materialized_sources_retain_verified_input_provenance(self):
        names = ('platform/shipyard/xenos/services.cpp',)
        with tempfile.TemporaryDirectory(dir=gen.ROOT / 'scratch') as directory:
            root = Path(directory)
            service = root / names[0]
            service.parent.mkdir(parents=True)
            service.write_bytes((gen.ROOT / names[0]).read_bytes())
            for name in names:
                original = gen.PLATFORM_BASE / name[9:] if name.startswith('shipyard/') else root / name
                before = original.read_bytes()
                output, provenance = cpu.materialize(name, root, gen.PLATFORM_BASE)
                self.assertNotEqual(output, name)
                self.assertEqual(provenance['source'], name)
                self.assertEqual(provenance['sha256'], hashlib.sha256(before).hexdigest())
                self.assertEqual(provenance['include_directory'], original.parent.as_posix())
                self.assertEqual(original.read_bytes(), before)
                projected = root / output
                stamp = projected.stat().st_mtime_ns
                self.assertEqual(cpu.materialize(name, root, gen.PLATFORM_BASE), (output, provenance))
                self.assertEqual(projected.stat().st_mtime_ns, stamp)
            # Shipyard's native.cpp owns wait-event reuse; it compiles unprojected.
            native = 'shipyard/sources/async/native.cpp'
            self.assertEqual(cpu.materialize(native, root, gen.PLATFORM_BASE), (native, None))
            self.assertIn('WaitEventScope waitEventScope;', (gen.PLATFORM_BASE / 'sources/async/native.cpp').read_text())
            self.assertEqual(cpu.materialize('unmodified.cpp', root, gen.PLATFORM_BASE), ('unmodified.cpp', None))

    def test_profile_header_preserves_declarations_and_layout(self):
        with tempfile.TemporaryDirectory(dir=gen.ROOT / 'scratch') as directory:
            root = Path(directory)
            original = root / 'platform/shipyard/application/thread_profile.h'
            original.parent.mkdir(parents=True)
            data = (gen.ROOT / original.relative_to(root)).read_bytes()
            original.write_bytes(data)
            include, provenance = cpu.materialize_headers(root)
            output = root / provenance['output']
            self.assertEqual(output, root / include / 'application/thread_profile.h')
            self.assertEqual(provenance['source_sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(provenance['output_sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
            before = data.decode('utf-8-sig').replace('\r\n', '\n')
            after = output.read_text()
            # Constructor and reset bodies are the only changes: fields, types,
            # member signatures and free-function declarations must stay exact.
            restored = after.replace('ThreadSample() { memset(this, 0, sizeof(*this)); }',
                                     'ThreadSample() { Reset(false); }')
            restored = restored.replace('        if (!requested) { enabled = false; return; }\n', '')
            self.assertEqual(restored, before)
            self.assertEqual(original.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
