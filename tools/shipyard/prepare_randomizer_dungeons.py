"""Complete pinned dungeon and trial units against canonical application classes."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import lower_defaults
from prepare_randomizer_item import inventory,methods
from prepare_randomizer_logic import includes as logic_includes
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/randomizer-dungeons';OUT=ROOT/'scratch/randomizer-dungeons-xdk'
BASE='soh/soh/Enhancements/randomizer/'
def sha(t):return hashlib.sha256(t.encode()).hexdigest()
def project(name,text,header):
    if name=='dungeon':
        header=header.replace('uint8_t vanillaKeyCount{};','uint8_t vanillaKeyCount = 0;').replace('uint8_t mqKeyCount{};','uint8_t mqKeyCount = 0;')
        text=once(text,'#include "3drando/pool_functions.hpp"','#include "randomizer-dungeons/pool_filter.h"')
        text=once(text,'std::array<DungeonInfo*, 12> dungeonList_{};','std::array<DungeonInfo*, 12> dungeonList_ = {};')
    else:
        text=once(text,'std::vector<TrialInfo*> trialList{};','std::vector<TrialInfo*> trialList;')
        text=once(text,'std::unordered_map<uint32_t, RandomizerHintTextKey> output = {};','std::unordered_map<uint32_t, RandomizerHintTextKey> output;')
    text=lower_defaults(text,inventory(header),[])
    text=re.sub(r'(~\w+\(\)) = default;',r'\1 {}',text)
    ranges=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    return '#include "resources/runtime_support.h"\n#include "z64scene.h"\n#include <algorithm>\n'+ranges(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={};outputs={}
    for name,digest in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if sha(text)!=digest:raise ValueError('Dungeon/trial source drift '+name)
        texts[name]=text
    for name,digest in lock.get('dependencies',{}).items():
        if sha((ROOT/name).read_text(encoding='utf-8-sig'))!=digest:raise ValueError('Dungeon/trial dependency drift '+name)
    for name in ('dungeon','trial'):
        text=project(name,texts[BASE+name+'.cpp'],texts[BASE+name+'.h']);stable(OUT/'generated'/(BASE+name+'.cpp'),text);outputs[name]=sha(text)
    pool=texts[BASE+'3drando/pool_functions.hpp'];nodes=[]
    for n in walk(PARSER.parse(pool.encode()).root_node):
        if n.type!='template_declaration':continue
        fn=next((c for c in n.named_children if c.type=='function_definition'),None)
        if fn is not None and fn.child_by_field_name('declarator').text.decode().split('(')[0] in ('erase_if','FilterFromPool'):
            nodes.append(n.text.decode())
    if len(nodes)!=2:raise ValueError('Actual pool filter template inventory')
    filtered='\n'.join(nodes).replace('begin(vector)','vector.begin()').replace('end(vector)','vector.end()').replace('std::vector<T> filteredPool = {};','std::vector<T> filteredPool;')
    pool_header='#pragma once\n#include <algorithm>\n#include <vector>\n#include <iterator>\n'+filtered+'\n';stable(OUT/'generated/include/randomizer-dungeons/pool_filter.h',pool_header)
    helper_files=[ROOT/'tools/shipyard'/n for n in ('prepare_randomizer.py','prepare_randomizer_item.py','prepare_configuration.py','prepare_archives.py','cpp_ast.py')]+[ROOT/'platform/shipyard/imgui/projection.py']
    stable(OUT/'manifest.json',json.dumps(dict(source_commit=lock['source_commit'],sources=lock['sources'],dependencies=lock.get('dependencies',{}),generated=outputs,pool_filter_sha256=sha(pool_header),original_functions={n:len(methods(texts[BASE+n+'.cpp'])) for n in ('dungeon','trial')},generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),projection_helpers={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in helper_files}),indent=2)+'\n')
def includes():return [OUT/'generated/soh',OUT/'generated'/BASE,OUT/'generated/include']+logic_includes()
def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2];flags[1:1]=['/I'+str(p) for p in includes()];rows=[]
    for name in ('dungeon','trial'):
        source=OUT/'generated'/(BASE+name+'.cpp');obj=folder/(name+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/(name+'.log'),r.stdout+r.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        else:print('\n'.join(s for s in (r.stdout+r.stderr).splitlines() if 'error ' in s)[:7000])
        rows.append(row);print('Full '+name+': '+str(r.returncode))
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
