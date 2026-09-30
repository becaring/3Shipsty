# Xbox 360 performance handoff — 2026-09-29

Work stopped at the user's explicit request. All three agents stopped; their owned Xenia/native processes finished. Do not resume optimization without a new user instruction. The user subsequently authorized committing and pushing incorporated changes and this handoff.

## Outcome and acceptance

**The performance objective is not achieved.** The user tested the delivered candidate on real Xbox 360 and reported identical performance, drops during boot/menu transitions, a hitch after pressing Start, and Kokiri below 45 FPS. They report that their actual 4.0.5 Xbox implementation does not have these problems. Treat this as the authoritative latest result. No corresponding new hardware log was supplied; older saved hardware logs are not logs of this candidate.

The objective remains sustained, correctly paced internal 1920×1080 at 60 presentations/sec on real hardware, authentic 20 Hz simulation, including settled Hyrule Field facing trees. No resolution/effect reduction, simulation slowdown, missing required presentations, or upstream behavior regression is acceptable. Field throughput is primary; shader creation and settings persistence hitches are separate issues. The user explicitly rejects shader caching as the explanation for sustained lag. Smaller routines, fewer evaluations, matching outputs and Xenia results do not establish acceptance.

## Workspaces and delivered checkpoint

- Modern active worktree: `D:/Projects/3Shipsty9.x/scratch/deslop-worktree`, branch `codex/shipyard-deslop`, origin `https://github.com/becaring/3Shipsty.git`.
- Selected shared Shipyard: `D:/Projects/LibUltraShip+Fast3D360/scratch/canonical-optimization`, branch `codex/shipyard-optimization`, origin `https://github.com/becaring/Shipyard.git`. It is a linked worktree of the canonical repository, not a separate implementation. Canonical `D:/Projects/becaring/shipyard` is outside writable roots.
- Actual older Xbox source/build: `D:/Projects/SoH360`; use its implementation, XDK flags and linked executable, not an upstream-only source comparison.
- Campaign root P: Modern `scratch/perf-campaign-20260928`. Run root R: Modern `scratch/xenia-profile-runs/campaign-20260928`.
- Ready-to-copy hardware folder: `D:/3Shipsty/1080p60-AB-20260929`. Each variant contains XEX and matching configuration. Existing installation/assets/save required.
- Delivered baseline XEX SHA256: `b7a1dbf791daf99adbba8ff9c352e1aa86c4af664326383db21802eeb47c58af`.
- Delivered candidate XEX SHA256: `41012ba8978e67d676cb7afa3b04069b048c787e9ee54a1ad8c7574a41a8fed9`.
- Both configurations retain normal audio, VSync, internal scale 1.5, 60 Hz interpolation, all presentations, no forced camera/autoload/RNG, and coarse frame timing only. They inherit enabled Portuguese mods and SohStats from the existing normal configuration; do not assume those features explain the disparity without comparison.

## Incorporated changes and their limits

The candidate uses 48-byte command records initialized directly in a bounded reusable POD buffer, replacing 72-byte temporary/copied records. It captures fog coefficients once per vertex context instead of per-vertex conversions and reads PPC rounding mode once per triangle instead of three times. Both builds disable interpreter detail sampling and native fine diagnostics separately from coarse cadence timing. Shared tiling continuation counts UP vertex payload/alignment separately from SDK command cursor with conservative reservations and viewport restoration.

Xenia checked 11,652 exact submitted presentation outputs across tree-facing Field, another Field entrance, and Kokiri; input checks had zero failures. This compares submitted floating-point vertex bits/draw ordering/counts, not a new full framebuffer pixel comparison. Fog tests cover signed coefficients and all rounding modes; cull tests cover exceptional/rounding cases. POD buffer tests cover growth, limits, allocation failures, reuse and native ABI. These are correctness facts, not performance success.

Final Xenia Field ABBA interpreter means were 8.588, 8.242, 8.583, 8.658 ms/update; whole-update periods 22.283, 21.567, 22.295, 22.072 ms. No robust throughput improvement established; hardware observation is unchanged. Raw cases: R `integrated-field-time-a1`, `-b1`, `-b2`, `-a2`; correctness cases start `integrated-` and results live P `update-stream-verify`.

**Build integration remains incomplete.** The delivered semantic/lane interpreter is an experimental linked overlay, not fully represented in the maintained production projection. Exact incorporated source snapshots and selection receipts are preserved in `performance/checkpoints/20260929`; this directory is not selected by the production project. P `integrated-candidate` retains EXE/map/objects/RSPs; P `fog-capture/allocation-overlays.json` closes the changed Interpreter layout across Fast3dWindow, Gui, ResolutionEditor and OTRGlobals. A fresh build must close that same allocation/header ABI. Never mix the new fog context header with old allocating or field-reading objects.

## Focused old/current comparison at stop

Latest valid old run: `D:/Projects/SoH360/scratch/performance/comparable-modern-20260929/old-field-tree-1080-coarse-final-4/application/soh360.log`. It accepted the migrated child save and verified scene 81, day 27307, internal1080/MSAA1/two tiles, authentic update rate3 and all three presentations. Actual tree camera/player coordinates are in startup evidence. It is not yet reconciled against the current run's complete workload/rendered features.

Last old settled report: logic/UI 2.607 ms/update; render excluding Present 3.189; Fast3D inclusive 2.537 across three calls; interpolation .170; Present 6.295. These scopes overlap: do not sum them. The failed `final-3` never started the guest and is excluded. Migration fixes include boolean-to-integer isMasterQuest and version/name conversion. Prepared old XEX SHA256 `182c20cfb53025dc2585f264954e0932eb6fb08e398b702fe886d47a1c998d5e`; verify preparation receipt before rerunning.

Verified differences/facts, without a completed causal throughput conclusion:

1. Delivered Modern explicitly clears shader-cache callbacks and reaches runtime D3DXCompileShader. Actual old run loaded 139 cache entries and had 33 hits, zero misses/compilations. P `integrated-candidate/linked-cache-null-proof.json` proves selection in the exact delivered XEX. This can concern transition hitches; it does not explain settled throughput and is not the lag fix.
2. Delivered baseline/candidate both select P `wait-budget/core.obj`, a diagnostic overlay. Even with nativeDetails=0, Draw executes two scope calls plus direct TLS save/restore; there are no TLS helper calls, active SDK timers/callbacks/atomics. The maintained selected production core differs only by those scratch profiling additions/equivalent braces and preserves tiling/cursor/HiZ/depth policies. Removing this overlay was proposed but **not built or measured**. Evidence: P `diagnostics-off/native-draw-selected.ppc.txt` and `native-core-compiled.ppc.txt`.
3. SDK default latency is one completed frame when D3DCREATE_BUFFER_2_FRAMES is absent; that matches old's explicit one-frame setting. No default queue-depth disparity established. SDK throttling can be deferred from Present into the next command segment's Direct3D call. Interpreter wall time may therefore contain previous-frame GPU/vblank backpressure. Do not label all interpreter time CPU computation or all Present time GPU duration.
4. Modern settings saving runs ConsoleVariable JSON serialization/unflatten/flatten validation/dump and durable filesystem flush synchronously on the submission owner. Actual old Mercury saveAsync queues an owned serialized snapshot, while synchronous save/reload waits. Older hardware logs contain isolated 131–166 ms gui_save_cvars spikes, but mostly tiny steady costs. No settings-worker implementation was written; this is not a settled throughput explanation.

Earlier actual hardware evidence P `hardware-returned-comparison.json` and `field-followup/hardware-return.json` is for earlier XEXs. It showed costly interpreter/update phases and Field tiling restarts. Preserve its provenance; do not claim it measures this candidate. Prior sparse exclusive elapsed probe selected only 15 complete update samples and had measurable observer overhead; it is insufficient to declare a worker strategy successful. User authorized operation-major batching and coarse independent worker preparation; no new worker architecture was implemented.

## Unincorporated work deliberately left dirty

- Modern `platform/shipyard/xenos/api.cpp`, `tools/shipyard/prepare_xenos.py`, and the cache assertion portion of `tools/shipyard/tests/test_xenos.py`: shader-cache/async cache-write wiring started immediately before stop. No current native compile, executable link, launch, or hardware validation. One existing shared cache-failure test passed. Do not ship this as validated.
- Selected Shipyard `sources/fast3d/vertex_transform.cpp/.h`: appended TransformPositionsDirect/Three/DirectProfiled. New shared contract fixture, Modern direct-geometry test runner and partial-store VMX model changes. 5,120 host equivalence/padding cases, negative control and native PPC compile passed, but no delivered executable uses these newly maintained names. Existing old function bodies remain byte-identical. Working baseline hashes include these additions; committed checkpoint baseline excludes them.
- No settings-persistence code was written. Read-only copies are P `compact-recording/integration/source-views`.
- Preserve unrelated preexisting PORTING_LEDGER, controller_routes fixture newline and Serena configuration changes. No reset, cleanup, archive, merge or whole-repository audit was performed.

## Operational constraints for an explicitly authorized resume

Use fixed read-only serena_modern/shipyard/smash for bounded source navigation, shipyard_nav for selected provenance and freshness. Coverage is partial. Refresh/restart after configuration changes; refresh returns semantic_restart_required, but no restart tool was available and initial_instructions was inactive. Do not infer absent callers from incomplete references.

Xenia desktop GPU execution needs `require_escalated`; sandboxed launches can stop before guest startup. Use existing bounded run.ps1 ownership (PID/start time and hidden launch); run only one GPU workload at a time, no heavy native build during timing. Xenia can validate output and iteration, not hardware acceptance. SDK xbdir reported no default Xbox configured. No owned process remains running at handoff.

The unfinished task is a causal, comparable actual-old/current slow-path comparison and an implementation that changes elapsed time through the complete authentic-update/presentation schedule. The comparison now has one valid old Field run, but attribution and a hardware throughput fix remain undone. Do not extend neutral micro-optimizations, substitute cache restoration for sustained60, or ask the user to choose the next optimization.
