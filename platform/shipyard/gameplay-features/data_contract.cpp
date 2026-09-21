#include <cmath>
#include <limits>
#ifdef SHIPYARD_FEATURE_PROJECTED
#include "gameplay-features/support.h"
#define FEATURE_FMAX Shipyard::GameplayFeatures::Fmax
#else
#define FEATURE_FMAX std::fmax
#endif
int main(){
    for(int i=-1024;i<=1024;++i){double v=i/8.0;assert(FEATURE_FMAX(v,1.0)==std::fmax(v,1.0));}
    assert(FEATURE_FMAX(std::numeric_limits<double>::quiet_NaN(),1.0)==1.0);
    assert(FEATURE_FMAX(1.0,std::numeric_limits<double>::quiet_NaN())==1.0);
    assert(FEATURE_FMAX(-std::numeric_limits<double>::infinity(),1.0)==1.0);
    assert(FEATURE_FMAX(std::numeric_limits<double>::infinity(),1.0)==std::numeric_limits<double>::infinity());
    for(int i=-32768;i<=32767;++i)std::cout<<IsFixedCameraType(static_cast<s16>(i));
    std::cout<<'\n';
    for(int i=-1;i<1024;++i)std::cout<<fogControlList.count(static_cast<SceneID>(i))<<skyboxSceneControlList.count(static_cast<SceneID>(i))<<skyboxIdControlList.count(static_cast<SkyboxId>(i))<<fixedCameraSceneList.count(static_cast<SceneID>(i));
    std::cout<<'\n';
    for(const auto& e:randomizedEnemySpawnTable)std::cout<<e.cvar<<':'<<e.name<<':'<<e.id<<':'<<e.params<<'\n';
    for(int e:enemiesToRandomize)std::cout<<e<<',';
    std::cout<<'\n';
    for(const auto& p:graveyardGeometryPatches)std::cout<<p.first.first<<':'<<p.first.second<<':'<<p.second.first<<':'<<p.second.second<<'\n';
    auto days=MakedayTimeGoldSkulltulas();assert(days.size()==7);size_t count=0;
    for(const auto& d:days){std::cout<<d.scene<<':'<<d.room<<':'<<d.forChild<<'\n';for(const ActorEntry& e:d.actorEntries){++count;std::cout<<e.id<<':'<<e.pos.x<<':'<<e.pos.y<<':'<<e.pos.z<<':'<<e.rot.x<<':'<<e.rot.y<<':'<<e.rot.z<<':'<<e.params<<'\n';}}
    assert(count==12);std::cout<<"Camera, enemy, geometry, and daytime actor data match.\n";
}
