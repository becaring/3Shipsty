# Building and contributing

## Checkout and dependencies

You need Windows, Git, Python 3, the Xbox 360 XDK compiler, linker and MSBuild
integration, and a desktop MSVC toolchain for host contracts. Build scripts
contain toolchain paths, so check them against your installation.

Clone Shipyard as a sibling named `Shipyard`. The game lock uses
`"base": "../Shipyard"`. Check out the revision recorded in
`platform-base.lock.json`; the resolver verifies its API version and baseline
digest before loading shared tools. For another location, set
`$env:XBOX360_PLATFORM_BASE = 'D:/path/to/Shipyard'`. This changes only the
location; the revision and baseline requirements still apply.

```powershell
git submodule update --init --recursive
python -m pip install -r tools/shipyard/requirements.txt
python -B tools/shipyard/setup_dependencies.py
```

The dependency lock and each module's source lock define the required inputs.
Keep dependency licenses with their snapshots. Supply a ROM and the SDK
separately. See [assets](ASSETS.md) and [upstream](UPSTREAM.md).

## Xbox build

Run from the game repository root, stopping on failure:

```powershell
python -B tools/shipyard/regenerate_all.py
python -B tools/shipyard/generate_xdk_project.py
python -B tools/shipyard/build_xdk_project.py --jobs 8
python -B tools/shipyard/link_xdk_application.py
```

Regeneration puts the providers in order. `--list` prints the stages; `--resume`
continues only when the recorded source identity matches. The compile driver
builds independent shards and checks object hashes. The linker checks source,
object, manifest, and header identities, then produces
`scratch/link-integration/3Shipsty.xex`. Build records include the Git revision.

For a module, run `tools/shipyard/prepare_<module>.py` with hyphens replaced by
underscores, then its matching `test_<module>.py` or test under
`tools/shipyard/tests`. Read the command's options before using `--build`,
because some providers have separate compilation switches. Prepare shared
dependencies first. Edit adapters and projectors, then regenerate their output.

## Host checks

The portable suite needs Python 3.13 and Git. It needs no game assets or XDK:

```powershell
python -B tools/check_hygiene.py
python -B tools/shipyard/test_host_ci.py
```

Other contracts under `tools/shipyard/test_*.py` and `tools/shipyard/tests`
need their locked dependency snapshots, generated sources, and a desktop C++
compiler. Native-object assertions also need matching build records.
Compile with precise floating point. Keep source locks, numeric behavior,
object lifetimes, and the original C/C++ language selection.

## Desktop build

The pinned desktop application builds with CMake. On Windows, use Visual Studio
2022 with Desktop development with C++, the v143 toolset, and a Windows SDK.
Initialize submodules, then configure `cmake -S . -B build/x64 -A x64`.
Build `GenerateSohOtr` for the application archive, then build the application
with `cmake --build build/x64 --config Release`. On Linux and macOS, follow the
dependency requirements in the pinned CMake configuration. The Xbox application
builds its own archives from a ROM, so this desktop build is optional.

## Mods and music

Code mods go in the game's source and hooks. CVars and menu widgets expose
settings. Keep default values so a new option changes nothing until it is
enabled. Follow source locks when updating a pinned input.

Custom sequences use matching `.seq` and `.meta` files. The metadata has two
lines: the display name, then the instrument-set number in hexadecimal. In Retro,
choose Create OTR, Custom Sequences, the sequence folder, Stage Files, Finalize
OTR, then Generate OTR. Put the result in `mods` beside `oot.o2r` and select
sequences in the SFX Editor. The limit is 1,024 sequences including the
original music. Sound-effect and instrument replacement are unsupported.

Desktop SDL controller mappings come from SDL_GameControllerDB through the
pinned CMake build. Xbox physical input goes through its native controller
adapter, so desktop mapping-file changes add no Xbox hardware capabilities.

## Optional maintainer navigation

The fixed read-only Serena servers provide symbols and bounded reads.
`shipyard_nav` reports selected builds, generated origins, and diff impact.
Check freshness and coverage before editing. Refresh with
`refresh_navigation_index` after dependency, branch, manifest, or configuration
changes, and restart affected Serena servers after configuration changes.
A partial index that shows no references does not prove a file is unused.

`tools/code_nav/nav.py` and `launch_serena.py` contain maintainer workstation
paths. These tools are optional and are not build dependencies. The navigation
runtime lives in the primary Modern checkout's `scratch/code-nav`.
To remove it, take only its five MCP registrations (`serena_shipyard`,
`serena_modern`, `serena_smash`, `serena_majora`, `shipyard_nav`) and navigation
instructions out of the local Codex configuration, restart Codex, and delete the
generated Serena configs, analysis compile databases, and navigation runtime.
Leave unrelated configuration and files alone.
