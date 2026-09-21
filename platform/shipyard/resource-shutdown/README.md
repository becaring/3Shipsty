# Resource work quiescence

The application must stop and join game/audio/network producers, release locks those workers might need, and retain a **strong real `Ship::Context` reference** while draining resource work:

```cpp
context->GetResourceManager()->WaitForPendingTasks();
Shipyard::Async::wait_for_detached();
// Only now continue Context/resource teardown.
```

These are application-thread barriers. Do not call a barrier from a worker it waits for, from the corresponding callable/capture destructor, or while holding a resource/application lock needed by those workers. They do not permanently close submission: stopping external producers is the caller's responsibility. Calling a barrier and then allowing new work before teardown is not safe.

The pinned resource-to-codec direction is the important order here: resource-factory jobs launch the MP3/FLAC/Ogg detached decoder workers. Drain the real resource pool first so no factory can launch a codec after the detached wait. Current codec workers consume their captured AudioSample/File/initData and do not submit new ResourceManager jobs. If future worker implementations introduce reverse submission, the owner must review that dependency rather than assume one pass remains sufficient.

## ResourceManager adaptation

`tools/shipyard/prepare_resource_manager.py` adds one nonvirtual method to the canonical generated class and source. It adds no state, replacement cache or alternate pool. `WaitForPendingTasks` uses the existing actual `mThreadPool`, unpauses it, then calls its existing `wait()`.

Unpausing is intentional: BS v4.1.0 considers `(paused || tasks.empty())` when deciding that `wait()` has completed. A paused pool can therefore report completion while retaining queued callable captures. The current ResourceManager pauses when no archives loaded. The shutdown method drains any already accepted queued jobs against the existing ResourceManager interfaces and their normal missing-resource results, rather than dropping jobs or silently leaving their ownership until Context has disappeared. Do not treat this API as a pause-preserving runtime wait.

The destructor calls the same barrier and resets the actual pool in its body. This joins the existing native workers while all ResourceManager members still exist. The original member order declares `mMutex` **after** `mThreadPool`, so automatic reverse-order destruction otherwise destroys the mutex before the pool's destructor waits for workers. The explicit reset corrects that lifetime boundary without rearranging the class or changing its instance layout.

The destructor is a defensive member-lifetime barrier, **not a replacement for the application-level call while Context is strong**. Actual `Context::GetInstance()` locks `Context::mContext`, a weak pointer. Once the last strong reference starts Context destruction, ResourceManager cannot resurrect it. The same strong-owner requirement applies on partial-initialization/error paths that admitted resource work.

For a targeted regeneration that touches only the two canonical ResourceManager files and their manifest entries:

```powershell
C:/Python313/python.exe -B tools/shipyard/prepare_resource_manager.py --lifecycle-only
```

Normal full generation applies the same lifecycle transformation. Pinned source/helper locks remain checked. No Context/application source, pinned upstream file or reference tree is edited by this module.

## Detached codec tracking

`platform/shipyard/async/detached.cpp` retains its real `CreateThread` call, 128 KiB stack and immediate `CloseHandle` ownership. It uses the existing Shipyard native mutex/condition-variable primitives for an active-work count. This adds a dependency on the already existing `async/native.cpp` implementation; no new pool or thread manager exists.

The callable copy is created before registration, so copy/allocation failure cannot leave a counted job. Registration happens **before** transferring the callable pointer to `CreateThread`, preserving the existing immediate-completion rule. On creation failure the callable and captures are destroyed, registration is balanced, and the original native creation error is propagated. On success, the worker runs the callable and explicitly destroys its captures **before** decrementing the count and notifying waiters. A child launched by existing work is registered while the parent is still counted.

All counter/predicate accesses are under the same native mutex; waiters use the existing condition-variable registration protocol. Multiple external waiters are supported. User callable/capture code is never invoked under the tracker mutex. Worker exceptions still terminate, and a valid native handle that cannot detach/close still terminates as before.

The tracker is initialized before application work rather than relying on unsafe XDK function-local-static initialization. Its single small allocation intentionally lives until process exit, so an already detached worker finishing during CRT static teardown cannot encounter a destroyed tracker mutex. This preserves ordinary detached-thread exit behavior; it is not a per-job allocation leak. The application must still drain before destroying Context and must not launch new Context-dependent work afterward. This is a work/capture drain; native handles still follow detached ownership. It does not claim to join arbitrary thread-local teardown unrelated to the callable.

## Verification and limits

```powershell
C:/Python313/python.exe -B tools/shipyard/test_resource_shutdown.py
```

The test first failed on the absent ResourceManager boundary before implementation. Its current passing checks use:

- The full actual generated ResourceManager class with a test-only friend, its real constructor/destructor/drain bodies, the actual generated BS pool, and real native synchronization primitives. No fake resource manager or pool is supplied. Tests cover null/partial initialization, a capture destructor that blocks then acquires the still-live ResourceManager mutex, both explicit drain and destructor drain, and 1,000 queued jobs on a paused pool.
- The actual detached implementation and real native threads/events/mutexes. Tests cover two simultaneous waiters, a blocked capture destructor after callable return, 1,000 immediate completions, child submission, creation failure and callable-copy failure without a stuck count. A test-only CreateThread interception injects the creation failure; every successful call forwards to the actual OS API. The production source/native object contains no interception.
- The previous detached ownership contract, compiled with its newly required native.cpp dependency, compared with real `std::thread` ownership. The original/projected output matches, including another 1,000 immediate completions. Uncaught worker exceptions terminate with the expected test exit 73 in both implementations.
- Native XDK compilation of the **whole current ResourceManager.cpp**, including all resource behavior, and actual tracked `detached.cpp`. Both produced COFF PPC machine `0x1F2` objects.

Receipts and hashes are in `scratch/resource-shutdown-xdk/verification.json` and `xdk/build.json`; logs and host contracts are alongside them. No actual Context/application shutdown, Xenia execution, XContent behavior or physical-hardware validation is claimed.

Integration note: the older standalone `tools/shipyard/tests/test_detached.py` command previously linked detached.cpp alone. Its projected build now also needs `platform/shipyard/async/native.cpp`; the new shutdown test already recompiles and runs that original contract with this dependency. The normal application already compiles native.cpp.
