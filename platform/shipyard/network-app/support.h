#pragma once
#include "input/compiler.h"
#include "resources/runtime_support.h"
#include "application-windows/support.h"
#include "network/support.h"
#include "soh/cvar_prefixes.h"
#include "soh/util.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/randomizer/SeedContext.h"
#include "soh/Enhancements/randomizer/item_location.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/Enhancements/randomizer/item.h"
#include "soh/Enhancements/randomizer/randomizer_check_tracker.h"
#include "fast/Fast3dWindow.h"
#include "macros.h"
#include "ship/window/gui/IconsFontAwesome4.h"
#include "ship/window/gui/ConsoleWindow.h"
#include <spdlog/spdlog.h>
template<class T> T ShipyardNetworkZero(){T result={};return result;}
template<class T,class U> std::shared_ptr<T> ShipyardNetworkReinterpret(const std::shared_ptr<U>& p){return std::shared_ptr<T>(p,reinterpret_cast<T*>(p.get()));}
template<class T> std::unique_ptr<T> ShipyardNetworkMakeUnique(){return std::unique_ptr<T>(new T());}
#if defined(_XBOX)
namespace nlohmann { namespace detail {
template<> struct enum_underlying<RandomizerCheck> {typedef int type;};
template<> struct enum_underlying<RandomizerCheckStatus> {typedef int type;};
}}
#endif
