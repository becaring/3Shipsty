"""Pack a release assets folder into one stored assets.zip for the console.

FTP copies the folder's thousands of small extraction XMLs slowly; the console
reads the same files from the zip in place. Entries stay uncompressed because
the extractor reads them without inflating.
"""

import argparse
from pathlib import Path
import zipfile


def pack(folder, output):
    files = sorted(p for p in Path(folder).rglob("*") if p.is_file())
    with zipfile.ZipFile(output, "x", zipfile.ZIP_STORED) as archive:
        for path in files:
            archive.write(path, path.relative_to(folder).as_posix())
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(pack(args.assets, args.output), "files ->", args.output)
