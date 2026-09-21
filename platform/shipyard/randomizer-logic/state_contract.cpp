template<class K> static void PrintTable(const char* name,const std::map<K,uint32_t>& table) {
    printf("%s %zu",name,table.size());
    for(const auto& row:table) printf(" %u:%u",unsigned(row.first),row.second);
    printf("\n");
}
int main() {
    using namespace Rando;
    SaveContext save={};Logic logic;logic.SetSaveContext(&save);
    assert(!logic.Bottles&&!logic.NumBottles&&!logic.IsChild&&!logic.IsAdult&&!logic.CalculatingAvailableChecks);
    for(unsigned i=0;i<LOGIC_MAX;++i) { logic.Set(LogicVal(i),false);assert(!logic.Get(LogicVal(i)));logic.Set(LogicVal(i),true);assert(logic.Get(LogicVal(i)));logic.Set(LogicVal(i),false); }
    unsigned upgrades=0;
    for(unsigned i=0;i<sizeof(gUpgradeMasks)/sizeof(gUpgradeMasks[0]);++i) for(unsigned value=0;value<256;++value) {
        save.inventory.upgrades=0xaaaaaaaa;logic.SetUpgrade(i,uint8_t(value));
        uint32_t expected=(0xaaaaaaaa&gUpgradeNegMasks[i])|(value<<gUpgradeShifts[i]);
        assert(save.inventory.upgrades==expected && logic.CurrentUpgrade(i)==((expected&gUpgradeMasks[i])>>gUpgradeShifts[i]));++upgrades;
    }
    unsigned slots=sizeof(gItemSlots)/sizeof(gItemSlots[0]);
    for(unsigned i=0;i<slots;++i) {
        assert(logic.InventorySlot(i)==gItemSlots[i]);
        logic.SetInventory(i,i);assert(logic.CurrentInventory(i)==i&&logic.CheckInventory(i,true));
        logic.SetInventory(i,ITEM_NONE);assert(!logic.CheckInventory(i,false));
        if(gItemSlots[i]<sizeof(save.inventory.ammo)/sizeof(save.inventory.ammo[0])) {
            logic.SetAmmo(i,127);assert(logic.GetAmmo(i)==127);
        }
    }
    for(unsigned i=0;i<31;++i) { save.inventory.questItems=0;logic.SetQuestItem(i,true);assert(logic.CheckQuestItem(i));logic.SetQuestItem(i,false);assert(!logic.CheckQuestItem(i)); }
    for(unsigned i=0;i<16;++i) { save.inventory.equipment=uint16_t(1u<<i);assert(logic.CheckEquipment(1u<<i));assert(!logic.CheckEquipment((1u<<i)^0xffff)); }
    unsigned randoFlags=sizeof(save.ship.randomizerInf)/sizeof(save.ship.randomizerInf[0])*16;
    for(unsigned i=0;i<randoFlags;++i) { logic.SetRandoInf(i,true);assert(logic.CheckRandoInf(i));logic.SetRandoInf(i,false);assert(!logic.CheckRandoInf(i)); }
    unsigned eventFlags=sizeof(save.eventChkInf)/sizeof(save.eventChkInf[0])*16;
    for(unsigned i=0;i<eventFlags;++i) { logic.SetEventChkInf(i,true);assert(logic.CheckEventChkInf(i));logic.SetEventChkInf(i,false);assert(!logic.CheckEventChkInf(i)); }
    for(unsigned d=0;d<sizeof(save.inventory.dungeonItems);++d) for(unsigned i=0;i<3;++i) {
        logic.SetDungeonItem(i,d,true);assert(logic.CheckDungeonItem(i,d));logic.SetDungeonItem(i,d,false);assert(!logic.CheckDungeonItem(i,d));logic.SetSmallKeyCount(d,7);assert(save.inventory.dungeonKeys[d]==7);
    }
    const LogicVal clears[]={LOGIC_DEKU_TREE_CLEAR,LOGIC_DODONGOS_CAVERN_CLEAR,LOGIC_JABU_JABUS_BELLY_CLEAR,LOGIC_FOREST_TEMPLE_CLEAR,LOGIC_FIRE_TEMPLE_CLEAR,LOGIC_WATER_TEMPLE_CLEAR,LOGIC_SPIRIT_TEMPLE_CLEAR,LOGIC_SHADOW_TEMPLE_CLEAR};
    const unsigned events[]={EVENTCHKINF_USED_DEKU_TREE_BLUE_WARP,EVENTCHKINF_USED_DODONGOS_CAVERN_BLUE_WARP,EVENTCHKINF_USED_JABU_JABUS_BELLY_BLUE_WARP,EVENTCHKINF_USED_FOREST_TEMPLE_BLUE_WARP,EVENTCHKINF_USED_FIRE_TEMPLE_BLUE_WARP,EVENTCHKINF_USED_WATER_TEMPLE_BLUE_WARP};
    for(unsigned mask=0;mask<256;++mask) {
        unsigned count=0;for(unsigned i=0;i<8;++i) {bool bit=(mask>>i)&1;logic.Set(clears[i],bit);count+=bit;}
        logic.CalculatingAvailableChecks=false;assert(logic.DungeonCount()==count);
        for(unsigned i=0;i<6;++i)logic.SetEventChkInf(events[i],(mask>>i)&1);
        logic.SetRandoInf(RAND_INF_DUNGEONS_DONE_SPIRIT_TEMPLE,(mask>>6)&1);logic.SetRandoInf(RAND_INF_DUNGEONS_DONE_SHADOW_TEMPLE,(mask>>7)&1);
        logic.CalculatingAvailableChecks=true;assert(logic.DungeonCount()==count);
    }
    save.inventory.gsTokens=255;assert(logic.GetGSCount()==255);assert(logic.CanBreakCrates()&&logic.CanBonkTrees());
    PrintTable("equipment",Logic::RandoGetToEquipFlag);PrintTable("randinf",Logic::RandoGetToRandInf);PrintTable("dungeon",Logic::RandoGetToDungeonScene);PrintTable("quest",Logic::RandoGetToQuestItem);PrintTable("bottles",BottleRandomizerGetToItemID);
    printf("Logic: %u upgrades, %u inventory IDs, %u randomizer flags, %u event flags, 512 dungeon-count states; 5 original maps; all contracts pass\n",upgrades,slots,randoFlags,eventFlags);
}
