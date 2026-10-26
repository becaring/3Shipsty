"""Observe ownership copies in extracted controller polling functions."""
import argparse
from pathlib import Path
from test_backend_cpu import function, host_environment, invoke, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    controller = (args.source_root / 'src/libultraship/controller/controldevice/controller/Controller.cpp').read_text()
    stick = (args.source_root / 'src/ship/controller/controldevice/controller/ControllerStick.cpp').read_text()
    read = function(controller, 'void Controller::ReadToOSContPad(')
    loop = function(read, '{ auto&&')
    axis = function(stick, 'float ControllerStick::GetAxisDirectionValue(')
    code = r'''
#include <algorithm>
#include <cassert>
#include <memory>
#include <string>
#include <unordered_map>
namespace Shipyard { namespace Resources { using std::begin; using std::end; } }
bool observedCopy=false;
struct Button {
 std::weak_ptr<Button> self;
 void UpdatePad(unsigned& buttons){if(self.use_count()!=2)observedCopy=true;buttons|=1;}
};
std::unordered_map<unsigned,std::shared_ptr<Button>> mButtons;
struct Pad{unsigned button;} padToBuffer={};
struct ControllerAxisDirectionMapping {
 std::weak_ptr<ControllerAxisDirectionMapping> self; float value;
 float GetNormalizedAxisDirectionValue(){if(self.use_count()!=2)observedCopy=true;return value;}
};
enum Direction {LEFT, RIGHT};
struct ControllerStick {
 std::unordered_map<Direction,std::unordered_map<std::string,std::shared_ptr<ControllerAxisDirectionMapping>>> mAxisDirectionMappings;
 float GetAxisDirectionValue(Direction direction);
};
'''
    code += axis + '\nvoid ReadButtons() ' + loop
    code += r'''
int main(){
 auto button=std::make_shared<Button>();button->self=button;mButtons[1]=button;
 ReadButtons();assert(padToBuffer.button==1);assert(!observedCopy);
 ControllerStick stick;
 auto a=std::make_shared<ControllerAxisDirectionMapping>();a->self=a;a->value=0.25f;
 auto b=std::make_shared<ControllerAxisDirectionMapping>();b->self=b;b->value=0.75f;
 assert(stick.GetAxisDirectionValue(LEFT)==0);
 stick.mAxisDirectionMappings[LEFT][std::string(128,'a')]=a;
 assert(stick.GetAxisDirectionValue(LEFT)==0.25f);
 stick.mAxisDirectionMappings[LEFT][std::string(128,'b')]=b;
 assert(stick.GetAxisDirectionValue(LEFT)==0.75f);assert(!observedCopy);
 b->value=0.25f;assert(stick.GetAxisDirectionValue(LEFT)==0.25f);
 assert(!observedCopy);
}
'''
    folder = ROOT / 'scratch/xenon-cpu-audit/input/host'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'contract.cpp'
    path.write_text(code)
    compiler, env = host_environment()
    invoke([compiler, '/nologo', '/std:c++20', '/EHsc', path,
            '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')], folder, 'build', env)
    invoke([folder / 'contract.exe'], folder, 'run')
    print('Controller polling retains results without temporary ownership copies.')


if __name__ == '__main__':
    main()
