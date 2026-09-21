"""Differential audit of real sequence, pool, CVar, and notification construction code.

The host audit excludes live-Gui scheduling, Config erase dispatch and Notification::Emit;
production retains them and compiles the complete TU. CVar storage/operations and
StringHelper operations are extracted unchanged from the pinned implementation,
with only member qualification rebased for this isolated method audit.
"""
import hashlib,json,re,runpy,struct,subprocess,unittest
from prepare_audio_collection import ROOT,OUT,OWN,BASE,prepare,build
from prepare_archives import stable
from cpp_ast import PARSER,walk

ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))

def nodes(text):return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
def select(text,name):
    found=[n.text.decode() for n in nodes(text) if n.child_by_field_name('declarator').text.decode().split('(')[0].strip()==name]
    assert len(found)==1,name
    return found[0]

def host(projected):
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    header=((OUT/'generated' if projected else ROOT)/BASE/'AudioCollection.h').read_text()
    header=header.replace('  private:','  public:')
    stable(folder/'AudioCollection.h',header)
    text=((OUT/'generated' if projected else ROOT)/BASE/'AudioCollection.cpp').read_text()
    # Keep every method except bridges (which require the application singleton)
    # and the notification service dispatch. Both remain in the production TU.
    body=text[text.index('#define SEQUENCE_MAP_ENTRY'):]
    edits=[]
    for n in nodes(body):
        name=n.child_by_field_name('declarator').text.decode().split('(')[0].strip()
        if 'AudioCollection_' in name:edits.append((n.start_byte,n.end_byte,''))
    from prepare_randomizer import edits_apply
    body=edits_apply(body.encode(),edits).replace('extern "C" ','')
    assert body.count('Ship::Context::GetInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();')==2
    body=body.replace('Ship::Context::GetInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();','// Live Gui dispatch excluded only from host method audit.')
    prefix='''#include <map>
#include <set>
#include <memory>
#include <unordered_map>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <locale>
#include <filesystem>
#include <imgui.h>
#include <libultraship/color.h>
#include "AudioCollection.h"
#include "sequence.h"
#include "sfx.h"
#include "soh/cvar_prefixes.h"
typedef int32_t s32;
'''
    from prepare_game import release_cvars
    prefix=''.join('#define '+n+' "'+v+'"\n' for n,v in release_cvars().items())+prefix
    if projected:prefix+='#include "filesystem/filesystem.h"\n#include "soh-ui/value_init.h"\n'
    cvar=(ROOT/'libultraship/include/ship/config/ConsoleVariable.h').read_text()
    a=cvar.index('typedef enum class');b=cvar.index('\nclass ConsoleVariable')
    prefix+=cvar[a:b]+'\nstd::unordered_map<std::string, std::shared_ptr<CVar>> mVariables;\n'
    cvar=(ROOT/'libultraship/src/ship/config/ConsoleVariable.cpp').read_text()
    for name,replacement in [('Get','Get'),('GetInteger','CVarGetInteger'),('SetInteger','CVarSetInteger')]:
        prefix+=select(cvar,'ConsoleVariable::'+name).replace('ConsoleVariable::'+name,replacement)+'\n'
    string=(ROOT/'libultraship/src/ship/utils/StringHelper.cpp').read_text()
    # Keep actual overload body and exact Replace behavior, avoiding unrelated APIs.
    prefix+='namespace StringHelper {\n'
    split=next(n.text.decode() for n in nodes(string) if n.child_by_field_name('declarator').text.decode().startswith('StringHelper::Split(std::string s,'))
    prefix+=split.replace('StringHelper::Split','Split')+'\n'+select(string,'StringHelper::Replace').replace('StringHelper::Replace','Replace')+'\n'+select(string,'StringHelper::Sprintf').replace('StringHelper::Sprintf','Sprintf')+'\n}\n'
    clear=select(cvar,'ConsoleVariable::ClearVariable').replace('ConsoleVariable::ClearVariable','CVarClear')
    clear=clear.replace('    std::shared_ptr<Config> conf = Context::GetInstance()->GetConfig();','')
    clear,n=re.subn(r'^\s*conf->Erase\([^\n]+\);','',clear,flags=re.M);assert n==6
    prefix+=clear+'\n'
    notice=((ROOT/'scratch/soh-menus-xdk/generated' if projected else ROOT)/'soh/soh/Notification/Notification.h').read_text()
    options=next(n.text.decode() for n in walk(PARSER.parse(notice.encode()).root_node) if n.type=='struct_specifier' and n.child_by_field_name('name').text==b'Options')
    prefix+='namespace Notification {\n'+options+';\n}\n'
    if projected:
        a=text.index('Notification::Options notification;');b=text.index('Notification::Emit(notification);',a)
        construction=text[a:b]+'return notification;'
    else:
        call=next(n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='call_expression' and n.child_by_field_name('function').text==b'Notification::Emit')
        construction='return '+call.child_by_field_name('arguments').named_children[0].text.decode()+';'
    prefix+='Notification::Options MakeSongNotification(const char* sequenceName){'+construction+'}\n'
    stable(folder/'contract.cpp',prefix+body+'\n'+(OWN/'contract.cpp').read_text())
    compiler,environment=ENV['host_environment']()
    command=[compiler,'/nologo','/std:c++20','/EHsc','/GR','/MD','/utf-8','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST',
        '/I'+str(OUT/'generated/soh'),'/I'+str(ROOT/'soh/include'),'/I'+str(ROOT/'soh'),'/I'+str(ROOT/'libultraship/include'),
        '/I'+str(ROOT/'scratch/imgui-xdk/generated'),'/I'+str(ROOT/'platform/shipyard'),folder/'contract.cpp']
    if projected:command+=[ROOT/'platform/shipyard/filesystem/filesystem.cpp',ROOT/'platform/shipyard/async/native.cpp']
    command+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    record=ENV['invoke'](command,folder,'compile',environment,success=False)
    assert record['returncode']==0,'\n'.join(l for l in (record['stdout']+record['stderr']).splitlines() if 'error ' in l)[:4500]
    return ENV['invoke']([folder/'contract.exe'],folder,'run',environment)['stdout']

class AudioCollectionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare()
    def test_native_full_unit_and_abi(self):
        build()
        from test_custom_message import coff_symbols
        abi=struct.unpack('>3I',coff_symbols(OUT/'xdk/declarations.obj')['AudioCollectionABI'][:12])
        self.assertEqual(abi,(52,68,7))
    def test_original_projected_contracts(self):
        original=host(False);projected=host(True);self.assertEqual(original,projected)
        stable(OUT/'verification.json',json.dumps(dict(table_rows=len(original.splitlines())-1,result=original.splitlines()[-1],
            table_sha256=hashlib.sha256(original.encode()).hexdigest(),native_runtime_executed=False,
            scope='Complete sequence table, map/copy/duplicate/name contracts, real pool operations and CVar bodies, replacement behavior and notification construction; live GUI dispatch, Config erase dispatch and notification emission excluded from host audit'),indent=2)+'\n')
    def test_inventory_and_retained_services(self):
        original=(ROOT/BASE/'AudioCollection.cpp').read_text();projected=(OUT/'generated'/BASE/'AudioCollection.cpp').read_text()
        names=lambda text:[n.child_by_field_name('declarator').text.decode() for n in nodes(text)]
        self.assertEqual(names(original),names(projected))
        rows=lambda text:re.findall(r'^\s*SEQUENCE_MAP_ENTRY\(.*$',text,re.M)
        self.assertEqual(rows(original),rows(projected))
        self.assertEqual(projected.count('Ship::Context::GetInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();'),2)
        self.assertIn('Notification::Emit(notification);',projected)
        self.assertIn('if (sequenceName != NULL)',projected)
    def test_repeatability(self):
        first=(OUT/'manifest.json').read_bytes();prepare();self.assertEqual(first,(OUT/'manifest.json').read_bytes())

if __name__=='__main__':unittest.main()
