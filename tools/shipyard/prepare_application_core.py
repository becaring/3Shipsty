"""Project complete modern scene/message/resource bridges and application utilities."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_application_windows import containers,includes as window_includes,SYNTAX
from prepare_enhancements import transform as enhancement_syntax
from prepare_custom_message import escape_literal
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/application-core';OUT=ROOT/'scratch/application-core-xdk'
UNITS=['soh/soh/'+n for n in ('ResourceManagerHelpers.cpp','z_message_OTR.cpp','z_play_otr.cpp','z_scene_otr.cpp','GbiWrap.cpp','util.cpp','CrashHandlerExt.cpp','Notification/Notification.cpp')]

def sha(t):return hashlib.sha256(t.encode()).hexdigest()

def project(name,text):
    # Canonical projected headers are selected by full application include paths.
    directory=Path(name).parent.as_posix().removeprefix('soh/')
    text=re.sub(r'#include "([^/\"]+\.h)"',lambda m:'#include "'+directory+'/'+m[1]+'"' if (ROOT/Path(name).parent/m[1]).exists() else m[0],text)
    text=re.sub(r'#include "((?:Enhancements|resource)/[^\"]+)"',r'#include "soh/\1"',text)
    text=text.replace('#include <libultraship/libultraship.h>','#include <ship/Context.h>\n#include <ship/resource/ResourceManager.h>\n#include <ship/window/gui/Gui.h>\n#include <libultraship/bridge.h>')
    text=enhancement_syntax(name,text)
    if name.endswith('/z_message_OTR.cpp'):
        text=once(text,'auto existingEntry = std::find_if(table, table + tableSize, [id = file->messages[j].id](const auto& entry)',
                  'const uint16_t id = file->messages[j].id;\n            auto existingEntry = std::find_if(table, table + tableSize, [id](const MessageTableEntry& entry)')
    if name.endswith('/ResourceManagerHelpers.cpp'):
        text='#include "soh/Enhancements/randomizer/SeedContext.h"\n#include <fast/resource/type/Texture.h>\n#include <fast/interpreter.h>\n#include <stb_image.h>\n'+text
        text=once(text,'pathStr.starts_with(sOtr)','Shipyard::Resources::starts_with(pathStr,sOtr)')
        raw=text.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type!='assignment_expression':continue
            right=n.child_by_field_name('right');left=n.child_by_field_name('left')
            if right.type=='initializer_list' and left.text.startswith(b'originalGfx['):
                assert n.parent.type=='expression_statement'
                edits.append((n.parent.start_byte,n.parent.end_byte,'{ const GfxPatch patch = '+right.text.decode()+'; '+left.text.decode()+' = patch; }'))
        assert len(edits)==3
        text=edits_apply(raw,edits)
    if name.endswith('/CrashHandlerExt.cpp'):
        text=re.sub(r'(static std::array<[^;{}]+> \w+)\{',r'\1 = {',text)
        text=text.replace('snprintf(', 'Shipyard::SohResources::snprintf(')
        text='#include "soh-resources/format.h"\n'+text
    if name.endswith('/z_scene_otr.cpp'):
        text=text.replace('(int)cmdCode','static_cast<int>(cmdCode.GetValue())')
    text=containers(text)
    text=SYNTAX(text,set())
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='string_literal' and any(b>=128 for b in n.text):edits.append((n.start_byte,n.end_byte,escape_literal(n.text.decode())))
    text=edits_apply(raw,edits)
    return '#include "input/compiler.h"\n#include "application-windows/support.h"\n#include "resources/runtime_support.h"\n#include "soh/cvar_prefixes.h"\n#include <spdlog/spdlog.h>\n'+text

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());generated={}
    for n,digest in lock['sources'].items():
        text=(ROOT/n).read_text(encoding='utf-8-sig');assert sha(text)==digest,n
        text=project(n,text);stable(OUT/'generated'/n,text);generated[n]=sha(text)
    helpers=[ROOT/'tools/shipyard'/n for n in ('prepare_application_windows.py','prepare_enhancements.py','prepare_custom_message.py','prepare_randomizer.py','prepare_resource_manager.py','cpp_ast.py')]+[ROOT/'platform/shipyard/input/lowering.py']
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated=generated,full_units=UNITS,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helpers={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}),indent=2)+'\n')

def includes():return [OUT/'generated/soh']+window_includes()

def build():
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    roots=list(dict.fromkeys(includes()+[Path(f[2:]) for f in flags if f.startswith('/I')]))
    roots.sort(key=lambda p:2 if p.is_relative_to(ROOT/'soh') else 1 if p.is_relative_to(ROOT/'scratch/game-xdk') else 0)
    flags=[f for f in flags if not f.startswith('/I')];flags[1:1]=['/I'+str(p) for p in roots];rows=[]
    for n in UNITS:
        source=OUT/'generated'/n;obj=folder/(source.stem+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        else:print('\n'.join(s for s in (r.stdout+r.stderr).splitlines() if 'error ' in s)[:2400])
        rows.append(row);print(source.stem+': '+str(r.returncode),flush=True)
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
