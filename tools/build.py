"""Build 3Shipsty.xex incrementally: refresh the build metadata, compile what changed, and link.

    python -B tools/build.py [--regenerate] [--jobs N]

The compile step reuses objects whose sources and headers are unchanged, so a commit that changes no
generated input costs only build.c and the link. --regenerate first reruns all regeneration stages, which
recompiles every stage; use it after changing Shipyard sources, projectors or pinned inputs. To refresh one
module, run its tools/shipyard/prepare_<module>.py before this script.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/shipyard"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    steps = [["regenerate_all.py"]] if args.regenerate else []
    steps += [["prepare_build_metadata.py"], ["generate_xdk_project.py"],
              ["build_xdk_project.py", "--jobs", str(args.jobs)], ["link_xdk_application.py"]]
    for script, *options in steps:
        print("==", script, *options, flush=True)
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", str(TOOLS / script), *options], cwd=ROOT)
        if result.returncode:
            return result.returncode
    print(ROOT / "scratch/link-integration/3Shipsty.xex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
