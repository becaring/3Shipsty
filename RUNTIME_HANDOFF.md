# 3Shipsty runtime resume point — 2026-09-22

Platform pin advanced to Shipyard `6a7f858`, baseline SHA-256 `dd3f0ae18d6d9287180ef40eff8a6daeab4faa3f6a78289fe3f07e1206de110d`. Shared member-default lowering preserves both interpreter and selected GUI header bytes, Smash's physical triangle certificate now uses an explicit Smash version trait, and modern resource variant projection uses physical Shipyard value types rather than a local duplicate. Focused host/PPC tests pass; no current full clean build, Xenia or hardware run. Modern triangle certificate integration and the 531 stale JSON include recipes remain open.

Platform migration now pins Shipyard `496b134`, baseline SHA-256 `5a13d73eca7b7700b8ebf95892672236c66ec596dd160a2aacd159453d9aac08` in both active consumers. Smash's triangle certificate header is physically Shipyard-owned and its stale stage shadow was removed; focused host/PPC and negative-dependency checks pass. Modern SoH does not yet consume that certificate. The last full XEX hashes below predate this relocation. Modern JSON's new clean-regeneration test passes, but its full project contract exposes 531 stale local include recipes. Do not infer new Xenia/hardware behavior or whole-tree clean-build parity.

Current architecture checkpoint: Shipyard `7db50f2cc8ad08ceb296fc55386da3561292573a`, baseline SHA-256 `841b7e02942c8b8d4bcfed73b8de37646c73126acaa8c101fd7780b3cee762a3` pinned by modern 3Shipsty and Smash360. Both use the physical six-slot Fast3D binding tracker, opcode lowerer and triangle splitter. Focused empty-stage PPC builds and physical-header negative dependency pass. Smash full link/ImageXex/native-link checks pass, XEX SHA-256 `775d5ba204f9edd32c42ffeec33e26e0cfc9bb6cfcc88329d3a33573eb358588`; modern's eight-shard full compile verified 1,844 PPC objects and genuine link/ImageXex produced SHA-256 `256b7bd0f424952a3eac6818bc28bc22f1407dcf5d3acbc838d3b8e053c9cc75`. No Xenia/retail test has been run for these changes. Whole-tree clean builds and several ownership boundaries, notably triangle reconciliation, texture cache policy and Smash's runtime donor, remain open.

Current priority changed on 2026-09-23: finish the Shipyard single-source platform migration for modern 3Shipsty and Smash360 before resuming consumer-specific optimization. This older runtime evidence and its code comparisons predate the Xenos/audio/filesystem/CRT migrations; `porting/SHIPYARD_OWNERSHIP.md` tracks active source/build ownership and `porting/POST_SHIPYARD_HANDOFF.md` is the provisional paused-work handoff. Historical SoH 4.0.5 is reference-only, not a migration or validation target.

Current shared-source pin is Shipyard `6707cfc`, baseline SHA-256 `9add30432b4ad3b330b3f5eae2d2c64e567d6c9034146a10aaeceb989d806fa2`. Smash's eight-shard application/libultraship build and native-link verification passed, yielding XEX SHA-256 `c04865d8b1714421713db592bcdb65986d98ec180f3008a078400d5a365c06cb`; there is no new Xenia/hardware evidence. Modern's full build at this pin is pending. Neither consumer has passed a whole-tree generated-state-free build at this pin.

The newer modern integration XEX at Shipyard `2c7fe70` compiled 1,844 PPC objects and linked/ImageXex; SHA-256 `17de66852e5070adf00afa416ed0cfc29747e3bec063ae0898b46727bc09a294`. It has not been launched in Xenia or copied to hardware and is not a final hardware candidate. The older 1,843-object XEX below is superseded.

The latest interim modern XDK build at Shipyard `32e325e` verified 1,843 PPC objects, linked and produced XEX SHA-256 `63ba755eca9d0a119fa728b4b930c8eb14e4477ebd6d920f9ef97103b319e070`. It has not been launched in Xenia or on hardware and is already being superseded by further shared-source migration. Do not infer a runtime regression or success from that compile receipt. See `porting/SHIPYARD_MIGRATION_REPORT.md` for separate gates.

## Current investigation: HD texture FPS loss and randomizer text

The user clarified Xenia was ~15 FPS in the title and ~11 FPS in gameplay
with the converted HD texture mod; removing it while retaining translation
restored ~60 FPS. The removed 70,525,755-byte `.o2r` was listed before
removal: 618 alt textures, 853,762,364 uncompressed bytes of potential payload
(not proven simultaneous residency), 212 records >1 MiB, 93 >4 MiB. The
separately supplied 654,820,398-byte root ZIP contains 37 nested archives
and is not itself that converted `.o2r`.

The current Xenos uploader is byte-identical to SoH360/Smash360. Its 16 KiB
identical-upload snapshot does not cover HD textures; large cache misses
create/fill new D3D textures. Fast3D has a 1,024-entry count-only LRU, and
replacement-release pressure above 8 MiB can force a framebuffer finish and
blocking collection. These are plausible contributors, but no per-frame
upload, residency or CPU/GPU timings were captured; do not assert cache
thrashing as proven. Owned Xenia also uses debug logging and 384/768 MiB
soft/hard host texture limits. Archive indexing is startup work; audio and
saves show no HD-specific repeated path. Per-draw cached player-limb loads
construct futures, but that baseline behavior is also in Smash360.

The active XDK endian projections correctly identify big-endian PPC. Audited
archive, texture, Fast3D, scene/skeleton, GPU, audio, save and network paths
show no new confirmed endian failure. Inactive raw LightEntry parsing and
O2R short-read acceptance remain bounded separate risks. The screenshot's
garbled randomizer combobox labels have a stronger source-level cause:
Option caches pointers to its own option strings, then XDK copy-assigns
temporary Options into Settings, preserving those now-dangling pointers.
The existing randomizer-options contract explicitly observes this pointer
mismatch. The tooltip refreshes its live pointer each frame, matching the
user's readable tooltip. No code or XEX change was made in this diagnostic
turn. Next narrow actions: repair Option pointer lifetime with a regression
check; separately, capture bounded per-frame upload/memory timing in a
controlled HD-vs-translation test before optimizing the renderer.

## Current: fixed mod MPQ boundary; final identity XEX and hardware pending

The black screen introduced when `game:/mods` became discoverable is fixed
in owned Xenia. `1ffe0eb74` selected the populated game mods directory;
`313004a10` draws a high-contrast controller cursor using the real ImGui draw
data. The first Portuguese OTR previously opened but its `(listfile)` read
failed with 1392; `OtrArchive::Open` then dereferenced the null result. A
host debugger showed a guest null read at this call site. Guest breakpoints
showed the aligned sector inflate succeeding and an unaligned sector failing
with zlib -3 (`"invalid code lengths set"`). The pinned StormLib unaligned
MPQ cipher helper byte-assembled its return DWORD as little-endian, which
poisoned the rolling key on big-endian Xenon after the first word. Commit
`8018f9714` replaces that unaligned word handling with native-order `memcpy`
for both encrypt and decrypt. The upstream submodule remains unmodified.

Tests: all 231 Xenon and 231 host StormLib objects, native-word endian
regression, and full pinned-host reads of both supplied OTR listfiles pass.
The full 1,836-object real application compiles, links and ImageXex succeeds.
Initial fixed test XEX staged in `scratch/runtime/3Shipsty/3Shipsty.xex` has
SHA256 `d3c068aed340a443d480caa9d0c83cd37063e8536f4e3d6621c90dd3243ca7b9`;
its embedded commit identity remains `313004a`, because the source checkpoint
followed the test build. Do not send that image to hardware. The owned Xenia
app log at `scratch/runtime/xenia/content/E0300000052D89D9/534F4809/00000001/3Shipsty/logs/Ship of Harkinian.log`
for this image shows 40 real `game:/mods` archives added (including both
Portuguese OTRs), zero listfile errors, `gui-ready` and `init-complete` in
`scratch/runtime/xenia/xenia.log`, and gameplay scene initialization. Xenia
temporary breakpoint and context-promotion settings were restored. The final
source-identity XEX and its validation are recorded below. Physical boot,
visible cursor, Back menu and mod appearance on hardware remain unproven; do
not ask for repeated console copies.
The user visually confirmed Brazilian-translated gameplay. The user clarified
that the HD pack gave ~15 FPS at the title and ~11 FPS in gameplay in Xenia;
translation-only runs around 60 FPS. The pack was removed between those
observations, so the prior same-mod relaunch wording was incorrect. No
performance source code changed. Investigate HD resource residency and upload
churn before attributing the slowdown to a specific layer.

The final source-identity build from code commit `55ce76c50` then verified
all 1,836 PPC objects, genuine link and ImageXex. Staged only the new XEX:
`scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`262e2ffbcd4998a90574e7e2a3d42a218961b5553a66bec8c7641797e7314694`.
Its owned Xenia log records `commit=55ce76c`, `gui-ready`, `init-complete`;
the application log opens both Portuguese OTRs and initializes gameplay.
The user confirmed on this exact XEX: translated gameplay, working audio and
controls, roughly 60 FPS. The earlier first-chance C++ exception remains
nonfatal. This XEX is ready for one physical-console test. Copy only this XEX
over the previous XEX, preserving archives/mods/saves; test boot, Back menu,
visible right-stick cursor, preset popup, translated assets, audio, gameplay
and save. No physical result for this image yet.

## 2026-09-22 modern menu and cursor candidate; retail validation pending

The user reports that the earlier diagnostic XEX `27f931b5...` booted on the
physical console into file select and gameplay, with audio, controller
movement, save reload, and a completed randomizer seed. Back did not open the
Enhancements menu, and the first-run preset popup could not be controlled.
Watson showed a first-chance `0xE06D7363` C++ exception after
`gui-windows-ready`; the user continued past it and the application booted.
The two supplied minidumps have zeroed stream-directory entries, so they do
not provide a reliable throw-site call stack. Do not conflate this nonfatal
exception with the independently explained menu-input failure.

The Xbox GUI registered `CVAR_IMGUI_CONTROLLER_NAV=1` before InitOTR's config
migrations. Version 2 invokes `CVarClearBlock`, which calls `Load()` and clears
all unsaved CVar defaults. On a fresh HDD profile, `Gui::DrawMenu` then sees
0 and ignores Back. Commit `27815b3ce` restores the default after migrations
without overriding an explicit saved value. Commit `fd8386fd5` allows the
modern standalone modal to receive controller navigation and blocks its A
press from leaking into gameplay. It also restores Smash360/SoH360 donor-style
right-stick pointer mode for the real ImGui UI: A/B clicks, triggers scroll,
R3 toggles pointer/navigation. No alternate menu is introduced.

Tests: application contracts, modern menu contracts, native ImGui host input
fixture, targeted PPC GUI/modal/input/startup TUs, fresh complete 1,836 PPC
objects, genuine link and ImageXex all pass. Staged *only* the fresh XEX at
`scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`7f3311a96ce40888a62b136178baf52604dffae90e57a1d6d29a3d266e203890`.
The existing `soh.o2r` and `oot.o2r` were not changed. Owned Xenia log for
this exact commit shows archive mounts and `gui-ready`/`init-complete`.
The log also shows one caught `0xE06D7363` first-chance exception between
`gui-windows-ready` and `gui-ready`; it proceeds through init. Visible GUI
interaction in Xenia and this candidate's console input are not yet proven.
One physical run should use this exact XEX only after the user is ready; test
Back, popup buttons/cursor, gameplay input, and save without recopying O2Rs.

## 2026-09-22 retail boot log localizes post-SaveManager gap

The user confirmed XEX SHA256 `ddbdf8dd59bc6d6c895bca9909e73d14b0c0d169f8706b500b2f7b40f0697859`
again powered off after HDD selection. The supplied real-hardware
`scratch/runtime/3Shipsty/3Shipsty.bootlog` is 655 bytes, SHA256
`edb6a51cb33d78a0aab2f5a7486697ff11e7b1e844810b95c70eea495b0b0609`,
preserved independently as `scratch/runtime/retail-9117bce.bootlog` before
staging another XEX. It records the actual `9117bce` application thread
through `entry`, `mounted`, `constructor-ready`, `pre-context`,
`logging-ready`, `audio-ready`, `factories-ready`, `randomizer-ready`,
`context-ready`, and finally `save-worker-ready` at tick 1299055. Thus this
title **can write and flush `game:` on the console**, and the real selector,
XContent mount, archives, Context, native audio initialization, resource
factories, randomizer context, and SaveManager construction all returned.
This does not prove the newly started save worker completed any task.

The next uncompleted InitOTR lines register six ConfigVersionUpdaters, run
their migrations and save, then register GUI windows and menu elements. The
old log cannot distinguish those operations or a concurrent worker fault.
No `startup-fault` receipt was supplied from this run. The current owned
Xenia profile is already at ConfigVersion 6, so it does not establish the
fresh-HDD migration behavior. Do not infer a migration root cause yet.

Commit `9b24272450a0f8dc452063da080ba80626ed6571` adds only flushed
`game:` trace calls within that exact gap: after updater registration, before
and after each actually-run migration version, before/after Config::Save,
after migration completion, and after GUI-window setup. It makes **no extra
XContentFlush calls**. The original/projected Config host behavior matches,
ten application tests and both affected PPC TUs pass, and a fresh complete
1,836-object build, genuine link and ImageXex pass. Staged XEX
`scratch/runtime/3Shipsty/3Shipsty.xex` is 45,703,168 bytes, SHA256
`27f931b533f41fb08eae1eaf888bcfd57117e1af3b3919a13f06b9d24926ecdc`.
Only the XEX changed beside the verified archives. One hardware run with
this exact hash should supply the new `3Shipsty.bootlog`; a last
`config-vN-begin`, `config-save-begin`, `gui-windows-ready`, or later stage
directly selects the next code boundary. This is diagnostic, not a claimed
boot fix. Do not copy the unrelated CON evidence file beside the XEX.

## 2026-09-22 diagnostic receipt gap fixed; one retail run needed

The user tested XEX `b4e9ebd4...` and found **no**
`game:\3Shipsty.startup-fault`. The old handler ran only for SEH, C++
terminate, or a handled InitOTR error. Direct Xenos/audio `abort()` calls
bypassed it, and `CreateFileA(game:)` failure was not reported. Therefore
absence of that sidecar cannot establish that `game:` is unwritable or locate
the shutdown. No root cause is claimed.

Code commit `9117bce812de2e8aa156ac478355d35ca69a9355` adds a bounded
hardware diagnostic on the genuine 9.2.3 boot path. It appends and flushes
`game:\3Shipsty.bootlog` at ordered InitOTR/Context/application boundaries,
starting before the storage selector. After a successful real XContent mount,
it also writes and XContentFlushes **only two** save-container checkpoints,
`boot-mounted.txt` and `boot-pre-context.txt`, before the async logger starts.
Each includes `game_write_error`, allowing the first retail result to say
whether `game:` actually accepted a write. The known Xenos and XAudio2
fatal-abort paths now record operation/HRESULT before abort, and a SIGABRT
handler covers other CRT aborts where the XDK delivers that signal. Faults
write both `game:\3Shipsty.startup-fault` and, after mount,
`shipyard:\startup-fault.txt` with XContentFlush. A kernel/RGH power-off or
failure inside XContentFlush may still preempt a final receipt; the committed
checkpoints remain the fallback. These are diagnostics, not a gameplay fix.

Ten application tests, the targeted real OTRGlobals/Context/XAudio2/Xenos PPC
compiles, fresh 1,836-object full build, genuine link, and ImageXex passed.
The map contains `RecordBootStage`, `RecordStartupFatal`, and the startup
handler. Staged XEX: `scratch/runtime/3Shipsty/3Shipsty.xex`, 45,703,168
bytes, SHA256 `ddbdf8dd59bc6d6c895bca9909e73d14b0c0d169f8706b500b2f7b40f0697859`.
Only that XEX was staged; the O2Rs and speech data are unchanged. A hidden
owned-Xenia launch reached emulator configuration but did not load the title,
so it is **not** runtime validation. The user-supplied untracked root
`3Shipsty` CON evidence file remains untouched.

For one physical test, replace **only** the console XEX with this hash. After
the selector/shutdown, copy whichever exist: the game-directory
`3Shipsty.bootlog` and `3Shipsty.startup-fault`; plus the newly updated HDD
save package `Content/<profile>/534F4809/00000001/3Shipsty` containing the
two checkpoint files or `startup-fault.txt`. Do not copy the CON beside the
XEX as a runtime input. The missing/present combinations, including
`game_write_error`, determine the next narrow investigation.

## 2026-09-22 same retail shutdown; bounded hard-fault receipt ready

The user confirmed the physical console ran staged XEX SHA256
`562d2ac49b1eefba4a8f89ca6b5322693fd95f6b87909cd2b756925938f5d123`.
It showed the HDD selector, paused the same 5–6 seconds, then powered off
without the new startup-error dialog. The supplied HDD `3Shipsty` package at
`scratch/runtime/3Shipsty/3Shipsty` is 40,960 bytes with the **same SHA256**
`7de209c096e75d776a9a2e58f6daf4a0912a51cf8c7d7b19c99dadcafefc8d98`
as the earlier empty package. This proves the processor-0 pin did not resolve
the shutdown. The empty CON cannot locate the fault because the clean app
does not flush startup writes. Absence of a dialog does not by itself prove
where the fault occurred; it may be a hard exception, a worker terminate, or
a failure to present the error UI. Do not claim storage or speech as root cause.

Commit `358435e6398b03cc6da1e3ddc4f50c70c770931f` adds one best-effort,
on-failure-only native fault receipt. It installs the XDK unhandled-exception
filter and C++ terminate handler before the real `InitOTR`; the existing Xbox
projection of libultraship CrashHandler does not replace that filter. It also
records a handled startup error *before* requesting the XAM dialog. A fault
writes `game:\3Shipsty.startup-fault` beside the XEX with build commit,
failure kind (`seh`, `terminate`, or `handled`), exception code, fault address,
thread ID, and any handled error text. No file is opened on a successful
startup, and no XContent flush or save path is changed. This is a diagnostic
boundary, **not a claimed boot fix**. If the game directory is unwritable or
the console powers down below the process exception layer, no receipt may
survive; do not infer success from its absence.

The native game, Context, and OTRGlobals targeted compiles, ten application
tests, 19 game projection tests, fresh complete 1,836-object XDK build, genuine
link and ImageXex passed. The linked map contains
`Shipyard_InstallStartupFaultHandler`, and no temporary boot-stage calls are
in generated startup. Staged `scratch/runtime/3Shipsty/3Shipsty.xex` is
45,703,168 bytes, SHA256
`b4e9ebd4fd2ef843645ab9243fd54f145e10011239efd5d76321a1b1da898c03`.
Physical boot of this image remains untested. For one bounded console run,
copy **only** this XEX (retain O2Rs/speech data and do not copy the separate
CON evidence file). If it shuts down, copy `3Shipsty.startup-fault` from the
game directory if present; its address can be resolved against
`scratch/link-integration/3Shipsty.map`. If absent, report that explicitly.

## 2026-09-22 donor-parity audit and one consolidated hardware candidate

Read-only audits against both working ports found one definite missing native
startup contract: SoH360 and Smash360 pin the title/render thread to Xbox
hardware thread 0 before XAM, graphics, or worker startup; the 9.2.3 entry
did not. Commit `dd7ad363329e99de777efc3297ad6c065e7e8f76` adds that pin
at the real generated C entry. It also catches native/C++ initialization
failures around the unchanged real `InitOTR`, reports the operation and Xbox
error code in an XAM dialog, and returns cleanly instead of allowing an
exception to escape before the game's crash handler exists. The XAM error
dialog now presents on the already-created native D3D device while pending.
The unused temporary game-directory boot trace is removed. These are parity
and failure-handling fixes, **not proof of the retail power-off cause**.

The same audits found no missing generic thread implementation: Shipyard's
`joining_thread` matches Smash360's, which also uses it for a resource pool.
Role-specific audio/save placement is a future performance/parity question,
not justified as this crash fix. The selector/XContent mechanics and D3D
device reuse match the working donors. Modern 9.x configuration/log/mod paths
in the CON and extra SaveManager/randomizer work are application differences,
not evidence of a dropped 4.0.5 implementation. An empty fresh CON does not
locate the fault because clean startup does not flush STFS writes.

The native startup-error host contract, nine application tests, 19 game
projection tests, selector test, targeted Context and OTRGlobals PPC builds,
fresh 1,836-object full XDK build, genuine link, and ImageXex pass. Staged
`scratch/runtime/3Shipsty/3Shipsty.xex` is 45,703,168 bytes, SHA256
`562d2ac49b1eefba4a8f89ca6b5322693fd95f6b87909cd2b756925938f5d123`.
The generated build identity is `dd7ad36`; no `RecordNativeBootStage` or
`3Shipsty.boottrace` call remains in generated startup. An attempted owned
Xenia launch produced a process but no user-visible window or title log; it
was stopped and is **not** a smoke-test pass. Physical-console behavior of
this new XEX is untested. Copy only the XEX beside the existing O2Rs and
speech data, never the unrelated `3Shipsty` CON evidence file. One retail
attempt should now either boot farther or expose a native startup error code;
a silent power-off would point away from a catchable native startup failure.

## 2026-09-22 clean retail XEX result; fresh package also fails

The user confirmed staged XEX SHA256
`9d95425e535ba41a018e78c3e52bf982911790725336f7f1edd643f090c3e303`
reached the storage selector and powered off after HDD selection. Re-copying
the old HDD CON yielded the identical `d2d0ef81...` bytes. The user backed
up and removed that old container, then retried the same XEX: it powered off
again. The newly created HDD CON, read only, is 40,960 bytes, SHA256
`7de209c096e75d776a9a2e58f6daf4a0912a51cf8c7d7b19c99dadcafefc8d98`.
Its committed file table is empty. This excludes old-container corruption as
the sole cause, but **does not establish a pre-`RunExtract` boundary**: the
clean XEX has no startup `XContentFlush`, so attempted writes may not survive
an abrupt power-off. The physical `XContentCreate` return code and later fault
site remain unknown. Do not infer SaveManager/speech or a mount failure from
the empty CON. The user's backup of the old CON also exists separately in the
owned workspace; preserve both copies.

## 2026-09-22 newest retail result and clean hardware retest

The latest user-supplied retail HDD CON at
`scratch/runtime/3Shipsty/3Shipsty` is 86,016 bytes, SHA256
`d2d0ef814f9a090371d1a34e865e98137bbae364422da75539a17f1b9d35808e`.
Read only: the committed STFS file table contains `mods`, stages 1–5,
`logs`, and `Ship of Harkinian.log`. Its log records real XAudio2 PCM
initialization and the 9.2.3 startup line for `7f174a1`. Stage-6 text is
present in the last raw data block, but no stage-6 directory entry committed.
The console powered off after selecting the HDD, with no fatal message. This
proves the logger fix reached retail, not that `OTRGlobals::Initialize` fully
returned. A stage-6 container flush failure or a later crash remains possible.

Code review compared the native selector/display, storage and worker paths
with the hardware-proven Smash360 and 4.0.5 ports. The selector and Fast3D
reuse one D3D device. The concrete extra retail STFS workload was the
temporary `RecordBootStage` call: it made six startup `XContentFlush` calls,
including one after the async log sink opened in the same container. Smash360
flushes for real saves and shutdown, not boot breadcrumbs. Commit
`a7e92f2f7` removes only the temporary markers and their repeated flushes.
The genuine logger, save mount, XAudio2, archives and 9.2.3 application remain.
Seven startup tests, fresh 1,836-object XDK build, genuine link/ImageXex pass.
The new staged XEX is `scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`9d95425e535ba41a018e78c3e52bf982911790725336f7f1edd643f090c3e303`.
An owned hidden Xenia process did not load the title; that smoke attempt is
inconclusive and was stopped. Next: copy **only this XEX** to hardware beside
the already-verified O2Rs and speech data, not the user-supplied CON in the
same staging folder. If it still powers off, copy the newly updated HDD CON
and inspect its real log. Xenia trace shows the next operation after stage-6
flush is a native worker creation from the modern SaveManager; speech and GUI
follow later. Missing main/worker affinity relative to Smash360 is a review
finding, not yet a proven crash cause. Do not stack those changes without the
clean hardware result.

## 2026-09-22 logger boundary fixed in source; retail retest required

The second user-supplied HDD STFS package (read only) is a valid 77,824-byte
CON file, SHA256
`0612bdc119285fee6f07e5d5c6edaa711bae21064e8f1f5ea5efc5c7d35cca1c`.
File table: `mods`, `boot-1-mounted`, `boot-2-preflight`,
`boot-3-archives`, `boot-4-config`, `boot-5-logging`; no
`boot-6-context`, `boot-7-logging-failed`, or `logs` entry. Stage 5 was
originally written immediately after `Context::InitLogging` regardless of its
boolean result. The real method catches `spdlog_ex` and returns false on
file-sink failure; the 9.2.3 caller then unconditionally dereferenced the
logger. The absent logs directory is consistent with that exact fault.

Code commit `7f174a11eec3248562af811daf5fcbf6adeba336` projects the real
Context logger onto a native preferred path and creates its directory through
`xbox_compat::filesystem` before constructing the unchanged spdlog sink.
`OTRGlobals::Initialize` now checks the return before dereference and writes
`boot-7-logging-failed` on failure. Targeted XDK compiles and source-order
tests pass; fresh full 1,836-object build/link/ImageXex produced staged XEX
`scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`286c487203439042c0054f36fb1bd217b3ebbdc3953b42fecd3ef7506eb6241b`.
Owned Xenia log at `[03:00:30.058]` identifies genuine 9.2.3 and commit
`7f174a1`; stages 1–6, real log, save metadata and scene startup followed.
Xenia had an existing logs directory, so retail verification is still
required. The user-supplied STFS file currently sits beside the staged XEX
for evidence only; never copy that file back as part of the runtime package.
Keep the O2Rs and speech data unchanged. If hardware fails again, copy the
fresh HDD package and compare marker file timestamps with this attempt;
stage 7 specifically indicates logger failure. Remove all temporary boot
markers from source after hardware boot is confirmed.

## 2026-09-22 retail post-mount crash: diagnostic retest next

The retail `3Shipsty` HDD save package supplied by the user was a valid
57,344-byte STFS `CON` package, SHA256
`23ce7ba95803282cd905946f626bc7d6a8a7e8ccac603732e666e3d36d909106`.
Its title ID is `534F4809`; read-only file-table inspection found the `mods`
directory and no other entries. Therefore the previous XEX successfully
completed the selector and `XContentCreate`, then entered the real
`OTRGlobals::RunExtract` code far enough to create `mods`. The generic RGH
"fatal crash intercepted" screen gave no code, and a missing log is not
conclusive about flush timing. Do not keep changing the storage selector.

Commit `9dfa266bd849fd6bfe43af3a8b0497c68005ac53` adds only bounded
pre-logging breadcrumbs persisted through the real XContent mount. Fresh
1,836-PPC-object build/link/ImageXex produced diagnostic XEX
`scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`4c3078779b058761ac6558d5d6a7b1a68f288633ee9bf7ebb7d617a9a5e70622`.
Owned Xenia created all six files (`boot-1-mounted` through
`boot-6-context`) and reached save-slot metadata initialization on this XEX.
The marker sequence is: 1 mount complete; 2 RunExtract/preflight complete;
3 optional archive discovery complete; 4 configuration/CVars complete;
5 logging initialized; 6 full Context/application Initialize returned.
They are temporary diagnostics, not part of the desired final image.

Run this XEX **once** on the HDD and, if it crashes, copy the HDD
`Content/<profile>/534F4809/00000001/3Shipsty` package immediately. Inspect
the highest numbered `boot-*` entry in its STFS file table (the first run
starts with no previous markers). A container with only `mods` again would
instead implicate marker creation/flush or an earlier fault. Do not copy the
STFS container beside the XEX as a runtime input. Keep both O2R archives and
`espeak-ng-data` unchanged. The retail fault remains unresolved until this
evidence arrives, then remove the diagnostic path after the narrow fix.

## 2026-09-22 hardware storage-selector failure and new retest candidate

This supersedes the clean-hardware-candidate conclusion immediately below.
The user reports that XEX `50f702fe...` reached the storage picker on a real
Xbox 360, then crashed and powered down the console with no warning. No
retail return code or log was captured. Code inspection shows the Shipyard
storage path invoked `XShowDeviceSelectorUI` before creating D3D and blocked
on its overlapped result, while Smash360's physically verified path creates
the display and presents the pending OS overlay. On that title a selection
interrupted by sign-in notifications needed one same-profile retry; ordinary
cancel, changed profile, and failed presentation do not retry.

New code commit `b9fcc89e7e2a0aa07394e2b615cbeb43d58a49f5` implements
the same narrow platform/UI contract in `platform/shipyard/save-storage` and
`platform/shipyard/xenos`, keeping real XContent and 9.x SaveManager. Native
XDK objects, selector contract test, Xenos test, and save-schema parity pass.
Fresh metadata/full 1,836-object build/link/ImageXex produced the staged XEX
`scratch/runtime/3Shipsty/3Shipsty.xex`, SHA256
`75a0562a7bdee9cf938ba9cacf615c53a09a7d7e1f20b408b59fa53368d55a20`.
The `soh.o2r`, `oot.o2r`, and `espeak-ng-data` beside it are unchanged.

Owned Xenia run of this exact XEX logged native display creation before the
selector, attempt 1 `initial=997 result=0 extended=0`, application identity
`Ackbar Delta (9.2.3) ... Commit: b9fcc89`, real save-slot metadata, and
scene init. The owned app log is under
`scratch/runtime/xenia/content/E0300000052D89D9/534F4809/00000001/3Shipsty/logs/Ship of Harkinian.log`
at `[02:17:00]` onward; Xenia log is `scratch/runtime/xenia/xenia.log` near
`[2026-09-23 02:16:59]`. The retail power-off/root cause is not yet proven
fixed. Next action: copy only the new XEX, leave the existing archives/speech
package, retest on hardware, and capture any selector attempt/result or
power-off behavior before further changes. Do not reuse the earlier hash.

## 2026-09-22 clean hardware candidate — current authority

This supersedes older live-status claims below. Branch
`shipyard/xbox360-9.2.3`; code commit embedded in the XEX is
`2e89e891489b9335044bc874830d20f95418fcd2`. The complete 1,836-object
XDK build, link, and ImageXex succeeded after metadata regeneration and
diagnostic cleanup. Staged XEX: `scratch/runtime/3Shipsty/3Shipsty.xex`,
SHA256 `50f702fe34958ecc59bb07b2725a3a3ee4cd71d10e471e915ecb7c5bfa8958e1`.
Stage it alongside `soh.o2r` (SHA256
`7b375d854385a6cdb6843db89c18da981948e5b56986f479297cca33d2914a2f`),
`oot.o2r` (SHA256
`c2b5d5af24a52095a13e50479763ff4b9dcc1d8afe6a0788fbfc26a91b17c03c`),
and the entire `espeak-ng-data` directory already in that staged folder.
Do not transfer owned Xenia accounts or save state.

The user confirmed on this exact clean XEX: file select, gameplay, audible
audio, and controller input. Final-run log evidence begins at
`[01:51:56.339]` in
`scratch/runtime/hardware-candidate-app-20260922.log`, SHA256
`d2d8aee895a9eb4dae0e29b29fb14034fde0df9cb12ff68912a20d9c0d05a872`.
At `[01:51:56.340]` the app identifies genuine Ackbar Delta (9.2.3) and
commit `2e89e89`; by `[01:51:59.790]` the real Xenos framebuffer path runs;
save-slot metadata initializes at `[01:52:02.415]`; file 0 loads at
`[01:52:09.875]`; real scene init follows at `[01:52:10.222]`.
Earlier Xenia runs confirmed save creation/reload and default modern randomizer
gameplay. Fresh save write was not separately repeated on this exact XEX.

The old ~7.758s hint-table startup delay was Xenia first-use guest-function
translation, established by entry/body timing, not an archive/filesystem
stall. `6ee8eb7ba` splits the four modern hint initializers into ordered,
non-inlined 16-assignment chunks. Tests preserve all 1,370 upstream
assignments and order; the fresh-XEX hint interval fell to ~0.299s. Other
startup costs and hardware boot time need physical measurement. `fc4e15590`
stripped heavy framebuffer, audio queue, and boot diagnostics; no such trace
families occur in the final-run segment. Potential first-use shader hitches
were seen in Xenia, but no modern storage-owned disk shader cache exists yet.
Do not port an old cache speculatively: measure on hardware first.

Next step is physical Xbox 360 validation of this exact package: boot to file
select, launch/load gameplay, test controller, audio and save/reload, measure
startup and Hyrule Field hitches, and check speech if exercised. Re-query
process state before any more Xenia use; no stale PID is authoritative. This
is a hardware handoff, not a claim of physical-console success.

## 2026-09-22 verified gameplay/audio/background checkpoint

This supersedes all older claims below that audio is silent, the shop
background is broken, or game-C native byte order is unresolved. Current
branch `shipyard/xbox360-9.2.3`, proven endian-fix checkpoint
`8f55f53cfa771d99fb26867b04f92fe40406dfb8`.
The exercised game-C startup/JPEG projections were checkpointed as
`867a586d05e7817a517d33b804b8701639373bd4`.
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
