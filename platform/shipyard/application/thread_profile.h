// A producer or mixer owns its sample until handoff; render merges only a
// completed sample. Disabled samples never read the clock or touch counters.
#pragma once
#include "application/frame_profile.h"

namespace ModernFrameProfile {
struct ThreadSample {
    bool enabled;
    uint64_t started, completed, cpuStart, cpuTicks;
    unsigned threadId, processorMask, cpuSamples, cpuFailures, cpuLastError;
    bool cpuActive, wholeCpu;
    PhaseStats phases[PhaseCount];
    uint64_t starts[PhaseCount];
    bool active[PhaseCount];
    ThreadSample() { Reset(false); }
    void Reset(bool requested) {
        memset(this, 0, sizeof(*this));
        enabled = requested;
    }
    void Begin(Phase phase, uint64_t now) {
        if (!enabled) return;
        starts[phase] = now;
        active[phase] = true;
    }
    void End(Phase phase, uint64_t now) {
        if (!enabled || !active[phase]) return;
        const uint64_t elapsed = now >= starts[phase] ? now - starts[phase] : 0;
        phases[phase].ticks += elapsed;
        if (elapsed > phases[phase].maximum) phases[phase].maximum = elapsed;
        ++phases[phase].calls;
        active[phase] = false;
    }
    void Merge(PhaseStats* destination) const {
        if (!enabled) return;
        for (unsigned phase = 0; phase < PhaseCount; ++phase) {
            destination[phase].ticks += phases[phase].ticks;
            destination[phase].calls += phases[phase].calls;
            if (phases[phase].maximum > destination[phase].maximum)
                destination[phase].maximum = phases[phase].maximum;
        }
    }
};

void BeginThreadSample(ThreadSample& sample, bool enabled, bool wholeCpu = true);
void EndThreadSample();
void ObserveGameSample(const ThreadSample& sample);
void ObserveAudioSample(const ThreadSample& sample);
void ResetGameSampleCadence();
}
