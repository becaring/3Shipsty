"""Reuse owned texture resolutions within an interpolation batch.

Command state still executes on every replay, including the upstream pointer
patch. A miss runs the unchanged resolver; batches, dirty resources and explicit
cache invalidations bound reuse. Paths and metadata never borrow cache slots.
"""
from prepare_configuration import once

HELPERS = r'''
// Requested mode is sampled at batch boundaries; counters have one render writer.
extern "C" volatile unsigned gModernTextureReplayControl[8] = { 1, 0, 0, 0, 0, 0, 0, 0 };
typedef Shipyard::Fast3D::TextureReplayCache<RawTexMetadata> ModernTextureReplays;
static __declspec(thread) ModernTextureReplays* sModernTextureReplays = NULL;
static void ModernBeginTextureReplays(unsigned count) {
    const bool enabled = gModernTextureReplayControl[0] != 0;
    gModernTextureReplayControl[1] = enabled ? 1 : 0;
    if (!enabled) count = 0;
    if (!sModernTextureReplays && count > 1) sModernTextureReplays = new ModernTextureReplays;
    if (sModernTextureReplays) sModernTextureReplays->Begin(count);
}
static void ModernEndTextureReplays() {
    if (sModernTextureReplays) {
        gModernTextureReplayControl[3] += sModernTextureReplays->hits;
        gModernTextureReplayControl[4] += sModernTextureReplays->misses;
        gModernTextureReplayControl[5] += sModernTextureReplays->stores;
        gModernTextureReplayControl[6] += sModernTextureReplays->clears;
    }
    if (sModernTextureReplays) sModernTextureReplays->End();
    ++gModernTextureReplayControl[2];
}
static void ModernClearTextureReplays() {
    if (sModernTextureReplays) sModernTextureReplays->Clear();
}
'''

WRAPPER = r'''
bool gfx_set_timg_otr_hash_handler_custom(F3DGfx** cmd0) {
    F3DGfx* cmd = *cmd0;
    const uint64_t hash = (static_cast<uint64_t>(cmd[1].words.w0) << 32) + cmd[1].words.w1;
    Interpreter* gfx = XboxDispatchInterpreter();
    const ModernTextureReplays::Entry* hit = sModernTextureReplays ? sModernTextureReplays->Lookup(gfx, hash) : NULL;
    if (!hit) return ModernResolveTextureHash(cmd0);
    ModernFrameProfile::TextureHashSample sample;
    ModernFrameProfile::BeginTextureHash(sample);
    if (ModernFrameProfile::CaptureResourceLookups()) ModernFrameProfile::ObserveTextureHashCache(true);
    // The command's format/size/width can differ even when its hash is shared.
    char* pixels = reinterpret_cast<char*>(hit->metadata.resource->ImageData);
    if (pixels) {
        cmd->words.w1 = reinterpret_cast<uintptr_t>(pixels);
        gfx->GfxDpSetTextureImage(C0(21, 3), C0(19, 2), C0(0, 12) + 1,
                                 hit->path.c_str(), hit->flags, hit->metadata, pixels);
    }
    ++(*cmd0);
    if (sample.sampled) ModernFrameProfile::EndTextureHash(sample);
    return false;
}
'''


def transform(text):
    text = '#include "fast3d/texture_replay.h"\n' + text
    text = once(text, 'static void ModernReleaseMaterialMemos();',
                HELPERS + '\nstatic void ModernReleaseMaterialMemos();')
    text = once(text, 'void ModernVertexReuseBeginBatch(unsigned replayCount) {',
                'void ModernVertexReuseBeginBatch(unsigned replayCount) {\n    ModernBeginTextureReplays(replayCount);')
    text = once(text, 'void ModernVertexReuseEndBatch() {',
                'void ModernVertexReuseEndBatch() {\n    ModernEndTextureReplays();')
    for signature in ('void Interpreter::TextureCacheClear() {',
                      'void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {',
                      'void Interpreter::RunGuiOnly() {'):
        text = once(text, signature, signature + '\n    ModernClearTextureReplays();')
    text = once(text, '    ModernReleaseMaterialMemos();',
                '    ModernReleaseMaterialMemos();\n    delete sModernTextureReplays;\n    sModernTextureReplays = NULL;')
    signature = 'bool gfx_set_timg_otr_hash_handler_custom(F3DGfx** cmd0) {'
    start = text.index(signature)
    end = text.index('\n}', start) + 2
    slow = text[start:end].replace(signature, 'static __declspec(noinline) bool ModernResolveTextureHash(F3DGfx** cmd0) {')
    anchor = '            gfx->GfxDpSetTextureImage(fmt, size, width, fileName, texFlags, rawTexMetadata, tex);'
    slow = once(slow, anchor,
                '            if (sModernTextureReplays)\n'
                '                sModernTextureReplays->Store(gfx, hash, fileName, texFlags, rawTexMetadata);\n' + anchor)
    return text[:start] + slow + '\n' + WRAPPER + text[end:]
