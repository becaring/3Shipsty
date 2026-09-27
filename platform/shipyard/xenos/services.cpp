#include "services.h"
#include "metrics.h"
#include "xenos/core.h"
#include "context/platform.h"
#include "storage/atomic_file.h"
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
    "audio_generate", "audio_submit", "interpreter_setup", "command_walk", "interpreter_finish", "resource_handoff_wait", "recording_rotate", "game_update"};
// Resource workers must never write the interpreter thread's profiling buckets.
__declspec(thread) bool inInterpreter=false;
volatile LONG observeWorkers=0, workerProcessorMask=0, workerJobs=0;
struct ResourceLookupCounters { unsigned calls, alternate, resolved, fallback, probes, textureHits, textureMisses, pathHits, pathMisses; };
ResourceLookupCounters resourceLookups = {};
struct TrianglePipelineCounters { unsigned hits, misses; };
TrianglePipelineCounters trianglePipeline = {};
struct DustCounters {
    unsigned draws, current, updatesWithDust, maxDrawsPerUpdate, near100, near250;
    float minDistanceSquared, maxScale;
    bool updateActive;
};
DustCounters dust = {};
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
    memset(&trianglePipeline,0,sizeof(trianglePipeline));
    memset(&dust,0,sizeof(dust));
}
double Milliseconds(uint64_t ticks) {
    return frequency ? double(ticks) * 1000.0 / double(frequency) : 0.0;
}
}
CommandSampler commandSampler(Clock);
void BeginFrame(bool enabled) {
    if (enabled != accumulator.enabled) {
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
bool CaptureTrianglePipeline() { return inInterpreter && accumulator.enabled; }
void ObserveTrianglePipeline(bool hit) {
    if (hit) ++trianglePipeline.hits;
    else ++trianglePipeline.misses;
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
    for (unsigned i = 0; i < intervalCount; ++i) {
        const double ms = Milliseconds(accumulator.presentIntervals[i]);
        over20 += ms > 20.0;
        over33 += ms > 33.0;
        over50 += ms > 50.0;
    }
    std::sort(accumulator.presentIntervals, accumulator.presentIntervals + intervalCount);
    Shipyard_Log("frame-profile present_intervals samples=%u overflow=%u median_ms=%.3f p95_ms=%.3f max_ms=%.3f over20=%u over33=%u over50=%u scope=present_begin_to_begin",
        intervalCount, accumulator.presentIntervalDropped,
        intervalCount ? Milliseconds(accumulator.presentIntervals[(intervalCount - 1) / 2]) : 0.0,
        intervalCount ? Milliseconds(accumulator.presentIntervals[(intervalCount * 95 - 1) / 100]) : 0.0,
        intervalCount ? Milliseconds(accumulator.presentIntervals[intervalCount - 1]) : 0.0,
        over20, over33, over50);
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
    Shipyard_Log("frame-profile triangle_pipeline hits=%u misses=%u scope=surviving_triangles",
        trianglePipeline.hits,trianglePipeline.misses);
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
extern "C" void Shipyard_FrameProfileDustDraw(float px, float py, float pz,
                                                float ex, float ey, float ez,
                                                float scale, unsigned flags) {
    ModernFrameProfile::ObserveDustDraw(px,py,pz,ex,ey,ez,scale,flags);
}
