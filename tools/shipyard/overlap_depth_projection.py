"""Capture graph depth values on the game owner and reject reused light slots.

The sequential callback remains intact; packets never carry game pointers.
"""

from prepare_configuration import once

LIGHT_STATE = """static uint64_t sShipyardLightIncarnation[LIGHTS_BUFFER_SIZE];
static uint64_t sShipyardDepthSceneEpoch = 1;

uint64_t Shipyard_OverlapDepthSceneEpoch(void) {
    return sShipyardDepthSceneEpoch;
}

"""

LIGHT_HOOKS = """
void Shipyard_OverlapCaptureLights(PlayState* play, ShipyardOverlapDepthRequest* request) {
    LightNode* node;
    request->sceneEpoch = sShipyardDepthSceneEpoch;
    request->screenWidth = SCREEN_WIDTH;
    request->screenHeight = SCREEN_HEIGHT;
    request->shrink = ShrinkWindow_GetCurrentVal();
    for (node = play->lightCtx.listHead; node != NULL; node = node->next) {
        if (node->info->type == LIGHT_POINT_GLOW) {
            uint32_t slot = (uint32_t)(node - sLightsBuffer.buf);
            LightPoint* params = &node->info->params.point;
            Vec3f pos;
            Vec3f projected;
            float inverseW;
            ShipyardOverlapLightRequest* light;
            if (slot >= LIGHTS_BUFFER_SIZE || request->lightCount >= SHIPYARD_OVERLAP_LIGHT_COUNT)
                continue;
            light = &request->lights[request->lightCount++];
            pos.x = params->x;
            pos.y = params->y;
            pos.z = params->z;
            func_8002BE04(play, &pos, &projected, &inverseW);
            light->slot = slot;
            light->incarnation = sShipyardLightIncarnation[slot];
            light->x = projected.x * inverseW * 160 + 160;
            light->y = projected.y * inverseW * 120 + 120;
            light->eligible = projected.z > 1.0f && light->y >= request->shrink &&
                              light->y <= SCREEN_HEIGHT - request->shrink;
            if (light->eligible)
                light->projectedZ = (s32)((projected.z * inverseW) * 16352.0f) + 16352;
        }
    }
}

void Shipyard_OverlapApplyLights(const ShipyardOverlapDepthResult* result) {
    uint32_t i;
    if (!result->active || result->sceneEpoch != sShipyardDepthSceneEpoch) return;
    for (i = 0; i < result->lightCount && i < SHIPYARD_OVERLAP_LIGHT_COUNT; ++i) {
        const ShipyardOverlapLightResult* light = &result->lights[i];
        LightNode* node;
        if (light->slot >= LIGHTS_BUFFER_SIZE ||
            light->incarnation != sShipyardLightIncarnation[light->slot]) continue;
        node = &sLightsBuffer.buf[light->slot];
        if (node->info != NULL && node->info->type == LIGHT_POINT_GLOW)
            node->info->params.point.drawGlow = light->drawGlow != 0;
    }
}
"""

ENV_HOOKS = """
int Shipyard_OverlapCaptureGraphCallback(GraphicsContext* gfxCtx,
                                       void (*callback)(GraphicsContext*, void*), void* param) {
    ShipyardOverlapDepthRequest request;
    if (!Shipyard_OverlapIsGameWorker() || callback != Environment_GraphCallback) return 0;
    memset(&request, 0, sizeof(request));
    request.active = 1;
    request.sunX = D_8015FD7E;
    request.sunY = D_8015FD80;
    Shipyard_OverlapCaptureLights((PlayState*)param, &request);
    Shipyard_OverlapStageDepth(&request);
    return 1;
}

void Shipyard_OverlapApplyDepthResult(const ShipyardOverlapDepthResult* result) {
    if (!result->active || result->sceneEpoch != Shipyard_OverlapDepthSceneEpoch()) return;
    D_8011FB44 = result->sunDepth;
    Shipyard_OverlapApplyLights(result);
}
"""


def project(name, text):
    if name == "soh/src/code/z_lights.c":
        text = once(
            text,
            "LightsBuffer sLightsBuffer;",
            "LightsBuffer sLightsBuffer;\n\n" + LIGHT_STATE,
        )
        text = once(
            text,
            "    sLightsBuffer.numOccupied++;",
            "    sLightsBuffer.numOccupied++;\n    ++sShipyardLightIncarnation[node - sLightsBuffer.buf];",
        )
        text = once(
            text,
            "        light->info = NULL;",
            "        ++sShipyardLightIncarnation[light - sLightsBuffer.buf];\n        light->info = NULL;",
        )
        text = once(
            text,
            "    memset(&sLightsBuffer, 0, sizeof(sLightsBuffer));",
            "    ++sShipyardDepthSceneEpoch;\n    memset(&sLightsBuffer, 0, sizeof(sLightsBuffer));",
        )
        text = once(
            text,
            "void LightContext_DestroyList(PlayState* play, LightContext* lightCtx) {",
            "void LightContext_DestroyList(PlayState* play, LightContext* lightCtx) {\n    ++sShipyardDepthSceneEpoch;",
        )
        return '#include "overlap/depth.h"\n' + text + LIGHT_HOOKS
    if name == "soh/src/code/z_kankyo.c":
        declarations = """
#include "overlap/depth.h"
extern int Shipyard_OverlapIsGameWorker(void);
extern uint64_t Shipyard_OverlapDepthSceneEpoch(void);
extern void Shipyard_OverlapCaptureLights(PlayState*, ShipyardOverlapDepthRequest*);
extern void Shipyard_OverlapApplyLights(const ShipyardOverlapDepthResult*);
"""
        return (
            once(text, '#include "global.h"', '#include "global.h"\n' + declarations)
            + ENV_HOOKS
        )
    return text
