"""Full stable Network transport and canonical remote-control declarations."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_soh_menus import inherited
from cpp_ast import PARSER,walk

OWN=ROOT/'platform/shipyard/network';OUT=ROOT/'scratch/network-xdk';BASE='soh/soh/Network/'

def value_expressions(text):
    names=('Network','Anchor','Effect','Response');raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='init_declarator':
            value=n.child_by_field_name('value');parent=n.parent;typ=parent.child_by_field_name('type') if parent.type=='declaration' else None
            if value and typ and value.text==b'{}' and typ.text.decode().split('::')[-1] in names:
                eq='' if any(c.type=='=' for c in n.children) else '= '
                edits.append((value.start_byte,value.end_byte,eq+typ.text.decode()+'(Shipyard::SohUI::ValueInit())'))
        if n.type not in ('new_expression','call_expression','compound_literal_expression'):continue
        typ=n.child_by_field_name('function') or n.child_by_field_name('type');args=n.child_by_field_name('arguments') or n.child_by_field_name('value')
        if typ is not None and args is not None and not args.named_children and typ.text.decode().split('::')[-1] in names:
            edits.append((args.start_byte,args.end_byte,'(Shipyard::SohUI::ValueInit())'))
    return edits_apply(raw,edits)

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());texts={};generated={}
    for n,h in lock['sources'].items():
        t=(ROOT/n).read_text(encoding='utf-8-sig')
        if hashlib.sha256(t.encode()).hexdigest()!=h:raise ValueError('Network source drift '+n)
        texts[n]=t
    for name,text in texts.items():
        if name.endswith('.yml'):continue
        text=text.replace('#include <thread>','#include "network/support.h"').replace('#include <mutex>','#include "async/native.h"')
        text=text.replace('std::thread ','Shipyard::Async::joining_thread ').replace('std::mutex ','Shipyard::Async::mutex ')
        if name.endswith('/Network.h'):
            text=once(text,'#ifdef __cplusplus','#ifdef __cplusplus\n#ifndef ENABLE_REMOTE_CONTROL\n#error The pinned Xbox Network class requires ENABLE_REMOTE_CONTROL in every consuming translation unit.\n#endif')
            text=once(text,'#include <SDL2/SDL_net.h>','#include "network/transport.h"')
            text=once(text,'    bool isEnabled;','    Shipyard::Network::Flag isEnabled;')
            text=once(text,'    bool isConnected;','    Shipyard::Network::Flag isConnected;')
            text=once(text,'  public:\n','''    Shipyard::Async::mutex socketMutex;
  public:
    Network() {}
    explicit Network(Shipyard::SohUI::ValueInit) :
#ifdef ENABLE_REMOTE_CONTROL
        networkAddress(), networkSocket(nullptr),
#endif
        receiveThread(), receivedData(), isEnabled(false), isConnected(false) {}
''')
        elif name.endswith('/Network.cpp'):
            text=once(text,'#include <libultraship/libultraship.h>','#include <cstring>')
            text=once(text,'receiveThread = std::thread(&Network::ReceiveFromServer, this);','receiveThread = Shipyard::Async::make_thread([this](){ ReceiveFromServer(); });')
            text=once(text,'        SPDLOG_ERROR("[Network] SDLNet_ResolveHost: {}", SDLNet_GetError());','        SPDLOG_ERROR("[Network] SDLNet_ResolveHost: {}", SDLNet_GetError());\n        return; // Failed DNS must not turn INADDR_NONE into a listening socket.')
            text=once(text,'    SDLNet_TCP_Send(networkSocket, payload, strlen(payload) + 1);','    Shipyard::Async::lock_guard<Shipyard::Async::mutex> socketLock(socketMutex);\n    SDLNet_TCP_Send(networkSocket, payload, strlen(payload) + 1);')
            text=once(text,'            networkSocket = SDLNet_TCP_Open(&networkAddress);','            {\n                Shipyard::Async::lock_guard<Shipyard::Async::mutex> socketLock(socketMutex);\n                networkSocket = SDLNet_TCP_Open(&networkAddress);\n            }')
            text=once(text,'            SDLNet_TCP_Close(networkSocket);\n            networkSocket = nullptr;','            {\n                Shipyard::Async::lock_guard<Shipyard::Async::mutex> socketLock(socketMutex);\n                SDLNet_TCP_Close(networkSocket);\n                networkSocket = nullptr;\n            }')
        elif name.endswith('/CrowdControl.h'):
            text=once(text,'    struct Response {','''    struct Response {
        Response() : type(ResponseType::EffectRequest) {}
        explicit Response(Shipyard::SohUI::ValueInit) : id(), status(), timeRemaining(), type(ResponseType::EffectRequest) {}
        Response(int id_, EffectResult status_, long remaining_, ResponseType type_=ResponseType::EffectRequest)
            : id(id_), status(status_), timeRemaining(remaining_), type(type_) {}
''')
            text=once(text,'ResponseType type = ResponseType::EffectRequest;','ResponseType type;')
            text=once(text,'    typedef struct Effect {','''    typedef struct Effect {
        Effect() : category(0) {}
        explicit Effect(Shipyard::SohUI::ValueInit) : id(), spawnParams(), category(0), timeRemaining(), giEffect(), viewerName(), isPaused(), lastExecutionResult() {}
''')
            text=once(text,'uint32_t category = 0;','uint32_t category;')
        elif name.endswith('/Anchor.h'):
            text=once(text,'#include <libultraship/libultraship.h>','#include <ship/window/gui/GuiWindow.h>\n#include "soh/Enhancements/randomizer/randomizerTypes.h"')
            defaults=re.findall(r'    (?:uint32_t|bool) (\w+) = ([^;]+);',text)
            if len(defaults)!=5:raise ValueError('Anchor default inventory changed')
            for member,value in defaults:text=once(text,member+' = '+value+';',member+';')
            normal=', '.join(n+'('+v+')' for n,v in defaults)
            text=once(text,'  public:\n    uint32_t ownClientId;','  public:\n    uint32_t ownClientId;\n    Anchor() : '+normal+' {}\n    explicit Anchor(Shipyard::SohUI::ValueInit) : Network(Shipyard::SohUI::ValueInit()), '+normal+', ownClientId(), roomState() {}\n')
            constants=re.findall(r'    inline static const std::string (\w+) = ([^;]+);',text)
            if len(constants)!=23:raise ValueError('Anchor constant inventory changed: '+str(len(constants)))
            for member,value in constants:text=once(text,'inline static const std::string '+member+' = '+value+';','static const std::string '+member+';')
            definitions='#include "soh/Network/Anchor/Anchor.h"\n'+'\n'.join('const std::string Anchor::'+n+' = '+v+';' for n,v in constants)+'\n'
            generated[BASE+'Anchor/AnchorConstants.cpp']=definitions
            text=once(text,'    using GuiWindow::GuiWindow;','    AnchorRoomWindow() : GuiWindow() {}\n'+inherited('AnchorRoomWindow'))
            text=text.replace(' override','')
        generated[name]=text
    for n,t in generated.items():stable(OUT/'generated'/n,t)
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated={n:hashlib.sha256(t.encode()).hexdigest() for n,t in generated.items()},
        helpers={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OWN.glob('*') if p.suffix in ('.h','.cpp')},remote_control_enabled=True,application_remotes_implemented=False),indent=2)+'\n')

def includes():
    from prepare_randomizer_options import includes as option_includes
    return [OUT/'generated/soh']+option_includes()

def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/randomizer-options-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    flags[1:1]=['/DENABLE_REMOTE_CONTROL','/I'+str(OUT/'generated/soh')]
    probe=folder/'declarations.cpp';stable(probe,'#include "soh/Network/CrowdControl/CrowdControl.h"\n#include "soh/Network/Sail/Sail.h"\n#include "soh/Network/Anchor/Anchor.h"\nvoid Probe(){Network value((Shipyard::SohUI::ValueInit()));Anchor a((Shipyard::SohUI::ValueInit()));}\n')
    rows=[]
    for path in [OWN/'transport.cpp',OUT/'generated'/BASE/'Network.cpp',OUT/'generated'/BASE/'Anchor/AnchorConstants.cpp',probe]:
        obj=folder/(path.stem+'.obj');command=flags+[str(path),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        rows.append(dict(source=path.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,production=path!=probe,
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None))
        print(path.name,r.returncode)
        if r.returncode:print('\n'.join(s for s in r.stdout.splitlines() if 'error ' in s)[:4500])
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args()
    build() if a.build else prepare()
