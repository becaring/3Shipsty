"""Check audio barrier insertion and the overlap runtime handoff edits."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
import overlap_audio_barrier_projection as projection
from overlap_audio_barrier_projection import game, runtime


def main():
    source = """void Audio_QueueCmd(u32 opArgs, u32 data) {
    s32 slot = 0;
    gAudioContext.cmdBuf[slot] = data;
}
void func_800E5EDC(void) {
    s32 pos = 1;
    send(pos);
}
void Audio_PlaySoundGeneral(u16 sfxId) {
    request(sfxId);
}
"""
    projection.BARRIERS["soh/src/code/code_800E4FE0.c"] = ("func_800E5EDC",)
    projected = game("soh/src/code/code_800E4FE0.c", source)
    assert projected.startswith("void Shipyard_OverlapAudioBarrier(void);")
    assert "{\n    if (Shipyard_OverlapAudioStage(0, opArgs, data)) return;\n    {\n    s32 slot" in projected
    assert "{\n    Shipyard_OverlapAudioBarrier();\n    {\n    s32 pos = 1;\n    send(pos);\n}}" in projected
    assert "{\n    request(sfxId);\n}" in projected
    assert game("soh/src/code/z_actor.c", source) == source

    inc = (ROOT / "platform/shipyard/application/overlap_runtime.inc").read_text(encoding="utf-8")
    out = runtime(inc)
    publish = out[out.index("static bool PublishCommands"):out.index("static void PrepareDepth")]
    assert "WaitAudio" not in publish and "DrainAudio(*session);" in publish
    handoff = out[out.index("    void Submit() {"):out.index("    void Begin() {")]
    assert "SubmitAudio" not in handoff
    build = out[out.index("    static void BuildFrame"):out.index("    void ApplyDepth()")]
    assert build.index("SubmitAudio(") < build.index("owner.runFrame();") < build.index("DrainAudio(owner);")
    render = out[out.index("static bool RenderPacket(Session& owner"):]
    assert "WaitAudio" not in render[:render.index("extern \"C\" int Shipyard_OverlapIsGameWorker")]
    print("overlap audio barrier: ok")


if __name__ == "__main__":
    main()
