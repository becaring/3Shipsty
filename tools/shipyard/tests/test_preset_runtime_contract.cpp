// Source substitutions are supplied by test_preset_runtime.py, not copies of
// the production implementation. Only external services are modeled here.
#include <nlohmann/json.hpp>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include "soh/ShipInit.hpp"
using json = nlohmann::json;
#define CVAR_IMGUI_CONTROLLER_NAV "gSettings.ControlNav"
namespace Shipyard { namespace Resources {
template<class T> auto begin(T& value) { return value.begin(); }
template<class T> auto end(T& value) { return value.end(); }
} }
namespace StringHelper {
std::vector<std::string> Split(const std::string& s, const std::string& separator) {
    std::vector<std::string> parts; size_t pos=0, next;
    while ((next=s.find(separator,pos))!=std::string::npos) {
        parts.push_back(s.substr(pos,next-pos)); pos=next+separator.size();
    }
    parts.push_back(s.substr(pos)); return parts;
}
}
struct Color_RGBA8 { uint8_t r,g,b,a; };
struct Color_RGB8 { uint8_t r,g,b; };
namespace Ship {
struct Config {
    json mFlattenedJson, mNestedJson;
    std::string disk;
    void Save() { mNestedJson=mFlattenedJson.unflatten(); disk=mNestedJson.dump(); }
    void Reload() { mNestedJson=json::parse(disk); mFlattenedJson=mNestedJson.flatten(); }
    json GetNestedJson() { return mNestedJson; }
    void SetBlock(const std::string&,json);
    void EraseBlock(const std::string&);
};
struct ConsoleVariable {
    std::map<std::string,json> mVariables;
    void Load();
    void LoadFromPath(std::string,nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<json>>);
    void LoadLegacy() {}
    void RegisterInteger(const char* key,int value) { if(!mVariables.count(key))SetInteger(key,value); }
    void SetInteger(const char* key,int value) { mVariables[key]=value; }
    void SetFloat(const char* key,float value) { mVariables[key]=value; }
    void SetString(const char* key,const char* value) { mVariables[key]=value; }
    void SetColor(const char* key,Color_RGBA8 v) { mVariables[key]=json::array({v.r,v.g,v.b,v.a}); }
    void SetColor24(const char* key,Color_RGB8 v) { mVariables[key]=json::array({v.r,v.g,v.b}); }
};
struct Context {
    std::shared_ptr<Config> config=std::make_shared<Config>();
    ConsoleVariable cvars;
    static Context* GetInstance() { static Context instance; return &instance; }
    std::shared_ptr<Config> GetConfig() { return config; }
    ConsoleVariable* GetConsoleVariables() { return &cvars; }
};
@SET_BLOCK@
@ERASE_BLOCK@
@LOAD@
}
namespace ShipyardInputCompiler { bool Contains(const json& v,const std::string& key) { return v.contains(key); } }
namespace fmt { std::string format(const char*,const char* a,const std::string& b) { return std::string(a)+"."+b; } }
void CVarClearBlock(const char* key) {
    auto ctx=Ship::Context::GetInstance();ctx->config->EraseBlock(std::string("CVars.")+key);ctx->cvars.Load();
}
// The live-variable-to-config boundary; SetBlock/Load and preset logic above
// are production source. JSON pointers match the dotted CVar config contract.
void CVarSave() {
    auto ctx=Ship::Context::GetInstance();
    for(const auto& value:ctx->cvars.mVariables) {
        std::string path="/CVars/"+value.first;
        std::replace(path.begin(),path.end(),'.','/');
        ctx->config->mFlattenedJson[path]=value.second;
    }
    ctx->config->Save();
}
const char* CVarGetString(const char* key,const char* fallback) {
    auto& vars=Ship::Context::GetInstance()->cvars.mVariables;
    return vars.count(key)&&vars[key].is_string()?vars[key].get_ref<const std::string&>().c_str():fallback;
}
enum PresetSection { PRESET_SECTION_SETTINGS, PRESET_SECTION_ENHANCEMENTS, PRESET_SECTION_AUDIO,
    PRESET_SECTION_COSMETICS, PRESET_SECTION_RANDOMIZER, PRESET_SECTION_TRACKERS, PRESET_SECTION_NETWORK, PRESET_SECTION_MAX };
struct PresetInfo { json presetValues; bool apply[PRESET_SECTION_MAX]={true,true,true,true,true,true,true}; };
struct BlockInfo { std::string names[2]; };
BlockInfo blockInfo[] = {{{"Settings","settings"}},{{"Enhancements","enhancements"}},{{"Audio","audio"}},
    {{"Cosmetics","cosmetics"}},{{"Randomizer","rando"}},{{"Trackers","trackers"}},{{"Network","network"}}};
std::map<std::string,PresetInfo> presets;
void ItemTracker_LoadFromPreset(json) {}
namespace CheckTracker { void LoadFromPreset(json) {} }
namespace EntranceTracker { void LoadFromPreset(json) {} }
int randoUpdates=0, trickUpdates=0, locationUpdates=0, scales=0, hooks=0;
namespace Rando { struct Settings { static Settings* GetInstance(){ static Settings s;return &s; }
    void UpdateAllOptions(){ ++randoUpdates; } }; }
namespace SohGui { void UpdateMenuTricks(){ ++trickUpdates; } void UpdateMenuLocations(){ ++locationUpdates; } }
struct OTRGlobals { static OTRGlobals* Instance; void ScaleImGui(){ ++scales; } } globals;
OTRGlobals* OTRGlobals::Instance=&globals;
@APPLY@
void require(bool value,const char* reason) { if(!value)throw std::runtime_error(reason); }
void checkMenu() {
    const char* headerCvar="gSettings.Menu.ActiveHeader";
    @HEADER@
    struct Entry { std::vector<std::string> sidebarOrder; };
    std::map<std::string,Entry> menuEntries={{"Settings",{{"General","Presets"}}}};
    std::map<std::string,int> sidebarEntries={{"General",0},{"Presets",1}};
    auto sidebar=&sidebarEntries;
    const char* sidebarCvar="gSettings.Menu.SettingsSidebarSection";
    @SIDEBAR@
    require(headerIndex=="Settings" && sectionIndex=="Presets","preset moved menu away from Presets");
    require(Ship::Context::GetInstance()->cvars.mVariables["gSettings.ControlNav"]==1,"controller navigation lost");
}
int main(int argc,char** argv) { try {
    auto ctx=Ship::Context::GetInstance();
    json initial={{"Window",{{"AudioBackend","xaudio2"}}},{"CVars",{{"gSettings",{
        {"Menu",{{"ActiveHeader","Settings"},{"SettingsSidebarSection","General"}}}}},
        {"gEnhancements",{{"RemoveMe",1}}},{"gCheats",{{"GodMode",1}}}}}};
    ctx->config->mFlattenedJson=initial.flatten();ctx->config->Save();ctx->cvars.Load();
    ctx->cvars.SetString("gSettings.Menu.SettingsSidebarSection","Presets");
    ctx->cvars.SetInteger("gSettings.PendingSetting",42);
    RegisterShipInitFunc hook([](){++hooks;});
    std::ifstream presetFile(argv[1]);presetFile>>presets["builtin"].presetValues;
    for(int repeat=0;repeat<2;++repeat) {
        applyPreset("builtin",{});
        require(ctx->cvars.mVariables["gEnhancements.TextSpeed"]==5,"preset value missing after reload");
        require(!ctx->cvars.mVariables.count("gEnhancements.RemoveMe"),"overwrite left old enhancement");
        require(!ctx->cvars.mVariables.count("gCheats.GodMode"),"null block did not clear cheat");
        require(ctx->cvars.mVariables["gSettings.PendingSetting"]==42,"preset discarded pending unrelated CVar");
        checkMenu();
    }
    require(hooks==2 && scales==2,"preset omitted init or scale effects");
    auto persisted=ctx->config->disk;
    ctx->config=std::make_shared<Ship::Config>();ctx->config->disk=persisted;ctx->cvars.mVariables.clear();ctx->cvars.Load();
    require(ctx->cvars.mVariables["gEnhancements.TextSpeed"]==5,"preset lost on startup");checkMenu();
    require(ctx->config->mNestedJson["Window"]["AudioBackend"]=="xaudio2","unrelated config lost");
    presets["merge"].presetValues={{"blockStrategy",{{"enhancements","merge"}}},{"blocks",{{"enhancements",{
        {"gEnhancements",{{"TextSpeed",3}}},{"gCheats",{{"MoonJump",1}}}}}}}};
    applyPreset("merge",{});
    require(ctx->cvars.mVariables["gEnhancements.TextSpeed"]==3 && ctx->cvars.mVariables["gEnhancements.Autosave"]==1,"merge failed");
    presets["rando"].presetValues={{"blocks",{{"rando",{{"gRandoSettings",{{"LogicRules",1}}}}}}}};
    applyPreset("rando",{});
    require(randoUpdates==1 && trickUpdates==1 && locationUpdates==1,"rando callbacks missing");
    // No CVars root exists on a genuinely fresh config. SetBlock must create it.
    ctx->config->mFlattenedJson=json{{"Window",{{"AudioBackend","xaudio2"}}}}.flatten();ctx->config->Save();ctx->cvars.Load();
    applyPreset("builtin",{});
    require(ctx->cvars.mVariables["gEnhancements.TextSpeed"]==5,"preset ignored when CVars root absent");
    std::cout<<"preset runtime PASS\n";return 0;
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n';return 1; } }
