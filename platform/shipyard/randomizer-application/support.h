#pragma once
#include "input/compiler.h"
#include "resources/runtime_support.h"
#include "application-windows/support.h"
#include "application-editors/support.h"
#include "randomizer-content/support.h"
#include "filesystem/filesystem.h"
#include "soh/Enhancements/randomizer/settings.h"
#include "soh/cvar_prefixes.h"
#include "soh/util.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/randomizer/SeedContext.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/Enhancements/randomizer/item.h"
#include "soh/Enhancements/randomizer/item_location.h"
#include "soh/Enhancements/randomizer/randomizer.h"
#include "soh/Enhancements/randomizer/randomizer_check_tracker.h"
#include "soh/Enhancements/custom-message/CustomMessageManager.h"
#include "soh/Enhancements/custom-message/CustomMessageTypes.h"
#include "soh/SohGui/UIWidgets.hpp"
#include "soh/Notification/Notification.h"
#include "ship/window/gui/IconsFontAwesome4.h"
#include "ship/window/gui/Gui.h"
#include "ship/Context.h"
#include "ship/resource/ResourceManager.h"
#include "fast/Fast3dWindow.h"
#include "macros.h"
#include <spdlog/spdlog.h>
namespace Shipyard { namespace RandomizerApplication {
inline CheckIdentity Identity(RandomizerInf flag,RandomizerCheck check){CheckIdentity value={flag,check};return value;}
inline bool EndsWith(const std::string& value,const std::string& suffix){return value.size()>=suffix.size() && value.compare(value.size()-suffix.size(),suffix.size(),suffix)==0;}
template<class Sequence> class SequenceValues {
    Sequence sequence;
public:
    SequenceValues& Add(const typename Sequence::value_type& value){sequence.push_back(value);return *this;}
    Sequence Finish()const{return sequence;}
};
}}
