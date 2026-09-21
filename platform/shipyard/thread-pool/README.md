# Pinned BS v4.1.0 projection for modern SoH

The owned upstream header is `upstream/BS_thread_pool.hpp`, from BS thread-pool
v4.1.0 commit `097aa718f25d44315cadb80b407144ad455ee4f9`. The original MIT license
is retained in `upstream/LICENSE.txt`. Upstream project:
https://github.com/bshoshany/thread-pool

The read-only reference's actual `HEAD` and `v4.1.0` tag were both resolved with
per-command `git -c safe.directory=...`; both equal the commit above. Its raw
header SHA-256 was
`fed5f7da0bc89fa747e65a8b3896344dc10f57c30d171b51e4fbde820b6d7c03`.
The owned LF-normalized copy is locked to
`1da8bb1562433cb0759d774182d0d6fa3b87a04c26f64c6886f640445bf68efe`.
`source-provenance.json` records those inputs, the donor generator and helper
hashes, and the exact git verification commands. No reference files were
changed and no reference generator was executed.

## Exact current consumers

`consumer-inventory.json` records source hashes and the audited contracts in
owned SoH `cb71e22a79bc5d1f688fa881795bbd93094895fc` and LUS
`fdcaf6336776d24a6408d016b0a52243f108f250`:

- `libultraship/CMake/dependencies/common.cmake:96` pins ThreadPool v4.1.0.
- `libultraship/include/ship/resource/ResourceManager.h` enables priority and
  pause. Its implementation submits value-captured identifiers/initialization
  data, returns shared resource and batch futures, submits void work and uses
  promises for cached results. The pool's futures remain real blocking results.
- `soh/soh/SaveManager.cpp:1213` copies `gSaveContext` into a separately
  allocated snapshot, then binds its pointer by value into `detach_task` on
  a one-worker pool. `SaveFileThreaded` owns/deletes that snapshot. The
  projection preserves callable capture lifetime and wait completion; it does
  not move serialization or game hooks onto another invented save pipeline.
- `soh/soh/OTRGlobals.cpp:446` uses one extraction worker and an optional
  `future<void>`. At line 720 it polls a zero-millisecond wait and only calls
  `get()` when ready. Owned future millisecond waits support that reached
  shape; the separate optional/consumer syntax projection is not implemented
  in this slice.
- `soh/soh/Enhancements/randomizer/randomizer.cpp:3457` uses an explicitly
  joined `std::thread`, **not a BS pool**. Its seed argument is copied into the
  thread. `Shipyard::Async::make_thread(std::bind(function, seed))` plus an
  owned `joining_thread` preserves that callable/argument/explicit-join shape.
  Current randomizer source is unchanged; application lifecycle integration
  and the native destructor's additional join remain work to review there.

## Projection boundaries

`tools/shipyard/prepare_async.py` extracts the actual locked BS methods and
emits `scratch/async-xdk/generated/BS_thread_pool.hpp`. Reviewed lowering keeps
the queue, priority ordering, counters, worker loop, pause, purge, task capture,
future submission and wait/destruction behavior. Native worker creation uses
the owned async primitives. Constructor initialization, range-free code,
type deduction and enum/attribute syntax are lowered for the XDK compiler.

Two explicit generic correctness fixes from the donor are retained and listed
in generated provenance, separate from mechanical lowering: keep the worker
completion predicate under `tasks_mutex`, and stop/join successfully launched
workers if a later worker creation fails. Thread-launch fault injection was
not performed in this slice; the cleanup path is source-reviewed.

Priority and pause configuration are required. Disable-exceptions,
wait-deadlock-check and native-handle options produce compile errors.
Unsupported APIs remain absent: reset, pool timed waits, multi_future,
block/loop/sequence helpers, optional TLS queries and native handle queries.
Future millisecond waits **are supported**. No use of those missing pool APIs
was found in the audited consumers. A one-worker task that submits another
task to the same worker and then waits still deadlocks, just as in BS; the
real ResourceManager batch correction belongs to its separate projection.

All inputs/helpers are SHA-256 checked after UTF-8 BOM removal and CRLF-to-LF
normalization before outputs are written. Generated source has stable owned
source mappings. Output is restricted to owned `scratch/async-xdk`.
`generated/provenance.json` records source/helper/generator/output hashes,
mapping operations, corrections and unsupported APIs.

## Commands and results

Run from `D:/Projects/3Shipsty9.x`:

```powershell
python -B tools/shipyard/prepare_async.py
python -B tools/shipyard/tests/test_async_generation.py
python -B tools/shipyard/tests/test_async.py
```

Executed successfully on 2026-09-20. The generator suite passed five tests:
repeat determinism and LF/CRLF equivalence, changed source without overwriting
valid output, changed helper before output, owned destination restriction,
and manifest/source authority.

The host driver builds the owned original BS header and the projected BS
header against the same contract using VS 2022 MSVC 14.43.34808, Windows SDK
10.0.26100.0, `/std:c++20 /EHsc /MD /W4`, and the real owned Win32 async backend.
Both printed exactly:

```text
PASS futures, save snapshot, resource shapes, extraction polling, priority, exceptions, shutdown, 512 wakeups, randomizer seed ownership
```

Both isolated detached-exception subprocesses exited with the expected
terminate-handler code 73. Futures were compared to original BS/std futures;
the snapshot/resource/seed structures are test fixtures rather than copies of
BattleShip consumers. The XDK test avoids a nested inline-lambda expression
unsupported by the older parser by submitting a named callable; actual modern
LUS performs the analogous inner submission through another method.

The native compiler is
`C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/cl.exe`, using
`/nologo /c /EHsc /D_XBOX /D_XBOX_VER=200`, real SDK headers, the generated pool
include root and `platform/shipyard`. It compiled the actual
`async/native.cpp` and the full contract's pool/future instantiations; both
object headers identify PowerPC BE COFF `0x1f2`. There was no XEX/link step.

Every compiler/run command, working directory, exit code and complete output
is retained under `scratch/async-xdk/host-{upstream,generated}/` and
`scratch/async-xdk/xdk/`. `scratch/async-xdk/verification.json` records matched
outputs and native object hashes with `target_runtime_executed: false`.

For integration, put `scratch/async-xdk/generated` before any upstream BS
include root, include `platform/shipyard`, and compile
`platform/shipyard/async/native.cpp` once. Explicitly project reached standard
future/mutex/condition-variable types to `Shipyard::Async` and map the
extraction duration/status spellings. No upstream consumers were edited or
whole game/resource manager translation units compiled by this slice.
