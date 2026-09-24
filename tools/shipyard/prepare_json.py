"""Build Shipyard's JSON backend and modern SoH contract probes."""

import hashlib
import json
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from platform_base import resolve as resolve_platform_base


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_BASE = resolve_platform_base(ROOT)
BACKEND = ROOT / "platform/shipyard/json"
SHIPYARD_JSON = PLATFORM_BASE / "sources/json"
SOURCE = PLATFORM_BASE / "third_party/nlohmann-3.12.0"
OUT = ROOT / "scratch/json-xdk/backend-generated/json/generated"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def generate(source=SOURCE, output=OUT):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "scratch/json-xdk").resolve()):
        raise ValueError("output must remain in owned scratch/json-xdk")
    core = runpy.run_path(str(PLATFORM_BASE / "python/xbox360_platform/json/backend.py"))["generate"](output, source)
    ordered_consumers = runpy.run_path(str(BACKEND / "generate_ordered_consumers.py"))["generate"](output)
    containers = runpy.run_path(str(BACKEND / "generate_containers.py"))["generate"](output)
    manifest = {
        "shipyard": core,
        "ordered_consumers": ordered_consumers,
        "containers": containers,
        "generator_sha256": sha(Path(__file__).read_bytes()),
        "full_modern_soh_json_contract": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    generate()
    print("Generated Shipyard JSON backend and modern SoH contract probes")
