"""Snapshot an exact clean Git dependency into owned scratch, read-only donor.

Git archive reads committed blobs, so generators never run in reference trees.
The resulting receipt records the commit and every copied byte hash. Local
snapshotting is an acquisition optimization, not dependency ownership by donor.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def snapshot(repository, name, revision):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name):
        raise ValueError('Invalid dependency name')
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    git = ['git', '-c', 'safe.directory=' + repository.resolve().as_posix(),
           '-C', str(repository)]
    def read(*args):
        return subprocess.check_output(git + list(args), env=environment)
    actual = read('rev-parse', revision + '^{commit}').decode().strip()
    if actual != revision:
        raise ValueError('Dependency revision is not an exact commit')
    if read('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Dependency source is modified')
    source = read('archive', '--format=zip', revision)
    target = ROOT / 'scratch/deps' / name
    files = {}
    ready = []
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            path = (target / entry.filename).resolve()
            if not path.is_relative_to(target.resolve()):
                raise ValueError('Archive escaped owned dependency')
            data = archive.read(entry)
            ready.append((path, data))
            files[entry.filename] = hashlib.sha256(data).hexdigest()
    for path, data in ready:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    receipt = dict(name=name, commit=actual, url=read('remote', 'get-url', 'origin').decode().strip(),
                   acquisition='git archive from read-only clean local reference', files=files)
    output = ROOT / 'scratch/deps' / (name + '-receipt.json')
    output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'{name}: {actual}, {len(files)} files, receipt {hashlib.sha256(output.read_bytes()).hexdigest()}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    parser.add_argument('name')
    parser.add_argument('revision')
    args = parser.parse_args()
    snapshot(args.repository, args.name, args.revision)
