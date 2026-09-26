#include "application/frame_profile.h"
#include <cassert>
#include <cstdio>

static unsigned reads;
static uint64_t tick;
static uint64_t Clock() { ++reads; return tick; }
int main() {
    ModernFrameProfile::Accumulator profile(Clock);
    for (int i = 0; i < 200; ++i) {
        profile.BeginFrame(false);
        profile.Begin(ModernFrameProfile::Interpolation);
        profile.End(ModernFrameProfile::Interpolation);
        assert(!profile.EndFrame());
    }
    assert(reads == 0 && profile.frames == 0);
    tick = 100;
    profile.BeginFrame(true);
    tick = 110; profile.Begin(ModernFrameProfile::Interpolation);
    tick = 120; profile.End(ModernFrameProfile::Interpolation);
    tick = 125; profile.Begin(ModernFrameProfile::Graphics);
    tick = 130; profile.Begin(ModernFrameProfile::GuiStart);
    tick = 150; profile.End(ModernFrameProfile::GuiStart);
    tick = 170; profile.End(ModernFrameProfile::Graphics);
    tick = 180; assert(!profile.EndFrame());
    assert(profile.phases[ModernFrameProfile::Graph].ticks == 80);
    assert(profile.phases[ModernFrameProfile::Graphics].ticks == 45);
    assert(profile.phases[ModernFrameProfile::GuiStart].ticks == 20);
    tick = 200; profile.BeginFrame(true);
    assert(profile.periods == 1 && profile.periodTicks == 100 && profile.outsideTicks == 20);
    tick = 240; assert(!profile.EndFrame());
    for (int i = 2; i < 120; ++i) {
        tick += 100; profile.BeginFrame(true);
        tick += 10;
        assert(profile.EndFrame() == (i == 119));
    }
    assert(profile.frames == 120 && profile.periods == 119);
    profile.ResetWindow();
    assert(profile.frames == 0 && profile.periods == 0);
    tick += 100; profile.BeginFrame(true);
    assert(profile.periods == 1 && profile.outsideTicks == 100);
    tick += 10; profile.EndFrame();
    profile.BeginFrame(false);
    const unsigned stopped = reads;
    profile.Begin(ModernFrameProfile::Present); profile.End(ModernFrameProfile::Present);
    assert(!profile.EndFrame() && reads == stopped);
    tick += 1000; profile.BeginFrame(true);
    assert(profile.periods == 0); // Disabled intervals never enter a later sample.
    std::puts("disabled: zero clock reads; nested scopes, frame periods, bounded reports, reset/re-enable: pass");
}
