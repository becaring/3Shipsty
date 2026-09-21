#include "ObjectExtension.h"
#include <cassert>
#include <cstdio>
#include <memory>
struct First {int value;explicit First(int n):value(n){}};
struct Second {std::shared_ptr<int> value;explicit Second(std::shared_ptr<int> p):value(p){}};
static ObjectExtension::Register<First> registerFirst;
static ObjectExtension::Register<Second> registerSecond;
int main(){
    ObjectExtension& registry=ObjectExtension::GetInstance();int one=0,two=0;
    assert(registry.Get<First>(NULL)==NULL&&!registry.Has<First>(NULL));
    registry.Set<First>(NULL,First(3));assert(!registry.Has<First>(NULL));
    registry.Set<First>(&one,First(7));registry.Set<First>(&two,First(9));
    assert(registry.Get<First>(&one)->value==7&&registry.Get<First>(&two)->value==9);
    registry.Get<First>(&one)->value=11;assert(registry.Get<First>(&two)->value==9);
    std::shared_ptr<int> owner(new int(4));std::weak_ptr<int> weak=owner;
    registry.Set<Second>(&one,Second(owner));owner.reset();assert(!weak.expired());
    assert(registry.Has<Second>(&one)&&!registry.Has<Second>(&two));
    registry.Remove<First>(&one);assert(!registry.Has<First>(&one)&&registry.Has<Second>(&one));
    ObjectExtension_Free(&one);assert(weak.expired()&&!registry.Has<Second>(&one)&&registry.Has<First>(&two));
    registry.Free(NULL);registry.Free(&two);assert(!registry.Has<First>(&two));
    puts("Actual ObjectExtension type IDs, object isolation, null handling, mutate/remove/free and captured ownership agree");
}
