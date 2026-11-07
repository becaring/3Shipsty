"""Check the per-profile save container policy and the linked shared selector contract."""
import json
from pathlib import Path
import subprocess
import sys

from platform_base import resolve

ROOT = Path(__file__).resolve().parents[2]
BASE = resolve(ROOT)
storage = (ROOT / 'platform/shipyard/save-storage/storage.cpp').read_text()
display = (BASE / 'sources/xenos/core.cpp').read_text()
assert storage.count('SelectAndMount(policy, display)') == 1
assert 'Fast::InitializeNativeDisplay, Fast::PresentNativeStartupUI' in storage
for directory in ('config', 'logs'):
    assert 'create_directories("game:\\\\' + directory + '");' in storage
assert 'return "shipyard:\\\\Save";' in storage
assert 'MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH' in storage
assert 'XShowDeviceSelectorUI' not in storage
report = json.loads((ROOT / 'scratch/save-storage-xdk/xdk/build.json').read_text())
assert any(row['source'] == 'shipyard/sources/storage/device.cpp' and row['exit'] == 0 for row in report)
assert any(row['source'] == 'platform/shipyard/save-storage/storage.cpp' and row['exit'] == 0 for row in report)
assert 'if(!xenos_device||!buffers.empty())returnE_UNEXPECTED;' in ''.join(display.split())
assert '::Shipyard::XenosPresentationChain().Present()' in display
result = subprocess.run([sys.executable, '-B', str(BASE / 'tests/test_storage_device.py')],
                        capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
print(result.stdout.strip())
