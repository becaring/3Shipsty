# Ship of Harkinian 9.2.3 Xbox 360 Runtime Bring-Up Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boot the genuine Ship of Harkinian 9.2.3 Xbox 360 application through its real runtime path in the owned Xenia instance and advance it to stable gameplay without bypasses.

**Architecture:** Keep upstream Shipwright 9.2.3 in control of application/game behavior and keep Shipyard limited to Xbox platform mechanisms and deterministic XDK compiler projections. Work forward from the last proven boundary, capture the exact failing boundary, apply one tested narrow fix, rebuild the affected production boundary, and replay the same reproduction.

**Tech Stack:** Shipwright 9.2.3, libultraship/Fast3D, XDK PowerPC/Xenon toolchain, ImageXex, Xenia Canary, Python build/projection tests.

**Spec:** `RUNTIME_HANDOFF.md`

## Global Constraints

- Modify only `D:\Projects\3Shipsty9.x`; every supplied reference tree is read-only.
- Preserve the real XEX, `InitOTR`, storage/filesystem, O2R archives, libultraship Context, current GUI, input, save, audio, and gameplay paths.
- Do not introduce fake menus, test-only application paths, alternate renderers, replacement resource managers, fake storage success, or hardcoded scene boot.
- Treat Xenon as big-endian and classify each data boundary before changing conversion behavior.
- Use only `scratch/runtime/xenia/xenia_canary.exe` and keep emulator state under the owned runtime tree.
- Do not reuse a stale full-build receipt after generated startup source changes.
- Record commit, XEX hash, logs, newly proven behavior, and remaining uncertainty at every crossed runtime boundary.

## Review Focus

- Profile-less Xenia storage must expose its exact native return path without being mistaken for the already-known relative-path exception.
- Missing optional `oot-mq.o2r` must be a normal absence after cwd initialization, while required `soh.o2r` and `oot.o2r` still mount.
- Generated callable containers must retain every upstream element and predicate in order under XDK `/O2`.
- Storage failure and partial Context initialization must unwind real XNet, workers, GUI, resource, and device ownership safely.
- Reaching gameplay must include real controller, save round-trip, audio, and one post-4.0.5 feature before completion is claimed.

---

### Task 1: Verify and checkpoint the two startup fixes

**Files:**
- Modify: `tools/shipyard/prepare_randomizer_generation.py`
- Modify: `tools/shipyard/test_randomizer_generation.py`
- Modify: `tools/shipyard/prepare_application.py`
- Modify: `tools/shipyard/test_application.py`
- Modify: `platform/shipyard/randomizer-generation/README.md`
- Modify: `STATUS.md`
- Modify: `PORTING_LEDGER.md`
- Create: `RUNTIME_HANDOFF.md`

**Interfaces:**
- Consumes: pinned upstream `conditionalAlwaysHints`, `InitOTR`, and existing `xbox_compat::filesystem` implementation.
- Produces: generated ordered callable insertion and `InitWorkingDirectory("game:/")` before `Storage::Mount()`.

- [ ] **Step 1: Run the callback projection regression**

Run: `C:\Python313\python.exe -B tools/shipyard/test_randomizer_generation.py`

Expected: all callback inventory/order checks pass, including 12 explicit `push_back` calls.

- [ ] **Step 2: Run the startup projection regression**

Run: `C:\Python313\python.exe -B tools/shipyard/test_application.py`

Expected: all startup checks pass and cwd initialization precedes storage mount.

- [ ] **Step 3: Compile the complete generated startup unit**

Run: `C:\Python313\python.exe -B tools/shipyard/prepare_application.py --build`

Expected: generated `OTRGlobals.cpp` compiles successfully through XDK.

- [ ] **Step 4: Review the exact checkpoint diff**

Run: `git diff --check` and `git status --short`

Expected: only the documented startup, regression, and handoff files differ.

- [ ] **Step 5: Commit the verified startup boundary**

Run: stage only the reviewed files, then `git commit -m "fix: initialize Xbox startup runtime paths"`.

Expected: a narrow bisectable commit containing the callback and cwd fixes.

### Task 2: Produce and stage a fresh genuine XEX

**Files:**
- Generated: `scratch/project-xdk/**`
- Generated: `scratch/link-integration/**`
- Replace after success only: `scratch/runtime/3Shipsty/3Shipsty.xex`

**Interfaces:**
- Consumes: the committed source checkpoint and all 1,836 production build inputs.
- Produces: a newly linked/ImageXex-produced real application XEX plus complete receipts.

- [ ] **Step 1: Regenerate build identity metadata**

Run: `C:\Python313\python.exe -B tools/shipyard/prepare_build_metadata.py`

Expected: generated metadata names the new checkpoint.

- [ ] **Step 2: Build every selected production object**

Run: `C:\Python313\python.exe -B tools/shipyard/build_xdk_project.py`

Expected: exit zero, 1,836 verified PPC objects, all 1,094 application translation units selected.

- [ ] **Step 3: Link and run ImageXex**

Run: `C:\Python313\python.exe -B tools/shipyard/link_xdk_application.py`

Expected: linker and ImageXex exit zero with no forced unresolved symbols.

- [ ] **Step 4: Verify artifact identity before staging**

Run: inspect the link receipt and `Get-FileHash -Algorithm SHA256` for the newly produced XEX.

Expected: receipt hashes match the produced file and differ from stale artifacts when source identity changed.

- [ ] **Step 5: Stage only the verified XEX**

Run: copy the receipt-identified XEX to `scratch/runtime/3Shipsty/3Shipsty.xex`; do not replace the verified archives or speech data.

Expected: the staged file hash equals the fresh link artifact hash.

### Task 3: Replay startup and isolate the storage boundary

**Files:**
- Evidence: `scratch/runtime/xenia/*.log`
- Modify only after root-cause proof: the owning Shipyard storage/filesystem source and its focused regression test.

**Interfaces:**
- Consumes: fresh XEX, `soh.o2r`, retail `oot.o2r`, absent optional `oot-mq.o2r`, owned portable Xenia state.
- Produces: proof that cwd fallback is fixed and an exact storage/profile/container/device result.

- [ ] **Step 1: Launch the fresh XEX in the owned Xenia runtime**

Run: start `scratch/runtime/xenia/xenia_canary.exe` with `scratch/runtime/3Shipsty/3Shipsty.xex` and the owned game working directory.

Expected: no recurrence of the old relative-path `ERROR_NOT_READY` forced trap.

- [ ] **Step 2: Preserve the complete run log and XEX hash**

Run: copy `xenia.log` to a milestone-named evidence file immediately after the run and hash both files.

Expected: immutable evidence tied to the fresh XEX.

- [ ] **Step 3: Identify the first unproven boundary**

Inspect: XNet startup, `XamContentCreateEx` return, device mapping, save-container mount, required archive mounts, optional MQ absence, and Context entry in order.

Expected: one specific failing component and return/error state, not a speculative diagnosis.

- [ ] **Step 4: If profile state is required, use Xenia's supported account UI**

Action: configure a new local test profile inside the owned portable runtime only; do not copy profile data from references.

Expected: profile availability is changed through Xenia's supported interface and the same startup reproduction is rerun.

- [ ] **Step 5: Add a failing focused regression before any source fix**

Run: the owning storage/filesystem test showing the captured return/path behavior.

Expected: the test fails for the observed root cause and does not bypass the Xbox storage contract.

- [ ] **Step 6: Apply one narrow fix and replay the same reproduction**

Expected: the regression passes, the affected production boundary rebuilds, and the fresh Xenia run advances past exactly that failure.

### Task 4: Advance the genuine runtime to gameplay

**Files:**
- Evidence and source are determined one boundary at a time from Task 3; update `STATUS.md`, `PORTING_LEDGER.md`, and `RUNTIME_HANDOFF.md` at milestones.

**Interfaces:**
- Consumes: a working storage/device mount and required archives.
- Produces: real Context, GUI/file select, controller input, save round-trip, audio, gameplay, and modern-version proof.

- [ ] **Step 1: Prove archive and Context initialization**

Expected: `soh.o2r` and `oot.o2r` mount; missing `oot-mq.o2r` is benign; real libultraship Context construction completes.

- [ ] **Step 2: Prove current GUI and file select**

Expected: current SoH GUI renders and file select is navigable without a fake or stripped menu.

- [ ] **Step 3: Prove controller and save behavior**

Expected: Xbox controller operates the real UI/game, a save is created under the mounted container, and the save reloads after restart.

- [ ] **Step 4: Prove audio and normal gameplay**

Expected: XAudio2 starts, audible game audio is present, and normal world/HUD gameplay remains stable.

- [ ] **Step 5: Prove modern 9.2.3 identity**

Expected: exercise one clearly post-4.0.5 feature such as current randomizer UI/state, tracker UI, or modern menu/search structure.

- [ ] **Step 6: Record the milestone checkpoint**

Record: exact commit, XEX SHA-256, evidence log, proven boundaries, unproven behavior, reproduction steps, and any physical-hardware requirement.
