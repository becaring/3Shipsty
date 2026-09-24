# Current resource leaf projection

This bounded increment projects **21 actual LUS source files** from commit
`fdcaf6336776d24a6408d016b0a52243f108f250`: File, ResourceType, IResource/Resource,
the factory interfaces, binary/XML validation, and Blob/Json/Shader types and
factories. It does not yet project Archive, ArchiveManager, ResourceLoader or
ResourceManager. No substitute manager, Context, logger, archive reader or game
consumer is supplied. No source or reference checkout is modified.

`sources.lock.json` records normalized SHA-256 for every source.
`tools/shipyard/prepare_resources.py` verifies all inputs
before writing output under `scratch/resources-xdk/generated`. UTF-8 BOM and CRLF
checkout differences are normalized. Changed input fails closed. Generated headers
have physical include guards and source-relative `#line` mapping; the manifest
records every changed source line and its replacement. Output is deterministic.

The transforms preserve current function bodies. They replace scoped-enum syntax,
inline static storage, default member initialization, inherited constructors,
`final`/`override` syntax and the reached variant calls. `gAltAssetPrefix` has one
definition in the generated Resource.cpp. Initialization moves into the same
constructors. The original resource destructor trace and factory error logging are
retained and compiled with `SPDLOG_ACTIVE_LEVEL=0` so native compilation covers
their real formatting calls. No Smash Blob padding, MIDI handling, archive manifests,
file buffer offsets, silent destructor, or manager cache correction is imported.

## Narrow variant contract

The projected resources include Shipyard's physical
`sources/value_types/xbox_compat/variant.h` through `<xbox_compat/variant.h>`.
The reached File shared-pointer pair and cache error/shared-pointer shape use the
same canonical implementation as other Shipyard consumers. Full manager
integration still needs its own tests.

## Validation and exact commands

Run from `D:/Projects/3Shipsty9.x` after the binary, JSON and logging generators:

```powershell
python -B tools/shipyard/tests/test_resources.py --baseline-only
python -B tools/shipyard/prepare_resources.py
python -B tools/shipyard/tests/test_resources_variant.py
python -B tools/shipyard/tests/test_resources_generation.py
python -B tools/shipyard/tests/test_resources.py
python -B tools/shipyard/tests/test_resources.py --integration-probe
```

The baseline was recorded before these resource transforms: all nine untouched
resource leaf translation units fail on XDK's absent `<variant>`. Every compiler
invocation, flags, output and exit status is in per-TU JSON evidence beneath
`scratch/resources-xdk/xdk-original`, `xdk-generated`, `host-original`,
`host-generated`, `variant`, and `integration-probe`.

Host tests compile and execute the original nine current TUs against original
binarytools, official JSON headers and real spdlog, then compile and execute the
generated TUs against the owned binary/JSON/async/logging implementations. Identical
results cover endian Blob payloads, exact data/pointer sizes, retained init-data
ownership, dirty state, wrong format/reader rejection, JSON comments/arrays/scalars,
invalid JSON and truncated binary exceptions. Two current behaviors are deliberately
preserved: ReadCString retains its trailing null byte (including Shader pointer
size), and XML validation accepts an XML shared-pointer alternative even when null.
Blob remains exactly its declared payload size.

The variant test additionally compares std::variant ownership counts, default
alternative, copy/type switch, move/moved-from state, null assignment, bad access,
throwing conversion and valueless recovery. The generator tests cover deterministic
bytes/mapping, BOM/CRLF, source rejection, canonical variant use and output confinement.

Native validation uses `C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/cl.exe`
with `/EHsc /D_XBOX /D_XBOX_VER=200 /DSPDLOG_ACTIVE_LEVEL=0`. The nine actual resource
TUs and the contract instantiate to PowerPC big-endian COFF (`0x1f2`). This is compile
evidence, **not target execution or a complete resource subsystem link**.
`scratch/resources-xdk/verification.json` records object hashes and host output.

The host JSON provider is compiled separately to `json-backend.obj`: Windows treats
the current resource `Json.cpp` and provider `json.cpp` as the same object basename.
This prevents accidental object replacement while retaining both real TUs.

## Dependency and continuation evidence

Include order for this increment is generated resources, generated binarytools,
owned JSON public headers, generated JSON backend, generated logging core,
generated logging compatibility, owned fmt projection, `platform/shipyard`, then
the repository root. The test driver records absolute paths. Host linking includes
owned JSON implementation, actual async native support, logging chrono and
environment support. Broader provider constraints remain in their own READMEs;
this factory contract does not establish arbitrary formatting or JSON equivalence.

The integration probe compiles all seven remaining **real current TUs** with the
completed providers available and `INCLUDE_MPQ_SUPPORT` enabled. It intentionally
does not claim those original sources have been transformed. First diagnostics:

| Current source | First unresolved boundary | Next bounded work |
|---|---|---|
| `src/ship/resource/ResourceLoader.cpp` | Relative include reaches original ResourceType syntax before the overlay | Project current loader header/TU together; preserve relative include relationships, designated keys and factory registration behavior |
| `src/ship/resource/ResourceManager.cpp` | Original `<mutex>` | Project current declarations and implementation to owned async/pool/variant; range loops, contains/starts_with and constructor syntax; test cache ownership/shutdown separately |
| `src/ship/resource/archive/Archive.cpp` | Original `<mutex>` in Archive.h | Project actual Archive and actual Context declarations; retain current metadata and legacy header behavior |
| `src/ship/resource/archive/ArchiveManager.cpp` | Original `<filesystem>` | Apply the filesystem agent's locked boundary hook, then lower actual loops and syntax without changing ordering/filtering |
| `src/ship/resource/archive/FolderArchive.cpp` | Archive.h mutex boundary | Project real filesystemtools with native stream path conversion; retain disk reading behavior |
| `src/ship/resource/archive/O2rArchive.cpp` | Archive.h mutex boundary | Use parent-provided real libzip/zlib headers/objects and actual archive classes |
| `src/ship/resource/archive/OtrArchive.cpp` | Original `<mutex>` before StormLib | Keep MPQ enabled; integrate actual pinned StormLib v9.25 rather than compiling an empty conditional TU |

These are ordinary unfinished compatibility work, not proven fundamental blockers.
Later dependencies visible in source include actual Context.h's audio settings and
spdlog async declarations, current Utils/StringHelper/glob, and tinyxml2. Context
must remain the actual class. The filesystem provider exports
`tools/shipyard/prepare_filesystem.py::project_boundary(relative, original)`; its
runtime namespace is `xbox_compat::filesystem`, with locks in `Shipyard::Async`.
The projected BS v4.1.0 pool remains under `scratch/async-xdk/generated`.

Current upstream manager concerns discovered during the audit are separate behavior
changes: nested task waits with one worker, cache insertion locking, drain order,
and UnloadResource bookkeeping. No correction is smuggled into this leaf compiler
projection. The broader differential audit remains `porting/resources-audit.md`.
