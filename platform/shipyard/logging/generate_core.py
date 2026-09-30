"""Modern policy adapter for Shipyard's pinned spdlog compiler projector."""

import os
from pathlib import Path
import importlib.util, json, sys

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).parent
UP = ROOT / "scratch/deps/spdlog/include"
sys.dont_write_bytecode = True


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


LANG = module("logging_language", BASE / "lowering.py")
PRISM = LANG
lock = json.loads((ROOT / "platform-base.lock.json").read_text())
PLATFORM = Path(os.environ.get("XBOX360_PLATFORM_BASE", ROOT / lock["base"])).resolve()
SHARED = module("shipyard_logging_core", PLATFORM / "python/xbox360_platform/logging_core.py")


def configure():
    SHARED.configure(
        upstream=UP,
        base=BASE,
        language=LANG,
        syntax=PRISM,
        namespace="Shipyard::Logging",
        environment_header=BASE / "environment.h",
        environment_get="ShipyardEnv_Get",
        guard_source="SHIPYARD_PRISM_",
        guard_target="SHIPYARD_SPDLOG_",
        overload_mode="filtered",
    )
    return SHARED


def common():
    return configure().common()


def generate(out):
    return configure().generate(out, normalize_file_paths=False)
