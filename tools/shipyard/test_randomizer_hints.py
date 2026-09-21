"""Actual Hint value methods and isolated source JSON blocks, without fake services."""
import hashlib,json,re,runpy,unittest
from prepare_randomizer_hints import ROOT,OUT,OWN,BASE,prepare,build,value_expressions
from prepare_archives import stable
from cpp_ast import PARSER,walk
from test_custom_message import bounded_source

ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))
VALUES={'AddHintedLocation','GetHintedLocations','SetHintType','GetHintType','AddHintedArea','GetHintedAreas','SetDistribution','GetDistribution','IsEnabled','GetHintTextKeys','GetHintedItems','GetItemNamesChosen','GetHintTextsChosen','GetAreaTextsChosen','GetHintedTrials','GetNum','ResetVariables'}
def functions(text):return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
def signature(n):return n.child_by_field_name('declarator').text.decode()
def cls(text,name,kind='class_specifier'):
    return next(n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type==kind and n.child_by_field_name('name') and n.child_by_field_name('name').text.decode()==name)
def if_blocks(method,keys):
    return '\n'.join(n.text.decode() for n in walk(method) if n.type=='if_statement' and n.child_by_field_name('condition').text.decode() in keys)

def host(projected):
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    bundle,_,_=bounded_source(projected)
    text=((OUT/'generated' if projected else ROOT)/BASE/'hint.cpp').read_text()
    header=((ROOT/'scratch/randomizer-xdk/generated' if projected else ROOT)/BASE/'hint.h').read_text()
    enum='#include "soh/Enhancements/randomizer/randomizerTypes.h"\n#include <nlohmann/json.hpp>\n#include <variant>\n#include <type_traits>\n'
    source=enum+bundle+'\nclass HintText;\ntypedef nlohmann::ordered_json oJson;\nnamespace Rando {\n'+cls(header,'Hint').replace('  private:','  public:')+';\n'
    chosen=[]
    for n in functions(text):
        s=signature(n);method=s.split('(')[0].split('::')[-1]
        if method in VALUES or s=='Hint::Hint()' or s.startswith('Hint::Hint(RandomizerHint ownKey_, std::vector<CustomMessage> messages_)'):
            source+=n.text.decode()+'\n';chosen.append(s)
    source+='}\n'
    json_ctor=next(n for n in functions(text) if signature(n)=='Hint::Hint(RandomizerHint ownKey_, nlohmann::json json_)')
    names=['itemNamesChosen','areaNamesChosen','hintTextsChosen','hintKeys','num']
    checks={'(json_.contains("'+n+'"))' for n in names}
    # Actual parser branches including their legacy singular-key else clauses.
    source+='void ParseSelectionFields(Rando::Hint& hint,nlohmann::json json_){\n'+''.join('auto& '+n+'=hint.'+n+';\n' for n in names)+if_blocks(json_ctor,checks)+'\n}\n'
    to_json=next(n for n in functions(text) if signature(n)=='Hint::toJSON()')
    names=['itemNamesChosen','areaNamesChosen','hintKeys','hintTextsChosen','num']
    checks={'('+n+'.size() == 1)' for n in names[:-1]}|{'(num != 0)'}
    source+='oJson EmitSelectionFields(const Rando::Hint& hint){\n'+''.join('const auto& '+n+'=hint.'+n+';\n' for n in names)
    source+=('nlohmann::ordered_json log;\n' if projected else 'nlohmann::ordered_json log = {};\n')+if_blocks(to_json,checks)+'\nreturn log;}\n'
    message=next(n for n in functions(text) if signature(n)=='Hint::GetHintMessage(MessageFormat format, size_t id) const')
    branch=next(n for n in walk(message) if n.type=='if_statement' and n.child_by_field_name('condition').text==b'(hintType == HINT_TYPE_MESSAGE)')
    source+='CustomMessage MessageBranch(const Rando::Hint& hint,MessageFormat format,size_t id){const auto& messages=hint.messages;const int num=hint.num;CustomMessage hintText=CustomMessage("");\n'+branch.child_by_field_name('consequence').text.decode()+'\nstd::vector<CustomMessage> toInsert;\n'
    suffix=message.text.decode();source+=suffix[suffix.index('    hintText.InsertNames(toInsert);'):]+ '\n'
    hsource=(ROOT/BASE/'3drando/hints.hpp').read_text()
    if projected:
        source+='#include "soh/Enhancements/randomizer/3drando/StaticHintInfo.h"\n'
        source+=(OUT/'generated/StaticHintInfo.cpp').read_text().split('\n',1)[1]
        source+='#define VALUE_STATIC_INFO StaticHintInfo(Shipyard::SohUI::ValueInit())\n#define HINT_VARIANT xbox_compat::variant\n#define HINT_GET xbox_compat::get\n'
    else:
        source+=cls(hsource,'StaticHintInfo','struct_specifier')+';\n'
        ctor=next(n.text.decode() for n in functions((ROOT/BASE/'3drando/hints.cpp').read_text()) if signature(n).startswith('StaticHintInfo::StaticHintInfo('))
        source+=ctor+'\n#define VALUE_STATIC_INFO StaticHintInfo()\n#define HINT_VARIANT std::variant\n#define HINT_GET std::get\n'
    source+=(OWN/'contract.cpp').read_text();stable(folder/'contract.cpp',source)
    compiler,env=ENV['host_environment']()
    roots=[OUT/'generated/soh',ROOT/'scratch/randomizer-xdk/generated/soh',ROOT/'scratch/randomizer-xdk/generated'/BASE,ROOT/'soh/include',ROOT/'scratch/deps/spdlog/include',ROOT/'platform/shipyard',ROOT/'scratch/binary-xdk/generated/include',ROOT/'scratch/prism-xdk/generated',ROOT/'libultraship/include']
    if projected:roots=[ROOT/'platform/shipyard/json/include',ROOT/'scratch/json-xdk/backend-generated']+roots
    else:roots=[ROOT/'platform/shipyard/json/upstream/include']+roots
    cmd=[compiler,'/nologo','/std:c++20','/utf-8','/Zc:preprocessor','/EHsc','/GR','/MD','/DNOMINMAX','/D_CRT_SECURE_NO_WARNINGS','/DSPDLOG_ACTIVE_LEVEL=0']+['/I'+str(p) for p in roots]+[folder/'contract.cpp']
    if projected:cmd+=[ROOT/'platform/shipyard/json/json.cpp']
    cmd+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=ENV['invoke'](cmd,folder,'compile',env,success=False)
    assert result['returncode']==0,'\n'.join(l for l in (result['stdout']+result['stderr']).splitlines() if 'error ' in l)[:5000]
    result=ENV['invoke']([folder/'contract.exe'],folder,'run',env)
    stable(folder/'methods.json',json.dumps(chosen,indent=2)+'\n')
    return result['stdout']

class HintContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare();build()
    def test_full_native(self):
        rows=json.loads((OUT/'xdk/build.json').read_text());self.assertEqual([r['exit'] for r in rows],[0,0,0])
        for row in rows:self.assertEqual(hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest(),row['source_sha256'])
    def test_values_and_json(self):
        a=host(False);b=host(True);self.assertEqual(a,b)
        stable(OUT/'verification.json',json.dumps(dict(result=a,native_runtime_executed=False,scope='Actual Hint default/message constructors and 17 value/reset methods; extracted real selection JSON branches and message-format branch; complete StaticHintInfo constructor and variant contracts. No seed/context/hint-generation services executed.'),indent=2)+'\n')
    def test_complete_function_inventory(self):
        original=(ROOT/BASE/'hint.cpp').read_text();projected=(OUT/'generated'/BASE/'hint.cpp').read_text()
        self.assertEqual([signature(n) for n in functions(original)],[signature(n) for n in functions(projected)])
        for required in ['FillGapsInData();','SetLocationsAsHinted();','NamesChosen();','GetForCurrentLanguage','hintText.SetSingularPlural();']:
            self.assertEqual(original.count(required),projected.count(required))
    def test_repeatable(self):
        first=(OUT/'manifest.json').read_bytes();prepare();self.assertEqual(first,(OUT/'manifest.json').read_bytes())
        self.assertEqual(value_expressions('StaticHintInfo x;'),'StaticHintInfo x;')
        self.assertEqual(value_expressions('auto x=new StaticHintInfo();'),'auto x=new StaticHintInfo(Shipyard::SohUI::ValueInit());')
        self.assertEqual(value_expressions('StaticHintInfo x={};'),'StaticHintInfo x=StaticHintInfo(Shipyard::SohUI::ValueInit());')

if __name__=='__main__':unittest.main()
