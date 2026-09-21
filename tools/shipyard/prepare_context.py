"""Compile actual current Context lifecycle and its console/diagnostic closure."""
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
from prepare_filesystem import project_boundary
from cpp_ast import PARSER,walk

OUT=ROOT/'scratch/context-xdk'
OWN=ROOT/'platform/shipyard/context'


def scoped(name,values):
    return ('struct '+name+' : Shipyard::Binary::ScopedEnum<'+name+'> {\nenum Value { '+values+' };\n'+name+'() {}\n'+name+
            '(Value value) : Shipyard::Binary::ScopedEnum<'+name+'>(value) {}\n};')


def transform(name,text):
    if name.endswith('/luslog.cpp'):
        text=once(text,'auto loc = spdlog::source_loc{ file, line, SPDLOG_FUNCTION };','spdlog::source_loc loc(file, line, SPDLOG_FUNCTION);')
        # The bridge takes an already formatted message, including literal braces.
        text=once(text,'spdlog::default_logger_raw()->log(loc, lvl, str);','spdlog::default_logger_raw()->log(loc, lvl, spdlog::string_view_t(str));')
    elif name.endswith('/Context.cpp'):
        text=project_boundary('libultraship/'+name,text)
        text=once(text,'#include "ship/controller/controldeck/ControlDeck.h"',
                  '#include "ship/config/Config.h"\n#include "ship/resource/ResourceManager.h"\n#include "ship/debug/Console.h"\n'
                  '#include "ship/window/Window.h"\n#include "ship/audio/Audio.h"\n#include "context/platform.h"\n#include "filesystem/filesystem.h"')
        text=once(text,'#include <spdlog/sinks/stdout_color_sinks.h>', '#ifndef _XBOX\n#include <spdlog/sinks/stdout_color_sinks.h>\n#endif')
        text=text.replace('#ifdef _WIN32','#if defined(_WIN32) && !defined(_XBOX)')
        text=once(text,'#if (!defined(_WIN32)) || defined(_DEBUG)','#if !defined(_XBOX) && ((!defined(_WIN32)) || defined(_DEBUG))')
        # Actual startup can fail before publishing these owners. Preserve
        # cleanup order while allowing that existing failure path to unwind.
        text=once(text,'    GetWindow()->SaveWindowToConfig();','    if (GetWindow()) GetWindow()->SaveWindowToConfig();')
        text=once(text,'    GetConfig()->Save();','    if (GetConfig()) GetConfig()->Save();')
        text=once(text,'    GetWindow()->Init();','    try {\n        GetWindow()->Init();\n    } catch (...) {\n        mWindow.reset();\n        throw;\n    }')
        source=text.encode();edits=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type!='function_definition':continue
            decl=node.child_by_field_name('declarator').text.decode()
            for method,platform in [('Context::GetAppBundlePath(', 'BundleDirectory'),('Context::GetAppDirectoryPath(', 'ApplicationDirectory')]:
                if decl.startswith(method):
                    body=node.child_by_field_name('body')
                    edits.append((body.start_byte,body.end_byte,('{\n#ifdef _XBOX\n    return Shipyard::Platform::'+platform+'();\n#else\n'+body.text.decode()[1:-1]+'\n#endif\n}').encode()))
        if len(edits)!=2:raise ValueError('Context directory boundary drift')
        for start,end,body in sorted(edits,reverse=True):source=source[:start]+body+source[end:]
        text=source.decode()
        text=once(text,'        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "OTR file not found",\n                                 "Main OTR file not found. Please generate one", nullptr);',
                  '        Shipyard::Platform::ShowError(L"OTR file not found", L"Main OTR file not found. Please generate one");')
        text=once(text,'#include "ship/install_config.h"', '#ifndef _XBOX\n#include "ship/install_config.h"\n#endif')
    elif name.endswith('/Console.h'):
        text=once(text,'#include <imgui.h>', '#include "binary/compat.h"')
        text=once(text,'enum class ArgumentType { TEXT, NUMBER };', scoped('ArgumentType','TEXT, NUMBER'))
        text=once(text,'struct CommandArgument {','struct CommandArgument {\n    CommandArgument() : Type(ArgumentType::NUMBER), Optional(false) {}\n    CommandArgument(const std::string& info, ArgumentType type=ArgumentType::NUMBER, bool optional=false) : Info(info), Type(type), Optional(optional) {}')
        text=text.replace('Type = ArgumentType::NUMBER;','Type;').replace('Optional = false;','Optional;')
    elif name.endswith('/Console.cpp'):
        text=once(text,'mCommands.contains(commandName)', 'Shipyard::Resources::contains(mCommands, commandName)')
    elif name.endswith('/GfxDebugger.h'):
        text=once(text,'  public:', '  public:\n    GfxDebugger() : mIsDebugging(false), mIsDebuggingRequested(false), mDlist(nullptr) {}')
        for old,new in [('mIsDebugging = false','mIsDebugging'),('mIsDebuggingRequested = false','mIsDebuggingRequested'),('mDlist = nullptr','mDlist'),('mBreakPoint = {}','mBreakPoint')]:text=text.replace(old,new)
    elif name.endswith('/GfxDebugger.cpp'):
        text=once(text,'mBreakPoint = { cmds };','mBreakPoint.assign(1, cmds);')
    elif name.endswith('/FileDropMgr.h'):
        text=once(text,'FileDropMgr() = default;','FileDropMgr() : mPath(nullptr), mFileDropped(false) {}')
        text=text.replace('mPath = nullptr;','mPath;').replace('mFileDropped = false;','mFileDropped;')
    elif name.endswith('/FileDropMgr.cpp'):
        text=once(text,'#include <Windows.h>','#if !defined(_XBOX)\n#include <Windows.h>')
        text=once(text,'#include <dbghelp.h>','#include <dbghelp.h>\n#endif')
        text=once(text,'#elif _MSC_VER','#elif defined(_XBOX)\n    SPDLOG_WARN("Trying to register {}. Already registered.", funcAddr);\n#elif _MSC_VER')
        text=once(text,'#include "ship/window/Window.h"','#include "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"\n#include "ship/window/gui/GameOverlay.h"')
    elif name.endswith('/GameOverlay.h'):
        text=once(text,'#include "ship/debug/Console.h"','#include "binary/compat.h"')
        text=once(text,'enum class OverlayType { TEXT, IMAGE, NOTIFICATION };',scoped('OverlayType','TEXT, IMAGE, NOTIFICATION'))
        # Constructor projection will supply these exact values when its TU is
        # brought through; no native GameOverlay object is built in this step.
        text=text.replace('mCurrentFont = "Default";','mCurrentFont;').replace('mNeedsCleanup = false;','mNeedsCleanup;')
    elif name.endswith(('/CrashHandler.h','/CrashHandler.cpp')):
        text=text.replace('#if _WIN32','#if defined(_WIN32) && !defined(_XBOX)').replace('#ifdef _WIN32','#if defined(_WIN32) && !defined(_XBOX)')
        text=text.replace('#elif defined(_WIN32)','#elif defined(_WIN32) && !defined(_XBOX)').replace('#elif _WIN32','#elif defined(_WIN32) && !defined(_XBOX)')
        if name.endswith('.h'):
            text=text.replace('mCallback = nullptr;','mCallback;').replace('mOutBuffer = nullptr;','mOutBuffer;').replace('mOutBuffersize = 0;','mOutBuffersize;').replace('static constexpr size_t','static const size_t')
        else:
            for signature in ['CrashHandler::CrashHandler()','CrashHandler::CrashHandler(CrashHandlerCallback callback)']:
                text=once(text,signature+' {',signature+' : mCallback(nullptr), mOutBuffer(nullptr), mOutBuffersize(0) {')
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    return '#include "resources/runtime_support.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()


def prepare():
    pending={}
    for name,expected in json.loads((OWN/'sources.lock.json').read_text())['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Context input drift: '+name)
        pending[name]=transform(name,text)
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    from prepare_window import includes
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
           '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OUT/'generated/include']+includes()+[ROOT/'scratch/async-xdk/generated']]
    sources=[OUT/'generated'/n for n in json.loads((OWN/'sources.lock.json').read_text())['sources'] if n.endswith('.cpp')]+[OWN/'platform.cpp']
    records=[]
    for source in sources:
        obj=folder/(source.stem+'.obj');command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        records.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command))
        if not result.returncode and struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
    stable(folder/'build.json',json.dumps(records,indent=2)+'\n')
    for row in records:print(str(row['exit'])+' '+row['source'])
    if any(r['exit'] for r in records):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
