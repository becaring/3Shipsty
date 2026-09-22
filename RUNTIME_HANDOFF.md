# 3Shipsty runtime resume point — 2026-09-21

## 2026-09-22 verified gameplay/audio/background checkpoint

This supersedes all older claims below that audio is silent, the shop
background is broken, or game-C native byte order is unresolved. Current
branch `shipyard/xbox360-9.2.3`, proven endian-fix checkpoint
`8f55f53cfa771d99fb26867b04f92fe40406dfb8`.
The XEX was built just before that checkpoint with embedded identity
`5dd926bf0922126f843b5ff8e1290054f9bf7d51` plus the same endian code and
other uncommitted narrow runtime changes. Current freshly linked/staged genuine XEX SHA256:
`1dffc060f65bb04dff8eb87b8a89d1b35090812e6f50fdbd9a1cf943b0f2b680`.
Owned Xenia launch returned PID 31588; re-query. No reference tree was edited.
Evidence: `scratch/runtime/post-endian-audio-gameplay-app-20260922.log`,
SHA256 `d37b21ded873d86e0191ecf72dec521dd25b54c07f3835224ef311b4180f92e6`.

User confirmed the Kokiri shop JPEG background is restored, default modern
randomizer gameplay works, controller movement/save/reload work, audio is
audible, and the Deku Tree exit fade is no longer pink. The shop fix checks
the serialized FF D8 FF E0 marker as bytes before calling the existing real
`ResourceMgr_LoadJPEG`; no renderer or decoder replacement. The audio/fade
fix projects `libultraship/include/ship/utils/binarytools/endianness.h` for
game C so `_XBOX && _M_PPC` selects the Xenon big-endian layout, matching
the already-correct binary-tools projection and 4.0.5 platform ABI. Before
this, generated game C had reversed packed-color and `AudioCmd` fields.
Afterward, targeted XDK compiles show the correct fields. The genuine mixer
now reports BGM/SFX enabled, 8 active notes at task 600, reset gate 0, and
309,748 nonzero PCM samples by block 600; the user hears audio.

Verification: 18 projection tests, 696/696 game C, 1,836 PPC objects,
genuine link/ImageXex success. The staged XEX loaded the existing real
randomizer save. Do not infer physical Xbox 360 validation. Initial black
startup delay remains about 9.25 seconds in application initialization.

## 2026-09-22 live update — real modern randomizer gameplay reached

This section supersedes older unresolved-randomizer/gameplay statements below.
Branch `shipyard/xbox360-9.2.3`, HEAD
`0cad9e225f77b3ff40530f56a5676913118f9d1d`; tree remains dirty.
Current staged genuine XEX SHA256:
`b7f83f704cd77b24711619c12e469d1213b9c8b005f9bb69c47b30e7ebc46c64`.
The owned Xenia PID was 40196 at the time of this entry; re-query rather than
trusting it. No reference tree was changed. The app-log snapshot is
`scratch/runtime/post-rando-gameplay-app-20260922.log`, SHA256
`d52d6b9ff6fc2ca880209e33aeac8bb7105e55d30f2a3957d635874868612fb3`.

The previous multi-minute seed stall was bounded to the first ice-trap
`Traps::GetTrapName` call. Its 192-row modern `InitTrickNames` never entered
its first statement while Xenia CPU rose, indicating guest function
translation/codegen overhead rather than filesystem I/O or table execution.
The Xbox projection now splits the initializer into 24 no-inline eight-row
helpers. Tests assert all 192 original assignment keys and their order;
native `Traps.cpp` compile and the 35-unit randomizer application contract
pass. On the fresh XEX, every helper ran in milliseconds, then item/entrance
overrides, hints, spoiler writing, and FileChoose-to-Gameplay completed.
The user confirms playable movement, a save, and successful save reload.
Owned storage contains valid JSON at `Randomizer/13-75-62-17-28.json` and
`Save/file1.sav`.

Not complete: the user hears no audio. XAudio2 queues all-zero buffers; the
game synth reports no active notes and disabled BGM/SFX sequence players
through task 1,200. Bounded sequence enqueue/process and game audio-update
probes are compiled but **not yet included in the staged XEX**. The user also
could not open chests or talk to NPCs in one randomizer run, although A works
for normal actions; they are testing a basic seed to distinguish settings
from an interaction defect. Startup still spends ~9.25 seconds inside modern
application initialization after factory registration. Thread placement needs
review: 4.0.5 pinned audio to Xbox hardware thread 2 and low-priority save to
3; current modern workers are already separate threads but generic
`joining_thread` has no XDK processor placement. Do not infer audio silence
is a threading issue without the next diagnostics.

## 2026-09-22 live update — post-logo fault cleared, FileChoose running

This section supersedes older black-screen and unrun-XEX statements below.
Branch `shipyard/xbox360-9.2.3`, HEAD
`0cad9e225f77b3ff40530f56a5676913118f9d1d`; current work remains dirty.
Owned Xenia PID for this run was 37844; it was stopped after the nine-minute
randomizer stall and evidence capture. Re-query before any later process action.
The user interacted with the visible file-select/randomizer UI.

The post-logo fault was in `Font_LoadOrderedFontNTSC`: modern 9.x loads the
Japanese 0xFFFC ordered-font list for NTSC startup even when the active
language is North American English. O2R serializes code units little-endian;
Xenon interpreted raw copied bytes as big-endian `u16` and used an invalid
kanji-table index. The Xbox-only projection in `prepare_game.py` now converts
the ordered-font and ordinary Japanese dialog copy boundaries into native
`Font.msgBufWide`, leaving all other text/archives untouched. 4.0.5 had only
the NES byte-font startup path, so this is specifically a 9.x boundary.

Fresh complete build: 696/696 generated C; 1,836 verified PPC objects; real
link/ImageXex exit zero. Both produced and staged XEX SHA256:
`2299f84cb404c2ec2729e7b66029fc88bc2d50055390ac6e5bd89c09891f6d14`.
Runtime evidence snapshot:
`scratch/runtime/post-font-filechoose-app-20260922.log` (SHA256
`7646f24b8698a897da315f94ca0c348913177ef7fd1216009675adbc3a1465f8`).
It records `MESSAGE font end`, all traced Play_Init stages, scene 81, actor/room
load, actual Gameplay frames, transition to FileChoose, and file-select fade
with `fill=0 window=200 controls=255`. The user confirms visible UI and is
starting a randomizer run. Do not infer visual blackness from Xenos CPU
framebuffer readback: it falsely reports black for graphics the user sees.

Open: randomizer completion, normal playable gameplay, save creation/load,
and audio. The user reports silence; native XAudio2 is initialized and queues
buffers, but the mixer counted zero nonzero samples through 600 blocks. This
is an upstream-audio-to-native-PCM problem, not yet localized. Do not claim
audio works merely because buffers submit. The randomizer run did not complete
after nine minutes. Its final log is `Calculating Playthrough Done`, after all
placement and playthrough-reduction stages, but before spoiler writing. The
process CPU continued rising while a sampled interval showed only one 24-byte
read and no writes; this is not evidence of a filesystem bottleneck. Its Xenia
log snapshot is `scratch/runtime/post-rando-hang-xenia-20260922.log`, SHA256
`3bd6b0bf94641737e913095dd02756d3bab4e4425176b7fd76fab4fb0201e040`.
The next source build has bounded markers around item/entrance overrides,
hints, warp texts, startup phases and audio synthesis state. Those probes do
not change application behavior.

## 2026-09-22 stop — Nintendo logo renders; post-logo state trace ready

The user explicitly requested a handoff and stop. No Xenia process is running.
No reference tree was modified and no physical Xbox validation occurred.

- Branch: `shipyard/xbox360-9.2.3`.
- HEAD: `0cad9e225f77b3ff40530f56a5676913118f9d1d`.
- Working tree is dirty with the narrow runtime/resource/font diagnostics and
  fixes listed by `git status`; none of this session's work is committed.
- Complete generated game rebuild: 696/696 C units passed.
- Complete application receipt: 1,836 verified PPC objects and all 1,094
  application translation units.
- Genuine linker and ImageXex returned zero.
- Fresh, complete, **not yet staged or run** XEX:
  `scratch/link-integration/3Shipsty.xex`.
- Fresh XEX size: 45,834,240 bytes.
- Fresh XEX SHA256:
  `146e9e6f44b3a09a286c1ce7f8e8c870419419add34682ebf51d26e36894d5ea`.
- Currently staged older diagnostic XEX:
  `scratch/runtime/3Shipsty/3Shipsty.xex`, 45,867,008 bytes, SHA256
  `d20852ab3c2b86de9864629d07fdc7ddf21b914442e11796e00a9d600fa7a6b4`.
  Do not mistake it for the newly linked XEX.

### Newly proven runtime boundary

The resource-init constructor fix removed the false `SHAD` factory/version
failure. The genuine renderer compiled real shaders, issued the first Fast3D
draw, completed native GUI/end-frame/Present, and the user visibly saw the
spinning Nintendo N. After the logo, the user observed a black screen. Xenia
remained responsive and no guest exception/fatal was present.

The runtime log after the logo shows the real save/file-select path opening
`shipyard:\\Save\\global.sav`, checking absent empty-slot files `file1.sav`
through `file3.sav`, and polling Xbox input with `XamInputGetCapabilities` and
`XamInputSetState`. Therefore the remaining black screen is after successful
title rendering and at or beyond Title -> Opening -> Gameplay title scene ->
FileChoose. File creation/load, visible file select, audible output, gameplay,
and post-4.0.5 feature proof remain unproven.

The CPU framebuffer-readback diagnostic reported black even while the user saw
the Nintendo N, so that diagnostic reads stale/unresolved Xenos surface memory
and must not be used as visual truth. Framebuffer 0 did alias the presentation
surface, and draw counts continued increasing.

### Instrumentation prepared but not yet executed

The working tree adapts the useful 4.0.5 central gamestate boundary tracing to
the modern generated C path and adds bounded file-select fade values. It logs:

- every gamestate init/end, first frame, transition and destroy;
- file-select frame/menu/config mode, black-fill alpha, window alpha and
  controls alpha for the first 12 frames and selected later frames.

`tools/shipyard/tests/test_game_projection.py` passes all 11 tests. The full
generated source contains `GAMESTATE` and `FILESELECT` markers. Obsolete ImGui
substage trace macros are compiled out; the real font lifecycle fix remains.

A first attempt at this probe exposed stale generator receipts: the build
verified old generated game/ImGui objects, so that XEX could not answer the
state question. A targeted `prepare_game.py --output-full` then temporarily
reduced the full manifest to two C units; this was caught before linking and
repaired with the required complete command. Current evidence is clean:
696/696 generated C units, 1,836 total objects, link/ImageXex zero. The fresh
hash above is the first XEX containing the actual state trace, but it was not
staged or run because the user requested stop.

### Exact next action

Stage only the fresh XEX, launch the owned runtime, wait through the Nintendo
logo, then inspect the application log for `GAMESTATE` and `FILESELECT`:

```powershell
Copy-Item -LiteralPath scratch/link-integration/3Shipsty.xex -Destination scratch/runtime/3Shipsty/3Shipsty.xex -Force
Start-Process -FilePath scratch/runtime/xenia/xenia_canary.exe -ArgumentList 'scratch/runtime/3Shipsty/3Shipsty.xex' -WorkingDirectory scratch/runtime/xenia
Select-String -LiteralPath 'scratch/runtime/xenia/content/E0300000052D89D9/534F4809/00000001/3Shipsty/logs/Ship of Harkinian.log' -Pattern 'GAMESTATE','FILESELECT'
```

Use the owned signed-in profile. If FileChoose reaches frames and fill alpha
falls to zero while the display stays black, trace the file-select draw command
mix and Xenos state transitions against the working 4.0.5/Smash360 backend. If
the gamestate never reaches FileChoose or a fade value stalls, fix that exact
state boundary instead. Do not bypass Opening/Gameplay/FileChoose, hardcode a
scene, or replace the renderer.

## Latest runtime stop — ImGui first-frame stall (supersedes the state below)

The user explicitly requested a stop after the current black-screen failure was
isolated. Xenia is stopped. No physical Xbox validation has occurred.

- Branch: `shipyard/xbox360-9.2.3`.
- Production-fix checkpoint: `0cad9e225f77b3ff40530f56a5676913118f9d1d`
  (`fix: normalize writable application root`).
- Earlier startup-fix checkpoint: `2e6db2f08ebc3e8a4f30b7702433b4ccc464c6bb`
  (`fix: initialize Xbox startup runtime paths`).
- Latest staged diagnostic XEX:
  `scratch/runtime/3Shipsty/3Shipsty.xex`.
- XEX size: 45,834,240 bytes.
- XEX SHA256:
  `9ba8b77a6ea3d083f6d261553cd8d8b7a318f431de6871ecbc6a71f28f42fe86`.
- Fresh build: exit 0, 1,836 verified PPC objects, all 1,094 application
  translation units; fresh archive/link/ImageXex exits are all zero.
- Build manifest SHA256:
  `7bc477af040ae8eddc1d5f004597b57188d111d90f3290ec2fd927a382de90eb`.

The signed-in owned Xenia profile resolves the earlier storage failure. The real
application now mounts its save container, opens `soh.o2r` and retail `oot.o2r`,
handles absent optional `oot-mq.o2r`, persists/reopens
`shipyard:/shipofharkinian.json`, constructs current libultraship Context,
initializes native Xenos/XAudio2/controller services, and creates current game
framebuffers 3 through 7. This proves the working-directory and CRT-safe
application-root fixes in the genuine runtime path. It does not prove file
select, saves, audible output, gameplay, or a modern post-4.0.5 feature.

### Exact black-screen boundary

One-shot diagnostics establish this sequence on the first normal frame:

1. `GfxWindowBackendXenos::IsFrameReady()` enters and returns true.
2. `Gui::StartFrame()` enters.
3. `Gui::HandleMouseCapture()` returns.
4. the renderer backend new-frame step returns.
5. `Shipyard_ImGuiPlatformNewFrame()` returns after the real Xbox gamepad sample.
6. `ImGui::NewFrame()` is called, but never returns.
7. `GfxRenderingAPIXenos::StartFrame`, the first Fast3D draw,
   `GfxRenderingAPIXenos::EndFrame`, and `Present` are never reached.

The screen is therefore black because the first ImGui frame stalls before the
real renderer begins or presents; this is not evidence of a bad presentation
resolve. The narrower internal cause inside `ImGui::NewFrame()` is not yet
identified. Do not claim a specific ImGui subroutine or compiler defect without
another checkpoint trace. The ordered candidates are the actual current
`ImGui::NewFrame()` stages in `scratch/imgui-xdk/generated/imgui.cpp`: context
hooks/sanity checks, settings update, input-event processing, viewport/font
setup, keyboard/gamepad `NavUpdate`, mouse update, docking update, and window
iteration. Controller navigation is enabled and a controller is connected, but
that correlation is not proof that `NavUpdate` owns the stall.

Conclusive evidence:

- `scratch/runtime/xenia/boottrace-imgui-newframe-black-20260921-1439.log`
  - SHA256 `5c11e5cb87b3cba8d368219b49200f7ed2dd1cdaa560a57ef9c63c6bd924d7af`
- `scratch/runtime/xenia/boottrace-imgui-newframe-soh-20260921-1439.log`
  - SHA256 `06fb8a4928240a73eb2ad36fe96c33a19c3c8451192de238a6cad92e969ac817`
- Prior pre-render boundary trace:
  `scratch/runtime/xenia/boottrace-pre-render-black-20260921-1430.log`
  - SHA256 `6e12bc3fe7cd411105b6db7ca77ac5f1b2c3ec5c531dffd3e336b90367fac956`

### Dirty diagnostic-only files

The latest XEX includes uncommitted one-shot `BOOTTRACE` logging. These are not
runtime fixes and should not be checkpointed as a behavioral change:

- `platform/shipyard/presentation/window_xenos.cpp`
- `platform/shipyard/xenos/api.inc`
- `tools/shipyard/prepare_gui.py`
- `tools/shipyard/prepare_presentation.py` is reported modified only because of
  working-tree line endings; `git diff --quiet` reports no textual change.

Keep the diagnostics until the next internal ImGui checkpoint run, then remove
them before committing the actual narrow fix. The next experiment should add
one-shot checkpoints inside the generated current `ImGui::NewFrame()` stages,
through the existing `prepare_imgui.py`/projection source of truth, rebuild the
fresh receipt, and rerun the same signed-profile reproduction. Do not disable
the GUI, controller navigation, or real menu to get past the stall.

Reproduction:

```powershell
C:\Python313\python.exe -B tools/shipyard/build_xdk_project.py
C:\Python313\python.exe -B tools/shipyard/link_xdk_application.py
Copy-Item scratch/link-integration/3Shipsty.xex scratch/runtime/3Shipsty/3Shipsty.xex
Start-Process scratch/runtime/xenia/xenia_canary.exe -ArgumentList scratch/runtime/3Shipsty/3Shipsty.xex -WorkingDirectory scratch/runtime/xenia
```

Use only the owned runtime and its existing signed-in local profile. Re-query
process state; all PIDs in prior notes are stale. Reference trees remain
read-only.

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
