#define BS_THREAD_POOL_ENABLE_PRIORITY
#define BS_THREAD_POOL_ENABLE_PAUSE
#include "BS_thread_pool.hpp"
#include "async/native.h"
#include "thread-pool/native_support.h"
#include <cstdio>
#include <string>
#include <vector>
#ifdef TEST_UPSTREAM
#include <chrono>
namespace result = std;
typedef std::chrono::milliseconds Milliseconds;
#else
namespace result = Shipyard::Async;
typedef Shipyard::Async::milliseconds Milliseconds;
#endif

static void check(bool value, const char* label) { if (!value) throw std::runtime_error(label); }
static bool broken(const result::future_error& error) {
#ifdef TEST_UPSTREAM
    return error.code() == std::make_error_code(std::future_errc::broken_promise);
#else
    return error.code() == result::broken_promise;
#endif
}

static void futures() {
    result::future<int> invalid;
    bool badGet = false, badWait = false, badPoll = false;
    try { invalid.get(); } catch (const result::future_error&) { badGet = true; }
    try { invalid.wait(); } catch (const result::future_error&) { badWait = true; }
    try { invalid.wait_for(Milliseconds(0)); } catch (const result::future_error&) { badPoll = true; }
    check(badGet && badWait && badPoll, "invalid futures reject get/wait/poll");
    result::promise<int> producer;
    result::future<int> value = producer.get_future();
    bool duplicate = false;
    try { producer.get_future(); } catch (const result::future_error&) { duplicate = true; }
    check(duplicate, "get_future once");
    check(value.wait_for(Milliseconds(-1)) == result::future_status::timeout, "negative timeout");
    producer.set_value(17);
    check(value.wait_for(Milliseconds(0)) == result::future_status::ready, "zero poll ready");
    check(value.get() == 17 && !value.valid(), "get consumes future");
    duplicate = false;
    try { producer.set_value(18); } catch (const result::future_error&) { duplicate = true; }
    check(duplicate, "single publication");
    result::future<int> abandoned;
    { result::promise<int> pending; abandoned = pending.get_future(); }
    bool failed = false;
    try { abandoned.get(); } catch (const result::future_error& e) { failed = broken(e); }
    check(failed, "broken promise propagates");
    result::promise<void> ready;
    result::shared_future<void> shared = ready.get_future().share();
    check(shared.wait_for(Milliseconds(1)) == result::future_status::timeout, "shared void timeout");
    ready.set_value(); shared.get(); shared.get();
    check(shared.valid() && shared.wait_for(Milliseconds(0)) == result::future_status::ready, "shared void repeated read");
    result::promise<std::unique_ptr<int> > moveProducer;
    result::future<std::unique_ptr<int> > moved = moveProducer.get_future();
    moveProducer.set_value(std::unique_ptr<int>(new int(9)));
    check(*moved.get() == 9, "move-only result ownership");
}

struct SaveSnapshot { int value; volatile LONG* destroyed; ~SaveSnapshot() { InterlockedIncrement(destroyed); } };
struct Saver {
    int written;
    Saver() : written(0) {}
    void write(int slot, SaveSnapshot* snapshot, int section) {
        written = snapshot->value + slot + section;
        delete snapshot;
    }
};
struct MakeSharedInt {
    std::shared_ptr<int> operator()() const { return std::shared_ptr<int>(new int(8)); }
};
static void save_and_resources() {
    BS::thread_pool pool(2);
    DWORD caller = GetCurrentThreadId();
    check(pool.submit_task([]() -> DWORD { return GetCurrentThreadId(); }).get() != caller, "real worker thread");
    volatile LONG destroyed = 0;
    Saver saver;
    pool.pause(); pool.wait();
    int liveValue = 30;
    SaveSnapshot* snapshot = new SaveSnapshot; snapshot->value = liveValue; snapshot->destroyed = &destroyed;
    pool.detach_task(std::bind(&Saver::write, &saver, 2, snapshot, 4));
    liveValue = 90;
    pool.unpause(); pool.wait();
    check(saver.written == 36 && destroyed == 1 && liveValue == 90, "SaveManager bound snapshot lifetime");
    std::shared_ptr<int> input(new int(7));
    result::shared_future<std::shared_ptr<int> > resource = pool.submit_task([input]() -> std::shared_ptr<int> { return input; });
    input.reset(); check(*resource.get() == 7 && resource.get() == resource.get(), "shared resource future");
    result::future<std::shared_ptr<std::vector<std::shared_ptr<int> > > > batch = pool.submit_task([&pool]() -> std::shared_ptr<std::vector<std::shared_ptr<int> > > {
        std::shared_ptr<std::vector<std::shared_ptr<int> > > values(new std::vector<std::shared_ptr<int> >());
        result::future<std::shared_ptr<int> > nested = pool.submit_task(MakeSharedInt());
        values->push_back(nested.get());
        return values;
    });
    check(*batch.get()->at(0) == 8, "LUS nested batch result with two workers");
    Shipyard::Async::manual_reset_event entered, release;
    result::future<void> extraction = pool.submit_task([&entered, &release]() -> void { entered.set(); release.wait(); });
    entered.wait(); check(extraction.wait_for(Milliseconds(0)) == result::future_status::timeout, "extraction polling does not block");
    release.set(); check(extraction.wait_for(Milliseconds(5000)) == result::future_status::ready, "timed wait sees completion");
    extraction.get(); check(!extraction.valid(), "extraction get consumes");
}

static void priority_errors_and_purge() {
    BS::thread_pool pool(1);
    pool.pause(); pool.wait();
    std::vector<int> order;
    result::future<int> low = pool.submit_task([&order]() -> int { order.push_back(1); return 1; });
    result::future<int> high = pool.submit_task([&order]() -> int { order.push_back(2); return 2; }, BS::pr::highest);
    check(pool.get_tasks_queued() == 2 && pool.get_tasks_running() == 0, "paused queue");
    pool.wait(); check(order.empty(), "paused wait excludes queued work");
    pool.unpause(); pool.wait();
    check(high.get() == 2 && low.get() == 1 && order[0] == 2, "priority");
    result::shared_future<void> failure = pool.submit_task([]() -> void { throw std::runtime_error("task failure"); });
    for (int i = 0; i < 2; ++i) {
        bool caught = false;
        try { failure.get(); } catch (const std::runtime_error& e) { caught = std::string(e.what()) == "task failure"; }
        check(caught, "exception repeat through shared future");
    }
    result::future<int> intFailure = pool.submit_task([]() -> int { throw std::runtime_error("integer failure"); });
    bool integerCaught = false;
    try { intFailure.get(); } catch (const std::runtime_error& e) { integerCaught = std::string(e.what()) == "integer failure"; }
    check(integerCaught && pool.submit_task([]() -> int { return 19; }).get() == 19, "worker survives submitted exception");
    pool.pause(); pool.wait();
    result::future<int> purged = pool.submit_task([]() -> int { return 1; }); pool.purge();
    bool abandoned = false;
    try { purged.get(); } catch (const result::future_error& e) { abandoned = broken(e); }
    check(abandoned && pool.get_tasks_queued() == 0, "purge abandons promise");
    pool.unpause();
}

struct Shutdown {
    Shipyard::Async::manual_reset_event entered, release, leaving, returned;
    int completed;
    Shutdown() : completed(0) {}
    static void run(void* arg) {
        Shutdown* self = static_cast<Shutdown*>(arg);
        { BS::thread_pool pool(2);
          pool.detach_task([self]() { self->entered.set(); self->release.wait(); self->completed = 1; });
          self->entered.wait(); self->leaving.set(); }
        self->returned.set();
    }
};
static void shutdown_and_wakeups() {
    Shutdown state;
    Shipyard::Async::joining_thread owner(&Shutdown::run, &state);
    state.leaving.wait(); bool early = state.returned.wait_for_ms(20);
    state.release.set(); check(state.returned.wait_for_ms(5000), "shutdown completes"); owner.join();
    check(!early && state.completed == 1, "destructor joins outstanding work");
    result::future<void> abandoned;
    { BS::thread_pool paused(1); paused.pause(); paused.wait(); abandoned = paused.submit_task([]() -> void {}); }
    bool caught = false; try { abandoned.get(); } catch (const result::future_error& e) { caught = broken(e); }
    check(caught, "paused destruction breaks pending promise");
    BS::thread_pool pool(4);
    for (int round = 0; round < 16; ++round) {
        std::vector<result::shared_future<int> > values;
        for (int i = 0; i < 32; ++i) values.push_back(pool.submit_task([i]() -> int { return i * 3; }).share());
        pool.wait(); for (int i = 0; i < 32; ++i) check(values[i].get() == i * 3, "wakeups");
    }
}

static void copy_seed(std::string seed, std::string* result) { *result = seed; }
#ifdef _XBOX
static void pinned_mixer_compile_contract() {
    Shipyard::Async::joining_thread worker = Shipyard::Async::make_thread_on_processor([]() {}, 2);
    worker.join();
}
#endif
static void randomizer_shape() {
    std::string seed = "owned seed", output;
    Shipyard::Async::joining_thread worker;
    worker = Shipyard::Async::make_thread(std::bind(&copy_seed, seed, &output));
    seed = "changed"; worker.join();
    check(output == "owned seed" && !worker.joinable(), "randomizer seed copied and explicitly joined");
}
#ifndef _XBOX
static void terminate_as_expected() { ExitProcess(73); }
#endif
int main(int argc, char** argv) {
#ifndef _XBOX
    if (argc == 2 && std::string(argv[1]) == "--detached-throws") {
        // Pinned BS detach_task has no promise exception wrapper; preserve its
        // terminate contract in an isolated process with a deterministic code.
        BS::thread_pool pool(1);
        pool.detach_task([]() {
            std::set_terminate(&terminate_as_expected);
            throw std::runtime_error("detached failure");
        });
        pool.wait();
        return 1;
    }
#else
    (void)argc; (void)argv;
#endif
    try {
        futures(); save_and_resources(); priority_errors_and_purge(); shutdown_and_wakeups(); randomizer_shape();
        std::puts("PASS futures, save snapshot, resource shapes, extraction polling, priority, exceptions, shutdown, 512 wakeups, randomizer seed ownership");
        return 0;
    } catch (const std::exception& e) { std::fprintf(stderr, "FAIL %s\n", e.what()); return 1; }
}
