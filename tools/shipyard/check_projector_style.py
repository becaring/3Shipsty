"""Keep maintained projector Python readable without scanning vendored code."""

from pathlib import Path
import sys

LIMIT = 140


def main():
    folder = Path(__file__).resolve().parent
    failures = []
    files = sorted(folder.glob("prepare*.py"))
    if not files:
        raise SystemExit("No projectors found")
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if len(line) > LIMIT:
                failures.append(f"{path.name}:{number}: {len(line)} characters (limit {LIMIT})")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Checked {len(files)} projectors: no lines exceed {LIMIT} characters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
