#pragma once
#include "soh/SohGui/MenuTypes.h"
namespace Shipyard { namespace ApplicationEditors {
inline WidgetInfo Widget(const std::string& name, WidgetType type) {
    WidgetInfo value((Shipyard::SohUI::ValueInit()));
    value.name=name; value.type=type; return value;
}
}}
