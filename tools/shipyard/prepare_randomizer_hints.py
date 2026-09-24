"""Complete stable Hint implementation on the canonical randomizer declarations."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import default_arguments,edits_apply
from cpp_ast import PARSER,walk
from platform_base import resolve as resolve_platform_base

OWN=ROOT/'platform/shipyard/randomizer-hints';OUT=ROOT/'scratch/randomizer-hints-xdk';BASE='soh/soh/Enhancements/randomizer/'
PLATFORM_BASE=resolve_platform_base(ROOT)

def value_expressions(text):
    """Preserve empty/value initialization of the newly canonical static record."""
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='init_declarator':
            value=n.child_by_field_name('value');p=n.parent;typ=p.child_by_field_name('type') if p.type=='declaration' else None
            if value and typ and value.text==b'{}' and typ.text==b'StaticHintInfo':
                eq='' if any(c.type=='=' for c in n.children) else '= '
                edits.append((value.start_byte,value.end_byte,eq+'StaticHintInfo(Shipyard::SohUI::ValueInit())'))
        if n.type not in ('new_expression','call_expression','compound_literal_expression'):continue
        typ=n.child_by_field_name('function') or n.child_by_field_name('type');args=n.child_by_field_name('arguments') or n.child_by_field_name('value')
        if typ and args and not args.named_children and typ.text==b'StaticHintInfo':
            edits.append((args.start_byte,args.end_byte,'(Shipyard::SohUI::ValueInit())'))
    return edits_apply(raw,edits)

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for name,digest in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('Hint source drift: '+name)
        texts[name]=text
    base=ROOT/'scratch/randomizer-xdk';manifest=json.loads((base/'manifest.json').read_text())
    source=(base/'generated'/BASE/'hint.cpp').read_text()
    assert hashlib.sha256(source.encode()).hexdigest()==manifest['generated'][BASE+'hint.cpp']
    assert manifest['sources'][BASE+'hint.cpp']==lock['sources'][BASE+'hint.cpp']
    assert manifest['sources'][BASE+'hint.h']==lock['sources'][BASE+'hint.h']
    assert hashlib.sha256((base/'generated'/BASE/'hint.h').read_text().encode()).hexdigest()==manifest['generated'][BASE+'hint.h']
    source=once(source,'#include "3drando/hints.hpp"','#include "3drando/HintText.h"\n#include "3drando/StaticHintInfo.h"\n#include "soh/Enhancements/randomizer/3drando/random.hpp"\n#include "trial.h"')
    source=source.replace('StaticData::staticHintInfoMap.contains(ownKey)','(StaticData::staticHintInfoMap.find(ownKey) != StaticData::staticHintInfoMap.end())')
    source=re.sub(r'(?m)^(\s*)namesTemp = \{\};',r'\1namesTemp.clear();',source)
    source=re.sub(r'(std::vector<[^;]+?> \w+) = \{\};',r'\1;',source)
    source=once(source,'nlohmann::ordered_json log = {};','nlohmann::ordered_json log;')
    source=once(source,'log["hintKey"] = hintKeys[0];','log["hintKey"] = static_cast<int>(hintKeys[0]);')
    source=once(source,'CustomMessage({ ctx->overrides[hintedCheck].GetTrickName() })','CustomMessage(ctx->overrides[hintedCheck].GetTrickName())')
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    source=lower(source.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    # Complete real static-hint record; canonical HintText remains item-owned.
    header=texts[BASE+'3drando/hints.hpp']
    declaration=next(n.text.decode() for n in walk(PARSER.parse(header.encode()).root_node) if n.type=='struct_specifier' and n.child_by_field_name('name').text==b'StaticHintInfo')+';'
    declaration=once(declaration,'StaticHintInfo() = default;','''StaticHintInfo() {}
    explicit StaticHintInfo(Shipyard::SohUI::ValueInit) : type(), hintKeys(), setting(), condition(), targetChecks(), targetItems(), hintChecks(), yourPocket(), num() {}''')
    declaration=default_arguments(declaration.replace('std::variant<bool, uint8_t>','xbox_compat::variant<bool, uint8_t>'))
    definition=next(n.text.decode() for n in walk(PARSER.parse(texts[BASE+'3drando/hints.cpp'].encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.startswith(b'StaticHintInfo::StaticHintInfo('))
    definition=definition.replace('std::variant<bool, uint8_t>','xbox_compat::variant<bool, uint8_t>')
    outputs={BASE+'hint.cpp':source,
        BASE+'3drando/StaticHintInfo.h':'#pragma once\n#include <vector>\n#include "soh/Enhancements/randomizer/randomizerTypes.h"\n#include "soh-ui/value_init.h"\n#include "xbox_compat/variant.h"\n'+declaration+'\n',
        'StaticHintInfo.cpp':'#include "soh/Enhancements/randomizer/3drando/StaticHintInfo.h"\n'+definition+'\n'}
    for name,text in outputs.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],base_projection_sha256=manifest['generated'][BASE+'hint.cpp'],generated={n:hashlib.sha256(t.encode()).hexdigest() for n,t in outputs.items()},native_runtime_executed=False),indent=2)+'\n')

def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    from prepare_randomizer_item import includes
    flags[1:1]=['/I'+str(p) for p in [OUT/'generated/soh',OUT/'generated'/BASE,PLATFORM_BASE/'sources/value_types',ROOT/'scratch/prism-xdk/generated']+includes()]
    probe=folder/'declarations.cpp'
    stable(probe,'''#include "soh/Enhancements/randomizer/3drando/StaticHintInfo.h"
#include "soh/Enhancements/randomizer/hint.h"
extern "C" const unsigned long HintABI[]={sizeof(Rando::Hint),sizeof(StaticHintInfo),sizeof(xbox_compat::variant<bool,uint8_t>)};
bool HintVariantProbe(){xbox_compat::variant<bool,uint8_t> a=true; xbox_compat::variant<bool,uint8_t> b=uint8_t(7);
StaticHintInfo value((Shipyard::SohUI::ValueInit()));return xbox_compat::get<bool>(a) && xbox_compat::get<uint8_t>(b)==7 && value.num==0;}
''')
    rows=[]
    for source in [OUT/'generated'/BASE/'hint.cpp',OUT/'generated/StaticHintInfo.cpp',probe]:
        obj=folder/(source.stem+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,production=source!=probe,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None))
        print(source.name,r.returncode)
        if r.returncode:print('\n'.join(l for l in r.stdout.splitlines() if 'error ' in l)[:5500])
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args()
    build() if a.build else prepare()
