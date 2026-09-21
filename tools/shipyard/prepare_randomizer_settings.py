"""Reproduce the complete pinned Settings implementation for XDK."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import lower_defaults,default_arguments,edits_apply
from prepare_randomizer_item import inventory,methods
from prepare_randomizer_logic import includes as logic_includes
from prepare_custom_message import escape_literal,literal_bytes
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/randomizer-settings';OUT=ROOT/'scratch/randomizer-settings-xdk'
BASE='soh/soh/Enhancements/randomizer/'
def sha(t):return hashlib.sha256(t.encode()).hexdigest()
def list_expressions(text):
    raw=text.encode();edits=[];audit=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type!='initializer_list':continue
        elements=[n for n in node.named_children if n.type!='comment'];start,end=node.start_byte,node.end_byte
        first=elements[0] if elements else None
        kind='Vector';typ=None
        if first is None:
            if node.parent.type!='init_declarator':raise ValueError('Unmapped empty initializer '+node.parent.text.decode())
            typ=node.parent.parent.child_by_field_name('type').text.decode();replacement=typ+'()'
        elif first.type=='call_expression' and first.child_by_field_name('function').text==b'NumOpts':
            if len(elements)!=1:raise ValueError('Unexpected NumOpts list')
            typ='vector-copy';replacement=first.text.decode()
        else:
            if first.type in ('string_literal','concatenated_string'):typ='std::string'
            elif first.type=='qualified_identifier' and first.text.startswith(b'Tricks::Tag::'):typ='Tricks::Tag';kind='Set'
            elif first.type=='pointer_expression':
                if first.text.startswith(b'&mOptionGroups['):typ='OptionGroup*'
                elif first.text.startswith(b'&mOptions['):typ='Option*'
                else:raise ValueError('Unknown list pointer '+first.text.decode())
                if node.parent.type=='init_declarator':
                    declared=node.parent.parent.child_by_field_name('type').text.decode()
                    if declared=='std::vector<OptionValue*>':typ='OptionValue*'
                    else:raise ValueError('Unknown vector declaration '+declared)
            else:raise ValueError('Unknown initializer '+node.text.decode()[:100])
            parent=node.parent
            if parent.type=='compound_literal_expression':
                explicit=parent.child_by_field_name('type').text.decode()
                if explicit!='std::initializer_list<'+typ+'>':raise ValueError('Explicit list element mismatch')
                start,end=parent.start_byte,parent.end_byte
            elif parent.type=='argument_list' and parent.parent.type=='call_expression' and parent.parent.child_by_field_name('function').text.startswith(b'std::initializer_list<'):
                call=parent.parent;start,end=call.start_byte,call.end_byte
            replacement='Shipyard::RandomizerSettings::'+kind+'<'+typ+'>('+ (str(len(elements)) if kind=='Vector' else '')+')'
            replacement+=''.join('.Add('+e.text.decode()+')' for e in elements)+'.Take()'
        edits.append((start,end,replacement));audit.append(dict(type=typ,kind=kind,count=len(elements),source=raw[start:end].decode(),replacement=replacement))
    if len(audit)!=383:raise ValueError('Settings list inventory changed '+str(len(audit)))
    return edits_apply(raw,edits),audit
def project(text,header):
    text=lower_defaults(text,inventory(header),[])
    ctor=next(n for n in methods(text) if n.child_by_field_name('declarator').text==b'Settings::Settings()');body=ctor.child_by_field_name('body')
    text=edits_apply(text.encode(),[(body.start_byte+1,body.start_byte+1,'\n    Shipyard::RandomizerOptions::ValueInitializeArray(mOptions);\n    Shipyard::RandomizerOptions::ValueInitializeArray(mTrickSettings);\n')])
    text=default_arguments(text)
    text=once(text,'SPDLOG_ERROR("REPEATED TRICK NAME TAG " + trick.GetName());','SPDLOG_ERROR(spdlog::string_view_t("REPEATED TRICK NAME TAG " + trick.GetName()));')
    text=once(text,'#include "settings.h"','#include "soh/Enhancements/randomizer/settings.h"\n#include "soh/Enhancements/randomizer/SeedContext.h"\n#include "soh/Enhancements/randomizer/static_data.h"\n#include "soh/Enhancements/randomizer/3drando/random.hpp"\n#include "randomizer-settings/lists.h"\n#include "input/compiler.h"\n#include <cassert>')
    text,audit=list_expressions(text)
    # Extend the initializer's scope to the original complete if/else statement.
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='if_statement':continue
        clause=n.child_by_field_name('condition')
        init=next((c for c in clause.named_children if c.type=='init_statement'),None) if clause else None
        if init:
            value=clause.child_by_field_name('value')
            replacement='{ '+init.text.decode()+' '+raw[n.start_byte:clause.start_byte].decode()+'('+value.text.decode()+')'+raw[clause.end_byte:n.end_byte].decode()+' }'
            edits.append((n.start_byte,n.end_byte,replacement))
    text=edits_apply(raw,edits)
    syntax=runpy.run_path(str(ROOT/'platform/shipyard/input/lowering.py'))['syntax']
    text=syntax(text,set())
    return text,audit
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for name,digest in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if sha(text)!=digest:raise ValueError('Settings source drift '+name)
        texts[name]=text
    for name,digest in lock.get('dependencies',{}).items():
        if sha((ROOT/name).read_text(encoding='utf-8-sig'))!=digest:raise ValueError('Settings dependency drift '+name)
    text,audit=project(texts[BASE+'settings.cpp'],texts[BASE+'settings.h']);raw=text.encode();edits=[];literals=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='string_literal' and any(b>=128 for b in n.text):
            value=n.text.decode();escaped=escape_literal(value);edits.append((n.start_byte,n.end_byte,escaped));literals.append(dict(original=value,bytes=literal_bytes(value).hex()))
    text=edits_apply(raw,edits);stable(OUT/'generated'/(BASE+'settings.cpp'),text)
    descriptions=once(texts[BASE+'option_descriptions.cpp'],'#include "settings.h"','#include "soh/Enhancements/randomizer/settings.h"')
    raw_desc=descriptions.encode();desc_edits=[]
    for n in walk(PARSER.parse(raw_desc).root_node):
        if n.type=='string_literal' and any(b>=128 for b in n.text):desc_edits.append((n.start_byte,n.end_byte,escape_literal(n.text.decode())))
    descriptions=edits_apply(raw_desc,desc_edits);stable(OUT/'generated'/(BASE+'option_descriptions.cpp'),descriptions)
    helper_files=[ROOT/'tools/shipyard'/n for n in ('prepare_randomizer.py','prepare_randomizer_item.py','prepare_configuration.py','prepare_archives.py','prepare_custom_message.py','cpp_ast.py')]+[ROOT/'platform/shipyard/input/lowering.py',ROOT/'platform/shipyard/imgui/projection.py']
    stable(OUT/'manifest.json',json.dumps(dict(source_commit=lock['source_commit'],sources=lock['sources'],dependencies=lock.get('dependencies',{}),generated_sha256=sha(text),descriptions_sha256=sha(descriptions),original_functions=len(methods(texts[BASE+'settings.cpp'])),list_initializers=audit,literals=literals,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helper_sha256=hashlib.sha256((OWN/'lists.h').read_bytes()).hexdigest(),projection_helpers={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in helper_files}),indent=2)+'\n')
def includes():return [OUT/'generated/soh',OUT/'generated'/BASE]+logic_includes()
def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    flags[1:1]=['/I'+str(p) for p in includes()]
    rows=[]
    for name in ('settings','option_descriptions'):
        source=OUT/'generated'/(BASE+name+'.cpp');obj=folder/(name+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/(name+'.log'),r.stdout+r.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        else:print('\n'.join(s for s in (r.stdout+r.stderr).splitlines() if 'error ' in s)[:10000])
        rows.append(row);print('Full randomizer '+name+': '+str(r.returncode))
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
