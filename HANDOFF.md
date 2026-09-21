# 3Shipsty forward-port handoff — 2026-09-21

Historical stop checkpoint. The later link closure and runtime resume point are
recorded in [RUNTIME_HANDOFF.md](RUNTIME_HANDOFF.md).

Stopped at the user's explicit request. Do not interpret this as completion or
an architectural blocker. All agents are completed or interrupted; the last
root-owned build session finished before this handoff. No further engineering
work was started after the stop request.

## Exact checkpoint and scope

- Working tree: `D:\Projects\3Shipsty9.x`
- Branch: `shipyard/xbox360-9.2.3`
- Last committed checkpoint: `c0e0343406cda289762ff1b892239a62796ec041`
- Subject: Complete modern application projections and integrate Xbox speech lifecycle.
- Current tree has **uncommitted work listed below**. This handoff is not a claim
  that those edits are included in the checkpoint or fully integrated.
- First real bring-up estimate: **about 65%**, uncertain until runtime. Application
  translation coverage is complete; runtime correctness is not established.

Pinned application is genuine Shipwright 9.2.3 / Ackbar Delta, upstream commit
`cb71e22a79bc5d1f688fa881795bbd93094895fc`. LUS is
`fdcaf6336776d24a6408d016b0a52243f108f250`; OTRExporter is
`32e088e28c8cdd055d4bb8f3f219d33ad37963f3`; ZAPDTR is
`ee3397a365c5f350a60538c88f0643f155944836`. This release has no Torch gitlink.
See UPSTREAM_BASELINE.md for source repositories and baseline verification.

All supplied reference trees remain read-only. Upstream application/submodule
sources remain untouched; adaptations live in Shipyard providers and reproducible
generated copies. Do not modify the reference trees when resuming.

## What is verified

- A complete production XDK compilation passed: **1,833 PowerPC objects**,
  including every **696 C + 398 C++ = 1,094 pinned application translation units**.
  The native declaration probe is excluded. Sixteen desktop/mobile backend
  selections have explicit Xbox replacements; application features are retained.
- Main build receipt records actual source/object hashes and the owned header
  closure from MSBuild. Eleven inventory checks passed.
- Complete startup, modern randomizer, enhancements, menus, resource integration,
  save serialization and speech are included in compilation. Focused original/
  projected contract checks passed as documented in their provider READMEs.
- Real linking was attempted with all application objects and an ordinary
  Shipyard static library. No forced unresolved symbols or fake entry point.
- Runtime archives from the user's retail NTSC 1.0 ROM are extracted, verified
  and staged; the permissions dialog was already resolved.

**Receipt limitation:** interpolation sources were regenerated after the main
1,833-object receipt. Current dirty sources need a fresh combined build; the
previous receipt must not be treated as verification of all current changes.

## Exact remaining link failure

Last genuine linker result: exit 1120, **16 unresolved externals**:

1. Ten build metadata globals from upstream `soh/src/boot/build.c.in`:
   `gBuildDate`, `gGitCommitHash`, `gGitBranch`, `gBuildVersion`,
   `gBuildVersionPatch`, `gBuildVersionMinor`, `gBuildVersionMajor`,
   `gGitCommitTag`, `gBuildMakeOption`, `gBuildTeam`.
2. Four XDK CRT gaps: `snprintf`, `roundf`, `truncf`, `nearbyintf`.
3. Two C++-mangled interpolation references from a FileSelectMoreInfo lambda:
   `FrameInterpolation_RecordOpenChild` and `FrameInterpolation_RecordCloseChild`.
   Real implementations export C linkage.

An earlier link attempt requested desktop `StormLibRAS.lib` via the pinned
StormLib header's autolink pragma. The wrapper now suppresses that one desktop
library with `/nodefaultlib:StormLibRAS.lib`; complete StormLib implementations
are already in Shipyard.lib. This does not suppress unresolved symbols.

**No successful executable link, modern XEX, Xenia boot, gameplay, or hardware
validation exists.** Linking is the immediate unfinished step. The 16-symbol
count describes the last attempt, not a guarantee that it is the final obstacle.

## Uncommitted fixes and their limits

- `tools/shipyard/prepare_build_metadata.py`: new generator consumes the actual
  pinned upstream template and CMake version values. Native C compilation and
  COFF inspection passed, including BE version fields and the real
  `Ackbar Delta (9.2.3)` string. Uses SOURCE_DATE_EPOCH or the port commit time for
  reproducible build date. **Not yet added to the combined source manifest.**
- `tools/shipyard/prepare_gameplay_features.py` and its source lock: narrow
  generated header removes redundant block-scope interpolation declarations
  inside OPEN_DISPS/CLOSE_DISPS while preserving their bodies. Actual global C
  declarations remain. This addresses XDK lambda linkage behavior. The pending
  standalone build completed successfully: **89/89 units**, session exit 0.
  **COFF reference inspection, focused checks and combined relink remain.**
- `platform/shipyard/crt/{float.cpp,format.cpp,contract.cpp}` and
  `tools/shipyard/{prepare_crt.py,test_crt.py}`: interrupted agent's new work.
  Existing receipt reports host exit 0 (1,273,868 float and 66,950 formatting
  cases) and two native PPC objects. Root has **not reviewed or integrated** this
  implementation. Review rounding modes, exception behavior, signed zero,
  NaN/infinity handling and formatting semantics before accepting it. Do not
  compile the host contract source into production.
- Build generator/wrapper/inventory changes establish canonical complete
  Window/Gui declarations, exclude the native ABI probe, track actual header
  dependencies and reject stale receipts before linking. Changes are in
  `tools/shipyard/{generate_xdk_project.py,build_xdk_project.py,
  link_xdk_application.py,test_xdk_project.py}` and
  `platform/shipyard/build/subsystems.json`.
- `platform/shipyard/build/xex.xml` exists but is ignored/untracked: development
  title ID `0x534F4809`, separate from the old development build. Preserve and
  explicitly stage it when checkpointing; ImageXex has not been reached.
- Documentation edits: STATUS.md, PORTING_LEDGER.md, UPSTREAM_BASELINE.md,
  platform/shipyard/build/README.md and this handoff.

No partial CRT work was committed automatically. Run `git status --short` on
resume; ignored scratch receipts and xex.xml are not all shown there.

## Evidence and artifacts

Paths below are relative to the working tree; scratch artifacts are local,
generally ignored by Git, and must be preserved for this handoff.

| Evidence/artifact | Location |
| --- | --- |
| Complete compile receipt/log | `scratch/project-xdk/complete-application-verification.json`, `complete-application-build.log` |
| Manifest and generated project | `scratch/project-xdk/manifest.json`, `ShipyardCompile.vcxproj` |
| Eleven inventory checks | `scratch/project-xdk/complete-inventory-tests.log` |
| Genuine link failure/receipt | `scratch/link-integration/application-link.log`, `link-verification.json` |
| Native static library, 134,650,332 bytes | `scratch/link-integration/Shipyard.lib` |
| Exact archive/link arguments | `scratch/link-integration/archive.rsp`, `application-link.rsp` |
| Metadata generation/native receipt | `scratch/build-metadata-xdk/manifest.json`, `xdk/build.json` |
| Latest interpolation batch build | `scratch/gameplay-features-xdk/link-closure-build.log` |
| Interrupted CRT agent receipts | `scratch/crt-xdk/verification.json`, `xdk/build.json`, `xdk/float.disasm.txt` |
| Verified retail archives | `scratch/assets/retail-ntsc10/archive-verification.json` |
| Runtime staging record | `scratch/runtime/staging.json` |

Runtime directory `scratch/runtime/3Shipsty` contains `oot.o2r`, `soh.o2r` and
364 eSpeak data files. No ROM is embedded or staged for Xbox runtime.
`scratch/runtime/xenia` contains an owned Xenia copy and portable configuration;
it has not been launched for this application. Retail archive SHA256 values:

- oot.o2r: `c2b5d5af24a52095a13e50479763ff4b9dcc1d8afe6a0788fbfc26a91b17c03c`
- soh.o2r: `7b375d854385a6cdb6843db89c18da981948e5b56986f479297cca33d2914a2f`

Speech uses official eSpeak NG 1.52.0; dependency source and licensing obligations
are recorded in its README and UPSTREAM_BASELINE.md. Xbox speech/audio remains
unexecuted.

## Resume sequence and commands

1. Review unfinished CRT provider and its evidence; verify interpolation C linkage.
2. Integrate actual metadata and the two production CRT sources through recipes in
   `platform/shipyard/build/subsystems.json`. Do not add duplicate implementations.
3. Refresh focused checks and combined compile receipt, then perform genuine link.
4. If ImageXex succeeds, stage the actual XEX with the existing archives and run
   the real application in the owned Xenia directory.
5. Validate real initialization/archive mounting/UI/input/storage/file-select,
   normal-save gameplay, audio, a modern feature and legitimate randomizer state.
   Xenia evidence never substitutes for user-provided physical Xbox validation.

Run from `D:\Projects\3Shipsty9.x` in PowerShell after the integration edits:

```powershell
C:\Python313\python.exe -B tools/shipyard/prepare_build_metadata.py
C:\Python313\python.exe -B tools/shipyard/test_crt.py
C:\Python313\python.exe -B tools/shipyard/test_gameplay_features.py
C:\Python313\python.exe -B tools/shipyard/test_xdk_project.py
C:\Python313\python.exe -B tools/shipyard/build_xdk_project.py
C:\Python313\python.exe -B tools/shipyard/link_xdk_application.py
```

XDK: `C:\Program Files (x86)\Microsoft Xbox 360 SDK`.
MSBuild: `C:\Windows\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe`.
Sandbox execution previously needed escalation for SDK per-user registration.
Git submodule helper failed on missing shell utilities; direct `git -C <path>
rev-parse HEAD` verified the pins without altering system PATH.

Startup audit note, **not a confirmed bug**: storage device selection may occur
before native display initialization. If system UI fails during execution,
investigate the existing InitializeNativeDisplay boundary and donor evidence.
Do not introduce a parallel game loop or assume this needs a speculative fix.

All work is now stopped. The interrupted CRT agent must not be resumed without
a subsequent user request to continue the project.
