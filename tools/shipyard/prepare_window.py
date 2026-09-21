"""Project current shared window/GUI declarations and common window ownership."""
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
from prepare_configuration import transform as config_transform, once
from cpp_ast import PARSER, walk

OUT = ROOT/'scratch/window-xdk'
OWN = ROOT/'platform/shipyard/window'


def gui_constructors(text, classname):
    """Expand only the audited empty delegations into real member initialization.

    The non-delegating constructor's original body becomes one private method;
    each generated constructor initializes the same base/members before it.
    """
    source=text.encode()
    nodes=[n for n in walk(PARSER.parse(source).root_node) if n.type=='function_definition'
           and n.child_by_field_name('declarator').text.startswith((classname+'::'+classname+'(').encode())]
    if len(nodes)!=(6 if classname=='GuiWindow' else 2):raise ValueError('GUI constructor shape drift')
    target=nodes[0]; body=target.child_by_field_name('body').text.decode()
    prefix=source[target.start_byte:target.child_by_field_name('body').start_byte].decode()
    initializer=prefix[prefix.index('\n    : ')+len('\n    : '):].strip()
    signatures=[]
    if classname=='GuiWindow':
        signatures=[{'isVisible':'isVisible','originalSize':'originalSize','windowFlags':'windowFlags'},
                    {'isVisible':'isVisible','originalSize':'originalSize','windowFlags':'ImGuiWindowFlags_None'},
                    {'isVisible':'isVisible','originalSize':'ImVec2(-1, -1)','windowFlags':'ImGuiWindowFlags_None'},
                    {'isVisible':'false','originalSize':'originalSize','windowFlags':'windowFlags'},
                    {'isVisible':'false','originalSize':'originalSize','windowFlags':'ImGuiWindowFlags_None'},
                    {'isVisible':'false','originalSize':'ImVec2(-1, -1)','windowFlags':'ImGuiWindowFlags_None'}]
    else:signatures=[{'isVisible':'isVisible'},{'isVisible':'false'}]
    edits=[]
    for index,node in enumerate(nodes):
        if index and node.child_by_field_name('body').text.strip()!=b'{\n}':raise ValueError('Nonempty delegation needs explicit audit')
        decl=node.child_by_field_name('declarator').text.decode()
        init=initializer
        for key,value in signatures[index].items():init=re.sub(r'\b'+key+r'\b',lambda _:value,init)
        replacement=decl+'\n    : '+init+' {\n    InitializeVisibility();\n}'
        if index==0:replacement+='\n\nvoid '+classname+'::InitializeVisibility() '+body
        edits.append((node.start_byte,node.end_byte,replacement.encode()))
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def transform(name, text):
    if name.endswith('/Window.h'):
        text = config_transform(name, text)
        text = once(text, '  private:', '  private:\n    void InitializeMembers(std::shared_ptr<Gui> gui, std::shared_ptr<MouseStateManager> mouseStateManager);')
    elif name.endswith('/Window.cpp'):
        text = once(text, '#include "ship/controller/controldeck/ControlDeck.h"',
                    '#include "ship/config/Config.h"\n#include "ship/window/gui/Gui.h"\n#include "ship/window/MouseStateManager.h"')
        signature = 'Window::Window(std::shared_ptr<Gui> gui, std::shared_ptr<MouseStateManager> mouseStateManager)'
        text = once(text, signature+' {', signature+' : mLastScancode(-1) {\n    InitializeMembers(gui, mouseStateManager);\n}\n\nvoid Window::InitializeMembers(std::shared_ptr<Gui> gui, std::shared_ptr<MouseStateManager> mouseStateManager) {')
        delegations = [
            ('Window::Window(std::shared_ptr<Gui> gui) : Window(gui, std::make_shared<MouseStateManager>())',
             'Window::Window(std::shared_ptr<Gui> gui)', 'gui, std::make_shared<MouseStateManager>()'),
            ('Window::Window(std::vector<std::shared_ptr<GuiWindow>> guiWindows) : Window(std::make_shared<Gui>(guiWindows))',
             'Window::Window(std::vector<std::shared_ptr<GuiWindow>> guiWindows)', 'std::make_shared<Gui>(guiWindows), std::make_shared<MouseStateManager>()'),
            ('Window::Window() : Window(std::vector<std::shared_ptr<GuiWindow>>())',
             'Window::Window()', 'std::make_shared<Gui>(std::vector<std::shared_ptr<GuiWindow>>()), std::make_shared<MouseStateManager>()')]
        for old, new, arguments in delegations:
            text = once(text, old+' {\n}', new+' : mLastScancode(-1) {\n    InitializeMembers('+arguments+');\n}')
    elif name.endswith('/MouseStateManager.h'):
        text = once(text, '#include <memory>', '#include <memory>\n#include <stdint.h>')
        for member, value in [('mAutoCaptureMouse','false'), ('mForceCursorVisibility','false'),
                              ('mCursorVisibleTicks','180'), ('mCursorVisibleTicksCounter','mCursorVisibleTicks')]:
            text = once(text, member+' = '+value+';', member+';')
    elif name.endswith('/MouseStateManager.cpp'):
        text = once(text, '#include "ship/window/Window.h"', '#include "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"')
        text = once(text, 'MouseStateManager::MouseStateManager() {',
                    'MouseStateManager::MouseStateManager() : mAutoCaptureMouse(false), mForceCursorVisibility(false), mCursorVisibleTicks(180), mCursorVisibleTicksCounter(mCursorVisibleTicks) {')
    elif name.endswith('/Gui.h'):
        # These headers supply implementation types, not stored values. Retain
        # every method/member and supply complete metadata from its real header.
        text = once(text, '#include <SDL2/SDL.h>', 'struct SDL_Renderer;')
        for header in ('ConsoleWindow.h','InputEditorWindow.h','GameOverlay.h','StatsWindow.h','GuiWindow.h','GuiMenuBar.h','IconsFontAwesome4.h'):
            text = once(text, '#include "ship/window/gui/'+header+'"', '')
        text = once(text, '#include "ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h"', '')
        text = once(text, '#include "fast/resource/type/Texture.h"', '')
        text = once(text, 'class Interpreter;', 'class Interpreter;\nclass Texture;')
        text = once(text, 'class Window;', 'class Window;\nclass GuiWindow;\nclass GuiMenuBar;\nclass GameOverlay;')
    elif name.endswith('/GuiTexture.h'):
        text = once(text, '#include <stb_image.h>', '')
        text = once(text, 'using Resource::Resource;', 'GuiTexture(std::shared_ptr<ResourceInitData> initData) : Resource<void>(initData) {}')
        text = text.replace(' override', '')
    elif name.endswith('/GuiElement.cpp'):
        # Neither header is used by this TU; this is the actual full class body.
        text = once(text, '#include "ship/Context.h"', '')
        text = once(text, '#include "ship/config/ConsoleVariable.h"', '')
        text = once(text, 'GuiElement::GuiElement() : GuiElement(false)',
                    'GuiElement::GuiElement() : mIsVisible(false), mIsInitialized(false)')
    elif name.endswith(('/GuiWindow.h','/GuiMenuBar.h')):
        text=text.replace(' override','')
        text=text.replace('GuiWindow() = default;', 'GuiWindow() : mWindowFlags(0) {}')
        text=once(text,'  private:', '  private:\n    void InitializeVisibility();')
    elif name.endswith(('/GuiWindow.cpp','/GuiMenuBar.cpp')):
        text=gui_constructors(text,Path(name).stem)
        text=text.replace('ImVec2{ -1, -1 }','ImVec2(-1, -1)')
    return text


def prepare():
    lock = json.loads((OWN/'sources.lock.json').read_text()); pending = {}
    for name, expected in lock['sources'].items():
        text = (ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest() != expected: raise ValueError('Window input drift: '+name)
        pending[name] = transform(name, text)
    for name, text in pending.items(): stable(OUT/'generated'/name, text)
    stable(OUT/'manifest.json', json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')


def includes():
    resources = runpy.run_path(str(ROOT/'tools/shipyard/tests/test_resources.py'))
    return [OUT/'generated/include', ROOT/'scratch/console-variables-xdk/generated/include', ROOT/'scratch/configuration-xdk/generated/include',
            ROOT/'scratch/audio-xdk/generated/include', ROOT/'scratch/resource-manager-xdk/generated/include',
            ROOT/'scratch/imgui-xdk/generated']+resources['includes'](True)+[ROOT/'libultraship/include']


def build():
    prepare(); folder=OUT/'xdk'; folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc', '/GR','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
           '/I'+str(sdk/'include/xbox')]+['/I'+str(p) for p in includes()]
    records=[]
    for name in ('Window.cpp','MouseStateManager.cpp','gui/GuiElement.cpp','gui/GuiWindow.cpp','gui/GuiMenuBar.cpp'):
        source=OUT/'generated/src/ship/window'/name; obj=folder/(source.stem+'.obj')
        command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        records.append(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command))
        if not result.returncode and struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2: raise ValueError('Not a Xenon object')
    stable(folder/'build.json',json.dumps(records,indent=2)+'\n')
    for row in records: print(str(row['exit'])+' '+row['source'])
    if any(r['exit'] for r in records): raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--build',action='store_true'); args=parser.parse_args()
    if args.build: build()
    else: prepare()
