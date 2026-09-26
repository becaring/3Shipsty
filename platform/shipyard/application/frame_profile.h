#pragma once
#include <stdint.h>
#include <string.h>

namespace ModernFrameProfile {
enum Phase {
    Graph, Interpolation, Graphics, Readiness, GuiStart, Framebuffer,
    Interpreter, GuiEnd, Present, AudioWait, AudioGenerate, AudioSubmit,
    InterpreterSetup, CommandWalk, InterpreterFinish, ResourceWait, PhaseCount
};
struct PhaseStats { uint64_t ticks, maximum; unsigned calls; };

// All scopes are wall time and inclusive. In particular Graphics contains the
// presentation phases; Graph contains Graphics, interpolation, and audio wait.
class Accumulator {
  public:
    explicit Accumulator(uint64_t (*clock)()) : enabled(false), readClock(clock),
        previousBegin(0), previousGraph(0), havePrevious(false) { ResetWindow(); }
    void ResetWindow() {
        memset(phases, 0, sizeof(phases));
        memset(active, 0, sizeof(active));
        frames = periods = 0;
        periodTicks = outsideTicks = 0;
    }
    void BeginFrame(bool requested) {
        if (requested != enabled) {
            enabled = requested;
            ResetWindow();
            havePrevious = false;
        }
        if (!enabled) return;
        const uint64_t now = readClock();
        if (havePrevious && now >= previousBegin) {
            const uint64_t elapsed = now - previousBegin;
            periodTicks += elapsed;
            if (elapsed >= previousGraph) outsideTicks += elapsed - previousGraph;
            ++periods;
        }
        previousBegin = now;
        havePrevious = true;
        starts[Graph] = now;
        active[Graph] = true;
    }
    void Begin(Phase phase) {
        if (!enabled) return;
        starts[phase] = readClock();
        active[phase] = true;
    }
    void End(Phase phase) {
        if (!enabled || !active[phase]) return;
        const uint64_t now = readClock();
        const uint64_t elapsed = now >= starts[phase] ? now - starts[phase] : 0;
        phases[phase].ticks += elapsed;
        if (elapsed > phases[phase].maximum) phases[phase].maximum = elapsed;
        ++phases[phase].calls;
        active[phase] = false;
        if (phase == Graph) previousGraph = elapsed;
    }
    bool EndFrame() {
        if (!enabled) return false;
        End(Graph);
        return ++frames == 120;
    }
    bool enabled;
    PhaseStats phases[PhaseCount];
    unsigned frames, periods;
    uint64_t periodTicks, outsideTicks;
  private:
    uint64_t (*readClock)();
    uint64_t starts[PhaseCount], previousBegin, previousGraph;
    bool active[PhaseCount], havePrevious;
};

void BeginFrame(bool enabled);
void Begin(Phase phase);
void End(Phase phase);
void Settings(int requestedFps, int targetFps, int originalFps, int updateRate,
              unsigned refresh, int lowRes, int advanced, int vsync);
void Batch(unsigned maps, unsigned interpolated, unsigned replacements);
void Dimensions(unsigned width, unsigned height, unsigned viewportWidth,
                unsigned viewportHeight, unsigned windowWidth, unsigned windowHeight,
                unsigned samples, float multiplier);
void EndFrame();
bool BeginResourceWait();
void EndResourceWait();
void ObserveResourceWorker();
class ResourceWaitScope {
  public:
    ResourceWaitScope() : active(BeginResourceWait()) {}
    ~ResourceWaitScope() { if (active) EndResourceWait(); }
  private:
    bool active;
    ResourceWaitScope(const ResourceWaitScope&);
    ResourceWaitScope& operator=(const ResourceWaitScope&);
};
}
