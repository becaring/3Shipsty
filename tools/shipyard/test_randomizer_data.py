"""Original/projected full Location factories and StaticData table differential."""
import hashlib,json,re,runpy,unittest
from prepare_randomizer_data import ROOT,OUT,OWN,BASE,prepare,build
from prepare_archives import stable
from cpp_ast import PARSER,walk
from test_custom_message import bounded_source

ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))
def functions(text):return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
def sig(n):return n.child_by_field_name('declarator').text.decode()
def name(n):return sig(n).split('(')[0].strip()
def cls(text,name):return next(n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type in ('class_specifier','struct_specifier') and n.child_by_field_name('name') and n.child_by_field_name('name').text.decode()==name)
def strip_includes(text):return re.sub(r'^#include[^\n]*\n','',text,flags=re.M)

def host(projected):
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    bundle,_,_=bounded_source(projected)
    source='#include <tuple>\n#include <variant>\n#include <iostream>\n#include <sstream>\n#include "soh/Enhancements/randomizer/option.h"\n#include "z64actor_enum.h"\n#include "z64scene.h"\n'+bundle+'\n'
    spoiler=(ROOT/BASE/'3drando/spoiler_log.hpp').read_text();source+=next(n.text.decode() for n in PARSER.parse(spoiler.encode()).root_node.named_children if n.type=='type_definition' and b'SpoilerCollectionCheckType' in n.text)+'\n'
    hints=((ROOT/'scratch/randomizer-item-xdk/generated'/BASE/'3drando/HintText.h') if projected else ROOT/BASE/'3drando/hints.hpp').read_text()
    source+=cls(hints,'HintText')+';\n'
    hint_methods=(ROOT/BASE/'3drando/hints.cpp').read_text()
    for n in functions(hint_methods):
        if name(n) in ['HintText::HintText','& HintText::GetClear']:source+=n.text.decode()+'\n'
    if projected:
        source+='#include "soh/Enhancements/randomizer/3drando/StaticHintInfo.h"\n'
        source+=strip_includes((ROOT/'scratch/randomizer-hints-xdk/generated/StaticHintInfo.cpp').read_text())
        source+='#define VARIANT_GET xbox_compat::get\n'
    else:
        source+=cls((ROOT/BASE/'3drando/hints.hpp').read_text(),'StaticHintInfo')+';\n'
        source+=next(n.text.decode() for n in functions(hint_methods) if name(n)=='StaticHintInfo::StaticHintInfo')+'\n#define VARIANT_GET std::get\n'
    util=(ROOT/'soh/soh/util.cpp').read_text()
    for n in PARSER.parse(util.encode()).root_node.named_children:
        if n.type=='declaration' and (b' rcareaPrefixes =' in n.text or n.text.startswith(b'std::string invalidString =')):source+=n.text.decode()+'\n'
    source+='namespace SohUtils { const std::string& GetRandomizerCheckAreaPrefix(int32_t rcarea); }\n'
    source+=next(n.text.decode() for n in functions(util) if 'SohUtils::GetRandomizerCheckAreaPrefix(' in sig(n))+'\n'
    location_header=((ROOT/'scratch/randomizer-item-xdk/generated' if projected else ROOT)/BASE/'location.h').read_text()
    source+='namespace Rando {\n'+cls(location_header,'SpoilerCollectionCheck')+';\n'+cls(location_header,'Location').replace('  private:','  public:')+';\nclass Item;\n'
    static_header=(ROOT/'scratch/randomizer-item-xdk/generated'/BASE/'static_data.h').read_text();source+=cls(static_header,'StaticData')+';\n}\n'
    # These already-tested canonical Option dependencies are real implementations,
    # shared on both sides; this audit changes only Location/data and message source.
    option=(ROOT/'scratch/randomizer-options-xdk/generated'/BASE/'option.cpp').read_text()
    source+='namespace Rando {\n'
    for n in functions(option):
        if name(n) in ['Option::Option','LocationOption::LocationOption','Option::PopulateTextToNum','Option::GetOptionCount']:source+=n.text.decode()+'\n'
    source+='}\n'
    location=((OUT/'generated' if projected else ROOT)/BASE/'location.cpp').read_text();static=((OUT/'generated' if projected else ROOT)/BASE/'static_data.cpp').read_text()
    source+=strip_includes(location)+'\n'+strip_includes(static)+'\n'+(OWN/'contract.cpp').read_text()
    calls=[]
    for n in functions(location):
        typ=n.child_by_field_name('type')
        if typ is None or typ.text!=b'Rando::Location':continue
        params=n.child_by_field_name('declarator').child_by_field_name('parameters');args=[]
        for p in params.named_children:
            if p.type not in ('parameter_declaration','optional_parameter_declaration'):continue
            t=p.child_by_field_name('type').text.decode()
            expressions={'RandomizerCheck':'RC_UNKNOWN_CHECK','RandomizerCheckQuest':'RCQUEST_BOTH','RandomizerCheckType':'RCTYPE_STANDARD','RandomizerCheckArea':'RCAREA_KOKIRI_FOREST','ActorID':'ACTOR_EN_ITEM00','SceneID':'SCENE_DEKU_TREE','std::string':'std::string("Test Chest")','RandomizerHintTextKey':'RHT_NONE','RandomizerGet':'RG_NONE','SpoilerCollectionCheck':'Rando::SpoilerCollectionCheck::Chest(2,3)','bool':'true','RandomizerInf':'RandomizerInf(3)'}
            args.append(expressions.get(t,t+'(3)'))
        calls.append('ShowLocation('+json.dumps(name(n))+','+name(n)+'('+','.join(args)+'));')
    prints=[]
    for table in json.loads((OUT/'manifest.json').read_text())['tables']:
        ident=table['name'];kind='ShowVector' if table['type'].startswith('std::vector<') else 'ShowMap'
        prints.append(kind+'('+json.dumps(ident)+',Rando::'+ident+');')
    source=source.replace('SHIPYARD_DATA_FACTORIES','\n'.join(calls)).replace('SHIPYARD_DATA_TABLES','\n'.join(prints))
    stable(folder/'contract.cpp',source)
    compiler,env=ENV['host_environment']();flags=json.loads((OUT/'xdk/build.json').read_text())[0]['command']
    includes=[p for p in flags if p.startswith('/I') and 'Microsoft Xbox 360 SDK' not in p]
    command=[compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t',
        '/I'+str(ROOT/'scratch/deps/spdlog/include')]+includes+[folder/'contract.cpp','/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=ENV['invoke'](command,folder,'compile',env,success=False)
    assert result['returncode']==0,'\n'.join(l for l in (result['stdout']+result['stderr']).splitlines() if 'error ' in l)[:5000]
    result=ENV['invoke']([folder/'contract.exe'],folder,'run',env,success=False)
    assert result['returncode']==0,result['stderr']+'\n'+result['stdout'][-350:]
    return result['stdout'],len(calls)

class DataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare();build()
    def test_native_complete_units(self):
        rows=json.loads((OUT/'xdk/build.json').read_text());self.assertEqual([r['exit'] for r in rows],[0,0])
        for row in rows:self.assertEqual(hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest(),row['source_sha256'])
    def test_actual_tables_factories_and_translations(self):
        a,count=host(False);b,other=host(True);self.assertEqual(a,b);self.assertEqual(count,other)
        stable(OUT/'verification.json',json.dumps(dict(factory_overloads=count,output_lines=len(a.splitlines()),stdout_sha256=hashlib.sha256(a.encode()).hexdigest(),scope='Complete real Location factories, actual StaticData tables/translation methods and real dependency constructor/text methods; no game/service stubs',native_runtime_executed=False),indent=2)+'\n')
    def test_function_inventory(self):
        for file in ['location.cpp','static_data.cpp']:
            original=(ROOT/BASE/file).read_text();projected=(OUT/'generated'/BASE/file).read_text()
            self.assertEqual([sig(n) for n in functions(original)],[sig(n) for n in functions(projected) if not name(n).startswith('Build_')])
    def test_repeatability(self):
        first=(OUT/'manifest.json').read_bytes();prepare();self.assertEqual(first,(OUT/'manifest.json').read_bytes())

if __name__=='__main__':unittest.main()
