struct SaveSerializationAccess {
    static void Use(SaveManager &manager, nlohmann::json &value) { manager.currentJsonContext = &value; }
};
int main() {
    SaveManager manager((SaveSerializationFixtureTag()));
    nlohmann::json data = nlohmann::json::parse("{\"names\":[{\"english\":\"Kokiri\"},{},{\"english\":\"\"}],\"hints\":"
                                                "[{\"message\":\"forest\"},null,7,[true,false]]}");
    SaveSerializationAccess::Use(manager, data);
    manager.LoadArray("names", 5, [&](size_t i) {
        manager.LoadStruct("", [&]() {
            std::string value = "prior";
            manager.LoadData("english", value);
            assert(value == (i == 0 ? "Kokiri" : ""));
            std::cout << "name " << i << ' ' << value << '\n';
        });
    });
    manager.LoadArray("hints", 6, [&](size_t i) {
        nlohmann::json value = true;
        manager.LoadData("", value);
        if (i >= 4)
            assert(value.is_null());
        std::cout << "hint " << i << ' ' << value.dump() << '\n';
    });
    data = nlohmann::json::parse("{\"english\":42}");
    SaveSerializationAccess::Use(manager, data);
    bool threw = false;
    std::string value = "keep";
    try {
        manager.LoadData("english", value);
    } catch (const nlohmann::json::type_error &) {
        threw = true;
    }
    assert(threw && value == "keep");
    unsigned count = 0;
    data = nlohmann::json::object();
    SaveSerializationAccess::Use(manager, data);
    for (int i = 0; i <= int(RG_MAX); ++i) {
        RandomizerGet e = RandomizerGet(i);
        manager.SaveData("enum", e);
        RandomizerGet loaded;
        manager.LoadData("enum", loaded);
        assert(loaded == e);
        ++count;
    }
    for (int i = 0; i <= int(RHT_MAX); ++i) {
        RandomizerHintTextKey e = RandomizerHintTextKey(i);
        manager.SaveData("enum", e);
        RandomizerHintTextKey loaded;
        manager.LoadData("enum", loaded);
        assert(loaded == e);
        ++count;
    }
    std::cout << count << " actual enum values round trip; named/implicit nontrivial defaults and type errors agree\n";
}
