#pragma once
#include "save-storage/instance.h"
#include "save-storage/json_compare.h"
#include "soh/util.h"
#if defined(_XBOX)
namespace nlohmann { namespace detail {
template<> struct enum_underlying<FileType> { typedef int type; };
}}
#endif
