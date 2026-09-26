#include "GameInteractor.h"
#include <cassert>
#include <cstdio>

int main() {
    GameInteractor gi;
    typedef GameInteractor::OnSceneInit H;
    typedef GameInteractor::RegisteredGameHooks<H> Registry;
    typedef GameInteractor::HooksToUnregister<H> Pending;
    for (int i = 100; i < 1100; ++i) {
        gi.ExecuteHooksForID<H>(i, 1);
        gi.ExecuteHooksForPtr<H>(static_cast<uintptr_t>(i), 1);
    }
    const size_t expected = EXPECT_EMPTY_GROUPS;
    assert(Registry::functionsForID.size() == expected);
    assert(Registry::functionsForPtr.size() == expected);
    assert(Registry::hookData.empty());

    int total = 0;
    HOOK_ID id = gi.RegisterGameHookForID<H>(7, [&total](int16_t n) { total += n; });
    HOOK_ID ptr = gi.RegisterGameHookForPtr<H>(7, [&total](int16_t n) { total += n; });
    gi.UnregisterGameHookForID<H>(id);
    gi.UnregisterGameHookForPtr<H>(ptr);
    gi.ExecuteHooksForID<H>(42, 9);
    gi.ExecuteHooksForPtr<H>(42, 9);
    assert(Pending::hooksForID.size() == 1 && Pending::hooksForID[0] == id);
    assert(Pending::hooksForPtr.size() == 1 && Pending::hooksForPtr[0] == ptr);
    assert(Registry::hookData.size() == 2 && total == 0);
    gi.ExecuteHooksForID<H>(7, 9);
    gi.ExecuteHooksForPtr<H>(7, 9);
    assert(Pending::hooksForID.empty() && Pending::hooksForPtr.empty());
    assert(Registry::hookData.empty() && total == 0);

    // Registering after a miss must still create a callable group. During its
    // callback grow the outer table enough to rehash, then defer self-removal.
    HOOK_ID lateID = 0, latePtr = 0;
    lateID = gi.RegisterGameHookForID<H>(42, [&gi, &total, &lateID](int16_t n) {
        total += n;
        for (int i = 2000; i < 4000; ++i)
            gi.RegisterGameHookForID<H>(i, [](int16_t) {});
        gi.UnregisterGameHookForID<H>(lateID);
    });
    latePtr = gi.RegisterGameHookForPtr<H>(42, [&gi, &total, &latePtr](int16_t n) {
        total += n;
        for (int i = 2000; i < 4000; ++i)
            gi.RegisterGameHookForPtr<H>(static_cast<uintptr_t>(i), [](int16_t) {});
        gi.UnregisterGameHookForPtr<H>(latePtr);
    });
    gi.ExecuteHooksForID<H>(42, 3);
    gi.ExecuteHooksForPtr<H>(42, 4);
    assert(total == 7 && Registry::hookData.at(lateID).calls == 1 && Registry::hookData.at(latePtr).calls == 1);
    gi.ExecuteHooksForID<H>(42, 9);
    gi.ExecuteHooksForPtr<H>(42, 9);
    assert(total == 7 && !Registry::hookData.count(lateID) && !Registry::hookData.count(latePtr));
    assert(Registry::functionsForID.at(42).empty() && Registry::functionsForPtr.at(42).empty());
    puts("Absent groups, pending removals, later registration, callback rehash and deferred self-removal: pass");
}
