# Shipyard recovery checkpoint — 2026-09-23

Later update: the stale recipe gate, fresh complete build/link receipts and source-state preservation are now closed in [the 66959d6 integration checkpoint](SHIPYARD_66959D6_CHECKPOINT.md). This document retains the intake assessment and its historical stopping point.

This is the recovered state from filesystem, Git, generated manifests, build receipts and fresh focused tests at approximately 18:15 Pacific. It supersedes the current-state summaries in SHIPYARD_OWNERSHIP.md, SHIPYARD_MIGRATION_REPORT.md and POST_SHIPYARD_HANDOFF.md; their historical evidence remains useful. This recovery did not implement another migration, commit changes, run a full application build, or execute an XEX.

The source work is recoverable and substantially migrated. The latest focused integration works in both consumers. Platform separation is not complete, and the current source state is not yet verified as a reproducible repository deliverable. My planning estimate is about 80% of the identified source-boundary migration, with roughly 15–25% still open. This is an engineering estimate, not a percentage derived from file or translation-unit counts. Release readiness is a separate set of unfinished gates.

| Checkout | Recovered state |
| --- | --- |
| Shipyard, `D:/Projects/LibUltraShip+Fast3D360` | Clean Git checkout on `codex/shipyard-platform-separation`, HEAD `66959d6`. Baseline covers 108 files. No Git remote is configured. |
| Modern consumer, `D:/Projects/3Shipsty9.x` | Branch `shipyard/xbox360-9.2.3`, HEAD `e3d1a098d`. At intake: 131 modified tracked files, 57 deleted tracked files, 20 untracked files; no staged changes. The migration is largely uncommitted here. |
| Smash consumer, `D:/Projects/Smash360` | Source and build tree exists, but this directory is not a Git repository. Its consumer changes are not protected by a commit in this directory. |
| Active locks | Both pin `66959d6`, API version 5, baseline SHA-256 `16ef0bb550dbddd5dbf0ee13537cb3f9712b590d17aa2f6ff45246f097f0b1ca`. Fresh consumer tests successfully resolve and verify the package. |

The pre-existing untracked `3Shipsty`, `Singularity.apk` and `djipi_s_3ds_experience_tot_fix.zip` are not migration source. Preserve them and exclude them from any broad source commit. Historical SoH360 remains a reference.

The previous task, “Bring up Ship of Harkinian runtime,” is not loaded, and its latest turns are marked interrupted. No Python, MSBuild, cl, link or Xenia process was running at the recovery process check. There is no live build to wait for. The available records establish interrupted work and stale receipts; they do not establish why the agent stopped responding.

The work completed after the older 70–80% report is real:

| Shared commit | Change |
| --- | --- |
| `81ff6c7` | Shared Fast3D opcode-table lowering. |
| `b4a5bf9` | Shared triangle cull/emission split transformation. |
| `7db50f2` | Per-slot native texture/sampler binding tracker, including alias correction. |
| `496b134` | Triangle certificate relocated into Shipyard. |
| `2e37cb3` | Shared C++ member-default extraction. |
| `6a7f858` | Version traits for the triangle certificate. |
| `66959d6` | Shared native-call certificate invalidation transformation. |

Modern's current uncommitted adapter now consumes the triangle certificate too; the ownership report's claim that only Smash uses it is stale. Modern's local resource variant has also been removed in favor of the shared value type. Do not redo these moves.

General inventory of physical Shipyard ownership:

| Area | Already moved |
| --- | --- |
| Rendering | Xenos core/framebuffer mechanics, shader lowering and provider orchestration, optional disk shader cache, presentation surface and pacing. |
| GUI and input | ImGui renderer/frame mechanics and gamepad bindings; physical controller and XInput implementations. |
| Audio | XAudio2 sink, PCM pool and layout interface. |
| Async and synchronization | Native synchronization/futures, optional detached lifetime, BS thread-pool projection, atomic operations and memory-order policies. |
| Storage and system services | Filesystem, XContent device/selector, atomic file writer, clocks/N64 timing, timer registry, CRT formatting and float helpers. |
| Optional services | Network transport/flag, shader-write worker, speech data boundary/queue, finite waits and address-gap arithmetic. |
| Serialization and compatibility | JSON backend and pinned generators/inputs, binarytools compatibility, Prism compatibility, common/optional/variant value types and variant generator, libzip native boundary/projection. |
| Fast3D kernels | Vertex transform, guarded clip/quantization, unit-color/value initialization, command stack, dispatch ownership, optional shade cache, texture binding tracker and triangle certificate. |
| Source transformations and build support | Vertex stream, C89, C++ syntax/member defaults, opcode tables, triangle splitting/invalidation, shared XDK settings, parallel compilation, object/header receipts and lock verification. |
| Small reusable helpers | UI scalar/color math and VMX load support. |

The modern generated application manifest selects 26 physical Shipyard translation units; Smash's application/LUS manifest selects 22. Twenty paths are common, six are modern-only in these inventories, and two are Smash-only. Shared headers, generators and separately built archive libraries are outside those counts. They do not measure whole-platform completion. Game policy, version-specific layouts and resource semantics should remain consumer adapters where appropriate.

Fresh recovery validation:

| Check | Result |
| --- | --- |
| Shipyard package suite | 25/25 passed, including timer re-entry, default flag state, shader-worker ownership/failure, atomic-file path behavior, sampler alias and invalidation. |
| Modern opcode/triangle ownership, triangle key/body preservation and resource generation | 14/14 passed. |
| Modern generated-project gate | 17/18 passed; `test_compile_contract` failed on the obsolete local JSON include option. |
| Smash Fast3D preparation contracts | 10/10 passed. |
| Smash platform-base/project contracts | 5/5 passed. |
| Smash triangle reconciliation | 4/4 passed, including 461 key checks and 8,233 extracted reconciliation steps. |
| Smash texture bindings | 2/2 passed, including 133,152 cache/import mutation steps. |
| Modern JSON generation/reproducibility | 12/12 passed. This is not a rerun of the full JSON behavioral differential. |
| Modern resource variant | Original/projected host differential and real PPC instantiation passed. |
| Both actual generated Fast3D interpreter TUs | Fresh XDK compilation passed; both objects have PPC machine `0x1f2`. `/showIncludes` resolves both texture_bindings.h and triangle_pipeline.h from the same physical Shipyard directory. |

Total: 89 passing unittest cases and one failing case across the selected suites, plus the separate variant and interpreter compile checks. This is focused recovery coverage, not the entire consumer test inventory. `git diff --check` also passed. Captured test output, interpreter compile commands and logs are under `scratch/recovery-2026-09-23/`; the new interpreter object outputs are isolated there.

The exact integration stopping point:

1. Modern's project gate still sees `/I$(ShipyardRoot)/platform/shipyard/json/include`. A fresh filesystem inventory found 46 of 85 `scratch/**/build.json` files naming that obsolete path; 419 rows of the existing application manifest inherit it. The shared JSON include is already selected earlier, but the source/recipe cleanup gate is genuinely failing.
2. Earlier full builds (`layout-c42aa851a3d98504` and `layout-d452aea6820daecf`) failed because generated resource factories still called the removed `Shipyard::Resources::get`. Current generated DisplayListFactory.cpp uses `xbox_compat::get`. The latest layout (`layout-a6b557dd9a227d7f`) has eight shard logs with no compiler-error lines, but no new completed compile receipt or link. This does not prove a successful full build.
3. Modern's `complete-application-verification.json` is absent. The remaining shared `compile-receipt.json` reports an older failure. Its last linked XEX still hashes to `256b7bd0f424952a3eac6818bc28bc22f1407dcf5d3acbc838d3b8e053c9cc75` and has a 16:39 timestamp. Its link receipt lists 1,094 application plus 750 archive objects, and `runtime_executed: false`. That XEX predates the current certificate/resource-variant state.
4. Smash's saved compile receipts report 140 LUS and 111 application sources, all shards successful. Its saved XEX matches `775d5ba204f9edd32c42ffeec33e26e0cfc9bb6cfcc88329d3a33573eb358588`. However, rechecking both receipts' header hashes finds the now-deleted staged `cpp-compat/fast3d/triangle_pipeline.h`. These successful receipts are stale for the current migration, even though recorded source hashes still match.

Remaining work is concentrated in these packages:

| Work package | Actual remaining obligation |
| --- | --- |
| Finish Fast3D ownership classification | Audit remaining local culling, lighting, vertex/cache, material/combiner and packing projections. Smash still has `cull_projection.h`, `light_batch.h`, `vertex_bytes.h`, `vertex_lighting.h`, `vertex_select.h`, and multiple local projection modules. Some are legitimate version adapters; do not move them blindly or count them as completed without classification. |
| Runtime diagnostics and other adapters | Smash's `prepare_runtime_xdk.py` still extracts a diagnostic worker from the pinned donor `platform.cpp` and rewrites SoH names. Presentation/window lifecycle, remaining Prism builder lowering, logging/entropy and codec/resource shims still need generic-versus-consumer classification. |
| Close generated-state integration | Regenerate obsolete subsystem recipes from their owning scripts, eliminate include shadows, pass the current project gate, finish both full compiles/links with fresh source/header receipts, then prove complete regeneration from empty owned outputs. Partial Fast3D/JSON clean-generation checks are already present; they are not a whole-tree clean build. |
| Close behavioral contracts | Preserve existing JSON, future/atomic and value-type tests. The modern JSON record still lists five unsupported general upstream forms (ADL, macro conversion, ordinary/ordered initializer lists, cross-DOM conversion). Determine which are explicitly projected at reached consumer callsites and document scope; do not claim full nlohmann equivalence. Modern triangle reconciliation still has narrower host evidence than Smash's extracted differential. |
| Make the repository deliverable | Checkpoint the consumer changes, preserve Smash's source state in version control, reconcile stale reports, and provide an actual from-source setup/build entry point with locked dependencies. Shipyard's NOTICE.md still marks provenance/redistribution grants unresolved; publication requires resolving that recorded gate. |
| Validate final runtime | Run exact final XEXs in Xenia and on hardware. Existing pre-migration gameplay/save/audio observations remain historical evidence; neither current migrated consumer has new runtime/hardware proof. |

Technical repo readiness is therefore blocked even if the remaining source extraction is around one fifth of the work. This is several substantive integration/ownership packages, not merely a final commit. A calendar estimate would be low confidence until the whole-tree clean build is exercised and the remaining Fast3D/diagnostic adapter decisions are bounded. Public release additionally has the repository's recorded provenance gate.

Resume with the stale JSON recipe gate and completion of the current full build/link receipts. Preserve and reuse the now-passing triangle, texture-binding, member-default and resource-variant work. Then close the remaining ownership packages and whole-tree clean-build gate. Do not restart the migration or offer either historical XEX as a current hardware candidate.

Key reproducible commands (run from the indicated checkout):

```powershell
# Shipyard
C:/Python313/python.exe -B -m unittest discover -s tests -v

# Modern
C:/Python313/python.exe -B tools/shipyard/test_xdk_project.py
C:/Python313/python.exe -B -m unittest tools.shipyard.tests.test_fast3d_opcode_owner tools.shipyard.tests.test_fast3d_triangle_pipeline tools.shipyard.tests.test_resources_generation -v
C:/Python313/python.exe -B tools/shipyard/tests/test_resources_variant.py
C:/Python313/python.exe -B -m unittest tools.shipyard.tests.test_json_generation -v

# Smash
C:/Python313/python.exe -B -m unittest discover -s tests/platform-base -v
C:/Python313/python.exe -B -m unittest discover -s tests/fast3d-xdk -p test_prepare.py -v
C:/Python313/python.exe -B -m unittest discover -s tests/fast3d-xdk -p test_triangle_pipeline.py -v
C:/Python313/python.exe -B -m unittest discover -s tests/fast3d-xdk -p test_texture_binding.py -v
```
