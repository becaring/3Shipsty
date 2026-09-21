# Current SoH application resource leaves

This bounded projection preserves the full Shipwright9.2.3 translation units for
Background, PlayerAnimation, Text, Array, Cutscene, Animation, AudioSequence,
AudioSoundFont, CollisionHeader, Path, SkeletonLimb and Scene, plus all 25 current
scene-command type/factory pairs. Each type and its factory compile as a separate
production TU, together with SceneCommandFactory, PathLogger and
SceneCommandLoggers: 77 actual application objects. All binary/XML factory implementations in those files are
retained. Nothing in the production objects is function-excluded or replaced by
a test harness. One hundred fifty-nine current source/header inputs are normalized and
SHA-256 pinned in `sources.lock.json` before any generated output is written.
The source commit metadata is the actual release tag commit
`cb71e22a79bc5d1f688fa881795bbd93094895fc`; every locked input was checked against it.

The generator changes inherited-constructor forwarding, scoped enum syntax and
switch dispatch, unsupported final/override syntax, range loops, compile-time
constant syntax and the existing two-reader variant API. AudioSample's tuning
initializer is moved to both constructors without changing its value. It
qualifies pointer casts for XDK lookup and supplies an owned C99 bounded-format
adapter preserving required-length and terminated-truncation behavior. RTTI is
explicitly enabled because SoundFont XML patch loading uses dynamic_pointer_cast.
The native ABI TU rejects a build without RTTI.

Scene command IDs retain their fixed one-byte representation, strongly typed
comparisons, wrapping casts and hash lookup. Both Scene factory maps retain all
25 registrations; their C++17 inline static storage is emitted once in the Scene
factory TU. The complete 26-name lookup table remains a mutable vector with the
same entries. Decimal command-path suffixes use an owned exact unsigned-decimal
conversion. Scene-command inherited constructors are forwarded through the real
ISceneCommand/SceneCommand hierarchy. Their generated defaults retain the
zeroed payload state of original make_shared<T>() value-initialization.

Unused umbrella includes are removed from SkeletonLimbFactory and SetMeshFactory.
Scene commands that acquire resources include the real Context/ResourceManager
headers. Both logger headers use the real CVar bridge header instead of OTRGlobals. SoundFontFactory uses the three
actual audio enum declarations extracted verbatim from locked z64audio.h instead
of unrelated game-wide structs. No service declarations or implementations are
invented. The full ResourceManager and Context interfaces come from their
existing projections. Path uses the existing release CMake CVar definitions.
Array's real Fast3D vertex definition is included before
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
- AudioSequence's encoded bytes remain unchanged, and its XML-generated opcode
  stream still explicitly selects Big on BinaryWriter. SoundFont binary envelope
  fields retain BE16SWAP after typed reads. XML envelope fields now use BE16SWAP
  instead of unconditional BSWAP16: the downstream envelope representation is BE
  bytes, so native Xenon values must remain unchanged. Original and projected
  desktop envelope bytes match; the native ABI verifies that BE16SWAP is identity.
- Collision bounds, vertices, polygon normals, surface words, camera indices and
  water-box fields remain typed reads with the same vector-backed pointer
  relocation and zero-camera fallback. Limb skin vertices, transforms and tagged
  display-list paths retain their actual layouts and lifetime ownership.

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
python tools/shipyard/test_soh_resources_methods.py
python tools/shipyard/test_soh_resources_scene.py
```

Verified on 2026-09-20:

- Six Python checks pass: deterministic output/no unnecessary rewrites, atomic
  source-drift rejection, retained production function signatures, verbatim
  cutscene helpers, source/audio endian invariants, and all Scene registrations,
  resource acquisitions, binary ID reads and CVar logging calls.
- All 77 production TUs compile with native XDK, plus the ABI TU. Every object is
  PPC BE COFF `0x1f2`. The ABI checks include 32-bit pointers, collision, limb,
  path, animation, audio, actor/transition, light, room and mesh sizes/offsets,
  one-byte scene IDs, resource tags, BE markers and RTTI.
  Seven existing AudioSettings qualified-enum extension warnings and one ABI
  include-order GIMMCMD macro redefinition warning remain. There are no
  dynamic-cast-without-RTTI warnings in the final build.
- The independent serialization contract compiles and runs seven complete type
  and factory pairs against original and projected sources: the previous five
  plus CollisionHeader and SkeletonLimb. Original SkeletonLimbFactory has only
  its unused libultraship umbrella include removed for the host test; every
  method body and actual type declaration remains intact. Both builds use real
  LUS readers, resource/factory bases, streams and TinyXML2. LE/BE and XML tests
  cover collision pointers, signed values, reversed surface-word input order,
  zero-camera fallback, Standard/LOD/Curve/Skin limb layouts, skin vertex and
  transform arrays, display-list tags and current XML LOD behavior, plus all
  prior empty/truncated/invalid-input contracts.
- A separate pure-method audit extracts complete original/projected Path XML,
  sequence opcode builders and sound-font envelope/enum methods. It matches
  all 2,068 mono/stereo/loop/delay bytecode cases, explicit BE envelope bytes,
  XML path pointers/counts, enum error text, and bounded-format behavior.
  `methods.json` records the limited scope; no Context/archive/CVar substitutes
  are linked into either host contract.
- A Scene audit executes 21 complete extracted XML command methods, every full
  scene-command type TU, the full Scene type TU, and the complete
  SceneCommandLoggers TU (25 loggers and their signature helper) against original and projected inputs. Binary/XML
  production factories are still compiled in full by XDK; the host audit does
  not replace their service calls. It checks 2,048 LE/BE command-ID reads,
  one-byte wrapping/hash lookup, all 26 command-name mappings, signed actor/light/
  settings fields, vector pointers and counts, ignored XML tags, mesh types
  0/1-multi/2, tagged display-list/background names, nullable collision/cutscene
  references, and every logger's actual formatted XML output. Both outputs match
  byte for byte. Complete extracted Scene XML parser methods also execute with
  those 21 real factories registered in the fixture, checking child ordering,
  unknown/unsupported commands, and inherited ID/type/path/version metadata.
  `scene-verification.json` records this bounded scope.

`scratch/soh-resources-xdk/xdk/build.json` records exact native commands, source
hashes and object hashes. Per-TU compiler logs and host build/run evidence are
beside it; `verification.json` records the host differential. This is compiler
and host behavior evidence, not Xenon execution, resource registration, a
linked application, archive startup, renderer integration or boot proof.

## Remaining application resource consumers

AudioSample and Skeleton type/factory pairs remain outside this increment.
AudioSampleFactory embeds the real dr_wav/dr_mp3/dr_flac implementations and
requires Vorbis/Ogg plus archive/Context audio loading. Those codec header/build
closures are not supplied by this resource projection. AudioSample.h is projected
as a real SoundFont dependency, but its production type/factory pair is not
counted as completed.

Skeleton.cpp contains the actual SkeletonPatcher, including live player,
pause-player, tunic, alternate/custom model and resource-manager behavior; it
cannot be advanced by compiling only the leaf GetPointer methods. Its OTRGlobals,
randomizer/game headers, inline static string, starts_with and actual global
runtime dependencies still need their complete projections. Nothing from those
patcher methods was removed or replaced here.

Scene and every current scene-command type/factory/logger now compile in full.
OTRGlobals registration and ResourceManagerHelpers consumers remain open. The
four service-dependent command factories (alternate headers, collision headers,
cutscenes and pathways) retain actual Context resource acquisition and still need
runtime integration. All 25 binary command factories retain their actual CVar
logging conditions and real logger calls. Full Scene binary dispatch and
service-backed XML dispatch remain native compiler and exact-registration
evidence, not claimed host service execution. Runtime factory execution for
Animation (including Link acquisition),
AudioSequence archive/XML loading, SoundFont sample resolution/patching, and
Path binary CVar/logging needs real Context/archive/CVar integration. Only the
explicit seven-pair runtime, pure-method and Scene XML/logger audits above are
execution evidence.
None of these checks establishes Xbox execution, registration, a linked
application, boot or playback.
