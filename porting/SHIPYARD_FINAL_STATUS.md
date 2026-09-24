# Shipyard technical successor and ownership status

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
| Shipyard | `b5f33d8bc3108c7934f07e3cc630c1c49534bff9`; `baseline.json` SHA-256 `612aa6370d1de554408a6ac23245a182006d39c8164d0d75142e199544eefd08` | `python -m unittest discover -s tests -v` |
| Modern 3Shipsty | `21cf7af7625506a7a8c9bc3f5c208b0d499adf19` for all selected build inputs | `platform/shipyard/build/BUILD_FROM_SOURCE.md` |
| Smash360 | `e565b7e0ac63c41a0f7572e05c165f0d9f79e8fd` for all selected build inputs | `README.md`, Xbox from-source section |

The consumers lock the exact technical Shipyard revision and manifest. Modern
also pins 16 external Git archives; Smash pins 11. Their setup scripts verify
those inputs before generating source. The builds do not read SoH 4.0.5. A
separate documentation-only Shipyard publication-notice candidate,
`53b5dd93de9128b492ad30418848c48371538ebb`, carries the corrected notices
and R1 trace. Its `baseline.json` is byte-identical to the technical successor;
it has not been published or substituted into the consumer binary locks.

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

Shipyard's post-freeze hardening contains the diagnostics callback/payload
contracts and optional shader-cache allocation containment. Its 42 package
tests passed (`scratch/hardening-tests-final.log` in the Shipyard successor).
The three source-review findings are fixed in this identified successor, not
retroactively in the frozen baseline.

Modern's menu-exception successor regenerated from empty owned output (72
generated directories emptied, one non-owned item preserved), passed all 96
generation stages, and freshly compiled all 696 selected game C units. The
receipts are
`scratch/final-regeneration/receipt.json` and
`scratch/game-xdk/full/compile-report.json`. Its project tests passed 18/18,
its unit suite 101/101, the 864-case full-RSP Fast3D differential passed, and
the original-versus-projected real menu checks passed. Logs are
the earlier `scratch/hardening-project-tests.log`, `scratch/hardening-unit-tests.log`,
and `scratch/hardening-menu-tests.log` plus this successor's verification
command output. All eight object-clean XDK shards exited 0;
`scratch/project-xdk/complete-application-verification.json` verifies 1,844
fresh PPC objects, source/header hashes and machine type. The new link used
1,094 application objects and a 750-object archive; archive, linker and
`imagexex` exits are 0 in `scratch/link-integration/link-verification.json`.

Smash's successor empty-output receipt is
`scratch/final-preclean/20260924T085948Z/emptied.json` in the Smash successor
(39 owned outputs). Its 45 scripts/100 unittest cases passed in
`scratch/hardening-tests.log`. The fresh build compiled 486 game C units,
140 LibUltraShip C++ units and 112 application/platform C++ units, all PPC;
the archive and new XEX link passed in
`scratch/application-xdk/native/build/native-link-verification.json`.

| Exact successor XEX | SHA-256 | Bytes | Local candidate manifest |
| --- | --- | ---: | --- |
| Modern `scratch/hardening-candidates/3Shipsty.xex` | `4270f9eba1a53b3d8980b07938d71d3cb99f71be914bac241f4b453d7368b8f7` | 43,311,104 | `scratch/hardening-candidates/manifest.json` in Modern |
| Modern menu-exception successor `scratch/menu-exception-fix-candidates/3Shipsty.xex` | `b1fdc4c83aa878703f5723eda34c6ea099d41d70f3e618f38918c48bc825e00a` | 43,311,104 | `scratch/menu-exception-fix-candidates/manifest.json` in Modern |
| Smash `scratch/hardening-candidates/Smash360.xex` | `d8447f9fb103a312366aa51bcb2027b0dc36ea91068f929d882a31d94f8ed891` | 8,728,576 | `scratch/hardening-candidates/manifest.json` in Smash |

The earlier Modern manifest binds its clean-regeneration, compile, link,
resource, Xenia and exact-copy receipts. The new Modern manifest binds the
fresh regeneration, compile/link and Xenia receipts for source revision
`21cf7af` and records the inherited exact-copy audit as earlier ownership
evidence. All 406 inventoried Modern runtime resource files were rehashed
after the new Xenia run with zero mismatches; the staged XEX hash equals the
new candidate hash. Smash's candidate manifest binds its newly linked XEX and
two named resource archives. These local runtime staging directories are not
cleared distribution packages.

The earlier Modern `scratch/hardening-xenia/result.json` identifies its exact
XEX, emulator and runtime-log hashes. The maintainer reports OoT ran and worked
in that predecessor Xenia candidate. Its guest C++ exception warning also
appears in the frozen baseline log. The menu-exception successor fixes a
`WidgetOptions`/`ButtonOptions` fluent-return type mismatch: the Xbox-only
disabled button in `SohMenu::AddMenuSettings()` was stored as the wrong variant
alternative and `std::get<ButtonOptions>` threw. The exact source contract test
failed before the fix and passed afterward. The final candidate's fresh-profile
Xenia receipt is `scratch/menu-exception-fix-candidates/xenia-result.json`:
it reached `gui-ready`, `speech-ready` and `init-complete` with zero guest C++
throw events, connected a controller, created graphics pipelines and a global
save file. Visible gameplay, specific input actions, audible output and
save/reload were not independently observed for this new XEX. Smash
`scratch/hardening-xenia/result.json` records visible intro/tutorial and
attract-mode fighting render, audio stream initialization, a controller
connection, and 131 shader-cache entries reloaded; the maintainer confirmed
the successor Smash XEX worked in Xenia. Specific input actions, audible
output, save/reload and title shutdown are not claimed without observation.

Physical Xbox execution is the remaining technical acceptance boundary. Run
the new Modern menu-exception successor and the preserved Smash successor with
their manifest-identified local resource sets on a real Xbox; record startup
without Watson, menu navigation, controller response, visible gameplay/rendering,
audible audio, save/reload and shutdown for each artifact. Preserve the
candidate hashes before and after transfer. The screenshot of the earlier
`b24272` hardware build shows a first-chance exception after
`gui-windows-ready`; it does not establish whether this new XEX fixes real
hardware. Xenia results do not establish hardware behavior.

The Modern build driver now preflights all 675 local source-lock entries before
deleting generated outputs, checks scoped Git trust, and resumes interrupted
stages only when the source revision, stage options and prior log hashes match.
The documented edit cycle keeps generated outputs and existing PPC objects,
runs affected owner projections, and lets MSBuild rebuild changed source/header
dependents. The final object-clean compile above was one uninterrupted run
from the required empty-output state; the prior candidates and their XEXs were
not overwritten.

## Release gate and scope

The separate Shipyard publication-notice revision corrects `NOTICE.md` and
keeps the maintainer-scoped `LICENSE` plus all upstream notices. The maintainer
owns their original SoH360, 3Shipsty, Smash360 and Shipyard Xbox contributions
and confirms that becaring is their account; donor-tree movement alone is not
evidence of another author. R1 is closed for selected source/build inputs by
`provenance/FAST3D_R1_LINEAGE.md` in that notice revision. The historical
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
