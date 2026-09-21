void Hex(const std::string& s){std::cout<<s.size()<<":";for(unsigned char c:s)printf("%02x",c);std::cout<<";";}
void Message(const CustomMessage& m){
    std::cout<<int(m.type)<<","<<int(m.position)<<":";
    for(const auto& s:m.messages)Hex(s);
    std::cout<<" colors:";for(const auto& s:m.colors)Hex(s);
    std::cout<<" capitals:";for(bool b:m.capital)std::cout<<b;
    std::cout<<"\n";
}
void Locations(const char* name,const std::vector<RandomizerCheck>& v){std::cout<<name<<":";for(auto x:v)std::cout<<x<<",";std::cout<<"\n";}
int main(){
    using Rando::StaticData;
    for(const auto& hint:StaticData::hintTextTable)if(!hint.clearText.messages[0].empty() || !hint.ambiguousText.empty() || !hint.obscureText.empty())return 1;
    StaticData::InitLocationTable();StaticData::InitHashMaps();
    std::cout<<"locations:"<<StaticData::GetLocationTable().size()<<"\n";
    for(const auto& v:StaticData::GetLocationTable()){
        auto c=v.GetCollectionCheck();
        std::cout<<v.GetRandomizerCheck()<<":"<<v.GetQuest()<<":"<<v.GetRCType()<<":"<<v.GetArea()<<":"<<v.GetActorID()<<":"<<v.GetScene()<<":"<<v.GetActorParams()<<":"<<v.GetHintKey()<<":"<<v.GetVanillaItem()<<":"<<v.GetVanillaPrice()<<":"<<v.IsVanillaCompletion()<<":"<<v.GetName()<<":"<<v.GetShortName()<<":"<<c.type<<":"<<int(c.scene)<<":"<<c.flag<<"\n";
    }
    for(const auto& p:StaticData::CheckFromActorMultimap)std::cout<<"actor:"<<std::get<0>(p.first)<<":"<<std::get<1>(p.first)<<":"<<std::get<2>(p.first)<<":"<<p.second<<"\n";
    std::map<std::string,RandomizerCheck> names(StaticData::locationNameToEnum.begin(),StaticData::locationNameToEnum.end());
    for(const auto& p:names)std::cout<<"name:"<<p.first<<":"<<p.second<<"\n";
    Locations("rewards",StaticData::dungeonRewardLocations);
    SHIPYARD_FILTER_CALLS
    for(const auto& p:RandomizerCheckObjects::GetAllRCObjectsByArea()){std::cout<<"area:"<<p.first<<":"<<RandomizerCheckObjects::GetRCAreaName(p.first)<<":"<<RandomizerCheckObjects::AreaIsDungeon(p.first)<<":"<<RandomizerCheckObjects::AreaIsOverworld(p.first)<<"\n";Locations("checks",p.second);}
    for(const auto& p:RandomizerCheckObjects::GetAllRCAreaBySceneID())std::cout<<"scene:"<<p.first<<":"<<p.second<<":"<<RandomizerCheckObjects::GetRCAreaBySceneID(p.first)<<"\n";
    if(RandomizerCheckObjects::GetRCAreaBySceneID(SceneID(-1))!=RCAREA_INVALID)return 2;
    StaticData::HintTable_Init();std::cout<<"hints:"<<StaticData::hintTextTable.size()<<"\n";
    for(size_t i=0;i<StaticData::hintTextTable.size();++i){const auto& h=StaticData::hintTextTable[i];std::cout<<"hint:"<<i<<":"<<h.ambiguousText.size()<<":"<<h.obscureText.size()<<"\n";Message(h.clearText);for(const auto& m:h.ambiguousText)Message(m);for(const auto& m:h.obscureText)Message(m);}
}
