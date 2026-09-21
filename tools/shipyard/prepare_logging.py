"""Reproduce pinned spdlog core/queue projection for Shipyard XDK."""
from pathlib import Path
import runpy
import json
import hashlib

ROOT = Path(__file__).resolve().parents[2]

def validate_inputs():
    base=ROOT/'platform/shipyard/logging'
    for filename in ('source-lock.json','core-source-lock.json'):
        for rel,expected in json.loads((base/filename).read_text()).items():
            path=ROOT/'scratch/deps/spdlog/include'/('spdlog/'+rel if filename.startswith('core') else rel)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise ValueError('Pinned spdlog source changed: '+rel)
    for rel,expected in json.loads((base/'fmt-source-lock.json').read_text()).items():
        if hashlib.sha256((ROOT/'scratch/deps/fmt-xdk'/rel).read_bytes()).hexdigest()!=expected:
            raise ValueError('Pinned fmt compiler dependency changed: '+rel)

if __name__ == '__main__':
    validate_inputs()
    runpy.run_path(str(ROOT / 'platform/shipyard/logging/prepare_donor.py'), run_name='__main__')
