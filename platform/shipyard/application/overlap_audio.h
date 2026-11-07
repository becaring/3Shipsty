// Protected by the OTRAudio mutex. One stamped request is outstanding;
// the producer waits for its completion before touching shared game/audio state.
#pragma once
#include "application/thread_profile.h"
#include <stdexcept>

namespace ModernOverlap {
struct AudioWorkState {
    uint64_t generation, completed;
    int divisor;
    bool profile;
    ModernFrameProfile::ThreadSample sample;
    AudioWorkState() : generation(0), completed(0), divisor(1), profile(false) {}
    void Reset() {
        generation = completed = 0;
        divisor = 1;
        profile = false;
        sample.Reset(false);
    }
    void Submit(uint64_t next, unsigned rate, bool enabled, bool processing) {
        if (processing || !next || next <= completed || generation > completed)
            throw std::logic_error("Overlapping audio submission");
        if (rate < 1 || rate > 3) throw std::logic_error("Unsupported audio frame divisor");
        generation = next;
        divisor = static_cast<int>(rate);
        profile = enabled;
    }
    void Complete() { completed = generation; }
    bool Ready(uint64_t requested) const { return completed >= requested; }
};
}
