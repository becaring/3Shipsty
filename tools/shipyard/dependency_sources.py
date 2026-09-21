"""Verify owned dependency snapshots against committed receipts before use."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def verified(name):
    lock = json.loads((ROOT / 'platform/shipyard/dependencies.lock.json').read_text())[name]
    receipt_path = ROOT / 'scratch/deps' / (name + '-receipt.json')
    if hashlib.sha256(receipt_path.read_bytes()).hexdigest() != lock['receipt_sha256']:
        raise ValueError('Dependency receipt drift: ' + name)
    receipt = json.loads(receipt_path.read_text())
    folder = ROOT / 'scratch/deps' / name
    for relative, expected in receipt['files'].items():
        if hashlib.sha256((folder / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Dependency source drift: ' + name + '/' + relative)
    return folder
