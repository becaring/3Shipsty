#include "application/overlap_audio.h"
#include <cassert>
#include <iostream>

int main() {
    ModernOverlap::AudioWorkState audio;
    assert(!audio.Ready(1));
    audio.Submit(1, 3, true, false);
    unsigned liveDivisor = 1;
    assert(audio.divisor == 3 && liveDivisor == 1);
    bool rejected = false;
    try { audio.Submit(2, 1, false, true); } catch (const std::logic_error&) { rejected = true; }
    assert(rejected && audio.generation == 1 && audio.divisor == 3);
    rejected = false;
    try { audio.Submit(2, 1, false, false); } catch (const std::logic_error&) { rejected = true; }
    assert(rejected);
    audio.Complete();
    assert(audio.Ready(1) && !audio.Ready(2));
    rejected = false;
    try { audio.Submit(1, 2, false, false); } catch (const std::logic_error&) { rejected = true; }
    assert(rejected);
    audio.Submit(2, 1, false, false);
    assert(audio.divisor == 1 && !audio.profile);
    audio.Complete();
    audio.Reset();
    assert(!audio.Ready(1));
    audio.Submit(1, 2, true, false);
    assert(audio.divisor == 2);
    std::cout << "Audio generation, divisor ownership, duplicate/inflight rejection and restart passed\n";
}
