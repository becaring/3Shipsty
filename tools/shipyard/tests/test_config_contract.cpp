#include "ship/config/Config.h"
#include <spdlog/spdlog.h>
#include <spdlog/sinks/sink.h>
#include <cassert>
#include <fstream>
#include <iostream>
#include <atomic>
#include <cstdlib>
#include <new>

class ConfigFailureSink : public spdlog::sinks::sink {
  public:
    std::string text;
    void log(const spdlog::details::log_msg &message) override {
        text.append(message.payload.data(), message.payload.size());
    }
    void flush() override {}
    void set_pattern(const std::string &) override {}
    void set_formatter(std::unique_ptr<spdlog::formatter>) override {}
};

static std::atomic<size_t> allocationCount(0);
void *operator new(size_t bytes) {
    allocationCount.fetch_add(1, std::memory_order_relaxed);
    if (void *result = std::malloc(bytes))
        return result;
    throw std::bad_alloc();
}
void operator delete(void *pointer) noexcept { std::free(pointer); }
void operator delete(void *pointer, size_t) noexcept { std::free(pointer); }

class Upgrade : public Ship::ConfigVersionUpdater {
  public:
    Upgrade(uint32_t version) : ConfigVersionUpdater(version) {}
    void Update(Ship::Config *config) { config->SetUInt("Migration.Last", GetVersion()); }
};
int main(int argc, char **argv) {
    assert(argc == 2);
    spdlog::set_level(spdlog::level::off);
    const std::string path = argv[1];
    {
        std::ofstream file(path);
        file << "{\"Features\":{\"Enabled\":true,\"Value\":17},\"ConfigVersion\":0}";
    }
    Ship::Config config(path);
    assert(config.GetBool("Features.Enabled") && config.GetUInt("Features.Value") == 17);
    assert(config.GetFloat("Features.Value", 3.5f) == 3.5f);
    config.SetFloat("Features.Gain", 0.125f);
    config.SetInt("Features.Signed", -7);
    config.SetString("Features.Name", "modern");
    config.SetBool("Features.Enabled", false);
    config.Copy("Features.Name", "Features.Copy");
    assert(config.GetString("Features.Copy") == "modern" && config.GetInt("Features.Signed") == -7);
    config.SetBlock("Features.Group", nlohmann::json::parse("{\"Items\":[1,2,3],\"Name\":\"nested\"}"));
    assert(config.GetString("Features.Group.Name") == "nested");
    config.Erase("Features.Copy");
    assert(config.GetString("Features.Copy", "missing") == "missing");
    config.EraseBlock("Features.Group");
    assert(!config.GetNestedJson()["Features"].contains("Group"));
    // Current Nested skips an absent path component, so the parent's Name is
    // still returned here. Preserve the actual upstream behavior in the port.
    assert(config.GetString("Features.Group.Name", "missing") == "modern");
    assert(config.RegisterVersionUpdater(std::make_shared<Upgrade>(3)));
    assert(config.RegisterVersionUpdater(std::make_shared<Upgrade>(1)));
    assert(!config.RegisterVersionUpdater(std::make_shared<Upgrade>(3)));
    config.RunVersionUpdates();
    assert(config.GetUInt("ConfigVersion") == 3 && config.GetUInt("Migration.Last") == 3);
    config.SetCurrentAudioBackend(Ship::AudioBackend::NUL);
    assert(config.GetCurrentAudioBackend() == Ship::AudioBackend::NUL &&
           config.GetString("Window.AudioBackend") == "null");
    config.Save();
    config.Reload();
    assert(config.GetFloat("Features.Gain") == 0.125f && !config.GetBool("Features.Enabled", true));
    std::cout << config.GetNestedJson().dump() << '\n';
    {
        std::ofstream file(path);
        file << "{broken";
    }
    config.Reload();
    assert(config.GetString("Features.Name", "empty") == "empty");
    config.Save();
    config.Reload();
    std::cout << config.GetNestedJson().dump() << '\n';
#ifdef SHIPYARD_PROJECTED_CONFIG_TEST
    // New configurations must accept a preset before any CVars exist.
    config.SetBlock("CVars.gEnhancements", nlohmann::json::parse("{\"InterpolationFPS\":60}"));
    Ship::Config restarted(path);
    assert(restarted.GetInt("CVars.gEnhancements.InterpolationFPS", 20) == 60);
    restarted.SetInt("CVars.gEnhancements.InterpolationFPS", 40);
    restarted.Save();
    config.Reload();
    assert(config.GetInt("CVars.gEnhancements.InterpolationFPS", 20) == 40);
    // The service writer reports failed writes through the logger. Reload
    // waits for completion, so the error must be visible before it returns.
    Ship::Config unwritable(path + "/missing/settings.json");
    unwritable.SetInt("Value", 1);
    auto priorLogger = spdlog::default_logger();
    auto failureSink = std::make_shared<ConfigFailureSink>();
    auto failureLogger = std::make_shared<spdlog::logger>("config-write-test", failureSink);
    failureLogger->set_level(spdlog::level::err);
    spdlog::set_default_logger(failureLogger);
    unwritable.Save();
    unwritable.Reload();
    spdlog::set_default_logger(priorLogger);
    assert(failureSink->text.find("Config save failed") != std::string::npos);
    assert(!std::ifstream(path + "/missing/settings.json"));
    config.SetString("Window.AudioBackend", "wasapi");
    assert(config.GetCurrentAudioBackend() == Ship::AudioBackend::XAUDIO2);
    config.SetCurrentAudioBackend(Ship::AudioBackend::XAUDIO2);
    assert(config.GetString("Window.AudioBackend") == "xaudio2");
    config.SetWindowBackend(Ship::WindowBackend::FAST3D_XENOS);
    assert(config.GetInt("Window.Backend.Id") == 3 && config.GetString("Window.Backend.Name") == "Xenos");
#endif
    {
        std::ofstream file(path);
        file << "{\"Escaped/"
                "Key\":{\"Value\":9},\"T~Key\":{\"Value\":10},\"Numeric\":{\"123\":11},\"Wild\":{\"*\":\"literal\"},"
                "\"Array\":[1,2,3]}";
    }
    config.Reload();
    assert(config.Contains("Escaped/Key") && config.Contains("Numeric"));
    assert(config.GetInt("Escaped/Key.Value", -1) == 9);
    assert(config.GetInt("T~Key.Value", -1) == 10);
    assert(config.GetInt("Numeric.123", -1) == 11);
    assert(config.GetString("Wild.*", "missing") == "literal");
    assert(config.GetInt("Array.0", -1) == -1);
    assert(config.GetInt("Missing.Numeric.123", -1) == 11);
    config.SetString("Bad~escape", "bad");
    bool unflattenRejected = false;
    try {
        config.GetInt("Numeric.123", -1);
    } catch (const std::exception &) {
        unflattenRejected = true;
    }
    assert(unflattenRejected);
    config.Reload();
    nlohmann::json bulk = nlohmann::json::object();
    for (int i = 0; i < 128; ++i)
        bulk["K" + std::to_string(i)] = i;
    config.SetBlock("Bulk", bulk);
    assert(config.GetInt("Bulk.K42", -1) == 42);
    config.SetInt("Bulk.K42", 42);
    config.Reload();
    allocationCount.store(0, std::memory_order_relaxed);
    volatile int lookupSum = 0;
    for (int i = 0; i < 100; ++i)
        lookupSum += config.GetInt("Bulk.K42", -1);
    assert(lookupSum == 4200);
    std::cerr << "config_lookup_allocations=" << allocationCount.load(std::memory_order_relaxed) << '\n';
    config.SetInt("Bulk.K129", 129);
    assert(config.GetInt("Bulk.K129", -1) == 129);
    allocationCount.store(0, std::memory_order_relaxed);
    config.Save();
    std::cerr << "config_save_allocations=" << allocationCount.load(std::memory_order_relaxed) << '\n';
    // Separate read-allocation measurements from the asynchronous writer.
    config.Reload();
    allocationCount.store(0, std::memory_order_relaxed);
    for (int i = 0; i < 100; ++i)
        lookupSum += config.GetInt("Bulk.K129", -1);
    assert(lookupSum == 17100);
    std::cerr << "config_lookup_after_save_allocations=" << allocationCount.load(std::memory_order_relaxed) << '\n';
}
