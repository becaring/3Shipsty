"""Actual option constructors and class contracts, original versus projected."""
import hashlib,json,runpy,struct,subprocess,unittest
from pathlib import Path
from prepare_randomizer_options import ROOT,OUT,OWN,BASE,NAMES,prepare,build,value_expressions
from prepare_randomizer import edits_apply,inventory
from cpp_ast import PARSER,walk
from prepare_archives import stable

ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))
EXCLUDED=['Option::RenderCheckbox','Option::RenderCombobox','Option::RenderSlider','Option::AddWidget','OptionGroup::AddWidgets',
          'Option::GetOptionIndex','Option::ChangeOptions','Option::GetValueFromText','Option::SetContextIndexFromText']

def fields(text):
    result={}
    for cls in walk(PARSER.parse(text.encode()).root_node):
        if cls.type!='class_specifier' or cls.child_by_field_name('name').text.decode() not in NAMES+['Settings']:continue
        names=[]
        for node in cls.child_by_field_name('body').named_children:
            if node.type!='field_declaration' or any(c.type=='storage_class_specifier' for c in node.named_children):continue
            d=node.child_by_field_name('declarator')
            if d is not None and d.type=='field_identifier':names.append((d.text.decode(),node.child_by_field_name('type').text.decode()))
        result[cls.child_by_field_name('name').text.decode()]=names
    return result

def friend(text):
    raw=text.encode();edits=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type=='class_specifier' and node.child_by_field_name('name').text.decode() in NAMES+['Settings']:
            pos=node.child_by_field_name('body').start_byte+1;edits.append((pos,pos,'\n    friend struct Contract;\n'))
    return edits_apply(raw,edits)

def host(projected):
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
    base=OUT/'generated' if projected else ROOT
    for name in ['option.h','settings.h','tricks.h']:
        text=(base/BASE/name).read_text(encoding='utf-8')
        text=text.replace('#include "randomizerTypes.h"','#include "soh/Enhancements/randomizer/randomizerTypes.h"')
        text=text.replace('#include "soh/SohGui/MenuTypes.h"','#include "MenuTypes.h"')
        if name=='settings.h':
            text=text.replace('#include "SeedContext.h"','namespace Rando {class Context;}').replace('#include "3drando/spoiler_log.hpp"','')
        stable(folder/name,friend(text))
    source=(base/BASE/'option.cpp').read_text(encoding='utf-8');methods=[];names=[]
    for node in walk(PARSER.parse(source.encode()).root_node):
        if node.type!='function_definition':continue
        ident=node.child_by_field_name('declarator').text.decode().split('(')[0].strip()
        if ident in EXCLUDED or ident.startswith('OptionValue::'):continue
        methods.append(node.text.decode());names.append(ident)
    ctor_source=(OUT/'generated'/BASE/'SettingsConstructor.cpp' if projected else ROOT/BASE/'settings.cpp').read_text()
    ctor=[n.text.decode() for n in walk(PARSER.parse(ctor_source.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.startswith(b'Settings::Settings(')]
    assert len(ctor)==1
    text='#include "settings.h"\nnamespace Rando {\n'+'\n'.join(methods+ctor)+'\n}\n'+(OWN/'contract.cpp').read_text()
    path=folder/'contract.cpp';stable(path,text)
    compiler,env=ENV['host_environment']()
    flags=json.loads((ROOT/'scratch/soh-ui-xdk/host-projected/run.json').read_text())['command']
    includes=[f for f in flags if f.startswith('/I')]
    ui=ROOT/'scratch/soh-ui-xdk'/('generated/soh/soh/SohGui' if projected else 'host-original')
    command=[compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(folder),'/I'+str(ui),'/I'+str(OUT/'generated/soh'),'/I'+str(ROOT/'scratch/randomizer-xdk/generated'/BASE)]+includes
    if projected:command+=['/DSHIPYARD_OPTIONS_PROJECTED']
    command+=[path,'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    record=ENV['invoke'](command,folder,'compile',env,success=False)
    if record['returncode']:raise AssertionError('\n'.join(l for l in (record['stdout']+record['stderr']).splitlines() if 'error ' in l)[:5000])
    result=ENV['invoke']([folder/'contract.exe'],folder,'run',env)
    stable(folder/'scope.json',json.dumps(dict(methods=names,excluded=EXCLUDED,settings='Exact real constructor with required paired default projection',native_ui_executed=False),indent=2)+'\n')
    return result['stdout']

class OptionsContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare()
    def test_host_contracts(self):self.assertEqual(host(False),host(True))
    def test_native_full_option(self):build()
    def test_field_and_method_inventory(self):
        original=(ROOT/BASE/'option.cpp').read_text();projected=(OUT/'generated'/BASE/'option.cpp').read_text()
        def names(text):return [n.child_by_field_name('declarator').text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
        expected=[n for n in names(original) if not n.startswith('OptionValue::')]
        self.assertEqual(expected,names(projected))
        self.assertNotIn('class OptionValue',(OUT/'generated'/BASE/'option.h').read_text())
        for name in ['option.h','settings.h']:
            self.assertEqual(fields((ROOT/BASE/name).read_text()),fields((OUT/'generated'/BASE/name).read_text()))
        first=json.loads((OUT/'manifest.json').read_text())['generated'];prepare();self.assertEqual(first,json.loads((OUT/'manifest.json').read_text())['generated'])
    def test_value_expression_boundary(self):
        self.assertEqual(value_expressions('Option option;'),'Option option;')
        self.assertIn('Option(Shipyard::SohUI::ValueInit())',value_expressions('auto a=Option();'))
        self.assertIn('Option(Shipyard::SohUI::ValueInit())',value_expressions('Option a{};'))
    def test_native_layout(self):
        host(True)
        records={**fields((ROOT/BASE/'option.h').read_text()),**fields((ROOT/BASE/'settings.h').read_text())}
        labels=[];values=[]
        for cls,members in records.items():
            labels.append(cls+'.sizeof');values.append('sizeof(Rando::'+cls+')')
            for name,_ in members:
                labels.append(cls+'.'+name);values.append('offsetof(Rando::'+cls+','+name+')')
        source=(OUT/'host-projected/contract.cpp').read_text()+'\nconst uint32_t Rando::Contract::layout[] = { '+', '.join(values)+' };\n'
        folder=OUT/'xdk';folder.mkdir(exist_ok=True);path=folder/'abi.cpp';stable(path,source)
        flags=json.loads((OUT/'xdk/build.json').read_text())[0]['command'][:-2]
        flags[1:1]=['/I'+str(OUT/'host-projected'),'/DSHIPYARD_OPTIONS_PROJECTED']
        obj=folder/'abi.obj';command=flags+[str(path),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'abi.log',r.stdout+r.stderr)
        self.assertEqual(r.returncode,0,r.stdout)
        raw=obj.read_bytes();machine,section_count,_,symbols,count,optional_size,_=struct.unpack_from('<HHIIIHH',raw)
        self.assertEqual(machine,0x1f2);strings=symbols+count*18;i=0;data=None
        while i<count:
            start=symbols+i*18
            if raw[start:start+4]==b'\0'*4:
                p=strings+struct.unpack_from('<I',raw,start+4)[0];name=raw[p:raw.index(b'\0',p)].decode()
            else:name=raw[start:start+8].rstrip(b'\0').decode()
            value,section,_,storage,aux=struct.unpack_from('<IhHBB',raw,start+8)
            if name.startswith('?layout@Contract@Rando@@') and section>0:
                sec=struct.unpack_from('<8sIIIIIIHHI',raw,20+optional_size+(section-1)*40)
                start=sec[4]+value;data=struct.unpack_from('>'+str(len(labels))+'I',raw,start)
            i+=1+aux
        self.assertIsNotNone(data)
        result=dict(zip(labels,data));self.assertGreater(result['Settings.sizeof'],result['Option.sizeof'])
        stable(folder/'abi.json',json.dumps(dict(layout=result,command=command,production_unit=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
