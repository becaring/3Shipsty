"""Compare actual upstream/projected Item constructors and value methods."""
import hashlib,json,re,runpy,subprocess
from prepare_randomizer_item import ROOT,OUT,OWN,BASE,prepare,includes,methods
from prepare_archives import stable
from cpp_ast import PARSER,walk
RUNTIME={'ApplyEffect','UndoEffect','GetGIEntry','GetGIEntry_Copy','IsMajorItem','GetHint'}
def signature(node):return node.child_by_field_name('declarator').text.decode()
def fields(text):
    cls=next(n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='class_specifier' and n.child_by_field_name('name').text==b'Item')
    result=[]
    for n in cls.child_by_field_name('body').named_children:
        if n.type=='field_declaration' and not any(c.type=='function_declarator' for c in walk(n)):
            value=n.child_by_field_name('default_value');s=n.text.decode()
            if value:s=s[:s.rindex('=')]+';'
            result.append(re.sub(r'\s+','',s))
    return result
def main():
    prepare();original=(ROOT/(BASE+'item.cpp')).read_text(encoding='utf-8');projected=(OUT/'generated'/(BASE+'item.cpp')).read_text()
    assert [signature(n) for n in methods(original)]==[signature(n) for n in methods(projected)]
    assert fields((ROOT/(BASE+'item.h')).read_text())==fields((OUT/'generated'/(BASE+'item.h')).read_text())
    for a,b in zip(methods(original),methods(projected)):
        if signature(a).startswith('Item::Item('):continue
        assert a.text.decode().replace('[[fallthrough]]','/* fall through */')==b.text.decode()
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();records=[]
    for projected_flag in (False,True):
        folder=OUT/('host-projected' if projected_flag else 'host-original');folder.mkdir(exist_ok=True)
        header=((OUT/'generated' if projected_flag else ROOT)/(BASE+'item.h')).read_text()
        header=header.replace('#include "3drando/hints.hpp"','class HintText;').replace('  private:','  private:\n    friend struct ItemTestAccess;')
        stable(folder/'item.h',header)
        if not projected_flag:
            stable(folder/'3drando/text.hpp',(ROOT/(BASE+'3drando/text.hpp')).read_text())
            logic_header=(ROOT/(BASE+'logic.h')).read_text().replace('#include "SeedContext.h"','#include <map>\n#include <memory>\n#include "z64save.h"\n#include "z64scene.h"\nnamespace Rando { class Context; class Item; }')
            stable(folder/'logic.h',logic_header)
        else:stable(folder/'logic.h',(OUT/'generated'/(BASE+'logic.h')).read_text())
        selected=[n.text.decode() for n in methods(projected if projected_flag else original) if signature(n).split('::')[-1].split('(')[0] not in RUNTIME]
        code='#include <cctype>\n#include "item.h"\n#include "logic.h"\nnamespace Rando {\n'+'\n'.join(selected)+'\n}\n'
        logic=((OUT/'generated' if projected_flag else ROOT)/(BASE+'logic.cpp')).read_text()
        ctor=next(n.text.decode() for n in methods(logic) if signature(n)=='Logic::Logic()')
        code+='namespace Rando {\n'+ctor+'\n}\n'+(OWN/'value_contract.cpp').read_text()
        stable(folder/'contract.cpp',code)
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/Od','/DNOMINMAX','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(folder)]+['/I'+str(p) for p in includes()]+[str(folder/'contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        assert result.returncode==0,folder/'build.log'
        result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        row=dict(projected=projected_flag,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);records.append(row);assert result.returncode==0,row
    assert records[0]['stdout']==records[1]['stdout']
    rows=json.loads((OUT/'xdk/build.json').read_text())
    for row in rows:
        assert row['exit']==0
        assert row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest()
    stable(OUT/'verification.json',json.dumps(dict(host=records,complete_item_definitions=len(methods(original)),retained_item_fields=len(fields((ROOT/(BASE+'item.h')).read_text())),host_methods=len(selected),unchanged_runtime_methods=sorted(RUNTIME),runtime_services_executed=False,native=rows),indent=2)+'\n')
    print(records[0]['stdout'].strip());print('All original Item definitions/fields retained; complete native TU compiled; no substituted game services')
if __name__=='__main__':main()
