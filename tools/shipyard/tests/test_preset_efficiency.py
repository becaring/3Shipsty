"""Run the pinned and selected preset block loops against one host config model."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment
from prepare_application_extras import prepare
from prepare_console_variables import prepare as prepare_cvars


def loop(text,begin):
    start=text.index(begin,text.index('void applyPreset('))
    end=text.index('            if (i == PRESET_SECTION_RANDOMIZER) {',start)
    return text[start:end]


class PresetEfficiencyTests(unittest.TestCase):
    def test_actual_block_loops_and_navigation_reload(self):
        prepare();prepare_cvars()
        original=(ROOT/'soh/soh/Enhancements/Presets/Presets.cpp').read_text()
        projected=(ROOT/'scratch/application-extras-xdk/generated/soh/soh/Enhancements/Presets/Presets.cpp').read_text()
        old=loop(original,'            for (auto& item : section.items()) {')
        new=loop(projected,'            auto presetConfig = Ship::Context::GetInstance()->GetConfig();')
        load=(ROOT/'scratch/console-variables-xdk/generated/src/ship/config/ConsoleVariable.cpp').read_text()
        self.assertIn('#include "compile_definitions.h"',load)
        body=load[load.index('void ConsoleVariable::Load() {'):load.index('\nvoid ConsoleVariable::LoadFromPath(')]
        self.assertLess(body.index('LoadLegacy();'),body.index('RegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);'))
        self.assertEqual(body.count('RegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);'),1)
        code=r'''#include <nlohmann/json.hpp>
#include <string>
#include <cstdio>
#include <stdexcept>
using json=nlohmann::json;
struct Config {
    json data; int saves=0;
    json GetNestedJson(){return data;}
    void SetBlock(const std::string& path,json block){
        json* target=&data; size_t pos=0,next;
        while((next=path.find('.',pos))!=std::string::npos){target=&(*target)[path.substr(pos,next-pos)];pos=next+1;}
        (*target)[path.substr(pos)]=block; ++saves;
    }
    void EraseBlock(const std::string& path){
        json* target=&data; size_t pos=0,next;
        while((next=path.find('.',pos))!=std::string::npos){target=&(*target)[path.substr(pos,next-pos)];pos=next+1;}
        target->erase(path.substr(pos)); ++saves;
    }
};
struct ConsoleVariables {
    Config* config; int loads=0; int nav=1;
    void Load(){++loads; const json& settings=config->data["CVars"]["gSettings"];
        nav=settings.is_object() && settings.contains("ControlNav") ? settings["ControlNav"].get<int>() : 1;}
};
namespace Ship { struct Context {
    Config config; ConsoleVariables cvars;
    Context(){cvars.config=&config;}
    static Context* GetInstance(){static Context ctx;return &ctx;}
    Config* GetConfig(){return &config;}
    ConsoleVariables* GetConsoleVariables(){return &cvars;}
}; }
namespace fmt {std::string format(const char*,const char* root,const std::string& key){return std::string(root)+"."+key;}}
namespace ShipyardInputCompiler {bool Contains(const json& value,const std::string& key){return value.contains(key);}}
void CVarClearBlock(const char* key){auto ctx=Ship::Context::GetInstance();ctx->config.EraseBlock(std::string("CVars.")+key);ctx->cvars.Load();}
void original(json section,std::string sectionStrategy){
''' + old + r'''}
void projected(json section,std::string sectionStrategy){
''' + new + r'''}
struct Result{json data;int saves;int loads;int nav;bool closed;bool reopened;};
Result run(void(*fn)(json,std::string),json section,const std::string& strategy,int savedNav){
    auto ctx=Ship::Context::GetInstance();
    ctx->config.data={{"CVars",{{"a",{{"old",7}}},{"b",{{"z",0}}},{"keep",{{"v",4}}},
        {"gSettings",savedNav<0?json::object():json{{"ControlNav",savedNav}}}}},
        {"Window",{{"AudioBackend","keep-me"}}}};
    ctx->config.saves=ctx->cvars.loads=0;ctx->cvars.nav=1;
    fn(section,strategy);fn(section,strategy);
    bool visible=true;
    if(ctx->cvars.nav)visible=false;
    bool closed=!visible;
    if(ctx->cvars.nav)visible=true;
    return {ctx->config.data,ctx->config.saves,ctx->cvars.loads,ctx->cvars.nav,closed,visible};
}
int check(json section,const std::string& strategy,int nav,int expectedOld,int expectedNew){
    Result a=run(original,section,strategy,nav),b=run(projected,section,strategy,nav);
    if(a.data!=b.data || a.nav!=b.nav || a.closed!=b.closed || a.reopened!=b.reopened)return 1;
    if(a.saves!=expectedOld || a.loads!=expectedOld || b.saves!=expectedNew || b.loads!=expectedNew)return 2;
    if(a.data["Window"]["AudioBackend"]!="keep-me")return 3;
    if(nav==0 && (a.closed || b.closed))return 4;
    if(nav!=0 && (!a.closed || !b.closed || !a.reopened || !b.reopened))return 5;
    return 0;
}
int main(){
    int code=0;
    code=check({{"a",{{"x",1}}},{"b",{{"y",2}}},{"c",{{"q",3}}}},"overwrite",-1,6,2);if(code)return 10+code;
    code=check({{"a",{{"x",1}}},{"b",{{"y",2}}}},"merge",1,4,2);if(code)return 20+code;
    code=check({{"a",nullptr},{"b",{{"y",2}}}},"overwrite",1,4,4);if(code)return 30+code;
    code=check({{"a.b",{{"x",1}}},{"b",{{"y",2}}}},"overwrite",0,4,4);if(code)return 40+code;
    code=check({{"a",4},{"b",{{"y",2}}}},"overwrite",1,4,4);if(code)return 50+code;
    code=check({{"a",{{"x",1}}}},"merge",1,2,2);if(code)return 60+code;
    std::puts("preset original/projected blocks, repeated apply, nav close/reopen PASS");return 0;
}
'''
        compiler,env=host_environment()
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as folder:
            path=Path(folder);source=path/'preset.cpp';source.write_text(code)
            executable=path/'preset.exe'
            command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/O2',
                     '/I'+str(ROOT/'platform/shipyard/json/upstream/include'),str(source),'/Fe:'+str(executable)]
            built=subprocess.run(command,cwd=path,env=env,capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            result=subprocess.run([str(executable)],cwd=path,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('nav close/reopen PASS',result.stdout)
