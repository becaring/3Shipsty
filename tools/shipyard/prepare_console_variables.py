"""Keep current typed CVar storage, recursive JSON load/save and legacy migration."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import transform as runtime_transform
from cpp_ast import PARSER, walk
from xbox360_platform.console_variable_lookup import transform as borrow_typed_cvars
from xbox360_platform.console_variable_lookup import header as borrow_cvar_names

OUT=ROOT/'scratch/console-variables-xdk'
OWN=ROOT/'platform/shipyard/console-variables'


def transform(name,text):
    if name.endswith('/ConsoleVariable.h'):
        text=borrow_cvar_names(text)
        text=once(text,'typedef enum class ConsoleVariableType { Integer, Float, String, Color, Color24 } ConsoleVariableType;',
                  'struct ConsoleVariableType : Shipyard::Binary::ScopedEnum<ConsoleVariableType> {\n'
                  'enum Value { Integer, Float, String, Color, Color24 };\nConsoleVariableType() {}\n'
                  'ConsoleVariableType(Value value) : Shipyard::Binary::ScopedEnum<ConsoleVariableType>(value) {}\n};')
        # Every reached creation is value-initialized make_shared<CVar>(). Its
        # original zero Type and null String are explicit in the legacy ctor.
        text=once(text,'typedef struct CVar {','typedef struct CVar {\n    CVar() : Type(ConsoleVariableType::Integer), String(nullptr) {}')
        text=once(text,'char* String = nullptr;','char* String;')
        text='#include "binary/compat.h"\n'+text
    elif name.endswith('/ConsoleVariable.cpp'):
        text=borrow_typed_cvars(text)
        # Load clears defaults installed at GUI startup. Restore the Xbox
        # controller-navigation default after persisted and legacy values load;
        # RegisterInteger leaves an explicit saved zero untouched.
        text=once(text,'    LoadLegacy();\n}',
                  '    LoadLegacy();\n    RegisterInteger(CVAR_IMGUI_CONTROLLER_NAV, 1);\n}')
        text=once(text,'switch (variableTo->Type)', 'switch (variableTo->Type.GetValue())')
        text=once(text,'for (const auto& item : items) {',
                  'for (auto cursor=items.begin(), finish=items.end(); cursor!=finish; ++cursor) {\n        const auto& item=*cursor;')
        lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text=lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
        text='#include "compile_definitions.h"\n#include "resources/runtime_support.h"\n#include <spdlog/spdlog.h>\n'+text
    elif name.endswith('/Path.h'):
        text=runtime_transform(name,text)
        text=once(text,'#include "../StringHelper.h"','#include "ship/utils/StringHelper.h"')
    elif name.endswith('/DiskFile.h'):
        text=once(text,'#include "Directory.h"','#include "ship/utils/filesystemtools/Directory.h"')
        source=text.encode();edits=[]
        for function in walk(PARSER.parse(source).root_node):
            if function.type!='function_definition':continue
            decl=function.child_by_field_name('declarator').text
            if b'const fs::path& filePath' not in decl:continue
            body=function.child_by_field_name('body')
            original=body.text;projected=original.replace(b'file(filePath,',b'file(filePath.string(),')
            if original!=projected:edits.append((body.start_byte,body.end_byte,projected))
        if len(edits)!=5:raise ValueError('DiskFile stream path boundary drift')
        for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
        text=source.decode()
    return text


def prepare():
    pending={}
    for name,expected in json.loads((OWN/'sources.lock.json').read_text())['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('ConsoleVariable input drift: '+name)
        pending[name]=transform(name,text)
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    from prepare_window import includes
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
             '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/I'+str(sdk/'include/xbox')]
    command+=['/I'+str(p) for p in [OUT/'generated/include']+includes()]
    source=OUT/'generated/src/ship/config/ConsoleVariable.cpp';obj=folder/'ConsoleVariable.obj'
    command+=[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    stable(folder/'ConsoleVariable.log',result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps(dict(command=command,exit=result.returncode),indent=2)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
    if struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
    print('Complete current ConsoleVariable compiles for Xenon')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
