"""Generate complete current ActorDB and configuration migration units for XDK."""
import argparse
import hashlib
import json
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import includes as enhancement_includes

OWN=ROOT/'platform/shipyard/app-services';OUT=ROOT/'scratch/app-services-xdk'

def transform(name,text):
    if name.endswith('/ConfigUpdaters.h'):
        text=once(text,'#include "libultraship/libultraship.h"',
                  '#include "ship/config/Config.h"\n#include "libultraship/bridge/consolevariablebridge.h"\n#include "ship/controller/controldevice/controller/mapping/keyboard/KeyboardScancodes.h"')
        text=text.replace(' final :',' :')
    elif name.endswith('/ActorDB.h'):
        fields=re.findall(r'    (int|u32|size_t|ActorFunc|ActorResetFunc) (\w+) = ([^;]+);',text.split('struct ActorDBInit {',1)[1].split('};',1)[0])
        if len(fields)!=9:raise ValueError('ActorDBInit default inventory changed')
        params=['const std::string& name_=std::string()','const std::string& desc_=std::string()']
        init=['name(name_)','desc(desc_)']
        for typ,member,value in fields:
            text=once(text,typ+' '+member+' = '+value+';',typ+' '+member+';')
            params.append(typ+' '+member+'_='+value);init.append(member+'('+member+'_)')
        text=once(text,'    ActorResetFunc reset;\n};','    ActorResetFunc reset;\n    ActorDBInit('+', '.join(params)+') : '+', '.join(init)+' {}\n};')
        text=once(text,'size_t nextFreeId = 0;','size_t nextFreeId;')
    elif name.endswith('/ActorDB.cpp'):
        text=once(text,'ActorDB::ActorDB() {','ActorDB::ActorDB() : nextFreeId(0) {')
        text=once(text,'static constexpr AddPair','static const AddPair')
        text=once(text,'static constexpr std::pair<u16, const char*> actorDescriptionData[]',
                  'struct ActorDescriptionPair { u16 first; const char* second; };\nstatic const ActorDescriptionPair actorDescriptionData[]')
        text=once(text,'static std::unordered_map<u16, const char*> actorDescriptions =\n    std::unordered_map<u16, const char*>(std::begin(actorDescriptionData), std::end(actorDescriptionData));',
                  'static std::unordered_map<u16, const char*> BuildActorDescriptions() {\n    std::unordered_map<u16, const char*> result;\n    for (size_t i=0;i<sizeof(actorDescriptionData)/sizeof(actorDescriptionData[0]);++i)\n        result.insert(std::make_pair(actorDescriptionData[i].first,actorDescriptionData[i].second));\n    return result;\n}\nstatic std::unordered_map<u16, const char*> actorDescriptions = BuildActorDescriptions();')
        text=once(text,'!nameTable.contains(name)','nameTable.find(name) == nameTable.end()')
        match=re.search(r'static ActorDBInit EnPartnerInit = \{([\s\S]+?)\n\};',text)
        if not match:raise ValueError('EnPartnerInit aggregate changed')
        text=text[:match.start()]+'static ActorDBInit EnPartnerInit('+match[1].rstrip().rstrip(',')+'\n);'+text[match.end():]
        lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text='#include "resources/runtime_support.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    return text

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());pending={}
    for name,expected in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('App service source drift '+name)
        pending[name]=transform(name,text)
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],source_sha256=lock['sources'],generated_sha256={n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()}),indent=2)+'\n')
    return [n for n in pending if n.endswith('.cpp')]

def includes():return [OUT/'generated/soh']+enhancement_includes()

def build():
    units=prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True);rows=[]
    flags=json.loads((ROOT/'scratch/game-interactor-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    flags[1:1]=['/I'+str(p) for p in includes()[:4]]
    for name in units:
        source=OUT/'generated'/name;obj=folder/(source.stem+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=result.returncode));print(name+': '+str(result.returncode),flush=True)
        if result.returncode:print('\n'.join(line for line in result.stdout.splitlines() if 'error ' in line)[:3000],flush=True)
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
