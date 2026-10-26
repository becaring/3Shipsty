"""Run each overlap generation's audio beside game logic instead of after publish.

Audio starts when the game frame starts; game functions that touch globals the
audio thread reaches wait for it at entry. Command queue writes made before then
are staged and replayed in order, so the audio thread consumes the same batches.
"""

import re
from cpp_ast import PARSER, walk

BARRIERS = {
    "soh/src/code/code_800EC960.c": (
        "AudioDebug_Draw", "AudioDebug_ProcessInput_SndCont",
        "AudioDebug_ProcessInput_SubTrackInfo", "Audio_ComputeSoundReverb",
        "Audio_DisableAllSeq", "Audio_OcaAdjStick", "Audio_OcaSetInstrument",
        "Audio_PlaySoundIncreasinglyTransposed", "Audio_PlaySoundTransposed",
        "Audio_SetGanonDistVol", "Audio_SplitBgmChannels", "func_800F3054",
        "func_800F56A8", "func_800F6BDC", "func_800F7170",
    ),
    "soh/src/code/audio_heap.c": ("AudioHeap_InitMainPools", "AudioHeap_ReleaseNotesForFont"),
    "soh/src/code/audio_load.c": (
        "AudioLoad_GetFontsForSequence", "AudioLoad_GetSamplesForFont", "AudioLoad_Init",
        "AudioLoad_InitSoundFontMeta", "AudioLoad_InitSwapFont", "AudioLoad_InitTable",
        "AudioLoad_IsSampleLoadComplete", "AudioLoad_SyncLoadSimple",
    ),
    "soh/src/code/code_800E4FE0.c": (
        "Audio_DestroyExternalPool", "Audio_GetGameVolume", "Audio_InitExternalPool",
        "Audio_InitMesgQueuesInternal", "Audio_PreNMIInternal", "Audio_ResetCmdQueue",
        "Audio_SetGameVolume", "Audio_WaitForAudioTask", "func_800E5000", "func_800E5E20",
        "func_800E5EA4", "func_800E5EDC", "func_800E5F34", "func_800E5F88", "func_800E6070",
        "func_800E60C4", "func_800E6590", "func_800E6680", "func_800E66A0",
    ),
    "soh/src/code/code_800F7260.c": ("Audio_PlayActiveSounds", "Audio_ProcessSoundRequest", "func_800F8F88"),
    "soh/src/code/code_800F9280.c": (
        "Audio_ProcessSeqCmds", "Audio_QueuePreviewSeqCmd", "func_800F9280", "func_800F9474",
        "func_800FA0B4", "func_800FA11C", "func_800FA3DC",
    ),
    # The audio thread reads gPlayState->sceneNum while initializing sequences.
    "soh/src/code/z_play.c": ("Play_Destroy",),
}
STAGED = {
    "soh/src/code/code_800E4FE0.c": ("Audio_QueueCmd", "if (Shipyard_OverlapAudioStage(0, opArgs, data)) return;"),
    "soh/src/code/code_800F9280.c": ("Audio_QueueSeqCmd", "if (Shipyard_OverlapAudioStage(1, cmd, 0)) return;"),
}
PROTOTYPES = (
    "void Shipyard_OverlapAudioBarrier(void);\n"
    "int Shipyard_OverlapAudioStage(unsigned kind, unsigned a, unsigned b);\n"
)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected one audio barrier anchor: " + old)
    return text.replace(old, new)


def game(name, text):
    name = name.replace("\\", "/")
    entries = [(function, "Shipyard_OverlapAudioBarrier();") for function in BARRIERS.get(name, ())]
    if name in STAGED:
        entries.append(STAGED[name])
    if not entries:
        return text
    raw = text.encode()
    bodies = []
    for function, code in entries:
        pattern = re.compile(r"\b" + re.escape(function) + r"\s*\(")
        nodes = [
            node for node in walk(PARSER.parse(raw).root_node)
            if node.type == "function_definition"
            and pattern.search(node.child_by_field_name("declarator").text.decode())
        ]
        if len(nodes) != 1:
            raise ValueError("Expected one audio barrier function: " + function)
        bodies.append((nodes[0].child_by_field_name("body"), code))
    # Nested blocks keep C89 declarations first after the inserted statement.
    for body, code in sorted(bodies, key=lambda item: -item[0].start_byte):
        raw = (raw[: body.start_byte + 1] + ("\n    " + code + "\n    {").encode()
               + raw[body.start_byte + 1 : body.end_byte - 1] + b"}" + raw[body.end_byte - 1 :])
    return PROTOTYPES + raw.decode()


def runtime(text):
    """Project overlap_runtime.inc, alone or inlined into OTRGlobals.cpp."""
    text = once(text, "    ModernFrameProfile::ThreadSample gameProfile;\n",
                "    ModernFrameProfile::ThreadSample gameProfile;\n"
                "    ModernFrameProfile::ThreadSample audioProfile;\n")
    text = once(text, "        gameProfile = other.gameProfile;\n",
                "        gameProfile = other.gameProfile;\n        audioProfile = other.audioProfile;\n")
    text = once(text, "\nstruct Session {\n", """
struct StagedAudio { unsigned kind; uint32_t a, b; };
static void DrainAudio(Session& owner);

struct Session {
""")
    text = once(text, "    ModernFrameProfile::ThreadSample tailProfile;\n", """\
    ModernFrameProfile::ThreadSample tailProfile;
    ModernFrameProfile::ThreadSample audioSample;
    std::vector<StagedAudio> stagedAudio;
    uint64_t pendingAudio;
""")
    text = once(text, "worker(BuildFrame, NULL) {", "worker(BuildFrame, NULL), pendingAudio(0) {")
    text = once(text, "        ModernFrameProfile::BeginThreadSample(packet.gameProfile, packet.profile);\n", """\
        ModernFrameProfile::BeginThreadSample(packet.gameProfile, packet.profile);
        // This generation's audio consumes the previous Audio_Update beside game logic.
        packet.audioProfile = owner.audioSample;
        SubmitAudio(owner.worker.buildingGeneration(), R_UPDATE_RATE, packet.profile);
        owner.pendingAudio = owner.worker.buildingGeneration();
""")
    text = once(text, "            owner.runFrame();\n", "            owner.runFrame();\n            DrainAudio(owner);\n")
    text = once(text, "\nstatic bool Requested() {", """
extern "C" void Audio_QueueCmd(uint32_t opArgs, uint32_t data);
extern "C" void Audio_QueueSeqCmd(uint32_t cmd);
static void DrainAudio(Session& owner) {
    const uint64_t generation = owner.pendingAudio;
    if (!generation) return;
    WaitAudio(generation, &owner.audioSample);
    owner.pendingAudio = 0;
    for (size_t index = 0; index < owner.stagedAudio.size(); ++index) {
        const StagedAudio& command = owner.stagedAudio[index];
        if (command.kind) Audio_QueueSeqCmd(command.a);
        else Audio_QueueCmd(command.a, command.b);
    }
    owner.stagedAudio.clear();
}

static bool Requested() {""")
    text = once(text, "    WaitAudio(generation);\n", "")
    text = once(text, "    if (prevAltAssets != alternate) {\n",
                "    if (prevAltAssets != alternate) {\n        DrainAudio(*session);\n")
    text = once(text, "        SubmitAudio(ticket.generation, packet.replay.updateRate, packet.profile);\n", "")
    text = once(text, """\
    ModernFrameProfile::Begin(ModernFrameProfile::AudioWait);
    ModernFrameProfile::ThreadSample audioProfile;
    WaitAudio(ticket.generation, &audioProfile);
    ModernFrameProfile::End(ModernFrameProfile::AudioWait);
    ModernFrameProfile::ObserveAudioSample(audioProfile);
""", "    ModernFrameProfile::ObserveAudioSample(packet.audioProfile);\n")
    text = once(text, '\nextern "C" void Shipyard_OverlapRunOnRender(', """
extern "C" void Shipyard_OverlapAudioBarrier(void) {
    if (ModernOverlap::onGameWorker) ModernOverlap::DrainAudio(*ModernOverlap::session);
}
extern "C" int Shipyard_OverlapAudioStage(unsigned kind, unsigned a, unsigned b) {
    if (!ModernOverlap::onGameWorker || !ModernOverlap::session->pendingAudio) return 0;
    const ModernOverlap::StagedAudio command = {kind, a, b};
    ModernOverlap::session->stagedAudio.push_back(command);
    return 1;
}
extern "C" void Shipyard_OverlapRunOnRender(""")
    return once(text, "    if (!ModernOverlap::onGameWorker) return;\n    // Requests run after publication;",
                "    if (!ModernOverlap::onGameWorker) return;\n"
                "    ModernOverlap::DrainAudio(*ModernOverlap::session);\n"
                "    // Requests run after publication;")
