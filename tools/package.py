"""Assemble a 3Shipsty release folder from the linked XEX, the SoH 9.2.3 release files and the speech data.

    python -B tools/package.py --destination <new folder> [--release <SoH 9.2.3 folder>] [--allow-dirty] [--zip]

Writes <destination>/3Shipsty/ (XEX, soh.o2r, assets.zip, espeak-ng-data, shaders), and beside it README.txt,
SOURCE.txt, licenses/ and SHA256SUMS.txt; --zip also writes <destination>.zip with that content. The package holds
no ROM archives: the console builds them from the player's ROM. The release links GPL eSpeak NG, so SOURCE.txt
names the commits that are its corresponding source and a dirty tree is refused unless --allow-dirty is given.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from pack_assets import pack  # noqa: E402
from platform_base import resolve as resolve_platform_base  # noqa: E402

XEX = ROOT / "scratch/link-integration/3Shipsty.xex"
LINK_RECORD = ROOT / "scratch/link-integration/link-verification.json"
SPEECH = ROOT / "scratch/speech-xdk/host-ninja/espeak-ng-data"
SPEECH_MANIFEST = ROOT / "scratch/speech-xdk/data-manifest.json"
SHADER_PACK = ROOT / "scratch/shader-pack/3shipsty.shaderpack"

README = """3Shipsty for Xbox 360

Copy the 3Shipsty folder to your console and put your own Ocarina of Time ROM
(.z64, .n64 or .v64) beside 3Shipsty.xex. The first launch builds the game data
from your ROM, and later launches reuse it. A Master Quest ROM adds the Master
Quest dungeons. The package contains no ROM data. SHA256SUMS.txt lists the
hashes of the packaged files.

Back opens or closes the menu. The right stick moves the cursor, A clicks or
drags, B right-clicks, LT and RT scroll, and R3 switches between the cursor and
D-pad navigation. Mods go in a mods folder beside 3Shipsty.xex.

To report a problem, open a bug report at
https://github.com/becaring/3Shipsty/issues and attach the logs folder from the
3Shipsty folder as a zip.

3Shipsty is distributed under GPL-3.0-or-later because it links eSpeak NG.
SOURCE.txt names its source, and the licenses folder holds the licenses of
3Shipsty, Shipyard and the components they include.
"""


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *arguments):
    command = ["git", "-c", "safe.directory=*", "-C", str(root), *arguments]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def require(path):
    if not path.exists():
        raise SystemExit("missing input: " + str(path))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--release", type=Path, default=ROOT / "scratch/assets/official-9.2.3")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    out = args.destination.resolve()
    if out.exists() or (args.zip and out.with_suffix(".zip").exists()):
        raise SystemExit("package folder or zip exists: " + str(out))
    platform = resolve_platform_base(ROOT)
    dirty = [root for root in (ROOT, platform) if git(root, "status", "--porcelain", "--untracked-files=no")]
    if dirty and not args.allow_dirty:
        raise SystemExit("uncommitted changes in " + ", ".join(map(str, dirty)) + "; commit them or pass --allow-dirty")

    # Check every input before writing anything.
    if sha256(require(XEX)) != json.loads(require(LINK_RECORD).read_text())["xex_sha256"]:
        raise SystemExit("3Shipsty.xex does not match the link record; relink before packaging")
    speech = json.loads(require(SPEECH_MANIFEST).read_text())["files"]
    stale = [name for name, digest in speech.items() if not (SPEECH / name).is_file() or sha256(SPEECH / name) != digest]
    if stale:
        raise SystemExit("espeak-ng-data does not match the speech manifest: " + ", ".join(stale[:5]))
    licenses = json.loads((ROOT / "release-licenses.json").read_text())
    sources = {name: ROOT / path for name, path in licenses["repository"].items()}
    sources.update({name: platform / path for name, path in licenses["platform"].items()})
    for path in [*sources.values(), args.release / "soh.o2r", args.release / "assets", SHADER_PACK]:
        require(path)

    game = out / "3Shipsty"
    (game / "shaders").mkdir(parents=True)
    shutil.copy2(XEX, game / "3Shipsty.xex")
    shutil.copy2(args.release / "soh.o2r", game / "soh.o2r")
    pack(args.release / "assets", game / "assets.zip")
    (game / "espeak-ng-data").mkdir()
    for name in speech:
        (game / "espeak-ng-data" / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SPEECH / name, game / "espeak-ng-data" / name)
    shutil.copy2(SHADER_PACK, game / "shaders/3shipsty.shaderpack")
    (out / "licenses").mkdir()
    for name, path in sources.items():
        shutil.copy2(path, out / "licenses" / name)

    revision = git(ROOT, "rev-parse", "HEAD") + (" with local changes" if ROOT in dirty else "")
    platform_revision = git(platform, "rev-parse", "HEAD") + (" with local changes" if platform in dirty else "")
    speech_commit = json.loads(SPEECH_MANIFEST.read_text())["commit"]
    (out / "README.txt").write_text(README, encoding="utf-8", newline="\n")
    (out / "SOURCE.txt").write_text(
        "Corresponding source for this 3Shipsty package (GPL-3.0-or-later):\n\n"
        f"3Shipsty  https://github.com/becaring/3Shipsty  commit {revision}\n"
        f"Shipyard  https://github.com/becaring/Shipyard  commit {platform_revision}\n"
        f"eSpeak NG https://github.com/espeak-ng/espeak-ng  commit {speech_commit}\n\n"
        "The 3Shipsty repository pins every other component by commit, and its docs/BUILDING.md\n"
        "explains how to build this package from those sources.\n",
        encoding="utf-8", newline="\n")
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    with open(out / "SHA256SUMS.txt", "w", encoding="utf-8", newline="\n") as sums:
        for path in files:
            sums.write(sha256(path) + "  " + path.relative_to(out).as_posix() + "\n")
    if args.zip:
        print(shutil.make_archive(str(out), "zip", out))
    if dirty:
        print("warning: packaged with uncommitted changes; this package is for testing, not release")
    print(out)


if __name__ == "__main__":
    main()
