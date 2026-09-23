# 3Shipsty porting ledger

## Design and acceptance

Forward-port the real pinned Shipwright 9.2.3 application through its LUS/Fast3D
interfaces to XDK/Xenon. Preserve modern randomizer, enhancements, menus, hooks,
save formats, resource behavior, and game ownership. Shipyard supplies Xbox
rendering, input, audio, storage, timing and narrow compiler/OS boundaries.
Generated compatibility files must trace to exact source hashes and deterministic
transforms; never maintain a second independent game implementation.

Only D:/Projects/3Shipsty9.x is writable for this mission. No reference builds,
reference caches, reference Git state or reference source may be changed.
No Xenos64/bromurokkk implementation, recomp architecture, custom asset format,
parallel renderer, fake menu, alternate loop or bypass of the real application.

Acceptance requires real initialization, archive mount, ImGui/UI, physical input,
storage/save, title/file-select, normal gameplay with world/HUD/audio, a modern
post-4.0.5 feature and legitimate randomizer UI/runtime in Xenia. Xenia results
are never hardware evidence. Stop only at the user's A/B/C conditions.

## Decisions and evidence

- 2026-09-22, codebase endian/redundant-work review after user reports an HD
  mod delta (~15 FPS title, ~11 FPS gameplay in Xenia; translation-only ~60).
  The removed converted 70,525,755-byte `.o2r` had 618 alt texture records
  totaling 853,762,364 uncompressed bytes before removal; 212 exceeded
  1 MiB and 93 exceeded 4 MiB. This is potential payload, not live residency.
  Current Xenos uploader is byte-identical to SoH360 and Smash360; its
  identical-upload snapshot is capped at 16 KiB, while a large miss creates
  and fills a GPU texture. Fast3D LRU is 1,024 entries by count; releases
  above 8 MiB pending budget can block. No per-frame miss count or GPU/CPU
  timing was captured, so the exact 45+ FPS loss is not yet assigned to a
  layer. Xenia's owned config has debug logging and 384/768 MiB soft/hard
  host texture limits. Startup archive indexing, audio loading and save work
  are not per-frame HD processing. Player-limb cached resource lookups do
  allocate futures each draw, but that is upstream/donor-shared baseline work.
  The user-supplied root ZIP is a different 654,820,398-byte outer package of
  37 nested OTR/O2R archives, not the deployed converted `.o2r`.
  Active XDK native-byte-order projection is correct across audited resource,
  Fast3D, graphics, audio, save and network boundaries; no new confirmed
  endian defect. Inactive raw LightEntry union parsing and O2R short-read
  acceptance are bounded risks, not explanations for this FPS delta.
  Separate screenshot: XDK copies Option temporaries into Settings but
  Option's cached `c_str()` map is shallow-copied; existing contract confirms
  destination pointers differ from destination strings. This strongly
  explains garbled dropdown labels beside readable refreshed tooltip text.
  Diagnosis only; no new XEX or code fix in this pass.

- 2026-09-22, `game:/mods` archive discovery (`1ffe0eb74`) exposed a real
  Xenon MPQ failure: first Portuguese OTR opened, but its encrypted/compressed
  `(listfile)` read returned 1392; upstream `OtrArchive::Open` then dereferenced
  null. Xenia debugger mapped the guest fault to that dereference. MPQ file
  flags are `0x80030200`; host StormLib reads both supplied listfiles fully.
  Guest sector 0 zlib returns 1, the next unaligned sector returns -3 and
  `"invalid code lengths set"`. Pinned StormLib's unaligned cipher path
  constructed its rolling-key return word as little-endian on big-endian PPC.
  Commit `8018f9714` projects native-word `memcpy` for both unaligned cipher
  helpers. Both 231-object Xenon/host StormLib builds and endian/real-mod
  regression checks pass. Full 1,836 PPC build/link/XEX passes; first fixed
  test XEX SHA256 is
  `d3c068aed340a443d480caa9d0c83cd37063e8536f4e3d6621c90dd3243ca7b9`.
  Owned Xenia logs 40 mod archives added, no listfile errors, GUI completion
  and gameplay scene initialization. The user visually confirmed translated
  gameplay. The user later clarified that the HD pack gave ~15 FPS at the
  title and ~11 FPS in gameplay in Xenia; translation-only runs around 60 FPS.
  The pack was removed between these observations, so they are not a
  same-mod relaunch comparison. This does not establish hardware behavior.
  The final source-identity XEX built from `55ce76c50` passed 1,836-object
  verification, genuine link and ImageXex; staged SHA256 is
  `262e2ffbcd4998a90574e7e2a3d42a218961b5553a66bec8c7641797e7314694`.
  Owned Xenia embeds `commit=55ce76c`, reaches `gui-ready`/`init-complete`,
  opens the Portuguese OTRs and enters gameplay. The user confirms translated
  gameplay, audio, controller input and ~60 FPS on this exact image. Physical
  validation is the next boundary; no console result for this image exists.

- 2026-09-22, physical console booted the previous `27f931b5...` XEX into
  real 9.2.3 gameplay with working audio, input, saves and randomizer generation,
  but Back and the preset modal were uncontrollable. The `gControlNav` Xbox
  default was registered before config version 2 calls `CVarClearBlock`, whose
  `Load()` discards unsaved CVars. On a fresh HDD config, the later modern GUI
  sees 0. Commits `27815b3ce`/`fd8386fd5` register the default after version
  updates, retain saved preferences, enable navigation and gamepad blocking
  for queued modals, and restore the donor right-stick cursor path. Input and
  menu tests plus targeted PPC compile pass. Full 1,836-object build/link/XEX
  pass at `fd8386fd5`, staged SHA256
  `7f3311a96ce40888a62b136178baf52604dffae90e57a1d6d29a3d266e203890`.
  Owned Xenia log reaches `gui-ready`/`init-complete`; no physical test of this
  build yet. One `0xE06D7363` first-chance C++ exception continues to occur
  between those stages and is not shown to cause the input problem.

- 2026-09-22, real-hardware XEX `ddbdf8dd...` again powered off after HDD
  selection. Supplied `3Shipsty.bootlog` is 655 bytes, SHA256
  `edb6a51cb33d78a0aab2f5a7486697ff11e7b1e844810b95c70eea495b0b0609`.
  It proves `game:` writable and the main thread returned from storage,
  archives, Context, audio, resource/randomizer setup, and SaveManager
  construction, ending at `save-worker-ready`. The next code block is six
  config migrations/save and GUI registration; the last marker alone does
  not prove which failed or rule out a concurrent worker. Commit
  `9b24272450a0f8dc452063da080ba80626ed6571` adds individual migration,
  save and GUI markers to the already proven writable `game:` trace, without
  another normal-path XContentFlush. Original/projected Config behavior and
  native targeted compiles pass; fresh 1,836-object build/link/XEX pass.
  Staged SHA256 `27f931b533f41fb08eae1eaf888bcfd57117e1af3b3919a13f06b9d24926ecdc`.
  Hardware result pending; no fix/root-cause claim.

- 2026-09-22, missing retail fault receipt: the user found no
  `game:\3Shipsty.startup-fault` from XEX `b4e9ebd4...`.
  `RecordNativeFault` was not called by direct Xenos/XAudio2 aborts, and its
  `CreateFileA` failure was silent. Absence was not evidence of an unwritable
  `game:` volume or a particular fault site. Commit
  `9117bce812de2e8aa156ac478355d35ca69a9355` adds explicit fatal hooks,
  SIGABRT capture, ordered flushed game-directory boot stages, and two bounded
  pre-logger save-container checkpoints carrying `game_write_error`. Once
  XContent is mounted, a fatal receipt also writes and flushes within the
  selected `shipyard:` container. Ten startup tests, targeted PPC compiles,
  fresh full 1,836-object build/link/XEX pass. Staged hash
  `ddbdf8dd59bc6d6c895bca9909e73d14b0c0d169f8706b500b2f7b40f0697859`.
  Retail result is pending; do not label the boot defect fixed.

- 2026-09-22, retail rerun of main-thread parity candidate: XEX SHA256
  `562d2ac49b1eefba4a8f89ca6b5322693fd95f6b87909cd2b756925938f5d123`
  showed the same selector and 5–6-second post-HDD pause, then silent
  power-off. Supplied CON SHA256
  `7de209c096e75d776a9a2e58f6daf4a0912a51cf8c7d7b19c99dadcafefc8d98`
  is identical to the prior blank package, so no crash stage can be inferred
  from STFS. The processor pin is correct parity, but not the demonstrated
  cause. Commit `358435e6398b03cc6da1e3ddc4f50c70c770931f` installs a
  lightweight, on-failure-only native SEH/C++ terminate/handled-error receipt
  to `game:\3Shipsty.startup-fault`, outside the unflushed save container.
  It neither fakes a mount nor changes real application/worker paths. Fresh
  1,836 PPC objects, genuine link/ImageXex, targeted native compiles and
  startup tests pass. Staged diagnostic XEX SHA256
  `b4e9ebd4fd2ef843645ab9243fd54f145e10011239efd5d76321a1b1da898c03`;
  physical behavior remains untested. Absence of the sidecar on a shutdown
  would not exclude a hardware-level failure or unwritable game directory.

- 2026-09-22, three isolated donor-parity audits: both working ports pin the
  title/render thread to hardware thread 0 before startup; 9.2.3 had omitted
  that. `dd7ad363329e99de777efc3297ad6c065e7e8f76` restores the early
  pin and adds a handled native `InitOTR` failure boundary with visible Xbox
  error code and active XAM presentation. This is a real foundation gap, but
  its relation to the retail power-off is not yet proven. The unused game-dir
  boot trace was removed. Generic `joining_thread` code matches Smash360;
  no global worker affinity or parallel save/renderer replacement is justified.
  Selector/XContent mechanics, D3D reuse, and XAudio2 setup also match the
  donors. Modern Context storage roots and SaveManager/randomizer work are
  version-specific application behavior, not missing 4.0.5 code. Nine startup
  tests, 19 game projection tests, selector checks, targeted PPC builds,
  complete 1,836-object build, link/ImageXex pass. Staged XEX SHA256
  `562d2ac49b1eefba4a8f89ca6b5322693fd95f6b87909cd2b756925938f5d123`.
  Owned Xenia process produced no visible window/title log and was stopped;
  there is no new Xenia or retail execution proof for this image.

- 2026-09-22, clean retail retest: XEX SHA256
  `9d95425e535ba41a018e78c3e52bf982911790725336f7f1edd643f090c3e303`
  still powers off after HDD selection. Backing up/removing the old CON and
  retrying did not change the outcome. Fresh CON SHA256
  `7de209c096e75d776a9a2e58f6daf4a0912a51cf8c7d7b19c99dadcafefc8d98`
  is a valid 40,960-byte package with no committed entries. The missing
  entries do not time-bound startup because the clean image has no diagnostic
  `XContentFlush`; the package can remain blank if power is lost before a real
  save commit. Existing-package corruption is excluded as the sole blocker.
  The exact `XContentCreate` return and subsequent fault site remain unknown.

- 2026-09-22, third retail STFS and no-marker retest candidate: read-only HDD
  CON SHA256 `d2d0ef814f9a090371d1a34e865e98137bbae364422da75539a17f1b9d35808e`
  contains committed `logs/Ship of Harkinian.log`, stages 1–5, and two real
  startup log lines (XAudio2 PCM and 9.2.3). Stage-6 text exists in a raw
  block without a directory entry; do not infer its flush completed. Temporary
  startup breadcrumbs caused repeated `XContentFlush` calls unlike Smash360's
  real-save-only flush path. `a7e92f2f7` removes the diagnostics, not storage
  semantics. Startup tests and fresh full XDK build/link/ImageXex pass; clean
  XEX SHA256 `9d95425e535ba41a018e78c3e52bf982911790725336f7f1edd643f090c3e303`.
  Hardware behavior without markers is pending. Main-thread/worker affinity
  and modern speech startup are code-review candidates only, not root causes.

- 2026-09-22, retail logger boundary: second HDD CON SHA256
  `0612bdc119285fee6f07e5d5c6edaa711bae21064e8f1f5ea5efc5c7d35cca1c`
  has boot stages 1–5 and `mods`, but no stage 6 or `logs`. The current
  `Context::InitLogging` returned false on a file-sink exception, and SoH
  immediately dereferenced the absent logger. `7f174a11eec3248562af811daf5fcbf6adeba336`
  normalizes only the Xbox file-sink path, creates its directory through the
  native filesystem, and checks the result before use; real spdlog and
  modern application ownership remain intact. Full 1,836-object XDK build,
  link/ImageXex, targeted compiles and order tests pass. New staged XEX SHA256
  `286c487203439042c0054f36fb1bd217b3ebbdc3953b42fecd3ef7506eb6241b`.
  Xenia logs real 9.2.3 startup, stages 1–6, save metadata and scene path.
  Hardware outcome is pending; stage 7 now explicitly records a failed logger.

- 2026-09-22, copied retail STFS package: 57,344 bytes, SHA256
  `23ce7ba95803282cd905946f626bc7d6a8a7e8ccac603732e666e3d36d909106`,
  valid CON/title `534F4809`, file table containing `mods` only. Selector and
  XContent mount therefore succeeded; the real 9.2.3 RunExtract path created
  the directory. Generic RGH fatal has no fault code. A six-file, flushed,
  pre-logger diagnostic in `9dfa266bd849fd6bfe43af3a8b0497c68005ac53`
  preserves actual application order and storage semantics. Fresh full build,
  link and ImageXex pass; diagnostic XEX SHA256
  `4c3078779b058761ac6558d5d6a7b1a68f288633ee9bf7ebb7d617a9a5e70622`.
  Owned Xenia created stages 1–6 and reached save metadata. One retail run
  and copied HDD package are required to identify the precise pre-logging
  boundary. The markers are temporary and must be removed for a clean image.

- 2026-09-22, first physical 9.2.3 test: user reports the previous candidate
  reached storage selection, then crashed and powered down the console without
  warning. No return/error code was captured. The current platform called
  XAM before native D3D creation and blocked the presentation owner. The
  hardware-tested Smash360 contract requires an early native device, present
  during pending selector UI, and one conditional retry only when sign-in
  notifications interrupted the request without B cancellation or offline
  profile change. `b9fcc89e7e2a0aa07394e2b615cbeb43d58a49f5` transfers
  that platform contract while preserving actual XContent and modern saves.
  Fresh full 1,836-object build, link, ImageXex, native compile and contract
  checks pass. New staged XEX SHA256
  `75a0562a7bdee9cf938ba9cacf615c53a09a7d7e1f20b408b59fa53368d55a20`.
  Owned Xenia logged selector `initial=997 result=0`, then 9.2.3 identity,
  save-slot metadata and real scene init. Retail root cause and retry outcome
  await a console retest; do not call this hardware-validated yet.

- 2026-09-22, hardware-candidate boundary: code HEAD
  `2e89e891489b9335044bc874830d20f95418fcd2`; clean full XDK/ImageXex
  result SHA256 `50f702fe34958ecc59bb07b2725a3a3ee4cd71d10e471e915ecb7c5bfa8958e1`.
  Exact final run in owned Xenia confirmed by user through file select,
  gameplay, audio, and controller input. Log
  `scratch/runtime/hardware-candidate-app-20260922.log`, SHA256
  `d2d8aee895a9eb4dae0e29b29fb14034fde0df9cb12ff68912a20d9c0d05a872`,
  at 01:51:56–01:52:10 records 9.2.3 identity, native framebuffer creation,
  save metadata, file load, and real scene initialization. The 7.758s hint
  startup interval was first-use Xenia function translation; an Xbox-only
  ordered chunk projection brings that interval to 0.299s while all 1,370
  upstream assignment keys and ordering pass host parity. Heavy bring-up
  diagnostics were removed/disabled in `fc4e15590` and absent from the final
  run. Staged hardware package is the XEX plus `soh.o2r`, `oot.o2r`, and the
  complete `espeak-ng-data` directory. No emulator profile or saves are part
  of it. Physical hardware behavior remains the next required validation;
  shader disk caching is deferred pending measured hardware hitches.

- 2026-09-22, verified runtime: shop JPEG background now renders after
  checking its serialized FF D8 FF E0 marker as bytes in the real room
  draw path. A separate shared game-C staging defect had left the raw
  upstream `endianness.h` in use despite the binary-tools projection
  already selecting Xenon big-endian layout. The corrected C projection
  restores packed transition-color and `AudioCmd` byte ordering; targeted
  XDK compilation confirms both layouts. This matches the working 4.0.5
  platform ABI without copying 4.0.5 gameplay behavior. Fresh complete
  verification: 18 tests, 696/696 game C, 1,836 PPC objects, genuine link.
  Staged XEX SHA256
  `1dffc060f65bb04dff8eb87b8a89d1b35090812e6f50fdbd9a1cf943b0f2b680`;
  embedded build identity HEAD `5dd926bf0922126f843b5ff8e1290054f9bf7d51`
  plus runtime projections; verified endian code subsequently checkpointed at
  `8f55f53cfa771d99fb26867b04f92fe40406dfb8`, and exercised game-C
  startup/JPEG projections at `867a586d05e7817a517d33b804b8701639373bd4`.
  Other platform projections remain
  uncommitted. Xenia mixer: gate 0, BGM/SFX
  enabled, 8 active notes and 309,748 nonzero PCM samples by block 600.
  User confirms audible audio and correct Deku Tree exit color. Evidence
  snapshot `scratch/runtime/post-endian-audio-gameplay-app-20260922.log`
  SHA256 `d37b21ded873d86e0191ecf72dec521dd25b54c07f3835224ef311b4180f92e6`.
  Real modern randomizer gameplay, controller movement and save/reload were
  already demonstrated. Hardware behavior and startup-time optimization
  remain unproven.

- 2026-09-22, runtime: the resource-init default constructor fix removes the
  bogus SHAD resource version and the real Xenos path visibly renders the
  spinning Nintendo N. Post-logo execution checks global/three slot saves and
  polls Xbox input, then remains visually black without a guest exception.
  CPU surface readback is disproven as a visual oracle because it reported black
  during the visible logo. Adapted the proven 4.0.5 central state tracing into
  the modern generated C boundary and added bounded FileChoose fade tracing.
  Tests pass 11/11; full generated game compile passes 696/696; combined build
  verifies 1,836 objects; link/ImageXex return zero. Fresh unrun XEX SHA256 is
  `146e9e6f44b3a09a286c1ce7f8e8c870419419add34682ebf51d26e36894d5ea`.
  A stale-receipt attempt was rejected as evidence, and a transient two-unit
  full-manifest overwrite was repaired by a complete regeneration before link.

- 2026-09-21: user challenged the excessively granular progress and remaining
  scope. Batch subsequent work by functional subsystem and report those milestones.
  Revise first genuine bring-up estimate to 60–65% with considerable uncertainty;
  the previous 70% estimate overweighted compile progress. No application has
  linked or executed; 260 application C++ units still remain at this checkpoint.

- 2026-09-21, A/B/H/I: complete SaveManager.cpp compiles with all 42 members,
  12 C bridges and every serialization key retained. Canonical raw legacy
  conversion replaces the old raw-pointer parser; the existing decoder remains
  separate. XDK ehexcept.c:971 was isolated to nontrivial default arguments in
  nested LoadRandomizer callbacks (the diagnostic pointed at the next method).
  Four scoped, named temporaries preserve exact string/JSON defaults and call
  lifetime; removing SaveRandomizer or /Od did not fix the compiler failure.
  Real load templates/array/structure methods agree for missing/nested values,
  errors and all 1,818 valid numeric enum values. See save-manager/README.md.
- Complete settings.cpp and option_descriptions.cpp compile against canonical
  full declarations. All 24 definitions, 383 initializer values, 125 U8 options,
  111 Boolean options, 193 trick registrations, 44 callbacks and 323 CVar
  expressions remain. Constructor/list/description/numeric contracts agree;
  actual callbacks/finalization need runtime validation. The main manifest
  excludes superseded SaveSerialization, LegacyConversion and SettingsConstructor
  fragments and tests guard against duplicate ownership. The full 1,536-item
  project passes with all source/object hashes verified in
  scratch/project-xdk/save-settings-verification.json (834 application units
  selected, 260 C++ units pending). First-bring-up estimate remains roughly 70%.

- 2026-09-21, A/B/C/D/E/F: complete OTRGlobals.cpp now compiles with its original
  function inventory, application initializer order and all resource factory
  registrations. Canonical full application/window/Item/AudioCollection headers
  resolve the actual ownership dependencies. Container, scoped-enum, Unicode,
  designated-audio-settings and JSON iterator adaptations preserve upstream
  contracts. Original/projected values match all 65,536 item IDs, 15 ROM hashes,
  ten controller masks, audio defaults and 63,487 BMP printing cases.
  Evidence: scratch/application-xdk/{xdk/build.json,values-verification.json}.
- Startup now establishes XNet and selected XContent storage before Context
  chooses its writable directory. Packaged archives still resolve under game:.
  Normal teardown stops actual producers, joins audio/timers/save work, releases
  GUI ownership, drains the actual resource pool and detached codec captures
  while Context is strong, releases Context, then storage/XNet. Partial-init
  cleanup and early native device-selection behavior remain execution work.
- ResourceManager's explicit drain unpauses/waits its real BS pool and destroys
  it before its mutex. Detached work tracking includes capture destruction and
  creation-failure rollback. Host real-primitive tests cover simultaneous waiters,
  paused jobs, child work and ownership failures; full native TUs compile.
  See platform/shipyard/resource-shutdown/README.md for boundaries and receipts.
- The original static audio instance in OTRAudio.h gives savestates.cpp a mutex
  separate from OTRGlobals.cpp. The projection now uses one named extern state
  defined only in the genuine application TU; all fields/zero initialization
  remain. A two-TU test reproduces the upstream defect and verifies identity and
  mutual exclusion after correction. No game/snapshot serialization is replaced.
- Full SohGui.cpp retains all 12 function bodies and 28 window registrations;
  all 2,485 debugger/tracker rows match. Complete AudioCollection preserves all
  258 source rows / 257 keys and original pool/notification behavior. Complete
  randomizer Item retains all 31 definitions and 16 fields. Native/host receipts
  accompany their platform/shipyard documentation; live UI/randomizer remain open.
- Full randomizer Logic (132 definitions) and save states now compile separately.
  Logic host contracts cover upgrades, inventory, randomizer/event flags, dungeon
  completion and all five maps. Save-state request/FIFO, slots, snapshot defaults
  and pointer relocation agree; live Save/Load remains unexecuted. The combined
  1,536-unit main project passes; every selected source/PPC object hash is recorded
  in scratch/project-xdk/startup-state-verification.json. The old Logic constructor
  fragment is excluded and an inventory test guards against reintroducing it.
- I: ENABLE_REMOTE_CONTROL is enabled across all application C++ recipes, as in
  the official release CI. The C preprocessing closure audit found no uses in
  any game C/header input; the only conditional header is Network.h, absent
  from all 696 actual preprocessor outputs. The C definition policy therefore
  retains its already-applied flags without demanding an irrelevant regeneration.
  This decision must be rechecked if a future C unit includes a remote API header.
- User confirmed the desktop permissions dialog was resolved. Retail baserom.z64
  has already produced the CRC-verified 9.2.3 NTSC 1.0 archive. No ROM or archive
  is tracked. First-bring-up estimate remains roughly 70%, with substantial
  50–75% uncertainty; no XEX, Xenia startup or hardware claim.

- 2026-09-20: complete modern controller editor retains 41 functions, all 50
  CVar expressions and seven search widgets. Actual state/value contracts and
  native UTF-8 bytes pass. Full 1,526-item integration compilation includes its
  production TU and the two explicit legacy conversion/decoder fragments.
  Source/PPC object receipts: scratch/project-xdk/editor-legacy-verification.json.
- Legacy conversion now reads the selected storage namespace, validates all
  occupied slots before writing, preserves producer-order song durations and
  uses unchanged CopyV0Save. 192 complete destination comparisons and 15,592
  truncations pass. Existing backup refusal precedes conversion; synchronous
  conversion/flush precedes backup rename/flush. Stricter damaged/ambiguous
  input rejection is explicit in platform/shipyard/legacy-save/README.md.
- Pinned release CI enables remote control. Complete modern Network.cpp and
  actual XDK transport compile with the matching conditional class layout.
  Nine loopback packets, fragmentation, malformed JSON, large input/output,
  reconnect and joined shutdown pass. Native XNet/WSA startup must precede
  resource/RNG initialization and cleanup must follow every consumer worker.
  External/Xenia/hardware connectivity remains unverified; see network README.
- 2026-09-20: release verified online and locally; see UPSTREAM_BASELINE.md.
- Ruling: use ZAPDTR/OTRExporter selected by 9.2.3; Torch is absent from its
  gitlinks. Importing BattleShip's extraction architecture would violate source
  authority. Cost if wrong: revisit the pinned dependency evidence, not the assets.
- Ruling: SoH 9.2.3's GfxRenderingAPI has uint64/uint32 shader IDs. Smash's
  uint64/uint64 interface cannot be copied wholesale. Adapt the donor to the
  actual pinned interface; cost if wrong is shader identity/rendering corruption.
- Baseline pristine after recursive submodule initialization. No source edits.

## Compatibility classification

| Class | Observed boundary | Narrow adaptation / proof |
| --- | --- | --- |
| A syntax/language | C++20/C23; scoped enums, default members, designated initialization in OTRGlobals audio setup | Deterministic checked source projections; retain initialization and evaluation order; compare against desktop originals |
| B standard library | filesystem, optional, variant, chrono, futures, JSON, formatting | Reuse audited XDK headers where contracts match; test actual consumers, not substitute APIs |
| C OS/platform | SDL, desktop windows/audio/input, process-based extraction | Xbox backends behind current interfaces; host-only extraction |
| D threading/async | resource thread pool, OTR audio thread, save worker | Preserve completion, exceptions, ownership and shutdown using XDK events/threads |
| E filesystem | app directory, mods, config, Save/*.sav/temp | XContent-backed app paths and correct filesystem errors/rename semantics |
| F resources | O2R loader/factories and exporter-defined byte order | Keep current archives, factories, type/version validation; prove header and payload endian separately |
| G rendering drift | class backends; current Prism shaders; framebuffer copy/readback | SoH360 mechanics behind pinned LUS virtual API; selectively reuse Smash extensions |
| H codegen defects | donor-proven mixed-size bitfields, PPC variadics/value initialization | Actual XDK object/layout evidence and differential tests before adapting |
| I build only | CMake excludes Xbox; modern compiler flags; source generation | Deterministic inspectable XDK projects from pinned source inventory and explicit exclusions |

## Endian boundary register

| Data | Contract and proof required |
| --- | --- |
| Raw N64/GC ROM | PC extractor decodes format; no whole-file desktop fixups on Xbox |
| OTR/O2R serialized entries | Resource header declares byte order; BinaryReader converts typed scalars to host representation; byte payloads retain factory-specific meaning |
| Host metadata | ZIP/MPQ metadata and generated IDs obey format, not N64 endianness |
| Native runtime structures | Xenon ILP32/BE; assert sizes and packed Gfx stride, inspect mixed-size bitfields |
| GPU data | Xenos texture upload, vertex fetch and readback conversion each require format-specific proof |
| Config/save/network | Text encodings and explicit serialized schemas remain upstream-owned; no blanket byteswap |

Known issue to reproduce: pinned LUS endianness.h recognizes GCC byte-order
macros but not XDK's PPC/Xbox macros. This can select Little on Xenon. Correct
the centralized host detection, not individual factories with compensating swaps.

## Implementation sequence

1. Complete source-backed migration tables before bulk imports.
2. Inventory and classify all runtime translation units; preserve all feature
   sources and explicitly separate host tools and desktop-only backends.
3. Compile actual boundary inputs with XDK and capture original failures. Start
   with platform endian/ABI and source generator, then C game/compiler headers.
4. Carry generic async/filesystem/JSON/resource compiler adaptations from Smash
   only after comparing exact current sources and donor hash provenance.
5. Integrate Xenos/window/ImGui/input/audio/storage into current Context and
   OTRGlobals lifecycle. Preserve SoH audio policy and current save sections.
6. Build the actual application, extract proper archives on PC, launch owned
   Xenia test storage and validate the full progression above.
7. Profile only after correctness; checkpoint each independent verified change.

## Migration table

Roots: O = D:/Projects/SoH360; S = D:/Projects/Smash360; M = this root.
Detailed graphics contracts: [graphics audit](porting/graphics-audit.md).
Resource contracts: [resource audit](porting/resources-audit.md), when recorded.

| Subsystem | Old Xbox / current / modern donor | Action | Risk / validation |
| --- | --- | --- | --- |
| Graphics API | O/platform/xbox360/gfx_xenos.cpp; M/libultraship/include/fast/backends/gfx_rendering_api.h; S/platform/xbox360/graphics | API adaptation | Current virtual ownership; concrete backend compilation and real frame output |
| Fast3D | O/upstream/libultraship/libultraship/Lib/Fast3D; M/libultraship/src/fast/interpreter.cpp; S/tools/prepare_fast3d_xdk.py | Preserve current interpreter, adapt compiler | Opcode/layout drift; full source compilation and modern display-list corpus |
| Shader generation | O/gfx_xenos.cpp and shader_cache.cpp; M/gfx_direct3d11.cpp builder + Prism; S/graphics/shader_lower.cpp | Rewrite binding to current builder, carry native compiler/cache | Key widths, six slots, custom overrides; original/projected shader comparison |
| Framebuffers | O/gfx_xenos.cpp; M/GfxRenderingAPI; S/graphics/native_extensions.inc | API adaptation | Separate attachment clears, copies/readback/MSAA; pause/blur/depth tests |
| Window/presentation | O/native_window.cpp; M/Fast3dWindow.cpp + Ship::Window; S/graphics/window_xenos.cpp | API adaptation | One owner/Present; actual GUI lifecycle and timing |
| ImGui | O/imgui_xenos.cpp; current Gui + pinned 1.91.9b; S/tools/prepare_imgui_xdk.py | API adaptation | Different LUS patch; fonts/clipping/input capture and real menus |
| Input/control deck | O/xinput_controller.cpp,input_xinput.cpp; M/ship/controller + libultraship/controller; S/input + controllers projections | API adaptation | Current custom button bitfield is uint32_t; all slots, remapping, rumble/disconnect |
| Audio | O/audio_xaudio2.cpp,audio_worker.cpp; M/AudioPlayer and OTRGlobals::OTRAudio_Thread; S/audio/XAudio2AudioPlayer.cpp | API adaptation | M explicitly requests 32000/1024/1680; preserve synthesis/thread policy and surround; inspect PCM and listen |
| Timing | O/platform.cpp,frame_driver.cpp; M/GfxWindowBackend::GetTime + current frame driver; S/runtime/clock.cpp | Carry native QPC, preserve app cadence | Monotonicity, fraction sequence, audio sync |
| Threading/async | O/save_worker.cpp,audio_worker.cpp; M/ResourceManager,BS pool,SaveManager,OTRAudio; S/cpp-compat/async,thread-pool | API adaptation | Futures/errors/shutdown and extended SoH pool use; actual consumer concurrency tests |
| Resource manager | O/assets.cpp,otr_application.cpp; M/ship/resource; S/cpp-compat/resources | Preserve upstream; compiler/platform adaptation | No custom asset manager; actual factory/load/cache failure tests |
| Archives | O/custom sohpak reader; M/O2rArchive,OtrArchive; S/resources + libzip | Old custom format no longer required | Correct O2R and MPQ semantics; mount versioned real archives |
| Asset lookup | O/assets.cpp; M/ResourceManagerHelpers.cpp + current factories; S/generic resource projections | Preserve current lookup | Type/version/path/mod precedence; real assets and missing-path behavior |
| Configuration/CVars | O/cvars.cpp,native_config.cpp; M/ship/config; S/cpp-compat/config | Preserve current, adapt serialization/filesystem | CVar persistence and upgrades; actual default/custom round trips |
| JSON | O/save_json.cpp; current nlohmann consumers; S/cpp-compat/json | Audited compatibility backport | Missing APIs/type narrowing; modern save/config/seed corpus |
| Filesystem | O/platform.cpp; M/std::filesystem app paths; S/cpp-compat/filesystem | Carry generic Xbox mechanisms | Relative/native roots, errors and rename; XContent integration tests |
| Save system | O/save_worker.cpp,save_json.cpp; M/soh/soh/SaveManager.cpp; S/runtime/storage.cpp mechanisms | Preserve current SaveManager; adapt platform | Section registration/migrations, async ordering; real save reload and error recovery |
| Storage/device | O/platform.cpp,mempak_xcontent.cpp; current app paths/save filesystem; S/runtime/storage.cpp | Carry native mechanisms with 3Shipsty identity | Sign-in cancellation, wrong profile/removal; Xenia profile/storage tests |
| Logging | O/diagnostic.h,platform.cpp; M/Context::InitLogging + spdlog; S/cpp-compat/logging | API adaptation | Formatting affects labels as well as diagnostics; differential formatter corpus |
| Crash/debug | O/diagnostic.h,perf_trace.cpp; M/ship/debug/CrashHandler.cpp + game debuggers; S/runtime/diagnostics | Native crash transport, preserve modern debugger | PPC varargs/stack data; checked log output and game debugger opening |
| Memory/allocation | O/arena_xbox.cpp,scene_memory.cpp; current shared resource/cache ownership; S/async/resources | Carry narrow CRT/alignment only | Do not import old scene allocator policy; alignment/lifetime/shutdown and memory growth |
| Interpolation | O/frame_driver.cpp,interpolation_map.h; M/frame_interpolation.cpp,OTRGlobals.cpp; S/Fast3D projection lessons | Keep upstream; compiler adaptation | Cut/actor lifetimes and frame fraction parity; real gameplay rate changes |
| Randomizer | Old 4.0.5 runtime is not a donor; M/Enhancements/randomizer + SeedContext; Smash game logic prohibited | Preserve current runtime | Modern seed JSON/pool use/hooks; legitimate seed/menu/runtime state |
| Enhancement UI | O/GameMenuBar old implementation; M/SohGui and Enhancements; S/generic Gui projections | Preserve modern UI; native input/render backend | No replacement menu; exercise a post-4.0.5 feature |
| Startup/application | O/main.cpp,otr_application.cpp,frame_driver.cpp; M/src/code/main.c -> InitOTR -> OTRGlobals -> Graph_ThreadEntry; S/Context platform lessons | Keep modern application ownership | Host extraction boundary only; full real startup trace and gameplay |

The O/platform/xbox360 prefix applies to abbreviated old filenames. Current
library paths are under libultraship/src or include; current SoH paths under
soh/soh. Detailed reports disambiguate exact interfaces. Every table row is a
planned migration, not proof of implementation or runtime support.

Inventory generator: `python -B tools/shipyard/source_inventory.py --audit`.
Initial result: 1,094 application source files, 133 host-tool files, 141 LUS
files awaiting target review, three speech transports awaiting platform review,
117 files excluded by upstream's own CMake rules. Three ownership/determinism
tests were observed failing before implementation, then passing.

## Compilation checkpoints

- Binary provider: `tools/shipyard/prepare_binary.py`, support under
  `platform/shipyard/binary`. Actual current nine inputs; seven matched modern
  donor, modern MemoryStream semantics retained. Four native TUs and two
  contracts compile. Six generator tests and original/projected host behavior
  pass. Native-endian bug reproduced with actual XDK, then corrected centrally.
- Graphics provider: `tools/shipyard/prepare_graphics.py`, support under
  `platform/shipyard/graphics`. Exact modern interfaces and decoder, donor
  generic HLSL lowering. Three native objects; four projection tests; 2,097,152
  host decoder/layout cases pass. Extracted decoder is audit-only: eventual
  production must link its full interpreter definition exactly once.
- Ruling: reject broad preprocessed-C-as-C++ compilation after actor/graph
  probes demonstrated incompatible pointer conversion rules. Preserve true C
  semantics through a narrower projection. Cost: additional typed boolean and
  C99 lowering work, instead of invasive changes to modern feature code.
- Official Windows 9.2.3 archive SHA256:
  `cc7bd5ada1332be50013976fc3db3289cacde1df57e7e6cf73d4a1df81313e30`.
  Package is PC extraction tooling/data only, never Xbox application evidence.
  API metadata's target_commitish says develop; the immutable tag resolves to
  the pinned cb71e22 commit. No develop source is used.
- Archive provider: verified owned libzip/zlib/tinyxml2 snapshots produce 131
  genuine XDK PowerPC BE objects and three libraries. Actual projected host
  libzip reads all 36,925 modern archive members with CRC/length parity and
  preserves create/overwrite/reopen and UTF-8 member names. Optional codecs,
  encryption and MPQ remain explicit integration work, not feature exclusions.
- Host extraction completed with the exact official 9.2.3 executable and owned
  copied supplied ROM; porting/ASSET_BASELINE.md records resulting hashes.
  Critical endian distinction: version records are BE, regular PC-exported
  binary resource scalar records are LE; preserve per-record markers.
- True-C projection now compiles main/graph/math/actor; bulk inventory underway.
  Async foundation preserves exception propagation, future polling, worker
  lifecycle and save snapshot ownership. Filesystem foundation adds modern
  create_directory/copy_file and safe replacement/error semantics. Full
  consumers, runtime and storage durability are not yet validated.
- Current ImGui dependency: exact tag and release LUS configuration, five native
  core TUs, host atlas/draw-data/command differential. No substitute SoH GUI.
- Current resource leaf boundary: 21 exact inputs, nine native TUs, real factory
  and variant differential. Remaining seven archive/manager/loader TUs retain
  explicit unresolved integration probes with MPQ enabled.
- Logging core carries current spdlog algorithms and native queues. Measured
  fmt4/fmt12 default-double precision difference remains a required integration
  fix; typed modern integer/string formatting corpus passes.
- C diagnostic pass under the correct fixed-point matrix ABI reached 656/696.
  Narrow corrections then passed all 40 residual TUs: typed current color/item
  factories, proven in-order designated initializers, XDK math macro capture,
  actual restrict spelling, C textual include closure, exact Opus headers, and
  canonical bool OR/store and framebuffer completion-pointer boundaries.
  The entire set is being rebuilt; do not combine differing configurations.


### 2026-09-20: Complete current C compiler pass and actual codecs

- One corrected full run now compiles all 696 selected application C TUs with
  XDK `/TC`; manifest SHA-256 is in the game provider README. No GBI_FLOATS,
  excluded failures, C-as-C++ frontend or alternate game path.
- A/H: typed rvalue aggregate factories, verified ordered designators, exact
  restrict/inline spellings and an isolated SDK math-macro boundary resolve
  the remaining failures. Scalar boolean `|=` preserves canonical conversion
  and unconditional RHS evaluation. Nine generator tests and the executable
  native/projected C corpus pass; all three compound-OR functions are included
  in the actual differential call list.
- D/G/endian: the pause capture flag was traced through FB_CopyToFramebuffer,
  gDPCopyFB and the actual interpreter bool-pointer writer. Only that specific
  boundary is permitted; target ABI/GPU completion still require runtime proof.
- B/C/I: exact official Opus 1.6.1, opusfile 0.12 and Ogg 1.3.6 supply the genuine
  current mixer APIs. All 143 PPC objects compile. Host encode/Ogg mux, full
  memory/file decode, accurate PCM seeking, EOF and malformed-input checks pass.
  Default dither intentionally differs after seek; exact seek alignment is
  tested with the public dither switch disabled, while full memory/file
  comparison retains default dithering. No runtime audio claim.
- Ownership: C language transforms are generic Shipyard mechanisms with
  3Shipsty-specific audited source patterns. Codecs are generic platform work;
  no Smash game behavior or Xenos64 source was imported.


### 2026-09-20: Complete current resource TUs and exact MPQ dependency

- Eleven complete current archive/loader/manager/utility TUs compile, with
  MPQ and trace logging enabled. Existing async job bodies, cache identities,
  archive dispatch and resource initialization remain in current LUS code.
- A/B/D/E: isolated typed constructors, scoped enum, container/string methods,
  original reference-preserving ranges, official nonstd string-view-lite and
  native filesystem/future/variant types resolve the reached incompatibilities.
  Context's real declaration is retained with a generated AudioSettings header;
  AudioPlayer must later consume the same definition. No Context substitute.
- Focused host loader/header/factory and view/glob checks pass. These are
  selected-method unit audits, not full resource manager or archive-mount tests.
  The complete TUs are compiled separately. An inherited negated glob class
  can consume NUL; documented without an unrelated platform behavior change.
- B/C/I/endian: exact required StormLib v9.25 plus the exact LUS optimization
  patch builds 231 PPC objects. Explicit big-endian MPQ conversions and portable
  cryptographic byte paths replace invalid desktop platform detection. Only
  unavailable mapped-view/WinInet providers take upstream unsupported branches;
  actual OtrArchive uses the retained native plain-file provider.
- Host encrypted format-V2 MPQ creation, five lossless codecs, random access,
  listfile and missing-member checks pass. LZMA requires format V2 in upstream;
  the fixture was corrected after the library properly rejected format V1.
- Details: platform/shipyard/resources/RUNTIME.md and STORMLIB.md. No XEX,
  Context execution, Xenia gameplay or hardware claim. All changes remain
  generated/platform-owned; upstream source and all references stay untouched.


### 2026-09-20: Current matrix/audio factory and configuration

- Seven actual current/native audio TUs compile. Modern matrix filters, delays,
  phase and saturation are retained; XDK syntax is generated. Host matrix PCM
  matches the original at 32/44.1/48 kHz across resets and variable block sizes.
- Generic donor XAudio2 ownership is carried through the real AudioPlayer API.
  Smash's application-specific raw51 rejection is not imported. The actual SoH
  32000/1024/1680 settings and 528/560 worker cadence remain upstream-owned;
  no old mixer or worker replaces OTRGlobals. Pool/routing host tests pass.
- Audio's real factory registers XAudio2; upstream null fallback remains explicit.
  Complete Config compiles, preserving modern nested/flat JSON, save/reload and
  version migration behavior. Host original/projected method audits agree.
- Native configuration maps unsupported desktop audio choices to XAudio2 and
  registers Xenos metadata. Existing enum numbers remain intact. Config uses
  the exact release CVar names via the shared evaluator, verified byte-identical
  to the successful full C build (no invented gSettings.AudioChannelsSetting).
- Pointer-only header dependencies are narrowed; real class declarations remain.
  Window's -1 scancode initialization must accompany its upcoming constructor
  projection. No Window implementation or Context startup claim yet.
- Config's local parse-only stream is read into a string for the real parser;
  full general JSON stream/ordered/custom APIs remain unresolved. Existing
  missing-component traversal behavior was observed and retained in tests.
- Source/ownership/validation details are in audio/README.md and
  configuration/README.md. No audio playback, XEX, Xenia or hardware claim.

### 2026-09-20: Shared window, CVar and actual Context closure

- Five complete current window/GUI base TUs and ConsoleVariable compile with
  XDK. Constructor projections preserve target bodies and member defaults,
  including all four Window -1 scancode paths. Current recursive CVar JSON and
  legacy migration are retained; full persistence execution is still pending.
- Twelve Context/lifecycle/bridge/native service TUs compile. Real initialization
  and ownership remain upstream. Native error reporting uses XShowMessageBoxUI;
  game: root follows primary SoH360. Writable XContent integration remains open.
- Ruling: guard partial Context cleanup and reset the published Window after
  Init throws. The modern donor identifies this real lifecycle failure boundary;
  ordinary successful startup is unchanged. Cost if wrong: partial GUI cleanup
  must be revisited during native failed-startup validation, which is pending.
- Generic Smash context/compiler lessons were read, not executed. No Smash
  application startup, paths, rumble policy or BattleShip EventSystem was
  imported; the pinned SoH LUS does not contain that EventSystem subsystem.
- Full original/projected GuiElement lifecycle and GfxDebugger state checks
  agree. Current Console method audit (excluding live-Context Run) agrees.
  Initial linker-discard experiment still needed Context symbols and was
  discarded; production TU compilation never excludes Run.
- Current CrashHandler buffer/callback implementation remains, with native
  exception capture pending. Upstream callback-constructor and truncation
  issues are documented in context/README.md rather than silently changed.
- GameOverlay constructor defaults and the direct implementation dependencies
  removed from Gui.h must accompany their forthcoming implementation projection.
  These headers preserve full declarations, not replacement implementations.
- Detailed commands, evidence and limitations: platform/shipyard/window,
  console-variables and context READMEs. All reference trees remain read-only.

### 2026-09-20: Logging conversion ordering regression

- Resource integration exposed a projected host crash at a trace call during
  destruction of a default Texture with null metadata. Original IResource's
  trace expression itself assumes non-null metadata; the final factory test
  uses the real factory's valid ResourceInitData ownership rather than relying
  on that undefined null-reference case.
- A separate well-defined counted-conversion test proved the platform defect:
  fmt4 overload macros packed filtered arguments eagerly (four conversions for
  two calls), while current spdlog performed none. Generate all logger arities
  with the original log/backtrace gate before packing; global overloads forward
  references, and packing stays inside the error-handler boundary. Generic
  Shipyard B compatibility correction; no game/resource behavior is replaced.
- The regression also checks global/source-location/extended-argument paths
  and preserves backtrace collection of messages filtered from normal output.

### 2026-09-20: Current GUI resource factories and overlay

- Seven complete current/dependency TUs compile: font, GUI texture and their
  factories, GameOverlay, Fast Texture, and exact CMake-pinned stb_image.
- Original/projected full factory tests agree on raw font bytes, PNG RGBA with
  alpha, invalid data, format rejection, size and valid metadata ownership.
  Both BinaryReader endian modes leave opaque font/encoded-image bytes intact;
  encoded formats parse their own byte order. No GPU upload or PPC runtime claim.
- GameOverlay's actual constructor restores Default/false state. Its current
  notification/settings/draw code remains; known unsafe inherited TEXT/format
  paths are noted for execution review, not silently rewritten or removed.
- Generic source ownership, header precedence and commands are in
  platform/shipyard/gui-resources/README.md. No application/runtime milestone.

### 2026-09-20: Complete modern Fast3D interpreter

- Full pinned interpreter compiles as one Xenon object. Every original command
  handler remains; six opcode tables retain names, function identities and
  insertion order. No old interpreter, Smash policy or wider shader key imported.
- Generic A/B/H projections preserve in-class defaults, scope and aggregate
  assignment. Raw RSP/RDP storage is zeroed before placement construction to
  preserve value initialization despite the XDK nested non-POD defect; live
  resource ownership is never overwritten. ShaderMod and raw texture metadata
  retain their original value-initialized state and default scales.
- Current texture-cache equality includes both palette pointers and size, and
  combiner ordering includes the exact two current fields. Depth-map range
  insertion preserves the current merge destination; its temporary source dies
  immediately. Round/clamp preserve the current numerical contracts.
- Host original/projected state and twelve-method audit passes alongside actual
  full-TU native compilation. GPU readback keeps the original host-endian guard;
  native backend must return numeric RGB5551. Native upload/readback and full
  renderer execution are still pending. See platform/shipyard/fast3d/README.md.

### 2026-09-20: Modern JSON container and enum contracts

- Generic Shipyard B boundary adds string-key map, std::array, C-array and enum
  conversion, preserving array partial mutation/error and char-string behavior.
  A narrow-arithmetic bool conversion mismatch was corrected against 3.12.0;
  enum conversion still rejects bool. Six host differentials and four native
  objects pass; unsupported conversions continue to fail compilation.
- XDK lacks underlying_type. Exact source-checked RandomizerCheck/Status
  registrations are generated for inclusion after real declarations. Other
  enums fail closed until audited; this is not full packet/save integration.
  Ordered/custom/initializer-list/stream APIs remain open. See JSON audit.

### 2026-09-20: Full current input core and native physical interface

- All 97 pinned input files are retained: 47 full controller/mapping TUs plus
  two generic native physical/XInput TUs compile. Modern defaults, blocking,
  lag buffer and mappings own input behavior. Controller/pad bits remain uint32.
- Primary SoH physical button/axis/trigger/rumble semantics inform the backend;
  generic Smash API/syntax lessons adapt modern SDL-named mapping calls to XInput.
  Old profiles, Smash defaults, Raphnet and game callbacks are not imported.
- Six default containers, custom high-bit bindings, 40,401 stick vectors and
  physical reconnect/axis/rumble fixtures pass. This is not native execution.
  Original mButtonNames/GetControllerBits/topology-ignore/copied-map quirks are
  documented for actual consumer integration, not silently changed. See input
  README for provenance, commands and remaining menu/device validation.

### 2026-09-20: First modern application resource factory closure

- Background, PlayerAnimation, Text, Array and Cutscene types/factories compile
  as ten complete TUs. Three generation checks, native ABI checks and full
  original/projected LE/BE/XML factory contracts pass. Narrow A/B projections
  preserve inherited constructors, distinct enums and reader variants.
- Cutscene's mixed byte/halfword helpers remain verbatim; the reader compares
  each payload order against native. Font/image/background byte streams and
  typed animation/text/array reads keep their separate contracts. No global
  swap or archive format replacement. Nine other resource pairs and all scene
  command factories/registration remain open; soh-resources/README.md records
  the next audio envelope endian boundary and exact validation evidence.

### 2026-09-20: Exact Prism and genuine modern shader generation

- Five complete Prism dependency TUs and the full current DX shader builder
  region compile with XDK. The real default/include Shader resource loads,
  native byte order and missing-default abort are retained in production.
- Generic Smash fixed-arity variant/optional and Prism syntax techniques are
  provenance-locked in owned files; no BattleShip builder, shader-ID packing,
  resource facade or default template is imported. Debug logging remains active.
- Original/projected full Prism and current builder audits agree over 936
  cases, vertex float counts and parser/errors/owned values. All 264 unique
  representative Xbox VS/PS compilations pass. Test-only template acquisition
  is isolated from the production resource path. GPU execution and native
  callback/stack behavior remain unproven; see prism/README.md.

### 2026-09-20: Native Xenos backend against the current API

- Primary SoH360 native mechanics are byte-locked and adapted with reviewed
  generic modern six-binding/framebuffer work. All current rendering virtual
  methods compile with real XDK APIs; old callback tables, test scenes and
  BattleShip-only rendering/ownership extensions are excluded.
- Current Prism/decoder own shaders. Internal cache identity also includes
  filtering/sRGB, with current variant selection for interpreter-held pointers.
  A 64-bit donor logging specifier was corrected for the genuine uint32 ID.
- Native ARGB-to-RGB5551 channel/alpha tests and full-width shader identity
  tests pass. New six-binding constants use direct SDK writes; old exact-value
  reuse retains invalidation/verification. All GPU behavior remains unexecuted.
- Old title asset-cache eviction and disk shader persistence are not connected
  to modern LUS/storage. Real shader compilation/allocation errors remain; no
  alternate resource manager or fake shader is supplied. XContent cache worker,
  window/GUI ownership and actual native validation remain open. See xenos README.

### 2026-09-20: Current Fast3D window and native presentation

- All methods of current Fast3dWindow and FastMouseStateManager compile, with
  exact draw ordering retained. A concrete native GfxWindowBackend provides
  real device initialization, presentation, latency, timing and XInput pumping.
- SoH360 presentation fraction behavior retains remainder on unchanged target
  rates; actual refresh and 64-bit addition make the native boundary explicit.
  Three Xenon objects and 2,024,400 host pacing checks pass.
- Shared fullscreen/pointer constraints remain platform behavior. No synthetic
  keyboard/pointer events or extra application loop. Native GUI integration,
  physical input execution and all Xenia validation remain open. First-bring-up
  estimate stays approximately 60%; see presentation/README.md.

### 2026-09-20: Modern application resource factories expanded

- Reviewed the independent resource-factory handoff: 49 pinned source inputs,
  23 complete production TUs and one native ABI object. Added animation,
  sequence/sound-font, collision, path and limb resources without removing
  service-dependent methods. SkeletonPatcher and AudioSample's codec closure
  remain explicit work, rather than compiling truncated classes.
- Original/projected tests match seven complete resource pairs, plus 2,068
  bytecode cases and XML path/envelope/error/format methods. Five projection
  checks pass. XML sound-font envelopes preserve BE byte storage on Xenon;
  RTTI is enabled for actual sample patch casts. See soh-resources/README.md.
- The three relevant sound-font audio enums are emitted from the pinned header;
  all production resource registrations and real service execution remain open.

### 2026-09-20: Genuine current GUI and native ImGui integration

- All current Gui/default concrete window methods compile, including the full
  controller editor, console and graphics debugger. Xenos initialization calls
  actual Gui::Init, preserving upstream Context/window/renderer ownership.
  Native GUI shutdown runs before graphics destruction and is idempotent for
  the existing base-window cleanup. Controller navigation defaults on only if
  its existing CVar is absent; saved choices remain authoritative.
- XDK's 65535-byte concatenated-string limit is resolved with a deterministic
  numeric array of the exact 155711-byte font. Independent compiled source
  literals and both real ImGui font atlases match (903 glyphs, 56e5f0b0).
- The debugger's unsupported default lambda parameter caused C1001/C3486.
  Exactly 32 call sites now provide its same default explicitly. Experiments
  with return annotations/formatter hoisting were discarded. Full console
  metadata, optional textures, clipboard and current UI paths remain.
- Native renderer/platform compile and actual shader stages pass XDK fxc;
  56 real ImGui controller bindings, disconnect/analog/timing checks pass.
  Native GPU rendering, SoH feature windows, text entry and persistence remain
  unvalidated/unintegrated as documented in gui and native-imgui READMEs.
- Auditing dynamic casts exposed /GR- in earlier native recipes. /GR is now
  explicit throughout native C++ build recipes. Input, binary tools and thirteen
  runtime components rebuild successfully; receipts are in scratch/rtti-rebuild.
  Resource leaf rebuild and final uniform build composition still remain.

### 2026-09-20: JSON stream contracts and RTTI resource rebuild

- The completed independent JSON stream change was reviewed and reverified:
  eight generation checks, seven original/backend differentials and five full
  native objects pass. Input extraction versus strict parse, stream flags,
  partial DOM mutations, serializer write boundaries, encoding failures and
  file-backed current consumer statements are covered. Serializer methods are
  projected from pinned nlohmann 3.12; no replacement save policy was imported.
- Ordered JSON, initializer lists, custom ADL/macros and binary DOM remain
  unsupported. The stream probes do not establish whole SaveManager execution.
- All nine complete resource leaf TUs now rebuild with explicit /GR and their
  original/projected factory differential passes against the updated JSON.
  Final uniform application build composition and runtime remain open.

### 2026-09-20: Complete current Fast3D resource readers

- Nine complete native TUs preserve binary/XML factories, all expanded display
  commands, owned XML strings and both texture versions. The 57 old-compiler
  brace assignments use deterministic typed temporaries; original GBI macros
  remain intact. Upstream F3DEX_GBI_2 is explicit, including XML ucode selection.
- Full original/generated factory executions match 19,167 official archive
  records and independent LE/BE/XML/failure fixtures. No texture-byte swap was
  introduced. Light raw-union point-coordinate format still requires actual
  producer/registration evidence; its host raw-byte check is narrowly reported.
- Generic Shipyard A/B/I changes; all nine Xenon objects pass with /GR. No native
  archive/resource execution or render/gameplay claim. See fast-resources/README.md.

### 2026-09-20: All scene commands and current interpolation

- Completed scene handoff reviewed: 54 additional full TUs, bringing application
  resource coverage to 77. All 25 command pairs, Scene/dispatcher/loggers retain
  their registrations, acquisitions and CVar calls. Six projection checks and
  original/projected 21-factory XML/type/logger/mesh/ID audits pass. Full binary
  Scene dispatch and the four service-dependent XML factories still need runtime
  integration. Native type/ID/ABI receipts remain explicit.
- Complete current frame interpolation now compiles, preserving the 72-byte
  native recording union. Exact existing FPS bridge, POD label, scoped enum and
  generated aggregate/iteration spellings resolve XDK limitations. The bounded
  host math/recorder audit matches 589,824 integer-angle cases and lifecycle,
  matrix/inverse/float-angle checks. No whole-frame native execution claim.
- Translation/first-bring-up estimate is now approximately 64% (50–70% range),
  with 696 C and 78 C++ application TUs compiled. Full modern application C++,
  release-definition integration, linking and genuine Xenia execution remain.

### 2026-09-20: Deterministic XDK project and required disassembler

- The completed independent project-generator handoff was reviewed. Declarative
  subsystem recipes produce inspectable XML and full pending-source coverage,
  with stable unique object names and explicit C/C++ ABI flags. Seven genuine
  production TUs compile through MSBuild; six generator checks pass. An ordinary
  incomplete Build fails before emitting a library/executable. The generator
  marks old preprocessed-C definition omissions for regeneration, not late /D fixes.
- The audit exposed root's enabled GFX_DEBUG_DISASSEMBLER. Exact libgfxd was
  acquired, all seven full C TUs translated, and 15,360 full original/projected
  disassemblies agree across opcode/ucode/endian cases. Table field order and
  C99 formatting are preserved; the host-word endian algorithm stays verbatim.
- All six full current GUI TUs now rebuild with disassembler and F3DEX_GBI_2
  enabled. The early isolated decoder object is excluded from final composition
  because the full interpreter owns the same symbol. No feature was disabled to
  obtain the generated project or successful GUI compile.

### 2026-09-20: Combined runtime compilation and complete sample decoders

- All 737 selected runtime/dependency units compile together through the generated
  XDK project; unique output objects verify as PPC BE. Evidence is
  scratch/project-xdk/runtime-integration-verification.json. All 696 application
  C units were regenerated and recompiled with INCLUDE_MPQ_SUPPORT and
  SPDLOG_ACTIVE_LEVEL=0; no lost preprocessor branches were repaired with late flags.
- Complete AudioSample type/factory adds two application TUs and every real codec
  branch. Exact upstream dr_libs is pinned; system Vorbis is explicitly pinned to
  v1.3.7, with all 22 source units mechanically compiled for XDK. Encoded bytes
  remain untouched. Vorbis output requests native PCM order because the genuine
  CODEC_S16 mixer reads copied bytes as native signed 16-bit values.
- Actual original/projected binary and codec-worker tests agree, digest
  10424164288805436507; 8,192-frame PCM fixture, four codecs, both serialized
  orders and opposite Vorbis byte orders. Host XML Context acquisition is outside
  this audit; its complete native method remains. See audio-verification.json.
- Generic Shipyard detached worker preserves callable ownership, real concurrency,
  creation-error propagation and termination on uncaught exceptions. Original
  std::thread comparison passes lifetime, 1,000 fast completions and exception
  subprocess checks. Existing upstream early decoder-buffer publication remains
  a runtime audit item, not a silently altered application behavior.
- Resource inventory is now 79 complete TUs; current application coverage is
  696 C plus 80 C++. The generated manifest contains 1,458 production compile
  items, with 318 application C++ units still explicitly pending. Estimate stays
  64% (50–70% range); no modern link, startup or gameplay claim.

### 2026-09-20: Ordered JSON, exact default floating formatting and libultra

- Reviewed and reran the three isolated task handoffs; all agents are finished.
  Ordered JSON has a distinct insertion-ordered nested DOM, exact ordered_map
  method projection, original/projected stream and real consumer-statement
  comparisons. Eleven generation tests, ten host differentials and seven PPC
  objects pass. No sorted alias or fake seed/application class was introduced.
- Actual pinned fmt12 Dragonbox supplies binary32/binary64 shortest formatting;
  361,013 comparisons pass. Native POD tables avoid dynamic cache initialization.
  This changes internal packed argument codes: an all-consumer XDK rebuild is
  running, and pre-change objects must not be linked with this formatter. Native
  CRT explicit-precision rounding and subnormal execution remain unproven.
- Eleven current LUS bridge/libultra TUs plus one generic Shipyard timer/clock
  unit compile. All 76 original methods remain. Queue/DMA and 200,004 exact
  clock checks plus real Win32 timer lifecycle tests pass. Keep the upstream
  static archive extraction boundary: application stubs override five inactive
  os_cache/os_pi symbols. StopTimers belongs before callback queue teardown.
- Native Skeleton type/factory and the complete modern SkeletonPatcher compile.
  Only unused umbrella includes, scoped enum casts, inline variable storage,
  string-prefix/range syntax and necessary game declaration order changed.
  Typed pointer-size ABI and original/projected removal/clear methods pass;
  actual player/custom/tunic service execution is not claimed.
- Three complete GameInteractor TUs compile with generated forwarding overloads
  derived from actual hook-table arity, original registry bodies and shared
  template storage. Source-location callers supply actual file/line/function
  metadata; no feature-disabled hook debugger fallback is selected. Host actual
  registry checks include cross-TU sharing and deferred registration removal.
  Full enhancement registration and native game execution remain pending.
- The assembled 1,475-item compile project subsequently passed with the new
  formatter and ordered JSON. Every object is verified PPC BE and every production
  source still matches its manifest hash; receipt is
  scratch/project-xdk/complete-selection-verification.json. Application coverage
  is 696 C plus 85 C++; 313 C++ TUs remain pending. First-bring-up estimate is
  now approximately 65%, with a 50–75% uncertainty range pending linking/runtime.

### 2026-09-20: Real cheat, actor and randomizer value integration

- Fifteen complete modern cheat units compile through real ShipInit/GameInteractor,
  including Infinite Ammo's actual randomizer Context/OptionValue branch. Generic
  A/B projections preserve set ordering/lifetimes, hook metadata and native variadic
  cursors; host dispatch and variadic contracts pass. No cheat execution is claimed.
- All three ObjectExtension/actor payload units compile. The reached std::any
  boundary is a copyable owning RTTI implementation with pointer casts, strong
  failed-copy behavior and actual registry lifetime/isolation tests. No small
  object optimization yet; profile its allocation cost after real gameplay.
- Full ActorDB and all six configuration updater implementations compile. Actor
  init globals and EnPartner remain genuine references. Description table/defaults
  and all five unchanged Entry ownership methods match upstream on the host.
  ConfigUpdaters.cpp is unchanged, including migration ordering and duplicates.
- ActorDB exposed the generated endianness helper through a C-linkage include.
  A narrow extern-C++ region fixes the generated C++ declarations without changing
  any swap decision. First-include native regression failed before and passed
  after; original/projected binary contracts and six generation tests pass.
- Reviewed the isolated randomizer foundation: complete current Context/value
  declarations, 73 inventoried defaults with 58 native-path initializers and
  canonical OptionValue ownership. Eleven tests pass, including full host field
  offsets and three real value-method comparisons. Context is 196044 bytes on
  Xenon. Full ItemOverride and four canonical OptionValue methods compile;
  partial method probes do not count as completed feature TUs.
- The real OTRGlobals declaration retains its fields and services and compiles to
  80 bytes on Xenon. Eight font pointer defaults move into the same retained real
  constructor; full application compilation and startup remain open.
- Assembled coverage is 696 C plus 106 complete application C++ TUs, with 292 C++
  units still pending. The 1,497-item integration compile passed; all object
  formats/source identities are verified in
  scratch/project-xdk/application-services-verification.json. Estimate
  stays 65% (50–75% range), with no modern XEX or target execution claim.
- Eight additional complete Fixes units compile outside that saved selection.
  The real stateless ShipInit callback is hoisted into a named generated function
  because XDK rejects __FUNCSIG__ in static-initializer lambdas. Deferred execution,
  path/callback order and metadata availability are tested. Hammer Hand retains
  its original gs macros through typed Gfx locals, resolving braced-call syntax.
  The complete GameInteractionEffect TU also compiles with a canonical action
  declaration split from the real cosmetics header; the real service is retained.

### Modern widget, message and utility integration (2026-09-20)

- A/B/G: complete UIWidgets.cpp, all twelve option structures and MenuTypes.h
  projected reproducibly. Original function inventory retained. Explicit value
  initialization preserves zero defaults without changing default-initialized
  indeterminate flags. Actual typed variants, ownership, callbacks, filter/text
  bodies and color results match upstream. Native rendering is not executed.
- A/B/F: all 67 CustomMessageManager functions compile, including the three live
  service methods excluded from bounded host execution. Five real language/maps
  retained; 2,462 host output lines agree and 312 UTF-8/embedded-control literal
  arrays agree in native COFF data. No message service substitutes.
- A/B/C: complete ShipUtils and randomizer RNG providers compile. Native entropy
  uses XNetRandom with real failure propagation; application startup must own
  XNet initialization. Seeded RNG/container references, 7,744 vertex groups and
  4,194,304 rotation cases pass. Platform wrappers are generic Shipyard; actual
  modern game algorithms remain source-derived 3Shipsty application code.
- Complete GameInteractor RawAction and Effects now join the other three units;
  all 23 selected modern Cheats/Fixes also compile. The expanded deterministic
  selection contains 816 application TUs (696 C, 120 C++), 278 C++ pending and
  1,512 total production units. Test probes are explicitly excluded, and the
  flattened full message source has its correct original-source identity.
- Full assembled rebuild passes; all 1,512 object formats and source hashes
  match scratch/project-xdk/ui-services-verification.json. First-bring-up estimate remains 65%.
  Two independent startup/save-storage tasks are active, without delegation
  chains. No XEX, gameplay or hardware claim.

### Full menu, option and save-boundary checkpoint (2026-09-20)

- A/B/G: six complete Menu/SohMenu/modal/settings/enhancement/developer-tool
  units compile. All 449 feature widget registrations retain original arguments;
  canonical value-initialization, search/modal ownership and three accented
  UTF-8 strings pass original/projected and native object checks. Xbox's absent
  desktop file-manager capability disables its existing folder button with an
  explanation; game/enhancement controls are retained.
- A/B/D/F: full option.cpp retains all 59 remaining methods and the original
  four OptionValue definitions in their existing canonical provider. Complete
  Settings/Option/LocationOption/TrickSetting/OptionGroup/Tricks declarations
  preserve all fields/defaults. Five checks cover 232 options, 268 tricks,
  85 groups and real callbacks. Settings is 242432 bytes on Xenon; options and
  tricks initialize in place without returning large temporary arrays. The
  genuine Settings constructor is an explicit fragment, full settings.cpp open.
- C/D/E/F: startup uses genuine version readers and the same upstream archive
  acceptance contract, with extraction owned by the PC. Real audio handshake
  uses native primitives; its unlocked running read is removed in favor of the
  existing locked exit check. Timer teardown precedes Context destruction.
  Initial evidence used eight method probes, excluded from production coverage.
  Full startup compilation now supersedes that earlier boundary milestone.
- B/D/E/F: 38 actual SaveManager members and 11 C bridges compile with the real
  modern BS worker. Native XContent selection/mount/flush/close and atomic file
  publication retain prior saves on pre-replacement failures. Host comparison
  covers 161 serialized outputs and four real base loaders; worker-drain and
  file-failure tests pass. No randomizer or legacy methods are substituted.
  Mount/configuration lifetime and asynchronous failure presentation remain open.
- The complete 1,521-item integration build passes, with all source identities
  and PPC objects verified in scratch/project-xdk/menu-storage-verification.json.
  Two additional randomizer option/constructor recipes pass their generated
  project with pinned target definitions. Inventory now selects 696 C and 127
  complete C++ application TUs, 271 C++ pending. Estimate: roughly 65–70% first
  bring-up, broad 50–75% uncertainty. No modern XEX or target execution claim.
- Legacy raw-save producer/layout/endian provenance is now recorded in
  porting/LEGACY_SAVE_AUDIT.md. An explicit byte decoder remains separate from
  modern JSON serialization; blanket swapping and native reinterprets are not
  acceptable. Implementation and controller editor are independent active tasks.


## 2026-09-21 — complete randomizer runtime batch

Integrated full SeedContext, ItemLocation, fishsanity, Kaleido collectibles,
ItemTableManager, Hint, Dungeon and Trial implementation sources plus canonical
StaticHintInfo construction. No alternate runtime or gameplay services were
introduced. This batch preserves 171 original definitions in the root provider
and all complete agent-provided hint/dungeon/trial definitions.

A/B adaptations retain constructor/default/value semantics, real JSON ordering,
set/map behavior, full option/texture/fish tables, hook registration and actual
Gfx command arguments. Header-only seed textures have one external definition.
KaleidoEntry remains abstract: pure virtual '= 0' declarations are explicitly
protected from member-default lowering. No endian conversion is introduced.
Detailed ownership and limitations are in platform/shipyard/randomizer-context,
randomizer-hints and randomizer-dungeons README files.

Original/projected value execution passes for 2,520 ItemLocation states, all
65,536 item IDs, fish helper tables, all 12 dungeon definitions/65,536 scenes/
4,096 MQ masks/64 trial masks, and hint formatting/ordered JSON/default behavior.
Full XDK integration passes: 1,545 selected production objects, 696 C plus 146
of 398 application C++ units. All source hashes/PPC object hashes are recorded in
scratch/project-xdk/randomizer-runtime-verification.json. Nine manifest/project
checks pass. Full application linking and execution remain outstanding.

The user's concern about granularity is valid: earlier compile milestones were
not the last remaining steps. Work/reporting is grouped by functional batch;
first-bring-up remains approximately 60–65% with high uncertainty, superseding
the overly optimistic 70% estimate. Complete application windows, remaining
randomizer/data/runtime and network implementations, speech, link integration,
and genuine Xenia validation remain. No modern XEX has run.


## 2026-09-21 — complete windows, editors and data integration

Thirteen complete debugger/resolution/icon window sources, both full audio and
cosmetic editors, and full location/static-data sources now pass the main XDK
build. All 1,562 selected source hashes and PowerPC objects are verified in
scratch/project-xdk/application-windows-verification.json. Application coverage
is 696 C plus 163/398 C++ sources, with 235 C++ sources still pending.

A/B/H adaptations preserve aggregate/default/widget semantics, lambda member
access, actual callback identity/lifetime, original container contents and UTF-8
bytes. C/D performance timers use the existing native monotonic clock wrapper.
Runtime-native geometry retains signed normals and qs105 texture-coordinate
scaling. There are no new endian conversions. Platform-specific statistics
correctly label Xbox 360. Details are in application-windows, application-editors
and randomizer-data READMEs.

Original/projected checks cover actual collision geometry, every 16-bit icon
input, timers, 161 UTF-8 literals, all cosmetic/audio editor tables and widget
values, 34 Location factories and 446 static-data entries. These are meaningful
translation checks, not target gameplay evidence. First bring-up remains about
60–65%; no modern XEX has linked or run. Work continues by complete functional
batches, with two independent agents and root integration.


## 2026-09-21 — genuine scene/message/resource bridge integration

All eight complete core application bridge TUs pass the integrated XDK build.
The 1,570 source hashes and PPC objects are recorded in
scratch/project-xdk/application-core-verification.json. Application coverage is
696 C plus 171/398 C++ TUs (227 C++ pending). All original function definitions,
UTF-8 literals, GfxPatch data, and the explicit high-byte/low-byte RGBA16 JPEG
conversion remain. A/B changes lower syntax and use existing native formatting
and enum wrappers. Detailed boundary evidence is in application-core/README.md.
Actual original/projected utility and message-field checks match 5,297 lines,
including 65,536 message IDs and bounded buffer/string byte tests.

An upstream custom-message override size mismatch (allocation messages.size(),
lookup messages.size()+1) is recorded for runtime review; it is not masked by
syntax changes. Complete scene execution and loaded archives still await Xenia.
First bring-up remains roughly 60–65%, with no linked/running modern XEX.


## Complete application feature integration, 2026-09-21 (in progress)

The full gameplay-enhancement, network application/packet, randomizer content,
region-graph and application-extras batches compile with XDK individually.
Root reran all five provider checks. Evidence is under their scratch directories;
main integration is still running and no link/runtime milestone is claimed.

A shared A/H projection defect was found through EntranceHints: textual removal
of ` override` also corrupted `overrideIndex`, ordinary fields and comments.
`prepare_resource_manager.syntax` now removes only AST virtual specifiers.
`test_contextual_specifiers.py` protects class/function specifiers, legal fields,
identifiers, strings and comments. Completed gameplay generated differences are
only restored comments; rebuild receipts will be refreshed before checkpointing.

Randomizer worker shutdown is being adapted to the existing joining_thread
boundary. The original JoinRandoGenerationThread checks only `generated`, so an
active incomplete generation could outlive resource teardown. The projection
joins any joinable real generation worker; original generation, seed, settings
and hook behavior remain. This lifecycle change is not yet runtime validated.


## 2026-09-21 — complete application source selection and lifecycle integration

All 696 C and 398 C++ application TUs now have complete selected production
providers. Individually verified batches include all enhancements, network
packets, randomizer content/regions/generation/hooks/trackers, application extras
and speech. The deterministic manifest contains 1,833 production objects, with
16 explicit desktop/mobile platform decisions; unmodified upstream stox.cpp
closes the remaining generic LUS utility gap. No application TU is excluded.
The combined release build is still running, so this is not a full-project
compile/link or target execution claim. No modern XEX exists yet.

Real InitOTR selects XboxSpeechSynthesizer ahead of desktop providers. DeinitOTR
joins any real generation worker before tearing down its dependencies, then
concretely destroys speech before GUI/Context release (upstream base destruction
is nonvirtual). The completion flag is cleared after the join, avoiding a write
racing the worker's completion. The actual join body passes idle, unfinished and
repeated shutdown contracts. Full OTRGlobals compiles; five startup checks pass.

Speech adds the real static eSpeak NG 1.52.0 engine, pinned to
4870adfa25b1a32b4361592f1be8a40337c58d6c, behind the existing application interface.
Six root-rerun checks pass, including actual multilingual PCM equivalence,
queue ownership and measured native data layouts. This dependency is GPL-3.0-or-later;
its notices and corresponding source/build changes belong in release packaging.
Engine data is built on the PC in the standard eSpeak format; field-level endian
conversion evidence and packaging are documented in speech/README.md. No speech
or game audio has yet executed on Xenon.

New build/link wrappers keep the normal inspectable XDK compile project and
record real exit codes/source/object hashes. The link consumes every application
object directly and preserves ordinary LUS/dependency archive extraction; it
supplies no replacement entry point, forced unresolved symbols or donor game
objects. They are awaiting full combined execution. First-bring-up estimate
remains about 60–65%, uncertain until linking and real runtime evidence.

## 2026-09-21 - user-requested stop and handoff

Stopped at the user's explicit request. See HANDOFF.md for the complete resume
record. Last commit: c0e0343406cda289762ff1b892239a62796ec041; uncommitted fixes
are preserved separately and are not represented as a verified checkpoint.

Full combined XDK compilation passed: 1,833 production PPC objects, all 1,094
application translation units selected, eleven inventory checks passing. Genuine
linking failed with 16 unresolved symbols: ten generated build metadata globals,
four CRT functions and two interpolation references with incorrect C++ linkage.
No modern XEX or application execution has occurred. First bring-up estimate is
about 65%, with runtime uncertainty.

Uncommitted metadata generator compiles the actual upstream template and verifies
native version fields. Interpolation macro projection preserves the original
macro bodies while eliminating block-scope declarations that confuse XDK lambda
linkage; its standalone rebuild completed 89/89 units. CRT agent was interrupted;
its standalone host/native receipts exist but implementation review and integration
remain. No combined build or link verifies these latest changes. The earlier
complete receipt must be refreshed after source regeneration.

Runtime retail NTSC 1.0 O2R archives and speech data are staged. All agents are
completed or interrupted; no new builds or fixes were started after the stop.
Reference trees and upstream application sources remain untouched. Resume steps,
commands, evidence and uncommitted file inventory are recorded in HANDOFF.md.
## 2026-09-21 - resumed link closure

User requested fixing all 16 unresolved symbols and continuing real bring-up.
The generated metadata provider and two generic CRT production sources are now
selected by the inspectable manifest. A new inventory check first failed because
the metadata recipe was absent, then all 12 checks passed after integration.
Metadata native version/string fields pass. CRT root rerun passes 1,273,868 float
cases across all rounding modes and 66,950 formatting cases; SDK sources establish
the control-word mapping and formatting boundary. Preserve /fp:strict.

The complete FileSelectMoreInfo native object now imports the actual unmangled C
interpolation symbols. The focused gameplay test checks that object linkage and
all 89 full source inventories/six original-projected contracts pass. This is an
H-class XDK block-scope declaration/lambda linkage adaptation, preserving both
original display macro bodies through generated source. No duplicate interpolation
implementations are supplied. Combined build/link verification is underway.
## 2026-09-21 - genuine application link achieved; runtime startup fault

Fresh combined build verified 1,836 production PPC objects. All 1,094 application
TUs remain selected. Genuine link and ImageXex returned zero: 3Shipsty.xex is
45,834,240 bytes, SHA256 3b6d82d9c29c4fe2787bd61a6da9d5758b8abd5b4fc2c763d272dad5f67f4fe0.
All sixteen previous symbols are resolved without suppressing unresolved symbols.
The exact prior failure is preserved in scratch/link-integration/before-symbol-closure.
Retail archives and speech data accompany the staged XEX. This is no gameplay claim.

Initial Xenia run pauses on an invalid read during conditionalAlwaysHints static
initialization. Noninvasive debugger captures under scratch/runtime/xenia map the
fault to hints.cpp vector<pair<RandomizerCheck,function<bool()>>> copy. Actual source
contains all twelve lambdas, but /O2 native GenerationList56 initializes only three
array elements then copies twelve. This is an H compiler-codegen defect at the
initializer-list projection boundary. Ordered named-element construction is being
verified; original callbacks/order/predicates are preserved. No game path bypass.
First-bring-up engineering estimate remains around 70% pending runtime correctness.
## 2026-09-21 - runtime progress and external approval-service block

Checkpoint 3581983af5a5d3dbc4a100aa6b37a241526c07bc commits all sixteen link fixes.
The uncommitted callable-array compiler workaround passes full compile/link and
real Xenia execution gets through static initialization into InitOTR and archive
discovery. Latest XEX SHA256 is dc03cb7a53475de94c7ec7e46fe247703843c184ce58516927cdd96feddcf0e5.

A second startup failure is the missing initialization of the logical filesystem
working directory: an absent optional MQ archive falls back to a relative path,
which throws ERROR_NOT_READY. InitOTR now calls InitWorkingDirectory("game:/")
before storage/Context. Five checks and complete native OTRGlobals compilation
pass. The full build command was not executed: automatic approval review failed
because the account hit its usage limit. This is an external review-service
failure, not an unsafe-action determination. Do not bypass the approval gate.

Owned Xenia has zero local profiles and XamContentCreateEx also failed. Verify
local-profile prerequisites and capture its exact return code when resuming; no
profile has been created yet. The current XEX lacks the CWD fix. Complete current
state, dirty files, artifacts, evidence and next commands: RUNTIME_HANDOFF.md.

## 2026-09-21 - runtime storage/config closure and ImGui NewFrame boundary

Two narrow production checkpoints supersede the earlier unresolved runtime
state. `2e6db2f08ebc3e8a4f30b7702433b4ccc464c6bb` initializes Xbox working
directory state at real InitOTR. `0cad9e225f77b3ff40530f56a5676913118f9d1d`
uses the storage root name as the writable application directory, preventing the
mixed `shipyard:\/shipofharkinian.json` CRT path. The latter was developed red/
green against the real platform adapter; `test_application.py` passes 6/6.

With a supported local Xenia profile signed in, native content creation and the
`shipyard:` device mapping succeed. Real `soh.o2r` and retail `oot.o2r` open;
absent `oot-mq.o2r` is nonfatal. Current configuration repeatedly writes and
reopens, Context initializes, XAudio2 registers, a real controller appears in
slot 0, and game framebuffer inventory reaches IDs 3-7. Speech data init error
22 is nonfatal and execution continues past it.

The next actual failure is before rendering. Diagnostic checkpoints preserve
the real GUI/game path and prove first-frame readiness, mouse capture, backend
new-frame, and Xbox platform input all complete. The call into current
`ImGui::NewFrame()` never returns. Renderer StartFrame/draw/end and D3D Present
are not invoked, which directly explains the black surface. The internal stage
within NewFrame remains unclassified; the next evidence step is checkpointing
its ordered stages rather than disabling GUI or navigation.

Latest fresh build verifies 1,836 PPC objects and all 1,094 application TUs;
archive/link/ImageXex exits are zero. Staged diagnostic XEX SHA256 is
`9ba8b77a6ea3d083f6d261553cd8d8b7a318f431de6871ecbc6a71f28f42fe86`.
Conclusive Xenia and SoH trace hashes are recorded in `RUNTIME_HANDOFF.md`.
Xenia was stopped at the user's request; file select, save load/create, audible
output, gameplay, and modern-feature proof remain open.
## 2026-09-22 — Real post-logo path and 9.x-only Japanese font boundary

- Compared the actual modern `Message_Init`/ordered-font call chain with the
  working 4.0.5 source, not just names: 4.0.5 always loaded the NES byte font;
  9.2.3 added an NTSC ordered Japanese `u16` font even for North American
  English startup. Its O2R bytes are little-endian, while Xenon `u16` is
  big-endian. The old path therefore could not have exposed this fault.
- The Xbox-only game projection converts the 0xFFFC ordered-font list and
  ordinary Japanese dialog only when copied to native `Font.msgBufWide`.
  The real O2R records, region/language selection, and other text paths remain
  upstream-owned. Regression checks cover projected call sites and the
  `0x82A0`/`0xA082` byte-order distinction.
- Fresh 696/696 C and 1,836-object application build, link, and ImageXex pass.
  XEX SHA256 `2299f84cb404c2ec2729e7b66029fc88bc2d50055390ac6e5bd89c09891f6d14`
  (HEAD `0cad9e225f77b3ff40530f56a5676913118f9d1d`, pending checkpoint).
  Owned Xenia trace `scratch/runtime/post-font-filechoose-app-20260922.log`
  proves ordered-font completion, scene 81, gameplay frames, natural transition
  to FileChoose, and file-select fade. The user confirms visible UI and is
  testing a modern randomizer run.
- Foundational 4.0.5 skybox ownership behavior was carried to the actual 9.x
  TitleSetup/PlayState/FileChoose layouts. Relevant Smash360/Xenos depth,
  HiZ/histencil and 8 MiB secondary ring behavior is already present; no
  duplicate renderer patch was made. This differs from the new 9.x font issue.
- Native audio is not verified: buffer submissions continue but sampled PCM is
  all zero through the first 600 blocks, matching the user's report of silence.
  Save creation/load, completed randomizer generation, and playable gameplay
  remain open.

## 2026-09-22 — Modern randomizer gameplay and worker-boundary follow-up

- Owned Xenia ran the genuine 9.2.3 XEX SHA256
  `b7f83f704cd77b24711619c12e469d1213b9c8b005f9bb69c47b30e7ebc46c64`
  at HEAD `0cad9e225f77b3ff40530f56a5676913118f9d1d` plus dirty fixes.
  `scratch/runtime/post-rando-gameplay-app-20260922.log` SHA256
  `d52d6b9ff6fc2ca880209e33aeac8bb7105e55d30f2a3957d635874868612fb3`
  proves item/entrance overrides, hints, spoiler write, and true gameplay.
  User confirms controller movement, save, and save reload. Owned spoiler/save
  files both parse as JSON.
- Randomizer stall ownership: first ice-trap `GetTrapName`, before the first
  statement of the 192-assignment modern trick-name initializer. Xbox-only
  projection splits it into 24 non-inlined eight-assignment helpers without
  changing table content/order or RNG. The projection contract checks all
  assignment keys in order; native compile and full application compile/link
  pass. Every chunk finished in milliseconds in the real Xenia run.
- Modern audio and 4.0.5 threading were compared at the actual worker path:
  both have a separate mixer worker, and modern resource/save/randomizer paths
  are also threaded. 4.0.5 explicitly placed audio on Xbox hardware thread 2
  and save/diagnostics on 3; the modern generic native worker has no explicit
  processor placement. This is a performance follow-up, not yet a proven cause
  of silence. Native PCM remains all zero, with no active notes or enabled
  sequence players through task 1,200. Bounded audio sequence diagnostics are
  compiled in two C units but not yet in the staged XEX.
- One randomizer run could move and save but could not interact with chests or
  NPCs; A works for normal actions. User is checking a basic seed before this
  is classified as settings versus port behavior. Startup timing marks about
  9.25 seconds in modern application initialization after factory registration.
