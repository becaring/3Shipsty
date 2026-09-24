# Shipyard technical freeze and ownership status

This is the current status document for the active Modern 3Shipsty and
Smash360 Xbox 360 consumers. The ownership decisions in
`SHIPYARD_REMAINING_OWNERSHIP_66959D6.md` remain the design authority. The
66959d6 checkpoint and earlier migration, recovery, and handoff reports are
historical evidence, not competing descriptions of the final candidate.

## Source authority

| Checkout | Frozen source authority | Rebuild entry point |
| --- | --- | --- |
| Shipyard | `e1e71554d9b64ff99165e68a1e2f25c66ca61915`; `baseline.json` SHA-256 `d6889f2495b3289c066942ee37c676f0fc47330c7153effe8c6db0a83ea75fad` | `python -m unittest discover -s tests -v` |
| Modern 3Shipsty | This document's Git commit on `shipyard/xbox360-9.2.3`; last implementation commit `c341ac8d1537e3af42906369942635f1917ee024` | `platform/shipyard/build/BUILD_FROM_SOURCE.md` |
| Smash360 | `a07e0db3adb9f3ed82561a98f8a4ea1cd7ee0c6e` on `shipyard/completion` | `README.md`, Xbox from-source section |

The consumers lock the exact Shipyard revision and manifest. Modern also pins
16 external Git archives; Smash pins 11. Their setup scripts verify those
inputs before generating source. The builds do not read SoH 4.0.5.

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

The active consumer trees contain no exact physical copies of the 116 Shipyard
implementation files scanned. The final generated-source audit is recorded in
`scratch/final-audit/exact-copies.json` in Modern; it covers both consumers.
Project manifests and full PPC compile receipts establish direct source and
header ownership. Search the active generators and final manifests when
reviewing semantic shadows; an exact-hash scan alone cannot prove equivalence.

## Verification and exact artifacts

Modern's empty-owned-output run removed only 77 inventoried outputs, passed
all 96 generator stages, and freshly compiled all 696 selected game C units.
The receipt is `scratch/final-regeneration/receipt.json`; the game compiler
receipt is `scratch/game-xdk/full/compile-report.json`. Modern's project test
log is `scratch/final-modern-project-tests.log` (18 cases), its unit test log is
`scratch/final-modern-unit-tests.log` (96 cases), and its real menu differential
is `scratch/final-modern-menu-tests.log`. Shipyard's 41 package tests are in
`scratch/shipyard-final-tests.log`.

Smash's empty-output receipt is
`D:/Projects/Smash360/scratch/final-preclean/20260924T040132Z/emptied.json`
(39 owned outputs). Its complete build and 45-script/100-case test logs are
`scratch/final-smash-build.log` and `scratch/final-smash-tests.log` in that
checkout. The fresh compile covers 486 game C inputs and 140 LibUltraShip plus
112 application/platform PPC C++ units. Its linked XEX and required resource
packages are frozen under `scratch/final-candidates/` in Smash.

The exact Modern build is the XEX named by
`scratch/link-integration/link-verification.json` and preserved under
`scratch/final-candidates/3Shipsty.xex`. The receipt records source, header,
PPC object, archive and linker input identities. The exact Smash XEX is
`D:/Projects/Smash360/scratch/final-candidates/Smash360.xex`; its SHA-256 is
`399dfd51e16511c689a0cca17bcd0980799b079eecfed8ba3531f0acafee50a2`.
Read the Modern link receipt for its exact hash after rebuilding. Never use the
earlier 66959d6 XEXs as final evidence.

Xenia receipts are under each checkout's `scratch/final-xenia/`. They record
the emulator and exact XEX hashes, command and runtime log. Claims about menu,
gameplay, save, input, audio and rendering are limited to observed entries in
those logs. Xenia execution does not establish physical Xbox behavior.

Physical hardware execution is outstanding from this environment. Test the
same frozen XEX files with their exact runtime resource packages on a real
Xbox before describing either artifact as hardware validated.

## Release gate and scope

Shipyard's `NOTICE.md` identifies unresolved authorship and redistribution
permission for the donor-derived Xbox adaptations, including Fast3D's distinct
binary restriction. Existing upstream notices remain in place. This is a
publication blocker, not a reason to label source migration incomplete or to
relicense upstream code. No repository has been pushed or published.

ResourceManager/archive semantics beyond an agreed bounded-read contract,
window/GUI/resource lifecycle, and genuinely different Fast3D formulas remain
consumer-owned. MM, Star Fox, Paper Mario, 364, SoH 4.0.5 and on-device ROM
extraction are outside this phase.
