#include "application/frame_profile.h"
#include "application/command_profile.h"
#include <cassert>
#include <cstdio>

static unsigned reads;
static uint64_t tick;
static uint64_t Clock() { ++reads; return tick; }
int main() {
    ModernFrameProfile::CommandSampler sampler(Clock);
    for (unsigned i=0;i<256;++i) sampler.End(sampler.Begin(1,2));
    assert(reads==0 && sampler.commands[1].calls==0);
    sampler.enabled=true;
    for (unsigned i=0;i<65536;++i) {
        ModernFrameProfile::CommandSampler::Token token=sampler.Begin(1,2);
        tick+=7;
        sampler.End(token);
    }
    const unsigned samples=sampler.commands[1].samples;
    assert(sampler.commands[1].calls==65536 && samples>850 && samples<1200);
    assert(sampler.commands[1].ticks==samples*7 && sampler.commands[1].maximum==7);
    assert(sampler.commands[1].ucodes==4 && reads==samples*2);
    unsigned positions[47]={};
    for (unsigned walk=0;walk<512;++walk) {
        for (unsigned j=0;j<47;++j) {
            ModernFrameProfile::CommandSampler::Token token=sampler.Begin(2,2);
            if (token.sampled) ++positions[j];
            sampler.End(token);
        }
    }
    for (unsigned j=0;j<47;++j) assert(positions[j]>0);
    sampler.Begin(1,3);
    assert(sampler.commands[1].ucodes==12);
    sampler.Reset();
    assert(sampler.commands[1].calls==0 && sampler.commands[1].ticks==0);
    sampler.enabled=false;
    const unsigned priorReads=reads;
    sampler.End(sampler.Begin(2,1));
    assert(reads==priorReads);
    reads=0;tick=0;
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
    tick += 2; profile.Begin(ModernFrameProfile::Present);
    tick += 1; profile.End(ModernFrameProfile::Present);
    tick += 25; profile.Begin(ModernFrameProfile::Present);
    assert(profile.presentIntervalCount == 1 && profile.presentIntervals[0] == 26);
    profile.End(ModernFrameProfile::Present);
    for (unsigned i = 0; i < ModernFrameProfile::Accumulator::PresentIntervalCapacity + 1; ++i) {
        ++tick; profile.Begin(ModernFrameProfile::Present);
        profile.End(ModernFrameProfile::Present);
    }
    assert(profile.presentIntervalCount == ModernFrameProfile::Accumulator::PresentIntervalCapacity);
    assert(profile.presentIntervalDropped == 2);
    tick += 10; profile.EndFrame();
    profile.BeginFrame(false);
    assert(profile.presentIntervalCount == 0 && profile.presentIntervalDropped == 0);
    const unsigned stopped = reads;
    profile.Begin(ModernFrameProfile::Present); profile.End(ModernFrameProfile::Present);
    assert(!profile.EndFrame() && reads == stopped);
    tick += 1000; profile.BeginFrame(true);
    assert(profile.periods == 0); // Disabled intervals never enter a later sample.
    profile.Begin(ModernFrameProfile::Present);
    assert(profile.presentIntervalCount == 0); // Disabled intervals never enter a later sample.
    std::puts("disabled: zero clock reads; nested scopes, frame periods, bounded reports, reset/re-enable: pass");
}
