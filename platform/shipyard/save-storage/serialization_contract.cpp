#include <iostream>
#include <sstream>
#include <cstring>
#include <cassert>
SaveManager* SaveManager::Instance = nullptr;
extern "C" { SaveContext gSaveContext; }
struct SaveSerializationAccess {
    static void WorkerBarrier(SaveManager& manager) {
        manager.smThreadPool = std::make_shared<BS::thread_pool>(1);
        unsigned completed = 0;
        for (unsigned i = 0; i < 1024; ++i) {
            manager.smThreadPool->detach_task([&completed]() { ++completed; });
        }
        manager.ThreadPoolWait();
        assert(completed == 1024);
        // Destruction joins the same pool after the upstream barrier.
        manager.smThreadPool.reset();
    }
    static void Use(SaveManager& manager, nlohmann::json& value) { manager.currentJsonContext = &value; }
    static nlohmann::json Save(SaveManager& manager, SaveContext& value) {
        nlohmann::json output = nlohmann::json::object(); Use(manager, output);
        SaveManager::SaveBase(&value, SECTION_ID_BASE, true); return output;
    }
    static void Load(SaveManager& manager, int version, nlohmann::json& value) {
        Use(manager, value);
        switch (version) {
        case 1: SaveManager::LoadBaseVersion1(); break;
        case 2: SaveManager::LoadBaseVersion2(); break;
        case 3: SaveManager::LoadBaseVersion3(); break;
        case 4: SaveManager::LoadBaseVersion4(); break;
        }
    }
};
int main() { try {
    // Fixture constructor is injected only into the test's copy of the class.
    // It creates no game services and bypasses no production execution path.
    SaveManager manager(SaveSerializationFixtureTag());
    SaveManager::Instance = &manager;
    SaveContext source = {};
    for (int round = 0; round < 32; ++round) {
        source.entranceIndex = round * 7919;
        source.linkAge = round & 1;
        source.deaths = (uint16_t)(65535 - round);
        source.health = (int16_t)(round * 1027 - 32000);
        source.rupees = (int16_t)(round * 503 - 9000);
        source.inventory.questItems = 0xfedcba98u ^ (round * 17777u);
        source.inventory.upgrades = round * 97;
        source.horseData.pos.x = round * 0.125f - 7.5f;
        source.horseData.pos.y = round * -1.125f;
        source.horseData.pos.z = round * 8.0f;
        for (size_t i = 0; i < sizeof(source.playerName); ++i) source.playerName[i] = (u8)(round * 19 + i);
        for (size_t i = 0; i < 24; ++i) source.inventory.items[i] = (u8)(round * 7 + i);
        nlohmann::json saved = SaveSerializationAccess::Save(manager, source);
        std::cout << saved.dump() << '\n';
        for (int version = 1; version <= 4; ++version) {
            memset(&gSaveContext, 0, sizeof(gSaveContext));
            nlohmann::json input = version == 4 ? saved : nlohmann::json::object();
            if (version != 4) {
                input["entranceIndex"] = saved["entranceIndex"];
                input["health"] = saved["health"];
                input["playerName"] = saved["playerName"];
            }
            if (round & 1) input.erase("health");
            if (round & 2) input["playerName"] = nlohmann::json::array();
            SaveSerializationAccess::Load(manager, version, input);
            std::cout << SaveSerializationAccess::Save(manager, gSaveContext).dump() << '\n';
        }
    }
    nlohmann::json structure = nlohmann::json::object();
    SaveSerializationAccess::Use(manager, structure);
    manager.SaveArray("list", 3, [&](size_t i) {
        manager.SaveStruct("", [&]() { manager.SaveData("index", i); });
    });
    manager.LoadArray("list", 5, [&](size_t i) {
        manager.LoadStruct("", [&]() {
            size_t value = 999; manager.LoadData("index", value, size_t(77));
            assert(value == (i < 3 ? i : 77));
        });
    });
    std::cout << structure.dump() << '\n';
    SaveSerializationAccess::WorkerBarrier(manager);
    SaveManager::Instance = nullptr;
} catch(const std::exception& e) {std::cerr << e.what() << std::endl; return 2;}
}
