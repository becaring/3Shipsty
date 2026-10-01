"""Keep the game state machine intact while its outer loop selects frame ownership.

Arena storage retires on the game owner after the last replay that can borrow it.
Reallocation fences before the allocator lock because it can overwrite old bytes.
"""

from prepare_configuration import once

ARENA_DECLARATIONS = """
typedef void (*ShipyardOverlapRelease)(void*, void*, const char*, int);
extern int Shipyard_OverlapDeferRelease(ShipyardOverlapRelease release, void* owner, void* data,
                                      const char* file, int line);
extern void Shipyard_OverlapFence(void);
extern void Shipyard_OverlapReleaseArena(void* arena);
extern void Shipyard_OverlapRetryAllocation(void);
extern int Shipyard_OverlapIsGameWorker(void);
"""


def arena_allocation_retry(text):
    from overlap_lifetime_projection import functions

    for name, declaration, arguments in (
        ("__osMalloc", "Arena* arena, size_t size", "arena, size"),
        ("__osMallocR", "Arena* arena, size_t size", "arena, size"),
        (
            "__osMallocDebug",
            "Arena* arena, size_t size, const char* file, int line",
            "arena, size, file, line",
        ),
        (
            "__osMallocRDebug",
            "Arena* arena, size_t size, const char* file, int line",
            "arena, size, file, line",
        ),
    ):
        (node,) = functions(text, name)
        raw = text.encode()
        original = raw[node.start_byte : node.end_byte].decode()
        helper = "Shipyard_Arena" + name[2:]
        original = "static " + once(original, name + "(", helper + "(")
        wrapper = (
            """
void* NAME(DECLARATION) {
    void* allocation = HELPER(ARGUMENTS);
    if (allocation == NULL && Shipyard_OverlapIsGameWorker()) {
        // The original attempt released the arena lock before waiting.
        Shipyard_OverlapRetryAllocation();
        allocation = HELPER(ARGUMENTS);
    }
    return allocation;
}
""".replace(
                "NAME", name
            )
            .replace("DECLARATION", declaration)
            .replace("HELPER", helper)
            .replace("ARGUMENTS", arguments)
        )
        text = (
            raw[: node.start_byte]
            + (original + wrapper).encode()
            + raw[node.end_byte :]
        ).decode()
    return text


def project(name, text):
    if name == "soh/src/code/graph.c":
        deferred = """    Graph_RunDeferredCallback();
    sShipyardDeferredCallback = gfxCtx->callback;
    sShipyardDeferredGfxCtx = gfxCtx;
    sShipyardDeferredParam = gfxCtx->callbackParam;"""
        if deferred in text:
            text = (
                """struct GraphicsContext;
extern int Shipyard_OverlapIsGameWorker(void);
extern int Shipyard_OverlapCaptureGraphCallback(struct GraphicsContext*,
    void (*)(struct GraphicsContext*, void*), void*);
extern void Shipyard_OverlapRunGraphCallback(struct GraphicsContext*,
    void (*)(struct GraphicsContext*, void*), void*);
"""
                + text
            )
            text = once(
                text,
                deferred,
                """    if (Shipyard_OverlapIsGameWorker()) {
        if (gfxCtx->callback != NULL &&
            !Shipyard_OverlapCaptureGraphCallback(gfxCtx, gfxCtx->callback, gfxCtx->callbackParam)) {
            Shipyard_OverlapRunGraphCallback(gfxCtx, gfxCtx->callback, gfxCtx->callbackParam);
        }
    } else {
        Graph_RunDeferredCallback();
        sShipyardDeferredCallback = gfxCtx->callback;
        sShipyardDeferredGfxCtx = gfxCtx;
        sShipyardDeferredParam = gfxCtx->callbackParam;
    }""",
            )
        text = once(
            text,
            "void Graph_ThreadEntry(void* arg0) {\n    while (WindowIsRunning()) {\n        RunFrame();\n    }\n}",
            """extern int Shipyard_OverlapRunFrame(void (*runFrame)(void));
extern void Shipyard_OverlapShutdown(void);

void Graph_ThreadEntry(void* arg0) {
    while (WindowIsRunning()) {
        if (!Shipyard_OverlapRunFrame(RunFrame)) RunFrame();
    }
    Shipyard_OverlapShutdown();
}""",
        )
        text += """
// Requested is checked only while the producer is idle at its handoff.
int Shipyard_OverlapNeedsFullSync(void) {
    PlayState* play;
    if (gGameState == NULL || gGameState->main != Play_Main || !gGameState->running) return 1;
    play = (PlayState*)gGameState;
    return play->pauseCtx.state != 0 || play->pauseCtx.debugState != 0 ||
           R_PAUSE_MENU_MODE != 0 || play->frameAdvCtx.enabled ||
           play->transitionMode != TRANS_MODE_OFF || play->transitionTrigger != TRANS_TRIGGER_OFF ||
           gTrnsnUnkState != 0 || play->gameOverCtx.state != GAMEOVER_INACTIVE || HREG(80) == 10;
}
"""
    if name == "soh/src/code/z_play.c":
        text = "extern int Shipyard_OverlapNeedsFullSync(void);\n" + text
        text = once(
            text,
            "void Play_Main(GameState* thisx) {\n    PlayState* play = (PlayState*)thisx;",
            """void Play_Main(GameState* thisx) {
    PlayState* play = (PlayState*)thisx;
    if (Shipyard_OverlapNeedsFullSync()) Shipyard_OverlapFence();""",
        )
        text = once(
            text,
            "    FrameInterpolation_StartRecord();\n    Play_Draw(play);",
            """    // Pause and frame advance can start inside this update.
    if (Shipyard_OverlapNeedsFullSync()) Shipyard_OverlapFence();
    FrameInterpolation_StartRecord();
    Play_Draw(play);""",
        )
    if name == "soh/src/code/__osMalloc.c":
        text = ARENA_DECLARATIONS + text
        text = once(
            text,
            "void __osMallocCleanup(Arena* arena) {",
            "void __osMallocCleanup(Arena* arena) {\n    Shipyard_OverlapReleaseArena(arena);",
        )
        text = arena_allocation_retry(text)
        text = once(
            text,
            """void __osFree(Arena* arena, void* ptr) {
    ArenaImpl_Lock(arena);
    __osFree_NoLock(arena, ptr);
    ArenaImpl_Unlock(arena);
}""",
            """static void Shipyard_ArenaFree(void* owner, void* ptr, const char* file, int line) {
    Arena* arena = (Arena*)owner;
    ArenaImpl_Lock(arena);
    __osFree_NoLock(arena, ptr);
    ArenaImpl_Unlock(arena);
}

void __osFree(Arena* arena, void* ptr) {
    if (Shipyard_OverlapDeferRelease(Shipyard_ArenaFree, arena, ptr, NULL, 0)) return;
    Shipyard_ArenaFree(arena, ptr, NULL, 0);
}""",
        )
        text = once(
            text,
            """void __osFreeDebug(Arena* arena, void* ptr, const char* file, int line) {
    ArenaImpl_Lock(arena);
    __osFree_NoLockDebug(arena, ptr, file, line);
    ArenaImpl_Unlock(arena);
}""",
            """static void Shipyard_ArenaFreeDebug(void* owner, void* ptr, const char* file, int line) {
    Arena* arena = (Arena*)owner;
    ArenaImpl_Lock(arena);
    __osFree_NoLockDebug(arena, ptr, file, line);
    ArenaImpl_Unlock(arena);
}

void __osFreeDebug(Arena* arena, void* ptr, const char* file, int line) {
    if (Shipyard_OverlapDeferRelease(Shipyard_ArenaFreeDebug, arena, ptr, file, line)) return;
    Shipyard_ArenaFreeDebug(arena, ptr, file, line);
}""",
        )
        text = once(
            text,
            "    newSize = ALIGN16(newSize);",
            "    Shipyard_OverlapFence();\n    newSize = ALIGN16(newSize);",
        )
    return text
