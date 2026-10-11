// Exercise the projected viewer callback while an earlier replay borrows its lists.
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

using Gfx = uint64_t;
static std::vector<Gfx> opaDl, xluDl, vtxDl, mtxDl;
static unsigned fences, resets, submitted;
static bool enabled, borrowed;
struct PlayState { struct { void* gfxCtx; } state; } play;
static PlayState* gPlayState = &play;
static Gfx commands[64];
static Gfx* POLY_OPA_DISP = commands;
static Gfx* POLY_XLU_DISP = commands + 32;
#define CVAR_DEVELOPER_TOOLS(name) name
#define CVAR_ENHANCEMENT(name) name
#define OPEN_DISPS(context)
#define CLOSE_DISPS(context)
#define SPDLOG_WARN(...) assert(false)
static const int G_EX_INVERT_CULLING = 1;
static int CVarGetInteger(const char* name, int) {
    return std::strcmp(name, "ColViewer.Enabled") == 0 && enabled;
}
static void Shipyard_OverlapFence() { ++fences; borrowed = false; }
template <typename T> size_t ResetVector(T& vec) {
    assert(!borrowed);
    ++resets;
    size_t oldSize = vec.size();
    vec.clear();
    vec.reserve(static_cast<size_t>(oldSize * 1.2));
    return vec.capacity();
}
static void DrawSceneCollision() {
    opaDl.push_back(10); xluDl.push_back(20);
    vtxDl.push_back(30); mtxDl.push_back(40);
}
static void DrawBgActorCollision() {}
static void DrawScarecrowSpawns() {}
static void DrawColCheckCollision() {}
static void DrawWaterboxList() {}
static Gfx gsSPEndDisplayList() { return 255; }
static void gSPDisplayList(Gfx*, Gfx*) { ++submitted; }
static void gSPSetExtraGeometryMode(Gfx*, int) {}
static void gSPClearExtraGeometryMode(Gfx*, int) {}

// DRAW_COL_VIEWER

int main() {
    for (unsigned i = 0; i < 20; ++i) DrawColViewer();
    assert(fences == 0 && resets == 0 && submitted == 0);
    assert(opaDl.empty() && xluDl.empty() && vtxDl.empty() && mtxDl.empty());

    enabled = true;
    DrawColViewer();
    assert(fences == 0 && submitted == 2);
    assert(opaDl.back() == 255 && xluDl.back() == 255);
    const auto opa = opaDl, xlu = xluDl, vtx = vtxDl, mtx = mtxDl;
    const auto opaPtr = opaDl.data(), xluPtr = xluDl.data(), vtxPtr = vtxDl.data(), mtxPtr = mtxDl.data();
    const unsigned savedResets = resets;
    borrowed = true;
    enabled = false;
    for (unsigned i = 0; i < 20; ++i) DrawColViewer();
    assert(borrowed && fences == 0 && resets == savedResets && submitted == 2);
    assert(opaDl == opa && xluDl == xlu && vtxDl == vtx && mtxDl == mtx);
    assert(opaDl.data() == opaPtr && xluDl.data() == xluPtr && vtxDl.data() == vtxPtr && mtxDl.data() == mtxPtr);

    enabled = true;
    DrawColViewer();
    assert(!borrowed && fences == 1 && submitted == 4);
    borrowed = true;
    gPlayState = nullptr;
    DrawColViewer();
    assert(borrowed && fences == 1 && submitted == 4);
}
