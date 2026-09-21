# Current SoH application resource leaves

This bounded projection preserves the full Shipwright9.2.3 translation units for
Background, PlayerAnimation, Text, Array and Cutscene. Each type and its factory
compile as a separate production TU: ten actual application objects, including
both binary and XML Text factories. Nothing is function-excluded or replaced by
a test harness. Twenty-one current source/header inputs are normalized and
SHA-256 pinned in `sources.lock.json` before any generated output is written.

The generator only changes inherited-constructor forwarding, scoped enum
syntax/switch dispatch, unsupported final/override syntax and the existing
two-reader variant API. Array's real Fast3D vertex definition is included before
the forwarding constructor so XDK can instantiate its vector destructor. The
complete generated files are under `scratch/soh-resources-xdk/generated/soh`;
upstream files remain untouched. The existing binary, resource, logging and
Fast3D generated headers are prerequisites and must precede upstream headers.

## Serialization and endian boundary

The existing archive-marker evidence is documented in
`porting/ASSET_BASELINE.md` and reproduced by `tools/shipyard/verify_assets.py`.
The supplied PC archives have little-endian resource records and big-endian
version metadata. These are separate markers, not a global archive byte order:

- `ResourceLoader::ReadResourceInitDataBinary` reads the record marker, then
  interprets header integers in that order. `ResourceLoader` supplies the
  payload reader with `initData->ByteOrder` before the factory runs.
- `Archive::Load` independently reads the `version` entry's byte-order marker
  before its 32-bit game version. These application factories do not parse or
  override either marker.
- Background bytes and Text string/control bytes remain byte sequences.
  PlayerAnimation's signed 16-bit values, Text IDs, and Array scalar/vertex
  values use the existing typed reader. No additional swap is appropriate.
- Cutscene stores a mixture of native 32-bit values and records containing
  bytes/halfwords. All four upstream raw-read helpers remain verbatim. The
  three active halfword helpers swap only the halfwords when the reader order
  differs from native order. They must not swap the entire 32-bit slot. Camera
  continuation reads byte zero of the resulting record, independent of host
  order. The unused BBBB helper remains present as in the current source.
- The existing binary projection selects `Native = Big` on Xenon. Thus LE
  payloads convert to native values there, while BE payloads remain native.
  No automatic desktop swap or assumption that every asset is BE was added.

Array's current format repeats the scalar type per outer array record and
adds a component count for vectors. Its existing `ArrayCount`-based pointer
size and 8-byte scalar union storage are preserved, including the current
size behavior for vectors. Unsupported scalar cases remain upstream behavior;
this projection does not add formats or silently reinterpret storage.

## Verification

From the owned root, after preparing existing dependencies:

```powershell
python tools/shipyard/test_soh_resources_projection.py
python tools/shipyard/prepare_soh_resources.py --build
python tools/shipyard/test_soh_resources.py
```

Verified on 2026-09-20:

- Three Python checks pass: deterministic output/no unnecessary rewrites,
  atomic rejection of source drift, and verbatim cutscene endian helpers.
- All ten production TUs compile with the native XDK compiler, with no warnings
  in their recorded logs. An additional native ABI TU checks BE marker values,
  32-bit pointers, 8-byte ScalarData, the 16-byte vertex and field offsets, and
  resource/array tag constants. Every emitted object is PPC BE COFF `0x1f2`.
- The same independent serialization contract compiles and runs against all ten
  original TUs and all ten projected TUs, with the real LUS reader/factory base,
  resource base, memory stream and TinyXML2 implementation. Results agree for
  LE and BE payloads, signed animation values, Text embedded NUL/control bytes,
  XML entities and terminators, scalar/vector/vertex arrays, Cutscene HH/HBB/BBH
  fields and camera termination, empty resources, truncated animation payload,
  and invalid reader/format rejection. Fixtures are serialized independently
  of the reader's paired BinaryWriter.

`scratch/soh-resources-xdk/xdk/build.json` records exact native commands, source
hashes and object hashes. Per-TU compiler logs and host build/run evidence are
beside it; `verification.json` records the host differential. This is compiler
and host behavior evidence, not Xenon execution, resource registration, a
linked application, archive startup, renderer integration or boot proof.

## Remaining application resource consumers

The nine remaining top-level type/factory pairs are Animation, AudioSample,
AudioSequence, AudioSoundFont, CollisionHeader, Path, Scene, Skeleton and
SkeletonLimb. All 25 scene-command type/factory pairs, the common
SceneCommandFactory, Path/scene-command loggers, OTRGlobals registration and
ResourceManagerHelpers consumers remain outside this increment.

Future audio work must preserve its distinct payload contracts: SoundFont V2
applies `BE16SWAP` to decoded envelope values because the downstream envelope
representation is BE bytes; that macro must be identity on Xenon. AudioSequence
XML uses a writer explicitly set to Big, while sample/sequence copies carry
encoded byte streams. Those paths were inspected for the endian audit, not
projected or claimed operational here. Path also introduces logging/cvar/math
dependencies and both binary/XML implementations; it should be advanced as a
whole factory TU when those boundaries are ready.
