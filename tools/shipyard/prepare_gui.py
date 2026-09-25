"""Project the full current Gui and its current concrete window declarations."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT,verified
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import syntax
from prepare_fast3d import member_defaults
from cpp_ast import PARSER,walk
from platform_base import resolve as resolve_platform_base
OWN=ROOT/'platform/shipyard/gui'
OUT=ROOT/'scratch/gui-xdk'
PLATFORM_BASE=resolve_platform_base(ROOT)


def inherited_window(text,classname):
    # Construct nonempty vector defaults with exact typed ordered values. Each
    # helper is local to the class that owns the original member declaration.
    source=text.encode();edits=[]
    for n in walk(PARSER.parse(source).root_node):
        if n.type!='field_declaration':continue
        typ=n.child_by_field_name('type');value=n.child_by_field_name('default_value')
        if not typ or not value or not typ.text.startswith(b'std::vector<') or value.type!='initializer_list' or value.text==b'{}':continue
        member=n.child_by_field_name('declarator').text.decode();t=typ.text.decode();element=t[len('std::vector<'):-1]
        values=value.text.decode();helper='MakeDefault'+member
        replacement='\n    static '+t+' '+helper+'(){ const '+element+' values[]='+values+'; return '+t+'(values,values+sizeof(values)/sizeof(values[0])); }\n'
        edits.append((n.start_byte,n.end_byte,n.text[:value.start_byte-n.start_byte]+(helper+'();'+replacement).encode()))
    for start,end,value in sorted(edits,reverse=True):source=source[:start]+value+source[end:]
    text,defaults,arrays=member_defaults(source.decode(),classname)
    if arrays:raise ValueError('GUI inherited array defaults require explicit audit')
    source=(ROOT/'libultraship/include/ship/window/gui/GuiWindow.h').read_bytes()
    decls=[]
    for n in walk(PARSER.parse(source).root_node):
        if n.type!='function_declarator':continue
        name=n.child_by_field_name('declarator')
        if not name or name.text!=b'GuiWindow':continue
        params=n.child_by_field_name('parameters');args=[]
        for p in params.named_children:
            d=p.child_by_field_name('declarator')
            identifiers=[v for v in walk(d) if v.type=='identifier'] if d else []
            if len(identifiers)!=1:raise ValueError('GuiWindow parameter shape')
            args.append(identifiers[0].text.decode())
        init='Ship::GuiWindow('+','.join(args)+')'
        if defaults:init+=','+','.join(defaults)
        decls.append('    '+classname+params.text.decode()+' : '+init+' {}')
    if len(decls)!=7:raise ValueError('GuiWindow overload set changed')
    return once(text,'    using GuiWindow::GuiWindow;','\n'.join(decls))


def cache_viewport_interpreter_locks(text):
    counts={'ApplyResolutionChanges':7,'GetIntegerScaleFactor':20,
            'CalculateGameViewport':16,'DrawGame':8}
    for method,expected in counts.items():
        start=text.index('Gui::'+method+'(')
        end=text.index('\n}\n',start)+2
        body=text[start:end]
        if body.count('mInterpreter.lock()')!=expected or 'mInterpreter =' in body:
            raise ValueError('GUI interpreter lifetime boundary drift: '+method)
        if method=='DrawGame':
            anchor='    GetGameOverlay()->Draw();'
            if body.index(anchor)>body.index('mInterpreter.lock()'):
                raise ValueError('DrawGame interpreter used before overlay callback')
            body=once(body,anchor,anchor+'\n    auto interpreter = mInterpreter.lock();')
        elif method=='GetIntegerScaleFactor':
            body=once(body,'            // Screen bounds take priority over whatever Factor is set to.',
                      '            auto interpreter = mInterpreter.lock();\n'
                      '            // Screen bounds take priority over whatever Factor is set to.')
            body=once(body,'        // Compare aspect ratios of game framebuffer and GUI',
                      '        auto interpreter = mInterpreter.lock();\n'
                      '        // Compare aspect ratios of game framebuffer and GUI')
        else:
            first=body.index('mInterpreter.lock()')
            line=body.rfind('\n',0,first)+1
            body=body[:line]+'    auto interpreter = mInterpreter.lock();\n'+body[line:]
        # Only references after the declaration are replaced. The two
        # integer-scale branches each own an independent local lifetime.
        marker='auto interpreter = mInterpreter.lock();'
        body=body.replace('mInterpreter.lock()', 'interpreter')
        body=body.replace('auto interpreter = interpreter;',marker)
        text=text[:start]+body+text[end:]
    return text

def transform(name,text):
    if name.endswith('/Fonts.h'):
        # XDK's concatenated string limit is 65535 bytes. Keep the exact same
        # base85 font (including its terminator) as a numeric static initializer.
        begin=text.index('=')+1;end=text.rindex(';')
        values=''.join(ast.literal_eval(m[0].replace('\\?','?')) for m in re.finditer(r'"(?:[^"\\]|\\.)*"',text[begin:end])).encode('ascii')+b'\0'
        if len(values)!=155711:raise ValueError('FontAwesome base85 length changed')
        return text[:begin]+' {\n'+''.join('    '+','.join(str(v) for v in values[i:i+32])+',\n' for i in range(0,len(values),32))+'};\n'
    if name.endswith('/Gui.h'):
        from prepare_window import transform as shared_gui
        text=shared_gui(name,text)
        text=once(text,'  private:','  private:\n    void InitializeWindows(std::vector<std::shared_ptr<GuiWindow>> guiWindows);')
    elif name.endswith('.h') and Path(name).stem in ('ConsoleWindow','InputEditorWindow','StatsWindow','GfxDebuggerWindow'):
        text=inherited_window(text,Path(name).stem)
        if name.endswith('/ConsoleWindow.h'):
            text,defaults,arrays=member_defaults(text,'ConsoleLine')
            text=once(text,'struct ConsoleLine {','struct ConsoleLine {\n        ConsoleLine() : '+','.join(defaults)+' {}')
            text=once(text,'struct ConsoleLine {','struct ConsoleLine {\n        ConsoleLine(const std::string& text,spdlog::level::level_enum priority) : Text(text),Priority(priority),Channel("Console") {}')
            text=text.replace('static constexpr size_t','static const size_t')
    elif name.endswith('/Gui.cpp'):
        headers=['ship/window/gui/'+n+'.h' for n in ('ConsoleWindow','InputEditorWindow','StatsWindow','GameOverlay','GuiWindow','GuiMenuBar','IconsFontAwesome4')]
        headers+=['ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h','ship/resource/ResourceLoader.h']
        text='\n'.join('#include "'+h+'"' for h in headers)+'\n#include "native_gui.h"\n'+text
        text=once(text,'#else\n#include <SDL2/SDL_hints.h>','#elif !defined(_XBOX)\n#include <SDL2/SDL_hints.h>')
        # Desktop branches require no runtime substitute on a native backend.
        for method,endpattern in [('ImGuiWMInit','\n#if __APPLE__'),('HandleWindowEvents','\n#ifdef ENABLE_DX11'),('ImGuiWMNewFrame','\n#ifdef ENABLE_DX11')]:
            begin=text.index('void Gui::'+method+'(');start=text.index('        case WindowBackend::FAST3D_SDL_OPENGL:',begin);end=text.index(endpattern,start)
            text=text[:start]+'#if defined(ENABLE_OPENGL) || defined(__APPLE__)\n'+text[start:end]+'\n#endif'+text[end:]
        start=text.index('        if (backend == WindowBackend::FAST3D_SDL_OPENGL && mImpl.Opengl.Context != nullptr)');end=text.index('#ifdef __APPLE__',start)
        region=text[start:end];region=once(region,'        } else {','        } else\n#endif\n        {')
        text=text[:start]+'#ifdef ENABLE_OPENGL\n'+region+text[end:]
        text=once(text,'Gui::Gui(std::vector<std::shared_ptr<GuiWindow>> guiWindows) : mNeedsConsoleVariableSave(false) {',
                  'Gui::Gui(std::vector<std::shared_ptr<GuiWindow>> guiWindows) : mNeedsConsoleVariableSave(false) { InitializeWindows(guiWindows); }\n\nvoid Gui::InitializeWindows(std::vector<std::shared_ptr<GuiWindow>> guiWindows) {')
        text=once(text,'Gui::Gui() : Gui(std::vector<std::shared_ptr<GuiWindow>>()) {\n}',
                  'Gui::Gui() : mNeedsConsoleVariableSave(false) { InitializeWindows(std::vector<std::shared_ptr<GuiWindow>>());\n}')
        text=once(text,'void Gui::ShutDownImGui(Ship::Window* window) {',
                  'void Gui::ShutDownImGui(Ship::Window* window) {\n    if (!ImGui::GetCurrentContext()) return;')
        text=text.replace('GetWindowBackend())','GetWindowBackend().GetValue())')
        methods={'ImGuiWMInit':'Shipyard_ImGuiPlatformInit();','ImGuiBackendInit':'Shipyard_ImGuiRendererInit();',
                 'ImGuiBackendNewFrame':'Shipyard_ImGuiRendererNewFrame();',
                 'ShutDownImGui':'Shipyard_ImGuiPlatformShutdown(); Shipyard_ImGuiRendererShutdown();',
                 'ImGuiWMNewFrame':'Shipyard_ImGuiPlatformNewFrame(Context::GetInstance()->GetWindow()->GetWidth(),Context::GetInstance()->GetWindow()->GetHeight(),GetMenuOrMenubarVisible() || ImGui::GetTopMostPopupModal()!=NULL);',
                 'ImGuiRenderDrawData':'Shipyard_ImGuiRender(data);'}
        for method,call in methods.items():
            begin=text.index('void Gui::'+method+'(');switch=text.index('switch (',begin);pos=text.index('{',switch)+1
            text=text[:pos]+'\n        case WindowBackend::FAST3D_XENOS: '+call+' break;'+text[pos:]
        text=once(text,'    ImGui::Render();\n    ImGuiRenderDrawData(ImGui::GetDrawData());',
                  '    Shipyard_ImGuiPlatformDrawCursor();\n    ImGui::Render();\n    ImGuiRenderDrawData(ImGui::GetDrawData());')
        # The renderer NewFrame hook rebuilds the atlas only when modern SoH
        # adds fonts after backend initialization and invalidates it.
        text=text.replace('mGuiTextures.contains(name)','Shipyard::Resources::contains(mGuiTextures,name)')
        text=text.replace('mGuiWindows.contains(guiWindow->GetName())','Shipyard::Resources::contains(mGuiWindows,guiWindow->GetName())')
        text=text.replace('mGuiWindows.contains(name)','Shipyard::Resources::contains(mGuiWindows,name)')
        text=text.replace('std::reinterpret_pointer_cast<','Shipyard::GuiCompat::ReinterpretPointerCast<')
        text=re.sub(r'(?<!::)\bdynamic_pointer_cast<','std::dynamic_pointer_cast<',text)
        text=once(text,'switch (res.Type)','switch (res.Type.GetValue())')
        text=re.sub(r'\b0b([01]+)\b',lambda m:str(int(m[1],2)),text)
        text=cache_viewport_interpreter_locks(text)
    elif name.endswith('/StatsWindow.cpp'):
        text=once(text,'#if defined(_WIN32)','#if defined(_XBOX)\n    ImGui::Text("Platform: Xbox 360");\n#elif defined(_WIN32)')
    elif name.endswith('/ConsoleWindow.cpp'):
        text=once(text,'constexpr ImGuiInputTextFlags','const ImGuiInputTextFlags')
        text='#include "ship/window/gui/Gui.h"\n#include "gui/command.h"\n'+text
        source=text.encode();edits=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type!='call_expression' or not node.child_by_field_name('function').text.endswith(b'AddCommand'):continue
            args=node.child_by_field_name('arguments').named_children
            if len(args)!=2 or args[1].type!='initializer_list':raise ValueError('Console command declaration changed')
            fields=args[1].named_children
            if len(fields) not in (2,3):raise ValueError('Console command field count changed')
            values='ShipyardInputCompiler::Build<std::vector<CommandArgument> >()'
            if len(fields)==3:
                for arg in fields[2].named_children:
                    values+='.Add(CommandArgument('+','.join(v.text.decode() for v in arg.named_children)+'))'
            value='Shipyard::GuiCompat::MakeCommand('+fields[0].text.decode()+','+fields[1].text.decode()+','+values+'.Get())'
            edits.append((args[1].start_byte,args[1].end_byte,value.encode()))
        if len(edits)!=7:raise ValueError('Console command inventory changed')
        for a,b,v in sorted(edits,reverse=True):source=source[:a]+v+source[b:]
        text=source.decode()
        text=once(text,'    va_copy(argsCopy, args);','    argsCopy = args; // XDK va_list is a scalar pointer; independent copied cursor.')
        text=once(text,'int size = vsnprintf(nullptr, 0, fmt, argsCopy);','int size = _vscprintf(fmt, argsCopy);')
        text=once(text,'vsnprintf(buf.data(), buf.size(), fmt, args);','_vsnprintf_s(buf.data(), buf.size(), _TRUNCATE, fmt, args);')
        text=once(text,'push_back({ std::string(buf.begin(), buf.end() - 1), priority });','push_back(ConsoleLine(std::string(buf.begin(), buf.end() - 1), priority));')
        text=text.replace('switch (var->Type)','switch (var->Type.GetValue())')
    elif name.endswith('/InputEditorWindow.cpp'):
        text='#include "ship/window/Window.h"\n#include "ship/window/gui/IconsFontAwesome4.h"\n#include <spdlog/spdlog.h>\n'+text
        for member in ('mButtonsBitmasks','mDpadBitmasks'):
            text=re.sub(r'    '+member+r' = (\{[^;]+\});',lambda m:'    { const CONTROLLERBUTTONS_T values[]='+m[1]+'; '+member+'=std::set<CONTROLLERBUTTONS_T>(values,values+sizeof(values)/sizeof(values[0])); }',text)
        # Both temporary lists have exact known element types and lifetimes.
        source=text.encode();edits=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type!='for_range_loop':continue
            right=node.child_by_field_name('right')
            if right.type!='initializer_list':continue
            value=right.text.decode()
            if value=='{ LEFT, RIGHT, UP, DOWN }':element='Direction'
            elif 'std::make_pair<uint8_t, std::shared_ptr<ControllerStick>>' in value:element='std::pair<uint8_t,std::shared_ptr<ControllerStick>>'
            else:raise ValueError('Unknown GUI temporary range')
            # Prefix and suffix retain nested loops for the later general pass.
            replacement='{ const '+element+' _guiValues[]='+value+'; '+source[node.start_byte:right.start_byte].decode()+'_guiValues'+source[right.end_byte:node.end_byte].decode()+' }'
            edits.append((node.start_byte,node.end_byte,replacement.encode()))
        # Inner direction range overlaps outer stick range; expand one at a time.
        if edits:
            for a,b,v in sorted(edits,reverse=True):
                if any(a<c and d<b for c,d,_ in edits):continue
                source=source[:a]+v+source[b:]
            text=source.decode()
            # The only remaining initializer range is the two-stick outer loop.
            source=text.encode()
            for node in walk(PARSER.parse(source).root_node):
                if node.type=='for_range_loop' and node.child_by_field_name('right').type=='initializer_list':
                    right=node.child_by_field_name('right');value=right.text.decode()
                    if 'std::make_pair<uint8_t, std::shared_ptr<ControllerStick>>' not in value:raise ValueError('Unexpected GUI range')
                    text=source[:node.start_byte].decode()+'{ const std::pair<uint8_t,std::shared_ptr<ControllerStick>> _guiValues[]='+value+'; '+source[node.start_byte:right.start_byte].decode()+'_guiValues'+source[right.end_byte:node.end_byte].decode()+' }'+source[node.end_byte:].decode();break
        text=re.sub(r'ImVec4 color = \{(.*?)\};',r'ImVec4 color(\1);',text,flags=re.S)
        text=re.sub(r'Color_RGB8\(\{(.*?)\}\)',r'Shipyard::GuiCompat::Rgb(\1)',text,flags=re.S)
    elif name.endswith('/GfxDebuggerWindow.cpp'):
        text='#include "ship/resource/ResourceManager.h"\n'+text
        text=once(text,'#include <optional>','#include "xbox_compat/optional.h"')
        text=text.replace('std::optional<','xbox_compat::optional<').replace('std::nullopt','xbox_compat::nullopt')
        text=re.sub(r'(?<!::)\bdynamic_pointer_cast<','std::dynamic_pointer_cast<',text)
        text=re.sub(r'ImVec([24])\{([^{}]+)\}',r'ImVec\1(\2)',text)
        text=once(text,'switch (type)','switch (type.GetValue())')
        text=text.replace('SDL_SetClipboardText(', 'ImGui::SetClipboardText(')
        # XDK both rejects lambda default arguments (C3486) and can ICE before
        # reporting that diagnostic. Make the same default explicit at each use.
        text=once(text,'const F3DGfx* sub = nullptr) mutable {','const F3DGfx* sub) mutable {')
        source=text.encode();positions=[]
        for node in walk(PARSER.parse(source).root_node):
            if node.type=='call_expression' and node.child_by_field_name('function').text==b'nodeWithText':
                args=node.child_by_field_name('arguments')
                if len(args.named_children)==2:positions.append(args.end_byte-1)
        if len(positions)!=32:raise ValueError('Debugger default argument use count changed')
        for pos in sorted(positions,reverse=True):source=source[:pos]+b', nullptr'+source[pos:]
        text=source.decode()
    if name.endswith(('/ConsoleWindow.cpp','/InputEditorWindow.cpp','/GfxDebuggerWindow.cpp')):
        general=runpy.run_path(str(ROOT/'platform/shipyard/input/lowering.py'))
        text='#include "input/compiler.h"\n'+general['syntax'](text,set())
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    return '#include "gui/compat.h"\n'+lower(syntax(text).encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()


def prepare():
    pending={}
    for name,sha in json.loads((OWN/'sources.lock.json').read_text())['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=sha:raise ValueError('GUI source drift '+name)
        pending[name]=transform(name,text)
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def includes():
    from prepare_presentation import includes as presentation_includes
    return [OUT/'generated/include',ROOT/'platform/shipyard/native-imgui',verified('stb'),verified('libgfxd'),ROOT/'scratch/async-xdk/generated',ROOT/'scratch/prism-xdk/generated',PLATFORM_BASE/'sources/value_types']+presentation_includes()


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc','/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DF3DEX_GBI_2','/DGFX_DEBUG_DISASSEMBLER','/DSPDLOG_ACTIVE_LEVEL=0','/DCONTROLLERBUTTONS_T=uint32_t',
           '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in includes()]
    rows=[]
    sources=[OUT/'generated/src/ship/window/gui'/(name+'.cpp') for name in ('Gui','StatsWindow','ConsoleWindow','InputEditorWindow')]
    sources+=[OUT/'generated/src/libultraship/window/gui/GfxDebuggerWindow.cpp']
    sources+=[ROOT/'platform/shipyard/native-imgui/gui_init.cpp']
    for source in sources:
        obj=folder/(source.stem+'.obj')
        command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command));print(source.name+': '+str(result.returncode))
        if result.returncode:print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:4500])
        elif struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not Xenon')
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
