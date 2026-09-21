#pragma once
#include "application-windows/support.h"
#include "gameplay-features/support.h"
#include "filesystem/filesystem.h"
#include "gui/compat.h"
#include "ship/window/Window.h"
#include "ship/resource/ResourceManager.h"
#include "ship/resource/archive/ArchiveManager.h"
#include "soh/Enhancements/randomizer/static_data.h"
namespace Shipyard { namespace ApplicationExtras {
inline Ship::Coords Coords(int32_t x,int32_t y){ Ship::Coords result={x,y};return result; }
}}
#include "soh/Enhancements/randomizer/settings.h"
#include "soh/Enhancements/randomizer/randomizer_check_tracker.h"
#include "soh/ShipInit.hpp"
#include "application-editors/support.h"
