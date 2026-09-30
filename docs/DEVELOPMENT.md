# Development

## Requirements

The Xbox build uses Windows, Git, Python 3, the Xbox 360 XDK compiler/linker and
MSBuild integration, and a desktop MSVC toolchain for host contracts. Install
the parser packages with:

```powershell
python -m pip install -r tools/shipyard/requirements.txt
git submodule update --init --recursive
```

The build scripts contain toolchain location assumptions. Check the configured
XDK/MSBuild and host compiler locations before building on another machine.
The SDK, generated game archives, and proprietary toolchain binaries are not
part of this repository.

Provide a Shipyard checkout at the exact revision, API version, and baseline
hash in `platform-base.lock.json`. `XBOX360_PLATFORM_BASE` can select its location
without changing the dependency pin. The resolver verifies the contract before
loading shared Python tooling. Do not substitute an arbitrary Shipyard HEAD.

Source preparation also needs the dependency snapshots named by the source
locks and subsystem READMEs under `platform/shipyard`. `setup_dependencies.py` acquires or verifies the dependency snapshots in the
committed dependency lock; subsystem-specific preparation remains documented
by its owner. The regeneration command validates those inputs.

## Build

Run these commands from the repository root, stopping if any command fails:

```powershell
python -B tools/shipyard/setup_dependencies.py
python -B tools/shipyard/regenerate_all.py
python -B tools/shipyard/generate_xdk_project.py
python -B tools/shipyard/build_xdk_project.py --jobs 8
python -B tools/shipyard/link_xdk_application.py
```

Regeneration orders the selected subsystem providers and runs their preparation
and verification commands. `--list` prints its stages; `--resume` continues an
interrupted run only when the recorded source identity still matches.

The XDK project is a compile inventory. Use `build_xdk_project.py` to compile
its independent shards and verify the objects, then `link_xdk_application.py`
to link the application and create `scratch/link-integration/3Shipsty.xex`.
The linker requires current metadata and matching source, object, manifest,
and header hashes. Build metadata embeds the current Git revision.

A source checkout with no generated products needs all locked dependency inputs
before regeneration. The `--empty-owned-outputs` regeneration option removes its
listed generated directories and preserves the prior standard XEX and receipts;
it is not needed for an ordinary incremental build.

## Tests and changes

The portable CI suite needs only Python 3.13 and Git. It runs in a fresh checkout
without submodules, game assets, Shipyard, or the Xbox SDK:

```powershell
python -B tools/shipyard/test_host_ci.py
```

It checks dependency acquisition, interrupted regeneration, source selection,
and the 140-character limit in `prepare*.py` projectors. Keep embedded C++ helpers
in readable multiline blocks. Exact source-match strings must keep their bytes;
split their Python literals when needed. CI does not build an XEX or establish
runtime compatibility. The subsystem tests below require their documented inputs.

Subsystem contracts live beside the generators and in `tools/shipyard/tests`.
Use the tests named in the affected subsystem README. For interpolation:

```powershell
python -B tools/shipyard/test_interpolation.py
python -B tools/shipyard/prepare_interpolation.py --build
```

Change the maintained adapter or generator, regenerate, inspect the emitted
difference, and verify the affected host contracts and native translation units.
Keep C/C++ language semantics, numeric behavior, object lifetimes, and source locks
intact. Preserve precise floating-point compilation.

Generated manifests and compile/link receipts record what was built. Host
contracts, PowerPC compilation, Xenia execution, and physical-console testing
establish different properties; report their results separately. Runtime
checks should cover boot, menu/input, graphics, audio, mods, saves, and restart
persistence with the exact image and asset set used.

The preserved [upstream build guide](BUILDING.md) describes desktop platforms.
The commands above are the Xbox build entry points.
