# OoT: main integration, 2026-09-29

Reviewed range: `4a4f5002813ff3cfcd207c2658e568ebf60b2fc3..ec84c1581922a690097fa327e46dc3c3fec9bc5f`.

The recorded builds and tests belong to the range endpoint above. The
documentation-only follow-up does not replace the binary build identity.

Bring the completed Xbox OoT development history onto main while retaining
the main branch's documentation and porting ledger. The range includes earlier
incorporated runtime work and historical performance checkpoints as well as the
subsequent source-review corrections. Checkpoint files are preserved evidence;
their presence does not select an experimental runtime configuration.

The source-review integration removes the redundant pre-ImportTexture batch
flush and preserves the necessary flush before shader creation. It brings in
pipeline mutation certification and reload restoration, prepared UV axes and
clamp bounds, numeric conversion and deferred lighting/fog changes, material-key
rounding-mode identity, generation-aware texture retirement, non-texture resource
resolution, and service-thread placement. Projector fixtures were updated with
the corresponding production-source changes.

Presentation changes select the asynchronous Xenos swap chain and defer the
OoT game depth read through the projected application/game callback schedule.
The resource-manager changes serialize O2r zip LoadFile/WriteFile and protect
cache publication, NotFound stores, and unloads with the resource-manager mutex.
The later revert restores directory/object/scene prefetch while retaining those
locks; the temporary prefetch-disable commit is not the final behavior.

The shader integration selects the resident program-keyed v2 pack, probes packed
program code before build/lower/compile fallback, wires the shader worker and
appendable cache, and retains official-archive pack generation/parity tooling.
The staged v2 pack contains 4,409 keys, 8,818 programs and 7,627 unique blobs,
with no reported lowering, compilation or missing-code failures.

Pin platform-base.lock.json to Shipyard 0f446c26719bb47cd0c73fd2109f0272a99cd7bd
and its selections/3Shipsty base, with the recomputed baseline digest. Preserve
fixed read-only navigation tools and add named-selection Git-root handling.
Retain unfinished direct-geometry test scaffolding on the local
codex/preserved-direct-geometry-tests branch; it is not part of this production
main integration. No branches, worktrees or unrelated user files were deleted.

Validation at the recorded source revision: regenerate the affected application,
game, resource, interpreter and Xenos projections; verify and compile all 1,846
PPC objects; link the Release XEX successfully. Focused deferred-depth,
presentation-depth, application-core, game-projection, shader-pack, Xenos,
texture-batch, TRI2 pair/pipeline, deferred-lighting and navigation checks pass.
Shared Shipyard baseline and selection-contract checks also pass.

Known exception: test_application.py has three failing assertions against the
existing generated-helper inventory, startup-fault path and application directory.
They were reported and left unchanged; this is not a claim that every test passes.

With a signed-in HOP profile, isolated Xenia logs show graphics/audio return,
v2 shader-pack verification and scene initialization. The staged XEX is
Main-Integration-20260929/OoT/3Shipsty.xex, SHA256
3b8660b6db247efa77eda16e3fe8264668c23199f8dcae4eb1a7f9870775c499.
The matching build-receipt.json records the tested revisions and asset hashes.
This is startup/build evidence, not verification of sustained hardware 1080p60.

## Incorporated commits

```text
ec84c1581 tools: retain fixed navigation and support consolidated selections
5530a601d integration: merge completed OoT development and preserve porting ledger
6a7a81153 build: pin OoT selection on consolidated Shipyard main
aee09b271 docs: retain reported boot recovery evidence
63c9045c1 Select v2 resident shader pack for OoT
f10647c72 Revert "Disable startup resource prefetch after collision-header crash"
c41e8efec Serialize O2r zip access and resource cache publication
90a212e34 Disable startup resource prefetch after collision-header crash
6b718c05a Integrate OoT shader pack and resource prefetch projections
7e5d61b28 Select reviewed presentation scheduling and deferred depth changes
6d37d8c65 Integrate reviewed pipeline certification and production source fixes
04203ab9a Integrate reviewed texture retirement and pipeline restoration adapters
92bb48ac2 Integrate reviewed pipeline certificates and prepared vertex packing
a2ee90cc5 Integrate Claude reviewed Xbox production source corrections
5f4305e38 Preserve incorporated Xbox performance work and failed hardware checkpoint
af1a07df9 Adopt framebuffer and configuration savings with certified full fills
ec9fe586f Select optimized Shipyard and eliminate print table allocations
0278fa629 Reduce baseline interpreter work and expose scene costs
8bba84624 Select Shipyard shard layout correction
3ff1cbc02 Compute forest dust camera basis once per update
34b0dfa5e Cull invisible forest effects and reuse billboard rotation trig
1493f9814 Profile outdoor actor drawing by callback and effects
99a379bb1 Skip intermediate depth resolves and pack TRI2 columns
72dada52c Skip deferred vertex attributes and certify archive texture hits
33470c549 Reuse TRI2 packed vertices and texture hits with present phase diagnostics
d33a7c70c Measure sampled VMX setup and vertex loop phases
f454f6c1f Reuse bound operation index during interpolation replay
84e17d7ac Profile present intervals by replay lane
f5b3f0572 Add opt-in exact tile-state dedup trial
b2fe27918 Add opt-in vertex hash phase sampling
b10c3ca04 Select measured texture route after cache A/B
2e15539d6 Add opt-in sampled TRI2 phase profiling
af83c6274 Adopt lower-cost archive texture ownership checks
fb45f34af Adopt archive-epoch texture route and profiler projection
22083fb24 Profile texture hash routes from owning-cache entry
a005269f2 Track archive hash mapping changes for texture cache validation
4da39d835 Profile texture hash route and expose tile draw trial
7ff5ddab8 Wire opt-in tiling guard trial and counters
af0beff27 Report whole tiling bracket occupancy in Modern profile
f826471e4 Add opt-in full color clear profile for game frames
823d83756 Report measured native ring writes beside tiling guard
a3cf26aaf Profile 1080 tile eligibility and cold triangle phases
3eec14486 Attribute presentation spikes and deferred context scans
f42cdad11 Remove low-hit vertex normal cache
6a84fb54b Reuse vertex normal lighting and profile present cadence
1f796647c Keep frame profiler contract aligned with color counters
507ebc5f1 Select owned texture cache and add uncapped Xenia profiling
dbe2782ed Pool interpolation recording storage and index operations
8451dfa3c modern: discard presentation color after GUI
dfccc5e8e Reuse pipeline certificate within TRI2 pairs
794c9f92a Select tiled ring telemetry and report native counters
5d5f76ead Count early depth fences and emitted dust in frame profile
c02570444 Profile emitted soft dust draws in projected game C
ea678b0c1 Select early depth fence Shipyard revision
a42fc951f Profile game update and triangle pipeline reuse
e0a944a34 Reuse owned textures across replay and discard presentation depth
eb0295efe Defer lit and fog attributes until visible triangles
3c798a856 Profile owned texture path cache in Modern
34b8621ba Profile depth readback in Modern
ae2bd303b Discard intermediate render depth in Modern
d4522b430 Use owned per-render texture resolution cache
c3317299f perf(resources): adopt allocation-free alternate cache resolution
8e32de6d4 fix(interpolation): transfer recording ownership on Xbox
d474999b0 perf(profile): expose resource resolution and recording rotation
9586672f3 perf: adopt shared runtime reductions and reuse interpolation lookups
ad7a9622c perf(modern): adopt resource lookup and triangle processing reductions
3a2fb1e99 perf(modern): measure interpreter CPU and resource handoff costs
286476741 test(ui): exercise resolution buttons and renderer updates
c21555f03 fix(config): persist settings and presets in raw game folders
895a88aed fix(ui): keep input overlay draggable and persist placement
396467f9b fix(ui): enable resolution scale increment controls
65c198cc5 fix(input): adopt Shipyard Xbox text entry
cee9dba9d perf(modern): avoid creating empty hook dispatch groups
9814f2691 perf(modern): include native renderer counters in frame reports
37ab23b81 build(modern): adopt reviewed Shipyard frame optimizations
1267bb5f5 perf(modern): add opt-in coarse frame timing reports
81f580496 perf(modern): reserve the scheduled interpolation batch
```
