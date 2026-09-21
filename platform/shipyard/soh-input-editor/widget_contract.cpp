#include <cassert>
#include <iostream>
#include <cstring>
#ifdef SHIPYARD_EDITOR_PROJECTED
#define VGET xbox_compat::get
#else
#define VGET std::get
#endif
int main() {
    for (unsigned i = 0; i < sizeof(editorWidgetNames)/sizeof(editorWidgetNames[0]); ++i) {
#ifdef SHIPYARD_EDITOR_PROJECTED
        WidgetInfo info = Shipyard::SohInputEditor::Checkbox(editorWidgetNames[i]);
#else
        WidgetInfo info{.name=editorWidgetNames[i],.type=WIDGET_CVAR_CHECKBOX};
#endif
        assert(info.name == editorWidgetNames[i] && info.type == WIDGET_CVAR_CHECKBOX);
        assert(info.cVar == nullptr && !info.options && VGET<bool*>(info.valuePointer) == nullptr);
        assert(!info.callback && !info.preFunc && !info.postFunc && !info.customFunction);
        assert(info.activeDisables.empty() && std::strcmp(info.windowName, "") == 0);
        assert(!info.isHidden && !info.sameLine && info.raceDisable && !info.hideInSearch);
        for (int disabled=0; disabled<=1; ++disabled) {
#ifdef SHIPYARD_EDITOR_PROJECTED
            UIWidgets::CheckboxOptions options = Shipyard::SohInputEditor::DisabledCheckbox(disabled != 0, "reason");
#else
            UIWidgets::CheckboxOptions options({{.disabled=disabled != 0,.disabledTooltip="reason"}});
#endif
            assert(options.disabled == (disabled != 0)); assert(std::strcmp(options.disabledTooltip,"reason") == 0);
            assert(std::strcmp(options.tooltip, "") == 0 && !options.defaultValue);
            assert(options.color == UIWidgets::Colors::LightBlue);
            info.Options(options);
            UIWidgets::CheckboxOptions* owned=static_cast<UIWidgets::CheckboxOptions*>(info.options.get());
            assert(owned != &options && owned->disabled == options.disabled);
            std::cout << info.name << ':' << owned->disabled << ':' << owned->defaultValue << ':' << owned->color << '\n';
        }
#ifdef SHIPYARD_EDITOR_PROJECTED
        SearchWidget search(info,"Settings","Controls","Camera Controls");
#else
        SearchWidget search{info,"Settings","Controls","Camera Controls"};
#endif
        assert(&search.info == &info && search.extraTerms.empty());
    }
}
