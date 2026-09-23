# 3Shipsty status

## 2026-09-22 — Hardware storage-selector crash; corrected XEX awaits console retest

The prior clean candidate (`50f702fe...`) reached storage selection on a real
Xbox 360, then the title crashed and the console powered down without a
warning. This is not a proven Dashboard-only exit. Its storage code called
`XShowDeviceSelectorUI` before creating the native D3D device and blocked in
`XGetOverlappedResult(..., TRUE)` without presenting the overlay. Smash360's
physical-console evidence established that this platform contract needs an
early display, continued presentation, and sometimes one guarded same-profile
retry after XAM cancellation during sign-in notifications. The exact failure
code for this SoH hardware attempt was not captured, so the root cause remains
an evidence-backed hypothesis until the retest.

Code commit `b9fcc89e7e2a0aa07394e2b615cbeb43d58a49f5` applies that
platform contract without changing 9.x SaveManager or bypassing XContent.
The new staged XEX at `scratch/runtime/3Shipsty/3Shipsty.xex` has SHA256
`75a0562a7bdee9cf938ba9cacf615c53a09a7d7e1f20b408b59fa53368d55a20`.
Fresh metadata, all 1,836 PPC objects, genuine link, and ImageXex succeeded.
XDK Xenos/storage compiles, selector contract, Xenos interface, and save-schema
tests passed. In owned Xenia this exact XEX logged a successful asynchronous
selector attempt (`initial=997 result=0`) after native-display creation, then
identified commit `b9fcc89` and reached real save metadata and scene init.
Xenia cannot prove the retail sign-in-interruption retry or resolve the
unlogged hardware power-off. Retest only this new XEX on hardware, keeping
archives and speech data unchanged; record the selector attempt/error if it
still fails.

## 2026-09-22 — Clean hardware candidate; physical Xbox 360 is next

The genuine 9.2.3 XEX built from code commit
`2e89e891489b9335044bc874830d20f95418fcd2` is staged at
`scratch/runtime/3Shipsty/3Shipsty.xex` (SHA256
`50f702fe34958ecc59bb07b2725a3a3ee4cd71d10e471e915ecb7c5bfa8958e1`).
It was produced by fresh build-metadata generation, a complete 1,836-object
XDK build, genuine link, and ImageXex. The staged folder also contains the
verified `soh.o2r`, `oot.o2r`, and complete `espeak-ng-data` directory; copy
these together, without emulator account/save state, for hardware testing.

On the exact cleaned XEX, the user confirmed file select, gameplay, audio,
and controls in owned Xenia. The final run starts at `[01:51:56.339]` in
`scratch/runtime/hardware-candidate-app-20260922.log` (SHA256
`d2d8aee895a9eb4dae0e29b29fb14034fde0df9cb12ff68912a20d9c0d05a872`):
it identifies Ackbar Delta 9.2.3 and commit `2e89e89`, creates native
framebuffers by `[01:51:59.790]`, initializes three save slots, and loads
file 0 into a real scene at `[01:52:10.222]`. Save creation/reload and modern
randomizer gameplay were confirmed in earlier Xenia runs, but a fresh save
write was not separately repeated on this exact cleaned XEX. Physical console
boot, save, speech, audio, and performance remain unproven.

Startup profiling located roughly 7.8 seconds in first-use Xenia translation
of large modern hint initializers, not filesystem reads. The Xbox-only
ordered 16-assignment chunk projection retains all 1,370 assignments and
passes upstream-order/parity tests. It reduced the measured hint interval
from ~7.758s to ~0.299s on a fresh XEX; full boot time is not yet independently
benchmarked on hardware. Heavy audio scans/queue sampling, framebuffer
readback, shader hitch probes, and boot traces were removed or disabled before
this full rebuild; the final-run log has no `BOOT_TIMING`, `FRAME_TRACE`,
`AUDIO queue`, or `HITCH shader` entries. First-use shader compilation remains
a plausible Xenia-only source of small Hyrule Field hitches; no disk cache was
added without hardware evidence.

## 2026-09-22 — Genuine 9.2.3 gameplay with audio, save, and backgrounds

The current owned Xenia run uses a freshly linked genuine XEX, SHA256
`1dffc060f65bb04dff8eb87b8a89d1b35090812e6f50fdbd9a1cf943b0f2b680`,
built with identity HEAD `5dd926bf0922126f843b5ff8e1290054f9bf7d51` plus
runtime projections. The proven endian fix was subsequently checkpointed as
`8f55f53cfa771d99fb26867b04f92fe40406dfb8`; the exercised game-C
startup/JPEG projections were checkpointed as
`867a586d05e7817a517d33b804b8701639373bd4`. Other platform projections
remain uncommitted. Re-query process state; the
launch returned PID 31588. The user confirms audible audio and correct
off-white/white Deku Tree exit transitions. The previous fresh XEX fixed the
Kokiri shop background, which the user visually confirmed; its explicit JPEG
byte-marker check is retained in this XEX. Default modern randomizer settings
complete, gameplay/controller movement and save/reload were previously
confirmed, and the newly rebuilt XEX loaded that real save into gameplay.

The second runtime failure was a game-C staging mismatch, not a 9.x gameplay
change: the binary-tools build already selected Xenon big-endian layout, but
`prepare_game.py` staged the raw upstream `endianness.h` for C translation
units. Thus packed `Color_RGBA8_u32` fields and `AudioCmd` byte fields were
compiled in little-endian order. The working 4.0.5 Xbox port selects its
big-endian ABI centrally. The modern game-C projection now does the same
for `_XBOX && _M_PPC`; targeted XDK compiles confirmed `r,g,b,a` and
`op,arg0,arg1,arg2` layouts. The earlier separate 4.0.5 color symptom was
in an intro cutscene, not this doorway; the shared ABI cause applies here.
The shop failure was the same wrong byte-order selection affecting the JPEG
marker; a direct serialized-byte check preserves the real decoder.

Full validation after the endian correction: 18 projection tests, 696/696
game C, 1,836 verified PPC objects, genuine link/ImageXex exit zero. In the
owned runtime, the audio reset gate returned to 0, BGM and SFX players were
both enabled, 8 notes were active at synth task 600, and native PCM had
309,748 nonzero samples by block 600 (peak 7,892). User hearing and fade
color independently confirm the on-screen/output behavior. Evidence snapshot:
`scratch/runtime/post-endian-audio-gameplay-app-20260922.log`, SHA256
`d37b21ded873d86e0191ecf72dec521dd25b54c07f3835224ef311b4180f92e6`.
Normal physical Xbox 360 validation is still unproven. Startup still spends
about 9.25 seconds inside modern application initialization; no speculative
optimization has been applied.

## 2026-09-22 — Genuine 9.2.3 randomizer gameplay; audio still silent

The current owned Xenia run reached real file select, completed a modern
randomizer seed, wrote its spoiler JSON, entered gameplay, and created a save.
The user confirmed controller movement, saving, and a successful save reload.
The staged genuine XEX SHA256 is
`b7f83f704cd77b24711619c12e469d1213b9c8b005f9bb69c47b30e7ebc46c64`;
HEAD is `0cad9e225f77b3ff40530f56a5676913118f9d1d` with uncommitted narrow
runtime fixes. The live owned Xenia PID was 40196; re-query before acting.
Snapshot `scratch/runtime/post-rando-gameplay-app-20260922.log` SHA256
`d52d6b9ff6fc2ca880209e33aeac8bb7105e55d30f2a3957d635874868612fb3`
records all 24 trick-name chunks, completed item/entrance overrides and hints,
`Writing Spoiler Log Done`, then actual FileChoose-to-Gameplay transitions.
Owned storage contains a parseable 124,047-byte spoiler JSON and 210,159-byte
`Save/file1.sav` JSON.

The generation freeze was not a filesystem stall. The first ice-trap lookup
never reached the first statement of modern `InitTrickNames` while Xenia CPU
rose; the generated function contained 192 ordered table assignments. Splitting
it into 24 no-inline eight-row helpers preserves all names/assignment order
and makes every chunk complete in milliseconds in Xenia. Native compile and
the randomizer application contract pass, including ordered-key coverage.

Audio is still genuinely broken. The user hears nothing, XAudio2 is active,
but the native mixer receives zero active notes and no enabled BGM/SFX sequence
players through task 1,200. New bounded sequence-queue/update diagnostics are
compiled in two C units but are **not in the staged XEX**. The user also reports
no chest/NPC interaction in this randomizer run; whether this is A-button
mapping or seed settings is not yet classified. Startup still spends roughly
9.25 seconds in modern application initialization after factory registration.
Threading is being checked against the working 4.0.5 worker placement; the
modern app already has dedicated audio, randomizer, resource, and save workers,
but the generic native worker currently does not set Xbox processor affinity.

## 2026-09-22 — Post-logo fault fixed; real file select reached

The current genuine 9.2.3 application now runs through the Nintendo logo,
Opening, full Gameplay/title-scene initialization, and the real FileChoose
state in the owned Xenia runtime. The user sees the UI and is testing a
randomizer start. The same run logs `MESSAGE font end`, `PLAY_INIT scene end
scene=81`, `GAMESTATE init end name=Gameplay`, and `GAMESTATE init end
name=FileChoose`; file-select fade reaches full control opacity. Evidence:
`scratch/runtime/post-font-filechoose-app-20260922.log`.

The post-logo exception was a 9.x-specific serialized-data boundary: the
ordered NTSC font reads Japanese Shift-JIS `u16` codes from little-endian O2R
bytes into a big-endian Xenon `Font` buffer. The first invalid native reading
was `0xA082` where the archive encodes `0x82A0`. The Xbox projection now
converts only the ordered-font and ordinary Japanese dialog copies; English,
PAL, credits, and serialized archive bytes are unchanged. Both changed C
units, 696/696 game C, 1,836 PPC objects, genuine link and ImageXex pass.
Staged/running XEX SHA256:
`2299f84cb404c2ec2729e7b66029fc88bc2d50055390ac6e5bd89c09891f6d14`.
HEAD remains `0cad9e225f77b3ff40530f56a5676913118f9d1d`; working tree
contains this and earlier narrow runtime changes, not yet committed.

Controller traversal is evidenced by the user's file-select/randomizer UI
interaction, but save creation/load and normal gameplay are not yet proven.
Audio remains a real failure: XAudio2 queues buffers, but the mixer reported
zero nonzero samples through 600 blocks, and the user hears no sound. The
randomizer generation did not complete after nine minutes. Its final log was
`Calculating Playthrough Done`; CPU kept rising while sampled process I/O
advanced only one 24-byte read and no writes. The owned process was stopped
after preserving the trace. Bounded override/hint-phase and audio probes are
being built; no filesystem change was made without evidence. The renderer
readback's `nonblack=0` remains an
invalid visual oracle because visible graphics were independently observed.

## 2026-09-22 — Nintendo logo renders; post-logo black trace ready

The genuine modern runtime now presents the spinning Nintendo N, then becomes
black. After the logo it continues through real save-slot checks and Xbox input
polling without a guest exception. This narrows the remaining failure to the
Title/Opening/Gameplay-title/FileChoose transition or file-select rendering.

A complete fresh rebuild passes 696/696 generated game C units, 1,836 PPC
objects, all 1,094 application TUs, genuine link and ImageXex. The new unrun XEX
is `scratch/link-integration/3Shipsty.xex`, SHA256
`146e9e6f44b3a09a286c1ce7f8e8c870419419add34682ebf51d26e36894d5ea`.
It contains bounded gamestate/file-select fade tracing. The staged XEX is older;
see `RUNTIME_HANDOFF.md`. Xenia is stopped at the user's request.

2026-09-21. **Runtime bring-up pending full rebuild; approval service unavailable.**
Forward port of Shipwright **9.2.3 / Ackbar Delta** to Xbox 360.
Current resume point: [RUNTIME_HANDOFF.md](RUNTIME_HANDOFF.md).
Last committed checkpoint: `3581983af5a5d3dbc4a100aa6b37a241526c07bc`.
All 16 link fixes are committed; two startup fixes remain uncommitted.

First genuine bring-up estimate: roughly 70% complete, with considerable
uncertainty until actual gameplay. Selected application source coverage is now
696/696 C and 398/398 C++ TUs.
The refreshed complete combined build passed with 1,836 verified PPC objects.
All 16 unresolved symbols are closed: genuine application link and ImageXex
both returned zero. The callback-table fix gets real Xenia execution through
static initialization into InitOTR and archive discovery. A missing logical CWD
initialization then causes an exception; its source fix passes native startup
compilation but awaits the full build/link/runtime test. This
estimate includes required integration and first execution; it does not measure
the complete polished-port effort or imply that gameplay works. Update
this first-bring-up estimate in meaningful milestone reports as requested.
Remaining work is being grouped by complete application subsystems; individual
compile units remain internal evidence rather than user-facing milestones.

Latest integration work (earlier milestones below retain their historical scope):

- Full gameplay enhancements, network/packets, content, regions, application
  extras, seed generation, randomizer hooks/trackers and speech pass individual
  XDK compilation and focused original/projected checks. The complete source
  manifest now selects every one of the 1,094 pinned application TUs, plus real
  LUS/dependencies/platform providers (1,836 production objects in total).
  Twelve inventory checks pass; no unresolved platform source selections remain.
- Real OTRGlobals now selects Xbox speech ahead of desktop SAPI, destroys the
  concrete speech worker/voices safely, and joins unfinished seed generation
  before teardown. Full startup compiles and five boundary checks pass. Speech's
  six tests and all 35 randomizer application source/object checks pass.
- Full production compilation and linking pass. Metadata, four CRT providers and
  interpolation linkage are integrated and verified; CRT review/root tests passed.
- The conditionalAlwaysHints compiler defect is corrected with generated ordered
  construction. All 12 callback predicates/order are checked; full build/link pass
  and real Xenia execution gets past the original fault.
- InitOTR now initializes the logical working directory to game:/ before storage
  or Context consumers. Five startup checks and native OTRGlobals compilation
  pass. Full rebuild was not executed because automatic approval review hit the
  account usage limit. Do not bypass that gate. The current XEX lacks this fix.
- Save-container creation also failed in the profile-less owned Xenia instance.
  No local test profile has been created yet. Verify that prerequisite and the
  exact native mount return code. UI/gameplay/audio/save correctness remain unproven.
- Retail NTSC 1.0 archives and speech data are staged in scratch/runtime/3Shipsty.
  Build evidence, exact dirty files and resume steps are in HANDOFF.md.

Historical milestones below describe their state at the time and are superseded
by the current summary above.

- Full scene/message/resource bridges, GBI wrappers, notifications, utilities
  and crash context pass the main XDK build: 1,570 production objects verified
  in application-core-verification.json. Actual utility/message conversions
  agree with upstream. Remaining application C++ count is 227.
- A third independent batch now covers the complete randomizer region graph;
  root proceeds with full network application/packet implementations.

- Complete debugger/resolution/icon windows, audio/cosmetic editors and location/
  static-data providers pass the main build. All 1,562 production source hashes
  and PPC objects are verified in application-windows-verification.json.
  Actual original/projected geometry, icons, timers, widget values and content
  tables agree. All corresponding agent tasks finished before reassignment.
  Remaining application C++ count is 235; linking and native execution remain.
- Current independent batches: gameplay enhancements and randomizer content
  tables. Root owns complete scene/message/resource bridges and utilities.

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

## 2026-09-21 - signed-profile runtime reaches first ImGui frame, then stalls

Checkpoint `0cad9e225f77b3ff40530f56a5676913118f9d1d` contains the proven
working-directory and CRT-safe writable-root fixes. With Xenia local profile
`E0300000052D89D9` signed in, the genuine 9.2.3 runtime mounts the save
container, opens both required O2R archives, accepts missing optional MQ,
persists/reopens current configuration, constructs Context, starts XAudio2,
connects controller slot 0, and creates framebuffers 3-7.

Fresh diagnostic build/link/ImageXex all return zero: 1,836 verified PPC objects,
1,094 real application TUs, XEX SHA256
`9ba8b77a6ea3d083f6d261553cd8d8b7a318f431de6871ecbc6a71f28f42fe86`.
The visible result remains black.

One-shot checkpoints prove `IsFrameReady`, mouse capture, renderer-backend frame
setup, and Xbox ImGui platform/gamepad setup all return. `ImGui::NewFrame()` does
not return. Therefore no renderer StartFrame, Fast3D draw, EndFrame, or Present
occurs, leaving the initialized presentation surface black. The internal ImGui
substage is still unknown; do not attribute it to navigation or XDK codegen yet.
Xenia is stopped at user request. Full hashes, dirty diagnostic files, exact
evidence and reproduction are in `RUNTIME_HANDOFF.md`.
