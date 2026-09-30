"""Actual startup tables, audio settings and Unicode/game-print differentials."""
import hashlib,json,re,runpy,struct,subprocess
from prepare_application import ROOT,OUT,prepare,function
from prepare_archives import stable
from cpp_ast import PARSER,walk

def main():
    prepare();compiler,environment=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();runs=[]
    for projected in [False,True]:
        folder=OUT/('values-projected' if projected else 'values-original');folder.mkdir(exist_ok=True)
        text=((OUT/'generated' if projected else ROOT)/'soh/soh/OTRGlobals.cpp').read_text(encoding='utf-8')
        source='''#include "resources/runtime_support.h"
#include "z64.h"
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#include "ship/audio/AudioSettings.h"
#include <cstdio>
#include <algorithm>
#include <vector>
#include <unordered_map>
#include <unordered_set>
'''
        header=((OUT/'generated' if projected else ROOT)/'soh/soh/OTRGlobals.h').read_text(encoding='utf-8')
        source+='\n'.join(re.findall(r'^#define BTN_CUSTOM_.*$',header,re.M))+'\n'
        begin=text.index('static std::unordered_map<ItemID, GetItemID> MakeItemIDtoGetItemIDMap') if projected else text.index('std::unordered_map<ItemID, GetItemID> ItemIDtoGetItemIDMap')
        end=function(text,'RetrieveRandomizerGetFromItemID').end_byte
        source+=text.encode()[len(text[:begin].encode()):end].decode()+'\n'
        if not projected:
            audio=(ROOT/'libultraship/include/ship/audio/AudioPlayer.h').read_text()
            definition=re.search(r'struct AudioSettings \{.*?\n\};',audio,re.S)[0]
            source=source.replace('#include "ship/audio/AudioSettings.h"','#include "ship/audio/AudioChannelsSetting.h"\nnamespace Ship {\n'+definition+'\n}\n')
        if projected:
            printer=function(text,'OTRGfxPrint').text.decode()
            assert printer.count('static const uint32_t ') == 4
            assert 'std::vector<uint32_t>' not in printer
        for name in ['StringToU16','OTRGfxPrint']:source+=function(text,name).text.decode()+'\n'
        ctor=function(text,'OTRGlobals::OTRGlobals').text.decode()
        if projected:
            array=re.search(r'const CONTROLLERBUTTONS_T buttonMasks\[\]=\{[\s\S]*?\};',ctor)[0]
            source+='std::vector<CONTROLLERBUTTONS_T> Buttons(){'+array+'return std::vector<CONTROLLERBUTTONS_T>(buttonMasks,buttonMasks+sizeof(buttonMasks)/sizeof(buttonMasks[0]));}\n'
        else:
            values=re.search(r'std::vector<CONTROLLERBUTTONS_T>\((\{[\s\S]*?\})\)',ctor)[0]
            source+='std::vector<CONTROLLERBUTTONS_T> Buttons(){return '+values+';}\n'
        init=function(text,'OTRGlobals::Initialize').text.decode()
        if projected:
            values=re.search(r'const uint32_t validHashValues\[\]=\{[\s\S]*?\};',init)[0]
            source+='std::unordered_set<uint32_t> Hashes(){'+values+'return std::unordered_set<uint32_t>(validHashValues,validHashValues+sizeof(validHashValues)/sizeof(validHashValues[0]));}\n'
            a=init.index('Ship::AudioSettings audioSettings;');b=init.index('context->InitAudio(audioSettings);',a)
            source+='Ship::AudioSettings Audio(){'+init[a:b]+'return audioSettings;}\n'
        else:
            values=re.search(r'std::unordered_set<uint32_t> ValidHashes = \{[\s\S]*?\};',init)[0]
            source+='std::unordered_set<uint32_t> Hashes(){'+values+'return ValidHashes;}\n'
            values=re.search(r'context->InitAudio\((\{[^;]+\})\);',init)[1]
            source+='Ship::AudioSettings Audio(){return '+values+';}\n'
        source='\n#include "soh/GameVersions.h"\n'+source
        source+='''
static unsigned long long digest=1469598103934665603ULL;
static void Byte(unsigned char value){digest=(digest^value)*1099511628211ULL;}
static void Print(void*,char value){Byte((unsigned char)value);}
static std::string Utf8(unsigned value){std::string r;
if(value<128)r+=(char)value;
else if(value<2048){r+=(char)(192|(value>>6));r+=(char)(128|(value&63));}
else if(value<65536){r+=(char)(224|(value>>12));r+=(char)(128|((value>>6)&63));r+=(char)(128|(value&63));}
else{r+=(char)(240|(value>>18));r+=(char)(128|((value>>12)&63));r+=(char)(128|((value>>6)&63));r+=(char)(128|(value&63));}return r;}
int main(){
std::vector<CONTROLLERBUTTONS_T> buttons=Buttons();
for(size_t i=0;i<buttons.size();++i)printf("button %u\\n",unsigned(buttons[i]));
std::unordered_set<uint32_t> hashes=Hashes();std::vector<uint32_t> ordered(hashes.begin(),hashes.end());std::sort(ordered.begin(),ordered.end());
for(size_t i=0;i<ordered.size();++i)printf("version %u\\n",unsigned(ordered[i]));
Ship::AudioSettings audio=Audio();printf("audio %d %d %d %d\\n",audio.SampleRate,audio.SampleLength,audio.DesiredBuffered,int(audio.ChannelSetting));
for(unsigned i=0;i<65536;++i){unsigned a=RetrieveGetItemIDFromItemID((ItemID)i),b=RetrieveRandomizerGetFromItemID((ItemID)i);for(unsigned j=0;j<4;++j){Byte((unsigned char)(a>>(8*j)));Byte((unsigned char)(b>>(8*j)));}}
printf("lookup %llu\\n",digest);digest=1469598103934665603ULL;
unsigned count=0;for(unsigned i=1;i<65536;++i){if(i>=0xD800 && i<=0xDFFF)continue;std::string value=Utf8(i);
std::wstring wide=StringToU16(value);for(size_t j=0;j<wide.size();++j){Byte((unsigned char)wide[j]);Byte((unsigned char)(wide[j]>>8));}
OTRGfxPrint(value.c_str(),NULL,Print);value=Utf8(GFXP_HIRAGANA_CHAR)+value;OTRGfxPrint(value.c_str(),NULL,Print);++count;}
for(unsigned i=0x10000;i<=0x10FFFF;i+=997){std::wstring wide=StringToU16(Utf8(i));for(size_t j=0;j<wide.size();++j){Byte((unsigned char)wide[j]);Byte((unsigned char)(wide[j]>>8));}}
printf("unicode %u %llu\\n",count,digest);return 0;}
'''
        stable(folder/'contract.cpp',source)
        ui_host=ROOT/'scratch/soh-ui-xdk/host-projected/run.json'
        if ui_host.is_file():
            flags=json.loads(ui_host.read_text())['command']
        else:
            # The value contract only needs the UI include roots; do not rerun
            # the unchanged UI projector just to recreate its host receipt.
            from prepare_soh_ui import includes as ui_includes, OUT as ui_out, BASE as ui_base
            flags=['/I'+str(ui_out/'generated'/ui_base)]+['/I'+str(p) for p in ui_includes()]
        header=ROOT/('scratch/resource-manager-xdk/generated/include' if projected else 'libultraship/include')
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(header)]+[f for f in flags if f.startswith('/I')]
        command+=[str(folder/'contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        r=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True);stable(folder/'build.log',r.stdout+r.stderr);assert r.returncode==0,folder/'build.log'
        r=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True);assert r.returncode==0,(r.returncode,r.stderr)
        runs.append(dict(command=command,stdout=r.stdout))
    assert runs[0]['stdout']==runs[1]['stdout'],runs
    flags=json.loads((OUT/'xdk/build.json').read_text())[0]['command'][:-2]
    obj=OUT/'xdk/values.obj';command=flags+[str(OUT/'values-projected/contract.cpp'),'/Fo'+str(obj)]
    r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr);assert r.returncode==0,obj.with_suffix('.log')
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(OUT/'values-verification.json',json.dumps(dict(host=runs,native_contract=command,target_execution=False),indent=2)+'\n')
    print(runs[0]['stdout'])

if __name__=='__main__':main()
