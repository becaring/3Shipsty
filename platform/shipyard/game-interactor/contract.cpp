#include "GameInteractor.h"
#include <cassert>
#include <cstdio>
#include <cstring>
HOOK_ID RegisterCrossTranslationUnit(GameInteractor*,int*);
int main(){
    GameInteractor gi;
    typedef GameInteractor::OnSceneInit H;
    int total=0;
    HOOK_ID first=gi.RegisterGameHook<H>([&total](int16_t n){total+=n;});
    assert(first==1 && gi.nextHookId==2);
    const HookRegisteringInfo& where=gi.GetHookData<H>()->at(first).registering;
    assert(where.valid&&where.line>0&&strstr(where.file,"contract.cpp")&&strstr(where.function,"main"));
    assert(where.type==HOOK_TYPE_NORMAL);
    gi.ExecuteHooks<H>(3);assert(total==3&&gi.GetHookData<H>()->at(first).calls==1);
    HOOK_ID second=gi.RegisterGameHook<H>([&gi,first,&total](int16_t n){total+=n*10;gi.UnregisterGameHook<H>(first);});
    gi.ExecuteHooks<H>(2);assert(total==25);
    gi.ExecuteHooks<H>(2);assert(total==45&&gi.GetHookData<H>()->count(first)==0);
    gi.UnregisterGameHook<H>(second);gi.ProcessUnregisteredHooks<H>();assert(gi.GetHookData<H>()->empty());
    HOOK_ID id=gi.RegisterGameHookForID<H>(17,[&total](int16_t n){total+=n;});
    gi.ExecuteHooksForID<H>(16,8);assert(total==45);
    gi.ExecuteHooksForID<H>(17,8);assert(total==53);
    gi.UnregisterGameHookForID<H>(id);
    gi.ExecuteHooksForID<H>(16,8);assert(gi.GetHookData<H>()->count(id)==1);
    gi.ExecuteHooksForID<H>(17,8);assert(total==53&&gi.GetHookData<H>()->count(id)==0);
    int object=0;uintptr_t key=(uintptr_t)&object;
    HOOK_ID ptr=gi.RegisterGameHookForPtr<H>(key,[&total](int16_t n){total+=n;});
    gi.ExecuteHooksForPtr<H>(key+1,4);assert(total==53);
    gi.ExecuteHooksForPtr<H>(key,4);assert(total==57);
    gi.UnregisterGameHookForPtr<H>(ptr);gi.RemoveAllQueuedHooks();assert(gi.GetHookData<H>()->count(ptr)==0);
    HOOK_ID filter=gi.RegisterGameHookForFilter<H>([](int16_t n){return n>0;},[&total](int16_t n){total+=n;});
    gi.ExecuteHooksForFilter<H>(-2);assert(total==57&&gi.GetHookData<H>()->at(filter).calls==0);
    gi.ExecuteHooksForFilter<H>(2);assert(total==59&&gi.GetHookData<H>()->at(filter).calls==1);
    gi.UnregisterGameHookForFilter<H>(filter);gi.ProcessUnregisteredHooks<H>();assert(gi.GetHookData<H>()->empty());
    gi.nextHookId=UINT32_MAX;
    HOOK_ID wrapped=gi.RegisterGameHook<H>([](int16_t){});assert(wrapped==1);
    gi.nextHookId=1;
    HOOK_ID collision=gi.RegisterGameHook<H>([](int16_t){});assert(collision==2);
    gi.UnregisterGameHook<H>(wrapped);gi.UnregisterGameHook<H>(collision);gi.RemoveAllQueuedHooks();
    typedef GameInteractor::OnPlayerShieldControl PointerHook;
    HOOK_ID change=gi.RegisterGameHook<PointerHook>([](float* a,float* b){*a+=*b;});
    float a=1,b=2;gi.ExecuteHooks<PointerHook>(&a,&b);assert(a==3&&b==2);
    gi.UnregisterGameHook<PointerHook>(change);gi.ProcessUnregisteredHooks<PointerHook>();
    HOOK_ID cross=RegisterCrossTranslationUnit(&gi,&total);
    gi.ExecuteHooks<H>(5);assert(total==64&&gi.GetHookData<H>()->count(cross)==1);
    gi.UnregisterGameHook<H>(cross);gi.RemoveAllQueuedHooks();assert(gi.GetHookData<H>()->empty());
    Actor actor={};actor.id=42;actor.params=7;
    assert(GameInteractor::HookFilter::ActorMatchIdAndParams(42,7)(&actor));
    assert(!GameInteractor::HookFilter::ActorMatchIdAndParams(42,8)(&actor));
    bool result=false;assert(GameInteractor::HookFilter::SActorMatchIdAndParams(42,7)(&actor,&result)&&!result);
    puts("Current hook registration, location metadata, deferred removal, ID/pointer/filter dispatch, wrap/collision and callback arguments agree");
}
