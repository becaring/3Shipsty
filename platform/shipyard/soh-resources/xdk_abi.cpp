#include <fast/lus_gbi.h>
#include <ship/utils/binarytools/endianness.h>
#include "soh/resource/type/Array.h"
#include "soh/resource/type/Text.h"
#include "soh/resource/type/Cutscene.h"
#include "soh/resource/type/SohResourceType.h"
#include "soh/resource/type/Animation.h"
#include "soh/resource/type/CollisionHeader.h"
#include "soh/resource/type/SkeletonLimb.h"
#include "soh/resource/type/Skeleton.h"
#include "soh/resource/type/Path.h"
#include "soh/resource/type/AudioSequence.h"
#include "soh/resource/type/AudioSoundFont.h"
#include "soh/resource/type/scenecommand/SetMesh.h"
#include "soh/resource/type/scenecommand/SetActorList.h"
#include "soh/resource/type/scenecommand/SetTransitionActorList.h"
#include "soh/resource/type/scenecommand/SetLightList.h"
#include "soh/resource/type/scenecommand/SetLightingSettings.h"
#include "soh/resource/type/scenecommand/RomFile.h"
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
typedef char skeleton_abi[(sizeof(SOH::SkeletonHeader)==8 && sizeof(SOH::FlexSkeletonHeader)==12 && sizeof(SOH::SkelCurveLimbList)==8 && sizeof(SOH::SkeletonData)==12)?1:-1];
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
typedef char scene_command_id[(sizeof(SOH::SceneCommandID)==1 && SOH::SceneCommandID::Error==255) ? 1 : -1];
typedef char actor_layout[(sizeof(SOH::ActorEntry)==16 && sizeof(SOH::TransitionActorEntry)==16) ? 1 : -1];
typedef char light_layout[(sizeof(SOH::LightInfo)==14 && sizeof(SOH::EnvLightSettings)==22) ? 1 : -1];
typedef char mesh_layout[(sizeof(SOH::BgImage)==28 && sizeof(SOH::MeshHeader)==32 && sizeof(SOH::PolygonDlist2)==16) ? 1 : -1];
typedef char room_file_layout[(sizeof(SOH::RomFile)==12 && offsetof(SOH::RomFile,fileName)==8) ? 1 : -1];
