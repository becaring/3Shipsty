# Shipyard queue-completion successor and ownership status

This records the verified post-freeze technical successor. The original
checkpoints and XEXs remain preserved. The ownership decisions in
`SHIPYARD_REMAINING_OWNERSHIP_66959D6.md` remain the design authority. The
66959d6 checkpoint and earlier migration, recovery, and handoff reports are
historical evidence, not competing descriptions of this candidate. Local
source/build acceptance does not grant permission to publish source or
distribute the game, SDK, or asset package.

## Source authority

| Checkout | Technical successor source authority | Rebuild entry point |
| --- | --- | --- |
| Shipyard | Branch `codex/shipyard-queue-completion`, commit `7ab5420bee2ae28e4c5b65813c0fc374150b3915`, API 6; `baseline.json` SHA-256 `6f4df44e0e52602ffc95b2e88d5bb0e05f6066fa162a600c434776426cf19327` | `README.md`, Test environments |
| Modern 3Shipsty | Branch `codex/shipyard-hardening`, selected build-input commit `159dddf03c78069741625d0c0fc3e65899556b9b` | `platform/shipyard/build/BUILD_FROM_SOURCE.md` |
| Smash360 | Branch `codex/shipyard-hardening`, selected build-input commit `52b1a825fb33ecce9b3b60c7d7aaef34a0961f6d` | `README.md`, Xbox from-source section |

Both `platform-base.lock.json` files resolve to that same exact Shipyard commit,
API and baseline digest. Modern also pins 16 external Git archives; Smash pins
11. Their setup scripts verify those inputs before generating source. The
builds do not read SoH 4.0.5. The original freeze `e1e71554...`, hardening
`b5f33d8b...`, and publication-notice `53b5dd93...` remain preserved history.
The selected successor contains the hardened production files and the corrected
notices and closed R1 trace from the publication-notice revision.

## Canonical ownership

| Responsibility | Canonical implementation | Consumer-owned boundary |
| --- | --- | --- |
| Xenos rendering, shader lowering/provider, presentation pacing, ImGui frame/renderer, physical input, PCM/audio pool | Shipyard `sources/{xenos,graphics,presentation,imgui,input,audio}` | Backend callbacks, title paths, window/device order, resources and GUI lifecycle |
| Native async, clock, filesystem, storage, networking, archive, entropy, diagnostics queue | Shipyard `sources/{async,clock,filesystem,storage,network,libzip,entropy,diagnostics}` | Storage identity, XNet lifetime, sinks, worker placement, errors and shutdown order |
| Immutable launch environment | Shipyard `sources/environment` | File path, initialization time, absence/error policy and logger binding |
| Fast3D numeric, projection, light color, material value, shader metadata and shade caches; source dedup, packing, triangle and dispatch mechanics | Shipyard `sources/fast3d` and `python/xbox360_platform` | Complete keys, formulas, capacity, layout, vertex indexing, cache lifetime, observations and microcode/version behavior |
| Prism, spdlog/fmt, JSON, C/C++ syntax, codec/StormLib and build projections | Shipyard shared projectors and direct platform sources where the pinned versions agree | Dependency acquisition, formatter/conversion ABI, resource builder, features and source/version locks |

Shared caches are Shipyard features. Modern consumes the common material,
projection/cull and shader-metadata mechanisms; Smash consumes those and the
light-color, combiner-value and optional directional shade mechanisms where its
current lighting/constant pipeline has the corresponding value boundary. Modern
retains its integer per-light accumulation and per-vertex constant publication;
replacing either with Smash's float/precomputed values would alter authoritative
arithmetic or observation order. The reusable cache implementation itself is
not copied into Smash. Near-plane rejection, packing inventories, triangle
traits, color/depth redirects, second-tile choice and distinct Round operations
remain explicit version contracts.

## Remaining local Xbox modules

Every active local module belongs to one of these explicit categories. A
directory list denotes all modules in that directory; no unresolved generic
implementation is accepted by this inventory.

| Consumer and category | Local modules | Why they remain local |
| --- | --- | --- |
| Modern adapters | `async`, `audio`, `binary`, `build`, `codecs`, `configuration`, `context`, `crt`, `fast3d`, `filesystem`, `gfxd`, `graphics`, `gui`, `imgui`, `input`, `json`, `libultra`, `libzip`, `logging`, `native-imgui`, `network`, `presentation`, `prism`, `resources`, `ship-utils`, `speech`, `thread-pool`, `vorbis`, `window`, `xenos` under `platform/shipyard` | Pin upstream inputs, provide title services and callbacks, or select version-specific compiler/ABI behavior around directly consumed Shipyard code. ResourceManager and archive interpretation remain version policy. |
| Modern application/version policy | `app-services`, `application`, `application-core`, `application-editors`, `application-extras`, `application-gui`, `application-windows`, `audio-collection`, `console-variables`, `custom-message`, `enhancements`, `fast-resources`, `game`, `game-interactor`, `gameplay-features`, `gui-resources`, `interpolation`, `legacy-save`, `network-app`, `object-extension`, `randomizer`, `randomizer-application`, `randomizer-content`, `randomizer-context`, `randomizer-data`, `randomizer-dungeons`, `randomizer-generation`, `randomizer-hints`, `randomizer-item`, `randomizer-logic`, `randomizer-options`, `randomizer-regions`, `randomizer-settings`, `resource-shutdown`, `save-manager`, `save-storage`, `savestates`, `soh-input-editor`, `soh-menus`, `soh-resources`, `soh-ui` under `platform/shipyard` | Current SoH application source, content, UI, save and resource semantics. Xbox projection is constrained by pinned Modern source; it is not an alternate platform implementation. |
| Smash adapters | `audio`, `endian`, `fast3d`, `game-compat`, `graphics`, `imgui`, `input`, `runtime`; and `cpp-compat/{async,binary,chrono,crt,fast3d,filesystem,format,json,libultra,libzip,logging,prism,thread-pool,value-types}` under `platform/xbox360` | BattleShip interfaces, direct Shipyard calls, pinned compiler/ABI projection, title sinks, and explicit Fast3D policy. The diagnostics adapter compiles Shipyard's queue directly; no runtime donor implementation is extracted. |
| Smash application/version policy | `cpp-compat/{config,context,controllers,fast-resources,gui,gui-widgets,hires,input-editor,port,postprocess,resources,startup}` under `platform/xbox360` | BattleShip configuration, resource, startup, GUI and game policy; pinned version semantics differ from Modern. |

The successor exact-copy scan covers 116 canonical Shipyard code files, 468
Modern active files, 158 Smash active files, 2,218 Modern generated files, and
390 Smash generated files; it found zero exact copies. Its receipt is
`scratch/final-audit/exact-copies.json` in the Modern successor. Project
manifests and full PPC compile receipts establish direct source and header
ownership. The source-generation/project suites check the shadow and rewrite
paths; exact hashes alone are not a semantic derivation test.

## Verification and exact artifacts

The diagnostics overlap was reproduced with a real Windows event/barrier test:
the second external `shutdown()` returned while `worker_stopped` was blocked.
That test failed before the source change and passes afterward. Every supported
external shutdown now waits for worker completion, including the final callback.
A worker callback may request shutdown without self-joining; an external
shutdown must complete before the callback context or queue is destroyed.
Concurrent destruction of the Queue object is not part of this contract.
Existing callback-exception and immutable-payload tests remain in the suite.
Shipyard's full Windows suite passed 43/43. Its `README.md` now separates
Python/Git-only checks, Windows/MSVC host C++ tests with `vswhere` discovery,
and the coordinate test requiring the Xbox compiler/XDK. Missing prerequisites
mean that coverage was not run; the Python/Git-only subset was 29/29 on this
Windows host. The review's Linux run covered 27 portable checks and did not
execute the Windows/XDK tests.

Modern's prior whole-tree empty-owned-output receipt is preserved at
`scratch/queue-followup-candidates/prior-empty-regeneration-receipt.json`
(SHA-256 `d7e7802e0e31acdac12c8e5a24bd589ed76aa2e793f7bcef58d5a0cee256f655`).
This pass did **not** rerun an empty-output regeneration. A broad regeneration
was stopped at stage 86 because its `--build` stages were unnecessary for the
queue-only lock change. Targeted owner scripts refreshed the remaining selected
recipes. The project gate passed 18/18 and the Modern unit suite 101/101;
the latter includes the 864-case full-RSP Fast3D differential. The selected
1,844-unit project contains no diagnostics queue source and no old Shipyard
absolute include option.

Modern's `scratch/queue-followup-candidates/reuse-verification.json` binds the
prior full PPC compile receipt to the new manifest: 1,843 unchanged PPC objects
were rehashed and one projected eSpeak object was compiled fresh. Its source
diff consists of two `#line` worktree paths. The 1,005-header closure was
rechecked; two generated JSON headers changed only a `#line` worktree path,
with the previous hashes reproduced by reversing that path. This is a verified
reuse/relink receipt, **not** a new full 1,844-object compile. The fresh archive,
link and `imagexex` steps all exited 0, using 1,094 application objects and
750 archive objects. `scratch/queue-followup-candidates/runtime-integrity.json`
checks 406 copied resource files with zero mismatches and an identical staged
XEX hash.

Smash's earlier 39-output empty-owned-state regeneration remains preserved as
historical evidence; this pass reran the affected runtime/application owners.
Its 45 scripts passed 100 unittest cases. The fresh PPC build compiled 486
game C units, 140 LibUltraShip units and 112 application/platform units. Its
project manifest selects Shipyard `sources/diagnostics/queue.cpp` directly,
with no local diagnostics implementation shadow. The new XEX, resource archives,
project items, object receipts and link verification are together in
`scratch/queue-followup-candidates` in the Smash successor.

| Current local candidate | SHA-256 | Bytes | Manifest |
| --- | --- | ---: | --- |
| Modern `scratch/queue-followup-candidates/3Shipsty.xex` | `86504a1422d36a3c0a9d98849cb13315d63f06cc919ad0f8355ce9db3eaac272` | 43,311,104 | Modern `scratch/queue-followup-candidates/manifest.json` |
| Smash `scratch/queue-followup-candidates/Smash360.xex` | `4c14a42f4d4118f7d7a626c01ba4c35572cff92eb3fdc2a19b11d34db7b325cd` | 8,728,576 | Smash `scratch/queue-followup-candidates/manifest.json` |

The earlier `scratch/hardening-candidates` XEXs and Modern's
`scratch/menu-exception-fix-candidates` XEX are preserved, not overwritten or
retroactively relabeled. Exact-candidate Xenia functional acceptance is still
unverified in this tool session. The new Smash XEX and its known-good frozen
control both reached only Xenia's configuration log; neither reached memory
setup. A visible launch opened no window on the maintainer's desktop. The new
Modern XEX was not observed in Xenia in an interactive desktop session.
Earlier Xenia observations apply only to their manifest-identified older XEXs.
No exact new candidate has run on a physical Xbox from this environment.

For functional/hardware acceptance, verify each manifest hash before and after
transfer, then exercise boot without Watson, visible rendering, menu navigation,
controller input, gameplay, audible audio, save/reload and title shutdown on
both exact XEXs with their manifest-identified resources. Record any first-
chance exception on the new Modern XEX separately from the older hardware
screenshot. Xenia cannot establish physical hardware behavior.

## Release gate and scope

The selected Shipyard successor retains the corrected `NOTICE.md`, the
maintainer-scoped `LICENSE`, and all upstream notices. The maintainer
owns their original SoH360, 3Shipsty, Smash360 and Shipyard Xbox contributions
and confirms that becaring is their account; donor-tree movement alone is not
evidence of another author. R1 is closed for selected source/build inputs by
`provenance/FAST3D_R1_LINEAGE.md` in the selected Shipyard revision. The historical
Re60 commit `23eb15e6bee171d6c1c2bd38350d222bedff0d4c` carries the full
asset-exception notice. The older SoH360 source-only notice, that later
conditional notice, and the active consumers' pinned MIT Fast3D notices remain
distinct and retained; no notice is assigned by donor folder name or by a
low exact-line match count.

The remaining publication/distribution gates are specific: R2 is GPL-3.0-or-
later eSpeak NG statically linked into the complete Modern XEX, requiring
whole-program Corresponding Source and compatibility analysis under sections
5 and 6, including local changes and build/projection scripts; any Xbox SDK
System Library exception requires component-specific analysis. R3 is rights
and SDK terms for the exact XEX/package assets and support files. R5 is the
upstream game/decomp source scope and terms, separate from the maintainer's
original Xbox contributions. An eSpeak-only source bundle does not resolve
R2. Standalone Shipyard's original MIT grant is separate. No repository or
binary has been published or pushed.

ResourceManager/archive semantics beyond an agreed bounded-read contract,
window/GUI/resource lifecycle, and genuinely different Fast3D formulas remain
consumer-owned. MM, Star Fox, Paper Mario, 364, SoH 4.0.5 and on-device ROM
extraction are outside this phase.
