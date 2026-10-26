// Compile the actual runtime with a controlled presentation surface and mixer.
// Native channel/worker synchronization and the replay loop remain production code.
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <memory>
#include <thread>
#include <unordered_map>
#include "imgui.h"
#include "imgui_internal.h"
#include "async/native.h"
#include "application/overlap.h"
#include "application/overlap_audio.h"
#include "overlap/depth.h"

struct Gfx { uint64_t generation; };
struct Mtx {};
struct MtxF { unsigned generation; float fraction; };
struct GraphicsContext {};
static std::atomic<unsigned> builds(0), tails(0), audioDone(0), callbacks(0), cacheDraws(0);
static std::atomic<unsigned> releases(0), nativeJobs(0), depthApplied(0), readyChecks(0);
static std::atomic<unsigned> cleanupJobs(0);
static std::atomic<unsigned> recycledMaps(0);
static unsigned nativeRefreshes;
static std::atomic<int> requested(1);
static std::atomic<bool> gameAtHandoff(false);
static uint64_t renderGeneration;
static unsigned preflights, accepted, dropped, depthReads, depthRetires, depthPublishes;
static bool pendingIntent, observedConcurrentBuild;
static bool allDropped, shutdownMode, offMode;
static bool hotplugMode, pendingHotplug;
static bool singleReplay;
static bool syncMode;
static bool restoreMode;
static const char* activeRemote;
static std::atomic<bool> needsFullSync(false);
extern "C" int Shipyard_OverlapNeedsFullSync() { return needsFullSync ? 1 : 0; }
static std::thread::id renderThread;
static void AssertIdleHandoff();
static void Pause(unsigned ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

#include "../../../soh/soh/cvar_prefixes.h"
#define CVAR_PREFIX_REMOTE "gRemote"
#undef CVAR_SETTING
#define CVAR_SETTING(name) name
#define CVAR_IMGUI_CONTROLLER_NAV "Nav"
#define CVAR_LOW_RES_MODE "LowRes"
#define CVAR_PREFIX_ADVANCED_RESOLUTION "Advanced"
#define CVAR_VSYNC_ENABLED "Vsync"
#define R_UPDATE_RATE 3
static int CVarGetInteger(const char* name, int fallback) {
    if (activeRemote && !strcmp(name, activeRemote)) return 1;
    if (!strcmp(name, "OverlapGameAndRender")) return requested.load();
    if (!strcmp(name, "InterpolationFPS")) return singleReplay ? 20 : 60;
    return fallback;
}
static bool GfxDebuggerIsDebugging() { return false; }
static std::unordered_map<Mtx*, MtxF> FrameInterpolation_Interpolate(float fraction) {
    static Mtx keys[2];
    std::unordered_map<Mtx*, MtxF> result;
    MtxF value = { builds.load(), fraction };
    result[&keys[value.generation % 2]] = value;
    return result;
}
static bool prevAltAssets = true;
static void gfx_texture_cache_clear() {}

namespace Ship {
class IResource {};
class ConsoleVariable {
public:
    typedef std::unordered_map<int, int> Snapshot;
    void CaptureSnapshot(Snapshot&) const { AssertIdleHandoff(); }
    void UseSnapshot(const Snapshot*) const {}
};
class Gui {
public:
    bool XboxHasInteractiveGui() { return false; }
    bool XboxBeginOverlapDraw() {
        AssertIdleHandoff();
        assert(nativeRefreshes == preflights + 1);
        ++preflights;
        pendingIntent = preflights == 3 && !shutdownMode && !offMode && !hotplugMode && !syncMode && !restoreMode;
        return !pendingIntent && !pendingHotplug;
    }
    void XboxFinishPassiveDraw() {}
    void XboxCommitOverlapIntent();
    bool GetMenuOrMenubarVisible() { return false; }
    ImGuiID GetMainGameWindowID() { return 1; }
};
class Window {
public:
    virtual ~Window() {}
    std::shared_ptr<Gui> GetGui() { return gui; }
    uintptr_t GetGfxFrameBuffer() { return 1; }
    std::shared_ptr<Gui> gui;
};
class ResourceManager {
public:
    void SetAltAssetsEnabled(bool) {}
    uint64_t GetXboxLookupGeneration() { return 1; }
};
class ConnectedPhysicalDeviceManager {
public:
    void RefreshNativeGamepads(bool presentation) {
        AssertIdleHandoff();
        assert(presentation);
        ++nativeRefreshes;
        if (hotplugMode && nativeRefreshes == 3) pendingHotplug = true;
    }
};
class ControlDeck {
public:
    std::shared_ptr<ConnectedPhysicalDeviceManager> GetConnectedPhysicalDeviceManager() { return manager; }
    std::shared_ptr<ConnectedPhysicalDeviceManager> manager;
};
class Context {
public:
    static std::shared_ptr<Context> GetInstance();
    std::shared_ptr<Window> GetWindow() { return window; }
    std::shared_ptr<ConsoleVariable> GetConsoleVariables() { return variables; }
    std::shared_ptr<ResourceManager> GetResourceManager() { return resources; }
    std::shared_ptr<ControlDeck> GetControlDeck() { return deck; }
    std::shared_ptr<Window> window;
    std::shared_ptr<ConsoleVariable> variables;
    std::shared_ptr<ResourceManager> resources;
    std::shared_ptr<ControlDeck> deck;
};
}
namespace Fast {
class Interpreter {
public:
    struct Cache { void Retire(uint64_t) {} } mXboxTextureHashCache;
    int mInterpolationIndex;
    bool mXboxDiscardGameDepth;
    void XboxRetireGameDepth() { ++depthRetires; }
    void XboxPublishGameDepth() { ++depthPublishes; }
};
class Fast3dWindow : public Ship::Window {
public:
    std::weak_ptr<Interpreter> GetInterpreterWeak() { return interpreter; }
    void SetTargetFps(int fps) { assert(fps == (singleReplay ? 20 : 60)); }
    void HandleEvents() {}
    unsigned GetCurrentRefreshRate() { return 60; }
    bool DrawAndRunGraphicsCommands(Gfx*, const std::unordered_map<Mtx*, MtxF>&);
    std::shared_ptr<Interpreter> interpreter;
};
}
static std::shared_ptr<Ship::Context> testContext;
std::shared_ptr<Ship::Context> Ship::Context::GetInstance() { return testContext; }
struct OTRGlobals {
    static OTRGlobals* Instance;
    int GetInterpolationFPS() { return singleReplay ? 20 : 60; }
};
static OTRGlobals globals;
OTRGlobals* OTRGlobals::Instance = &globals;
namespace SOH { struct SkeletonPatcher { static void UpdateSkeletons() {} }; }
struct GameInteractor {
    struct OnAssetAltChange {};
    static GameInteractor* Instance;
    template<class T> void ExecuteHooks() {}
};
static GameInteractor interactor;
GameInteractor* GameInteractor::Instance = &interactor;
struct AudioState {
    Shipyard::Async::mutex mutex;
    Shipyard::Async::condition_variable cv_from_thread, cv_to_thread;
    bool running, processing;
    ModernOverlap::AudioWorkState overlap;
    AudioState() : running(true), processing(false) {}
} audio;
namespace ModernFrameProfile {
static thread_local ThreadSample* currentSample;
void BeginFrame(bool) {}
void Begin(Phase) {}
void End(Phase) {}
void EndFrame() {}
void Settings(int, int, int, int, unsigned, int, int, int) {}
void Batch(unsigned, unsigned, unsigned) {}
void BeginThreadSample(ThreadSample& sample, bool enabled, bool) {
    sample.Reset(enabled);
    currentSample = &sample;
}
void EndThreadSample() { currentSample = NULL; }
void ObserveGameSample(const ThreadSample&) {}
void ObserveAudioSample(const ThreadSample&) {}
void ResetGameSampleCadence() {}
}

#include "application/overlap_runtime.inc"

void FrameInterpolation_Recycle(std::unordered_map<Mtx*, MtxF>& maps) {
    if (maps.empty()) return;
    assert(Shipyard_OverlapIsGameWorker());
    for (const auto& entry : maps)
        assert(ModernOverlap::session->worker.retiredGeneration() >= entry.second.generation);
    ++recycledMaps;
    maps.clear();
}

static void AssertIdleHandoff() {
    assert(std::this_thread::get_id() == renderThread);
    assert(gameAtHandoff);
    Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
    assert(!audio.processing);
}
void Shipyard_Log(const char*, ...) {}
extern "C" uint32_t ResourceMgr_IsGameMasterQuest() { return 0; }
extern "C" void Shipyard_OverlapCaptureGraphics() {}
static bool vertexReuseBatchActive = false;
static unsigned vertexReuseReplayCount = 0, vertexReuseReplayCalls = 0;
extern "C" void ModernVertexReuseBeginBatch(unsigned count) {
    assert(!vertexReuseBatchActive);
    vertexReuseBatchActive = true;
    vertexReuseReplayCount = count;
    vertexReuseReplayCalls = 0;
}
extern "C" void ModernVertexReuseBeginReplay(unsigned index) {
    assert(vertexReuseBatchActive && index == vertexReuseReplayCalls && index < vertexReuseReplayCount);
    ++vertexReuseReplayCalls;
}
extern "C" void ModernVertexReuseEndBatch() {
    assert(vertexReuseBatchActive && vertexReuseReplayCalls == vertexReuseReplayCount);
    vertexReuseBatchActive = false;
}
extern "C" void OTRGetPixelDepthPrepare(float, float) {}
extern "C" uint16_t OTRGetPixelDepth(float x, float) { ++depthReads; return static_cast<uint16_t>(x); }
extern "C" void Shipyard_OverlapApplyDepthResult(const ShipyardOverlapDepthResult* value) {
    assert(ModernOverlap::session->worker.buildingGeneration() >= value->generation + 2);
    assert(value->sunDepth == value->generation);
    ++depthApplied;
}
void Shipyard_ImGuiBeginCapture(ModernOverlap::GuiFrameCache*, bool) {}
bool Shipyard_ImGuiEndCapture() { return true; }
void Shipyard_ImGuiDrawCache(ModernOverlap::GuiFrameCache&, uintptr_t) { ++cacheDraws; }

bool Fast::Fast3dWindow::DrawAndRunGraphicsCommands(Gfx* commands,
    const std::unordered_map<Mtx*, MtxF>& maps) {
    assert(std::this_thread::get_id() == renderThread);
    assert(vertexReuseBatchActive && vertexReuseReplayCalls == interpreter->mInterpolationIndex + 1);
    const unsigned check = ++readyChecks;
    renderGeneration = commands->generation;
    for (const auto& entry : maps) assert(entry.second.generation == commands->generation);
    if (allDropped || check % 3 == 2) { ++dropped; return false; }
    ++accepted;
    const uint64_t original = commands->generation;
    assert(Shipyard_OverlapDrawGui(1));
    if (original == 1) {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
        while (builds <= original && std::chrono::steady_clock::now() < deadline) Pause(1);
        assert(builds > original);
    } else Pause(8);
    assert(commands->generation == original);
    for (const auto& entry : maps) assert(entry.second.generation == original);
    if (builds > original) observedConcurrentBuild = true;
    assert(Shipyard_OverlapDrawGui(0));
    return true;
}
void Ship::Gui::XboxCommitOverlapIntent() {
    assert(ModernOverlap::session->worker.retiredGeneration() >= renderGeneration);
    assert(audioDone >= renderGeneration);
    assert(tails == builds);
    if (pendingIntent) ++callbacks;
}
static void CleanupNativeJob(void*) {
    assert(std::this_thread::get_id() == renderThread);
    ++cleanupJobs;
}
static void Release(void*, void* pointer, const char*, int) {
    assert(Shipyard_OverlapIsGameWorker());
    assert(ModernFrameProfile::currentSample && !ModernFrameProfile::currentSample->enabled);
    uint64_t* generation = static_cast<uint64_t*>(pointer);
    assert(ModernOverlap::session->worker.retiredGeneration() >= *generation);
    Shipyard_OverlapRunOnRender(CleanupNativeJob, NULL);
    ++releases;
    delete generation;
}
static void NativeJob(void*) {
    assert(std::this_thread::get_id() == renderThread);
    ++nativeJobs;
}
static Gfx commandSlots[2];
static void GameFrame() {
    const uint64_t generation = ModernOverlap::session->worker.buildingGeneration();
    assert(generation <= 3);
    assert(audioDone >= generation - 1);
    if (generation > 2) assert(ModernOverlap::session->worker.retiredGeneration() >= generation - 2);
    ++builds;
    if (syncMode && generation == 3) {
        needsFullSync = true;
        Shipyard_OverlapFence();
        assert(ModernOverlap::session->worker.retiredGeneration() >= generation - 1);
    }
    if (generation == 3) Shipyard_OverlapRunOnRender(NativeJob, NULL);
    Gfx& commands = commandSlots[(generation - 1) % 2];
    commands.generation = generation;
    ShipyardOverlapDepthRequest depth;
    memset(&depth, 0, sizeof(depth));
    depth.active = 1;
    depth.sunX = static_cast<float>(generation);
    Shipyard_OverlapStageDepth(&depth);
    Shipyard_OverlapDeferRelease(Release, NULL, new uint64_t(generation), NULL, 0);
    gameAtHandoff = true;
    assert(ModernOverlap::PublishCommands(&commands));
    gameAtHandoff = false;
    if (restoreMode && generation == 3) {
        Shipyard_OverlapSaveStateBoundary(1);
        assert(releases == 3 && ModernOverlap::session->depthResults.empty());
    }
    assert(audioDone >= generation);
    ++tails;
}
static void Mixer() {
    for (;;) {
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
        while (!audio.processing && audio.running) audio.cv_to_thread.wait(lock);
        if (!audio.running) return;
        assert(audio.overlap.divisor == 3);
        Pause(2);
        audio.overlap.Complete();
        audioDone = static_cast<unsigned>(audio.overlap.completed);
        audio.processing = false;
        audio.cv_from_thread.notify_all();
    }
}
int main(int argc, char** argv) {
    allDropped = argc > 1 && (!strcmp(argv[1], "drop") || !strcmp(argv[1], "shutdown-drop"));
    shutdownMode = argc > 1 && (!strcmp(argv[1], "shutdown") || !strcmp(argv[1], "shutdown-drop"));
    offMode = argc > 1 && !strcmp(argv[1], "off");
    hotplugMode = argc > 1 && !strcmp(argv[1], "hotplug");
    singleReplay = argc > 1 && !strcmp(argv[1], "single");
    syncMode = argc > 1 && !strcmp(argv[1], "sync");
    restoreMode = argc > 1 && !strcmp(argv[1], "restore");
    if (argc > 1 && !strcmp(argv[1], "remote-cc")) activeRemote = CVAR_REMOTE_CROWD_CONTROL("Enabled");
    if (argc > 1 && !strcmp(argv[1], "remote-anchor")) activeRemote = CVAR_REMOTE_ANCHOR("Enabled");
    if (argc > 1 && !strcmp(argv[1], "remote-sail")) activeRemote = CVAR_REMOTE_SAIL("Enabled");
    renderThread = std::this_thread::get_id();
    ImGui::CreateContext();
    testContext.reset(new Ship::Context());
    std::shared_ptr<Fast::Fast3dWindow> window(new Fast::Fast3dWindow());
    window->gui.reset(new Ship::Gui());
    window->interpreter.reset(new Fast::Interpreter());
    testContext->window = window;
    testContext->variables.reset(new Ship::ConsoleVariable());
    testContext->resources.reset(new Ship::ResourceManager());
    testContext->deck.reset(new Ship::ControlDeck());
    testContext->deck->manager.reset(new Ship::ConnectedPhysicalDeviceManager());
    std::thread mixer(Mixer);
    if (activeRemote) {
        assert(Shipyard_OverlapRunFrame(GameFrame) == 0);
        assert(ModernOverlap::session == NULL && !ModernOverlap::capturingWarmup);
        activeRemote = NULL;
    }
    if (syncMode) {
        needsFullSync = true;
        assert(Shipyard_OverlapRunFrame(GameFrame) == 0);
        assert(ModernOverlap::session == NULL && !ModernOverlap::capturingWarmup);
        needsFullSync = false;
    }
    assert(Shipyard_OverlapRunFrame(GameFrame) == 0);
    for (unsigned index = 0; index != 2; ++index) assert(Shipyard_OverlapRunFrame(GameFrame) == 1);
    if (shutdownMode) Shipyard_OverlapShutdown();
    else {
        if (allDropped || offMode || singleReplay || restoreMode) requested = 0;
        assert(Shipyard_OverlapRunFrame(GameFrame) == 1);
    }
    assert(ModernOverlap::session == NULL);
    assert(builds == 3 && tails == 3 && audioDone == 3);
    assert(recycledMaps == (singleReplay ? 0u : 6u));
    assert(readyChecks == (singleReplay ? 3u : 9u) && accepted == (allDropped ? 0u : singleReplay ? 2u : 6u));
    assert(dropped == (allDropped ? 9u : singleReplay ? 1u : 3u) && cacheDraws == accepted);
    assert(preflights == (allDropped ? 0u : singleReplay ? 2u : 3u));
    assert(nativeRefreshes == preflights);
    assert(callbacks == (allDropped || shutdownMode || offMode || hotplugMode || singleReplay || syncMode || restoreMode ? 0u : 1u) && nativeJobs == 1);
    assert(pendingHotplug == hotplugMode);
    assert(releases == 3 && cleanupJobs == 3 && (allDropped || observedConcurrentBuild));
    assert(depthApplied >= 1 && depthReads == 3 && depthRetires == (singleReplay ? 9u : 6u) && depthPublishes == 3);
    requested = 0;
    assert(Shipyard_OverlapRunFrame(GameFrame) == 0);
    Shipyard_OverlapShutdown();
    {
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
        audio.running = false;
        audio.cv_to_thread.notify_all();
    }
    mixer.join();
    ImGui::DestroyContext();
    puts("Actual runtime: dropped replay cadence, audio ownership, immutable pool, depth lag, GUI retirement and stop drain passed");
}
