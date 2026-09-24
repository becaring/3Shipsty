"""Locate and verify the independently cloned Xbox 360 platform base."""

import json
import os
from pathlib import Path
import sys


def resolve(root: Path) -> Path:
    lock_path = root / 'platform-base.lock.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    location = os.environ.get('XBOX360_PLATFORM_BASE')
    base = (Path(location) if location else root / lock['base']).resolve()
    if not (base / 'python/xbox360_platform/contract.py').is_file():
        raise FileNotFoundError('Xbox 360 platform base not found: ' + str(base))
    sys.path.insert(0, str(base / 'python'))
    from xbox360_platform.contract import verify
    verify(base, lock_path)
    return base
