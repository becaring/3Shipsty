// Host-only fixtures exercise production mapping/math and physical bridge code.
#include "input/physical.h"
#include "ship/controller/controldevice/controller/ControllerStick.h"
#include "libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.h"
#include "libultraship/libultra/controller.h"
#include <cassert>
#include <iostream>
#include <cstring>
#include <map>
#include <algorithm>
#include <sstream>
using namespace Ship;
static ShipyardInputRawPad samples[4];
static bool connected[4];
static uint16_t motors[4][2];
static uint32_t ticks;
bool ShipyardInput_ReadPhysicalPad(unsigned slot,ShipyardInputRawPad* state){if(!connected[slot])return false;*state=samples[slot];return true;}
bool ShipyardInput_PhysicalPadHasRumble(unsigned slot){return connected[slot];}
bool ShipyardInput_WritePhysicalRumble(unsigned slot,uint16_t a,uint16_t b){motors[slot][0]=a;motors[slot][1]=b;return connected[slot];}
uint32_t ShipyardInput_InputMilliseconds(){return ticks;}
class AxisFixture : public ControllerAxisDirectionMapping {
 public: float value; std::string id;
 AxisFixture(Direction direction,std::string name):ControllerInputMapping(SDLGamepad),ControllerAxisDirectionMapping(SDLGamepad,0,LEFT_STICK,direction),value(0),id(name){}
 float GetNormalizedAxisDirectionValue(){return value;}
 std::string GetAxisDirectionMappingId(){return id;}
 void SaveToConfig(){} void EraseFromConfig(){}
};
template<class T> std::string dump(const T& v){std::ostringstream o;o<<v;return o.str();}
template<class A,class B> std::string dump(const std::pair<A,B>&);
template<class V> std::string dump(const std::vector<V>&);
template<class K> std::string dump(const std::unordered_set<K>&);
template<class K,class V> std::string dump(const std::unordered_map<K,V>&);
template<class A,class B> std::string dump(const std::pair<A,B>& p){return "("+dump(p.first)+","+dump(p.second)+")";}
template<class V> std::string dump(const std::vector<V>& v){std::string s="[";for(auto x:v)s+=dump(x)+";";return s+"]";}
template<class K> std::string dump(const std::unordered_set<K>& v){std::vector<std::string>s;for(auto x:v)s.push_back(dump(x));std::sort(s.begin(),s.end());return dump(s);}
template<class K,class V> std::string dump(const std::unordered_map<K,V>& v){std::vector<std::string>s;for(auto x:v)s.push_back(dump(x));std::sort(s.begin(),s.end());return dump(s);}
int main(){
 static_assert(sizeof(CONTROLLERBUTTONS_T)==4,"modern custom button width");
 static_assert(sizeof(((OSContPad*)0)->button)==4,"pad width");
 LUS::ControllerDefaultMappings defaults;
 auto keyboard=defaults.GetDefaultKeyboardKeyToButtonMappings();
 auto keyboardAxis=defaults.GetDefaultKeyboardKeyToAxisDirectionMappings();
 auto buttons=defaults.GetDefaultSDLButtonToButtonMappings();
 auto buttonAxis=defaults.GetDefaultSDLButtonToAxisDirectionMappings();
 auto axisButtons=defaults.GetDefaultSDLAxisDirectionToButtonMappings();
 auto axisAxis=defaults.GetDefaultSDLAxisDirectionToAxisDirectionMappings();
 std::cout<<dump(keyboard)<<dump(keyboardAxis)<<dump(buttons)<<dump(buttonAxis)<<dump(axisButtons)<<dump(axisAxis)<<"\n";
 keyboard.clear();keyboard[0x80000000u].insert(LUS_KB_F24);
 buttons.clear();buttons[0x40000000u].insert(SDL_CONTROLLER_BUTTON_X);
 LUS::ControllerDefaultMappings custom(keyboard,keyboardAxis,buttons,buttonAxis,axisButtons,axisAxis);
 assert(custom.GetDefaultKeyboardKeyToButtonMappings().at(0x80000000u).count(LUS_KB_F24));
 assert(custom.GetDefaultSDLButtonToButtonMappings().at(0x40000000u).count(SDL_CONTROLLER_BUTTON_X));
 std::cout<<dump(custom.GetDefaultKeyboardKeyToButtonMappings())<<dump(custom.GetDefaultSDLButtonToButtonMappings())<<"\n";
 ControllerStick stick(0,LEFT_STICK);
 auto right=std::make_shared<AxisFixture>(RIGHT,"right");auto left=std::make_shared<AxisFixture>(LEFT,"left");
 auto up=std::make_shared<AxisFixture>(UP,"up");auto down=std::make_shared<AxisFixture>(DOWN,"down");
 auto extra=std::make_shared<AxisFixture>(RIGHT,"extra");
 stick.AddAxisDirectionMapping(RIGHT,right);stick.AddAxisDirectionMapping(LEFT,left);stick.AddAxisDirectionMapping(UP,up);stick.AddAxisDirectionMapping(DOWN,down);stick.AddAxisDirectionMapping(RIGHT,extra);
 assert(stick.HasMappingsForPhysicalDeviceType(SDLGamepad));assert(!stick.HasMappingsForPhysicalDeviceType(Mouse));
 uint32_t hash=2166136261u;
 for(int x=-100;x<=100;++x)for(int y=-100;y<=100;++y){
   right->value=x>0?float(x):0;left->value=x<0?float(-x):0;up->value=y>0?float(y):0;down->value=y<0?float(-y):0;extra->value=3;
   int8_t px=0,py=0;stick.UpdatePad(px,py);hash=(hash^uint8_t(px))*16777619u;hash=(hash^uint8_t(py))*16777619u;
 }
 std::cout<<"stick-grid "<<hash<<"\n";
 ShipyardInput_PumpGamepads();assert(ShipyardInput_NumGamepads()==0);
 connected[1]=connected[3]=true;samples[1].buttons=0x1001;samples[1].leftY=-32768;samples[1].rightY=32767;samples[1].leftTrigger=255;
 ShipyardInput_PumpGamepads();assert(ShipyardInput_NumGamepads()==2);
 auto a=ShipyardInput_OpenGamepad(0);auto b=ShipyardInput_OpenGamepad(1);assert(a&&b&&a!=b);assert(!ShipyardInput_OpenGamepad(2));
 assert(ShipyardInput_GamepadButton(a,ShipyardButtonA)==1);assert(ShipyardInput_GamepadButton(a,ShipyardButtonUp)==1);assert(!ShipyardInput_GamepadButton(a,ShipyardButtonGuide));
 assert(ShipyardInput_GamepadAxis(a,ShipyardAxisLeftY)==32767);assert(ShipyardInput_GamepadAxis(a,ShipyardAxisRightY)==-32767);assert(ShipyardInput_GamepadAxis(a,ShipyardAxisLeftTrigger)==32767);
 int32_t oldId=ShipyardInput_GamepadInstance(a);uint32_t generation=ShipyardInput_GamepadTopologyGeneration();
 ticks=0xfffffff0u;assert(!ShipyardInput_GamepadRumble(a,50000,12345,32));assert(motors[1][0]==50000&&motors[1][1]==12345);
 ticks=0x0f;ShipyardInput_PumpGamepads();assert(motors[1][0]==50000);ticks=0x10;ShipyardInput_PumpGamepads();assert(!motors[1][0]);
 assert(!ShipyardInput_GamepadRumble(a,30000,40000,0));ticks+=10000;ShipyardInput_PumpGamepads();assert(motors[1][1]==40000);
 connected[1]=false;ShipyardInput_PumpGamepads();assert(!ShipyardInput_GamepadButton(a,ShipyardButtonA));assert(ShipyardInput_GamepadInstance(a)==-1);assert(!motors[1][1]);
 assert(ShipyardInput_GamepadTopologyGeneration()!=generation);connected[1]=true;ShipyardInput_PumpGamepads();assert(ShipyardInput_GamepadInstance(a)!=oldId);
 assert(!ShipyardInput_GamepadHasSensor(a,2));assert(ShipyardInput_GamepadSensorData(a,2,0,0)==-1);assert(!ShipyardInput_GamepadHasLED(a));
 ShipyardInput_StopPhysicalRumble();std::cout<<"physical fixture passed: slots, axes, topology, disconnect, timed/sustained rumble, capabilities\n";
}
