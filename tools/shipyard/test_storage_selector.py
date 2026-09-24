"""Exercise the pinned Shipyard XAM selector used by the SoH storage adapter."""
import json
from pathlib import Path
import subprocess
import sys

from platform_base import resolve

ROOT = Path(__file__).resolve().parents[2]
BASE = resolve(ROOT)
storage = (ROOT / 'platform/shipyard/save-storage/storage.cpp').read_text()
display = (BASE / 'sources/xenos/core.cpp').read_text()
assert 'SelectAndMount(policy, display)' in storage
assert '16 * 1024 * 1024, root, "3Shipsty", L"Ship of Harkinian"' in storage
assert 'XShowDeviceSelectorUI' not in storage
report = json.loads((ROOT / 'scratch/save-storage-xdk/xdk/build.json').read_text())
assert any(row['source'] == 'shipyard/sources/storage/device.cpp' and row['exit'] == 0 for row in report)
assert 'if(!xenos_device || !buffers.empty())return E_UNEXPECTED;' in display
assert 'xenos_device->Present(NULL,NULL,NULL,NULL)' in display
result = subprocess.run([sys.executable, '-B', str(BASE / 'tests/test_storage_device.py')],
                        capture_output=True, text=True)
assert result.returncode == 0, result.stdout + result.stderr
print(result.stdout.strip())
