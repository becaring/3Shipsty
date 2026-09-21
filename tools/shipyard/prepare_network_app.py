"""Complete current Anchor, Sail, Crowd Control and network menu projection."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_application_windows import containers,includes as window_includes,SYNTAX,PAIR_BINDINGS
from prepare_enhancements import transform as enhancement_syntax
from prepare_custom_message import escape_literal
from prepare_soh_ui import common,value_expressions
from prepare_network import value_expressions as network_values
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/network-app';OUT=ROOT/'scratch/network-app-xdk'
BASE='soh/soh/Network/'

def sha(t):return hashlib.sha256(t.encode()).hexdigest()

def notifications(text):
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='call_expression' or n.child_by_field_name('function').text!=b'Notification::Emit':continue
        args=n.child_by_field_name('arguments').named_children
        if len(args)!=1 or args[0].type!='initializer_list':continue
        values=[]
        for value in args[0].named_children:
            if value.type=='comment':continue
            assert value.type=='initializer_pair',value.text
            field=value.child_by_field_name('designator');expr=value.child_by_field_name('value')
            assert field and expr,value.text
            values.append('notification'+field.text.decode()+' = '+expr.text.decode()+';')
        assert n.parent.type=='expression_statement'
        edits.append((n.parent.start_byte,n.parent.end_byte,'{ Notification::Options notification; '+''.join(values)+' Notification::Emit(notification); }'))
    return edits_apply(raw,edits)

def json_header(text):
    read_types=re.findall(r'inline void from_json\(const json& j, (\w+)&',text)
    write_types=re.findall(r'inline void to_json\(json& j, const (\w+)&',text)
    assert len(read_types)==12 and len(write_types)==11,(read_types,write_types)
    pre='\n'.join('inline void from_json(const json&, '+t+'&);' for t in read_types)+'\n'
    pre+='\n'.join('inline void to_json(json&, const '+t+'&);' for t in write_types)+'\n'
    pre+='template<class T> inline json ShipyardNetworkToJson(const T& value){return json(value);}\n'
    pre+='\n'.join('inline json ShipyardNetworkToJson(const '+t+'& value){json result;to_json(result,value);return result;}' for t in write_types)+'\n'
    pre+='namespace nlohmann {\n'
    for t in read_types:
        pre+='template<> inline '+t+'& json::get_to<'+t+'>('+t+'& value) const {::from_json(*this,value);return value;}\n'
    pre+='namespace detail {\n'
    for t in read_types:
        pre+='template<> struct conversion<'+t+'> {static '+t+' get(const json& j){'+t+' value = {};::from_json(j,value);return value;}};\n'
    pre+='}}\n'
    text=once(text,'using json = nlohmann::json;','typedef nlohmann::json json;\n'+pre)
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='compound_literal_expression':continue
        typ=n.child_by_field_name('type');value=n.child_by_field_name('value')
        if typ.text!=b'json':continue
        rows=[v for v in value.named_children if v.type!='comment'];lines=['[&]() -> json { json value = json::object();']
        for row in rows:
            assert row.type=='initializer_list' and len(row.named_children)==2,row.text
            key,val=row.named_children;lines.append('value['+key.text.decode()+'] = ShipyardNetworkToJson('+val.text.decode()+');')
        lines.append('return value; }()');edits.append((n.start_byte,n.end_byte,' '.join(lines)))
    assert len(edits)==11,len(edits)
    text=edits_apply(raw,edits)
    text=text.replace('Color_RGB8{ 255, 255, 255 }','ShipyardRGB(255,255,255)')
    return text

def project(name,text):
    directory=Path(name).parent.as_posix().removeprefix('soh/')
    text=re.sub(r'#include "([^/\"]+\.(?:h|hpp))"',lambda m:'#include "'+directory+'/'+m[1]+'"' if (ROOT/Path(name).parent/m[1]).exists() else m[0],text)
    text=text.replace('#include <libultraship/libultraship.h>','#include <ship/Context.h>\n#include <ship/window/gui/Gui.h>\n#include <libultraship/bridge.h>')
    if name.endswith('JsonConversions.hpp'):text=json_header(text)
    text=PAIR_BINDINGS(text.encode()).decode()
    text=enhancement_syntax(name,text)
    text=text.replace('std::lock_guard<std::mutex>','Shipyard::Async::lock_guard<Shipyard::Async::mutex>')
    if name.endswith('/CrowdControl.cpp'):
        text=once(text,'std::thread(&CrowdControl::ProcessActiveEffects, this)','Shipyard::Async::make_thread([this](){this->ProcessActiveEffects();})')
        text=once(text,'std::this_thread::sleep_for(std::chrono::seconds(1));','Sleep(1000);')
    text=network_values(text)
    text=notifications(text)
    text=text.replace('CVarGetColor24(CVAR_REMOTE_ANCHOR("Color.Value"), { 100, 255, 100 })','CVarGetColor24(CVAR_REMOTE_ANCHOR("Color.Value"), ShipyardRGB(100,255,100))')
    text=text.replace('CVarGetColor(CVAR_REMOTE_ANCHOR("Color.Value"), { 100, 255, 100 })','CVarGetColor(CVAR_REMOTE_ANCHOR("Color.Value"), ShipyardRGBA(100,255,100,0))')
    text=text.replace('std::reinterpret_pointer_cast<','ShipyardNetworkReinterpret<')
    text=re.sub(r'\.(PlaceholderText|DefaultValue)\(("[^"\\]*(?:\\.[^"\\]*)*")\)',r'.\1(std::string(\2))',text)
    if name.endswith('/CrowdControl.cpp'):
        text=re.sub(r'std::make_unique<(GameInteractionEffect::\w+)>\(\)',r'ShipyardNetworkMakeUnique<\1>()',text)
        text=once(text,'payload["status"] = status;','payload["status"] = static_cast<int>(status);')
    if name.endswith('/Anchor.cpp'):
        text=once(text,'uint32_t clientId = 0;','uint32_t clientId;\n    explicit DummyPlayerClientId(uint32_t value=0) : clientId(value) {}')
        text=once(text,'DummyPlayerClientId{ clientId }','DummyPlayerClientId(clientId)')
    if name.endswith('/UpdateTeamState.cpp'):
        text=once(text,'ceil((RAND_INF_MAX + 15) / 16)','ceil(static_cast<double>((RAND_INF_MAX + 15) / 16))')
    if name.endswith('/UpdateClientState.cpp'):
        text=once(text,'payload["sceneNum"] = SCENE_ID_MAX;','payload["sceneNum"] = static_cast<int>(SCENE_ID_MAX);')
    if name.endswith('/TeleportTo.cpp'):
        text=once(text,'payload["posRot"] = player->actor.world;','payload["posRot"] = ShipyardNetworkToJson(player->actor.world);')
    if name.endswith('/DummyPlayer.cpp'):
        text=once(text,'NameTag_RegisterForActorWithOptions(actor, client.name.c_str(), {});','NameTag_RegisterForActorWithOptions(actor, client.name.c_str(), ShipyardNetworkZero<NameTagOptions>());')
    text=re.sub(r'(WidgetPath path) = \{([^{}]*)\};',r'\1(\2);',text)
    text=re.sub(r'\bpath = \{([^{}]*)\};',r'path = WidgetPath(\1);',text)
    text=text.replace('PosRot{ 0 }','ShipyardNetworkZero<PosRot>()').replace('Vec3s{ 0 }','ShipyardNetworkZero<Vec3s>()').replace('std::vector<int>{}','std::vector<int>()')
    # These assignments invoke the original ADL serializers through an explicit
    # overload, retaining the existing JSON object and packet schemas.
    if name.endswith('/PlayerUpdate.cpp'):
        for expr in ('player->actor.world.pos','player->actor.shape.rot','player->skelAnime.prevTransl','player->upperLimbRot'):
            text=once(text,'= '+expr+';','= ShipyardNetworkToJson('+expr+');')
    if name.endswith('/UpdateTeamState.cpp'):text=once(text,'payload["state"] = gSaveContext;','payload["state"] = ShipyardNetworkToJson(gSaveContext);')
    if name.endswith('/UpdateClientState.cpp'):
        text=once(text,'CVarGetColor24(CVAR_REMOTE_ANCHOR("Color.Value"), ShipyardRGB(100,255,100))','ShipyardNetworkToJson(CVarGetColor24(CVAR_REMOTE_ANCHOR("Color.Value"), ShipyardRGB(100,255,100)))')
    text=containers(text);text=common(value_expressions(SYNTAX(text,set())))
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='string_literal' and any(b>=128 for b in n.text):edits.append((n.start_byte,n.end_byte,escape_literal(n.text.decode())))
    text=edits_apply(raw,edits)
    return '#include "network-app/support.h"\n'+text

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());generated={}
    for n,digest in lock['sources'].items():
        text=(ROOT/n).read_text(encoding='utf-8-sig');assert sha(text)==digest,n
        text=project(n,text);stable(OUT/'generated'/n,text);generated[n]=sha(text)
    helpers=[ROOT/'tools/shipyard'/n for n in ('prepare_application_windows.py','prepare_enhancements.py','prepare_custom_message.py','prepare_randomizer.py','prepare_network.py','prepare_soh_ui.py','cpp_ast.py')]+[ROOT/'platform/shipyard/input/lowering.py',OWN/'support.h']
    units=[n for n in lock['sources'] if n.endswith('.cpp')]
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated=generated,full_units=units,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helpers={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}),indent=2)+'\n')
    return units

def includes():return [OUT/'generated/soh',ROOT/'scratch/object-extension-xdk/generated/soh']+window_includes()

def build(selected=None):
    units=prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    roots=list(dict.fromkeys(includes()+[Path(f[2:]) for f in flags if f.startswith('/I')]))
    roots.sort(key=lambda p:2 if p.is_relative_to(ROOT/'soh') else 1 if p.is_relative_to(ROOT/'scratch/game-xdk') else 0)
    flags=[f for f in flags if not f.startswith('/I')];flags[1:1]=['/I'+str(p) for p in roots];rows=[]
    if selected:units=[n for n in units if Path(n).stem in selected]
    previous=json.loads((folder/'build.json').read_text()) if selected and (folder/'build.json').exists() else []
    def compile_unit(n):
        source=OUT/'generated'/n;obj=folder/(source.stem+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        else:print('\n'.join(s for s in (r.stdout+r.stderr).splitlines() if 'error ' in s)[:1800])
        print(source.stem+': '+str(r.returncode),flush=True)
        return row
    with ThreadPoolExecutor(max_workers=3) as workers:rows=list(workers.map(compile_unit,units))
    changed={r['source'] for r in rows};rows=[r for r in previous if r['source'] not in changed]+rows
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--units',nargs='+');a=p.parse_args();build(a.units) if a.build else prepare()
