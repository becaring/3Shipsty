static uint64_t digest = 1469598103934665603ULL;
static void Mix(unsigned value) { digest = (digest ^ value) * 1099511628211ULL; }
static void Text(const std::string &s) {
    Mix(unsigned(s.size()));
    for (size_t i = 0; i < s.size(); ++i)
        Mix(static_cast<unsigned char>(s[i]));
}
static void CheckContainer(const std::vector<EventAccess> &v) {
    Mix(unsigned(v.size()));
    for (const auto &e : v) {
        Text(e.GetEventStr());
        Text(e.GetConditionStr());
    }
}
static void CheckContainer(const std::vector<LocationAccess> &v) {
    Mix(unsigned(v.size()));
    for (const auto &e : v) {
        Mix(e.GetLocation());
        Text(e.GetConditionStr());
    }
}
static void CheckContainer(const std::list<Rando::Entrance> &v) {
    Mix(unsigned(v.size()));
    for (const auto &e : v) {
        Mix(e.GetConnectedRegionKey());
        Mix(e.GetOriginalConnectedRegionKey());
        Text(e.GetConditionStr());
    }
}
static void CheckContainer(const std::set<RandomizerArea> &v) {
    Mix(unsigned(v.size()));
    for (const auto &e : v)
        Mix(e);
}
static bool TestAge() { return logic->IsChild && !logic->IsAdult; }
static bool TestTrue() { return true; }
static void Defaults(const Region &r) {
    assert(!r.childDay && !r.childNight && !r.adultDay && !r.adultNight && !r.addedToPool &&
           r.randomizerRegionKey == RR_NONE);
}
int main() {
    logic.reset(new Rando::Logic());
    unsigned evaluations = 0;
    for (unsigned pattern = 0; pattern < 64; ++pattern) {
        for (unsigned i = 0; i < LOGIC_MAX; ++i)
            logic->Set(LogicVal(i), pattern == 0   ? false
                                    : pattern == 1 ? true
                                                   : ((i * 2654435761u + pattern * 2246822519u) >> (pattern % 24)) & 1);
        for (unsigned mask = 0; mask < 16; ++mask) {
            logic->IsChild = !!(mask & 1);
            logic->IsAdult = !!(mask & 2);
            logic->AtDay = !!(mask & 4);
            logic->AtNight = !!(mask & 8);
            for (auto predicate : predicates) {
                Mix(predicate());
                ++evaluations;
            }
        }
    }
    /* CONTAINER_CALLS */
    Region empty;
    Defaults(empty);
    assert(empty.events.empty() && empty.locations.empty() && empty.exits.empty() && empty.entrances.empty());
    std::vector<EventAccess> events;
    events.push_back(EventAccess(LOGIC_FAIRY_ACCESS, "first", TestTrue, "true"));
    events.push_back(EventAccess(LOGIC_FAIRY_ACCESS, "second", TestAge, "age"));
    std::vector<LocationAccess> locations;
    locations.push_back(LocationAccess(RC_ALTAR_HINT_CHILD, TestAge));
    locations.push_back(LocationAccess(RC_ALTAR_HINT_ADULT, TestTrue, "true"));
    std::list<Rando::Entrance> exits;
    exits.push_back(Rando::Entrance(RR_TEMPLE_OF_TIME, TestTrue, "one"));
    exits.push_back(Rando::Entrance(RR_THE_MARKET, TestAge, "two", false));
    std::set<RandomizerArea> areas;
    areas.insert(RA_THE_MARKET);
    Region explicitRegion("explicit", SCENE_TEMPLE_OF_TIME, true, areas, events, locations, exits);
    Defaults(explicitRegion);
    assert(explicitRegion.timePass && explicitRegion.regionName == "explicit" &&
           explicitRegion.scene == SCENE_TEMPLE_OF_TIME && explicitRegion.areas == areas);
    CheckContainer(explicitRegion.events);
    CheckContainer(explicitRegion.locations);
    CheckContainer(explicitRegion.exits);
    assert(explicitRegion.events[0].GetEventStr() == "first" && explicitRegion.events[1].GetEventStr() == "second");
    auto first = &explicitRegion.exits.front();
    explicitRegion.exits.push_back(Rando::Entrance(RR_NONE, TestTrue, "third"));
    assert(first == &explicitRegion.exits.front());
    const SceneID scenes[] = {SCENE_DEKU_TREE,    SCENE_SPIRIT_TEMPLE, SCENE_TEMPLE_OF_TIME, SCENE_KOKIRI_FOREST,
                              SCENE_HYRULE_FIELD, SCENE_GROTTOS,       SCENE_ID_MAX};
    for (auto scene : scenes) {
        Region derived("derived", scene, events, locations, exits);
        Defaults(derived);
        assert(derived.areas == CalculateAreas(scene) && derived.TimePass() == GetTimePassFromScene(scene));
        CheckContainer(derived.areas);
        Mix(derived.TimePass());
    }
    for (unsigned access = 0; access < 16; ++access)
        for (unsigned prior = 0; prior < 4; ++prior) {
            explicitRegion.childDay = !!(access & 1);
            explicitRegion.childNight = !!(access & 2);
            explicitRegion.adultDay = !!(access & 4);
            explicitRegion.adultNight = !!(access & 8);
            logic->IsChild = !!(prior & 1);
            logic->IsAdult = !!(prior & 2);
            bool result = explicitRegion.AnyAgeTime(TestAge);
            assert(result == (!!(access & 3) && !(access & 12)));
            assert(logic->IsChild == !!(prior & 1) && logic->IsAdult == !!(prior & 2));
            Mix(result);
        }
    explicitRegion.ResetVariables();
    Defaults(explicitRegion);
    SpiritLogicData zero = {};
    assert(!zero.childKeys && !zero.childRevKeys && !zero.adultKeys && !zero.adultRevKeys && !zero.childAccess &&
           !zero.adultAccess && !zero.reverseAccess);
    printf("regions contract %llu; %u predicate evaluations; sizes %zu %zu %zu %zu\n",
           static_cast<unsigned long long>(digest), evaluations, sizeof(Region), sizeof(EventAccess),
           sizeof(LocationAccess), sizeof(SpiritLogicData));
}
