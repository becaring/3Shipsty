# Fresh integration checkpoint — 66959d6

Both active consumers now have fresh complete native compile/link evidence against Shipyard `66959d6abce9e3606e15b8728aa5496fd560a696`. Their source states and matching receipts were preserved and verified before remaining ownership classification resumed on 2026-09-23 at approximately 19:20 Pacific. Historical SoH 4.0.5 was not accessed or modified in this integration work. Existing XEXs were moved aside before each final link.

Shipyard remains clean. Both locks use API 5 and baseline SHA-256 `16ef0bb550dbddd5dbf0ee13537cb3f9712b590d17aa2f6ff45246f097f0b1ca`. Parallel compilation is authorized going forward; both project builds used eight independent compiler shards.

## Fresh build and link evidence

| Consumer | Fresh compilation | Final link evidence |
| --- | --- | --- |
| Modern 3Shipsty 9.2.3 | All 1,844 selected PPC units from an empty canonical object directory; eight successful shards; source/header/object receipts verified. The stale JSON project gate now passes all 18 tests. | 1,094 application objects plus 750 archive objects; `lib.exe`, `link.exe` and `imagexex.exe` all exited zero. Output timestamps fall within the recorded invocation. |
| Smash360 | 140 LUS and 111 application project units with `--rebuild`; all 486 game C units recompiled after verifying 1,767 projection dependencies; 130 native compression-library units and two archive operations passed. | Links 485 of the new direct game objects; the application's own `port_log` replaces the extra game-C copy. Fresh output created with old outputs absent; XEX2 and scheduler/VI/message symbol ownership verified. |

The modern final shard took 1,013 seconds. Its `randomizer/location.cpp` compilation accounted for a long active tail; the other seven shards had already finished their object sets. The initial sandbox-denied MSBuild attempt produced no objects and is retained separately under `scratch/integration-66959d6/attempt-sdk-denied`.

| Final artifact | SHA-256 |
| --- | --- |
| [Modern XEX](../scratch/link-integration/3Shipsty.xex) | `2e9c342201eebc52bd1c55f5777ed41b87ca7c533992edbefbf03543fbc33ce7` |
| [Smash XEX](D:/Projects/Smash360/scratch/application-xdk/native/build/Smash360.xex) | `2d8227dc966660a8a273f5004f7cf4c2ed722ec43649a6226ded5072cd6c5c3e` |

Modern's [run record](../scratch/integration-66959d6/modern-run.json), [complete compile receipt](../scratch/project-xdk/complete-application-verification.json) and [link receipt](../scratch/link-integration/link-verification.json) bind the current manifest and hashes. Smash's project receipts are under `scratch/application-xdk/native/parallel/{Libultraship360,Smash360}`, its game receipt is `scratch/integration-66959d6/game-recompile.json`, and its library receipt is `scratch/libzip-xdk/compile-results.json` in the Smash checkout. All are included in their corresponding frozen archives.

## Preserved source states

Archives are local, exclusive-create snapshots. Every entry was reread and checked against its recorded SHA-256 at creation; the archive hashes and current final XEX hashes were independently rechecked afterward. The [checkpoint index](../scratch/checkpoints/66959d6-2026-09-23/checkpoint-index.json) provides compact machine-readable metadata. Matching `*.json` files list every archived file hash.

| Archive | Files | Archive SHA-256 |
| --- | ---: | --- |
| [modern.zip](../scratch/checkpoints/66959d6-2026-09-23/modern.zip) | 15,613 | `561aafb971c559d065b5c49a4fb86d2bfe00e8ab7527cc26b4a693c9fd5bf9e8` |
| [smash-full.zip](../scratch/checkpoints/66959d6-2026-09-23/smash-full.zip) | 5,665 | `dedc4057614ccb5fe6f1045035868bc56368f01ea1686ba175e28ef448b31c2c` |
| [shipyard.zip](../scratch/checkpoints/66959d6-2026-09-23/shipyard.zip) | 141 | `1b6239b846ca1d0a96c092aae4fe5dce9f7819f63dfdcaddbf5366036210b598` |

Modern's base remains Git `e3d1a098dea39cc62ece7c62757e8171d3e38ff3`. The snapshot preserves tracked source files, newly owned platform/tools/porting files, actual compiled source/header inputs, locks, recipes, build/link receipts, symbols and final artifacts. The adjacent `modern-working-tree.patch` and metadata preserve the uncommitted diff and tracked deletions. The build metadata's embedded commit identifies the base; the snapshot hashes identify the actual migrated working tree. Unrelated root assets `3Shipsty`, `Singularity.apk`, and `djipi_s_3ds_experience_tot_fix.zip` were left untouched and excluded.

Smash remains a source tree without a Git repository. Its archive includes the verified game projection dependency closure and generated game sources, fresh direct game objects, compression sources/libraries, source staging, locks, tools/tests, project receipts and final artifacts. The earlier `smash.zip` archive and its `9998bf...` XEX are superseded by `smash-full.zip` and the final hash above. Shipyard's clean source package is preserved separately. No SDK installation files are copied.

For recovery, verify the archive against its matching JSON manifest and extract into a separate checkout/directory. Preserve the modern base/deletion metadata and the sibling Shipyard layout. These snapshots preserve the reached working state; they are not an empty-machine setup or dependency-fetch procedure.

## Gate repairs and limits

The stale JSON include came from saved subsystem recipes. Their owning scripts were executed to regenerate real compiler records. The common resource include provider now includes the verified Shipyard package root, which its filesystem forwarding headers require. Regeneration exposed a stale collision-viewer rule: numeric tuple access must be restored from `xbox_compat::get` to `std::get`. A real-source regression test failed before that correction and passed afterward. All 13 application-window units then compiled, and the host geometry/icon comparison matched across 712 lines. The host test's missing platform-root resolver import was also repaired. Resource shutdown's detached lifetime/1,000-completion and PPC checks passed.

The receipts prove fresh native compilation of the verified projected source trees and successful static links. Complete regeneration from empty generated outputs, Xenia execution, hardware behavior, and broader JSON/async semantic coverage remain separate work. Source migrations remain uncommitted in modern and unversioned in Smash; the archives protect this checkpoint. Remaining reusable-source ownership is recorded in [the post-checkpoint classification](SHIPYARD_REMAINING_OWNERSHIP_66959D6.md).

The [execution ledger](SHIPYARD_66959D6_EXECUTION.md) records the integration sequence. The earlier [recovery assessment](SHIPYARD_RECOVERY_2026-09-23.md) describes the intake state and superseded build failures.
