void Write(const std::string &v) { std::cout << v; }
template <class T> void Write(const T &v) { std::cout << v; }
template <class T> void Write(const std::vector<T> &v) {
    std::cout << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        Write(v[i]);
        std::cout << ",";
    }
    std::cout << "]";
}
void Write(const CustomMessage &v) { Write(v.GetAllMessages(MF_RAW)); }
void Write(const StaticHintInfo &v) {
    std::cout << v.type << ":";
    Write(v.hintKeys);
    std::cout << ":" << v.setting << ":" << v.condition.index() << ":";
    if (v.condition.index() == 0)
        std::cout << VARIANT_GET<bool>(v.condition);
    else
        std::cout << int(VARIANT_GET<uint8_t>(v.condition));
    Write(v.targetChecks);
    Write(v.targetItems);
    Write(v.hintChecks);
    std::cout << ":" << v.yourPocket << ":" << v.num;
}
template <class K, class V> void ShowMap(const char *name, const std::unordered_map<K, V> &values) {
    std::map<K, V> ordered(values.begin(), values.end());
    std::cout << name << ":" << values.size() << "\n";
    for (typename std::map<K, V>::const_iterator it = ordered.begin(); it != ordered.end(); ++it) {
        Write(it->first);
        std::cout << "=";
        Write(it->second);
        std::cout << "\n";
    }
}
template <class T> void ShowVector(const char *name, const std::vector<T> &v) {
    std::cout << name << ":";
    Write(v);
    std::cout << "\n";
}
void ShowLocation(const char *name, const Rando::Location &v) {
    Rando::SpoilerCollectionCheck c = v.GetCollectionCheck();
    std::cout << name << ":" << v.GetRandomizerCheck() << ":" << v.GetQuest() << ":" << v.GetRCType() << ":"
              << v.GetArea() << ":" << v.GetActorID() << ":" << v.GetScene() << ":" << v.GetActorParams() << ":"
              << v.GetHintKey() << ":" << v.GetVanillaItem() << ":" << v.GetVanillaPrice() << ":"
              << v.IsVanillaCompletion() << ":" << v.GetName() << ":" << v.GetShortName() << ":" << v.IsDungeon() << ":"
              << v.IsOverworld() << ":" << v.IsShop() << ":" << c.type << ":" << int(c.scene) << ":" << c.flag << ":"
              << v.checked << ":" << v.isHintable << "\n";
}
#define CHECK(x)                                                                                                       \
    do {                                                                                                               \
        if (!(x)) {                                                                                                    \
            fprintf(stderr, "line %d: %s\n", __LINE__, #x);                                                            \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)
int main() {
    spdlog::set_pattern("%v");
    SHIPYARD_DATA_FACTORIES
    SHIPYARD_DATA_TABLES
    Rando::Location empty;
    CHECK(empty.GetRandomizerCheck() == RC_UNKNOWN_CHECK && !empty.checked && !empty.isHintable);
    CHECK(empty.GetQuest() == RCQUEST_BOTH && empty.GetArea() == RCAREA_INVALID && empty.GetActorID() == ACTOR_ID_MAX);
    CHECK(empty.GetCollectionCheck().type == SPOILER_CHK_NONE);
    Rando::SpoilerCollectionCheck i = Rando::SpoilerCollectionCheck::ItemGetInf(9);
    CHECK(i.type == SPOILER_CHK_ITEM_GET_INF && i.scene == 0 && i.flag == 9);
    i = Rando::SpoilerCollectionCheck::EventChkInf(7);
    CHECK(i.type == SPOILER_CHK_EVENT_CHK_INF && i.scene == 255 && i.flag == 7);
    i = Rando::SpoilerCollectionCheck::InfTable(65535);
    CHECK(i.type == SPOILER_CHK_INF_TABLE && i.scene == 255 && i.flag == 65535);
    i = Rando::SpoilerCollectionCheck::Collectable(8, 3);
    CHECK(i.type == SPOILER_CHK_COLLECTABLE && i.scene == 8 && i.flag == 3);
    i = Rando::SpoilerCollectionCheck::Chest(8, 3);
    CHECK(i.type == SPOILER_CHK_CHEST && i.scene == 8 && i.flag == 3);
    i = Rando::SpoilerCollectionCheck::RandomizerInf(65535);
    CHECK(i.type == SPOILER_CHK_RANDOMIZER_INF && i.scene == 0 && i.flag == 65535);
    for (size_t k = 0; k < Rando::StaticData::hintTextTable.size(); ++k)
        CHECK(Rando::StaticData::hintTextTable[k].GetClear().GetEnglish(MF_RAW).empty());
    CHECK(Rando::Location::SpoilerNameFromShortName("Loose", RCAREA_INVALID) == "Loose");
    CHECK(Rando::Location::SpoilerNameFromShortName("Chest", RCAREA_KOKIRI_FOREST) == "KF Chest");
    std::unordered_map<std::string, uint32_t> translated =
        Rando::StaticData::PopulateTranslationMap(Rando::StaticData::hintTypeNames);
    CHECK(translated.size() >= Rando::StaticData::hintTypeNames.size());
    ShowMap("translated-types", translated);
    std::unordered_map<uint32_t, CustomMessage> collision;
    collision.emplace(11, CustomMessage("same"));
    collision.emplace(22, CustomMessage("same"));
    uint32_t first = collision.begin()->first;
    translated = Rando::StaticData::PopulateTranslationMap(collision);
    CHECK(translated.begin()->second == first);
    std::cout << "collision-first:" << first << "\n";
    // Fill actual table slots with real HintText values for the second overload.
    Rando::StaticData::hintTextTable[0] = HintText(CustomMessage("First"));
    Rando::StaticData::hintTextTable[1] = HintText(CustomMessage("Second"));
    std::unordered_map<uint32_t, RandomizerHintTextKey> keys;
    keys.emplace(5, RandomizerHintTextKey(0));
    keys.emplace(8, RandomizerHintTextKey(1));
    translated = Rando::StaticData::PopulateTranslationMap(keys);
    CHECK(translated.size() == 3 && translated["First"] == 5 && translated["Second"] == 8);
    ShowMap("translated-hints", translated);
    Rando::Location probe(RC_UNKNOWN_CHECK, RCQUEST_BOTH, RCTYPE_STANDARD, RCAREA_INVALID, ACTOR_EN_ITEM00,
                          SCENE_DEKU_TREE, 0, "short", RHT_NONE, RG_NONE);
    CHECK(probe.GetHint() == &Rando::StaticData::hintTextTable[RHT_NONE]);
    CHECK(probe.GetExcludedOption()->GetOptionCount() == 2);
    std::cout << "Location factories/defaults; static tables and both translation overloads passed\n";
    return 0;
}
