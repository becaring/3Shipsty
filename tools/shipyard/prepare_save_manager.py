"""Assemble the complete modern SaveManager with canonical native storage/legacy boundaries."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_save_storage import project,methods
from prepare_randomizer import lower_defaults,default_arguments,edits_apply
from prepare_randomizer_item import inventory
from prepare_binary import strong_enum
from prepare_application import function
from prepare_randomizer_logic import includes as logic_includes
from cpp_ast import walk

OWN=ROOT/'platform/shipyard/save-manager';OUT=ROOT/'scratch/save-manager-xdk'
BASE='soh/soh/Enhancements/randomizer/'

def load_defaults(source):
    # XDK's EH backend crashes on a nontrivial default-argument temporary in
    # these nested closures (ehexcept.c:971). Give each identical temporary a
    # scoped name; its construction/value/destruction still surround one call.
    body=function(source,'SaveManager::LoadRandomizer');edits=[]
    for node in walk(body):
        if node.type!='call_expression':continue
        fn=node.child_by_field_name('function');args=node.child_by_field_name('arguments')
        if not fn.text.endswith(b'LoadData') or len(args.named_children)!=2:continue
        value=args.named_children[1].text.decode()
        typ='std::string' if '.GetTrickName().' in value else 'nlohmann::json' if value=='json' else None
        if typ is None:continue
        statement=node.parent;assert statement.type=='expression_statement'
        call=node.text.decode();call=call[:-1]+', defaultValue)'
        edits.append((statement.start_byte,statement.end_byte,'{ const '+typ+' defaultValue; '+call+'; }'))
    if len(edits)!=4:raise ValueError('Expected four nontrivial LoadRandomizer default arguments')
    return edits_apply(source.encode(),edits)

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={};generated={};defaults={}
    for name,digest in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('SaveManager input drift: '+name)
        texts[name]=text
    def emit(name,text):
        stable(OUT/'generated'/name,text);generated[name]=hashlib.sha256(text.encode()).hexdigest()
    # Hint and Trial already have full canonical declarations/default projections
    # in randomizer-xdk. Do not create second class definitions for those types.
    for stem in ['trial','hint']:
        for suffix in ['.h','.cpp']:
            stale=OUT/'generated'/(BASE+stem+suffix)
            if stale.exists():stale.unlink()
    for stem in ['entrance']:
        header=texts[BASE+stem+'.h'];members=inventory(header);defaults[stem]=members
        header=default_arguments(lower_defaults(header,members,[]))
        if stem=='entrance':
            condition=re.search(r'^typedef bool \(\*ConditionFn\)\(\);$',texts[BASE+'location_access.h'],re.M)[0]
            header=once(header,'#include "location_access.h"','#include <list>\n#include <map>\n#include <array>\n'+condition+'\nclass Region;')
            header=re.sub(r'enum class EntranceType \{(.*?)\};',lambda m:strong_enum('EntranceType',m[1]),header,flags=re.S)
            header=re.sub(r'using (Entrance\w+) = ([^;]+);',r'typedef \2 \1;',header)
            header='#include "binary/compat.h"\n'+header
        emit(BASE+stem+'.h',header)
        emit(BASE+stem+'.cpp',lower_defaults(texts[BASE+stem+'.cpp'],members,[]))
    source=project('soh/soh/SaveManager.cpp',texts['soh/soh/SaveManager.cpp'])
    source=source.replace('#include "Enhancements/','#include "soh/Enhancements/')
    # The explicit decoder already owns the raw legacy structures and unchanged
    # CopyV0Save in its namespace. Replace that contiguous old parser region with
    # the verified canonical conversion method; retain every modern method.
    start=source.index('// Functionality required to convert old saves into versioned saves')
    original=function(source,'SaveManager::ConvertFromUnversioned')
    converted=methods((ROOT/'scratch/legacy-save-xdk/generated/LegacyConversion.cpp').read_text())['ConvertFromUnversioned']
    raw=source.encode();source=(raw[:len(source[:start].encode())]+converted.encode()+raw[original.end_byte:]).decode()
    source='#include "legacy-save/format.h"\n#include "soh/Enhancements/randomizer/3drando/HintText.h"\n#include "soh/Enhancements/randomizer/static_data.h"\n#include "soh/Enhancements/randomizer/randomizer.h"\n#include "soh/Enhancements/randomizer/item_location.h"\n#include "soh/Enhancements/randomizer/item_override.h"\n'+source
    source=source.replace('#include <Windows.h>','#include <xtl.h>')
    source='#include <iomanip>\n#include "soh/Enhancements/randomizer/logic.h"\n#include "soh/Enhancements/randomizer/settings.h"\n'+source
    source='#include "save-manager/enum_traits.h"\n'+source
    source=once(source,'randoContext->overrides.emplace(static_cast<RandomizerCheck>(i),\n                                                Rando::ItemOverride(static_cast<RandomizerCheck>(i), rg));',
                'randoContext->overrides.insert(std::make_pair(static_cast<RandomizerCheck>(i),\n                                                Rando::ItemOverride(static_cast<RandomizerCheck>(i), rg)));')
    match=re.search(r'std::vector<RandomizerHint> Rando::StaticData::oldVerHintOrder(\{[\s\S]*?\});',source)
    if not match:raise ValueError('Old hint order inventory drift')
    source=source[:match.start()]+'static const RandomizerHint oldVerHintValues[]='+match[1]+';\nstd::vector<RandomizerHint> Rando::StaticData::oldVerHintOrder(oldVerHintValues,oldVerHintValues+sizeof(oldVerHintValues)/sizeof(oldVerHintValues[0]));'+source[match.end():]
    source=load_defaults(source)
    emit('soh/soh/SaveManager.cpp',source)
    emit('include/save-manager/enum_traits.h','''#pragma once
#include <nlohmann/json.hpp>
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#if defined(_XBOX)
namespace nlohmann { namespace detail {
template<> struct enum_underlying<RandomizerGet> { typedef int type; };
template<> struct enum_underlying<RandomizerHintTextKey> { typedef int type; };
}}
#endif
''')
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated=generated,
        dependency_defaults=defaults,uncompiled_dependencies=[BASE+'entrance.cpp'],
        modern_methods=len(methods(source)),legacy_decoder='scratch/legacy-save-xdk/generated/LegacyDecode.cpp',
        legacy_conversion_sha256=hashlib.sha256(converted.encode()).hexdigest()),indent=2)+'\n')

def includes():return [OUT/'generated/soh',OUT/'generated'/BASE,OUT/'generated/include',ROOT/'scratch/legacy-save-xdk/generated',
    ROOT/'scratch/save-storage-xdk/generated/soh/soh',ROOT/'scratch/save-storage-xdk/generated/include']+logic_includes()

def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    roots=includes()+[Path(f[2:]) for f in flags if f.startswith('/I')]
    roots=list(dict.fromkeys(roots));roots.sort(key=lambda p: 2 if p.is_relative_to(ROOT/'soh') else 1 if p.is_relative_to(ROOT/'scratch/game-xdk') else 0)
    flags=[f for f in flags if not f.startswith('/I')];flags[1:1]=['/I'+str(p) for p in roots]
    source=OUT/'generated/soh/soh/SaveManager.cpp';obj=folder/'SaveManager.obj';command=flags+[str(source),'/Fo'+str(obj)]
    run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),run.stdout+run.stderr)
    row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=run.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    if not run.returncode:
        assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
    stable(folder/'build.json',json.dumps([row],indent=2)+'\n');print('Complete SaveManager.cpp:',run.returncode)
    if run.returncode:print('\n'.join(s for s in (run.stdout+run.stderr).splitlines() if 'error ' in s)[:7500]);raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
