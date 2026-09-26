#include "services.h"
#include "metrics.h"
#include "xenos/core.h"
#include "context/platform.h"
#include "storage/atomic_file.h"
#include <spdlog/spdlog.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include "application/frame_profile.h"
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
    "audio_generate", "audio_submit"};
void ResetMetadata() {
    maps = nonemptyMaps = replacements = 0;
    haveSettings = haveDimensions = changed = false;
}
double Milliseconds(uint64_t ticks) {
    return frequency ? double(ticks) * 1000.0 / double(frequency) : 0.0;
}
}
void BeginFrame(bool enabled) {
    if (enabled != accumulator.enabled) {
        Fast::ShipyardXenos::SetTimingEnabled(enabled);
        if (enabled) {
            Fast::ShipyardXenos::NativeCounters discarded;
            Fast::ShipyardXenos::CaptureAndResetCounters(&discarded);
        }
        ResetMetadata();
        previousReportTicks = 0;
    }
    if (enabled && !frequency) {
        LARGE_INTEGER value;
        QueryPerformanceFrequency(&value);
        frequency = static_cast<uint64_t>(value.QuadPart);
    }
    accumulator.BeginFrame(enabled);
}
void Begin(Phase phase) { accumulator.Begin(phase); }
void End(Phase phase) { accumulator.End(phase); }
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
    for (unsigned i = 0; i < PhaseCount; ++i) {
        const PhaseStats& p = accumulator.phases[i];
        Shipyard_Log("frame-profile phase=%s calls=%u inclusive_ms=%.3f ms_per_game=%.3f ms_per_call=%.3f max_ms=%.3f", names[i], p.calls,
            Milliseconds(p.ticks), Milliseconds(p.ticks) / accumulator.frames,
            p.calls ? Milliseconds(p.ticks) / p.calls : 0.0, Milliseconds(p.maximum));
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
    Shipyard_Log("frame-profile native_counts sampler_attempted=%u written=%u suppressed=%u constants_attempted=%u written=%u suppressed=%u binding_attempted=%u written=%u suppressed=%u uploads=%u reused=%u saved_bytes=%u clears=%u restores_avoided=%u depth_restores_avoided=%u",
        counters.samplerAttempted, counters.samplerWritten, counters.samplerSuppressed,
        counters.constantsAttempted, counters.constantsWritten, counters.constantsSuppressed,
        counters.bindingAttempted, counters.bindingWritten, counters.bindingSuppressed,
        counters.uploadRequests, counters.uploadReused, counters.uploadSavedBytes, counters.clears,
        counters.restoresAvoided, counters.depthRestoresAvoided);
    Shipyard_Log("frame-profile previous_report_ms=%.3f scopes=inclusive_wall qpc_overhead=included outside_graph=game_update+scheduling+reporting",
        Milliseconds(previousReportTicks));
    // Reporting lies outside Graph and appears in the next outside_graph
    // interval. QPC/scope overhead remains inside measured parent scopes.
    accumulator.ResetWindow();
    ResetMetadata();
    previousReportTicks = Clock() - reportBegin;
}
}
