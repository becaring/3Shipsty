#include "services.h"
#include "metrics.h"
#include "xenos/core.h"
#include "context/platform.h"
#include "storage/atomic_file.h"
#include "libultraship/bridge/consolevariablebridge.h"
#include <spdlog/spdlog.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include "application/frame_profile.h"
#include "application/command_profile.h"
static bool verifyReuse=false;
void Shipyard_SetGraphicsVerification(bool enabled){verifyReuse=enabled;}
bool Shipyard_VerifyFast3DReuse(){return verifyReuse;}
void Shipyard_Log(const char* format,...) {
    char buffer[2048];va_list args;va_start(args,format);_vsnprintf_s(buffer,sizeof(buffer),_TRUNCATE,format,args);va_end(args);
    spdlog::info("{}",buffer);
}
// Legacy bounded bring-up call sites remain linkable, but release builds do
// not format or emit their high-volume diagnostic events.
extern "C" void Shipyard_RuntimeTrace(const char*,...) {}
extern "C" void Shipyard_FrameProfileGameUpdateBegin(void);
extern "C" void Shipyard_FrameProfileGameUpdateEnd(void);
extern "C" void Shipyard_FrameProfilePlayUpdateBegin(void);
extern "C" void Shipyard_FrameProfilePlayUpdateEnd(void);
extern "C" void Shipyard_FrameProfilePlayDrawRecordBegin(void);
extern "C" void Shipyard_FrameProfilePlayDrawRecordEnd(void);
extern "C" void Shipyard_FrameProfileGameStateDrawBegin(void);
extern "C" void Shipyard_FrameProfileGameStateDrawEnd(void);
void Shipyard_Fatal(const char* operation,HRESULT result){
    Shipyard::Platform::RecordStartupFatal(operation,static_cast<unsigned long>(result));
    try{spdlog::critical("Xenos failure: {} ({:08x})",operation,static_cast<unsigned>(result));spdlog::default_logger()->flush();}
    catch(...){OutputDebugStringA("Shipyard fatal graphics failure while logging\n");}
    std::abort();
}
double Shipyard_Time(){LARGE_INTEGER tick,freq;QueryPerformanceCounter(&tick);QueryPerformanceFrequency(&freq);return double(tick.QuadPart)/double(freq.QuadPart);}
bool Shipyard_WriteFile(const char* relative,const void* bytes,size_t size){
    try {Shipyard::Storage::WriteAtomicRelativeFile("game:\\",relative,bytes,size);return true;}
    catch(...) {return false;}
}

namespace ModernFrameProfile {
namespace {
uint64_t Clock() {
    LARGE_INTEGER value;
    QueryPerformanceCounter(&value);
    return static_cast<uint64_t>(value.QuadPart);
}
Accumulator accumulator(Clock);
// Frame reporting uses the already recorded intervals; no extra work is done
// during a present. Each 120-update window can have at most 120 samples/lane.
uint64_t presentLaneIntervals[18][120];
uint64_t frequency = 0;
uint64_t previousReportTicks = 0;
unsigned maps = 0, nonemptyMaps = 0, replacements = 0;
// Last values plus a change flag make mixed-settings windows identifiable.
int settings[8] = {};
unsigned dimensions[7] = {};
float multiplier = 0;
bool haveSettings = false, haveDimensions = false, changed = false;
const char* names[PhaseCount] = {"graph", "interpolation", "graphics", "readiness",
    "gui_start", "framebuffer", "interpreter", "gui_end", "present", "audio_wait",
    "audio_generate", "audio_submit", "interpreter_setup", "command_walk", "interpreter_finish", "resource_handoff_wait", "recording_rotate", "game_update",
    "play_update", "play_draw_record", "scene_room_draw", "actor_draw",
    "actor_effect", "actor_effect_ss", "actor_lights_glow", "game_state_draw", "gui_start_frame", "gui_draw_menu", "gui_viewport",
    "gui_draw_game", "gui_render", "gui_draw_data", "gui_floating", "gui_save_cvars",
    "present_end_frame", "present_swap_begin", "present_finish_render", "present_swap_end"};
// Resource workers must never write the interpreter thread's profiling buckets.
__declspec(thread) bool inInterpreter=false;
volatile LONG observeWorkers=0, workerProcessorMask=0, workerJobs=0;
struct ResourceLookupCounters { unsigned calls, alternate, resolved, fallback, probes, textureHits, textureMisses, pathHits, pathMisses; };
ResourceLookupCounters resourceLookups = {};
struct TileStateCounters {
    unsigned calls[2], same[2], avoidable[2];
};
TileStateCounters tileState = {};
struct TrianglePipelineCounters { unsigned hits, misses; };
TrianglePipelineCounters trianglePipeline = {};
struct ContextSearchCounters { unsigned attempts, slots, maximum; };
ContextSearchCounters contextSearch = {};
struct PipelinePreparationCounters {
    uint64_t ticks[PipelinePreparationPhaseCount], maximum[PipelinePreparationPhaseCount];
    unsigned calls, samples;
};
PipelinePreparationCounters pipelinePrep = {};
uint32_t pipelineRandomState = 0x23ab45cdu;
const char* pipelineNames[PipelinePreparationPhaseCount] = {
    "state_combiner", "texture_imports", "geometry_sampler",
    "shader_transitions", "final_capture"
};
struct Tri2Counters {
    uint64_t ticks[Tri2PhaseCount], maximum[Tri2PhaseCount];
    unsigned calls, samples;
};
Tri2Counters tri2 = {};
uint32_t tri2RandomState = 0x6c83d52fu;
bool tri2ProfileEnabled = false;
const char* tri2Names[Tri2PhaseCount] = {
    "cull", "materialize", "pipeline", "pack", "flush"
};
struct VtxHashCounters {
    uint64_t ticks[VtxHashPhaseCount], maximum[VtxHashPhaseCount];
    uint64_t vmxSetupTicks, vmxLoopTicks, vmxSetupMaximum, vmxLoopMaximum;
    unsigned calls, samples, routes[VtxHashRouteCount], deferred, vmx;
    unsigned vmxAttempts, vmxAccepted, vmxVertices;
};
VtxHashCounters vtxHash = {};
uint32_t vtxHashRandomState = 0x3a9e176du;
bool vtxHashProfileEnabled = false;
const char* vtxHashNames[VtxHashPhaseCount] = {
    "dispatch", "resource_lookup", "deferred_setup", "transform", "pending_insert", "finish"
};
struct TextureHashCounters {
    uint64_t ticks[TextureHashPhaseCount], maximum[TextureHashPhaseCount];
    unsigned calls, samples;
};
TextureHashCounters textureHash = {};
uint32_t textureHashRandomState = 0xa24920cdu;
const char* textureHashNames[TextureHashPhaseCount] = {
    "map_lookup", "owning_cache", "loader_fallback", "final_metadata"
};
struct DustCounters {
    unsigned draws, current, updatesWithDust, maxDrawsPerUpdate, near100, near250;
    float minDistanceSquared, maxScale;
    bool updateActive;
};
DustCounters dust = {};
enum { ActorProfileCapacity = 512, ActorProfileTopCount = 8 };
struct ActorDrawCounters { uint64_t ticks; unsigned calls, samples; };
ActorDrawCounters actorDraw[ActorProfileCapacity] = {};
uint32_t actorRandomState = 0x9827b18du;
struct ThreadCpu {
    uint64_t start, ticks;
    unsigned samples, failures, processorMask, threadId, lastError;
    bool active;
};
ThreadCpu renderCpu = {}, audioCpu = {};
uint64_t FileTicks(const FILETIME& value) {
    return (static_cast<uint64_t>(value.dwHighDateTime) << 32) | value.dwLowDateTime;
}
bool ReadCpu(uint64_t& ticks, unsigned& error) {
    FILETIME created, exited, kernel, user;
    if (!GetThreadTimes(GetCurrentThread(), &created, &exited, &kernel, &user)) {
        error=GetLastError();
        return false;
    }
    ticks=FileTicks(kernel)+FileTicks(user);
    return true;
}
void BeginCpu(ThreadCpu& cpu) {
    cpu.threadId=GetCurrentThreadId();
    const unsigned processor=GetCurrentProcessorNumber();
    if (processor<32) cpu.processorMask|=1u<<processor;
    cpu.active=ReadCpu(cpu.start,cpu.lastError);
    if (!cpu.active) ++cpu.failures;
}
void EndCpu(ThreadCpu& cpu) {
    if (!cpu.active) return;
    uint64_t now;
    cpu.active=false;
    if (!ReadCpu(now,cpu.lastError) || now<cpu.start) { ++cpu.failures; return; }
    cpu.ticks+=now-cpu.start;
    ++cpu.samples;
}
void ResetMetadata() {
    maps = nonemptyMaps = replacements = 0;
    haveSettings = haveDimensions = changed = false;
    memset(&renderCpu,0,sizeof(renderCpu));
    memset(&audioCpu,0,sizeof(audioCpu));
    memset(&resourceLookups,0,sizeof(resourceLookups));
    memset(&tileState,0,sizeof(tileState));
    memset(&trianglePipeline,0,sizeof(trianglePipeline));
    memset(&contextSearch,0,sizeof(contextSearch));
    memset(&pipelinePrep,0,sizeof(pipelinePrep));
    memset(&tri2,0,sizeof(tri2));
    memset(&vtxHash,0,sizeof(vtxHash));
    memset(&textureHash,0,sizeof(textureHash));
    memset(&dust,0,sizeof(dust));
    memset(actorDraw,0,sizeof(actorDraw));
    actorRandomState = 0x9827b18du;
}
double Milliseconds(uint64_t ticks) {
    return frequency ? double(ticks) * 1000.0 / double(frequency) : 0.0;
}
void RecordPipelinePreparationPhase(PipelinePreparationSample& sample) {
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    sample.ticks[sample.currentPhase] += now >= sample.lastTick ? now - sample.lastTick : 0;
    sample.lastTick=now;
}
void RecordTri2Phase(Tri2Sample& sample) {
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    sample.ticks[sample.currentPhase] += now >= sample.lastTick ? now - sample.lastTick : 0;
    sample.lastTick=now;
}
void RecordVtxHashPhase(VtxHashSample& sample) {
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    sample.ticks[sample.currentPhase] += now >= sample.lastTick ? now - sample.lastTick : 0;
    sample.lastTick=now;
}
void RecordTextureHashPhase(TextureHashSample& sample) {
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    sample.ticks[sample.currentPhase] += now >= sample.lastTick ? now - sample.lastTick : 0;
    sample.lastTick=now;
}
}
CommandSampler commandSampler(Clock);
void BeginFrame(bool enabled) {
    if (enabled != accumulator.enabled) {
        // Read once per profiling session. A cache A/B with only the coarse
        // frame profile enabled incurs no TRI2 timing or per-command counts.
        tri2ProfileEnabled = enabled &&
            CVarGetInteger("gSettings.XboxTri2PhaseProfile", 0) != 0;
        vtxHashProfileEnabled = enabled &&
            CVarGetInteger("gSettings.XboxVtxHashPhaseProfile", 0) != 0;
        InterlockedExchange(&observeWorkers,enabled ? 1 : 0);
        InterlockedExchange(&workerProcessorMask,0);
        InterlockedExchange(&workerJobs,0);
        Fast::ShipyardXenos::SetTimingEnabled(enabled);
        if (enabled) {
            Fast::ShipyardXenos::NativeCounters discarded;
            Fast::ShipyardXenos::CaptureAndResetCounters(&discarded);
        }
        ResetMetadata();
        commandSampler.Reset();
        previousReportTicks = 0;
    }
    if (enabled && !frequency) {
        LARGE_INTEGER value;
        QueryPerformanceFrequency(&value);
        frequency = static_cast<uint64_t>(value.QuadPart);
    }
    accumulator.BeginFrame(enabled);
    commandSampler.enabled=enabled;
}
void Begin(Phase phase) {
    accumulator.Begin(phase);
    if (!accumulator.enabled) return;
    if (phase==Interpreter) { inInterpreter=true; BeginCpu(renderCpu); }
    else if (phase==AudioGenerate) BeginCpu(audioCpu);
}
void End(Phase phase) {
    if (accumulator.enabled) {
        if (phase==Interpreter) { EndCpu(renderCpu); inInterpreter=false; }
        else if (phase==AudioGenerate) EndCpu(audioCpu);
    }
    accumulator.End(phase);
}
uint64_t BeginActorInstance(int actorId) {
    if (!accumulator.enabled || actorId < 0 || actorId >= ActorProfileCapacity) return 0;
    ActorDrawCounters& counter = actorDraw[actorId];
    ++counter.calls;
    actorRandomState ^= actorRandomState << 13;
    actorRandomState ^= actorRandomState >> 17;
    actorRandomState ^= actorRandomState << 5;
    if ((actorRandomState & 3u) != 0) return 0;
    ++counter.samples;
    return Clock() + 1;
}
void EndActorInstance(int actorId, uint64_t started) {
    if (!started || actorId < 0 || actorId >= ActorProfileCapacity) return;
    const uint64_t now = Clock();
    const uint64_t start = started - 1;
    if (now >= start) actorDraw[actorId].ticks += now - start;
}
bool BeginResourceWait() {
    if (!inInterpreter || !accumulator.enabled) return false;
    accumulator.Begin(ResourceWait);
    return true;
}
void EndResourceWait() { accumulator.End(ResourceWait); }
bool CaptureResourceLookups() { return inInterpreter && accumulator.enabled; }
void ObserveResourceLookup(bool alternate, bool resolved, unsigned probes) {
    ++resourceLookups.calls;
    if (alternate) ++resourceLookups.alternate;
    if (resolved) ++resourceLookups.resolved;
    else ++resourceLookups.fallback;
    resourceLookups.probes += probes;
}
void ObserveTextureHashCache(bool hit) {
    if (hit) ++resourceLookups.textureHits;
    else ++resourceLookups.textureMisses;
}
void ObserveTexturePathCache(bool hit) {
    if (hit) ++resourceLookups.pathHits;
    else ++resourceLookups.pathMisses;
}
void ObserveTileState(unsigned kind, bool same, bool avoidable) {
    if (kind >= 2) return;
    ++tileState.calls[kind];
    if (same) ++tileState.same[kind];
    if (avoidable) ++tileState.avoidable[kind];
}
bool CaptureTrianglePipeline() { return inInterpreter && accumulator.enabled; }
void ObserveTrianglePipeline(bool hit) {
    if (hit) ++trianglePipeline.hits;
    else ++trianglePipeline.misses;
}
void ObserveContextSearch(unsigned attempts, unsigned slots, unsigned maximum) {
    contextSearch.attempts += attempts;
    contextSearch.slots += slots;
    if (maximum > contextSearch.maximum) contextSearch.maximum = maximum;
}
void BeginPipelinePreparation(PipelinePreparationSample& sample) {
    sample.sampled=false;
    if (!inInterpreter || !accumulator.enabled) return;
    ++pipelinePrep.calls;
    pipelineRandomState^=pipelineRandomState<<13;
    pipelineRandomState^=pipelineRandomState>>17;
    pipelineRandomState^=pipelineRandomState<<5;
    if ((pipelineRandomState & 63u) != 0) return;
    sample.sampled=true;
    sample.currentPhase=PipelineStateCombiner;
    memset(sample.ticks,0,sizeof(sample.ticks));
    sample.lastTick=Clock();
}
void AdvancePipelinePreparation(PipelinePreparationSample& sample, PipelinePreparationPhase next) {
    if (!sample.sampled) return;
    RecordPipelinePreparationPhase(sample);
    sample.currentPhase=next;
}
void EnterPipelineTextureImport(PipelinePreparationSample& sample) {
    AdvancePipelinePreparation(sample,PipelineTextureImports);
}
void ExitPipelineTextureImport(PipelinePreparationSample& sample) {
    AdvancePipelinePreparation(sample,PipelineGeometrySampler);
}
void EndPipelinePreparation(PipelinePreparationSample& sample) {
    if (!sample.sampled) return;
    RecordPipelinePreparationPhase(sample);
    for(unsigned i=0;i<PipelinePreparationPhaseCount;++i) {
        pipelinePrep.ticks[i] += sample.ticks[i];
        if (sample.ticks[i] > pipelinePrep.maximum[i])
            pipelinePrep.maximum[i] = sample.ticks[i];
    }
    ++pipelinePrep.samples;
    sample.sampled=false;
}
void BeginTri2(Tri2Sample& sample) {
    sample.sampled=false;
    if (!inInterpreter || !tri2ProfileEnabled) return;
    ++tri2.calls;
    tri2RandomState^=tri2RandomState<<13;
    tri2RandomState^=tri2RandomState>>17;
    tri2RandomState^=tri2RandomState<<5;
    if ((tri2RandomState & 63u) != 0) return;
    sample.sampled=true;
    sample.currentPhase=Tri2Cull;
    memset(sample.ticks,0,sizeof(sample.ticks));
    sample.lastTick=Clock();
}
void AdvanceTri2(Tri2Sample& sample, Tri2Phase next) {
    if (!sample.sampled) return;
    RecordTri2Phase(sample);
    sample.currentPhase=next;
}
void EndTri2(Tri2Sample& sample) {
    if (!sample.sampled) return;
    RecordTri2Phase(sample);
    for(unsigned i=0;i<Tri2PhaseCount;++i) {
        tri2.ticks[i] += sample.ticks[i];
        if (sample.ticks[i] > tri2.maximum[i])
            tri2.maximum[i] = sample.ticks[i];
    }
    ++tri2.samples;
    sample.sampled=false;
}
void BeginVtxHash(VtxHashSample& sample) {
    sample.sampled=false;
    if (!inInterpreter || !vtxHashProfileEnabled) return;
    ++vtxHash.calls;
    vtxHashRandomState^=vtxHashRandomState<<13;
    vtxHashRandomState^=vtxHashRandomState>>17;
    vtxHashRandomState^=vtxHashRandomState<<5;
    if ((vtxHashRandomState & 63u) != 0) return;
    sample.sampled=true;
    sample.currentPhase=VtxHashDispatch;
    sample.route=VtxHashMissing;
    sample.deferred=sample.vmx=false;
    memset(sample.ticks,0,sizeof(sample.ticks));
    sample.vmxStartTick=sample.vmxLoopStartTick=0;
    sample.vmxSetupTicks=sample.vmxLoopTicks=0;
    sample.vmxAttempts=sample.vmxAccepted=sample.vmxVertices=sample.vmxPendingVertices=0;
    sample.vmxLoopEntered=false;
    sample.lastTick=Clock();
}
void BeginVtxTransform(VtxHashSample& sample, unsigned vertices) {
    if (!sample.sampled) return;
    ++sample.vmxAttempts;
    sample.vmxPendingVertices=vertices;
    sample.vmxLoopEntered=false;
    sample.vmxStartTick=Clock();
}
void EnterVtxTransformLoop(void* context) {
    VtxHashSample& sample=*static_cast<VtxHashSample*>(context);
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    sample.vmxSetupTicks += now-sample.vmxStartTick;
    sample.vmxLoopStartTick=now;
    sample.vmxLoopEntered=true;
}
void EndVtxTransform(VtxHashSample& sample, bool accepted) {
    if (!sample.sampled) return;
    const uint64_t now=Clock();
    if (accepted && sample.vmxLoopEntered) {
        sample.vmxLoopTicks += now-sample.vmxLoopStartTick;
        ++sample.vmxAccepted;
        sample.vmxVertices += sample.vmxPendingVertices;
    } else {
        sample.vmxSetupTicks += now-sample.vmxStartTick;
    }
    sample.vmxPendingVertices=0;
}
void AdvanceVtxHash(VtxHashSample& sample, VtxHashPhase next) {
    if (!sample.sampled) return;
    RecordVtxHashPhase(sample);
    sample.currentPhase=next;
}
void EndVtxHash(VtxHashSample& sample) {
    if (!sample.sampled) return;
    RecordVtxHashPhase(sample);
    for(unsigned i=0;i<VtxHashPhaseCount;++i) {
        vtxHash.ticks[i] += sample.ticks[i];
        if (sample.ticks[i] > vtxHash.maximum[i])
            vtxHash.maximum[i] = sample.ticks[i];
    }
    ++vtxHash.samples;
    ++vtxHash.routes[sample.route];
    if (sample.deferred) ++vtxHash.deferred;
    if (sample.vmx) ++vtxHash.vmx;
    vtxHash.vmxSetupTicks += sample.vmxSetupTicks;
    vtxHash.vmxLoopTicks += sample.vmxLoopTicks;
    if (sample.vmxSetupTicks > vtxHash.vmxSetupMaximum)
        vtxHash.vmxSetupMaximum=sample.vmxSetupTicks;
    if (sample.vmxLoopTicks > vtxHash.vmxLoopMaximum)
        vtxHash.vmxLoopMaximum=sample.vmxLoopTicks;
    vtxHash.vmxAttempts += sample.vmxAttempts;
    vtxHash.vmxAccepted += sample.vmxAccepted;
    vtxHash.vmxVertices += sample.vmxVertices;
    sample.sampled=false;
}
void BeginTextureHash(TextureHashSample& sample, TextureHashPhase initialPhase) {
    sample.sampled=false;
    if (!inInterpreter || !accumulator.enabled) return;
    ++textureHash.calls;
    textureHashRandomState^=textureHashRandomState<<13;
    textureHashRandomState^=textureHashRandomState>>17;
    textureHashRandomState^=textureHashRandomState<<5;
    if ((textureHashRandomState & 63u) != 0) return;
    sample.sampled=true;
    sample.currentPhase=initialPhase;
    memset(sample.ticks,0,sizeof(sample.ticks));
    sample.lastTick=Clock();
}
void AdvanceTextureHash(TextureHashSample& sample, TextureHashPhase next) {
    if (!sample.sampled) return;
    RecordTextureHashPhase(sample);
    sample.currentPhase=next;
}
void EndTextureHash(TextureHashSample& sample) {
    if (!sample.sampled) return;
    RecordTextureHashPhase(sample);
    for(unsigned i=0;i<TextureHashPhaseCount;++i) {
        textureHash.ticks[i] += sample.ticks[i];
        if (sample.ticks[i] > textureHash.maximum[i])
            textureHash.maximum[i] = sample.ticks[i];
    }
    ++textureHash.samples;
    sample.sampled=false;
}
void DustUpdateBegin() {
    if (!accumulator.enabled) return;
    dust.current = 0;
    dust.updateActive = true;
}
void DustUpdateEnd() {
    if (!dust.updateActive) return;
    dust.updateActive = false;
    if (dust.current) {
        ++dust.updatesWithDust;
        if (dust.current > dust.maxDrawsPerUpdate)
            dust.maxDrawsPerUpdate = dust.current;
    }
}
void ObserveDustDraw(float px, float py, float pz, float ex, float ey, float ez,
                     float scale, unsigned flags) {
    if (!accumulator.enabled || !dust.updateActive) return;
    (void)flags;
    const float dx = px - ex, dy = py - ey, dz = pz - ez;
    const float distanceSquared = dx * dx + dy * dy + dz * dz;
    if (!dust.draws || distanceSquared < dust.minDistanceSquared)
        dust.minDistanceSquared = distanceSquared;
    if (!dust.draws || scale > dust.maxScale) dust.maxScale = scale;
    if (distanceSquared < 10000.0f) ++dust.near100;
    if (distanceSquared < 62500.0f) ++dust.near250;
    ++dust.draws;
    ++dust.current;
}
void ObserveResourceWorker() {
    if (!InterlockedCompareExchange(&observeWorkers,0,0)) return;
    const unsigned processor=GetCurrentProcessorNumber();
    if (processor<32) InterlockedOr(&workerProcessorMask,1u<<processor);
    InterlockedIncrement(&workerJobs);
}
void Settings(int requestedFps, int targetFps, int originalFps, int updateRate,
              unsigned refresh, int lowRes, int advanced, int vsync) {
    if (!accumulator.enabled) return;
    const int values[8] = {requestedFps, targetFps, originalFps, updateRate,
        static_cast<int>(refresh), lowRes, advanced, vsync};
    if (haveSettings && memcmp(settings, values, sizeof(values))) changed = true;
    memcpy(settings, values, sizeof(values));
    haveSettings = true;
}
void Batch(unsigned count, unsigned nonempty, unsigned size) {
    if (!accumulator.enabled) return;
    maps += count; nonemptyMaps += nonempty; replacements += size;
}
void Dimensions(unsigned width, unsigned height, unsigned viewportWidth,
                unsigned viewportHeight, unsigned windowWidth, unsigned windowHeight,
                unsigned samples, float scale) {
    if (!accumulator.enabled) return;
    const unsigned values[7] = {width, height, viewportWidth, viewportHeight,
        windowWidth, windowHeight, samples};
    if (haveDimensions && (memcmp(dimensions, values, sizeof(values)) || multiplier != scale)) changed = true;
    memcpy(dimensions, values, sizeof(values));
    multiplier = scale;
    haveDimensions = true;
}
void EndFrame() {
    if (!accumulator.EndFrame()) return;
    const uint64_t reportBegin = Clock();
    Fast::ShipyardXenos::NativeTimingCounters native;
    Fast::ShipyardXenos::NativeCounters counters;
    Fast::ShipyardXenos::CaptureAndResetTimingCounters(&native);
    Fast::ShipyardXenos::CaptureAndResetCounters(&counters);
    // This runs after the audio rendezvous. Scopes are inclusive wall time,
    // not CPU utilization or GPU duration; their totals must not be added.
    Shipyard_Log("frame-profile frames=%u periods=%u period_ms=%.3f outside_graph_ms=%.3f mixed=%u requested=%d effective=%d original=%d update_rate=%d refresh=%d lowres=%d advanced=%d vsync=%d internal=%ux%u viewport=%ux%u window=%ux%u msaa=%u scale=%.3f maps=%u nonempty_maps=%u replacements=%u",
        accumulator.frames, accumulator.periods, Milliseconds(accumulator.periodTicks), Milliseconds(accumulator.outsideTicks),
        changed ? 1u : 0u, settings[0], settings[1], settings[2], settings[3], settings[4], settings[5], settings[6], settings[7],
        dimensions[0], dimensions[1], dimensions[2], dimensions[3], dimensions[4], dimensions[5], dimensions[6], multiplier,
        maps, nonemptyMaps, replacements);
    const unsigned intervalCount = accumulator.presentIntervalCount;
    unsigned over20 = 0, over33 = 0, over50 = 0;
    unsigned laneSamples[3] = {}, laneOver20[3] = {};
    unsigned laneCounts[18] = {}, laneOver8[18] = {}, laneOverflow = 0;
    for (unsigned i = 0; i < intervalCount; ++i) {
        const double ms = Milliseconds(accumulator.presentIntervals[i]);
        over20 += ms > 20.0;
        over33 += ms > 33.0;
        over50 += ms > 50.0;
        const unsigned lane = accumulator.presentIntervalLanes[i];
        if (lane < 18) {
            if (laneCounts[lane] < 120) {
                presentLaneIntervals[lane][laneCounts[lane]++] = accumulator.presentIntervals[i];
                laneOver8[lane] += ms > 8.0;
            } else {
                ++laneOverflow;
            }
        }
        if (lane < 3) {
            ++laneSamples[lane];
            laneOver20[lane] += ms > 20.0;
        }
    }
    std::sort(accumulator.presentIntervals, accumulator.presentIntervals + intervalCount);
    Shipyard_Log("frame-profile present_intervals samples=%u overflow=%u median_ms=%.3f p95_ms=%.3f max_ms=%.3f over20=%u over33=%u over50=%u lane_samples=%u/%u/%u lane_over20=%u/%u/%u scope=present_begin_to_begin",
        intervalCount, accumulator.presentIntervalDropped,
        intervalCount ? Milliseconds(accumulator.presentIntervals[(intervalCount - 1) / 2]) : 0.0,
        intervalCount ? Milliseconds(accumulator.presentIntervals[(intervalCount * 95 - 1) / 100]) : 0.0,
        intervalCount ? Milliseconds(accumulator.presentIntervals[intervalCount - 1]) : 0.0,
        over20, over33, over50,
        laneSamples[0], laneSamples[1], laneSamples[2],
        laneOver20[0], laneOver20[1], laneOver20[2]);
    for (unsigned lane = 0; lane < 18; ++lane) {
        const unsigned count = laneCounts[lane];
        if (!count) continue;
        std::sort(presentLaneIntervals[lane], presentLaneIntervals[lane] + count);
        Shipyard_Log("frame-profile present_lane=%u samples=%u median_ms=%.3f p95_ms=%.3f max_ms=%.3f over8=%u lane_overflow=%u scope=present_begin_to_begin",
            lane, count,
            Milliseconds(presentLaneIntervals[lane][(count - 1) / 2]),
            Milliseconds(presentLaneIntervals[lane][(count * 95 - 1) / 100]),
            Milliseconds(presentLaneIntervals[lane][count - 1]),
            laneOver8[lane], laneOverflow);
    }
    for (unsigned i = 0; i < PhaseCount; ++i) {
        const PhaseStats& p = accumulator.phases[i];
        Shipyard_Log("frame-profile phase=%s calls=%u inclusive_ms=%.3f ms_per_game=%.3f ms_per_call=%.3f max_ms=%.3f", names[i], p.calls,
            Milliseconds(p.ticks), Milliseconds(p.ticks) / accumulator.frames,
            p.calls ? Milliseconds(p.ticks) / p.calls : 0.0, Milliseconds(p.maximum));
    }
    const ThreadCpu* cpus[2]={&renderCpu,&audioCpu};
    const Phase cpuPhases[2]={Interpreter,AudioGenerate};
    for (unsigned i=0;i<2;++i) {
        const ThreadCpu& cpu=*cpus[i];
        Shipyard_Log("frame-profile thread=%s id=%u processor_mask=%x cpu_ms=%.3f wall_ms=%.3f samples=%u failures=%u last_error=%u cpu_clock=GetThreadTimes",
            i ? "audio" : "interpreter", cpu.threadId,cpu.processorMask,double(cpu.ticks)/10000.0,
            Milliseconds(accumulator.phases[cpuPhases[i]].ticks),cpu.samples,cpu.failures,cpu.lastError);
    }
    const unsigned observedJobs=InterlockedExchange(&workerJobs,0);
    const unsigned observedProcessors=InterlockedExchange(&workerProcessorMask,0);
    Shipyard_Log("frame-profile resource_workers jobs_started=%u processor_mask=%x window=observed_between_reports",
                observedJobs,observedProcessors);
    Shipyard_Log("frame-profile resource_lookup calls=%u alt_enabled=%u cached=%u fallback=%u cache_probes=%u scope=interpreter",
        resourceLookups.calls,resourceLookups.alternate,resourceLookups.resolved,resourceLookups.fallback,resourceLookups.probes);
    Shipyard_Log("frame-profile texture_hash_cache hits=%u misses=%u scope=interpreter",
        resourceLookups.textureHits,resourceLookups.textureMisses);
    Shipyard_Log("frame-profile texture_path_cache hits=%u misses=%u scope=interpreter",
        resourceLookups.pathHits,resourceLookups.pathMisses);
    if (tileState.calls[0] || tileState.calls[1])
        Shipyard_Log("frame-profile tile_state calls=%u/%u same=%u/%u avoidable=%u/%u scope=tile/size",
            tileState.calls[0], tileState.calls[1], tileState.same[0], tileState.same[1],
            tileState.avoidable[0], tileState.avoidable[1]);
    Shipyard_Log("frame-profile triangle_pipeline hits=%u misses=%u scope=surviving_triangles",
        trianglePipeline.hits,trianglePipeline.misses);
    Shipyard_Log("frame-profile context_search attempts=%u slots=%u max_scan=%u scope=deferred_vertex_contexts",
        contextSearch.attempts,contextSearch.slots,contextSearch.maximum);
    Shipyard_Log("frame-profile pipeline_prep calls=%u samples=%u sample_probability=1/64 scope=cold_triangle_preparation",
        pipelinePrep.calls,pipelinePrep.samples);
    for(unsigned i=0;i<PipelinePreparationPhaseCount;++i) {
        const double sampled=Milliseconds(pipelinePrep.ticks[i]);
        const double estimated=pipelinePrep.samples ? sampled*pipelinePrep.calls/pipelinePrep.samples : 0.0;
        Shipyard_Log("frame-profile pipeline_prep_phase=%s sampled_ms=%.3f estimated_ms=%.3f sample_max_ms=%.3f",
            pipelineNames[i],sampled,estimated,Milliseconds(pipelinePrep.maximum[i]));
    }
    unsigned actorCalls = 0, actorSamples = 0;
    double actorEstimatedTicks = 0;
    int topActorIds[ActorProfileTopCount];
    double topActorTicks[ActorProfileTopCount];
    for (unsigned i = 0; i < ActorProfileTopCount; ++i) {
        topActorIds[i] = -1;
        topActorTicks[i] = 0;
    }
    for (unsigned id = 0; id < ActorProfileCapacity; ++id) {
        const ActorDrawCounters& actor = actorDraw[id];
        actorCalls += actor.calls;
        actorSamples += actor.samples;
        if (!actor.samples) continue;
        const double estimate = double(actor.ticks) * actor.calls / actor.samples;
        actorEstimatedTicks += estimate;
        for (unsigned rank = 0; rank < ActorProfileTopCount; ++rank) {
            if (topActorIds[rank] >= 0 && estimate <= topActorTicks[rank]) continue;
            for (unsigned move = ActorProfileTopCount - 1; move > rank; --move) {
                topActorIds[move] = topActorIds[move - 1];
                topActorTicks[move] = topActorTicks[move - 1];
            }
            topActorIds[rank] = static_cast<int>(id);
            topActorTicks[rank] = estimate;
            break;
        }
    }
    Shipyard_Log("frame-profile actor_instances calls=%u samples=%u estimated_ms=%.3f scope=Actor_Draw sampled_1_in_4",
        actorCalls, actorSamples, Milliseconds(static_cast<uint64_t>(actorEstimatedTicks)));
    for (unsigned rank = 0; rank < ActorProfileTopCount && topActorIds[rank] >= 0; ++rank) {
        const unsigned id = static_cast<unsigned>(topActorIds[rank]);
        const ActorDrawCounters& actor = actorDraw[id];
        Shipyard_Log("frame-profile actor_id rank=%u id=%u calls=%u samples=%u estimated_ms=%.3f ms_per_game=%.3f",
            rank, id, actor.calls, actor.samples,
            Milliseconds(static_cast<uint64_t>(topActorTicks[rank])),
            Milliseconds(static_cast<uint64_t>(topActorTicks[rank])) / accumulator.frames);
    }
    if (tri2ProfileEnabled) {
        Shipyard_Log("frame-profile tri2_route calls=%u samples=%u sample_probability=1/64 scope=opcode_06_interpreter flush_scope=buffer_full_only",
            tri2.calls,tri2.samples);
        for(unsigned i=0;i<Tri2PhaseCount;++i) {
            const double sampled=Milliseconds(tri2.ticks[i]);
            const double estimated=tri2.samples ? sampled*tri2.calls/tri2.samples : 0.0;
            Shipyard_Log("frame-profile tri2_phase=%s sampled_ms=%.3f estimated_ms=%.3f sample_max_ms=%.3f",
                tri2Names[i],sampled,estimated,Milliseconds(tri2.maximum[i]));
        }
    }
    if (vtxHashProfileEnabled) {
        Shipyard_Log("frame-profile vtx_hash_route calls=%u samples=%u pointer=%u hash_resolved=%u hash_missing=%u deferred=%u vmx=%u sample_probability=1/64 scope=opcode_32_interpreter route_counts=sampled",
            vtxHash.calls,vtxHash.samples,vtxHash.routes[VtxHashPointer],
            vtxHash.routes[VtxHashResolved],vtxHash.routes[VtxHashMissing],
            vtxHash.deferred,vtxHash.vmx);
        for(unsigned i=0;i<VtxHashPhaseCount;++i) {
            const double sampled=Milliseconds(vtxHash.ticks[i]);
            const double estimated=vtxHash.samples ? sampled*vtxHash.calls/vtxHash.samples : 0.0;
            Shipyard_Log("frame-profile vtx_hash_phase=%s sampled_ms=%.3f estimated_ms=%.3f sample_max_ms=%.3f",
                vtxHashNames[i],sampled,estimated,Milliseconds(vtxHash.maximum[i]));
        }
        const double vmxScale=vtxHash.samples ? double(vtxHash.calls)/vtxHash.samples : 0.0;
        Shipyard_Log("frame-profile vtx_vmx_split attempts=%u accepted=%u sampled_vertices=%u sampled_setup_ms=%.3f estimated_setup_ms=%.3f sampled_loop_ms=%.3f estimated_loop_ms=%.3f setup_max_ms=%.3f loop_max_ms=%.3f scope=opcode_32_sampled_transform",
            vtxHash.vmxAttempts,vtxHash.vmxAccepted,vtxHash.vmxVertices,
            Milliseconds(vtxHash.vmxSetupTicks),Milliseconds(vtxHash.vmxSetupTicks)*vmxScale,
            Milliseconds(vtxHash.vmxLoopTicks),Milliseconds(vtxHash.vmxLoopTicks)*vmxScale,
            Milliseconds(vtxHash.vmxSetupMaximum),Milliseconds(vtxHash.vmxLoopMaximum));
    }
    Shipyard_Log("frame-profile texture_hash_route calls=%u samples=%u sample_probability=1/64 scope=opcode_20_interpreter",
        textureHash.calls,textureHash.samples);
    for(unsigned i=0;i<TextureHashPhaseCount;++i) {
        const double sampled=Milliseconds(textureHash.ticks[i]);
        const double estimated=textureHash.samples ? sampled*textureHash.calls/textureHash.samples : 0.0;
        Shipyard_Log("frame-profile texture_hash_phase=%s sampled_ms=%.3f estimated_ms=%.3f sample_max_ms=%.3f",
            textureHashNames[i],sampled,estimated,Milliseconds(textureHash.maximum[i]));
    }
    Shipyard_Log("frame-profile dust draws=%u updates=%u max_per_update=%u near_100=%u near_250=%u min_distance_sq=%.1f max_scale=%.3f scope=game_update",
        dust.draws,dust.updatesWithDust,dust.maxDrawsPerUpdate,dust.near100,dust.near250,
        dust.minDistanceSquared,dust.maxScale);
    unsigned totalCommands=0,totalSamples=0;
    double estimates[256];
    for (unsigned i=0;i<256;++i) {
        const CommandStats& command=commandSampler.commands[i];
        totalCommands+=command.calls; totalSamples+=command.samples;
        estimates[i]=command.samples ? Milliseconds(command.ticks)*command.calls/command.samples : 0;
    }
    Shipyard_Log("frame-profile commands=%u timed_samples=%u sample_probability=1/64 detail=top12_estimated_wall_cost",
                totalCommands,totalSamples);
    for (unsigned rank=0;rank<12;++rank) {
        unsigned best=256;
        for (unsigned i=0;i<256;++i)
            if (estimates[i]>0 && (best==256 || estimates[i]>estimates[best])) best=i;
        if (best==256) break;
        const CommandStats& command=commandSampler.commands[best];
        Shipyard_Log("frame-profile opcode=%02x ucode_mask=%x calls=%u samples=%u sampled_ms=%.3f estimated_ms=%.3f sample_max_ms=%.3f",
            best,command.ucodes,command.calls,command.samples,Milliseconds(command.ticks),estimates[best],Milliseconds(command.maximum));
        estimates[best]=-1;
    }
    const double gameHz = accumulator.periodTicks ? double(accumulator.periods) * frequency / accumulator.periodTicks : 0.0;
    const double presentsPerGame = double(accumulator.phases[Present].calls) / accumulator.frames;
    Shipyard_Log("frame-profile game_hz=%.3f presents_per_game=%.3f estimated_present_hz=%.3f",
        gameHz, presentsPerGame, gameHz * presentsPerGame);
    const double nativeMs = native.frequency ? 1000.0 / double(native.frequency) : 0.0;
    Shipyard_Log("frame-profile native_inclusive_ms draw=%.3f upload=%.3f setup=%.3f resolve=%.3f clear=%.3f calls=%u/%u/%u/%u/%u upload_bytes=%I64u preparation_rebuilt=%u reused=%u active=%ux%u samples=%u tiles=%u presentation=%ux%u buffer2frames=%u present_interval=%u",
        native.drawTicks * nativeMs, native.uploadTicks * nativeMs, native.framebufferSetupTicks * nativeMs,
        native.framebufferResolveTicks * nativeMs, native.framebufferClearTicks * nativeMs,
        native.drawCalls, native.uploadCalls, native.framebufferSetupCalls, native.framebufferResolveCalls,
        native.framebufferClearCalls, native.uploadBytes, native.preparationRebuilt, native.preparationReused,
        native.activeWidth, native.activeHeight, native.activeSamples, native.activeTiles,
        native.presentationWidth, native.presentationHeight, native.buffer2Frames, native.presentationInterval);
    Shipyard_Log("frame-profile depth_read_ms total=%.3f lock=%.3f calls=%u lock_calls=%u samples=%u prelock_busy=%u prelock_idle=%u busy_1080=%u idle_1080=%u",
        native.depthReadTicks * nativeMs, native.depthLockTicks * nativeMs,
        native.depthReadCalls, native.depthLockCalls, native.depthSamples,
        native.depthBusyCalls, native.depthIdleCalls,
        native.depthBusy1080Calls, native.depthIdle1080Calls);
    Shipyard_Log("frame-profile native_counts sampler_attempted=%u written=%u suppressed=%u constants_attempted=%u written=%u suppressed=%u binding_attempted=%u written=%u suppressed=%u uploads=%u reused=%u saved_bytes=%u clears=%u restores_avoided=%u depth_restores_avoided=%u",
        counters.samplerAttempted, counters.samplerWritten, counters.samplerSuppressed,
        counters.constantsAttempted, counters.constantsWritten, counters.constantsSuppressed,
        counters.bindingAttempted, counters.bindingWritten, counters.bindingSuppressed,
        counters.uploadRequests, counters.uploadReused, counters.uploadSavedBytes, counters.clears,
        counters.restoresAvoided, counters.depthRestoresAvoided);
    Shipyard_Log("frame-profile depth_resolves retained=%u skipped=%u early_fences=%u",
        counters.depthResolves, counters.depthResolvesSkipped, counters.earlyDepthFences);
    Shipyard_Log("frame-profile tiled_ring restarts=%u peak_estimated_bytes=%u guard_bytes=2097152",
        counters.tilingDrawRestarts,counters.tilingPeakBytes);
    Shipyard_Log("frame-profile tiling_space_1080 brackets=%u guard_finishes=%u normal_finishes=%u queries=%u query_calls=%u query_ms=%.3f capacity_changes=%u used_regressions=%u max_setup_bytes=%u max_finish_bytes=%u",
        counters.tilingSpace.brackets,counters.tilingSpace.guardFinishes,
        counters.tilingSpace.normalFinishes,counters.tilingSpace.querySamples,
        native.tilingSpaceQueryCalls,native.tilingSpaceQueryTicks*nativeMs,
        counters.tilingSpace.capacityChanges,counters.tilingSpace.usedRegressions,
        counters.tilingSpace.maxSetupBytes,counters.tilingSpace.maxFinishBytes);
    Shipyard_Log("frame-profile tiling_space_1080_phase max_used=%u/%u/%u/%u min_remaining=%u/%u/%u/%u phases=begin/setup/pre_resolve/pre_end",
        counters.tilingSpace.maxUsed[0],counters.tilingSpace.maxUsed[1],
        counters.tilingSpace.maxUsed[2],counters.tilingSpace.maxUsed[3],
        counters.tilingSpace.minRemaining[0],counters.tilingSpace.minRemaining[1],
        counters.tilingSpace.minRemaining[2],counters.tilingSpace.minRemaining[3]);
    const Fast::ShipyardXenos::TilingGuardTrialStats& guard = counters.tilingGuardTrial;
    Shipyard_Log("frame-profile tiling_guard_trial enabled=%d begin_rejected=%u candidates=%u continued=%u fallback_ineligible=%u fallback_oversize=%u fallback_capacity=%u fallback_cursor=%u fallback_space=%u post_queries=%u post_fallbacks=%u post_capacity_changes=%u post_cursor_regressions=%u max_draw_bytes=%u max_used=%u total_draw_bytes=%I64u",
        CVarGetInteger("gSettings.XboxTilingGuardTrialProfile", 0),
        guard.beginCapacityRejected,guard.candidates,guard.continued,
        guard.ineligibleFallbacks,guard.oversizeFallbacks,guard.capacityFallbacks,
        guard.cursorFallbacks,guard.spaceFallbacks,guard.postQueries,
        guard.postFallbacks,guard.postCapacityChanges,guard.postCursorRegressions,
        guard.maxDrawBytes,guard.maxUsed,guard.totalDrawBytes);
    Shipyard_Log("frame-profile ring_draw_probe same_segment=%u ambiguous=%u segment_changed=%u actual_bytes=%.0f estimated_bytes=%.0f max_actual_bytes=%u segment_bytes=262144",
        counters.ringSameSegmentDraws, counters.ringAmbiguousDraws,
        counters.ringSegmentChangedDraws,
        (double)counters.ringSameSegmentBytes,
        (double)counters.ringSameSegmentEstimatedBytes,
        counters.ringMaxSameSegmentBytes);
    Shipyard_Log("frame-profile tiled_1080_batches total=%u tile1_only=%u vertices=%u tile1_only_vertices=%u oversize=%u",
        counters.tiling1080Batches, counters.tiling1080Tile1Batches,
        counters.tiling1080Vertices, counters.tiling1080Tile1Vertices,
        counters.tiling1080OversizeBatches);
    const Fast::ShipyardXenos::Tile1PredicationTrialCounters& tile1 = counters.tile1PredicationTrial;
    Shipyard_Log("frame-profile tile1_predication_trial enabled=%d candidates=%u eligible=%u applied=%u target_rejected=%u viewport_rejected=%u geometry_rejected=%u",
        CVarGetInteger("gSettings.XboxTile1PredicationTrialProfile", 0),
        tile1.candidates,tile1.eligible,tile1.applied,
        tile1.targetRejected,tile1.viewportRejected,tile1.geometryRejected);
    Shipyard_Log("frame-profile presentation_color resolves_skipped=%u discard_blocked=%u",
        counters.presentationColorResolvesSkipped, counters.presentationColorDiscardBlocked);
    Shipyard_Log("frame-profile previous_report_ms=%.3f scopes=inclusive_wall qpc_overhead=included outside_graph=game_update+scheduling+reporting",
        Milliseconds(previousReportTicks));
    // Reporting lies outside Graph and appears in the next outside_graph
    // interval. QPC/scope overhead remains inside measured parent scopes.
    accumulator.ResetWindow();
    commandSampler.Reset();
    ResetMetadata();
    previousReportTicks = Clock() - reportBegin;
}
}
extern "C" void Shipyard_FrameProfileGameUpdateBegin(void) {
    ModernFrameProfile::DustUpdateBegin();
    ModernFrameProfile::Begin(ModernFrameProfile::GameUpdate);
}
extern "C" void Shipyard_FrameProfileGameUpdateEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::GameUpdate);
    ModernFrameProfile::DustUpdateEnd();
}
extern "C" void Shipyard_FrameProfilePlayUpdateBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::PlayUpdate);
}
extern "C" void Shipyard_FrameProfilePlayUpdateEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::PlayUpdate);
}
extern "C" void Shipyard_FrameProfilePlayDrawRecordBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::PlayDrawRecord);
}
extern "C" void Shipyard_FrameProfilePlayDrawRecordEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::PlayDrawRecord);
}
extern "C" void Shipyard_FrameProfileSceneRoomDrawBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::SceneRoomDraw);
}
extern "C" void Shipyard_FrameProfileSceneRoomDrawEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::SceneRoomDraw);
}
extern "C" void Shipyard_FrameProfileActorDrawBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::ActorDraw);
}
extern "C" void Shipyard_FrameProfileActorDrawEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::ActorDraw);
}
extern "C" uint64_t Shipyard_FrameProfileActorInstanceBegin(int actorId) {
    return ModernFrameProfile::BeginActorInstance(actorId);
}
extern "C" void Shipyard_FrameProfileActorInstanceEnd(int actorId, uint64_t started) {
    ModernFrameProfile::EndActorInstance(actorId, started);
}
extern "C" void Shipyard_FrameProfileEffectBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::ActorEffect);
}
extern "C" void Shipyard_FrameProfileEffectEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::ActorEffect);
}
extern "C" void Shipyard_FrameProfileEffectSsBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::ActorEffectSs);
}
extern "C" void Shipyard_FrameProfileEffectSsEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::ActorEffectSs);
}
extern "C" void Shipyard_FrameProfileLightsGlowBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::ActorLightsGlow);
}
extern "C" void Shipyard_FrameProfileLightsGlowEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::ActorLightsGlow);
}
extern "C" void Shipyard_FrameProfileGameStateDrawBegin(void) {
    ModernFrameProfile::Begin(ModernFrameProfile::GameStateDraw);
}
extern "C" void Shipyard_FrameProfileGameStateDrawEnd(void) {
    ModernFrameProfile::End(ModernFrameProfile::GameStateDraw);
}
extern "C" void Shipyard_FrameProfileDustDraw(float px, float py, float pz,
                                                float ex, float ey, float ez,
                                                float scale, unsigned flags) {
    ModernFrameProfile::ObserveDustDraw(px,py,pz,ex,ey,ez,scale,flags);
}
