# 3Shipsty runtime resume point — 2026-09-21

This supersedes HANDOFF.md's earlier stopped state. User authorized fixing the
16 link symbols and proceeding. All sixteen are fixed and committed. The current
external blocker is **automatic approval review unavailable due to the account
usage limit**. The latest full rebuild was rejected before execution; the review
explicitly states this is a review failure, not an unsafe-action determination,
and must not be bypassed. No new approval-dependent work was attempted afterward.

## Checkpoint and actual execution

- Branch: shipyard/xbox360-9.2.3.
- HEAD: `3581983af5a5d3dbc4a100aa6b37a241526c07bc`.
- Genuine combined build: 1,836 verified PPC objects, all 1,094 application TUs.
- Genuine linker and ImageXex both returned zero, without forced unresolveds.
- Latest staged XEX: `scratch/runtime/3Shipsty/3Shipsty.xex`.
- XEX SHA256: `dc03cb7a53475de94c7ec7e46fe247703843c184ce58516927cdd96feddcf0e5`.
- This XEX includes the callback-table fix below, but **does not include the
  working-directory fix**. Build identity metadata still names the prior c0e0343
  checkpoint; regenerate metadata after the next source checkpoint for packaging.
- First-bring-up estimate remains about 70%; no working game UI/gameplay/audio
  or save correctness is claimed. No physical Xbox validation.

## Runtime issue 1: fixed and verified in real application

The initial black screen was an invalid read while copying conditionalAlwaysHints
during C++ static initialization. Noninvasive cdb inspection of owned Xenia mapped
the fault to hints.cpp's vector<pair<RandomizerCheck,function<bool()>>> copy.
The generated source had twelve entries; XDK optimized code initialized only
three array elements before copying twelve, consuming stale stack bytes as a
callable vtable. This is an H-class compiler/codegen issue at a generated boundary.

`prepare_randomizer_generation.py` now constructs named callback elements and
inserts them in the original order, reserving capacity once. All actual predicates
and check IDs remain. `test_randomizer_generation.py` compares all twelve against
upstream. Native compilation, original/projected contract output, complete build
and link passed. Real execution now reaches InitOTR, native XNet/storage calls,
and opens both `soh.o2r` and retail `oot.o2r` during archive discovery.

Evidence:

- `scratch/runtime/xenia/startup-host-stacks.txt`
- `scratch/runtime/xenia/startup-exception-context.txt`
- `scratch/runtime/xenia/startup-callable-array.txt`
- `scratch/runtime/xenia/hints-native.disasm.txt`
- `scratch/runtime/xenia/hints-fixed-native.disasm.txt`
- `scratch/runtime/xenia/startup-before-callback-fix.log`
- `scratch/randomizer-generation-xdk/startup-fix-test.log`
- `scratch/link-integration/link-verification.json`

An independent audit found the huge .CRT$XCU section is mostly null compiler
padding, with 2,651 unique valid constructors. It is not the cause of the fault;
do not strip constructors. Evidence: `scratch/crt-initializer-audit/README.md`.
The single audit agent has finished and is idle. No agents are running.

## Runtime issue 2: source fixed; full verification pending

Xbox's filesystem wrapper deliberately requires `InitWorkingDirectory`, but the
real application never called it. Absolute `game:` paths worked. When upstream
LocateFileAcrossAppDirs fell back to `./oot-mq.o2r`, the relative existence check
threw ERROR_NOT_READY instead of reporting an absent optional MQ archive.

`prepare_application.py` now inserts
`xbox_compat::filesystem::InitWorkingDirectory("game:/");` at InitOTR entry,
before storage and Context. This initializes the existing filesystem interface;
it does not fake MQ availability or alter archive acceptance. Upstream's real
missing-archive sentinel/version behavior remains unchanged.

`test_application.py` first failed on the missing initialization; after the fix,
all five checks passed. `prepare_application.py --build` compiled the complete
OTRGlobals.cpp successfully. Evidence:

- `scratch/application-xdk/cwd-startup-test.log`
- `scratch/application-xdk/cwd-startup-build.log`
- `scratch/runtime/xenia/after-callback-fix-before-cwd.log`

The combined build command was blocked by automatic approval review. Therefore
the earlier complete-build receipt is stale for the current generated startup
source. Do not link it without a fresh full compile receipt.

## Storage prerequisite still to verify

The owned Xenia runtime had zero local profiles. It returned from
XamContentCreateEx into a native C++ exception, and subsequent `shipyard:` lookups
had no device mapping. A missing signed-in local profile is a concrete suspect,
but the exact native return code was not captured. Do not claim this is resolved.

Owned Xenia was restarted without a title to inspect its Profile menu. Current
observed process was PID 78420, window title Xenia-canary; re-query rather than
trusting stale IDs. No profile was created, and no account/sign-in data was copied
from references. Configure a local emulator test profile through its supported
interface and verify the save-container result. Keep all storage under the owned
runtime folder. The user's reference Xenia instance was only observed/read.

## Uncommitted implementation files

- platform/shipyard/randomizer-generation/README.md
- tools/shipyard/prepare_randomizer_generation.py
- tools/shipyard/test_randomizer_generation.py
- tools/shipyard/prepare_application.py
- tools/shipyard/test_application.py
- STATUS.md, PORTING_LEDGER.md and this runtime handoff document.

Upstream application files and all reference trees remain unmodified by this
work. Keep D:\Projects\SoH360, D:\Projects\Smash360, D:\3Shipsty and historical
Re60/Xenia references read-only.

## Next actions after the approval service is available

1. Refresh `git status`; review and checkpoint the two narrow startup fixes.
2. Regenerate metadata for that checkpoint, build the full application and link:

```powershell
C:\Python313\python.exe -B tools/shipyard/prepare_build_metadata.py
C:\Python313\python.exe -B tools/shipyard/build_xdk_project.py
C:\Python313\python.exe -B tools/shipyard/link_xdk_application.py
```

3. Stage only the successfully produced XEX beside existing retail archives and
   speech data. Run with the owned emulator `scratch/runtime/xenia/xenia_canary.exe`.
4. Verify working-directory fallback, storage mount and archive initialization;
   continue through real UI/file-select/input/save/gameplay/audio and modern-feature
   validation. Do not stop at a successful link or splash screen.

Standalone startup and generation commands already passed:

```powershell
C:\Python313\python.exe -B tools/shipyard/test_application.py
C:\Python313\python.exe -B tools/shipyard/prepare_application.py --build
C:\Python313\python.exe -B tools/shipyard/test_randomizer_generation.py
```

Do not use a different execution route to evade the failed automatic approval.
