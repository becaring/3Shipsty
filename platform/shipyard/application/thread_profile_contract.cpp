#include "application/thread_profile.h"
#include <cassert>
#include <iostream>
#include <thread>

int main() {
    using namespace ModernFrameProfile;
    ThreadSample game, audio;
    game.Reset(true);
    audio.Reset(true);
    std::thread worker([&game]() {
        game.Begin(GameUpdate, 100);
        game.Begin(PlayUpdate, 110);
        game.End(PlayUpdate, 150);
        game.End(GameUpdate, 180);
        game.Begin(PlayUpdate, 200);
        game.End(PlayUpdate, 205);
    });
    audio.Begin(AudioGenerate, 120);
    audio.End(AudioGenerate, 140);
    worker.join();
    PhaseStats combined[PhaseCount] = {};
    combined[Interpreter].ticks = 75;
    game.Merge(combined);
    audio.Merge(combined);
    assert(combined[GameUpdate].ticks == 80 && combined[GameUpdate].calls == 1);
    assert(combined[PlayUpdate].ticks == 45 && combined[PlayUpdate].maximum == 40);
    assert(combined[PlayUpdate].calls == 2);
    assert(combined[AudioGenerate].ticks == 20 && combined[Interpreter].ticks == 75);
    const ThreadSample frozen = game;
    game.Reset(false);
    game.Begin(GameUpdate, 1);
    game.End(GameUpdate, 999);
    game.Merge(combined);
    assert(combined[GameUpdate].ticks == 80);
    assert(frozen.phases[GameUpdate].ticks == 80);
    std::cout << "Thread phase ownership, nested scopes, merge and disabled path passed\n";
}
