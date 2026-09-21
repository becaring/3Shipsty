#include "ship/config/Config.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <fstream>
#include <iostream>

class Upgrade : public Ship::ConfigVersionUpdater {
public:
    Upgrade(uint32_t version) : ConfigVersionUpdater(version) {}
    void Update(Ship::Config* config) { config->SetUInt("Migration.Last",GetVersion()); }
};
int main(int argc,char** argv) {
    assert(argc==2);spdlog::set_level(spdlog::level::off);
    const std::string path=argv[1];
    { std::ofstream file(path);file << "{\"Features\":{\"Enabled\":true,\"Value\":17},\"ConfigVersion\":0}"; }
    Ship::Config config(path);
    assert(config.GetBool("Features.Enabled") && config.GetUInt("Features.Value")==17);
    assert(config.GetFloat("Features.Value",3.5f)==3.5f);
    config.SetFloat("Features.Gain",0.125f);config.SetInt("Features.Signed",-7);
    config.SetString("Features.Name","modern");config.SetBool("Features.Enabled",false);
    config.Copy("Features.Name","Features.Copy");
    assert(config.GetString("Features.Copy")=="modern" && config.GetInt("Features.Signed")==-7);
    config.SetBlock("Features.Group",nlohmann::json::parse("{\"Items\":[1,2,3],\"Name\":\"nested\"}"));
    assert(config.GetString("Features.Group.Name")=="nested");
    config.Erase("Features.Copy");assert(config.GetString("Features.Copy","missing")=="missing");
    config.EraseBlock("Features.Group");assert(!config.GetNestedJson()["Features"].contains("Group"));
    // Current Nested skips an absent path component, so the parent's Name is
    // still returned here. Preserve the actual upstream behavior in the port.
    assert(config.GetString("Features.Group.Name","missing")=="modern");
    assert(config.RegisterVersionUpdater(std::make_shared<Upgrade>(3)));
    assert(config.RegisterVersionUpdater(std::make_shared<Upgrade>(1)));
    assert(!config.RegisterVersionUpdater(std::make_shared<Upgrade>(3)));
    config.RunVersionUpdates();assert(config.GetUInt("ConfigVersion")==3 && config.GetUInt("Migration.Last")==3);
    config.SetCurrentAudioBackend(Ship::AudioBackend::NUL);
    assert(config.GetCurrentAudioBackend()==Ship::AudioBackend::NUL && config.GetString("Window.AudioBackend")=="null");
    config.Save();config.Reload();
    assert(config.GetFloat("Features.Gain")==0.125f && !config.GetBool("Features.Enabled",true));
    std::cout << config.GetNestedJson().dump() << '\n';
    { std::ofstream file(path);file << "{broken"; }
    config.Reload();assert(config.GetString("Features.Name","empty")=="empty");
    config.Save();std::cout << config.GetNestedJson().dump() << '\n';
#ifdef SHIPYARD_PROJECTED_CONFIG_TEST
    config.SetString("Window.AudioBackend","wasapi");
    assert(config.GetCurrentAudioBackend()==Ship::AudioBackend::XAUDIO2);
    config.SetCurrentAudioBackend(Ship::AudioBackend::XAUDIO2);
    assert(config.GetString("Window.AudioBackend")=="xaudio2");
    config.SetWindowBackend(Ship::WindowBackend::FAST3D_XENOS);
    assert(config.GetInt("Window.Backend.Id")==3 && config.GetString("Window.Backend.Name")=="Xenos");
#endif
}
