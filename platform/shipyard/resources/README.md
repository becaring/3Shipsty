# Current resource leaf projection

This module projects **21 actual LUS source files** from commit
`fdcaf6336776d24a6408d016b0a52243f108f250`: File, ResourceType, IResource/Resource,
the factory interfaces, binary/XML validation, and Blob/Json/Shader types and
factories. Archive, ArchiveManager, ResourceLoader, and ResourceManager have separate
projection providers. No substitute manager, Context, logger, archive reader or game
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

Run from the repository root after the binary, JSON and logging generators:

```powershell
python -B tools/shipyard/tests/test_resources.py --baseline-only
python -B tools/shipyard/prepare_resources.py
python -B tools/shipyard/tests/test_resources_variant.py
python -B tools/shipyard/tests/test_resources_generation.py
python -B tools/shipyard/tests/test_resources.py
python -B tools/shipyard/tests/test_resources.py --integration-probe
```

The original source requires `<variant>`, which XDK does not provide. Compiler
invocations, flags, output, and exit status are recorded beneath
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

Native validation uses the installed XDK `cl.exe`
with `/EHsc /D_XBOX /D_XBOX_VER=200 /DSPDLOG_ACTIVE_LEVEL=0`. The nine actual resource
TUs and the contract instantiate to PowerPC big-endian COFF (`0x1f2`). This is compile
evidence, **not target execution or a complete resource subsystem link**.
`scratch/resources-xdk/verification.json` records object hashes and host output.

The host JSON provider is compiled separately to `json-backend.obj`: Windows treats
the current resource `Json.cpp` and provider `json.cpp` as the same object basename.
This prevents accidental object replacement while retaining both real TUs.

## Dependencies and integration

Include order for this module is generated resources, generated binarytools,
owned JSON public headers, generated JSON backend, generated logging core,
generated logging compatibility, owned fmt projection, `platform/shipyard`, then
the repository root. The test driver records absolute paths. Host linking includes
owned JSON implementation, actual async native support, logging chrono and
environment support. Broader provider constraints remain in their own READMEs;
this factory contract does not establish arbitrary formatting or JSON equivalence.

Archive and manager providers use the real Context, filesystem, async/pool,
JSON, XML, and archive-library contracts. Their source projection and runtime
verification are separate from these resource-leaf checks. The filesystem
provider exposes `prepare_filesystem.py::project_boundary(relative, original)`;
its runtime namespace is `xbox_compat::filesystem`.

The durable format and lifetime contracts are in the
[resource reference](../../../docs/reference/RESOURCES.md).
