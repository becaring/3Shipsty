"""Reuse condition wait events for managed workers without changing native ABI.
Thread scope owns the event; unowned or nested waits retain private events.
"""
from audio_cpu_projection import once

SCOPE = r'''
namespace {
struct WaitEventScope;
__declspec(thread) WaitEventScope* activeWaitEventScope = NULL;
struct WaitEventScope {
    std::unique_ptr<manual_reset_event> event;
    bool busy;
    WaitEventScope* previous;
    WaitEventScope() : busy(false), previous(activeWaitEventScope) { activeWaitEventScope = this; }
    ~WaitEventScope() { activeWaitEventScope = previous; }
};
struct WaitEventPool {
    enum { Capacity = 16 };
    mutex gate;
    manual_reset_event* events[Capacity];
    bool busy[Capacity];
    WaitEventPool() {
        for (unsigned i = 0; i < Capacity; ++i) { events[i] = NULL; busy[i] = false; }
    }
    manual_reset_event* acquire(unsigned& slot) {
        lock_guard<mutex> lock(gate);
        for (unsigned i = 0; i < Capacity; ++i) {
            if (busy[i]) continue;
            if (!events[i]) events[i] = new manual_reset_event();
            busy[i] = true;
            slot = i;
            return events[i];
        }
        return NULL;
    }
    void release(unsigned slot) { lock_guard<mutex> lock(gate); busy[slot] = false; }
};
static void* volatile waitEventPoolPointer = NULL;
static WaitEventPool* GetWaitEventPool() {
    WaitEventPool* pool = static_cast<WaitEventPool*>(InterlockedCompareExchangePointer(&waitEventPoolPointer, NULL, NULL));
    if (!pool) {
        std::unique_ptr<WaitEventPool> candidate(new WaitEventPool());
        pool = static_cast<WaitEventPool*>(InterlockedCompareExchangePointer(&waitEventPoolPointer, candidate.get(), NULL));
        if (!pool) pool = candidate.release();
    }
    // At most sixteen handles survive until process exit, including main-thread waits.
    // No static destructor can race a different module's shutdown waits.
    return pool;
}
}
'''

WAITER = r'''
struct condition_variable::waiter {
    union { unsigned char bytes[sizeof(manual_reset_event)]; void* alignment; } owned;
    manual_reset_event* event;
    WaitEventScope* borrowed;
    WaitEventPool* pool;
    unsigned poolSlot;
    waiter* next;
    waiter() : event(NULL), borrowed(NULL), pool(NULL), poolSlot(0), next(NULL) {
        WaitEventScope* scope = activeWaitEventScope;
        if (scope && !scope->busy) {
            if (!scope->event.get()) scope->event.reset(new manual_reset_event());
            else scope->event->reset();
            scope->busy = true;
            borrowed = scope;
            event = scope->event.get();
        } else {
            pool = GetWaitEventPool();
            event = pool->acquire(poolSlot);
            if (event) {
                try { event->reset(); }
                catch (...) { pool->release(poolSlot); throw; }
            } else {
                pool = NULL;
                event = new (owned.bytes) manual_reset_event();
            }
        }
    }
    ~waiter() {
        if (borrowed) borrowed->busy = false;
        else if (pool) pool->release(poolSlot);
        else event->~manual_reset_event();
    }
};
'''

def source(text):
    old = '''struct condition_variable::waiter {
    manual_reset_event event;
    waiter* next;
    waiter() : next(NULL) {
    }
};'''
    text = once(text, old, SCOPE + WAITER)
    text = once(text, '        entry.event.wait();', '        entry.event->wait();')
    if text.count('target->event.set();') != 2:
        raise ValueError('Native notification anchor drift')
    text = text.replace('target->event.set();', 'target->event->set();')
    text = once(text, '    try {\n        entry(argument);', '    try {\n        WaitEventScope waitEventScope;\n        entry(argument);')
    return text
