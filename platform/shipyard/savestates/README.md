# Pinned modern savestates

This provider compiles the entire actual 9.2.3 `savestates.cpp`, including all
snapshot copies, camera/demo/overlay/miscellaneous state, audio script relocation,
request processing and application bridge. The source, external declarations and
complete SaveStateInfo field layout remain tied to SHA-256 locked upstream inputs.

The canonical SaveStateMgr/request declarations remain owned by
`prepare_application.py`. This provider does not duplicate those classes or
define game/application services. Its only production generated files are
`soh/soh/Enhancements/savestates.cpp` and the unchanged `savestates_extern.inc`.

## Compatibility boundaries

| Class | Change | Preserved contract |
|---|---|---|
| A/B | `contains` becomes typed `find` comparison | Existing-key request acceptance, slot creation and missing-slot errors. |
| A | Projected scoped enums use `GetValue()` in switch/log formatting | Original discriminator values, default branch and returned statuses. |
| A | Remove `[[unlikely]]` | Same default branch; only a branch-prediction hint is removed. |
| D | Native `unique_lock<mutex>` | Same lock scope around complete Save and Load operations. |
| I | Explicit Context/Window/Gui/GameOverlay includes; rooted actor/header paths | Actual application/provider declarations, no substitute services. |

Every SaveState method body is checked byte-for-byte against upstream after only
the lock spelling change. SaveStateInfo and its full declaration inventory are
unchanged. Request queues, notifications and the OTRGlobals bridge are preserved.

These snapshots contain native runtime structures and heap copies. They are
in-memory snapshots for this running application, not OTR/O2R resources or a new
disk format. No byteswap is introduced. SeqScriptState saves pointer offsets from
gAudioHeap and reconstructs native pointers relative to that heap; the original
uintptr_t arithmetic remains intact.

## Required shared audio integration

The upstream `OTRAudio.h` declares `static ... audio`, which creates a different
mutex in every translation unit. That cannot protect the real audio worker from
savestate Save/Load. The root integration task owns the correction: one named
audio-state type, an `extern audio` declaration, and its sole definition in
OTRGlobals.cpp, preserving all fields and static zero initialization. This
provider does not edit that shared header. Cross-translation-unit mutex identity
and locking verification belong to that application integration.

## Build and evidence

```
C:\Python313\python.exe -B tools/shipyard/prepare_savestates.py --build
C:\Python313\python.exe -B tools/shipyard/test_savestates.py
```

The recipe consumes the existing full application compiler command and generated
dependencies, without rerunning shared generators. Its production object is
`scratch/savestates-xdk/xdk/savestates.obj`; prepend the provider's
`generated/soh` root when integrating its source.

Four tests pass: complete native PPC TU compilation, original/projected host
contracts, unchanged serialization/field/method inventories, and deterministic
generation. Host contracts execute eight actual methods and test missing gameplay,
unknown request, missing/existing slot, FIFO order, arbitrary slot selection,
snapshot value initialization, and relocation of twenty pointers across four
audio sequence players with sixteen loop counters. Test memory uses actual game
type declarations; no game or service function stubs are supplied. The three
live notification calls reached by this isolated host audit are excluded only
from its extracted methods, while real logging executes. All five notification
calls remain in the production TU.

`manifest.json`, `verification.json`, host `compile.json`/`run.json`, and native
`xdk/build.json`/log/object are under `scratch/savestates-xdk`. Native execution,
full live Save/Load, notification rendering, Xenia and hardware are unvalidated.
