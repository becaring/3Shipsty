"""Project the real OTRGlobals declaration and coupled constructor defaults.

The complete application source is retained but not yet claimed compiled. Its
build integration stays blocked until the real service/header closure is ready.
"""
import argparse
import hashlib
import json
import re
import subprocess
import struct
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import includes as enhancement_includes

OWN=ROOT/'platform/shipyard/application';OUT=ROOT/'scratch/application-xdk'
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for name,expected in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Application source drift '+name)
        texts[name]=text
    header=texts['soh/soh/OTRGlobals.h'];source=texts['soh/soh/OTRGlobals.cpp']
    defaults=re.findall(r'    ImFont\* (\w+) = nullptr;',header)
    if len(defaults)!=8:raise ValueError('OTRGlobals font default inventory changed')
    for member in defaults:header=once(header,'ImFont* '+member+' = nullptr;','ImFont* '+member+';')
    header=once(header,'#include "Enhancements/savestates.h"','class SaveStateMgr;')
    header=once(header,'#include "Enhancements/randomizer/randomizer.h"','class Randomizer;\nnamespace Rando {class Context;}\nstruct ImFont;')
    header=once(header,'#include "Enhancements/randomizer/settings.h"','// Only the forward-declared randomizer owner is used by this class declaration.')
    source=once(source,'#include "OTRGlobals.h"','#include "OTRGlobals.h"\n#include "Enhancements/savestates.h"\n#include "Enhancements/randomizer/settings.h"')
    source=once(source,'OTRGlobals::OTRGlobals() {','OTRGlobals::OTRGlobals() : '+', '.join(member+'(nullptr)' for member in defaults)+' {')
    stable(OUT/'generated/soh/soh/OTRGlobals.h',header)
    stable(OUT/'generated/soh/soh/OTRGlobals.cpp',source)
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],constructor_default_members=defaults,full_application_compiled=False),indent=2)+'\n')
def includes():return [OUT/'generated/soh']+enhancement_includes()
def probe():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    source=folder/'declaration.cpp';stable(source,'#include "soh/OTRGlobals.h"\ntypedef char owner_layout[(sizeof(OTRGlobals)==80)?1:-1];\n')
    recipe=json.loads((ROOT/'scratch/game-interactor-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    recipe.insert(1,'/I'+str(OUT/'generated/soh'));obj=folder/'declaration.obj';command=recipe+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'declaration.log',result.stdout+result.stderr)
    stable(folder/'declaration.json',json.dumps(dict(command=command,exit=result.returncode,production_application_compiled=False),indent=2)+'\n')
    if result.returncode:print(result.stdout);raise SystemExit(1)
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    print('Complete OTRGlobals class declaration: 80-byte Xenon layout; coupled full constructor projection retained, not yet compiled')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',action='store_true');args=p.parse_args()
    if args.probe:probe()
    else:prepare()
