#include <cassert>
#include <cstring>
#include <iostream>
#include <new>
#include <type_traits>
#include <cmath>
#include <limits>
#ifdef SHIPYARD_UI_PROJECTED
#define VALUE(T) T(Shipyard::SohUI::ValueInit())
#define VGET xbox_compat::get
#define BAD_VARIANT xbox_compat::bad_variant_access
#else
#define VALUE(T) T()
#define VGET std::get
#define BAD_VARIANT std::bad_variant_access
#endif
static int initCalls=0;
static RegisterMenuInitFunc registration([](){++initCalls;});
int main(){
    using namespace UIWidgets;
    ColorPickerOptions color=VALUE(ColorPickerOptions);
    assert(!color.useAlpha&&!color.showReset&&!color.showRandom&&!color.showRainbow&&!color.showLock);
    assert(color.defaultValue.r==255&&color.defaultValue.g==255&&color.defaultValue.b==255&&color.defaultValue.a==255);
    assert(!color.disabled&&std::strcmp(color.tooltip,"")==0&&color.size.x==-1&&color.padding.y==8);
    // Inspect object representation without evaluating indeterminate bools.
    std::aligned_storage<sizeof(ColorPickerOptions),std::alignment_of<ColorPickerOptions>::value>::type storage;
    std::memset(&storage,0xa5,sizeof(storage));
    ColorPickerOptions* defaultColor=new(&storage)ColorPickerOptions;
    unsigned char untouched;std::memcpy(&untouched,&defaultColor->showReset,1);assert(untouched==0xa5);
    defaultColor->~ColorPickerOptions();
    WidgetInfo info=VALUE(WidgetInfo);
    assert(!info.cVar&&info.type==0&&VGET<bool*>(info.valuePointer)==NULL);
    assert(!info.callback&&!info.preFunc&&!info.postFunc&&!info.customFunction);
    assert(!info.isHidden&&!info.sameLine&&info.raceDisable&&!info.hideInSearch&&info.activeDisables.empty());
    info.type=WIDGET_CVAR_COLOR_PICKER;info.Options(color);
    ColorPickerOptions* stored=static_cast<ColorPickerOptions*>(info.options.get());
    assert(stored!=&color&&stored->defaultValue.r==255&&!stored->showReset);
    info.options->disabled=true;info.options->disabledTooltip="reason";info.isHidden=true;
    info.activeDisables.push_back(DISABLE_FOR_NULL_PLAY_STATE);info.ResetDisables();
    assert(!info.isHidden&&!info.options->disabled&&info.activeDisables.empty());
    assert(std::strcmp(info.options->disabledTooltip,"")==0);
    bool value=false;info.ValuePointer(&value);assert(VGET<bool*>(info.valuePointer)==&value);
    bool caught=false;try{VGET<int32_t*>(info.valuePointer);}catch(const BAD_VARIANT&){caught=true;}assert(caught);
    OptionsVariant options=VALUE(ButtonOptions);assert(options.index()==0);
    CheckboxOptions check=VALUE(CheckboxOptions);options=check;assert(options.index()==1);
    options=VALUE(ComboboxOptions);assert(options.index()==2);
    options=VALUE(FloatSliderOptions);assert(options.index()==3);
    options=VALUE(IntSliderOptions);assert(options.index()==4);
    options=VALUE(TextOptions);assert(options.index()==5);
    options=VALUE(WidgetOptions);assert(options.index()==6);
    options=VALUE(WindowButtonOptions);assert(options.index()==7);
    options=color;assert(options.index()==8);
    options=VALUE(BtnSelectorOptions);assert(options.index()==9);
    CVarVariant cvar=int32_t(42);assert(VGET<int32_t>(cvar)==42);
    cvar="text";assert(std::strcmp(VGET<const char*>(cvar),"text")==0);
    cvar=0.5f;assert(VGET<float>(cvar)==0.5f);
    const Color_RGBA8 rgba={1,2,3,4};cvar=rgba;assert(VGET<Color_RGBA8>(cvar).a==4);
    const Color_RGB8 rgb={5,6,7};cvar=rgb;assert(VGET<Color_RGB8>(cvar).b==7);
#ifdef SHIPYARD_UI_PROJECTED
    SearchWidget search(info,"menu","sidebar","location");
#else
    SearchWidget search{info,"menu","sidebar","location"};
#endif
    assert(&search.info==&info&&search.extraTerms.empty());search.info.isHidden=true;assert(info.isHidden);
    assert(initCalls==0);for(size_t i=0;i<MenuInit::GetInitFuncs().size();++i)MenuInit::GetInitFuncs()[i]();assert(initCalls==1);
    for(int c=0;c<65536;++c){ImGuiInputTextCallbackData data;data.EventChar=(ImWchar)c;
        std::cout<<TextFilters::FilterNumbers(&data)<<TextFilters::FilterAlphaNum(&data);}
    std::cout<<'\n';
    for(int i=Red;i<=NoColor;++i){ImVec4 v=ColorValues.at((Colors)i);std::cout<<i<<':'<<v.x<<','<<v.y<<','<<v.z<<','<<v.w<<'\n';}
    for(unsigned width=0;width<90;width+=3){std::string s="A long first line and words\nsecond line has some more words\n\nfinal";
        assert(WrappedText(s,width)==WrappedText(s.c_str(),width));std::cout<<width<<':'<<WrappedText(s,width)<<'\n';}
    uint32_t bits=17;uint64_t hash=1469598103934665603ULL;
    for(unsigned i=0;i<1048576;++i){bits=bits*1664525u+1013904223u;float v;std::memcpy(&v,&bits,4);
#ifdef SHIPYARD_UI_PROJECTED
        unsigned char channel=(unsigned char)Shipyard::SohUI::FMin(Shipyard::SohUI::FMax(v*255,0),255);
#else
        unsigned char channel=(unsigned char)fmin(fmax(v*255,0),255);
#endif
        hash=(hash^channel)*1099511628211ULL;
    }
    std::cout<<"Real menu option ownership, defaults, ten alternatives, callbacks, filters, colors and text agree "<<hash<<'\n';
}
