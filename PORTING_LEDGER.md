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
