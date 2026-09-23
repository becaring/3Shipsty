# Modern SaveManager and Shipyard storage boundary

Upstream authority is Shipwright `cb71e22a79bc5d1f688fa881795bbd93094895fc` (9.2.3).
`sources.lock.json` locks the complete SaveManager header/implementation and the
actual popup declaration, plus supporting source evidence. Reference code was
read only. The generator never executes or writes into a donor tree.

## Current compiled scope

`tools/shipyard/prepare_save_storage.py --build` produces three real PPC objects:

* `scratch/save-storage-xdk/generated/SaveSerialization.cpp`: 38 of the 42
  complete upstream SaveManager member definitions and 11 of the 12 C bridges.
  This includes the real constructor, single BS worker creation, SaveSection's
  SaveContext snapshot and dispatch, complete SaveFileThreaded serialization /
  publication / metadata / hook sequence, full load and metadata startup logic,
  all four base-version loaders, SaveBase, all three initial-file presets, global
  saves, section registration, copying and deletion, and the wait barrier.
* `platform/shipyard/save-storage/storage.cpp`: real device selector, XContent
  mount/flush/close and mounted-save path ownership.
* `platform/shipyard/save-storage/atomic_file.cpp`: actual Win32/XDK temporary
  file write, flush and replacement, shared by the native storage wrapper and
  the host filesystem contract test.

The generated **complete** `soh/soh/SaveManager.cpp` is retained as the next
integration input. It is not currently a passing full-TU recipe. The four
uncompiled members are `LoadRandomizer`, `SaveRandomizer`, `InitMeta`, and
`ConvertFromUnversioned`; the remaining C bridge is `Save_LoadFile`. The real
class and all of its declarations/members are retained. There are no substitute
definitions for the missing methods. This fragment cannot link an application
without them. Do not compile both the fragment and the eventual full TU.

Current full-TU dependency gate: canonical projected modern entrance-shuffler,
dungeon, static-data/location/hint-text, settings, and logic headers. Using old
fallback game-header copies mixes enum owners and produces redefinitions;
using upstream directly reaches unsupported modern syntax. Finish those real
headers/interfaces, then complete the full TU. This is ordinary pending port
work, not an architectural blocker or a reason to bypass randomizer saves.

## Startup and shutdown integration

Call `Shipyard::Storage::Mount(userIndex)` on the application thread with the
real Xbox UI available, before `SaveManager::Init()` or any save operation.
Default user index is 0, matching the primary donor. The storage boundary
creates the native D3D display before `XShowDeviceSelectorUI`, then continues
presenting the system overlay while its overlapped request is pending. Normal
Fast3D surfaces/context are initialized later on the same device. A selector
cancellation accompanied by sign-in notifications can retry once after the UI
hides, but only if the same offline profile remains signed in and no B cancel,
profile change, or presentation failure was observed. This mirrors the
hardware-tested Smash360 platform contract; it does not alter modern 9.x save
semantics. Other cancel/error results throw `Shipyard::Async::native_error`.
It does not silently fall back to a different device or pretend storage exists.

The content package filename is `3Shipsty`, display name is `Ship of Harkinian`,
and mount root is `shipyard:`. The requested device capacity is 16 MiB. Modern
save paths become `shipyard:\Save\fileN.sav`, the matching `.temp` files, and
`global.sav`. Game/resource archive paths remain owned by the application.

Keep the mount open while the real SaveManager and its BS worker exist. At
shutdown stop producers, run the real `SaveManager::ThreadPoolWait()`, complete
final save/configuration work, destroy/join SaveManager and any other writers,
then call `Shipyard::Storage::Shutdown()`. It flushes and closes XContent and
propagates failures. Never close the mount while a queued or in-flight save
can still access it. The implicit SaveManager destructor destroys its mutex
before its pool member, so the explicit pre-destruction wait is necessary.

Configuration/CVar path selection is outside this owned SaveManager boundary;
startup's application-directory/configuration policy still needs integration.
Do not route read-only resource archives into this content container.

## Changes and ownership

| Classification | Exact incompatibility / action | Ownership |
| --- | --- | --- |
| A | Alias declarations become typedefs; two DMIs move to the real constructor; range loops keep their original algorithms; integer to_string calls select the long-long overload. | Generic compiler compatibility |
| B | Real filesystem paths explicitly pass `c_str()` to XDK streams; map `contains` and two-argument `emplace` use equivalent find/insert; JSON `.items()` becomes the same native JSON iterator with key/value. | Generic library compatibility |
| B | Two save-metadata JSON/int comparisons use a bounded nlohmann 3.12 type-order/numeric helper, including unsigned-to-signed behavior and NaN. No shared JSON backend was edited. | Generic compatibility, currently located here |
| H | XDK incorrectly captures `SaveManager::Instance` as an implicit `__this` in nested lambdas within static methods. The namespace inline accessor returns the same actual singleton pointer and avoids the defective capture. | Generic compiler technique / SoH call-site projection |
| D | Existing current BS thread_pool and Shipyard native mutex adapter are used directly. There is no imported second save-worker queue, coalescer, or alternate save manager. | Generic Shipyard threading |
| C/E | Actual device selection and XContent lifetime; native file flush/replace followed by container flush. | Generic Shipyard platform; package identity is 3Shipsty-specific |
| E | Final-save publication checks stream state, flushes the temporary file, replaces without deleting the old file first, then flushes XContent. Global and metadata rewrites use the same atomic boundary. Copy/delete/backup operations commit the container. | Platform durability |
| D/E | SaveFileThreaded owns its copied SaveContext and lock with RAII, preserving the success-path deletion/callback order while releasing ownership on actual I/O errors. | Narrow failure/lifetime adaptation |

The primary donor's storage/device/flush implementation informed the platform
boundary. Its old 4.0.5 serialization, queue scheduling, settings coalescing,
shader-cache jobs, and game behavior were not imported. No Smash application
behavior or unrelated Xenos64 implementation was used. The modern BS worker
already has the native platform primitive backend, so reusing the donor queue
would have created a prohibited parallel system.

`WriteAtomicFile` assumes its caller serializes writers to a destination. The
XContent wrapper enforces that using its storage mutex. Failures before the
replacement preserve the prior file and discard the new temporary. A failure
of XContentFlush after replacement reports failure; rollback/power-loss
durability is not claimed. Existing modern detached-task exception policy and
game-thread error presentation still require runtime integration review.

## Endian audit

Modern versioned saves are JSON, not a native SaveContext memory dump. The real
field-by-field SaveBase/LoadBase code and JSON numeric conversion handle host
representation. No wholesale byteswap is introduced. SaveSection's memcpy is
between two runtime-native SaveContext objects on the same host and must not
swap. The native storage layer publishes opaque serialized bytes.

The pre-versioned `oot_save.sav` converter is a separate unresolved boundary:
upstream reinterprets bytes as native `SaveContext_v0` and accesses fields.
This legacy format has no portable endian marker here. Its raw desktop-host
layout/producer provenance must be established and a field-accurate conversion
implemented before compiling/enabling that method on Xenon. The retained
upstream converter is not evidence that its raw reinterpretation works on a
big-endian target. Do not invent a ROM-style blanket swap.

## Validation and reproducibility

Run from the owned repository:

```
C:/Python313/python.exe -B tools/shipyard/prepare_save_storage.py --build
C:/Python313/python.exe -B tools/shipyard/test_save_storage.py
```

Native recipes/object/source hashes are in `scratch/save-storage-xdk/xdk/build.json`.
PPC COFF machine `0x1f2` is checked for all three production objects.
`manifest.json` records source locks, generated hashes and exact fragment scope.

The host test executes actual original/projected base-save methods against the
complete real class layout with a test-only constructor that initializes its
state without linking game registration services. It compares 161 complete
serialized outputs: 32 varied current SaveContext states, all four base-version
loaders, older-schema missing-field defaults, short arrays, nested structs, and
the current schema round trip. Output SHA256:
`4b3182262d174e734e39e47a0aad9cb93d2f6324d04f65a9f9a58765ff7df400`.
The exact upstream character-copy leaf is linked; no fake game service is used.
All serialized key literals are checked across the entire projected source,
including the randomizer bodies awaiting full compilation.

The actual ThreadPoolWait method drains 1,024 jobs from the current BS pool on
the host before the pool is destroyed. This validates the wait/join boundary,
not live application save scheduling or Xbox worker execution.

The actual atomic file code writes all byte values, replaces with shorter/empty
content, and proves old-file preservation under sharing-denial and read-only
destination failures. A 13-value JSON ordering contract compares the helper
with original nlohmann for null/bool/object/array/string, signed/unsigned bounds,
floating-point values and NaN. Both original and projected runs agree.

No Xbox/Xenia execution, successful XContent mount, power-loss recovery,
randomizer save runtime, or physical-hardware save claim is made.
