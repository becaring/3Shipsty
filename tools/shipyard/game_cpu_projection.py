"""Skip saturated light binding and zero-weight animation work without changing output."""


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Game CPU projection source drift: " + old[:80])
    return text.replace(old, new)


def project(name, text):
    if name.endswith("/z_actor.c"):
        text = actor(text)
    if name.endswith("/z_lights.c"):
        text = once(text, "while (listHead != NULL) {",
                    "while (listHead != NULL && lights->numLights < 7) {")
    if name.endswith("/z_skelanime.c"):
        old = """        SkelAnime_GetFrameData(skelAnime->animation, frame, skelAnime->limbCount, nextjointTable);
        SkelAnime_InterpFrameTable(skelAnime->limbCount, skelAnime->jointTable, skelAnime->jointTable, nextjointTable,
                                   partialFrame);"""
        text = once(text, old, "        if (partialFrame != 0.0f) {\n" + old + "\n        }")
    return text


def actor(text):
    signature = """s32 Ship_CalcShouldDrawAndUpdate(PlayState* play, Actor* actor, Vec3f* projectedPos, f32 projectedW, bool* shouldDraw,
                                 bool* shouldUpdate) {"""
    internal = """typedef struct {
    s32 distance;
    s32 widescreen;
    bool hasWidescreen;
} ShipActorCullSettings;

static s32 Ship_CalcShouldDrawAndUpdateWithSettings(PlayState* play, Actor* actor, Vec3f* projectedPos,
    f32 projectedW, bool* shouldDraw, bool* shouldUpdate, const ShipActorCullSettings* settings) {"""
    start = text.index(signature)
    end = text.index("\n// #endregion", start)
    body = text[start:end]
    body = once(body, signature, internal)
    body = once(body, '    s32 multiplier = CVarGetInteger(CVAR_ENHANCEMENT("DisableDrawDistance"), 1);',
                '    s32 multiplier = settings ? settings->distance : '
                'CVarGetInteger(CVAR_ENHANCEMENT("DisableDrawDistance"), 1);')
    body = once(body, 'if (CVarGetInteger(CVAR_ENHANCEMENT("WidescreenActorCulling"), 0)) {',
                'if (settings && settings->hasWidescreen ? settings->widescreen : '
                'CVarGetInteger(CVAR_ENHANCEMENT("WidescreenActorCulling"), 0)) {')
    wrapper = signature + """
    return Ship_CalcShouldDrawAndUpdateWithSettings(play, actor, projectedPos, projectedW, shouldDraw, shouldUpdate, NULL);
}
"""
    text = text[:start] + body + '\n' + wrapper + text[end:]
    old = """                if (CVarGetInteger(CVAR_ENHANCEMENT("DisableDrawDistance"), 1) > 1 ||
                    CVarGetInteger(CVAR_ENHANCEMENT("WidescreenActorCulling"), 0)) {
                    Ship_CalcShouldDrawAndUpdate(play, actor, &actor->projectedPos, actor->projectedW, &shipShouldDraw,
                                                 &shipShouldUpdate);"""
    new = """                ShipActorCullSettings settings;
                settings.distance = CVarGetInteger(CVAR_ENHANCEMENT("DisableDrawDistance"), 1);
                settings.widescreen = 0;
                settings.hasWidescreen = settings.distance <= 1;
                if (settings.hasWidescreen) {
                    settings.widescreen = CVarGetInteger(CVAR_ENHANCEMENT("WidescreenActorCulling"), 0);
                }
                if (settings.distance > 1 || settings.widescreen) {
                    Ship_CalcShouldDrawAndUpdateWithSettings(play, actor, &actor->projectedPos, actor->projectedW,
                        &shipShouldDraw, &shipShouldUpdate, &settings);"""
    text = once(text, old, new)
    old = """            char* actorName = ActorDB_Retrieve(actor->id)->name;

            gDPNoOpString(POLY_OPA_DISP++, actorName, i);
            gDPNoOpString(POLY_XLU_DISP++, actorName, i);"""
    new = """            if (GfxDebuggerIsDebugging() || GfxDebuggerIsDebuggingRequested()) {
                char* actorName = ActorDB_Retrieve(actor->id)->name;
                gDPNoOpString(POLY_OPA_DISP++, actorName, i);
                gDPNoOpString(POLY_XLU_DISP++, actorName, i);
            }"""
    return once(text, old, new)
