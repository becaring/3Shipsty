# Shipyard native async foundation

`native.h/.cpp` and `future.h` provide the owned `Shipyard::Async` namespace
for Xbox XDK and host Win32. These are real native workers, critical sections,
event-backed condition variables and blocking futures. Work is not run inline
as a synchronous compatibility shortcut.

The source was adapted from the read-only Smash360 generic async primitives,
with donor input SHA-256 values in
`../thread-pool/source-provenance.json`. Runtime and build use only owned files.
The generation contract in `tools/shipyard/prepare_async.py` verifies all four
owned helper files by normalized SHA-256 before generating the pool header.

## Contracts

- `mutex`, `lock_guard` and `unique_lock` provide lock ownership and explicit
  unlock/relock. Recursive use of `mutex` remains outside the API contract,
  like `std::mutex`, although the underlying native critical section supports it.
- `manual_reset_event` implements persistent publication, blocking wait and
  finite millisecond waits. `condition_variable` registers each waiter before
  releasing its external mutex, then synchronizes notification/removal to avoid
  lost wakeups and a notifier touching a destroyed waiter.
- `joining_thread` owns a native thread handle, moves ownership, explicitly
  joins and joins during destruction/replacement. It has no detach API.
  Self-join throws; an exception escaping a thread callback terminates, as an
  uncaught standard thread exception does. `thread-pool/native_support.h`
  exposes `make_thread(std::function<void()>)`, which owns the copied bound
  callable until the worker takes it.
- `promise<T>`, `future<T>` and `shared_future<T>` support value and void
  results, move-only returned values, shared repeated reads, exceptions,
  blocking completion and invalid-state errors. `future::get()` consumes its
  state even on a thrown task exception. Promise destruction publishes a
  preallocated broken-promise exception. A promise may be retrieved and
  fulfilled once; unsupported reference results fail compilation.

The one added reached API is `wait_for(Shipyard::Async::milliseconds)`, returning
`Shipyard::Async::future_status::Value`, on all value/void future/shared-future
forms. Modern SoH extraction uses `wait_for(std::chrono::milliseconds(0))` to
keep its UI responsive; the donor implementation lacked that method. Zero or
negative timeouts poll without blocking. Successful waits acquire the state
mutex before exposing readiness; they do not consume the future or rethrow a
stored task exception. Large finite durations are split into finite native
waits to avoid narrowing to the `INFINITE` sentinel. This duration adapter is
not a full `std::chrono` implementation. Consumers must project the reached
`std::chrono::milliseconds` spelling and future types explicitly.

`tests/test_async_contract.cpp` (under `tools/shipyard`) was written before the
projection. Its generated build initially failed on the missing millisecond
and wait_for API, then passed after that implementation was added. During
validation, pinned upstream source confirmed that an exception escaping
`detach_task` terminates rather than being swallowed. The test was corrected
to preserve this source contract: submitted task failures propagate through
futures, while detached failures are checked in an isolated host process.
The terminate handler is installed inside the worker because the MSVC CRT's
handler state is per thread in this test configuration.

## Verified scope

On 2026-09-20, host upstream/projected pool contracts agreed, and actual XDK
compilation of `native.cpp` and the full template-instantiation contract
produced PowerPC BE COFF objects (`0x1f2`). Five deterministic-generation and
fail-closed tests passed. Exact commands, results, integration and limitations
are recorded in `../thread-pool/README.md` and `scratch/async-xdk/*.json`.

The tests cover native worker identity, conditions/events exercised by 512
queued wakeups, blocked shutdown, invalid/abandoned/consumed futures, numeric
and void exceptions, move-only values, shared resource-shaped results,
single-worker save snapshot ownership, extraction polling, priorities,
pause/purge, explicitly joined seed generation and detached exception policy.
No XEX was built and no target runtime was executed. Native compilation alone
does not establish Xenia scheduling or whole-application shutdown correctness.
