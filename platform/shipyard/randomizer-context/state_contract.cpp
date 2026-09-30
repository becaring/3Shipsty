namespace Rando {
struct LocationContract {
    static void Run() {
        for (int rc = 0; rc < RC_MAX; ++rc) {
            ItemLocation loc(static_cast<RandomizerCheck>(rc));
            assert(loc.rc == rc && loc.price == 0 && loc.parentRegion == RR_NONE);
            assert(!loc.addedToPool && !loc.hidden && !loc.hasCustomPrice && !loc.isAvailable);
            assert(loc.placedItem == RG_NONE && loc.delayedItem == RG_NONE && loc.status == RCSHOW_UNCHECKED);
            loc.AddToPool();
            loc.SetAsHintable();
            loc.SetHintAccesible();
            loc.SetAvailable(true);
            loc.SetVisible(true);
            loc.SetWothCandidate();
            loc.SetBarrenCandidate();
            assert(loc.IsAddedToPool() && loc.IsHintable() && loc.IsAHintAccessible() && loc.IsAvailable());
            loc.SetHidden(true);
            assert(!loc.IsHintable());
            loc.SetDelayedItem(RG_ICE_TRAP);
            loc.SaveDelayedItem();
            assert(loc.RefPlacedItem() == RG_ICE_TRAP && loc.delayedItem == RG_NONE);
            for (unsigned price = 0; price < 65536; price += 257) {
                loc.SetPrice((uint16_t)price);
                assert(loc.price == price);
            }
            loc.SetCustomPrice(500);
            loc.SetPrice(700);
            assert(loc.price == 500 && loc.HasCustomPrice());
            std::set<RandomizerArea> areas;
            areas.insert(RA_NONE);
            loc.MergeAreas(areas);
            assert(loc.GetFirstArea() == RA_NONE);
            areas.insert(RA_KOKIRI_FOREST);
            loc.MergeAreas(areas);
            assert(loc.areas.size() == 1 && !loc.areas.count(RA_NONE));
            loc.AddHintedBy(static_cast<RandomizerHint>(0));
            assert(loc.GetHintedBy().size() == 1);
            loc.SetExcludedOption(RO_LOCATION_EXCLUDE);
            assert(loc.IsExcluded());
            loc.ResetVariables();
            assert(!loc.IsAvailable() && loc.GetHintedBy().empty() && loc.GetAreas().empty());
            assert(loc.IsVisible() && loc.IsExcluded()); // Original reset intentionally retains these.
            assert(loc.GetPlacedRandomizerGet() == RG_NONE && !loc.HasObtained() && !loc.GetIsSkipped());
        }
        printf("Location state/reset/area/price parity: %d locations\n", RC_MAX);
    }
};
struct FishContract {
    static void Run() {
        Fishsanity first, second;
        for (size_t i = 0; i < StaticData::randomizerFishingPondFish.size(); ++i) {
            const auto p = StaticData::randomizerFishingPondFish[i];
            assert(Fishsanity::childPondFish[i] == p.first && Fishsanity::adultPondFish[i] == p.second);
            printf("Fish %u %u %u\n", (unsigned)i, (unsigned)p.first, (unsigned)p.second);
        }
        for (int key = -128; key <= 127; ++key) {
            auto it = StaticData::randomizerGrottoFishMap.find((int8_t)key);
            if (it != StaticData::randomizerGrottoFishMap.end())
                printf("Grotto %d %u\n", key, (unsigned)it->second);
        }
        printf("Helper construction %u %u %u\n", (unsigned)Fishsanity::childPondFish.size(),
               (unsigned)Fishsanity::adultPondFish.size(), (unsigned)Fishsanity::pondFishAgeMap.size());
    }
};
}
int main() {
    Rando::LocationContract::Run();
    Rando::FishContract::Run();
    ItemTableManager tables;
    GetItemEntry none = GET_ITEM_NONE;
    assert(!tables.AddItemEntry(1, 1, none) && !tables.ClearItemTable(1));
    assert(tables.RetrieveItemEntry(1, 1).itemId == ITEM_NONE);
    assert(tables.AddItemTable(1) && !tables.AddItemTable(1));
    for (unsigned id = 0; id < 65536; ++id) {
        GetItemEntry entry = GET_ITEM_NONE;
        entry.itemId = (uint16_t)id;
        entry.modIndex = (uint16_t)(id ^ 0x5a5a);
        entry.drawItemId = 7;
        entry.drawModIndex = 9;
        assert(tables.AddItemEntry(1, (uint16_t)id, entry));
        assert(!tables.AddItemEntry(1, (uint16_t)id, none));
        GetItemEntry got = tables.RetrieveItemEntry(1, (uint16_t)id);
        assert(got.itemId == id && got.drawItemId == entry.itemId && got.drawModIndex == entry.modIndex);
    }
    assert(tables.ClearItemTable(1));
    assert(tables.RetrieveItemEntry(1, 4).itemId == ITEM_NONE);
    puts("65536 item IDs: first insertion, draw metadata, missing-table and clear parity");
}
