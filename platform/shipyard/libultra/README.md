# Pinned LUS libultra and remaining bridges

`tools/shipyard/prepare_libultra.py --build` projects the eight exact
`src/libultraship/libultra/*.cpp` units plus `controllerbridge.cpp`,
`gfxbridge.cpp`, and `resourcebridge.cpp` from LUS
`fdcaf6336776d24a6408d016b0a52243f108f250`. All 76 function definitions and
overloads remain, including upstream empty implementations. `os_time.cpp` is
already empty upstream and is reported as such. Eleven upstream translation
units and one Shipyard platform unit compile to verified Xenon COFF objects.
Normalized source/header hashes and the owning LUS CMake file are locked.
No upstream or reference file is changed.

## Ownership and final linking

These files belong to the release: LUS `src/libultraship/CMakeLists.txt`
includes both directory globs in its **static library**. SoH excludes the old
`src/libultra/io` and `src/libultra/os` directories, but its real `soh/stubs.c`
also defines five methods present in this library: `osCreatePiManager`,
`osWritebackDCache`, `osWritebackDCacheAll`, `osInvalICache`, and
`osInvalDCache`. They remain owned by the application. All four cache functions
are in the unneeded `os_cache.obj`; `os_pi.obj` has no current SoH callers.

**Do not flatten these objects into the application's final link or use
whole-archive.** The recipe writes `scratch/libultra-xdk/xdk/shipyard_libultra.lib`
with normal member extraction, preserving upstream ownership without deleting
methods or manufacturing alternate names. Compile-only project inclusion is
fine; final linking must keep the archive boundary (or incorporate these
members into the overall LUS static archive). `ownership.json` checks the
77 public C symbols against all 696 compiled application C objects and confirms
exactly those five expected, inactive member collisions. This is an ownership
audit, not evidence that the complete application links.

## Narrow adaptations

| Category | Boundary and reason | Preserved contract |
| --- | --- | --- |
| B, C | Replace SDL controller initialization/database discovery with the existing real XInput-backed ControlDeck path | `osContInit` still resets bits, updates status, and calls the real deck's `Init`. Full pad clearing, `WriteToPad`, current-port rumble and motor channel assignment remain. Xbox does not parse an SDL controller mapping database. |
| B, H | Replace unavailable chrono ratio aliases with `NowCycles`, using the existing Shipyard steady clock and overflow-safe integer conversion | N64 46.875 MHz clock, integer truncation, all upstream set/get/count arithmetic retained. The source's `osSetTime` addition is intentionally not changed. |
| C, D | Replace the SDL 16 ms repeating VI timer with the existing native event and joining-thread services | Real worker calls the complete upstream `__lusViCallback`, queues the same VI message, honors the callback's next interval or zero cancellation, and owns/join-cleans all workers. No rendering or application loop is added. |
| A | Qualify the real `std::static_pointer_cast` in `GfxSetNativeDimensions` because XDK misses the unqualified explicit-template call through ADL | Same shared owner, weak interpreter acquisition, exact native dimensions call. Dynamic cast and null-result paths in pixel-depth methods remain. |
| B | Narrow umbrella headers to the actual libultra declarations and needed real service definitions | Avoids unrelated SDL/desktop header dependencies; all methods retained. Resource bridge methods use real ResourceManager and archives, with no providers substituted. |

`StopTimers()` stops and joins workers. Call it during orderly application
shutdown **before destroying callback queue storage**. The registry also joins
at process teardown, but that fallback does not extend caller-owned queue
lifetimes. The present VI callback only enqueues; it must not recursively stop
or add timers while registry shutdown is joining it. A stopped registry accepts
new timers, matching reinitialization needs.

The constructor warning about passing `this` to the worker is expected: all
callback values and the stop event precede the worker in declaration and
initialization order. Failed timer creation returns false, like SDL's failure
result; the upstream `osCreateViManager` intentionally ignores that result.

## Endian and behavior boundaries

Message queues contain **native runtime unions, counts and pointers**. They are
copied without swapping. PI DMA here is the release's native memory copy, not a
new GPU DMA implementation. EEPROM reads/writes preserve file bytes; no implicit
word conversion is added. Resource bridge byte/size/pointer queries delegate to
the actual modern resource system; conversion remains at its serialized input
boundaries. This work does not alter controller button width: production uses
the release's 32-bit button definition.

Upstream limitations remain explicit: message queues ignore the blocking flag
and have no synchronization; `osJamMesg` rejects an empty queue and permits a
full queue to overfill its count. Upstream audio/PI/cache no-op bodies and the
EEPROM `default.sav` behavior are unchanged. Those functions are not evidence
of modern SoH save or XAudio execution. Xbox GPU coherency belongs to its actual
render backend, not these legacy CPU cache no-ops.

## Verification and limits

Run `python -B tools/shipyard/test_libultra.py` after the native build. It:

- compares 65,536 operations through complete original/projected queue code,
  exercises 512-byte real PI memory copy, native pointer mapping and cache
  entry points; digest `3070488509590722794` matches;
- checks 200,004 exact N64 clock conversions, including signed 64-bit limits,
  and executes the actual native steady clock;
- runs real Win32 native worker/event implementations for repeated callbacks,
  next-interval changes, zero cancellation, explicit stop/join, reuse and
  idempotent stop;
- verifies all production function signatures/overloads remain and audits
  actual PPC public symbol ownership against the current application C build.

Host queue tests only narrow the original umbrella header and do not replace
Context, resources or graphics services. Resource/graphics/controller bridges,
EEPROM and full controller/rumble paths have native compilation evidence, not
host runtime substitution. Xenia and physical Xbox execution remain pending.
