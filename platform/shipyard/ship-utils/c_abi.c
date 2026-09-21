#include "soh/ShipUtils.h"
static f32 (*aspect_signature)(void) = Ship_GetExtendedAspectRatioMultiplier;
static void (*vertex_signature)(Vtx*, s32, s32, s32, s32, u8) = Ship_CreateQuadVertexGroup;
int shipyard_empty_from_c(const char* str) { return Ship_IsCStringEmpty(str); }
static void (*actor_signature)(struct Actor*) = Ship_ExtendedCullingActorAdjustProjectedX;
static void (*restore_signature)(struct PlayState*, struct Actor*) = Ship_ExtendedCullingActorRestoreProjectedPos;
