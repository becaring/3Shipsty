// Included by the projected OTR bridge after the original audio helpers.
// Game owns whole RunFrame callbacks; render owns device work and idle GUI.
#include "application/overlap.h"
#include "overlap/frame_worker.h"
#include "overlap/replay_batch.h"
#include "overlap/deferred_storage.h"
#include "overlap/writable_spans.h"
#include "overlap/depth.h"
#include "application/gui_frame_cache.h"
#include "application/thread_profile.h"
#include "native-imgui/gui_capture.h"
#include <deque>

extern "C" uint32_t ResourceMgr_IsGameMasterQuest(void);
extern "C" void OTRGetPixelDepthPrepare(float x, float y);
extern "C" uint16_t OTRGetPixelDepth(float x, float y);
extern "C" void Shipyard_OverlapCaptureGraphics(void);
extern "C" int Shipyard_OverlapNeedsFullSync(void);
extern "C" void ModernVertexReuseBeginBatch(unsigned replayCount);
extern "C" void ModernVertexReuseBeginReplay(unsigned replayIndex);
extern "C" void ModernVertexReuseEndBatch(void);
void FrameInterpolation_Recycle(std::unordered_map<Mtx*, MtxF>& replacements);
void Shipyard_Log(const char* format, ...);

namespace ModernOverlap {
using Shipyard::Overlap::DeferredStorage;
using Shipyard::Overlap::FrameWorker;
using Shipyard::Overlap::ReplayBatch;
using Shipyard::Overlap::ReplayCadence;
using Shipyard::Overlap::WritableSpans;
typedef std::unordered_map<Mtx*, MtxF> ReplacementMap;
typedef std::vector<std::shared_ptr<Ship::IResource> > ResourceOwners;
struct FramePacket {
    Gfx* commands;
    ReplayBatch<ReplacementMap> replay;
    ModernFrameProfile::ThreadSample gameProfile;
    ShipyardOverlapDepthRequest depth;
    ResourceOwners resources;
    uint32_t masterQuest;
    int requestedFps;
    bool profile;
    uint64_t inputTicks;
    FramePacket() : commands(NULL), masterQuest(0), requestedFps(20), profile(false), inputTicks(0) {
        memset(&depth, 0, sizeof(depth));
    }
    FramePacket& operator=(const FramePacket& other) {
        if (this == &other) return *this;
        // FrameChannel resets retired packets on the producer before reuse.
        for (size_t i = 0; i < replay.maps.size(); ++i)
            FrameInterpolation_Recycle(replay.maps[i]);
        commands = other.commands;
        replay = other.replay;
        gameProfile = other.gameProfile;
        depth = other.depth;
        resources = other.resources;
        masterQuest = other.masterQuest;
        requestedFps = other.requestedFps;
        profile = other.profile;
        inputTicks = other.inputTicks;
        return *this;
    }
};
typedef FrameWorker<FramePacket> GameWorker;
struct Session;
static bool RenderPacket(Session& session, const GameWorker::Ticket& ticket,
                         const FramePacket& packet, bool forceStop);

__declspec(thread) bool onGameWorker = false;
__declspec(thread) const FramePacket* renderingPacket = NULL;
__declspec(thread) ResourceOwners* renderResourceOwners = NULL;
static Session* session;
static std::shared_ptr<GuiFrameCache> passiveGui;
static bool capturingWarmup;
static bool deferredGuiIntent;
static GuiFrameCache* replayGui;
struct ReplayHandoff;
static ReplayHandoff* replayHandoff;
static void ClearTextureCache(void*) { gfx_texture_cache_clear(); }
struct GraphCallbackJob {
    GraphicsContext* graphics;
    void (*callback)(GraphicsContext*, void*);
    void* parameter;
};
static void RunGraphCallback(void* context) {
    GraphCallbackJob& job = *static_cast<GraphCallbackJob*>(context);
    job.callback(job.graphics, job.parameter);
}
static void AbortRuntime(const char* operation) {
    Shipyard_Log("Game/render overlap stopped: %s", operation);
    std::abort();
}
// Call only inside a catch block.
static void LogException(const char* where) {
    try { throw; }
    catch (const std::exception& e) { Shipyard_Log("%s: %s", where, e.what()); }
    catch (...) { Shipyard_Log("%s: non-standard exception", where); }
}
static uint64_t Ticks() {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return static_cast<uint64_t>(now.QuadPart);
}
static uint64_t Microseconds(uint64_t ticks) {
    static uint64_t frequency;
    if (!frequency) {
        LARGE_INTEGER value;
        QueryPerformanceFrequency(&value);
        frequency = static_cast<uint64_t>(value.QuadPart);
    }
    return ticks * 1000000 / frequency;
}
// Slack for a game frame that runs longer than its recent peak.
static const uint64_t PermitMarginMicros = 3000;

static void WaitAudio(uint64_t generation, ModernFrameProfile::ThreadSample* sample = NULL) {
    Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
    while (!audio.overlap.Ready(generation) && audio.running)
        audio.cv_from_thread.wait(lock);
    if (!audio.overlap.Ready(generation)) throw std::runtime_error("Audio stopped during replay");
    if (sample) *sample = audio.overlap.sample;
}

static void SubmitAudio(uint64_t generation, unsigned divisor, bool profile) {
    {
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
        audio.overlap.Submit(generation, divisor, profile, audio.processing);
        audio.processing = true;
    }
    audio.cv_to_thread.notify_one();
}

static void ResetAudio() {
    Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(audio.mutex);
    while (audio.processing) audio.cv_from_thread.wait(lock);
    audio.overlap.Reset();
}

struct Session {
    void (*runFrame)();
    GameWorker worker;
    ReplayCadence cadence;
    DeferredStorage storage;
    WritableSpans writableSpans;
    Ship::ConsoleVariable::Snapshot frozenVariables;
    ModernFrameProfile::ThreadSample tailProfile;
    Shipyard::Async::mutex depthGate;
    std::deque<ShipyardOverlapDepthResult> depthResults;
    bool inputBlocked[3];
    // Worker only: when the last handoff released it, and how long it has since waited on render.
    uint64_t resumedTicks, blockedTicks;
    // Recent peak of worker time from release to publish, excluding waits on render. Render reads it.
    volatile LONG buildMicros;
    explicit Session(void (*callback)()) : runFrame(callback), worker(BuildFrame, NULL) {
        inputBlocked[0] = inputBlocked[1] = inputBlocked[2] = false;
        resumedTicks = blockedTicks = 0;
        buildMicros = 0;
    }
    // Waits on render shrink when the worker starts later, so the estimate leaves them out.
    struct Blocked {
        uint64_t started;
        Blocked() : started(onGameWorker && session ? Ticks() : 0) {}
        ~Blocked() { if (started) session->blockedTicks += Ticks() - started; }
    };
    void ObserveBuild(uint64_t published) {
        if (!resumedTicks) return;
        const uint64_t elapsed = published - resumedTicks;
        const LONG sample = static_cast<LONG>(Microseconds(elapsed > blockedTicks ? elapsed - blockedTicks : 0));
        const LONG previous = buildMicros;
        // Rise at once, fall slowly, so one quick frame does not release the next one too late.
        InterlockedExchange(&buildMicros, sample >= previous ? sample : previous - (previous - sample) / 16);
    }
    static void BuildFrame(void* context) {
        (void)context;
        Session& owner = *session;
        // Keep the worker identity through retirement destructors between callbacks.
        onGameWorker = true;
        FramePacket& packet = owner.worker.buildingPacket();
        packet.profile = CVarGetInteger(CVAR_SETTING("XboxFrameProfile"), 0) != 0;
        ModernFrameProfile::BeginThreadSample(packet.gameProfile, packet.profile);
        try {
            owner.ApplyDepth();
            owner.storage.collect();
            owner.runFrame();
        } catch (...) {
            LogException("Game frame threw");
            ModernFrameProfile::EndThreadSample();
            ModernFrameProfile::BeginThreadSample(owner.tailProfile, false);
            throw;
        }
        ModernFrameProfile::EndThreadSample();
        ModernFrameProfile::BeginThreadSample(owner.tailProfile, false);
    }
    void ApplyDepth() {
        ShipyardOverlapDepthResult result;
        bool ready = false;
        {
            Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(depthGate);
            while (!depthResults.empty() &&
                   Shipyard_OverlapDepthReady(&depthResults.front(), worker.buildingGeneration())) {
                result = depthResults.front();
                depthResults.pop_front();
                ready = true;
            }
        }
        if (ready) Shipyard_OverlapApplyDepthResult(&result);
    }
    void PublishDepth(const ShipyardOverlapDepthResult& result) {
        if (!result.active) return;
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(depthGate);
        depthResults.push_back(result);
    }
    void CaptureInput() {
        std::shared_ptr<Ship::Gui> gui = Ship::Context::GetInstance()->GetWindow()->GetGui();
        ImGuiContext* context = ImGui::GetCurrentContext();
        const bool modal = ImGui::GetTopMostPopupModal() != NULL;
        inputBlocked[0] = modal || (gui->GetMenuOrMenubarVisible() &&
            CVarGetInteger(CVAR_IMGUI_CONTROLLER_NAV, 0) != 0);
        inputBlocked[1] = modal || (context->ActiveIdWindow != NULL &&
            context->ActiveIdWindow->ID != gui->GetMainGameWindowID());
        inputBlocked[2] = context->HoveredWindow == NULL ||
            context->HoveredWindow->ID != gui->GetMainGameWindowID();
    }
};

static bool Requested() {
    return CVarGetInteger(CVAR_SETTING("OverlapGameAndRender"), 1) != 0 &&
        CVarGetInteger(CVAR_SETTING("XboxInterpreterDetailsProfile"), 0) == 0 &&
        // Network integrations can dispatch game mutations on service threads.
        CVarGetInteger(CVAR_REMOTE_CROWD_CONTROL("Enabled"), 0) == 0 &&
        CVarGetInteger(CVAR_REMOTE_ANCHOR("Enabled"), 0) == 0 &&
        CVarGetInteger(CVAR_REMOTE_SAIL("Enabled"), 0) == 0 &&
        !GfxDebuggerIsDebugging() && !Shipyard_OverlapNeedsFullSync();
}

static bool PublishCommands(Gfx* commands) {
    if (!onGameWorker) return false;
    FramePacket& packet = session->worker.buildingPacket();
    const uint64_t generation = session->worker.buildingGeneration();
    packet.commands = commands;
    packet.masterQuest = ResourceMgr_IsGameMasterQuest();
    packet.requestedFps = CVarGetInteger(CVAR_SETTING("InterpolationFPS"), 20);
    const int rate = R_UPDATE_RATE;
    if (rate < 1 || rate > 3) throw std::runtime_error("Unsupported overlap frame divisor");
    ModernFrameProfile::Begin(ModernFrameProfile::Interpolation);
    ReplayBatch<ReplacementMap> prepared = session->cadence.prepare<ReplacementMap>(
        OTRGlobals::Instance->GetInterpolationFPS(), rate, GfxDebuggerIsDebugging(),
        [](float fraction) { return FrameInterpolation_Interpolate(fraction); });
    packet.replay.fps = prepared.fps;
    packet.replay.gameFps = prepared.gameFps;
    packet.replay.updateRate = prepared.updateRate;
    packet.replay.maps.swap(prepared.maps);
    ModernFrameProfile::End(ModernFrameProfile::Interpolation);
    packet.depth.generation = generation;
    ModernFrameProfile::EndThreadSample();
    ModernFrameProfile::BeginThreadSample(session->tailProfile, false);
    // This frame read the controller shortly after the previous release.
    packet.inputTicks = session->resumedTicks;
    session->ObserveBuild(Ticks());
    if (!session->worker.publishAndWait()) throw std::runtime_error("Game handoff aborted");
    session->resumedTicks = Ticks();
    session->blockedTicks = 0;
    WaitAudio(generation);
    const bool alternate = CVarGetInteger(CVAR_SETTING("AltAssets"), 1) != 0;
    if (prevAltAssets != alternate) {
        Shipyard_OverlapFence();
        prevAltAssets = alternate;
        Ship::Context::GetInstance()->GetResourceManager()->SetAltAssetsEnabled(alternate);
        Shipyard_OverlapRunOnRender(ClearTextureCache, NULL);
        SOH::SkeletonPatcher::UpdateSkeletons();
        GameInteractor::Instance->ExecuteHooks<GameInteractor::OnAssetAltChange>();
    }
    return true;
}

static void PrepareDepth(float x, float y, void*) { OTRGetPixelDepthPrepare(x, y); }
static uint16_t ReadDepth(float x, float y, void*) { return OTRGetPixelDepth(x, y); }

struct ReplayHandoff {
    Session& owner;
    const GameWorker::Ticket& ticket;
    const FramePacket& packet;
    std::shared_ptr<Ship::Gui> gui;
    std::shared_ptr<Ship::ConsoleVariable> variables;
    Ship::ConsoleVariable::Snapshot& frozenVariables;
    bool forceStop, started, submitted, permitted;
    size_t permitAt;
    ReplayHandoff(Session& value, const GameWorker::Ticket& frame, const FramePacket& data, bool stop)
        : owner(value), ticket(frame), packet(data),
          gui(Ship::Context::GetInstance()->GetWindow()->GetGui()),
          variables(Ship::Context::GetInstance()->GetConsoleVariables()),
          frozenVariables(value.frozenVariables),
          forceStop(stop), started(false), submitted(false), permitted(false), permitAt(0) {
        // Release the next game frame as late as its recent cost allows: it reads the controller
        // then, so its input reaches the screen sooner. Desktop SoH reads input right before each frame.
        const size_t frames = packet.replay.maps.size();
        if (frames > 1 && packet.replay.fps > 0) {
            const uint64_t period = 1000000 / static_cast<uint64_t>(packet.replay.fps);
            const uint64_t needed = static_cast<uint64_t>(owner.buildMicros) + PermitMarginMicros;
            const size_t covered = static_cast<size_t>((needed + period - 1) / period);
            permitAt = covered >= frames ? 0 : frames - covered;
        }
    }
    void Submit() {
        if (submitted) return;
        variables->CaptureSnapshot(frozenVariables);
        variables->UseSnapshot(&frozenVariables);
        SubmitAudio(ticket.generation, packet.replay.updateRate, packet.profile);
        submitted = true;
        if (permitAt == 0) Permit();
    }
    // The next callback mutates game state, so it starts only after the snapshot above.
    void Permit() {
        if (permitted || !submitted) return;
        permitted = true;
        if (!forceStop) owner.worker.permitNext(ticket);
    }
    void Begin() {
        if (started) return;
        started = true;
        Ship::Context::GetInstance()->GetControlDeck()->GetConnectedPhysicalDeviceManager()->RefreshNativeGamepads(true);
        std::shared_ptr<GuiFrameCache> nextGui(new GuiFrameCache());
        Shipyard_ImGuiBeginCapture(nextGui.get());
        const bool passive = gui->XboxBeginOverlapDraw();
        gui->XboxFinishPassiveDraw();
        const bool captured = Shipyard_ImGuiEndCapture();
        if (captured) passiveGui = nextGui;
        forceStop = forceStop || !passive || !captured;
        replayGui = passiveGui.get();
        owner.CaptureInput();
        Shipyard_OverlapCaptureGraphics();
        Submit();
    }
};

static bool RenderPacket(Session& owner, const GameWorker::Ticket& ticket,
                         const FramePacket& packet, bool forceStop) {
    std::shared_ptr<Fast::Fast3dWindow> window = std::dynamic_pointer_cast<Fast::Fast3dWindow>(
        Ship::Context::GetInstance()->GetWindow());
    if (!window) throw std::runtime_error("Overlap render window unavailable");
    std::shared_ptr<Fast::Interpreter> interpreter = window->GetInterpreterWeak().lock();
    ReplayHandoff handoff(owner, ticket, packet, forceStop);
    ModernFrameProfile::BeginFrame(packet.profile);
    ModernFrameProfile::ObserveGameSample(packet.gameProfile);
    window->SetTargetFps(packet.replay.fps);
    window->HandleEvents();
    ResourceOwners retainedResources;
    renderingPacket = &packet;
    renderResourceOwners = &retainedResources;
    replayGui = passiveGui.get();
    replayHandoff = &handoff;
    if (packet.profile) {
        ModernFrameProfile::Settings(packet.requestedFps, packet.replay.fps, packet.replay.gameFps,
            packet.replay.updateRate, window->GetCurrentRefreshRate(), CVarGetInteger(CVAR_LOW_RES_MODE, 0),
            CVarGetInteger(CVAR_PREFIX_ADVANCED_RESOLUTION ".Enabled", 0), CVarGetInteger(CVAR_VSYNC_ENABLED, 1));
        unsigned nonempty = 0, replacements = 0;
        for (size_t index = 0; index < packet.replay.maps.size(); ++index) {
            if (!packet.replay.maps[index].empty()) ++nonempty;
            replacements += static_cast<unsigned>(packet.replay.maps[index].size());
        }
        ModernFrameProfile::Batch(static_cast<unsigned>(packet.replay.maps.size()), nonempty, replacements);
    }
    interpreter->mInterpolationIndex = 0;
    interpreter->mXboxTextureHashCache.Retire(
        Ship::Context::GetInstance()->GetResourceManager()->GetXboxLookupGeneration());
    ShipyardOverlapDepthResult depth;
    memset(&depth, 0, sizeof(depth));
    bool sampled = false;
    ModernFrameProfile::Begin(ModernFrameProfile::Graphics);
    if (packet.replay.maps.size() < 2) {
        Shipyard_OverlapSampleDepth(&packet.depth, &depth, PrepareDepth, ReadDepth, NULL);
        interpreter->XboxRetireGameDepth();
        sampled = true;
    }
    {
        struct VertexReuseBatchScope {
            explicit VertexReuseBatchScope(unsigned count) { ModernVertexReuseBeginBatch(count); }
            ~VertexReuseBatchScope() { ModernVertexReuseEndBatch(); }
        } vertexReuseBatch(static_cast<unsigned>(packet.replay.maps.size()));
        for (size_t index = 0; index < packet.replay.maps.size(); ++index) {
            if (index == handoff.permitAt) handoff.Permit();
            ModernVertexReuseBeginReplay(static_cast<unsigned>(index));
            interpreter->mXboxDiscardGameDepth = index + 1 < packet.replay.maps.size();
            window->DrawAndRunGraphicsCommands(packet.commands, packet.replay.maps[index]);
            if (index == 0 && packet.profile && packet.inputTicks)
                ModernFrameProfile::ObserveInputAge(static_cast<unsigned>(Microseconds(Ticks() - packet.inputTicks)),
                                                    static_cast<unsigned>(handoff.permitAt));
            if (index == 0) {
                if (!sampled) {
                    Shipyard_OverlapSampleDepth(&packet.depth, &depth, PrepareDepth, ReadDepth, NULL);
                    sampled = true;
                }
                interpreter->XboxRetireGameDepth();
            }
            ++interpreter->mInterpolationIndex;
        }
    }
    interpreter->XboxRetireGameDepth();
    interpreter->XboxPublishGameDepth();
    handoff.Submit();
    handoff.Permit();
    ModernFrameProfile::End(ModernFrameProfile::Graphics);
    owner.PublishDepth(depth);
    renderingPacket = NULL;
    renderResourceOwners = NULL;
    replayGui = NULL;
    replayHandoff = NULL;
    ModernFrameProfile::Begin(ModernFrameProfile::AudioWait);
    ModernFrameProfile::ThreadSample audioProfile;
    WaitAudio(ticket.generation, &audioProfile);
    ModernFrameProfile::End(ModernFrameProfile::AudioWait);
    ModernFrameProfile::ObserveAudioSample(audioProfile);
    ModernFrameProfile::EndFrame();
    handoff.variables->UseSnapshot(NULL);
    if (!owner.worker.retire(ticket)) throw std::runtime_error("Replay retirement failed");
    if (handoff.forceStop) {
        deferredGuiIntent = handoff.started;
        owner.worker.stopAtHandoff(ticket);
    }
    return !handoff.forceStop;
}
}

extern "C" int Shipyard_OverlapIsGameWorker(void) { return ModernOverlap::onGameWorker ? 1 : 0; }
extern "C" int Shipyard_OverlapDrawGui(int begin) {
    if (!ModernOverlap::renderingPacket) return 0;
    if (begin && ModernOverlap::replayHandoff) ModernOverlap::replayHandoff->Begin();
    if (!begin && ModernOverlap::replayGui) {
        Shipyard_ImGuiDrawCache(*ModernOverlap::replayGui,
            Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer());
    }
    return 1;
}
extern "C" void Shipyard_OverlapFence(void) {
    ModernOverlap::Session::Blocked blocked;
    if (ModernOverlap::onGameWorker && !ModernOverlap::session->worker.fencePreviousReplay())
        ModernOverlap::AbortRuntime("Game replay fence aborted");
}
extern "C" void Shipyard_OverlapRunOnRender(void (*callback)(void*), void* context) {
    if (!callback) return;
    if (!ModernOverlap::onGameWorker) { callback(context); return; }
    Shipyard_OverlapFence();
    ModernOverlap::Session::Blocked blocked;
    if (!ModernOverlap::session->worker.runOnRender([callback, context]() { callback(context); }))
        ModernOverlap::AbortRuntime("Native render job aborted");
}
extern "C" int Shipyard_OverlapDeferRelease(ShipyardOverlapRelease release, void* owner, void* data,
                                          const char* file, int line) {
    if (!ModernOverlap::onGameWorker) return 0;
    ModernOverlap::session->storage.defer(ModernOverlap::session->worker, release, owner, data, file, line);
    return 1;
}
extern "C" void Shipyard_OverlapReleaseArena(void* owner) {
    ModernOverlap::Session::Blocked blocked;
    if (ModernOverlap::onGameWorker &&
        !ModernOverlap::session->storage.drainOwner(ModernOverlap::session->worker, owner))
        ModernOverlap::AbortRuntime("Arena retirement aborted");
}
extern "C" void Shipyard_OverlapRetryAllocation(void) {
    ModernOverlap::Session::Blocked blocked;
    if (ModernOverlap::onGameWorker &&
        !ModernOverlap::session->storage.retryAllocation(ModernOverlap::session->worker))
        ModernOverlap::AbortRuntime("Allocation retirement aborted");
}
extern "C" void Shipyard_OverlapTouchWritableSpan(void* pointer, size_t bytes) {
    if (!ModernOverlap::onGameWorker || !pointer || bytes == 0) return;
    ModernOverlap::Session& owner = *ModernOverlap::session;
    const uint64_t generation = owner.worker.buildingGeneration();
    uint64_t retired = owner.worker.retiredGeneration();
    if (owner.writableSpans.LatestReader(pointer, bytes, generation, retired)) {
        Shipyard_OverlapFence();
        retired = owner.worker.retiredGeneration();
    }
    owner.writableSpans.Record(pointer, bytes, generation, retired);
}
extern "C" void Shipyard_OverlapSaveStateBoundary(int restoring) {
    if (!ModernOverlap::onGameWorker) return;
    // Requests run after publication; retire frees before copying arena bytes.
    Shipyard_OverlapRetryAllocation();
    if (restoring) {
        ModernOverlap::Session& owner = *ModernOverlap::session;
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(owner.depthGate);
        owner.depthResults.clear();
    }
}
extern "C" int Shipyard_OverlapInputBlocked(unsigned kind, int* value) {
    if (!ModernOverlap::onGameWorker || kind >= 3 || !value) return 0;
    *value = ModernOverlap::session->inputBlocked[kind] ? 1 : 0;
    return 1;
}
extern "C" int Shipyard_OverlapMasterQuest(uint32_t* value) {
    if (!ModernOverlap::renderingPacket || !value) return 0;
    *value = ModernOverlap::renderingPacket->masterQuest;
    return 1;
}
void Shipyard_OverlapRetainResource(const std::shared_ptr<Ship::IResource>& resource) {
    if (!resource) return;
    if (ModernOverlap::onGameWorker)
        ModernOverlap::session->worker.buildingPacket().resources.push_back(resource);
    else if (ModernOverlap::renderResourceOwners)
        ModernOverlap::renderResourceOwners->push_back(resource);
}
extern "C" void Shipyard_OverlapStageDepth(const ShipyardOverlapDepthRequest* request) {
    if (ModernOverlap::onGameWorker && request)
        ModernOverlap::session->worker.buildingPacket().depth = *request;
}
extern "C" void Shipyard_OverlapRunGraphCallback(GraphicsContext* graphics,
    void (*callback)(GraphicsContext*, void*), void* parameter) {
    if (!callback) return;
    ModernOverlap::GraphCallbackJob job = {graphics, callback, parameter};
    Shipyard_OverlapRunOnRender(ModernOverlap::RunGraphCallback, &job);
}

static int Shipyard_OverlapRunFrameInternal(void (*runFrame)(void)) {
    using namespace ModernOverlap;
    std::shared_ptr<Ship::Gui> gui = Ship::Context::GetInstance()->GetWindow()->GetGui();
    if (capturingWarmup) {
        if (!Shipyard_ImGuiEndCapture()) passiveGui.reset();
        capturingWarmup = false;
    }
    if (!session) {
        if (!Requested() || gui->XboxHasInteractiveGui()) { passiveGui.reset(); return 0; }
        if (!passiveGui) {
            passiveGui.reset(new GuiFrameCache());
            Shipyard_ImGuiBeginCapture(passiveGui.get(), false);
            capturingWarmup = true;
            return 0;
        }
        ResetAudio();
        ModernFrameProfile::ResetGameSampleCadence();
        session = new Session(runFrame);
        deferredGuiIntent = false;
        session->CaptureInput();
        Shipyard_OverlapCaptureGraphics();
        // Render stays on processor 0; the mixer and XAudio engine use 2 and 3.
        session->worker.start(4);
    }
    GameWorker::Ticket ticket;
    const FramePacket* packet;
    if (!session->worker.acquireReady(ticket, packet)) {
        session->worker.joinPumping();
        delete session;
        session = NULL;
        return 1;
    }
    if (!RenderPacket(*session, ticket, *packet, !Requested())) {
        session->worker.joinPumping();
        if (deferredGuiIntent) gui->XboxCommitOverlapIntent();
        deferredGuiIntent = false;
        delete session;
        session = NULL;
        passiveGui.reset();
    }
    return 1;
}

static void Shipyard_OverlapShutdownInternal(void) {
    using namespace ModernOverlap;
    if (capturingWarmup) { Shipyard_ImGuiEndCapture(); capturingWarmup = false; }
    if (session) {
        GameWorker::Ticket ticket;
        const FramePacket* packet;
        if (session->worker.acquireReady(ticket, packet)) RenderPacket(*session, ticket, *packet, true);
        session->worker.joinPumping();
        if (deferredGuiIntent)
            Ship::Context::GetInstance()->GetWindow()->GetGui()->XboxCommitOverlapIntent();
        deferredGuiIntent = false;
        delete session;
        session = NULL;
    }
    passiveGui.reset();
}

#ifdef _XBOX
// catch(...) also takes hardware faults here; log the code and address while
// the faulting frame is still on the stack, then let the catch handle it.
static int LogFrameFault(EXCEPTION_POINTERS* info) {
    Shipyard_Log("Frame handoff fault: code=%08lx address=%p", info->ExceptionRecord->ExceptionCode,
                 info->ExceptionRecord->ExceptionAddress);
    return EXCEPTION_CONTINUE_SEARCH;
}
static int RunFrameLoggingFaults(void (*runFrame)(void)) {
    __try { return Shipyard_OverlapRunFrameInternal(runFrame); }
    __except (LogFrameFault(GetExceptionInformation())) { return 1; }
}
#else
static int RunFrameLoggingFaults(void (*runFrame)(void)) { return Shipyard_OverlapRunFrameInternal(runFrame); }
#endif

extern "C" int Shipyard_OverlapRunFrame(void (*runFrame)(void)) {
    try { return RunFrameLoggingFaults(runFrame); }
    catch (...) {
        ModernOverlap::LogException("Frame handoff threw");
        ModernOverlap::AbortRuntime("Frame handoff failed");
    }
    return 1;
}

extern "C" void Shipyard_OverlapShutdown(void) {
    try { Shipyard_OverlapShutdownInternal(); }
    catch (...) {
        ModernOverlap::LogException("Frame shutdown threw");
        ModernOverlap::AbortRuntime("Frame shutdown failed");
    }
}
