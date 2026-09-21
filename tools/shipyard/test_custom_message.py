"""Full custom message source and literal audit with bounded real method execution."""
import hashlib,json,re,runpy,struct,subprocess,unittest
from pathlib import Path
from prepare_custom_message import ROOT,OWN,OUT,RANDOMIZER_OUT,CUSTOM,PARSER,walk,functions,prepare,sha
ENV=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))
EXCLUDED=['CustomMessage::LoadVanillaMessageTableEntry','CustomMessage::GetForCurrentLanguage','CustomMessage::LoadIntoFont']

def class_node(text,name):return next(n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='class_specifier' and n.child_by_field_name('name').text.decode()==name)
def bounded_source(projected):
    cpp=((OUT/'generated/CustomMessageManager.cpp') if projected else ROOT/(CUSTOM+'.cpp')).read_text(encoding='utf-8-sig')
    header=((RANDOMIZER_OUT/'generated'/(CUSTOM+'.h')) if projected else ROOT/(CUSTOM+'.h')).read_text(encoding='utf-8-sig')
    text_path='soh/soh/Enhancements/randomizer/3drando/text.hpp'
    text_header=((RANDOMIZER_OUT/'generated'/text_path) if projected else ROOT/text_path).read_text(encoding='utf-8-sig')
    prelude='''#include <string>
#include <vector>
#include <unordered_map>
#include <map>
#include <memory>
#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <exception>
#include <cstdio>
#include <cstring>
#include <cctype>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/ostream_sink.h>
#include <z64item.h>
#include <message_data_textbox_types.h>
'''
    z64=(ROOT/'soh/include/z64.h').read_text(encoding='utf-8-sig')
    prelude+=re.search(r'typedef enum \{\s*LANGUAGE_ENG,.*?\} Language;',z64,re.S)[0]+'\n'+re.search(r'#define TODO_TRANSLATE[^\n]*',z64)[0]+'\n'
    prelude+=re.search(r'typedef enum \{\s*MF_FORMATTED,.*?\} MessageFormat;',header,re.S)[0]+'\n'
    prelude+='\n'.join(re.findall(r'^#define (?:PLURAL|SINGULAR)[^\n]*',text_header,re.M))+'\n'
    prelude+='using namespace std::literals::string_literals;\n'+'\n'.join(re.findall(r'^#define (?:QM_\w+|HS_HORSE_ARCHERY)[^\n]*',header,re.M))+'\n'
    if projected:
        prelude+='#include "randomizer/support.h"\n#include "custom-message/support.h"\n'
        wrapper=(OUT/'generated/include/CustomMessageManager.h').read_text()
        prelude+=wrapper[wrapper.index('#undef QM_WHITE'):]
    prelude+='#define private public\n'+class_node(text_header,'Text').text.decode()+';\n'
    for cls in ['CustomMessage','CustomMessageManager','MessageNotFoundException']:
        if cls=='CustomMessageManager':prelude+=re.search(r'typedef std::unordered_map<uint16_t, CustomMessage> CustomMessageTable;',header)[0]+'\n'
        prelude+=class_node(header,cls).text.decode()+';\n'
    prelude+='#undef private\n'
    root=PARSER.parse(cpp.encode()).root_node
    tables=[]
    for n in root.named_children:
        if n.type=='declaration' and n.text.startswith(b'static '):tables.append(n.text.decode())
        elif n.type=='function_definition' and n.child_by_field_name('declarator').text.decode().endswith('_initialize()'):tables.append(n.text.decode())
    selected=[n for n in functions(cpp) if not any(name+'(' in n.child_by_field_name('declarator').text.decode() for name in EXCLUDED) and not n.child_by_field_name('declarator').text.decode().endswith('_initialize()')]
    bodies='\n'.join(tables)+'\n'+'\n'.join(n.text.decode() for n in selected)
    return prelude+bodies, [n.child_by_field_name('declarator').text.decode() for n in selected],header

def host(projected):
    folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    bundle,methods,header=bounded_source(projected)
    manifest=json.loads((OUT/'manifest.json').read_text())
    prints=[]
    for i,record in enumerate(manifest['literals']):
        # Compile original spelling on the original side; compare independent
        # host compiler-decoded bytes to the emitted target octal literals.
        literal=record['original'] if not projected else re.sub(r'^std::string\((".*"),.*$',r'\1',record['projected'])
        prints.append('show("literal-'+str(i)+'",std::string('+literal+', sizeof('+literal+')-1));')
    layout=[]
    for cls in ['CustomMessage','CustomMessageManager','MessageNotFoundException']:
        layout.append('std::cout<<"layout-size-'+cls+':"<<sizeof('+cls+')<<"\\n";')
        for n in class_node(header,cls).child_by_field_name('body').named_children:
            if n.type!='field_declaration':continue
            d=n.child_by_field_name('declarator')
            if d is not None and d.type=='field_identifier':layout.append('std::cout<<"layout-offset-'+cls+'.'+d.text.decode()+':"<<offsetof('+cls+','+d.text.decode()+')<<"\\n";')
    driver=(OWN/'contract.cpp').read_text().replace('SHIPYARD_MESSAGE_LITERALS','\n'.join(prints)).replace('SHIPYARD_MESSAGE_LAYOUT','\n'.join(layout))
    source=folder/'contract.cpp';source.write_text(bundle+'\n'+driver,encoding='utf-8',newline='\n')
    compiler,env=ENV['host_environment']();incs=[ROOT/'soh/include',ROOT/'scratch/deps/spdlog/include',ROOT/'platform/shipyard',ROOT/'scratch/binary-xdk/generated/include']
    cmd=[compiler,'/nologo','/std:c++20','/utf-8','/Zc:preprocessor','/EHsc','/GR','/MD','/D_CRT_SECURE_NO_WARNINGS','/DSPDLOG_ACTIVE_LEVEL=0']+['/I'+str(p) for p in incs]+[source,'/Fe'+str(folder/'contract.exe'),'/Fo'+str(folder/'contract.obj')]
    ENV['invoke'](cmd,folder,'compile',env)
    record=ENV['invoke']([folder/'contract.exe'],folder,'run',env)
    (folder/'methods.json').write_text(json.dumps(methods,indent=2)+'\n')
    return record['stdout']

def coff_symbols(path):
    raw=path.read_bytes();machine,count,_,symbols,n,optional,_=struct.unpack_from('<HHIIIHH',raw);assert machine==0x1f2
    strings=symbols+n*18;out={};i=0
    while i<n:
        off=symbols+i*18
        if raw[off:off+4]==b'\0'*4:
            start=strings+struct.unpack_from('<I',raw,off+4)[0];name=raw[start:raw.index(b'\0',start)].decode()
        else:name=raw[off:off+8].rstrip(b'\0').decode()
        value,section,_,_,aux=struct.unpack_from('<IhHBB',raw,off+8)
        if section>0:
            header=20+optional+(section-1)*40;size,pointer=struct.unpack_from('<II',raw,header+16);out[name]=raw[pointer+value:pointer+size]
        i+=1+aux
    return out

class CustomMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.manifest=prepare()
    def test_entire_function_inventory_preserved(self):
        generated=(OUT/'generated/CustomMessageManager.cpp').read_text()
        actual=[n.child_by_field_name('declarator').text.decode() for n in functions(generated) if not n.child_by_field_name('declarator').text.decode().endswith('_initialize()')]
        self.assertEqual(actual,self.manifest['functions'])
        self.assertEqual(len(self.manifest['tables']),5)
        self.assertEqual(self.manifest['call_boundaries'],{'literal_to_rvalue':7,'dynamic_log_view':2,'map_insert':2})
    def test_host_original_projected(self):
        before=host(False);after=host(True);self.assertEqual(before,after)
        (OUT/'differential.json').write_text(json.dumps(dict(equal=True,stdout_sha256=sha(before.encode()),lines=len(before.splitlines()),methods=len(json.loads((OUT/'host-original/methods.json').read_text())),excluded_service_methods=EXCLUDED),indent=2)+'\n')
    def test_native_full_unit(self):
        records=json.loads((OUT/'xdk/build.json').read_text());self.assertEqual([r['exit'] for r in records],[0,0])
        for name,r in zip(['CustomMessageManager','literal_probe'],records):
            self.assertEqual(sha((OUT/'xdk'/(name+'.obj')).read_bytes()),r['object_sha256'])
            self.assertEqual(sha((OUT/'generated'/(name+'.cpp')).read_bytes()),r['source_sha256'])
        symbols=coff_symbols(OUT/'xdk/CustomMessageManager.obj')
        for name in EXCLUDED:
            self.assertTrue(any('?'+name.split('::')[1]+'@CustomMessage@' in key for key in symbols),name)
    def test_native_literal_bytes_against_original_host(self):
        log=json.loads((OUT/'host-original/run.json').read_text())['stdout'];expected={}
        for line in log.splitlines():
            if line.startswith('literal-'):
                name,length,encoded=line.split(':');expected[int(name[8:])]=bytes.fromhex(encoded)
        self.assertEqual(len(expected),len(self.manifest['literals']))
        symbols=coff_symbols(OUT/'xdk/literal_probe.obj')
        for i,value in expected.items():
            self.assertEqual(value.hex(),self.manifest['literals'][i]['bytes'])
            self.assertEqual(symbols['shipyard_message_literal_'+str(i)][:len(value)+1],value+b'\0',i)
    def test_provider_header_remains_canonical(self):
        wrapper=(OUT/'generated/include/CustomMessageManager.h').read_text();self.assertNotIn('class CustomMessage',wrapper)
        for suffix in ['.h','.cpp']:
            path=RANDOMIZER_OUT/'generated'/(CUSTOM+suffix)
            self.assertEqual(sha(path.read_text(encoding='utf-8-sig').encode()),self.manifest['provider_inputs'][CUSTOM+suffix])
    def test_source_matches_pinned_commit(self):
        for rel in self.manifest['sources']:
            original=subprocess.run(['git','show',self.manifest['source_commit']+':'+rel],cwd=ROOT,capture_output=True,check=True).stdout
            self.assertEqual(original.replace(b'\r\n',b'\n'),(ROOT/rel).read_bytes().replace(b'\r\n',b'\n'),rel)
if __name__=='__main__':unittest.main()

