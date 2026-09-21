static uint64_t digest=1469598103934665603ULL;
static void Mix(uint64_t value){digest=(digest^value)*1099511628211ULL;}
static void Bytes(const std::string& value){Mix(value.size());for(unsigned char c:value)Mix(c);}
static bool TrueCondition(){return true;}
int main(){
    auto fullShop=GetMinVanillaShopItems(0);assert(fullShop.size()==64);
    for(int removed=0;removed<=64;++removed){auto items=GetMinVanillaShopItems(removed);assert(items.size()==64-removed);for(size_t i=0;i<items.size();++i){assert(items[i]==fullShop[i]);Mix(items[i]);}}
    unsigned distributions=0,prices=0;
    for(uint64_t seed=0;seed<128;++seed){
        Random_Init(seed*6364136223846793005ULL+1);
        for(unsigned i=0;i<128;++i){auto price=GetCheapBalancedPrice();assert(price<=95&&price%5==0);Mix(price);++prices;}
        for(unsigned mode=0;mode<8;++mode){
            std::vector<HintDistributionSetting> table;
            table.push_back(HintDistributionSetting("woth",HINT_TYPE_WOTH,mode&1?12:0,1,2,NoFilter,2));
            table.push_back(HintDistributionSetting("foolish",HINT_TYPE_FOOLISH,mode&2?7:0,0,1,NoFilter,1));
            table.push_back(HintDistributionSetting("empty",HINT_TYPE_ITEM,mode&4?20:0,0,0,NoFilter));
            for(unsigned stones=2;stones<=40;++stones){
                std::vector<uint8_t> selected(4,0);auto oldTable=table;
                DistributeHints(selected,stones,table,uint8_t(mode%3),true);
                unsigned consumed=selected[0]*2+selected[1]+selected[3];assert(consumed==stones);
                for(auto value:selected)Mix(value);
                for(size_t i=0;i<table.size();++i)assert(table[i].weight==oldTable[i].weight&&table[i].copies==oldTable[i].copies);
                ++distributions;
            }
        }
        for(unsigned i=0;i<32;++i){auto junk=GetRandomJunkHint();auto ganon=GetRandomGanonJoke();assert(junk>=RHT_JUNK01&&junk<RHT_JUNK71&&ganon>=RHT_GANON_JOKE01&&ganon<RHT_GANON_JOKE11);Mix(junk);Mix(ganon);}
        Mix(next32());
    }
    for(int maximum=0;maximum<=5;++maximum){itemPool.assign(6,RG_BOMBS_5);itemPool.insert(itemPool.begin()+2,RG_RED_RUPEE);ReplaceMaxItem(RG_BOMBS_5,maximum);assert(std::count(itemPool.begin(),itemPool.end(),RG_BOMBS_5)==maximum);for(auto value:itemPool)Mix(value);}
    StartingInventory.clear();AddItemToInventory(RG_KOKIRI_SWORD,2);AddItemToInventory(RG_BOMBS_5,0);AddItemToInventory(RG_RED_RUPEE,3);assert(StartingInventory.size()==5);for(auto value:StartingInventory)Mix(value);
    for(const std::string name:{"Buy Deku Nut (10)","Buy Red Potion [30] (1)","Buy Arrows","123"})Bytes(GetShopItemBaseName(name));
    Bytes(RemoveLineBreaks("a\nb\n\rc"));
    using namespace CustomMessages;
    std::string (*fixed[])()={MESSAGE_END,WAIT_FOR_INPUT,INSTANT_TEXT_ON,INSTANT_TEXT_OFF,SHOP_MESSAGE_BOX,EVENT_TRIGGER,PLAYER_NAME,PLAY_OCARINA,SKULLTULAS_DESTROYED,CURRENT_TIME,UNSKIPPABLE,TWO_WAY_CHOICE,NEWLINE,CENTER_TEXT,IF_NOT_MQ,MQ_ELSE,MQ_END};
    for(auto fn:fixed)Bytes(fn());assert(MESSAGE_END()==std::string("\x7f\0",2)&&SHOP_MESSAGE_BOX().size()==3);
    for(unsigned i=0;i<256;++i){Bytes(HORIZONTAL_SPACE(uint8_t(i)));Bytes(DELAY_FRAMES(uint8_t(i)));Bytes(CLOSE_AFTER(uint8_t(i)));Bytes(ITEM_OBTAINED(uint8_t(i)));Bytes(SET_SPEED(uint8_t(i)));assert(Shipyard::Generation::Decimal(uint8_t(i))==std::to_string(i));}
    for(unsigned i=0;i<65536;++i){auto s=GO_TO(uint16_t(i));assert(s.size()==4&&uint8_t(s[2])==i/256&&uint8_t(s[3])==i%256);Bytes(s);}
    Bytes(COLOR(std::string("A\0B",3)));
    for(int n:{0,1,100}){GetAccessibleLocationsStruct state(n);assert(state.regionPool.size()==1&&state.regionPool[0]==RR_ROOT&&state.gsCount==0&&state.maxGsCount==n&&!state.logicUpdated&&!state.resetSphere&&!state.calculatingAvailableChecks);Mix(state.maxGsCount);}
    std::vector<RandomizerHintTextKey> keys(2,RHT_WARP_SONG);std::vector<RandomizerCheck> checks(2,RC_ALTAR_HINT_CHILD);std::vector<RandomizerGet> items(1,RG_KOKIRI_SWORD);
    StaticHintInfo a(HINT_TYPE_ITEM,keys,RSK_HINT_CLARITY,true,checks,items,checks,true,7);
    StaticHintInfo b(HINT_TYPE_ITEM,keys,RSK_HINT_CLARITY,uint8_t(2),checks);
    assert(a.hintKeys==keys&&a.targetChecks==checks&&a.targetItems==items&&a.hintChecks==checks&&a.yourPocket&&a.num==7&&HINT_GET<bool>(a.condition));
    assert(HINT_GET<uint8_t>(b.condition)==2&&b.targetItems.empty()&&b.hintChecks.empty()&&!b.yourPocket&&!b.num);
    Rando::Entrance entry(RR_TEMPLE_OF_TIME,TrueCondition,"a"),reverse(RR_THE_MARKET,TrueCondition,"b");entry.BindTwoWay(&reverse);entry.SetType(Rando::EntranceType::Dungeon);reverse.SetType(Rando::EntranceType::DungeonReverse);
    for(int index:{-1,0,32767}){auto j=EntranceJSON(&entry,int16_t(index),-1,42,77);auto serialized=j.dump();Bytes(serialized);assert(j[0]["index"].get<int>()==index&&j[0]["override"].get<int>()==42&&j[1]["index"].get<int>()==77);assert(serialized.find("\"type\"")<serialized.find("\"index\""));}
    std::set<int> to={1,3},from={2,3};Shipyard::Generation::Merge(to,from);assert((to==std::set<int>{1,2,3})&&(from==std::set<int>{3}));
    std::vector<int> values={1,2,1,3,1};assert(Shipyard::Generation::Erase(values,1)==3&&(values==std::vector<int>{2,3}));
    assert(Shipyard::Generation::Decimal(UINT32_MAX)=="4294967295"&&Shipyard::Generation::Decimal(INT32_MIN)=="-2147483648");
    printf("generation contract %llu; %u hint distributions; %u seeded shop prices\n",static_cast<unsigned long long>(digest),distributions,prices);
}
