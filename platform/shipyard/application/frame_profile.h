#pragma once
#include <stdint.h>
#include <string.h>

namespace ModernFrameProfile {
enum Phase {
    Graph, Interpolation, Graphics, Readiness, GuiStart, Framebuffer,
    Interpreter, GuiEnd, Present, AudioWait, AudioGenerate, AudioSubmit,
    InterpreterSetup, CommandWalk, InterpreterFinish, ResourceWait, RecordingRotate,
    GameUpdate, PlayUpdate, PlayDrawRecord, SceneRoomDraw, ActorDraw,
    ActorEffect, ActorEffectSs, ActorLightsGlow, GameStateDraw,
    GuiStartFrame, GuiDrawMenu, GuiViewport,
    GuiDrawGame, GuiRender, GuiDrawData, GuiFloating, GuiSaveCvars,
    PresentEndFrame, PresentSwapBegin, PresentFinishRender, PresentSwapEnd,
    PixelDepthRead, PhaseCount
};
struct PhaseStats { uint64_t ticks, maximum; unsigned calls; };

// All scopes are wall time and inclusive. In particular Graphics contains the
// presentation phases; Graph contains Graphics, interpolation, and audio wait.
class Accumulator {
  public:
    explicit Accumulator(uint64_t (*clock)()) : enabled(false), readClock(clock),
        previousBegin(0), previousGraph(0), previousPresentBegin(0),
        havePrevious(false), havePreviousPresent(false) { ResetWindow(); }
    void ResetWindow() {
        memset(phases, 0, sizeof(phases));
        memset(active, 0, sizeof(active));
        frames = periods = 0;
        periodTicks = outsideTicks = 0;
        presentIntervalCount = presentIntervalDropped = 0;
        presentIndexInGame = 0;
    }
    void BeginFrame(bool requested) {
        if (requested != enabled) {
            enabled = requested;
            ResetWindow();
            havePrevious = false;
            havePreviousPresent = false;
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
        presentIndexInGame = 0;
        starts[Graph] = now;
        active[Graph] = true;
    }
    void Begin(Phase phase) {
        if (!enabled) return;
        const uint64_t now = readClock();
        if (phase == Present) {
            if (havePreviousPresent && now >= previousPresentBegin) {
                if (presentIntervalCount < PresentIntervalCapacity)
                {
                    presentIntervals[presentIntervalCount] = now - previousPresentBegin;
                    presentIntervalLanes[presentIntervalCount++] =
                        static_cast<uint8_t>(presentIndexInGame < 255 ? presentIndexInGame : 255);
                }
                else
                    ++presentIntervalDropped;
            }
            previousPresentBegin = now;
            havePreviousPresent = true;
            ++presentIndexInGame;
        }
        starts[phase] = now;
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
    enum { PresentIntervalCapacity = 4096 };
    PhaseStats phases[PhaseCount];
    unsigned frames, periods;
    uint64_t periodTicks, outsideTicks;
    uint64_t presentIntervals[PresentIntervalCapacity];
    uint8_t presentIntervalLanes[PresentIntervalCapacity];
    unsigned presentIntervalCount, presentIntervalDropped;
  private:
    uint64_t (*readClock)();
    uint64_t starts[PhaseCount], previousBegin, previousGraph, previousPresentBegin;
    unsigned presentIndexInGame;
    bool active[PhaseCount], havePrevious, havePreviousPresent;
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
bool CaptureResourceLookups();
void ObserveResourceLookup(bool alternate, bool resolved, unsigned probes);
void ObserveTextureHashCache(bool hit);
void ObserveTexturePathCache(bool hit);
void ObserveTileState(unsigned kind, bool same, bool avoidable);
bool CaptureTrianglePipeline();
void ObserveTrianglePipeline(bool hit);
void ObserveContextSearch(unsigned attempts, unsigned slots, unsigned maximum);
enum PipelinePreparationPhase {
    PipelineStateCombiner, PipelineTextureImports, PipelineGeometrySampler,
    PipelineShaderTransitions, PipelineFinalCapture, PipelinePreparationPhaseCount
};
struct PipelinePreparationSample {
    uint64_t lastTick, ticks[PipelinePreparationPhaseCount];
    unsigned currentPhase;
    bool sampled;
};
void BeginPipelinePreparation(PipelinePreparationSample& sample);
void AdvancePipelinePreparation(PipelinePreparationSample& sample, PipelinePreparationPhase next);
void EnterPipelineTextureImport(PipelinePreparationSample& sample);
void ExitPipelineTextureImport(PipelinePreparationSample& sample);
void EndPipelinePreparation(PipelinePreparationSample& sample);
enum Tri2Phase {
    Tri2Cull, Tri2Materialize, Tri2Pipeline, Tri2Pack, Tri2Flush, Tri2PhaseCount
};
struct Tri2Sample {
    uint64_t lastTick, ticks[Tri2PhaseCount];
    unsigned currentPhase;
    bool sampled;
};
void BeginTri2(Tri2Sample& sample);
void AdvanceTri2(Tri2Sample& sample, Tri2Phase next);
void EndTri2(Tri2Sample& sample);
enum VtxHashPhase {
    VtxHashDispatch, VtxHashLookup, VtxHashDeferred, VtxHashTransform,
    VtxHashInsert, VtxHashFinish, VtxHashPhaseCount
};
enum VtxHashRoute { VtxHashPointer, VtxHashResolved, VtxHashMissing, VtxHashRouteCount };
struct VtxHashSample {
    uint64_t lastTick, ticks[VtxHashPhaseCount];
    uint64_t vmxStartTick, vmxLoopStartTick, vmxSetupTicks, vmxLoopTicks;
    unsigned currentPhase, route;
    unsigned vmxAttempts, vmxAccepted, vmxVertices, vmxPendingVertices;
    bool sampled, deferred, vmx, vmxLoopEntered;
};
void BeginVtxHash(VtxHashSample& sample);
void AdvanceVtxHash(VtxHashSample& sample, VtxHashPhase next);
void EndVtxHash(VtxHashSample& sample);
void BeginVtxTransform(VtxHashSample& sample, unsigned vertices);
void EnterVtxTransformLoop(void* sample);
void EndVtxTransform(VtxHashSample& sample, bool accepted);
enum TextureHashPhase {
    TextureHashMapLookup, TextureHashOwningCache, TextureHashLoader,
    TextureHashFinal, TextureHashPhaseCount
};
struct TextureHashSample {
    uint64_t lastTick, ticks[TextureHashPhaseCount];
    unsigned currentPhase;
    bool sampled;
};
void BeginTextureHash(TextureHashSample& sample,
                      TextureHashPhase initialPhase = TextureHashMapLookup);
void AdvanceTextureHash(TextureHashSample& sample, TextureHashPhase next);
void EndTextureHash(TextureHashSample& sample);
class PhaseScope {
  public:
    explicit PhaseScope(Phase value) : phase(value) { Begin(phase); }
    ~PhaseScope() { End(phase); }
  private:
    Phase phase;
    PhaseScope(const PhaseScope&);
    PhaseScope& operator=(const PhaseScope&);
};
class ResourceLookupScope {
  public:
    explicit ResourceLookupScope(bool alternateMode) : active(CaptureResourceLookups()),
        alternate(alternateMode), resolved(false), probes(0) {}
    ~ResourceLookupScope() { if (active) ObserveResourceLookup(alternate, resolved, probes); }
    void Probe() { if (active) ++probes; }
    void Resolved() { resolved = true; }
  private:
    bool active, alternate, resolved;
    unsigned probes;
    ResourceLookupScope(const ResourceLookupScope&);
    ResourceLookupScope& operator=(const ResourceLookupScope&);
};
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
