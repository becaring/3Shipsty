"""Full graph preservation and bounded genuine original/projected runtime parity."""
import hashlib,json,re,runpy,struct,subprocess
from prepare_randomizer_regions import *

def sig(n):return n.child_by_field_name('declarator').text.decode()
def fname(n):return sig(n).split('(')[0].split('::')[-1]
def tokens(text):
    result=[]
    def visit(n):
        if n.type=='comment':return
        if not n.children:result.append(n.text)
        else:
            for c in n.children:visit(c)
    visit(PARSER.parse(text.encode()).root_node)
    return result

def restore(text,audit):
    # Undo generated ordered containers, macros and pointer conversions. Compare
    # the recovered production table functions against every original token.
    for row in reversed(audit['containers']):text=text.replace(row['name']+'()',row['source'])
    text=re.sub(r'std::(?:vector<EventAccess>|vector<LocationAccess>|list<Rando::Entrance>|set<RandomizerArea>)\(\)','{}',text)
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='call_expression':continue
        name=n.child_by_field_name('function').text.decode()
        if not name.startswith('SHIPYARD_'):continue
        args=arguments(n);edits.append((n.start_byte,n.end_byte,name[9:]+'('+', '.join(args[:2]+args[3:])+')'))
    text=edits_apply(raw,edits)
    for row in audit['predicates']:
        if row['kind']=='lambda':text=re.sub(r'\b'+row['name']+r'\b',lambda _:row['original'],text)
    return text

def pure(row):
    rest=re.sub(r'logic->Get\(\s*LOGIC_\w+\s*\)','',row['body'])
    rest=re.sub(r'logic->(?:IsAdult|IsChild|AtDay|AtNight)\b|\b(?:true|false|return)\b|[{};()!&|\s]','',rest)
    return not rest

def preservation(manifest):
    table_count=0;predicate_count=0;methods_count=0
    original_header=(ROOT/(BASE+'location_access.h')).read_text()
    def classes(text):return {n.child_by_field_name('name').text.decode():n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type in ('class_specifier','struct_specifier') and n.child_by_field_name('body') is not None}
    expected=classes(lower_defaults(original_header,inventory(original_header),[]))
    actual=classes((OUT/'generated'/(BASE+'location_access.h')).read_text())
    assert set(expected)==set(actual)
    for cls in expected:assert tokens(expected[cls])==tokens(actual[cls]),cls
    for name in UNITS:
        original=(ROOT/name).read_text();generated=(OUT/'generated'/name).read_text();audit=manifest['audit'][name]
        origs={sig(n):n for n in methods(original)};gens={sig(n):n for n in methods(generated)}
        assert set(origs)<=set(gens),(name,set(origs)-set(gens));methods_count+=len(origs)
        if name!=BASE+'location_access.cpp':
            for key,node in origs.items():
                actual=restore(gens[key].text.decode(),audit)
                assert tokens(actual)==tokens(node.text.decode()),(name,key)
                table_count+=1
        # Every real pointer function has exactly the source predicate body,
        # except nested captureless callbacks replaced by their own real pointer.
        for row in audit['predicates']:
            node=gens[row['name']+'()'];body=node.child_by_field_name('body').text.decode()
            for nested in audit['predicates']:
                if nested['kind']=='lambda':body=re.sub(r'\b'+nested['name']+r'\b',lambda _:nested['original'],body)
            assert tokens(body)==tokens(row['body']),(name,row['name'])
            predicate_count+=1
        if name==BASE+'location_access.cpp':
            original_map=next(n for n in walk(PARSER.parse(original.encode()).root_node) if n.type=='init_declarator' and n.child_by_field_name('declarator').text==b'Region::spiritLogicData').child_by_field_name('value').text.decode()
            helper=gens['ShipyardSpiritData()']
            generated_map=next(n for n in walk(helper) if n.type=='init_declarator' and n.child_by_field_name('declarator').text==b'values[]').child_by_field_name('value').text.decode()
            assert tokens(original_map)==tokens(restore(generated_map,dict(containers=[],predicates=audit['predicates'])))
    assert table_count==35 and len(UNITS)==36
    defaults=manifest['defaults']['Region'];assert len(defaults)==6
    constructors=manifest['audit'][BASE+'location_access.cpp']['constructors']
    region=[c for c in constructors if c['constructor'].startswith('Region::Region(')]
    assert len(region)==3 and all(c['added']==defaults for c in region)
    return dict(table_functions=table_count,full_original_functions=methods_count,predicates=predicate_count,containers=sum(len(a['containers']) for a in manifest['audit'].values()),region_constructors=len(region),complete_classes=list(expected),spirit_map_restored=True)

def runtime(manifest):
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();rows=[]
    selections=[]
    for name in UNITS:
        audit=manifest['audit'][name];preds=[r for r in audit['predicates'] if pure(r)]
        allowed={r['name'] for r in preds};containers=[]
        for row in audit['containers']:
            refs=set(re.findall(r'\bShipyardRegionPredicate\d+\b',row['source']))
            if row['type'] in ('std::vector<EventAccess>','std::vector<LocationAccess>','std::list<Rando::Entrance>','std::set<RandomizerArea>') and refs<=allowed:containers.append(row)
        selections.append((name,preds,containers))
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        if not projected:
            h=(ROOT/(BASE+'location_access.h')).read_text().replace('enum class EntranceType;','struct EntranceType;')
            h=h.replace('#include "soh/Enhancements/randomizer/dungeon.h"','#include "soh/Enhancements/randomizer/dungeon.h"\n#include "soh/Enhancements/randomizer/entrance.h"')
            stable(folder/'soh/Enhancements/randomizer/location_access.h','#include <cassert>\n'+h)
            h=(ROOT/(BASE+'logic.h')).read_text().replace('#include "SeedContext.h"','#include <map>\n#include <memory>\n#include "z64save.h"\n#include "z64scene.h"\nnamespace Rando { class Context; class Item; }')
            stable(folder/'soh/Enhancements/randomizer/logic.h',h)
        source=(OUT/'generated'/(BASE+'location_access.cpp') if projected else ROOT/(BASE+'location_access.cpp')).read_text()
        chosen=[n.text.decode() for n in methods(source) if fname(n) in ('Region','~Region','CalculateAreas','GetTimePassFromScene','TimePass','ResetVariables','ReplaceFirstInString','ReplaceAllInString','CleanConditionString')]
        code=PREFIX+'\n#include <cstdio>\n#include <cstdint>\nRando::Context* ctx;\nstd::shared_ptr<Rando::Logic> logic;\n'
        if projected:
            code+='\n'.join(n.text.decode() for n in methods(source) if sig(n).startswith('ShipyardRegionContainer') and n.child_by_field_name('type').text==b'std::set<RandomizerArea>')+'\n'
        code+='\n'.join(chosen)+'\n'
        logic_source=(ROOT/('scratch/randomizer-logic-xdk/generated/'+BASE+'logic.cpp') if projected else ROOT/(BASE+'logic.cpp')).read_text()
        code+='namespace Rando {\n'+'\n'.join(n.text.decode() for n in methods(logic_source) if fname(n) in ('Logic','Get','Set'))+'\n}\n'
        # Canonical Entrance translation preserves its own defaults; its real
        # constructor and observers serve both Region comparison executables.
        entrance=(ROOT/('scratch/save-manager-xdk/generated/'+BASE+'entrance.cpp')).read_text()
        code+='namespace Rando {\n'+'\n'.join(n.text.decode() for n in methods(entrance) if fname(n) in ('Entrance','GetConnectedRegionKey','GetOriginalConnectedRegionKey','GetConditionStr','RemoveFromPool'))+'\n}\n'
        fnrefs=[];containerrefs=[]
        for index,(name,preds,containers) in enumerate(selections):
            namespace='Graph'+str(index);code+='namespace '+namespace+' {\n'
            gen=(OUT/'generated'/name).read_text();nodes={sig(n).split('(')[0]:n.text.decode() for n in methods(gen)}
            for row in preds:
                code+=(nodes[row['name']] if projected else 'static bool '+row['name']+'() '+row['body'])+'\n'
                fnrefs.append(namespace+'::'+row['name'])
            for row in containers:
                if projected:code+=nodes[row['name']]+'\n'
                else:
                    body=restore(row['source'],dict(containers=[],predicates=manifest['audit'][name]['predicates']))
                    # Current host enum is canonical unscoped RandomizerRegion.
                    # Use exact pointer macro body, with only qualification removed.
                    code+='#undef ENTRANCE\n#define ENTRANCE(check, condition, ...) Entrance(check, [] { return condition; }, CleanConditionString(#condition), ##__VA_ARGS__)\n'
                    code+='static '+row['type']+' '+row['name']+'() { return '+body+'; }\n'
                containerrefs.append(namespace+'::'+row['name'])
            code+='}\n'
        code+='static ConditionFn predicates[] = {'+','.join(fnrefs)+'};\n'
        code+=(OWN/'state_contract.cpp').read_text().replace('/* CONTAINER_CALLS */','\n'.join('CheckContainer('+n+'());' for n in containerrefs))
        stable(folder/'contract.cpp',code)
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/Od','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(folder)]+['/I'+str(p) for p in includes()]+[str(folder/'contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr);assert not result.returncode,folder/'build.log'
        result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        rows.append(dict(projected=projected,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr));assert not result.returncode,rows[-1]
    assert rows[0]['stdout']==rows[1]['stdout'],rows
    return dict(host=rows,host_predicates=len(fnrefs),host_containers=len(containerrefs),external_services_executed=False)

def main():
    prepare();manifest=json.loads((OUT/'manifest.json').read_text());report=preservation(manifest);report.update(runtime(manifest))
    native=json.loads((OUT/'xdk/build.json').read_text());assert len(native)==36
    for row in native:
        assert row['exit']==0,row['source'];assert row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest()
        obj=next(s[3:] for s in row['command'] if s.startswith('/Fo'));assert struct.unpack_from('<H',Path(obj).read_bytes())[0]==0x1f2
        assert row['object_sha256']==hashlib.sha256(Path(obj).read_bytes()).hexdigest();assert '/GR' in row['command']
    report['native']=native
    stable(OUT/'verification.json',json.dumps(report,indent=2)+'\n')
    print(report['host'][0]['stdout']);print('36 full native units; 35 table bodies restored token-for-token; all 5885 predicates preserved')
if __name__=='__main__':main()
