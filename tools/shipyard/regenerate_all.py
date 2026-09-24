"""Regenerate every selected Modern Xbox compiler recipe from locked source.

With --empty-owned-outputs, removes only the generated scratch directories
named by the canonical subsystem inventory, plus its project/link directories.
The previous XEX and receipts are copied to a timestamped preservation folder
first. Dependency snapshots and historical checkpoints are never removed.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dependency_sources import ROOT


SCRATCH = ROOT / "scratch"
CONFIG = ROOT / "platform/shipyard/build/subsystems.json"
STAGES = [
    ("prepare_logging.py", []),
    ("tests/test_logging.py", []),
    ("tests/test_logging_float.py", []),
    ("prepare_async.py", []), ("tests/test_async.py", []),
    ("prepare_binary.py", []), ("tests/test_binary.py", []),
    ("prepare_filesystem.py", []), ("tests/test_filesystem.py", []),
    ("prepare_json.py", []), ("tests/test_json_backend.py", []),
    ("prepare_archives.py", ["--build"]),
    ("prepare_stormlib.py", ["--build"]),
    ("prepare_codecs.py", ["--build"]),
    ("prepare_vorbis.py", ["--build"]),
    ("prepare_imgui.py", ["--compile"]),
    # Prism's real shader builder includes the complete Fast3D, resource,
    # audio and GUI declarations. Generate their canonical header providers
    # before its isolated native compile; their full builds follow below.
    ("prepare_resources.py", []),
    ("prepare_audio.py", []),
    ("prepare_resource_manager.py", []),
    ("prepare_gui_resources.py", []),
    ("prepare_fast3d.py", []),
    ("prepare_prism.py", ["--build"]),
    ("prepare_graphics.py", ["--compile"]),
    ("prepare_xenos.py", ["--build"]),
    ("prepare_presentation.py", ["--build"]),
    ("prepare_native_imgui.py", ["--build"]),
    ("prepare_gfxd.py", ["--build"]),
    ("prepare_resources.py", []), ("tests/test_resources.py", []),
    ("prepare_resource_manager.py", ["--build"]),
    ("prepare_configuration.py", ["--build"]),
    ("prepare_console_variables.py", ["--build"]),
    ("prepare_context.py", ["--build"]),
    ("prepare_window.py", ["--build"]),
    ("prepare_audio.py", ["--build"]),
    ("prepare_gui_resources.py", ["--build"]),
    ("prepare_fast3d.py", ["--build"]),
    ("prepare_fast_resources.py", ["--build"]),
    ("prepare_input.py", ["--build"]),
    ("prepare_gui.py", ["--build"]),
    ("prepare_soh_resources.py", ["--build"]),
    ("prepare_interpolation.py", ["--build"]),
    ("prepare_libultra.py", ["--build"]),
    ("prepare_game_interactor.py", ["--build"]),
    ("prepare_enhancements.py", ["--build"]),
    ("prepare_object_extension.py", ["--build"]),
    ("prepare_app_services.py", ["--build"]),
    ("prepare_randomizer.py", ["--build"]),
    ("prepare_ship_utils.py", ["--build"]),
    ("prepare_custom_message.py", ["--build"]),
    ("prepare_soh_ui.py", ["--build"]),
    ("prepare_soh_menus.py", ["--build"]),
    ("prepare_save_storage.py", ["--build"]),
    ("prepare_randomizer_options.py", ["--build"]),
    ("prepare_soh_input_editor.py", ["--build"]),
    ("prepare_legacy_save.py", ["--build"]),
    ("prepare_network.py", ["--build"]),
    ("prepare_application.py", ["--build"]),
    ("prepare_application_gui.py", ["--build"]),
    ("prepare_audio_collection.py", ["--build"]),
    ("prepare_randomizer_item.py", ["--build"]),
    ("prepare_randomizer_logic.py", ["--build"]),
    ("prepare_savestates.py", ["--build"]),
    ("prepare_save_manager.py", ["--build"]),
    ("prepare_randomizer_settings.py", ["--build"]),
    ("prepare_randomizer_context.py", ["--build"]),
    ("prepare_randomizer_dungeons.py", ["--build"]),
    ("prepare_randomizer_hints.py", ["--build"]),
    ("prepare_application_windows.py", ["--build"]),
    ("prepare_application_editors.py", ["--build"]),
    ("prepare_randomizer_data.py", ["--build"]),
    ("prepare_application_core.py", ["--build"]),
    ("prepare_network_app.py", ["--build"]),
    ("prepare_gameplay_features.py", ["--build"]),
    ("prepare_randomizer_content.py", ["--build"]),
    ("prepare_randomizer_regions.py", ["--build"]),
    ("prepare_application_extras.py", ["--build"]),
    ("prepare_randomizer_generation.py", ["--build"]),
    ("prepare_randomizer_application.py", ["--build"]),
    ("prepare_speech.py", ["--engine"]),
    ("prepare_speech.py", ["--application"]),
    ("prepare_game.py", ["--all", "--output-full"]),
    ("prepare_build_metadata.py", []),
    ("prepare_crt.py", ["--build"]),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def owned_targets():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    names = {Path(pattern).parts[1] for patterns in config["reports"].values()
             for pattern in patterns}
    names.update(("logging-xdk", "project-xdk", "link-integration"))
    # Speech keeps two clean, pinned Git dependency checkouts beside its
    # generated products. Never classify their parent as an owned output.
    names.remove("speech-xdk")
    targets = [SCRATCH / name for name in sorted(names)]
    speech = SCRATCH / "speech-xdk"
    if speech.is_dir():
        targets.extend(child for child in sorted(speech.iterdir())
                       if child.name not in ("espeak-ng", "sonic"))
    return targets


def clean_owned():
    root = SCRATCH.resolve()
    paths = owned_targets()
    speech_root = (SCRATCH / "speech-xdk").resolve()
    for path in paths:
        resolved = path.resolve()
        if resolved.parent not in (root, speech_root) or not resolved.is_relative_to(root):
            raise ValueError("Generated target escapes owned scratch: " + str(path))
        if path.is_dir() and any(p.name == ".git" for p in path.rglob(".git")):
            raise ValueError("Generated target contains a Git checkout: " + str(path))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    preserved = SCRATCH / "final-preclean" / stamp
    preserved.mkdir(parents=True, exist_ok=False)
    records = []
    for relative in ("link-integration/3Shipsty.xex",
                     "link-integration/link-verification.json",
                     "project-xdk/complete-application-verification.json"):
        source = SCRATCH / relative
        if source.is_file():
            target = preserved / source.name
            shutil.copy2(source, target)
            records.append({"source": relative, "preserved": target.relative_to(ROOT).as_posix(),
                            "sha256": sha(target)})
    (preserved / "manifest.json").write_text(json.dumps(records, indent=2) + "\n",
                                                encoding="utf-8")
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    return preserved, [path.relative_to(ROOT).as_posix() for path in paths]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empty-owned-outputs", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print(json.dumps({"owned_targets": [p.relative_to(ROOT).as_posix()
                                            for p in owned_targets()], "stages": STAGES}, indent=2))
        return
    from platform_base import resolve
    resolve(ROOT)
    if args.empty_owned_outputs:
        preserved, removed = clean_owned()
    else:
        preserved, removed = None, []
    log_dir = SCRATCH / "final-regeneration"
    log_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"preserved": str(preserved.relative_to(ROOT)) if preserved else None,
               "emptied_directories": removed, "stages": []}
    for index, (script, options) in enumerate(STAGES, 1):
        command = [sys.executable, "-B", "-X", "utf8",
                   str(ROOT / "tools/shipyard" / script), *options]
        print("Regenerating %02d/%02d: %s %s" % (index, len(STAGES), script,
                                                 " ".join(options)), flush=True)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        label = "%02d-%s" % (index, Path(script).stem)
        log = log_dir / (label + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        receipt["stages"].append({"script": script, "options": options,
                                  "exit": result.returncode,
                                  "log": log.relative_to(ROOT).as_posix(),
                                  "log_sha256": sha(log)})
        (log_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                               encoding="utf-8")
        if result.returncode:
            print((result.stdout + result.stderr)[-6000:], flush=True)
            raise SystemExit(result.returncode)
    print("All %d generation stages passed" % len(STAGES), flush=True)


if __name__ == "__main__":
    main()
