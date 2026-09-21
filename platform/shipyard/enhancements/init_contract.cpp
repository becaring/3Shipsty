#include "soh/ShipInit.hpp"
#include <cassert>
#include <cstdio>
static int total=0;
static void First(){total=total*10+1;}
static void Second(){total=total*10+2;}
static RegisterShipInitFunc first(First,{"A","B","A"});
static RegisterShipInitFunc second(Second,{"A"});
static std::string callbackFunction;
static RegisterShipInitFunc third([](){total=total*10+3;callbackFunction=__FUNCSIG__;},{"C"});
int main(){
    assert(total==0&&callbackFunction.empty());
    assert(ShipInit::GetAll()["A"].size()==2&&ShipInit::GetAll()["B"].size()==1);
    ShipInit::InitAll();assert(total==123&&!callbackFunction.empty());
    total=0;ShipInit::Init("A");assert(total==12);
    total=0;ShipInit::Init("B");assert(total==1);
    ShipInit::Init("absent");assert(total==1&&ShipInit::GetAll().count("absent")==1);
    puts("Actual ShipInit boot/path dispatch, duplicate path handling and callback order agree");
}
