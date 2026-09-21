"""Full-header state/method audit; production builds the whole interpreter."""
import json
from pathlib import Path
import runpy
import sys
import re

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
import prepare_fast3d as projection
from cpp_ast import PARSER,walk
from prepare_archives import stable
from prepare_window import includes


def audit_source(text):
    source=text.encode();parts=[]
    for node in PARSER.parse(source).root_node.named_children:
        if node.type!='namespace_definition':continue
        for item in node.child_by_field_name('body').named_children:
            if item.type!='function_definition':continue
            declarator=item.child_by_field_name('declarator')
            names=[n.text.decode() for n in walk(declarator) if n.type=='qualified_identifier']
            name=names[0] if names else ''
            if name.startswith('GfxExecStack::') or name in ('Interpreter::Interpreter','Interpreter::~Interpreter','Interpreter::AdjustWidthHeightForScale'):
                parts.append(item.text.decode())
    if len(parts)!=12:raise ValueError('Method audit inventory drift '+str(len(parts)))
    start=text.index('class UcodeHandler {');end=text.index('\n};',start)+3
    if 'struct UcodeEntry {' in text:start=text.index('struct UcodeEntry {')
    limit=re.search(r'^(?:constexpr|const) size_t MAX_TRI_BUFFER = [0-9]+;',text,re.M).group(0)
    return '#include "fast/interpreter.h"\n#include "fast3d/value_init.h"\n#include "fast3d/math.h"\n#include <cmath>\n#include <limits>\n'+limit+'\nnamespace Fast {\n'+ '\n'.join(parts)+'\ntypedef bool (*GfxOpcodeHandlerFunc)(F3DGfx**);\n'+text[start:end]+'\n}\n'


def table_entries(text,projected):
    result={}
    for node in walk(PARSER.parse(text.encode()).root_node):
        if node.type!='declaration':continue
        prefix=b'static const UcodeEntry ' if projected else b'static constexpr UcodeHandler '
        if not node.text.startswith(prefix):continue
        decl=node.child_by_field_name('declarator')
        name=decl.child_by_field_name('declarator').text.decode().replace('Entries[]','')
        values=decl.child_by_field_name('value');rows=[]
        for entry in values.named_children:
            if entry.type=='comment':continue
            fields=[n for n in entry.named_children if n.type!='comment']
            if not projected:fields=[fields[0]]+[n for n in fields[1].named_children if n.type!='comment']
            rows.append([n.text.decode() for n in fields])
        result[name]=rows
    return result


def main():
    projection.prepare();env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler,environment=env['host_environment']();outputs=[]
    original=(ROOT/'libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
    generated=(projection.OUT/'generated/src/fast/interpreter.cpp').read_text(encoding='utf-8')
    entries=table_entries(original,False)
    if len(entries)!=6 or entries!=table_entries(generated,True):raise ValueError('Opcode names/order/function identities changed')
    for projected in (False,True):
        folder=projection.OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        stable(folder/'methods.h',audit_source(generated if projected else original))
        paths=([projection.OUT/'generated/include',ROOT/'scratch/gui-resources-xdk/generated/include']+includes()) if projected else [ROOT/'libultraship/include',ROOT/'scratch/imgui-xdk/generated',ROOT/'platform/shipyard']
        paths=[folder]+paths
        flags=['/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DNOMINMAX']+(['/DSHIPYARD_PROJECTED'] if projected else [])
        command=[compiler]+flags+['/I'+str(p) for p in paths]+[Path(__file__).with_name('test_fast3d_contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        env['invoke'](command,folder,'build',environment)
        outputs.append(env['invoke']([folder/'contract.exe'],folder,'run')['stdout'])
    if outputs[0]!=outputs[1]:raise ValueError('Original/projected state contract mismatch')
    stable(projection.OUT/'verification.json',json.dumps(dict(host_output=outputs[0],opcode_entries={n:len(r) for n,r in entries.items()},target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0])


if __name__=='__main__':main()
