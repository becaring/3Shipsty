"""Reproduce pinned spdlog core/queue projection for Shipyard XDK."""

from pathlib import Path
import runpy
import json
import hashlib
import importlib.util

ROOT = Path(__file__).resolve().parents[2]


def validate_inputs():
    base = ROOT / "platform/shipyard/logging"
    for filename in ("source-lock.json", "core-source-lock.json"):
        for rel, expected in json.loads((base / filename).read_text()).items():
            path = (
                ROOT
                / "scratch/deps/spdlog/include"
                / ("spdlog/" + rel if filename.startswith("core") else rel)
            )
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Pinned spdlog source changed: " + rel)
    for rel, expected in json.loads((base / "fmt-source-lock.json").read_text()).items():
        if (
            hashlib.sha256((ROOT / "scratch/deps/fmt-xdk" / rel).read_bytes()).hexdigest()
            != expected
        ):
            raise ValueError("Pinned fmt compiler dependency changed: " + rel)
    for rel, expected in json.loads((base / "float-source-lock.json").read_text()).items():
        if (
            hashlib.sha256(
                (ROOT / "scratch/deps/spdlog/include/spdlog/fmt/bundled" / rel).read_bytes()
            ).hexdigest()
            != expected
        ):
            raise ValueError("Pinned float source changed: " + rel)


if __name__ == "__main__":
    validate_inputs()
    spec = importlib.util.spec_from_file_location(
        "logging_float", ROOT / "platform/shipyard/logging/generate_float.py"
    )
    floating = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(floating)
    floating.generate(ROOT / "scratch/logging-xdk/include")
    runpy.run_path(str(ROOT / "platform/shipyard/logging/prepare_donor.py"), run_name="__main__")
