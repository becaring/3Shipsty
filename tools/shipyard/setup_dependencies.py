"""Acquire or verify the exact dependency snapshots used by Xbox generators.

Each snapshot is made from a clean Git archive at the locked commit. The
committed receipt hash and every archived byte are checked before success.
"""

import argparse
import json
import subprocess
from pathlib import Path

from dependency_sources import ROOT, verified
from snapshot_dependency import snapshot


LOCK = ROOT / "platform/shipyard/dependencies.lock.json"
REPOSITORIES = ROOT / "scratch/dependency-repositories"


def git(repository, *args):
    command = ["git", "-c", "safe.directory=" + repository.resolve().as_posix(),
               "-C", str(repository), *args]
    return subprocess.check_output(command, text=True).strip()


def acquire(name, entry):
    repository = REPOSITORIES / name
    if not repository.exists():
        repository.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", entry["url"], str(repository)], check=True)
    if git(repository, "remote", "get-url", "origin") != entry["url"]:
        raise ValueError("Dependency URL drift: " + name)
    if git(repository, "status", "--porcelain"):
        raise ValueError("Dependency checkout is modified: " + name)
    revision = entry["commit"]
    found = subprocess.run(["git", "-c", "safe.directory=" + repository.resolve().as_posix(),
                            "-C", str(repository), "cat-file", "-e", revision + "^{commit}"],
                           capture_output=True)
    if found.returncode:
        git(repository, "fetch", "origin", revision)
    git(repository, "checkout", "--detach", revision)
    if git(repository, "rev-parse", "HEAD") != revision:
        raise ValueError("Dependency revision drift: " + name)
    snapshot(repository, name, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    entries = json.loads(LOCK.read_text(encoding="utf-8"))
    for name, entry in entries.items():
        if not args.verify_only:
            try:
                verified(name)
            except (FileNotFoundError, ValueError):
                acquire(name, entry)
        verified(name)
        print(name + ": locked snapshot verified", flush=True)


if __name__ == "__main__":
    main()
