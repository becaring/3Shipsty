#pragma once
#include "fast3d/vertex_transform.h"
namespace Shipyard { namespace Fast3D {
bool CampaignTransformDirect(const void*,size_t,const float[4][4],void*,bool,size_t);
bool CampaignTransformDirectProfiled(const void*,size_t,const float[4][4],void*,bool,size_t,const TransformPhaseHook*);
} }

namespace Shipyard { namespace Fast3D {bool CampaignTransformThree(const void*,size_t,const float[3][4][4],void* const[3],size_t);}}
