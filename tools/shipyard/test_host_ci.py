"""Run the portable tests available in a fresh checkout without game assets or XDK."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TESTS = (
    "tools/shipyard/check_projector_style.py",
    "tools/shipyard/test_setup_dependencies.py",
    "tools/shipyard/tests/test_regeneration_resume.py",
    "tools/shipyard/tests/test_source_inventory.py",
)


def main():
    for test in TESTS:
        print(f"Running {test}", flush=True)
        subprocess.run([sys.executable, "-B", str(ROOT / test)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
