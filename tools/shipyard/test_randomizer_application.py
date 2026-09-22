"""Full-source inventory plus actual entrance/tracker table and JSON contracts."""
import collections,hashlib,json,re,runpy,struct,subprocess
from prepare_randomizer_application import ROOT,OUT,OWN,BASE,includes,prepare,kids
from prepare_archives import stable
from cpp_ast import PARSER,walk
from prepare_custom_message import literal_bytes

def functions(t):return [n for n in walk(PARSER.parse(t.encode()).root_node) if n.type=='function_definition']
def name(n):return n.child_by_field_name('declarator').text.decode().split('(')[0].strip('*& ')
def declaration(t,ident):
    for n in walk(PARSER.parse(t.encode()).root_node):
        if n.type!='init_declarator':continue
        if n.child_by_field_name('declarator').text.decode().split('[')[0]==ident:return n.parent.text.decode()
    raise AssertionError(ident)

def inventory():
    rows={}
    for p in json.loads((OWN/'sources.lock.json').read_text())['sources']:
        a=(ROOT/p).read_text(encoding='utf-8-sig');b=(OUT/'generated'/p).read_text()
        original=collections.Counter(name(n) for n in functions(a));projected=collections.Counter(name(n) for n in functions(b))
        assert not original-projected,(p,original-projected)
        def literals(t):
            t=re.sub(r'^\s*#(?:include|line)[^\n]*','',t,flags=re.M)
            return collections.Counter(literal_bytes(n.text.decode()) for n in walk(PARSER.parse(t.encode()).root_node) if n.type=='string_literal')
        # String-literal suffix lowering may expose another copy of a length
        # expression, but every original execution literal must remain.
        assert not literals(a)-literals(b),(p,literals(a)-literals(b))
        hooks=lambda t:collections.Counter(re.findall(r'\b(?:COND_HOOK|COND_ID_HOOK|COND_VB_SHOULD|REGISTER_VB_SHOULD)\s*\(\s*([\w:]+)',t))
        assert hooks(a)==hooks(b),(p,'hooks')
        rows[p]=dict(functions=sum(original.values()),hooks=sum(hooks(a).values()),literals=sum(literals(a).values()))
    return rows

def trick_name_contract():
    source=BASE+'Traps.cpp'
    def assigned_keys(text):
        return [n.child_by_field_name('left').text.decode() for n in walk(PARSER.parse(text.encode()).root_node)
                if n.type=='assignment_expression' and n.child_by_field_name('left').text.startswith(b'trickNameTable[')]
    original=assigned_keys((ROOT/source).read_text(encoding='utf-8-sig'))
    projected=(OUT/'generated'/source).read_text()
    assert len(original)>100
    assert assigned_keys(projected)==original
    assert projected.count('static __declspec(noinline) void ShipyardTrickNamesChunk')>=20
    return dict(rows=len(original),chunks=projected.count('static __declspec(noinline) void ShipyardTrickNamesChunk'))

def host(projected):
    root=OUT/'generated' if projected else ROOT
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
    text='#include "randomizer-application/support.h"\n#include "soh/Enhancements/randomizer/entrance.h"\n#include "soh/Enhancements/randomizer/randomizer_entrance_tracker.h"\n#include "soh/Enhancements/randomizer/randomizer_item_tracker.h"\n#include "soh/Enhancements/randomizer/randomizer_entrance.h"\n#include "soh/Enhancements/randomizer/randomizer_grotto.h"\n#include <cassert>\n#include <cstdio>\nusing namespace Rando;\n'
    entrance=(root/BASE/'entrance.cpp').read_text()
    text+=declaration(entrance,'NO_RETURN_ENTRANCE')+'\n'
    if projected:
        text+='\n'.join(n.text.decode() for n in functions(entrance) if name(n) in ('ShipyardEntranceLink','ShipyardEntranceOverride'))+'\n'
    text+='std::vector<EntranceInfoPair> EntranceRows(){'+declaration(entrance,'entranceShuffleTable')+'return entranceShuffleTable;}\n'
    tracker=(root/BASE/'randomizer_entrance_tracker.cpp').read_text()
    if projected:
        text+='\n'.join(n.text.decode() for n in functions(tracker) if name(n)=='ShipyardTrackerScene')+'\n'
        text+='#define SHIPYARD_SINGLE_SCENE_INFO(scene) std::vector<EntranceDataSceneAndSpawn>(1,ShipyardTrackerScene(scene,-1))\n'
    text+=declaration(tracker,'entranceData')+'\n'
    items=(root/BASE/'randomizer_item_tracker.cpp').read_text();tables=[]
    for n in walk(PARSER.parse(items.encode()).root_node):
        if n.type!='declaration':continue
        typ=n.child_by_field_name('type');init=n.child_by_field_name('declarator')
        if typ is None or typ.text!=b'std::vector<ItemTrackerDungeon>' or init is None or init.type!='init_declarator':continue
        ident=init.child_by_field_name('declarator').text.decode()
        if not ident.startswith('itemTrackerDungeons'):continue
        tables.append(ident)
        if projected:text+=next(f.text.decode() for f in functions(items) if name(f)=='_Build_'+ident)+'\n'
        text+=n.text.decode()+'\n'
    assert len(tables)==4,tables
    text+='''static unsigned long long digest=1469598103934665603ULL;
void number(long long value){for(unsigned i=0;i<8;++i){digest^=(static_cast<unsigned long long>(value)>>(i*8))&255;digest*=1099511628211ULL;}}
void string(const std::string& value){number(value.size());for(unsigned char c:value)number(c);}
void dungeon(const std::vector<ItemTrackerDungeon>& rows){number(rows.size());for(const auto& row:rows){number(row.id);number(row.items.size());for(auto item:row.items)number(item);}}
'''
    # Use actual RHS projections with explicit inputs; no application services
    # are replaced. Original JSON gets the official upstream implementation.
    plando=(root/BASE/'Plandomizer.cpp').read_text();assignments=[]
    for n in walk(PARSER.parse(plando.encode()).root_node):
        if n.type=='assignment_expression' and n.child_by_field_name('left').text.startswith(b'spoilerSave['):
            rhs=n.child_by_field_name('right')
            if not (rhs.type=='initializer_list' or b' -> nlohmann::json ' in rhs.text):continue
            assignments.append(rhs.text.decode())
    assert len(assignments)==4,len(assignments)
    substitutions={'import.hintType.c_str()':'hintType.c_str()','import.hintText.c_str()':'hintText.c_str()',
      'import.checkRewardItem.GetName().english':'itemName','import.iceTrapModel.GetName().english':'modelName',
      'import.iceTrapName.c_str()':'trickName.c_str()','import.shopPrice':'shopPrice'}
    for i,expression in enumerate(assignments):
        for a,b in substitutions.items():expression=expression.replace(a,b)
        text+='nlohmann::json Json'+str(i)+'(const std::vector<int32_t>& plandoHash,const std::string& hintType,const std::string& hintText,const std::string& itemName,const std::string& modelName,const std::string& trickName,int shopPrice){nlohmann::json result;result='+expression+';return result;}\n'
    text+='''int main(){auto entrances=EntranceRows();number(entrances.size());for(const auto& row:entrances){const EntranceLinkInfo values[]={row.first,row.second};for(const auto& v:values){number(v.type.GetValue());number(v.parentRegion);number(v.connectedRegion);number(v.index);}}
number(sizeof(entranceData)/sizeof(entranceData[0]));for(const auto& row:entranceData){number(row.index);number(row.reverseIndex);number(row.scenes.size());for(const auto& scene:row.scenes){number(scene.scene);number(scene.spawn);}string(row.source);string(row.destination);number(row.srcGroup);number(row.dstGroup);number(row.type);string(row.metaTag);number(row.oneExit);}
'''
    text+=''.join('dungeon('+t+');' for t in tables)
    text+='for(int i=-1024;i<=1024;++i){std::vector<int32_t> hash={i,-i,0,2147483647,(-2147483647-1)};'
    text+=''.join('string(Json'+str(i)+'(hash,"hint","h\\xc3\\xa9llo", "item", "model", std::string("trick\\0tail",10),i).dump());' for i in range(4))+'}\n'
    text+='printf("application tables and 8196 JSON cases: %llu\\n",digest);}\n'
    stable(folder/'contract.cpp',text)
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    jsonroots=[ROOT/'platform/shipyard/json/include',ROOT/'scratch/json-xdk/backend-generated'] if projected else [ROOT/'platform/shipyard/json/upstream/include']
    roots=jsonroots+includes();cmd=[str(compiler),'/nologo','/std:c++20','/Zc:preprocessor','/utf-8','/EHsc','/GR','/MD','/O2','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/DSPDLOG_ACTIVE_LEVEL=6']+['/I'+str(p) for p in roots]+[str(folder/'contract.cpp')]
    if projected:cmd.append(str(ROOT/'platform/shipyard/json/json.cpp'))
    cmd.append(str(ROOT/'platform/shipyard/async/native.cpp'))
    cmd+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',r.stdout+r.stderr);assert not r.returncode,folder/'build.log'
    r=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True);assert not r.returncode,(r.stdout,r.stderr)
    return dict(projected=projected,command=cmd,stdout=r.stdout,exit=r.returncode)

def main():
    prepare();before=(OUT/'manifest.json').read_bytes();prepare();assert before==(OUT/'manifest.json').read_bytes()
    data=inventory();trick_names=trick_name_contract();runs=[host(False),host(True)];assert runs[0]['stdout']==runs[1]['stdout'],runs
    native=json.loads((OUT/'xdk/build.json').read_text());assert len(native)==35
    for row in native:
        assert row['exit']==0,row['path']
        assert row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest(),row['path']
        raw=(ROOT/row['object']).read_bytes();assert struct.unpack_from('<H',raw)[0]==0x1f2
        assert row['object_sha256']==hashlib.sha256(raw).hexdigest(),row['path']
    worker=worker_contract()
    stable(OUT/'verification.json',json.dumps(dict(inventory=data,trick_names=trick_names,host=runs,native=native,worker=worker,runtime_executed=False),indent=2)+'\n')
    print('35 full randomizer application units verified; '+runs[0]['stdout'])
def worker_contract():
    folder=OUT/'worker-contract';folder.mkdir(exist_ok=True)
    source=(OUT/'generated'/BASE/'randomizer.cpp').read_text()
    join=next(n.text.decode() for n in functions(source) if name(n)=='JoinRandoGenerationThread')
    text='''#include "thread-pool/native_support.h"
#include <cassert>
#include <cstdio>
Shipyard::Async::joining_thread randoThread;
int generated=0;
volatile LONG completed=0;
'''+join+'''
int main(){
    JoinRandoGenerationThread();
    randoThread=Shipyard::Async::make_thread([](){Sleep(50);generated=1;InterlockedExchange(&completed,1);});
    JoinRandoGenerationThread();
    assert(InterlockedCompareExchange(&completed,0,0)==1);
    assert(!randoThread.joinable() && generated==0);
    JoinRandoGenerationThread();
    randoThread=Shipyard::Async::make_thread([](){generated=1;});
    JoinRandoGenerationThread();
    assert(!randoThread.joinable() && generated==0);
    puts("actual generation join: idle, unfinished, completed, repeated shutdown passed");
}
'''
    stable(folder/'contract.cpp',text)
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    cmd=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/I'+str(ROOT/'platform/shipyard'),str(folder/'contract.cpp'),str(ROOT/'platform/shipyard/async/native.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr);assert result.returncode==0,folder/'build.log'
    result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
    return dict(command=cmd,exit=result.returncode,stdout=result.stdout)

if __name__=='__main__':main()
