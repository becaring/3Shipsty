"""Maintainer-local relationships for the fixed Xbox development checkouts.

No source is parsed or copied here. Compiler inputs and provenance come from
the selected build manifests, source locks, project file, and #line records.
Workstation paths are intentional; this module is not a portable build input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from filelock import FileLock
import yaml

VERSION = "3"
NAV_ROOT = Path(r"D:\Projects\3Shipsty9.x")
MODERN = NAV_ROOT / "scratch/deslop-worktree"
SMASH = Path(r"D:\Projects\Smash360\scratch\deslop-worktree")
MAJORA = Path(r"D:\Projects\2Ship3Shipsty")
SHIPYARD = Path(r"D:\Projects\becaring\shipyard")
STATE = NAV_ROOT / "scratch/code-nav"
DB = Path(os.environ.get("CODE_NAV_DB", str(STATE / "relationships.sqlite")))
SDK = Path(r"C:\Program Files (x86)\Microsoft Xbox 360 SDK")


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git_dirs(root: Path) -> tuple[Path, Path]:
    if root.parent.name == "selections" and root.name in ("3Shipsty", "2Ship"):
        root = root.parent.parent
    marker = root / ".git"
    git_dir = marker
    if marker.is_file():
        value = marker.read_text(encoding="utf-8").strip()
        if not value.startswith("gitdir: "):
            raise ValueError(f"Unrecognized worktree marker: {marker}")
        git_dir = (root / value[8:]).resolve()
    common_file = git_dir / "commondir"
    common = ((git_dir / common_file.read_text(encoding="utf-8").strip()).resolve()
              if common_file.is_file() else git_dir)
    return git_dir, common


def head(root: Path) -> str:
    """Read HEAD without spawning Git from an MCP stdio request."""
    git_dir, common = git_dirs(root)
    value = (git_dir / "HEAD").read_text(encoding="ascii").strip()
    if not value.startswith("ref: "):
        return value
    ref = value[5:]
    for directory in (git_dir, common):
        path = directory / ref
        if path.is_file():
            return path.read_text(encoding="ascii").strip()
    packed = common / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="ascii").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    raise ValueError(f"Missing Git ref {ref} in {root}")


def data(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_text(path: Path, content: str) -> bool:
    """Replace one index/config file only when its bytes changed."""
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def selected_base(root: Path) -> tuple[Path, Path]:
    lock = root / "platform-base.lock.json"
    override = os.environ.get("XBOX360_PLATFORM_BASE")
    return (Path(override) if override else root / data(lock)["base"]).resolve(), lock


def verify_base(base: Path, lock: Path):
    pinned = data(lock)
    if not head(base).startswith(pinned["git_revision"]):
        raise ValueError(f"Shipyard checkout does not match {lock}")
    if sha(base / "baseline.json") != pinned["baseline_sha256"]:
        raise ValueError(f"Shipyard baseline does not match {lock}")


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Git identity check failed in {root}: {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def shipyard_identity(base: Path) -> dict:
    """Verify a local checkout of the canonical history, without contacting a remote."""
    canonical = SHIPYARD.resolve()
    selected = base.resolve()
    maintained_head, selected_head = head(canonical), head(selected)
    linked = git_dirs(selected)[1].resolve() == git_dirs(canonical)[1].resolve()
    if not linked:
        remote = Path(git_output(selected, "remote", "get-url", "canonical-local")).resolve()
        if remote != canonical:
            raise ValueError(f"Selected Shipyard remote is {remote}, expected {canonical}")
    common_ancestor = git_output(canonical, "merge-base", selected_head, maintained_head)
    if common_ancestor == selected_head:
        history_relation = "selected-ancestor-of-maintained"
    elif common_ancestor == maintained_head:
        history_relation = "selected-descendant-of-maintained"
    else:
        history_relation = "diverged-branch-of-maintained"
    root = git_output(canonical, "rev-list", "--max-parents=0", maintained_head).splitlines()[0]
    return {"canonical": str(canonical), "canonical_head": maintained_head,
            "history_root": root, "repository_relation": (
                "linked-worktree-of-canonical" if linked else "normal-checkout-of-canonical"),
            "history_relation": history_relation}


def modern_rows(base: Path):
    manifest = MODERN / "scratch/project-xdk/manifest.json"
    for row in data(manifest)["sources"]:
        name = row["source"]
        source = base / name.removeprefix("shipyard/") if name.startswith("shipyard/") else MODERN / name
        yield source.resolve(), row, manifest


def smash_rows(base: Path):
    manifest = SMASH / "scratch/application-xdk/native/project-items.json"
    staged = SMASH / "scratch/application-xdk/native/source"
    for project in ("Smash360", "Libultraship360"):
        for row in data(manifest)[project]:
            source = base / row["shipyard_source"] if "shipyard_source" in row else staged / row["staged"]
            yield source.resolve(), row | {"project": project}, manifest


def majora_rows(base: Path):
    """Read only the selected Xbox compiler recipes, never infer from host CMake."""
    manifest = MAJORA / "scratch/project-xdk/manifest.json"
    if not manifest.is_file():
        return
    selected = data(manifest)
    if selected.get("upstream_commit") != data(MAJORA / "platform/xbox360/source-lock.json")["upstream_commit"]:
        raise ValueError("Majora selected manifest differs from pinned upstream")
    for row in selected["sources"]:
        name = row["source"]
        source = base / name.removeprefix("shipyard/") if name.startswith("shipyard/") else MAJORA / name
        yield source.resolve(), row, manifest


def verify_majora_upstream():
    lock = data(MAJORA / "platform/xbox360/source-lock.json")
    if head(MAJORA) != lock["upstream_commit"] and not git_output(
            MAJORA, "merge-base", "--is-ancestor", lock["upstream_commit"], "HEAD") == "":
        raise ValueError("Majora checkout does not contain the pinned upstream")
    for name, expected in lock["submodules"].items():
        if head(MAJORA / name) != expected:
            raise ValueError(f"Majora submodule {name} differs from source lock")


def modern_flags(options: list[str], base: Path) -> list[str]:
    replacements = {
        "$(ShipyardPlatformBase)": str(base),
        "$(ShipyardRoot)": str(MODERN),
        "$(XEDK)": str(SDK),
    }
    result = []
    for option in options:
        for key, value in replacements.items():
            option = option.replace(key, value)
        if option.startswith(("/I", "/D", "/U")) or option in ("/EHsc", "/GR"):
            result.append(option)
        elif option.startswith("/std:"):
            result.append(option)
    return result


def majora_flags(options: list[str], base: Path) -> list[str]:
    replacements = {
        "$(ShipyardPlatformBase)": str(base),
        "$(MajoraRoot)": str(MAJORA),
        "$(XEDK)": str(SDK),
    }
    result = []
    for option in options:
        for key, value in replacements.items():
            option = option.replace(key, value)
        if option.startswith(("/I", "/D", "/U", "/std:")) or option in ("/EHsc", "/GR"):
            result.append(option)
    return result


def smash_flags(base: Path, project: str) -> list[str]:
    path = SMASH / "platform/xbox360" / (project + ".vcxproj")
    ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
    root = ET.parse(path).getroot()
    group = root.find(".//m:ItemDefinitionGroup/m:ClCompile", ns)
    if group is None:
        raise ValueError(f"No selected ClCompile definition: {path}")
    staged = SMASH / "scratch/application-xdk/native/source"
    substitutions = {"$(SmashSourceRoot)": str(staged) + os.sep,
                     "$(ShipyardRoot)": str(base), "$(SmashFullProfiling)": "0"}
    result = []
    for entry in (group.findtext("m:AdditionalIncludeDirectories", "", ns) or "").split(";"):
        if not entry or entry.startswith("%("):
            continue
        for key, value in substitutions.items():
            entry = entry.replace(key, value)
        result.append("/I" + entry)
    for entry in (group.findtext("m:PreprocessorDefinitions", "", ns) or "").split(";"):
        if not entry or entry.startswith("%("):
            continue
        for key, value in substitutions.items():
            entry = entry.replace(key, value)
        result.append("/D" + entry)
    result.append("/I" + str(SDK / "include/xbox"))
    if group.findtext("m:ExceptionHandling", "", ns) == "Sync":
        result.append("/EHsc")
    if group.findtext("m:RuntimeTypeInfo", "", ns).lower() == "true":
        result.append("/GR")
    return result


def analysis_command(source: Path, options: list[str], language: str) -> dict:
    # clangd infers the clang-cl driver from argv[0]. XDK-only output/link flags
    # are intentionally absent; these are analysis recipes, never build recipes.
    return {"directory": str(source.parent), "file": str(source),
            "arguments": ["clang-cl", "/nologo", "/std:c++14" if language != "c" else "/TC",
                          *options, str(source)]}


def probe_commands():
    """Write only the actual selected shader provider, core and builder TUs."""
    modern_base, _ = selected_base(MODERN)
    smash_base, _ = selected_base(SMASH)
    names = ("shader_provider.cpp", "core.cpp", "shader_builder.cpp")
    for consumer, rows, base in (("modern", modern_rows(modern_base), modern_base),
                                 ("smash", smash_rows(smash_base), smash_base)):
        commands = []
        for source, row, _ in rows:
            if source.name not in names:
                continue
            if consumer == "modern":
                flags = modern_flags(row["options"], base)
                language = row["language"]
            else:
                flags = smash_flags(base, row["project"])
                language = "c" if source.suffix == ".c" else "cpp"
            commands.append(analysis_command(source, flags, language))
        path = (MODERN if consumer == "modern" else SMASH) / "compile_commands.json"
        atomic_text(path, json.dumps(commands, indent=2) + "\n")
        print(f"{consumer}: {len(commands)} probe translation units -> {path}")


def all_commands(*, verbose: bool = True):
    modern_base, _ = selected_base(MODERN)
    smash_base, _ = selected_base(SMASH)
    for consumer, root, rows, base in (("modern", MODERN, modern_rows(modern_base), modern_base),
                                       ("smash", SMASH, smash_rows(smash_base), smash_base)):
        commands = []
        for source, row, _ in rows:
            if consumer == "modern":
                flags, language = modern_flags(row["options"], base), row["language"]
            else:
                flags = smash_flags(base, row["project"])
                language = "c" if source.suffix == ".c" else "cpp"
            commands.append(analysis_command(source, flags, language))
        atomic_text(root / "compile_commands.json", json.dumps(commands, indent=2) + "\n")
        if verbose:
            print(f"{consumer}: {len(commands)} selected translation units")
    manifest = MAJORA / "scratch/project-xdk/manifest.json"
    if manifest.is_file():
        base, _ = selected_base(MAJORA)
        commands = [analysis_command(source, majora_flags(row["options"], base), row["language"])
                    for source, row, _ in majora_rows(base)]
        atomic_text(MAJORA / "compile_commands.json", json.dumps(commands, indent=2) + "\n")
        if verbose:
            print(f"majora: {len(commands)} selected translation units")
    elif verbose:
        print("majora: Xbox build selection pending; no analysis database synthesized")


def configure_serena(phase: str, *, verbose: bool = True):
    """Limit default Serena walks to selected active paths, never old trees."""
    for consumer, root in (("modern", MODERN), ("smash", SMASH)):
        path = root / ".serena/project.yml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if phase == "probe":
            folders = (["platform/shipyard/xenos", "scratch/prism-xdk/generated", "tools/shipyard"]
                       if consumer == "modern" else
                       ["platform/xbox360/graphics", "scratch/prism-xdk", "tools"])
        else:
            base, _ = selected_base(root)
            rows = modern_rows(base) if consumer == "modern" else smash_rows(base)
            selected = list(rows)
            folders = sorted({str(source.parent.relative_to(root)).replace("\\", "/")
                              for source, _, _ in selected if source.is_relative_to(root)})
            if consumer == "smash":
                folders += [str((root / row["path"]).parent.relative_to(root)).replace("\\", "/")
                            for _, row, _ in selected
                            if row["path"].startswith(("platform/xbox360/", "scratch/"))]
            folders += ["tools/shipyard"] if consumer == "modern" else ["tools", "platform/xbox360"]
        folders = sorted(set(folders))
        prefixes = {""}
        for folder in folders:
            parts = Path(folder).parts
            prefixes.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
        ignored = []
        for prefix in sorted(prefixes):
            directory = root / prefix
            if not directory.is_dir():
                continue
            for entry in directory.iterdir():
                if not entry.is_dir():
                    continue
                relative = entry.relative_to(root).as_posix()
                if relative not in prefixes:
                    ignored.append("/" + relative + "/")
        ignored += ["*.apk", "*.zip", "*.obj", "*.lib", "*.xex", "*.rom", "*.z64", "*.n64"]
        config.update(ignore_all_files_in_gitignore=False, read_only=True,
                      excluded_tools=["activate_project", "onboarding", "initial_instructions",
                                      "write_memory", "read_memory", "list_memories",
                                      "delete_memory", "edit_memory", "rename_memory"],
                      ls_workspace_folders=folders, ignored_paths=sorted(set(ignored)))
        config["ls_specific_settings"] = {"cpp": {"ls_path": str(STATE /
            "serena-home/language_servers/static/ClangdLanguageServer/clangd/clangd_19.1.2/bin/clangd.exe")},
            "python": {"pyright_version": "1.1.403"}}
        atomic_text(path, yaml.safe_dump(config, sort_keys=False))
        if verbose:
            print(f"{consumer}: {len(folders)} workspace paths, {len(ignored)} ignored patterns")
    manifest = MAJORA / "scratch/project-xdk/manifest.json"
    if not manifest.is_file():
        if verbose:
            print("majora: fixed source scope retained until Xbox build selection exists")
        return
    path = MAJORA / ".serena/project.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    base, _ = selected_base(MAJORA)
    selected = list(majora_rows(base))
    folders = {"platform/xbox360", "mm/src", "mm/2s2h", "mm/include",
               "libultraship/src/fast", "libultraship/src/ship",
               "libultraship/src/libultraship", "libultraship/include"}
    folders.update(source.parent.relative_to(MAJORA).as_posix()
                   for source, _, _ in selected if source.is_relative_to(MAJORA))
    selected_manifest = MAJORA / "scratch/project-xdk/manifest.json"
    if selected_manifest.is_file():
        folders.update((MAJORA / row["output"]).parent.relative_to(MAJORA).as_posix()
                       for row in data(selected_manifest).get("projections", []))
    config["ls_workspace_folders"] = sorted(folders)
    config["ignored_paths"] = sorted((set(config.get("ignored_paths", [])) - {"/scratch/"}) | {
        "*.z64", "*.n64", "*.o2r", "*.otr", "*.zip", "*.obj", "*.lib", "*.xex"})
    atomic_text(path, yaml.safe_dump(config, sort_keys=False))
    if verbose:
        print(f"majora: {len(folders)} workspace paths from selected Xbox sources")


def projections():
    modern_input = MODERN / "libultraship/src/fast/backends/gfx_direct3d11.cpp"
    modern_lock = MODERN / "platform/shipyard/graphics/source-lock.json"
    modern_output = MODERN / "scratch/prism-xdk/generated/shader_builder.cpp"
    smash_input = SMASH / "upstream/BattleShip/libultraship/src/fast/backends/gfx_direct3d11.cpp"
    smash_lock = SMASH / "platform/xbox360/cpp-compat/prism/source-lock.json"
    smash_output = SMASH / "scratch/prism-xdk/shader_builder.cpp"
    shared_base, _ = selected_base(MODERN)
    records = [
        ("modern", modern_output, MODERN / "tools/shipyard/prepare_prism.py",
         shared_base / "python/xbox360_platform/prism.py", modern_input,
         data(modern_lock)["inputs"]["libultraship/src/fast/backends/gfx_direct3d11.cpp"], modern_lock),
        ("smash", smash_output, SMASH / "tools/prepare_prism_xdk.py",
         shared_base / "python/xbox360_platform/prism.py", smash_input,
         data(smash_lock)["source"]["upstream/BattleShip/libultraship/src/fast/backends/gfx_direct3d11.cpp"], smash_lock),
    ]
    staged = SMASH / "scratch/application-xdk/native/source/scratch/prism-xdk/shader_builder.cpp"
    records.append(("smash", staged, records[-1][2], records[-1][3], records[-1][4],
                    records[-1][5], records[-1][6]))
    return records


def modern_manifest_projections(base: Path):
    """Use explicit upstream_source and subsystem lock, never guessed bodies."""
    for output, row, _ in modern_rows(base):
        upstream_name = row.get("upstream_source")
        if not upstream_name or not output.is_relative_to(MODERN / "scratch"):
            continue
        subsystem = row.get("subsystem", "")
        projector = MODERN / "tools/shipyard" / ("prepare_" + subsystem.replace("-", "_") + ".py")
        if not projector.is_file():
            continue
        upstream = (base / upstream_name.removeprefix("shipyard/") if upstream_name.startswith("shipyard/")
                    else MODERN / upstream_name)
        locks = [MODERN / "platform/shipyard" / subsystem / name
                 for name in ("sources.lock.json", "source-lock.json")]
        lock = next((p for p in locks if p.is_file()), None)
        locked = data(lock) if lock else {}
        pinned = (locked.get("sources", {}).get(upstream_name) or
                  locked.get("inputs", {}).get(upstream_name))
        yield ("modern", output, projector, None, upstream, pinned, lock, row["sha256"])


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot (
 consumer TEXT PRIMARY KEY, root TEXT, root_head TEXT, base TEXT, base_head TEXT,
 lock_path TEXT, lock_sha TEXT, manifest_path TEXT, manifest_sha TEXT,
 compile_sha TEXT, serena_sha TEXT, indexer TEXT, updated REAL,
 canonical TEXT, canonical_head TEXT, canonical_config_sha TEXT,
 dependency_config_sha TEXT, history_root TEXT, repository_relation TEXT,
 history_relation TEXT, source_lock_path TEXT, source_lock_sha TEXT);
CREATE TABLE IF NOT EXISTS selection (
 consumer TEXT, config TEXT, source TEXT, source_sha TEXT, kind TEXT,
 manifest_path TEXT, receipt TEXT, options_json TEXT, receipt_sha TEXT,
 PRIMARY KEY (consumer, config, source));
CREATE TABLE IF NOT EXISTS projection (
 consumer TEXT, output TEXT, output_sha TEXT, projector TEXT, projector_sha TEXT,
 shared_projector TEXT, shared_projector_sha TEXT, upstream TEXT, upstream_sha TEXT,
 lock_path TEXT, lock_sha TEXT, PRIMARY KEY (consumer, output));
"""


def majora_vendor_headers(row: dict, output: Path, upstream: Path, projector: Path) -> tuple[bool, bool]:
    lock_name = row.get("lock")
    if lock_name == "platform/xbox360/png-source-lock.json":
        source_dir = "build/host/vcpkg/buildtrees/libpng/src/v1.6.58-b91136795d.clean"
        output_dir = MAJORA / "scratch/project-xdk/libpng"
        projector_name = "platform/xbox360/project_png.py"
        headers = {name: name for name in ("png.h", "pngconf.h", "pngdebug.h", "pnginfo.h",
                                           "pngpriv.h", "pngstruct.h")}
        headers["scripts/pnglibconf.h.prebuilt"] = "pnglibconf.h"
        is_png = True
    elif lock_name == "platform/xbox360/gfxd-source-lock.json":
        source_dir = "build/host/_deps/libgfxd-src"
        output_dir = MAJORA / "scratch/project-xdk/gfxd"
        projector_name = "platform/xbox360/project_gfxd.py"
        headers = {name: name for name in ("gbi.h", "gfxd.h", "priv.h")}
        is_png = False
    else:
        return False, False
    source_root = MAJORA / source_dir
    if not upstream.is_relative_to(source_root):
        return False, False
    relative = upstream.relative_to(source_root).as_posix()
    lock = data(MAJORA / lock_name)
    allowed = (lock.get("source_directory") == source_dir and
               relative in headers and lock.get("files", {}).get(relative) == row.get("upstream_sha256") and
               output == output_dir / headers.get(relative, "") and
               projector == MAJORA / projector_name)
    return (allowed, False) if is_png else (False, allowed)


def majora_interpreter_projection(row: dict, output: Path, upstream: Path, projector: Path) -> bool:
    return (row.get("lock") == "platform/xbox360/project_interpreter.py" and
            output == MAJORA / "scratch/project-xdk/generated/libultraship/src/fast/interpreter.cpp" and
            upstream == MAJORA / "libultraship/src/fast/interpreter.cpp" and
            projector == MAJORA / "platform/xbox360/project_interpreter.py")


def refresh():
    STATE.mkdir(parents=True, exist_ok=True)
    with FileLock(str(DB) + ".lock", timeout=60):
        conn = sqlite3.connect(DB, timeout=60)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshot)")}
            for column in ("compile_sha", "serena_sha", "canonical", "canonical_head",
                           "canonical_config_sha", "dependency_config_sha", "history_root",
                           "repository_relation", "history_relation", "source_lock_path",
                           "source_lock_sha"):
                if column not in columns:
                    conn.execute(f"ALTER TABLE snapshot ADD COLUMN {column} TEXT")
            selection_columns = {row[1] for row in conn.execute("PRAGMA table_info(selection)")}
            if "receipt_sha" not in selection_columns:
                conn.execute("ALTER TABLE selection ADD COLUMN receipt_sha TEXT")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM snapshot")
            conn.execute("DELETE FROM selection")
            conn.execute("DELETE FROM projection")
            for consumer, root in (("modern", MODERN), ("smash", SMASH)):
                base, lock = selected_base(root)
                verify_base(base, lock)
                identity = shipyard_identity(base)
                manifest = (MODERN / "scratch/project-xdk/manifest.json" if consumer == "modern"
                            else SMASH / "scratch/application-xdk/native/project-items.json")
                conn.execute("INSERT INTO snapshot (consumer,root,root_head,base,base_head,lock_path,lock_sha,manifest_path,manifest_sha,compile_sha,serena_sha,indexer,updated,canonical,canonical_head,canonical_config_sha,dependency_config_sha,history_root,repository_relation,history_relation) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (consumer, str(root), head(root), str(base), head(base), str(lock), sha(lock),
                              str(manifest), sha(manifest), sha(root / "compile_commands.json"),
                              sha(root / ".serena/project.yml"), VERSION, time.time(),
                              identity["canonical"], identity["canonical_head"],
                              sha(git_dirs(SHIPYARD)[1] / "config"),
                              sha(git_dirs(base)[1] / "config"),
                              identity["history_root"], identity["repository_relation"],
                              identity["history_relation"]))
                rows = modern_rows(base) if consumer == "modern" else smash_rows(base)
                for source, row, origin in rows:
                    config = "xdk-release" if consumer == "modern" else row["project"] + "-release"
                    kind = "shared" if source.is_relative_to(base) else ("generated" if "scratch" in source.parts else "consumer")
                    receipt = (str(MODERN / row.get("report", "scratch/project-xdk/manifest.json"))
                               if consumer == "modern" else str(SMASH / "scratch/application-xdk/native/parallel" /
                               row["project"] / "compile-receipt.json"))
                    options = row.get("options", []) if consumer == "modern" else smash_flags(base, row["project"])
                    conn.execute("INSERT INTO selection (consumer,config,source,source_sha,kind,manifest_path,receipt,options_json,receipt_sha) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (consumer, config, str(source), row.get("sha256", sha(source)), kind, str(origin), receipt,
                                  json.dumps(options), sha(Path(receipt))))
            verify_majora_upstream()
            base, lock = selected_base(MAJORA)
            verify_base(base, lock)
            identity = shipyard_identity(base)
            manifest = MAJORA / "scratch/project-xdk/manifest.json"
            source_lock = MAJORA / "platform/xbox360/source-lock.json"
            conn.execute("INSERT INTO snapshot (consumer,root,root_head,base,base_head,lock_path,lock_sha,manifest_path,manifest_sha,compile_sha,serena_sha,indexer,updated,canonical,canonical_head,canonical_config_sha,dependency_config_sha,history_root,repository_relation,history_relation,source_lock_path,source_lock_sha) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("majora", str(MAJORA), head(MAJORA), str(base), head(base), str(lock), sha(lock),
                          str(manifest), sha(manifest), sha(MAJORA / "compile_commands.json"),
                          sha(MAJORA / ".serena/project.yml"), VERSION, time.time(),
                          identity["canonical"], identity["canonical_head"],
                          sha(git_dirs(SHIPYARD)[1] / "config"),
                          sha(git_dirs(base)[1] / "config"), identity["history_root"],
                          identity["repository_relation"], identity["history_relation"],
                          str(source_lock), sha(source_lock)))
            for source, row, origin in majora_rows(base):
                receipt = MAJORA / row["receipt"] if row.get("receipt") else origin
                kind = "shared" if source.is_relative_to(base) else (
                    "generated" if source.is_relative_to(MAJORA / "scratch") else "consumer")
                conn.execute("INSERT INTO selection (consumer,config,source,source_sha,kind,manifest_path,receipt,options_json,receipt_sha) VALUES (?,?,?,?,?,?,?,?,?)",
                             ("majora", row.get("config", "xdk-release"), str(source), row["sha256"],
                              kind, str(origin), str(receipt), json.dumps(row["options"]), sha(receipt)))
                if row.get("upstream_source") and row.get("projector"):
                    upstream = (base / row["upstream_source"].removeprefix("shipyard/")
                                if row["upstream_source"].startswith("shipyard/")
                                else MAJORA / row["upstream_source"])
                    projector = MAJORA / row["projector"]
                    shared = (base / row["shared_projector"].removeprefix("shipyard/")
                              if row.get("shared_projector") else None)
                    projection_lock = MAJORA / row["lock"] if row.get("lock") else source_lock
                    conn.execute("INSERT INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 ("majora", str(source), row["sha256"], str(projector), sha(projector),
                                  str(shared) if shared else None, sha(shared) if shared else None,
                                  str(upstream), row.get("upstream_sha256"), str(projection_lock),
                                   sha(projection_lock)))
            majora_manifest = MAJORA / "scratch/project-xdk/manifest.json"
            if majora_manifest.is_file():
                for row in data(majora_manifest).get("projections", []):
                    output = (MAJORA / row["output"]).resolve()
                    upstream = (MAJORA / row["upstream_source"]).resolve()
                    projector = (MAJORA / row["projector"]).resolve()
                    libzip_source = MAJORA / "build/host/vcpkg/buildtrees/libzip/src/v1.11.4-05742a9dee.clean"
                    zlib_source = MAJORA / "build/host/vcpkg/buildtrees/zlib/src/v1.3.2-c19a0bfd23.clean"
                    tinyxml2_source = MAJORA / "build/host/vcpkg/buildtrees/tinyxml2/src/11.0.0-f00fa8a9d2.clean"
                    from_libzip = (row.get("lock") == "platform/xbox360/libzip-source-lock.json" and
                                   output.is_relative_to(MAJORA / "scratch/project-xdk/libzip") and
                                   upstream.is_relative_to(libzip_source))
                    from_zlib = (row.get("lock") == "platform/xbox360/zlib-source-lock.json" and
                                 output.is_relative_to(MAJORA / "scratch/project-xdk/zlib") and
                                 upstream.is_relative_to(zlib_source))
                    from_tinyxml2 = (row.get("lock") == "platform/xbox360/tinyxml2-source-lock.json" and
                                     output == MAJORA / "scratch/project-xdk/tinyxml2/tinyxml2.h" and
                                     upstream == tinyxml2_source / "tinyxml2.h")
                    from_imgui = (row.get("lock") == "platform/xbox360/imgui-source-lock.json" and
                                  output.parent == MAJORA / "scratch/project-xdk/imgui" and
                                  output.name in {"imconfig.h", "imgui.h", "imgui_internal.h"} and
                                  upstream == MAJORA / "build/host/_deps/imgui-src" / output.name)
                    from_png, from_gfxd = majora_vendor_headers(row, output, upstream, projector)
                    from_interpreter = majora_interpreter_projection(row, output, upstream, projector)
                    from_lus = (row.get("lock") == "platform/xbox360/source-lock.json" and
                                upstream.is_relative_to(MAJORA / "libultraship"))
                    from_input = (row.get("lock") == "platform/xbox360/input-source-lock.json" and
                                  upstream.is_relative_to(MAJORA / "libultraship/include") and
                                  output == MAJORA / "scratch/project-xdk/headers" / upstream.relative_to(MAJORA / "libultraship/include") and
                                  projector == MAJORA / "platform/xbox360/project_input.py")
                    from_codecs = False
                    if row.get("lock") == "platform/xbox360/codec-source-lock.json":
                        for package, codec in data(MAJORA / row["lock"]).items():
                            source_root = MAJORA / codec["source_directory"]
                            if upstream.is_relative_to(source_root):
                                relative = upstream.relative_to(source_root).as_posix()
                                from_codecs = (relative in codec["files"] and
                                               output == MAJORA / "scratch/project-xdk/codecs" / package / relative and
                                               projector == MAJORA / "platform/xbox360/project_codecs.py")
                                break
                    from_prism = (row.get("lock") == "platform/xbox360/prism-source-lock.json" and
                                  output.is_relative_to(MAJORA / "scratch/project-xdk/prism/prism") and
                                  upstream.is_relative_to(MAJORA / "build/host/_deps/prism-src/src/prism") and
                                  projector == MAJORA / "platform/xbox360/project_prism.py")
                    from_fixed_point = (row.get("lock") == "platform/xbox360/project_c89.py" and
                                        output == MAJORA / "scratch/project-xdk/generated/mm/src/boot/O2/fixed_point_xdk.h" and
                                        upstream == MAJORA / "mm/include/fixed_point.h" and
                                        projector == MAJORA / "platform/xbox360/project_c89.py")
                    from_majora = (row.get("lock") in ("platform/xbox360/source-lock.json", "platform/xbox360/majora-resource-header-lock.json") and
                                   output.is_relative_to(MAJORA / "scratch/project-xdk/generated/mm/2s2h") and
                                   upstream.is_relative_to(MAJORA / "mm/2s2h"))
                    from_cvars = (row.get("lock") == "platform/xbox360/source-lock.json" and
                                  output == MAJORA / "scratch/project-xdk/generated/mm/2s2h/XboxCvars.h" and
                                  upstream == MAJORA / "CMake/2ship-cvars.cmake")
                    from_logging = (row.get("lock") == "platform/xbox360/logging/core-source-lock.json" and
                                    (output.is_relative_to(MAJORA / "scratch/project-xdk/logging/core-include/spdlog") or
                                     output.is_relative_to(MAJORA / "scratch/project-xdk/logging/queue-include/spdlog")) and
                                    upstream.is_relative_to(MAJORA / "scratch/deps/spdlog/include/spdlog"))
                    from_runtime = (row.get("lock") == "platform/xbox360/runtime-dependency-lock.json" and
                                    ((output == MAJORA / "scratch/project-xdk/thread-pool/BS_thread_pool.hpp" and
                                      upstream == MAJORA / "build/host/_deps/threadpool-src/include/BS_thread_pool.hpp") or
                                     (output.is_relative_to(MAJORA / "scratch/project-xdk/json/generated") and
                                      upstream in {MAJORA / "build/host/vcpkg/installed/x64-windows-static/include/nlohmann/ordered_map.hpp",
                                                   MAJORA / "build/host/vcpkg/installed/x64-windows-static/include/nlohmann/detail/input/lexer.hpp",
                                                   MAJORA / "build/host/vcpkg/installed/x64-windows-static/include/nlohmann/detail/conversions/to_chars.hpp",
                                                   MAJORA / "build/host/vcpkg/installed/x64-windows-static/include/nlohmann/detail/output/serializer.hpp"})))
                    if not (output.is_relative_to(MAJORA / "scratch") and
                            (from_lus or from_majora or from_cvars or from_libzip or from_zlib or from_tinyxml2 or from_imgui or
                             from_png or from_gfxd or from_interpreter or
                             from_logging or from_runtime or from_prism or from_fixed_point or from_input or from_codecs) and
                            projector.is_relative_to(MAJORA)):
                        raise ValueError("Majora projected header escaped selected roots")
                    shared = (base / row["shared_projector"].removeprefix("shipyard/")
                              if row.get("shared_projector") else None)
                    lock_path = MAJORA / row["lock"]
                    existing = conn.execute(
                        "SELECT output_sha,projector,projector_sha,upstream,upstream_sha,lock_path,lock_sha "
                        "FROM projection WHERE consumer='majora' AND output=?", (str(output),)).fetchone()
                    if existing is not None:
                        expected = (row["sha256"], str(projector), sha(projector), str(upstream),
                                    row["upstream_sha256"], str(lock_path), sha(lock_path))
                        if not from_interpreter or existing != expected:
                            raise ValueError("Conflicting Majora projection provenance")
                        continue
                    conn.execute("INSERT INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 ("majora", str(output), row["sha256"], str(projector), sha(projector),
                                  str(shared) if shared else None, sha(shared) if shared else None,
                                  str(upstream), row["upstream_sha256"], str(lock_path), sha(lock_path)))
            for consumer, output, projector, shared, upstream, pinned, lock in projections():
                output_name = "shader_builder.cpp"
                expected_output = (data(MODERN / "scratch/prism-xdk/manifest.json")["outputs"][output_name]
                                   if consumer == "modern" else
                                   data(SMASH / "scratch/prism-xdk/manifest.json")["outputs"][output_name])
                conn.execute("INSERT INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (consumer, str(output), expected_output, str(projector), sha(projector), str(shared),
                              sha(shared), str(upstream), pinned, str(lock), sha(lock)))
            modern_base, _ = selected_base(MODERN)
            for consumer, output, projector, shared, upstream, pinned, lock, expected in modern_manifest_projections(modern_base):
                conn.execute("INSERT OR IGNORE INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (consumer, str(output), expected, str(projector), sha(projector),
                              str(shared) if shared else None, sha(shared) if shared else None,
                              str(upstream), pinned, str(lock) if lock else None, sha(lock) if lock else None))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def refresh_modern():
    """Refresh Modern relationships while preserving other consumer snapshots."""
    STATE.mkdir(parents=True, exist_ok=True)
    with FileLock(str(DB) + ".lock", timeout=60):
        conn = sqlite3.connect(DB, timeout=60)
        try:
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            for table in ("snapshot", "selection", "projection"):
                conn.execute(f"DELETE FROM {table} WHERE consumer='modern'")
            base, lock = selected_base(MODERN)
            verify_base(base, lock)
            identity = shipyard_identity(base)
            manifest = MODERN / "scratch/project-xdk/manifest.json"
            conn.execute("INSERT INTO snapshot (consumer,root,root_head,base,base_head,lock_path,lock_sha,manifest_path,manifest_sha,compile_sha,serena_sha,indexer,updated,canonical,canonical_head,canonical_config_sha,dependency_config_sha,history_root,repository_relation,history_relation) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("modern", str(MODERN), head(MODERN), str(base), head(base), str(lock), sha(lock),
                          str(manifest), sha(manifest), sha(MODERN / "compile_commands.json"),
                          sha(MODERN / ".serena/project.yml"), VERSION, time.time(),
                          identity["canonical"], identity["canonical_head"],
                          sha(git_dirs(SHIPYARD)[1] / "config"), sha(git_dirs(base)[1] / "config"),
                          identity["history_root"], identity["repository_relation"],
                          identity["history_relation"]))
            for source, row, origin in modern_rows(base):
                kind = "shared" if source.is_relative_to(base) else (
                    "generated" if "scratch" in source.parts else "consumer")
                receipt = MODERN / row.get("report", "scratch/project-xdk/manifest.json")
                conn.execute("INSERT INTO selection (consumer,config,source,source_sha,kind,manifest_path,receipt,options_json,receipt_sha) VALUES (?,?,?,?,?,?,?,?,?)",
                             ("modern", "xdk-release", str(source), row.get("sha256", sha(source)), kind,
                              str(origin), str(receipt), json.dumps(row.get("options", [])), sha(receipt)))
            for consumer, output, projector, shared, upstream, pinned, projection_lock in projections():
                if consumer != "modern":
                    continue
                expected = data(MODERN / "scratch/prism-xdk/manifest.json")["outputs"]["shader_builder.cpp"]
                conn.execute("INSERT INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (consumer, str(output), expected, str(projector), sha(projector), str(shared),
                              sha(shared), str(upstream), pinned, str(projection_lock), sha(projection_lock)))
            for consumer, output, projector, shared, upstream, pinned, projection_lock, expected in modern_manifest_projections(base):
                conn.execute("INSERT OR IGNORE INTO projection VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (consumer, str(output), expected, str(projector), sha(projector),
                              str(shared) if shared else None, sha(shared) if shared else None,
                              str(upstream), pinned, str(projection_lock) if projection_lock else None,
                              sha(projection_lock) if projection_lock else None))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _status(path: str | None, stored: str | None) -> str:
    if path is None:
        return "unmapped"
    current = sha(Path(path))
    return "current" if current and current == stored else ("deleted" if current is None else "stale")


def _snapshot_status(conn: sqlite3.Connection, consumer: str) -> str:
    snap = conn.execute("SELECT * FROM snapshot WHERE consumer=?", (consumer,)).fetchone()
    if snap is None or snap["indexer"] != VERSION:
        return "stale-indexer"
    try:
        topology_stale = bool(snap["canonical"] and (
            head(Path(snap["canonical"])) != snap["canonical_head"] or
            sha(git_dirs(Path(snap["canonical"]))[1] / "config") != snap["canonical_config_sha"] or
            sha(git_dirs(Path(snap["base"]))[1] / "config") != snap["dependency_config_sha"] or
            (git_dirs(Path(snap["base"]))[1].resolve() ==
             git_dirs(Path(snap["canonical"]))[1].resolve()) !=
            (snap["repository_relation"] == "linked-worktree-of-canonical")))
        manifest_changed = (_status(snap["manifest_path"], snap["manifest_sha"]) != "current"
                            if snap["manifest_sha"] else Path(snap["manifest_path"]).is_file())
        if (topology_stale or
            _status(snap["lock_path"], snap["lock_sha"]) != "current" or
            manifest_changed or
            (snap["source_lock_path"] is not None and
             _status(snap["source_lock_path"], snap["source_lock_sha"]) != "current") or
            sha(Path(snap["root"]) / "compile_commands.json") != snap["compile_sha"] or
            sha(Path(snap["root"]) / ".serena/project.yml") != snap["serena_sha"] or
            head(Path(snap["root"])) != snap["root_head"] or
            head(Path(snap["base"])) != snap["base_head"] or
            selected_base(Path(snap["root"]))[0] != Path(snap["base"])):
            return "stale-configuration"
    except (OSError, ValueError):
        return "stale-configuration"
    if consumer == "majora" and snap["manifest_sha"] is None:
        return "pending-build-selection"
    return "current"


def topology() -> dict:
    """Bounded persisted checkout relationship for the two active consumers."""
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        results = []
        for row in conn.execute("SELECT * FROM snapshot ORDER BY consumer"):
            lock = data(Path(row["lock_path"])) if Path(row["lock_path"]).is_file() else {}
            results.append({"consumer": row["consumer"], "consumer_worktree": row["root"],
                            "selected_builds": [r[0] for r in conn.execute(
                                "SELECT DISTINCT config FROM selection WHERE consumer=? ORDER BY config",
                                (row["consumer"],))],
                            "maintained_worktree": row["canonical"],
                            "maintained_revision": row["canonical_head"],
                            "selected_worktree": row["base"],
                            "selected_revision": row["base_head"],
                            "locked_revision": lock.get("git_revision"),
                            "repository_relation": row["repository_relation"],
                            "history_relation": row["history_relation"],
                            "history_root": row["history_root"],
                            "maintained_baseline_sha": sha(Path(row["canonical"]) / "baseline.json")
                                if row["canonical"] else None,
                            "selected_baseline_sha": sha(Path(row["base"]) / "baseline.json"),
                            "locked_baseline_sha": lock.get("baseline_sha256"),
                            "maintained_api_version": data(Path(row["canonical"]) / "baseline.json").get("api_version")
                                if row["canonical"] and (Path(row["canonical"]) / "baseline.json").is_file() else None,
                            "selected_api_version": lock.get("api_version"),
                            "lock": row["lock_path"],
                            "upstream_source_lock": row["source_lock_path"],
                            "upstream_source_lock_sha": row["source_lock_sha"],
                            "status": _snapshot_status(conn, row["consumer"]),
                            "coverage": ("source and Shipyard locks; Xbox selection pending" if
                                         row["consumer"] == "majora" and not row["manifest_sha"] else
                                         "locks, selected manifest, receipts, local Git ancestry, file hashes")})
        return {"indexer": VERSION, "results": results, "truncated": False}
    finally:
        conn.close()


def refresh_all(*, verbose: bool = True):
    """Regenerate selected analysis maps and metadata with one cross-process writer."""
    STATE.mkdir(parents=True, exist_ok=True)
    with FileLock(str(STATE / "refresh.lock"), timeout=120):
        all_commands(verbose=verbose)
        configure_serena("all", verbose=verbose)
        refresh()


def query(kind: str, path: str, *, limit: int = 10, offset: int = 0, line: int | None = None) -> dict:
    if not 1 <= limit <= 50 or offset < 0:
        raise ValueError("limit must be 1..50 and offset nonnegative")
    target = str(Path(path).resolve())
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        if kind == "consumers":
            sql = "SELECT * FROM selection WHERE source=? ORDER BY consumer,config LIMIT ? OFFSET ?"
            rows = conn.execute(sql, (target, limit + 1, offset)).fetchall()
            result = []
            for row in rows[:limit]:
                status = _status(row["source"], row["source_sha"])
                config_status = _snapshot_status(conn, row["consumer"])
                snapshot = conn.execute("SELECT root,base,base_head,canonical,canonical_head,repository_relation,history_relation FROM snapshot WHERE consumer=?",
                                        (row["consumer"],)).fetchone()
                if config_status != "current":
                    status = config_status
                result.append({"consumer": row["consumer"], "config": row["config"],
                               "worktree": snapshot["root"] if snapshot else None,
                               "dependency": snapshot["base"] if snapshot else None,
                               "selected_revision": snapshot["base_head"] if snapshot else None,
                               "maintained_worktree": snapshot["canonical"] if snapshot else None,
                               "maintained_revision": snapshot["canonical_head"] if snapshot else None,
                               "repository_relation": snapshot["repository_relation"] if snapshot else None,
                               "history_relation": snapshot["history_relation"] if snapshot else None,
                               "source": row["source"], "source_sha": row["source_sha"],
                               "kind": row["kind"], "manifest": row["manifest_path"],
                               "receipt": row["receipt"],
                               "receipt_status": _status(row["receipt"], row["receipt_sha"]),
                               "coverage": "build-selected; semantic references partial",
                               "status": status})
        elif kind == "origin":
            rows = conn.execute("SELECT * FROM projection WHERE output=? LIMIT ? OFFSET ?",
                                (target, limit + 1, offset)).fetchall()
            result = []
            for row in rows[:limit]:
                snapshot = conn.execute("SELECT root,base,base_head,canonical,canonical_head,repository_relation,history_relation FROM snapshot WHERE consumer=?",
                                        (row["consumer"],)).fetchone()
                selected = conn.execute("SELECT config FROM selection WHERE consumer=? AND source=? LIMIT 1",
                                        (row["consumer"], row["output"])).fetchone()
                status = {"output": _status(row["output"], row["output_sha"]),
                          "projector": _status(row["projector"], row["projector_sha"]),
                          "shared_projector": _status(row["shared_projector"], row["shared_projector_sha"]),
                          "upstream": (_status(row["upstream"], row["upstream_sha"])
                                       if row["upstream_sha"] else "unpinned"),
                          "lock": _status(row["lock_path"], row["lock_sha"])}
                status["configuration"] = _snapshot_status(conn, row["consumer"])
                mapped = map_line(Path(row["output"]), line) if line and status["output"] == "current" else None
                result.append({"consumer": row["consumer"],
                               "config": selected["config"] if selected else None,
                               "worktree": snapshot["root"] if snapshot else None,
                               "dependency": snapshot["base"] if snapshot else None,
                               "selected_revision": snapshot["base_head"] if snapshot else None,
                               "maintained_worktree": snapshot["canonical"] if snapshot else None,
                               "maintained_revision": snapshot["canonical_head"] if snapshot else None,
                               "repository_relation": snapshot["repository_relation"] if snapshot else None,
                               "history_relation": snapshot["history_relation"] if snapshot else None,
                               "output": row["output"],
                               "line": line, "line_mapping": mapped, "projector": row["projector"],
                               "shared_projector": row["shared_projector"], "upstream": row["upstream"],
                               "output_sha_pinned": row["output_sha"],
                               "upstream_sha_pinned": row["upstream_sha"], "lock": row["lock_path"],
                               "coverage": "#line" if mapped else ("projector/source-lock (no exact #line)"
                                   if row["lock_path"] else "manifest origin (no source lock or exact #line)"),
                               "status": status})
        elif kind == "affected":
            contexts = {r["consumer"]: (r["root"], r["base"])
                        for r in conn.execute("SELECT consumer,root,base FROM snapshot")}
            selected = conn.execute("SELECT * FROM selection WHERE source=? OR manifest_path=? ORDER BY consumer,config,source",
                                    (target, target)).fetchall()
            projected = conn.execute("SELECT * FROM projection WHERE output=? OR projector=? OR shared_projector=? OR upstream=? OR lock_path=? ORDER BY consumer,output",
                                     (target, target, target, target, target)).fetchall()
            all_results = [
                {"consumer": r["consumer"], "config": r["config"],
                 "worktree": contexts.get(r["consumer"], (None, None))[0],
                 "dependency": contexts.get(r["consumer"], (None, None))[1],
                 "source": r["source"],
                 "status": _status(r["source"], r["source_sha"]),
                 "configuration": _snapshot_status(conn, r["consumer"]), "relationship": "selection"}
                for r in selected]
            for r in projected:
                selected_config = conn.execute(
                    "SELECT config FROM selection WHERE consumer=? AND source=? LIMIT 1",
                    (r["consumer"], r["output"])).fetchone()
                all_results.append({"consumer": r["consumer"],
                                    "config": selected_config["config"] if selected_config else None,
                                    "worktree": contexts.get(r["consumer"], (None, None))[0],
                                    "dependency": contexts.get(r["consumer"], (None, None))[1],
                                    "output": r["output"], "upstream": r["upstream"],
                                    "projector": r["projector"], "relationship": "projection",
                                    "status": _status(r["output"], r["output_sha"]),
                                    "configuration": _snapshot_status(conn, r["consumer"])})
            result = all_results[offset:offset + limit]
            rows = all_results
        else:
            raise ValueError("kind must be consumers, origin, or affected")
        return {"indexer": VERSION, "query": kind, "path": target, "offset": offset,
                "limit": limit, "results": result, "truncated": len(rows) > offset + limit,
                "next_offset": offset + limit if len(rows) > offset + limit else None}
    finally:
        conn.close()


def map_line(path: Path, line: int) -> dict | None:
    if line < 1 or not path.is_file():
        return None
    current_file = None
    current_line = None
    for number, text in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = re.match(r'\s*#line\s+(\d+)\s+"([^"]+)"', text)
        if match:
            current_file, current_line = match.group(2), int(match.group(1))
        elif current_line is not None:
            if number == line:
                return {"source": current_file, "line": current_line}
            current_line += 1
        if number >= line:
            break
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe-db")
    sub.add_parser("all-db")
    sub.add_parser("probe-config")
    sub.add_parser("all-config")
    sub.add_parser("refresh")
    sub.add_parser("refresh-modern")
    sub.add_parser("refresh-all")
    q = sub.add_parser("query")
    q.add_argument("kind", choices=("consumers", "origin", "affected"))
    q.add_argument("path")
    q.add_argument("--line", type=int)
    q.add_argument("--limit", type=int, default=10)
    q.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    if args.command == "probe-db":
        probe_commands()
    elif args.command == "all-db":
        all_commands()
    elif args.command == "probe-config":
        configure_serena("probe")
    elif args.command == "all-config":
        configure_serena("all")
    elif args.command == "refresh":
        refresh()
    elif args.command == "refresh-modern":
        refresh_modern()
    elif args.command == "refresh-all":
        refresh_all()
    else:
        print(json.dumps(query(args.kind, args.path, limit=args.limit, offset=args.offset, line=args.line), indent=2))


if __name__ == "__main__":
    main()
