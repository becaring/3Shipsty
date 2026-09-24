"""Generate the pinned BS thread-pool adapter from Shipyard."""

import argparse
from pathlib import Path

from platform_base import resolve

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "platform/shipyard/thread-pool/upstream/BS_thread_pool.hpp"
OUTPUT = ROOT / "scratch/async-xdk/generated"


def main(source=SOURCE, output=OUTPUT):
    resolve(ROOT)
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "scratch/async-xdk").resolve()):
        raise ValueError("output must remain under owned scratch/async-xdk")
    from xbox360_platform.bs_thread_pool import generate
    return generate(source, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    main(args.source, args.output)
