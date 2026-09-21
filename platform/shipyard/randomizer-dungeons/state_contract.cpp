#include <cassert>
#include <cstdio>
#include <cstring>
#include <new>
#include <type_traits>
namespace Rando {
struct DungeonContract {
    template<class T> static void Untouched(const T& value) {
        const unsigned char* bytes=reinterpret_cast<const unsigned char*>(&value);
        for(size_t i=0;i<sizeof(value);++i)assert(bytes[i]==0xa5);
    }
    static int Run() {
        std::aligned_storage<sizeof(DungeonInfo),alignof(DungeonInfo)>::type dungeonBytes;
        memset(&dungeonBytes,0xa5,sizeof(dungeonBytes));auto* defaultDungeon=new(&dungeonBytes) DungeonInfo;
        assert(defaultDungeon->GetName().empty() && defaultDungeon->GetHintKey()==RHT_NONE && defaultDungeon->GetMap()==RG_NONE);
        assert(defaultDungeon->GetSmallKey()==RG_NONE && defaultDungeon->GetKeyRing()==RG_NONE && defaultDungeon->GetCompass()==RG_NONE && defaultDungeon->GetBossKey()==RG_NONE);
        assert(!defaultDungeon->IsMQ() && !defaultDungeon->HasKeyRing() && defaultDungeon->GetSmallKeyCount()==0);
        assert(defaultDungeon->isDungeonModeKnown);Untouched(defaultDungeon->area);Untouched(defaultDungeon->mqSetting);defaultDungeon->~DungeonInfo();
        std::aligned_storage<sizeof(TrialInfo),alignof(TrialInfo)>::type trialBytes;
        memset(&trialBytes,0xa5,sizeof(trialBytes));auto* defaultTrial=new(&trialBytes) TrialInfo;
        assert(defaultTrial->IsSkipped());Untouched(defaultTrial->nameKey);Untouched(defaultTrial->trialKey);defaultTrial->~TrialInfo();
        Dungeons dungeons;assert(dungeons.GetDungeonListSize()==12&&dungeons.CountMQ()==0);
        const unsigned scenes[]={SCENE_DEKU_TREE,SCENE_DODONGOS_CAVERN,SCENE_JABU_JABU,SCENE_FOREST_TEMPLE,SCENE_FIRE_TEMPLE,SCENE_WATER_TEMPLE,SCENE_SPIRIT_TEMPLE,SCENE_SHADOW_TEMPLE,SCENE_BOTTOM_OF_THE_WELL,SCENE_ICE_CAVERN,SCENE_GERUDO_TRAINING_GROUND,SCENE_INSIDE_GANONS_CASTLE};
        const unsigned vanilla[]={0,0,0,5,8,6,5,5,3,0,9,2};const unsigned mq[]={0,0,0,6,5,2,7,6,2,0,3,3};
        auto list=dungeons.GetDungeonList();
        for(unsigned i=0;i<12;++i) {
            auto* dungeon=dungeons.GetDungeon(DungeonKey(i));assert(dungeon==list[i]&&dungeon==dungeons.GetDungeonFromScene(scenes[i]));
            assert(dungeon->GetSmallKeyCount()==vanilla[i]);dungeon->SetMQ();assert(dungeon->GetSmallKeyCount()==mq[i]);dungeon->ClearMQ();
            dungeon->SetKeyRing();assert(dungeon->HasKeyRing());dungeon->ClearKeyRing();assert(!dungeon->HasKeyRing());
            dungeon->SetDungeonKnown(false);assert(!dungeon->isDungeonModeKnown);dungeon->SetDungeonKnown(true);
            dungeon->locations.push_back(RC_UNKNOWN_CHECK);auto copy=dungeon->GetDungeonLocations();copy.clear();assert(dungeon->locations.size()==1);dungeon->locations.clear();
            printf("D %u %s %u %u %u %u %u %u %u %u %u\n",i,dungeon->GetName().c_str(),dungeon->GetHintKey(),dungeon->GetArea(),dungeon->GetMap(),dungeon->GetCompass(),dungeon->GetSmallKey(),dungeon->GetKeyRing(),dungeon->GetBossKey(),dungeon->GetMQSetting(),mq[i]);
        }
        list[0]=nullptr;assert(dungeons.GetDungeonList()[0]!=nullptr);
        for(unsigned scene=0;scene<65536;++scene) {bool valid=false;for(unsigned expected:scenes)valid|=scene==expected;assert((dungeons.GetDungeonFromScene(uint16_t(scene))!=nullptr)==valid);}
        for(unsigned mask=0;mask<4096;++mask) {
            nlohmann::json root;root["masterQuestDungeons"]=nlohmann::json::array();unsigned count=0;
            for(unsigned i=0;i<12;++i)if((mask>>i)&1){root["masterQuestDungeons"].push_back(dungeons.GetDungeon(DungeonKey(i))->GetName());++count;}
            dungeons.ParseJson(root);assert(dungeons.CountMQ()==count);
            for(unsigned i=0;i<12;++i)assert(dungeons.GetDungeon(DungeonKey(i))->IsMQ()==bool((mask>>i)&1));
        }
        nlohmann::json invalid;invalid["masterQuestDungeons"]=nlohmann::json::array();invalid["masterQuestDungeons"].push_back("unknown");invalid["masterQuestDungeons"].push_back(42);invalid["masterQuestDungeons"].push_back(false);invalid["masterQuestDungeons"].push_back(nullptr);dungeons.ParseJson(invalid);assert(dungeons.CountMQ()==0);
        dungeons.ClearAllMQ();assert(dungeons.CountMQ()==0);
        Trials trials;assert(trials.GetTrialListSize()==TK_MAX);auto trialList=trials.GetTrialList();auto keys=trials.GetAllTrialHintHeys();assert(keys==StaticData::trialData);
        for(unsigned i=0;i<TK_MAX;++i) {auto* t=trials.GetTrial(TrialKey(i));assert(t==trialList[i]&&t->IsSkipped()&&!t->IsRequired()&&t->GetTrialKey()==i&&t->GetNameKey()==keys[i]);printf("T %u %u\n",i,t->GetNameKey());}
        for(unsigned mask=0;mask<(1u<<TK_MAX);++mask) {trials.SkipAll();for(unsigned i=0;i<TK_MAX;++i)if((mask>>i)&1)trials.GetTrial(TrialKey(i))->SetAsRequired();for(unsigned i=0;i<TK_MAX;++i)assert(trials.GetTrial(TrialKey(i))->IsRequired()==bool((mask>>i)&1));}
        trials.RequireAll();for(auto* t:trials.GetTrialList())assert(t->IsRequired());trials.SkipAll();for(auto* t:trials.GetTrialList())assert(t->IsSkipped());
        std::vector<int> input={5,2,5,8,3};auto evens=FilterFromPool(input,[](int v){return v%2==0;});assert(evens.size()==2&&evens[0]==2&&evens[1]==8&&input.size()==5);
        unsigned calls=0;auto odd=FilterFromPool(input,[&](int v){++calls;return v%2!=0;},true);assert(calls==10&&odd.size()==3&&odd[0]==5&&odd[1]==5&&odd[2]==3&&input.size()==2&&input[0]==2&&input[1]==8);
        printf("Dungeons/trials: 12 definitions, 65536 scene IDs, 4096 MQ JSON masks, 64 trial masks; pool order/erase and constructor defaults pass\n");return 0;
    }
};
}
int main(){return Rando::DungeonContract::Run();}
