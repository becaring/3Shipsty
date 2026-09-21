# 3Shipsty status

2026-09-21. Active forward port of Shipwright **9.2.3 / Ackbar Delta** to Xbox 360.

First genuine bring-up estimate: roughly 60–65% complete, with considerable
uncertainty. The earlier 70% estimate weighted compilation too heavily before
linking or native execution. Selected application source coverage is 696/696 C and 146/398 C++ TUs,
with substantial LUS/dependency/native backend compilation established. This
estimate includes required integration and first execution; it does not measure
the complete polished-port effort or imply that a modern XEX has run. Update
this first-bring-up estimate in meaningful milestone reports as requested.
Remaining work is being grouped by complete application subsystems; individual
compile units remain internal evidence rather than user-facing milestones.

Latest integration work (earlier milestones below retain their historical scope):

- Complete seed Context, ItemLocation, fishsanity, Kaleido collectibles, item
  tables, hints, dungeons and trials are integrated. The full project passes with
  1,545 PPC objects/source hashes verified in randomizer-runtime-verification.json.
  Original/projected checks cover 2,520 location states, 65,536 item IDs, complete
  dungeon/trial combinations, hint formatting and ordered JSON. No target
  application execution is implied. Remaining application C++ count is 252.
- The user requested less granular work/reporting. Work is now grouped into
  complete functional batches. Two independent follow-on tasks cover location/
  static data and audio/cosmetic editors; root handles application/debug windows.
  Agents deliver one handoff and become idle. No more than three are active.
- Complete OTRGlobals.cpp now compiles with XDK. Actual initialization order,
  resource registrations, archive version readers and all application functions
  remain. Original/projected value checks match all 65,536 item IDs, accepted ROM
  versions, controller masks, audio defaults and 63,487 BMP printing cases.
- Complete SohGui.cpp retains all 28 real window registrations; full window
  declarations and 2,485 debugger/tracker table rows pass native/host checks.
  Complete AudioCollection.cpp and randomizer item.cpp compile with their actual
  canonical types, metadata, ownership and constructor defaults preserved.
- Startup owns early XNet/storage initialization; writable application paths use
  the selected container. Normal shutdown drains resource/codec work while
  Context remains strongly owned, then closes storage and XNet. Actual XContent
  selection, partial-init errors and application teardown remain unexecuted.
- The upstream header-local audio state gave save states a different mutex from
  the audio worker. One externally shared state now preserves all fields and
  static initialization. A two-source test reproduces the original separation
  and verifies shared identity and mutual exclusion in the projection.
- Desktop permissions dialog is resolved; the user confirmed this. Supplied
  baserom.z64 has already produced a verified retail NTSC 1.0 modern archive.
- Expanded main integration build passes: 1,536 selected PPC objects and all
  source hashes verified in scratch/project-xdk/save-settings-verification.json.
  Full Logic and save states are included; the obsolete standalone Logic
  constructor is excluded. No modern XEX or native execution yet.
- Full SaveManager.cpp now compiles: all 42 members, all 12 C bridges and all
  serialization keys remain. Four named default temporaries fix an isolated XDK
  EH backend crash without changing JSON/default values; actual string/JSON
  fallback, type-error and 1,818 enum round-trip checks agree with upstream.
- Full settings.cpp and option_descriptions.cpp compile, retaining 24 definitions,
  all 383 initializer values, 44 callbacks, 323 CVars and modern option/trick
  registrations. Full SaveManager/settings pass the main build, replacing their
  earlier fragments. Two agents are now independently translating hints and
  dungeon/trial implementations; root is working on genuine randomizer Context.
- The 260 remaining application C++ implementations, speech backend, final linking
  and native execution remain open; no placeholder link providers are supplied.

- Exact release and all three submodules fetched and verified; pristine baseline
  recorded in UPSTREAM_BASELINE.md.
- Differential platform audit recorded in PORTING_LEDGER.md and porting/*.md.
- BinaryReader/Writer/MemoryStream/Stream generated from current LUS now compile
  with XDK; central Xenon endian detection is corrected in the projection.
  Host original/generated contract and six generator tests pass.
- Current graphics interfaces, extracted current combiner decoder and generic
  shader lowerer compile with XDK. Four generator tests and 2,097,152 host
  decoder/layout cases pass. Full native graphics execution remains unvalidated.
- All 696/696 selected current application C TUs compile in one corrected
  XDK C run; no failed files are excluded.
  Async/futures/pool and filesystem platform
  foundations pass host differential and native object checks.
  Broad C-as-C++ compilation was rejected after actual actor/graph failures.
  No upstream source has been changed.
- All five exact current ImGui core TUs compile for XDK; eight-frame host draw
  data/atlas differential passes. Native UI/backend integration remains open.
- Nine current resource leaf TUs and eleven complete archive/loader/manager
  and utility TUs compile. Focused loader endian/registration and string-view/
  glob checks pass. Context and actual resource-manager execution remain open.
- Actual spdlog core and typed modern formatting corpus pass host/native checks.
  Default float/double formatting now matches 361,013 modern cases; the complete
  1,475-item XDK compile project passes with the corrected argument encoding. Ordered JSON is now a
  distinct DOM with tested insertion order. Generic initializer-list syntax,
  custom ADL/macros, sorted/ordered conversion and binary DOM remain open.
- No modern XEX has been produced or run. No gameplay or hardware claim.
- Full UIWidgets.cpp and the canonical modern option/menu types compile. Actual
  value/ownership/variant/text/color differentials pass; rendered frames remain
  untested. Full CustomMessageManager (67 functions) compiles, with 2,462 matching
  host output lines and 312 native UTF-8/control-byte literal proofs. ShipUtils
  and the real randomizer RNG compile, with seeded/container/rotation checks.
  Native entropy uses XNetRandom and requires startup ownership of XNet.
- All five GameInteractor units and all 23 selected Cheats/Fixes compile.
  The expanded 1,512-item selection passes; all source hashes and native PPC
  objects are verified in scratch/project-xdk/ui-services-verification.json.
  The newer menu/storage integration checkpoint is recorded below.
- Supplied unmodified baserom.z64 extracted with the exact official PC release:
  retail NTSC 1.0 oot.o2r has 38,390 CRC-verified entries and version 9.2.3.
  This archive is available for Xbox bring-up; target execution is unverified.
- Six complete application menu units compile, retaining all 449 enhancement,
  settings and developer-tool widget registrations. Actual menu/default/modal/
  notification and native UTF-8 contracts pass. The 1,521-item full integration
  build passes with source/object hashes in menu-storage-verification.json.
- Actual option.cpp now compiles, retaining its four existing canonical
  OptionValue definitions separately. Complete Settings/Option/OptionGroup and
  trick declarations pass native layout and original/projected tests covering
  232 options, 268 tricks and 85 groups. The real Settings constructor compiles
  in place. These two additional recipes pass the generated project separately;
  full settings.cpp remains pending and no constructor is duplicated.
- Initial startup archive/audio evidence used bounded method probes. This has
  since advanced to the full OTRGlobals.cpp compilation described above.
- Real SaveManager serialization (38/42 members, 11/12 C bridges) and native
  XContent/atomic publication compile. 161 original/projected serialized outputs,
  four base loaders, worker drain and failure preservation pass. The fragment is
  explicitly partial; randomizer methods and legacy conversion are still pending.
  Device mounting, producer shutdown, worker join and configuration persistence
  still need final startup integration. The complete controller editor now
  compiles with its original 41 functions and passes state/widget contracts.
  Legacy conversion explicitly validates producer order before writes and
  preserves existing backups. Both LE/BE decoder checks and 161 modern save
  outputs pass. The expanded 1,526-item integration compilation passes; source
  and PPC object hashes are in editor-legacy-verification.json. No target run.
- Full release-enabled Network.cpp and native XDK transport compile; actual
  host loopback passes framing, fragmented/coalesced data, reconnect and joined
  shutdown. Full application remote handlers and XNet lifetime integration are
  pending. GUI registration retains all 28 real windows and all 12 original
  method bodies; 2,485 table rows match, but its full compile still needs the
  canonical Item header. Item and AudioCollection are the two active subtasks.
- All fifteen modern cheat units compile, including the real randomizer bombchu
  capacity path. Three object-extension units and both ActorDB/config-migration
  units compile. ShipInit, variadic cursors, owning any/registry and ActorDB
  entry/table host differentials pass. All six migration bodies are unchanged.
- The complete randomizer Context/value header foundation preserves current
  fields and constructors. Eleven checks pass, including full member offsets,
  actual value methods and 256 OptionValue values. Complete ItemOverride and
  canonical OptionValue compile; full randomizer implementations remain pending.
- The complete OTRGlobals declaration compiles at 80 bytes on Xenon. Its eight
  font defaults are coupled to the retained real constructor projection; the
  full application implementation has not yet compiled.
- The 1,497-item assembled compile selection passes after these integrations
  and the endian header's C/C++ linkage correction; every object is verified
  PPC BE and every source matches its saved manifest hash. Eight further modern
  Fixes units and the complete game-effects unit compile outside that selection.
- The assembled XDK project compiles all 737 previously selected runtime and
  dependency units; every resulting object is verified PowerPC BE. All 696
  game C units also pass regeneration/recompilation with the exact release
  MPQ/logging definitions. This is integration compilation, not application linking.
- Full AudioSample binary/XML factory and actual WAV/MP3/FLAC/Vorbis workers
  now compile; resources total 79 production units. Host original/projected
  decoding matches across actual codec fixtures and serialized LE/BE samples.
  Native Vorbis contributes 22 real dependency units. Detached worker lifetime,
  rapid completion and exception contracts match std::thread on the host.
- Full Skeleton type/factory and modern player/pause/tunic/custom patcher compile,
  bringing application resources to 81 production TUs. Bounded pointer/removal
  methods match upstream; live resource patching remains a runtime gate.
- Current GameInteractor registry/state/C hook bridge compile (three TUs).
  Actual registry algorithms pass cross-TU storage, caller metadata, deferred
  removal, ID/pointer/filter dispatch and callback argument checks on the host.
- Remaining LUS bridges and libultra compile (11 upstream + one native TU).
  Final linking must retain static archive extraction because SoH stubs own five
  symbols in inactive LUS members. Native timers must stop before queue teardown.
- Complete current Fast3D display-list/matrix/vertex/light factories and texture
  factory versions compile. Original/projected results match all 19,167 applicable
  official archive records plus LE/BE/XML fixtures. Real resource mounting and
  GPU execution remain unvalidated; native point-light raw-union provenance is open.
- Matching official 9.2.3 archives generated by the exact official Windows
  extractor; both version records and all 36,925 entry CRCs pass. Native libzip,
  zlib and tinyxml2 build (131 objects); host native-boundary archive tests pass.
  Asset provenance is in porting/ASSET_BASELINE.md. Owned copied ROM SHA1:
  cee6bc3c2a634b41728f2af8da54d9bf8cc14099. Extraction is not Xbox validation.
- Exact stable Opus 1.6.1, opusfile 0.12 and Ogg 1.3.6 dependencies fetched;
  143 native codec objects compile; host real Ogg/Opus encode, memory/file
  decode, sample seek, EOF and invalid-input contracts pass. Xbox audio remains
  unvalidated. Exact LUS-patched StormLib also builds all 231 native objects;
  host encrypted MPQ and five lossless compression/seek/listfile checks pass.
- Current Audio factory/player/matrix decoder and native XAudio2/pool/logging
  compile (seven TUs). Host matrix PCM matches upstream at three rates;
  routing and buffer-ownership tests pass. XAudio2 has not executed in Xenia.
- Complete current Config compiles. Original/projected configuration method
  audits agree on save/reload, typed/nested values and migrations. Native
  backend registration is present; Context/window execution remains open.
- Complete current Context and eleven lifecycle/platform/bridge TUs compile,
  together with five current shared window/menu base TUs and ConsoleVariable.
  GUI element lifecycle, console registration/usage and debugger state audits
  match upstream. Full Context/CVar execution and native presentation remain
  unvalidated; modern application C++ and full graphics remain major work.
- Current font/GUI/Fast texture resources, GameOverlay and exact pinned stb
  compile (seven TUs). Full host factory tests match upstream for binary font
  bytes, RGBA image decode/alpha, failure and size contracts. A logging argument
  conversion-order defect found during this integration was fixed and tested.
- Complete current Fast3D interpreter now compiles as a Xenon object, with no
  handler omissions. Original/projected state, stack, cache keys, opcode-domain
  and scale/math audits pass; all six real opcode table entries match exactly.
  Xenos backend/shader integration and actual renderer execution remain open.
- JSON string-key maps, std::array, C arrays and registered enum conversions now
  pass original/projected tests and native compilation. Full consumer integration
  and the remaining JSON APIs are still pending.
- All 47 current input/controller TUs and two native XInput/physical TUs compile.
  Original/projected defaults, high-bit bindings and 40,401 stick vectors agree;
  physical fixtures pass topology/axis/rumble cases. Actual input execution,
  menu capture, remapping persistence and four-port routing remain unvalidated.
- Ten full application resource type/factory TUs now compile: Background,
  PlayerAnimation, Text, Array and Cutscene. Original/projected LE/BE and XML
  payload contracts agree; mixed-width cutscene helpers remain verbatim.
  This initial batch has since expanded to the 77 production resource TUs below.
- Exact Prism and current shader builder compile (six TUs), retaining real
  resource acquisition. All 936 host generation cases match; 264 unique Xbox
  vertex/pixel shader compilations pass. GPU execution remains unvalidated.
- The native Xenos backend now compiles against every current rendering virtual
  method (three TUs). Six bindings, separate attachment clears, rectangular
  copies and numeric RGB5551 readback are present. Host pixel/cache boundary
  checks pass; window/GUI wiring and native GPU behavior remain unvalidated.
- Full current Fast3dWindow/FastMouseStateManager and native presentation compile
  (three TUs). The real GUI/interpreter draw sequence remains byte-identical;
  2,024,400 pacing checks pass. Native GUI is wired; execution remains open.
- Application resource coverage expanded to Animation, AudioSequence,
  AudioSoundFont, CollisionHeader, Path and SkeletonLimb, including PathLogger.
  All 23 complete application TUs plus ABI checks compile. Seven full factory
  pairs and 2,068 sequence/method cases match original host behavior. Actual
  sample resolution, archive/CVar integration and AudioSample/Skeleton remain.
- All 25 current scene-command type/factory pairs plus Scene, dispatch support
  and loggers compile, bringing resources to 77 TUs. Original/projected XML,
  mesh, logger, ID/endian audits pass; actual service-backed/binary dispatch is open.
- Complete current frame interpolation compiles; 589,824 angle cases plus
  matrix/inverse/recorder lifecycle checks match in a bounded host audit.
- Complete current Gui, ConsoleWindow, InputEditorWindow, StatsWindow and
  GfxDebuggerWindow compile, with native Gui initialization (six TUs). The
  primary native ImGui renderer/platform compile (two TUs), and both UI shaders
  compile with XDK. The exact font bytes produce matching 903-glyph atlases;
  real ImGui controller-event host checks pass. No native UI has executed.
- Native C++ recipes now explicitly enable RTTI, which current dynamic casts
  require. Input, binary tools and thirteen runtime components were rebuilt;
  the former /GR- cast warnings are absent in the inspected rebuilt logs.
  Nine resource leaf TUs also rebuilt and their host factory differential passes.
  Final uniform build composition remains pending.
- Deterministic XDK project inventory now records every application source,
  pending translations, unique objects and release definition corrections.
  Generated MSBuild compilation passes seven genuine C/C++ production files;
  incomplete application builds are explicitly rejected before linking.
- Exact release-enabled libgfxd compiles all seven C TUs; 15,360 complete host
  disassembly cases match. Full GUI rebuild passes with both GFX_DEBUG_DISASSEMBLER
  and F3DEX_GBI_2, correcting omissions in the earlier isolated GUI recipe.
- Next: integrate real Context/platform initialization and resource consumers,
  then the complete modern C++ application, renderer, input, audio and storage.

Authority: upstream owns game/application/features/resources/save semantics;
Shipyard owns Xbox platform mechanisms. Work and outputs remain in this tree.
All six supplied reference roots remain read-only.
