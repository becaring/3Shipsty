"""Generate the real current hook registry/dispatch for the XDK C++ frontend."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import syntax
from cpp_ast import PARSER,walk

OWN=ROOT/'platform/shipyard/game-interactor'
OUT=ROOT/'scratch/game-interactor-xdk'
BASE='soh/soh/Enhancements/game-interactor/'

def call_sites(text,name):
    raw=text.encode();edits=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type!='call_expression':continue
        function=node.child_by_field_name('function');args=node.child_by_field_name('arguments')
        match=re.search(rb'\b(RegisterGameHook(?:ForID|ForPtr|ForFilter)?)<',function.text)
        if not match:continue
        count=1 if match[1]==b'RegisterGameHook' else 2
        if len(args.named_children)==count+1:continue # An explicit original location remains authoritative.
        if len(args.named_children)!=count:raise ValueError('Hook registration call arity changed')
        location=', Shipyard::SourceLocation('+json.dumps((ROOT/name).as_posix())+','+str(node.start_point.row+1)+','+str(node.start_point.column+1)+',__FUNCSIG__)'
        edits.append((args.end_byte-1,args.end_byte-1,location.encode()))
    for a,b,value in sorted(edits,reverse=True):raw=raw[:a]+value+raw[b:]
    return raw.decode()

def header(text,max_arity):
    text=once(text,'#include "libultraship/libultraship.h"','#include <libultraship/bridge.h>\n#include <string>')
    text=once(text,'#include <version>','#include "game-interactor/source_location.h"\n#define __cpp_lib_source_location 201907L')
    text=once(text,'#include <source_location>','// Source locations are supplied by the deterministic call-site projection.')
    text=text.replace('std::source_location','Shipyard::SourceLocation').replace(' = Shipyard::SourceLocation::current()','')
    text=once(text,'HOOK_ID nextHookId = 1;','GameInteractor() : nextHookId(1) {}\n    HOOK_ID nextHookId;')
    text=once(text,'struct HookInfo {','struct HookInfo {\n    HookInfo() : calls(0), registering() {}\n    HookInfo(uint32_t c,const HookRegisteringInfo& r) : calls(c), registering(r) {}')
    text=text.replace('HookRegisteringInfo{ location.file_name(), location.line(), location.column(), location.function_name(), type }','HookRegisteringInfo(location.file_name(), location.line(), location.column(), location.function_name(), type)')
    text=text.replace('HookRegisteringInfo{}','HookRegisteringInfo()')
    text=once(text,'        })\n','        }, SHIPYARD_CURRENT_HOOK_LOCATION)\n')
    text=text.replace('>(body);','>(body, SHIPYARD_CURRENT_HOOK_LOCATION);').replace('>(id, body);','>(id, body, SHIPYARD_CURRENT_HOOK_LOCATION);')
    text=re.sub(r'HookInfo\{ 0, (GET_CURRENT_REGISTERING_INFO\(\w+\)) \}',r'HookInfo(0, \1)',text)
    # Inline template variables become ordinary template definitions in the same
    # generated header. Linker COMDAT ownership remains one instance per H.
    definitions=[]
    for cls in ('RegisteredGameHooks','HooksToUnregister'):
        match=re.search(r'template <typename H> struct '+cls+r' \{(.*?)\n    \};',text,re.S)
        members=re.findall(r'inline static (.*?) (\w+);',match[1])
        for typ,name in members:
            definitions.append('template<typename H> '+typ+' GameInteractor::'+cls+'<H>::'+name+';')
    if len(definitions)!=9:raise ValueError('Hook static storage inventory changed')
    text=text.replace('inline static ','static ')
    text=once(text,'#undef GET_CURRENT_REGISTERING_INFO','\n'.join(definitions)+'\n#undef GET_CURRENT_REGISTERING_INFO')
    # Instantiate the same forwarding algorithm for every arity in the exact
    # hook table, preserving lvalue/rvalue categories. No alternate dispatcher.
    raw=text.encode();edits=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type!='template_declaration' or b'typename... Args' not in node.text:continue
        body=node.text.decode();copies=[]
        for arity in range(max_arity+1):
            params=', '.join('typename A'+str(i) for i in range(arity))
            copy=body.replace('typename H, typename... Args','typename H'+(', '+params if params else ''))
            copy=copy.replace('Args&&... args',', '.join('A'+str(i)+'&& a'+str(i) for i in range(arity)))
            copy=copy.replace('std::forward<Args>(args)...',', '.join('std::forward<A'+str(i)+'>(a'+str(i)+')' for i in range(arity)))
            copy=copy.replace('int32_t id, )','int32_t id)').replace('uintptr_t ptr, )','uintptr_t ptr)')
            copies.append(copy)
        edits.append((node.start_byte,node.end_byte,'\n'.join(copies).encode()))
    if len(edits)!=4:raise ValueError('Hook forwarding algorithm inventory changed')
    for a,b,replacement in sorted(edits,reverse=True):raw=raw[:a]+replacement+raw[b:]
    text=raw.decode()
    for name,result in [('ActorNotPlayer','bool'),('SActorNotPlayer','bool'),('ActorMatchIdAndParams','std::function<bool(Actor*)>'),('SActorMatchIdAndParams','std::function<bool(Actor*,bool*)>')]:
        text=once(text,'static auto '+name+'(', 'static '+result+' '+name+'(')
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    return '#include "resources/runtime_support.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={}
    for name,expected in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('GameInteractor source drift '+name)
        texts[name]=text
    table=texts[BASE+'GameInteractor_HookTable.h']
    args=re.findall(r'^DEFINE_HOOK\(\w+, \((.*?)\)\);',table,re.M)
    arity=max(0 if not arg.strip() else len(arg.split(',')) for arg in args)
    for name,text in texts.items():
        if name.endswith('/GameInteractor.h'):text=header(text,arity)
        elif name.endswith('.cpp'):text=call_sites(text,name)
        if name.endswith('/GameInteractionEffect.cpp'):
            text=once(text,'#include "soh/Enhancements/cosmetics/CosmeticsEditor.h"','#include "soh/Enhancements/cosmetics/CosmeticsEditorActions.h"')
        if name.endswith('/GameInteractor_RawAction.cpp'):
            text=once(text,'#include "soh/Enhancements/debugger/colViewer.h"','#include "soh/Enhancements/debugger/colViewerTypes.h"')
        text=syntax(text)
        stable(OUT/'generated'/name,text)
    # The game-effect caller needs the real action declaration and collision
    # enum, not the editor classes. Extract their single canonical declarations
    # and include them from the retained complete editor headers as well.
    cosmetic='soh/soh/Enhancements/cosmetics/CosmeticsEditor.h'
    declaration='void CosmeticsEditor_RandomizeAll();'
    actions=cosmetic.replace('CosmeticsEditor.h','CosmeticsEditorActions.h')
    stable(OUT/'generated'/actions,'#pragma once\n'+declaration+'\n')
    stable(OUT/'generated'/cosmetic,once(texts[cosmetic],declaration,'#include "CosmeticsEditorActions.h"'))
    collision='soh/soh/Enhancements/debugger/colViewer.h'
    enum='typedef enum { COLVIEW_DISABLED, COLVIEW_SOLID, COLVIEW_TRANSPARENT } ColViewerRenderSetting;'
    types=collision.replace('colViewer.h','colViewerTypes.h')
    stable(OUT/'generated'/types,'#pragma once\n'+enum+'\n')
    stable(OUT/'generated'/collision,once(texts[collision],enum,'#include "colViewerTypes.h"'))
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],hook_types=len(args),maximum_arity=arity),indent=2)+'\n')

def includes():
    from prepare_soh_resources import includes as resource_includes
    from prepare_fast_resources import includes as fast_includes
    return [OUT/'generated/soh',ROOT/'scratch/ship-utils-xdk/generated/soh',ROOT/'scratch/game-xdk/full/source/soh',ROOT/'scratch/game-xdk/full/source/soh/include',ROOT/'scratch/game-xdk/full/source/soh/src']+fast_includes()+resource_includes(True)

def build():
    prepare();sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK');folder=OUT/'xdk';folder.mkdir(exist_ok=True);rows=[]
    flags=['/nologo','/c','/TP','/EHsc','/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DF3DEX_GBI_2','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0','/DINCLUDE_MPQ_SUPPORT','/DCONTROLLERBUTTONS_T=uint32_t',
           '/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/FI'+str(ROOT/'platform/shipyard/game/include/xdk_math_boundary.h'),'/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in includes()]
    for name in ('GameInteractor','GameInteractor_State','GameInteractor_Hooks'):
        source=OUT/'generated'/BASE/(name+'.cpp');obj=folder/(name+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/(name+'.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=result.returncode));print(name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(line for line in result.stdout.splitlines() if 'error ' in line)[:3000])
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(row['exit'] for row in rows):raise SystemExit(1)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
