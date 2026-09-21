#pragma once
#include "soh/SohGui/MenuTypes.h"
namespace Shipyard { namespace SohInputEditor {
inline WidgetInfo Checkbox(const std::string& name) {
    WidgetInfo value((Shipyard::SohUI::ValueInit()));
    value.name = name; value.type = WIDGET_CVAR_CHECKBOX; return value;
}
inline UIWidgets::CheckboxOptions DisabledCheckbox(bool disabled, const char* tooltip) {
    UIWidgets::CheckboxOptions value((Shipyard::SohUI::ValueInit()));
    value.disabled = disabled; value.disabledTooltip = tooltip; return value;
}
}}
