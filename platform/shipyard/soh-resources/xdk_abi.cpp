#include <fast/lus_gbi.h>
#include <ship/utils/binarytools/endianness.h>
#include "soh/resource/type/Array.h"
#include "soh/resource/type/Text.h"
#include "soh/resource/type/Cutscene.h"
#include "soh/resource/type/SohResourceType.h"
#include "soh/resource/type/Animation.h"
#include "soh/resource/type/CollisionHeader.h"
#include "soh/resource/type/SkeletonLimb.h"
#include "soh/resource/type/Path.h"
#include "soh/resource/type/AudioSequence.h"
#include "soh/resource/type/AudioSoundFont.h"
#include <cstddef>
#ifndef _XBOX
#error This ABI contract must use the actual Xenon compiler.
#endif
#ifndef _CPPRTTI
#error SoundFont patch loading requires RTTI for its actual dynamic_pointer_cast.
#endif
typedef char native_big[(Ship::Endianness::Native == Ship::Endianness::Big) ? 1 : -1];
typedef char marker_values[(Ship::Endianness::Little == 0 && Ship::Endianness::Big == 1) ? 1 : -1];
typedef char pointer_size[(sizeof(void*) == 4) ? 1 : -1];
typedef char scalar_size[(sizeof(SOH::ScalarData) == 8) ? 1 : -1];
typedef char vertex_size[(sizeof(Fast::F3DVtx) == 16) ? 1 : -1];
typedef char vertex_tc_offset[(offsetof(Fast::F3DVtx_t, tc) == 8) ? 1 : -1];
typedef char vertex_color_offset[(offsetof(Fast::F3DVtx_t, cn) == 12) ? 1 : -1];
typedef char resource_tag[(SOH::ResourceType::SOH_Cutscene == 0x4f435654) ? 1 : -1];
typedef char array_tags[(SOH::ArrayResourceType::Scalar == 16 && SOH::ArrayResourceType::Vertex == 25) ? 1 : -1];
typedef char animation_header[(sizeof(SOH::AnimationHeader)==16 && sizeof(SOH::TransformUpdateIndex)==16) ? 1 : -1];
typedef char collision_header[(sizeof(SOH::CollisionHeaderData)==48 && offsetof(SOH::CollisionHeaderData,cameraDataListLen)==44) ? 1 : -1];
typedef char collision_polygon[(sizeof(SOH::CollisionPoly)==16 && offsetof(SOH::CollisionPoly,dist)==14) ? 1 : -1];
typedef char limb_layout[(sizeof(SOH::LodLimb)==16 && sizeof(SOH::SkinVertex)==10 && sizeof(SOH::SkinTransformation)==10) ? 1 : -1];
typedef char path_layout[(sizeof(SOH::PathData)==8 && offsetof(SOH::PathData,points)==4) ? 1 : -1];
typedef char audio_layout[(sizeof(SOH::Sequence)==32 && sizeof(SOH::Sample)==24 && sizeof(SOH::SoundFont)==24) ? 1 : -1];
typedef char envelope_layout[(sizeof(SOH::AdsrEnvelope)==4 && BE16SWAP(0x1234)==0x1234) ? 1 : -1];
