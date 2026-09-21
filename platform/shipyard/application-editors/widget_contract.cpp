#ifdef SHIPYARD_EDITOR_PROJECTED
#define VGET xbox_compat::get
#else
#define VGET std::get
#endif
template<class T> void BaseOptions(const T& o) {
    std::cout<<o.tooltip<<':'<<o.disabled<<':'<<o.disabledTooltip<<':'<<o.color<<':'<<o.alignment<<':'<<o.labelPosition<<'\n';
}
template<class T> void Slider(const T& o){BaseOptions(o);std::cout<<o.min<<':'<<o.max<<':'<<o.defaultValue<<':'<<o.step<<':'<<o.format<<':'<<o.showButtons<<':'<<o.clamp<<':'<<o.flags<<':'<<o.size.x<<':'<<o.size.y<<'\n';}
int main(){
    InitializeValues(UIWidgets::Colors::LightBlue);assert(sizeof(widgets)/sizeof(widgets[0])==11 && searches.size()==9);
    for(WidgetInfo* p:widgets){const WidgetInfo& w=*p;
        assert(w.cVar && w.options && !w.callback && !w.preFunc && !w.postFunc && !w.customFunction);
        assert(VGET<bool*>(w.valuePointer)==nullptr && w.activeDisables.empty() && !w.isHidden && !w.sameLine && w.raceDisable && !w.hideInSearch);
        std::cout<<w.name<<':'<<w.type<<':'<<w.cVar<<'\n';
        switch(w.type){
        case WIDGET_CVAR_CHECKBOX:{const auto& o=*static_cast<const CheckboxOptions*>(w.options.get());BaseOptions(o);assert(!o.defaultValue);std::cout<<o.padding.x<<':'<<o.padding.y<<'\n';break;}
        case WIDGET_CVAR_SLIDER_INT:Slider(*static_cast<const IntSliderOptions*>(w.options.get()));break;
        case WIDGET_CVAR_SLIDER_FLOAT:{const auto& o=*static_cast<const FloatSliderOptions*>(w.options.get());Slider(o);std::cout<<o.isPercentage<<'\n';break;}
        case WIDGET_CVAR_COMBOBOX:{const auto& o=*static_cast<const ComboboxOptions*>(w.options.get());BaseOptions(o);assert(o.defaultIndex==RANDOMIZE_OFF && o.comboMap.size()==5);for(auto& r:o.comboMap)std::cout<<r.first<<':'<<r.second<<'\n';break;}
        default:assert(false);
        }
    }
    for(auto& s:searches){assert(s.extraTerms.empty());std::cout<<s.info.name<<'\n';}
    // Actual shared ownership used by WidgetInfo must survive temporary options
    // and copies, including the combobox map's complete key/value contents.
    WidgetInfo copy=randomAudioGenModes;assert(copy.options==randomAudioGenModes.options);
    assert(static_cast<ComboboxOptions*>(copy.options.get())->comboMap.size()==5);
    std::cout<<"All 11 widget values and 9 search references match.\n";
}
