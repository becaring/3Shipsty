#include <fast/lus_gbi.h>
#include <ship/utils/binarytools/endianness.h>
#include "soh/resource/type/Array.h"
#include "soh/resource/type/Text.h"
#include "soh/resource/type/Cutscene.h"
#include "soh/resource/type/SohResourceType.h"
#include <cstddef>
#ifndef _XBOX
#error This ABI contract must use the actual Xenon compiler.
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
