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
