"""Execute actual typed CVar methods before/after the shared borrow projection."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment, PLATFORM_BASE
from xbox360_platform.console_variable_lookup import transform, header


def method(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2]


class ConsoleVariableLookupTests(unittest.TestCase):
    def test_actual_getters_mutation_clear_and_reload(self):
        original = (ROOT / 'libultraship/src/ship/config/ConsoleVariable.cpp').read_text()
        projected = transform(original)
        public = 'std::shared_ptr<CVar> ConsoleVariable::Get('
        self.assertIn('return it != mVariables.end() ? it->second : nullptr;', method(projected, public))
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(dir=ROOT / 'scratch') as temp:
            folder = Path(temp)
            for label, text, expected in [('original', original, 5), ('projected', projected, 0)]:
                # Actual Get through ClearVariable, and actual recursive Load.
                bodies = text[text.index(public):text.index('\nvoid ConsoleVariable::ClearBlock(')]
                load = text[text.index('void ConsoleVariable::Load()'):text.index('\nvoid ConsoleVariable::LoadLegacy()')]
                get_signature = 'std::shared_ptr<CVar> ConsoleVariable::Get(const char* name) {'
                bodies = bodies.replace(get_signature, get_signature + '\n    ++getCalls;', 1)
                bodies += '\n' + method(text, 'void ConsoleVariable::CopyVariable(')
                bodies += '\n' + method(text, 'void ConsoleVariable::Save()')
                include = folder / label / 'ship/config/ConsoleVariable.h'
                include.parent.mkdir(parents=True)
                declaration = (ROOT / 'libultraship/include/ship/config/ConsoleVariable.h').read_text()
                include.write_text(header(declaration) if label == 'projected' else declaration)
                source = folder / (label + '.cpp')
                source.write_text(r'''
#include "ship/config/ConsoleVariable.h"
#include <cstring>
#include <algorithm>
#include <iostream>
#include <stdexcept>
using json=nlohmann::json;
int getCalls=0;
bool countAllocations=false;size_t allocations=0;
void* operator new(size_t size) { if(countAllocations)++allocations;void* p=std::malloc(size?size:1);if(!p)throw std::bad_alloc();return p; }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p,size_t) noexcept { std::free(p); }
namespace Ship {
struct Config {
    json disk,live=json::object();
    void Reload() { live=disk; }
    void Save() { disk=live; }
    json GetNestedJson() { return live; }
    std::string pointer(std::string key) {std::replace(key.begin(),key.end(),'.','/');return "/"+key;}
    template<class T>void set(const std::string& key,T value){live[json::json_pointer(pointer(key))]=value;}
    void SetString(const std::string& key,const char* v){set(key,v);}
    void SetInt(const std::string& key,int32_t v){set(key,v);}
    void SetFloat(const std::string& key,float v){set(key,v);}
    void SetUInt(const std::string& key,uint32_t v){set(key,v);}
    void Erase(const std::string& key) {json flat=live.flatten();flat.erase(pointer(key));live=flat.unflatten();}
};
struct Context {
    std::shared_ptr<Config> config=std::make_shared<Config>();
    static Context* GetInstance() { static Context ctx;return &ctx; }
    std::shared_ptr<Config> GetConfig() { return config; }
};
namespace StringHelper {
std::string Sprintf(const char*,const char* a,const char* b) { return std::string(a)+"."+b; }
std::string Sprintf(const char*,const char* a) { return std::string("CVars.")+a; }
}
ConsoleVariable::ConsoleVariable() {}
ConsoleVariable::~ConsoleVariable() {}
void ConsoleVariable::LoadLegacy() {}
''' + bodies + '\n' + load + r'''
}
void require(bool value,const char* message) { if(!value)throw std::runtime_error(message); }
int main() { try {
    Ship::ConsoleVariable vars;
    vars.SetInteger("int",17);vars.SetFloat("float",2.5f);vars.SetString("string","first");
    Color_RGBA8 rgba={1,2,3,4};Color_RGB8 rgb={5,6,7};
    vars.SetColor("rgba",rgba);vars.SetColor24("rgb",rgb);
    getCalls=0;
    require(vars.GetInteger("int",0)==17,"integer value");
    require(vars.GetFloat("float",0)==2.5f,"float value");
    require(std::strcmp(vars.GetString("string","fallback"),"first")==0,"string value");
    require(vars.GetColor("rgba",rgba).a==4,"RGBA value");
    require(vars.GetColor24("rgb",rgb).b==7,"RGB value");
    require(getCalls==EXPECTED_GET_CALLS,"typed getters unexpectedly acquired shared ownership");
    require(vars.GetColor("rgb",rgba).a==255 && vars.GetColor24("rgba",rgb).r==1,"color conversion");
    require(vars.GetInteger("float",39)==39 && vars.GetFloat("int",8.5f)==8.5f,"wrong-type default");
    const char* fallback="same fallback pointer";
    require(vars.GetString("missing",fallback)==fallback && vars.GetString("int",fallback)==fallback,"string default");
    require(vars.GetInteger("missing",99)==99 && vars.GetColor("int",rgba).a==4 &&
            vars.GetColor24("missing",rgb).r==5,"missing/color defaults");
    vars.SetInteger("int",23);require(vars.GetInteger("int",0)==23,"getter cached old integer");
    vars.SetString("string","second");require(std::strcmp(vars.GetString("string",""),"second")==0,"getter cached old string");
    auto owned=vars.Get("int");require(owned.use_count()==2,"public Get no longer owns value");
    vars.ClearVariable("int");require(vars.GetInteger("int",51)==51 && owned->Integer==23,"clear ownership/default");
    auto oldString=vars.Get("string");
    Ship::Context::GetInstance()->config->disk={{"CVars",{{"int",71},{"string","reloaded"},
        {"rgba",{{"Type","RGBA"},{"R",8},{"G",9},{"B",10},{"A",11}}}}}};
    vars.Load();
    require(vars.GetInteger("int",0)==71 && vars.GetFloat("float",12)==12,"reload replacement/default");
    require(std::strcmp(vars.GetString("string",""),"reloaded")==0 &&
            std::strcmp(oldString->String,"second")==0,"reload string ownership");
    require(vars.GetColor("rgba",rgba).a==11,"reload color");
    vars.ClearVariable("string");require(vars.GetString("string",fallback)==fallback,"cleared string default");
    const char* longName="gEnhancements.AReallyLongConsoleVariableNameForWarmLookup";
    const char* missingName="gEnhancements.AnotherLongConsoleVariableNameAbsentFromTheMap";
    vars.SetInteger(longName,83);
    allocations=0;countAllocations=true;
    for(int i=0;i<1000;++i){
        require(vars.GetInteger(longName,0)==83,"long-name hit");
        require(vars.GetInteger(missingName,9)==9,"long-name miss");
        require(vars.GetFloat(longName,1)==1&&vars.GetString(longName,fallback)==fallback,"long-name type");
        require(vars.GetColor(longName,rgba).a==4&&vars.GetColor24(longName,rgb).b==7,"long-name color default");
        require(vars.Get(longName)->Integer==83,"owning public lookup");
    }
    countAllocations=false;
    require(EXPECTED_GET_CALLS==0?allocations==0:allocations>0,"warm lookup allocation contract");
    char temporaryName[]="gSettings.TemporaryOwnedNameThatExceedsSmallStringCapacity";
    vars.SetInteger(temporaryName,92);temporaryName[0]='X';
    require(vars.GetInteger("gSettings.TemporaryOwnedNameThatExceedsSmallStringCapacity",0)==92,"insertion borrowed caller name");
    vars.CopyVariable(longName,"gSettings.CopyOfLongName");vars.ClearVariable(longName);
    require(vars.GetInteger("gSettings.CopyOfLongName",0)==83,"copy/clear mutation");
    vars.SetString("savedString","saved");vars.SetFloat("savedFloat",1.25f);
    vars.SetColor24("savedRGB",rgb);vars.Save();
    require(Ship::Context::GetInstance()->config->disk["CVars"]["savedString"]=="saved","key serialization string");
    vars.Load();require(vars.GetInteger("gSettings.CopyOfLongName",0)==83&&vars.GetFloat("savedFloat",0)==1.25f&&
        vars.GetColor24("savedRGB",rgb).b==7,"serialized reload");
#if EXPECTED_GET_CALLS == 0
    using Shipyard::ConsoleVariables::NameKey;using Shipyard::ConsoleVariables::NameHash;
    char keyBuffer[]="a_long_borrowed_name_that_must_be_copied_before_storage";
    NameKey borrowed(keyBuffer,NameKey::Borrow);NameKey ownedKey(borrowed);
    std::unordered_map<NameKey,int,NameHash> keys;keys.insert(std::make_pair(borrowed,7));
    keyBuffer[0]='X';
    require(std::strcmp(ownedKey.c_str(),"a_long_borrowed_name_that_must_be_copied_before_storage")==0,"key copy retained borrow");
    require(keys.find("a_long_borrowed_name_that_must_be_copied_before_storage")->second==7,"stored key retained borrow");
    NameKey alias(ownedKey.c_str()+2,NameKey::Borrow);ownedKey=alias;
    require(std::strcmp(ownedKey.c_str(),"long_borrowed_name_that_must_be_copied_before_storage")==0,"alias assignment");
    NameKey withNull(std::string("a\0b",3)),shortKey("a");require(!(withNull==shortKey),"key equality truncated bytes");
#endif
    std::cout<<"CVar typed lookup ownership/value/clear/reload PASS\n";
    return 0;
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n';return 1; } }
''')
                exe = folder / (label + '.exe')
                command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD',
                           '/DEXPECTED_GET_CALLS=' + str(expected),
                           '/I' + str(folder / label), '/I' + str(PLATFORM_BASE / 'sources'),
                           '/I' + str(ROOT / 'libultraship/include'),
                           '/I' + str(ROOT / 'platform/shipyard/json/upstream/include'),
                           str(source), '/Fe:' + str(exe)]
                result = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(exe)], cwd=folder, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('reload PASS', result.stdout)
