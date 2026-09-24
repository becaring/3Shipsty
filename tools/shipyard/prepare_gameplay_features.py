"""Complete pinned gameplay enhancement batch against canonical native providers."""
import argparse,hashlib,json,re,runpy,struct,subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_enhancements import transform as enhancement_transform
from prepare_randomizer import edits_apply
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/gameplay-features';OUT=ROOT/'scratch/gameplay-features-xdk'
from platform_base import resolve as resolve_platform_base
resolve_platform_base(ROOT)
from xbox360_platform.cpp_syntax import lower_if_initializers
def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def project(name,text):
    if name.endswith('/WeirdAnimation.h'):
        text=text.replace('#include <optional>','#include <xbox_compat/optional.h>').replace('std::optional<','xbox_compat::optional<').replace('std::byte','unsigned char')
        text=once(text,'enum class IndexDirection {','enum IndexDirection {')
        return text
    text=text.replace('overrideBlueWarpDestinations','shipyard_original_overrideBlueWarpDestinations')
    if name.endswith('/FileSelectMoreInfo.cpp'):
        text=once(text,'#include "macros.h"','#include "gameplay-features/interpolation_scope.h"')
    lowering=runpy.run_path(str(ROOT/'platform/shipyard/input/lowering.py'))
    text=lowering['pair_bindings'](text.encode()).decode()
    raw=text.encode();edits=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type=='preproc_function_def':
            replacement=re.sub(r'\b(COND_HOOK|COND_ID_HOOK|COND_VB_SHOULD|REGISTER_VB_SHOULD)\b',r'SHIPYARD_MACRO_\1',node.text.decode())
            edits.append((node.start_byte,node.end_byte,replacement))
    text=edits_apply(raw,edits)
    text=enhancement_transform(name,text)
    text=text.replace('SHIPYARD_MACRO_','')
    text=text.replace('shipyard_original_overrideBlueWarpDestinations','overrideBlueWarpDestinations')
    text=re.sub(r'\bconstexpr\b','const',text)
    # The umbrella imports desktop backends; these actual subsystem headers
    # retain the current LUS platform interfaces without a replacement facade.
    text=text.replace('#include <libultraship/libultraship.h>','#include "soh/SohGui/UIWidgets.hpp"\n#include "ship/controller/controldeck/ControlDeck.h"\n#include "ship/controller/controldevice/controller/Controller.h"')
    text=text.replace('#include "FileSelectEnhancements.h"','#include "soh/Enhancements/FileSelectEnhancements.h"').replace('#include "AudioCollection.h"','#include "soh/Enhancements/audio/AudioCollection.h"')
    text=re.sub(r'(std::vector<\w+> \w+) = \{\};',r'\1;',text)
    text=re.sub(r'WidgetPath (\w+) = \{([^{}]+)\};',r'WidgetPath \1(\2);',text)
    text=re.sub(r'(COND_HOOK\()GameInteractor::',r'\1',text)
    if name.endswith('/SunlightArrows.cpp'):
        text=once(text,'bool activatedByLightArrow = false;','SunlightArrowData():activatedByLightArrow(false){}\n bool activatedByLightArrow;').replace('SunlightArrowData{}','SunlightArrowData()')
    if 'std::reinterpret_pointer_cast<' in text:
        text='#include "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"\n#include "ship/window/gui/ConsoleWindow.h"\n#include "gui/compat.h"\n'+text.replace('std::reinterpret_pointer_cast<','Shipyard::GuiCompat::ReinterpretPointerCast<')
    if name.endswith('/WeirdAnimation.cpp'):
        text=text.replace('auto& animation = animationData.emplace();','animationData.reset(); animationData = std::vector<unsigned char>();\n    auto& animation = *animationData;')
        text=text.replace('std::end(*animationData)','animationData->end()').replace('std::begin(*animationData)','animationData->begin()')
        text=text.replace('const auto directionStr = [this] {','const auto directionStr = [this]() -> const char* {')
    text=text.replace('std::optional<','xbox_compat::optional<')
    if name.endswith('/FileSelectEnhancements.cpp'):text=text.replace('static_pointer_cast<SohModalWindow>','std::static_pointer_cast<SohModalWindow>')
    if name.endswith('/GraveHoleJumps.cpp'):text='#include "ship/Context.h"\n#include "ship/resource/ResourceManager.h"\n'+text
    if name.endswith('/GraveHoleJumps.cpp'):
        text=re.sub(r'\{ \{ (\d+), (\d+) \}, \{ (\d+), (\w+) \} \}',r'std::make_pair(std::make_pair<u16,u16>(\1,\2),std::make_pair<u16,u16>(\3,\4))',text)
    if name.endswith('/DaytimeGS.cpp') or name.endswith('/N64WeirdFrames.cpp'):
        text=nested_vectors(name,text)
    if name.endswith('/Warping.cpp'):text='#include "ship/Context.h"\n#include "ship/config/Config.h"\n#include "soh/SohGui/UIWidgets.hpp"\n'+warping(text)
    from prepare_soh_ui import maps,value_expressions
    text=maps(text);text=value_expressions(text)
    raw=text.encode();edits=[]
    for node in walk(PARSER.parse(raw).root_node):
        if node.type=='declaration':
            typ=node.child_by_field_name('type');init=next((n for n in node.named_children if n.type=='init_declarator'),None)
            if typ is not None and typ.text.startswith(b'std::set<') and init is not None:
                value=init.child_by_field_name('value');ident=init.child_by_field_name('declarator')
                if value is not None and value.type=='initializer_list':
                    element=typ.text.decode()[9:-1];array='ShipyardSetValues'+str(node.start_byte)
                    edits.append((node.start_byte,node.start_byte,'static const '+element+' '+array+'[]='+value.text.decode()+';\n'))
                    edits.append((ident.end_byte,value.end_byte,'('+array+','+array+'+sizeof('+array+')/sizeof('+array+'[0]))'))
        if node.type=='call_expression':
            fn=node.child_by_field_name('function');args=node.child_by_field_name('arguments')
            option=None;val=None
            if fn.text==b'Notification::Emit' and args.named_children and args.named_children[0].type=='initializer_list':option='Notification::Options';val=args.named_children[0]
            if fn.text in (b'UIWidgets::Button',b'UIWidgets::InputString') and args.named_children[-1].type=='initializer_list':option='UIWidgets::ButtonOptions' if fn.text==b'UIWidgets::Button' else 'UIWidgets::InputOptions';val=args.named_children[-1]
            if val is not None:
                assign=[]
                for entry in val.named_children:
                    if entry.type=='comment':continue
                    field=next(n for n in walk(entry) if n.type=='field_identifier').text.decode();v=entry.child_by_field_name('value')
                    assign.append('notification.'+field+'='+v.text.decode()+';')
                ctor=';' if option=='Notification::Options' else '((Shipyard::SohUI::ValueInit()));'
                edits.append((val.start_byte,val.end_byte,'[&]() -> '+option+' { '+option+' notification'+ctor+' '+' '.join(assign)+' return notification; }()'))
            if fn.text.startswith(b'gs') and node.parent.type=='argument_list':
                ancestor=node.parent;local=False
                while ancestor:
                    if ancestor.type in ('function_definition','lambda_expression'):local=True;break
                    ancestor=ancestor.parent
                if local:edits.append((node.start_byte,node.end_byte,' [&]() -> Gfx { Gfx value = '+node.text.decode()+'; return value; }()'))
                else:
                    declaration=node
                    while declaration.parent.type!='translation_unit':declaration=declaration.parent
                    value='shipyardGfxValue'+str(node.start_byte)
                    edits.append((declaration.start_byte,declaration.start_byte,'static Gfx '+value+' = '+node.text.decode()+';\n'))
                    edits.append((node.start_byte,node.end_byte,value))
            if fn.type=='field_expression' and fn.child_by_field_name('field').text==b'Replace':
                for a in args.named_children:
                    if a.type in ('string_literal','concatenated_string'):edits.append((a.start_byte,a.end_byte,'std::string('+a.text.decode()+')'))
    text=edits_apply(raw,edits)
    text=re.sub(r'\{ \.r = (\d+), \.g = (\d+), \.b = (\d+), \.a = (\d+) \}',r'{ \1, \2, \3, \4 }',text)
    text=re.sub(r'Color_RGB8\{([^{}]+)\}',r'Shipyard::GameplayFeatures::Rgb(\1)',text)
    if name.endswith('/EnemyRandomizer.cpp'):
        text=once(text,'struct CustomStalfosPairFightData {','struct CustomStalfosPairFightData {\n CustomStalfosPairFightData():moriBigst(nullptr),originalDestroy(nullptr){}\n CustomStalfosPairFightData(BgMoriBigst* actor,ActorFunc destroy):moriBigst(actor),originalDestroy(destroy){}')
        text=text.replace('moriBigst = nullptr;','moriBigst;').replace('originalDestroy = nullptr;','originalDestroy;')
        text=re.sub(r'CustomStalfosPairFightData\{\s*\.moriBigst = ([^,]+),\s*\.originalDestroy = ([^}]+)\}',r'CustomStalfosPairFightData(\1,\2)',text)
    if name.endswith('/DisableFixedCamera.cpp'):
        text=once(text,'struct CamDataBackup {','struct CamDataBackup {\n CamDataBackup():original(nullptr),copy(nullptr),len(0),active(false){}')
        text=text.replace('CamData* original = nullptr;','CamData* original;').replace('CamData* copy = nullptr;','CamData* copy;').replace('size_t len = 0;','size_t len;').replace('bool active = false;','bool active;')
    text=lowering['syntax'](text,{'IndexDirection'}).replace('fmax(', 'Shipyard::GameplayFeatures::Fmax(')
    from prepare_custom_message import escape_literal
    text=lower_if_initializers(text,PARSER,walk,max_depth=3)
    raw=text.encode();edits=[(n.start_byte,n.end_byte,escape_literal(n.text.decode())) for n in walk(PARSER.parse(raw).root_node) if n.type=='string_literal' and any(c>=128 for c in n.text)]
    prefix='#include "gameplay-features/support.h"\n#include "soh/Enhancements/game-interactor/GameInteractor_Hooks.h"\n'
    if 'RAND_GET_OPTION' in text or 'Rando::Context' in text:prefix+='#include "soh/Enhancements/randomizer/SeedContext.h"\n'
    if 'gRandomizer' in text:prefix+='#include "soh/Enhancements/randomizer/randomizer.h"\n'
    if 'CustomMessage' in text or 'TEXT_' in text:prefix+='#include "soh/Enhancements/custom-message/CustomMessageManager.h"\n#include "soh/Enhancements/custom-message/CustomMessageTypes.h"\n'
    if 'RegisterShipInitFunc' in text:prefix+='#include "soh/ShipInit.hpp"\n'
    if 'ICON_FA_' in text:prefix+='#include "ship/window/gui/IconsFontAwesome4.h"\n'
    return prefix+edits_apply(raw,edits)

def nested_vectors(name,text):
    daytime=name.endswith('/DaytimeGS.cpp');ident='dayTimeGoldSkulltulas' if daytime else 'weirdAnimations';typ='DayTimeGoldSkulltulas' if daytime else 'WeirdAnimation'
    text=text.replace('using DayTimeGoldSkulltulasList = std::vector<DayTimeGoldSkulltulas>;','typedef std::vector<DayTimeGoldSkulltulas> DayTimeGoldSkulltulasList;')
    raw=text.encode();init=next(n for n in walk(PARSER.parse(raw).root_node) if n.type=='init_declarator' and n.child_by_field_name('declarator').text.decode()==ident);value=init.child_by_field_name('value');helper='Make'+ident
    lines=['static std::vector<'+typ+'> '+helper+'(){ std::vector<'+typ+'> result;']
    for i,row in enumerate(n for n in value.named_children if n.type!='comment'):
        values=[c for c in row.named_children if c.type!='comment'];a='values'+str(i);element='ActorEntry' if daytime else 'std::string'
        lines.append('const '+element+' '+a+'[]='+values[3].text.decode()+';')
        args=','.join(v.text.decode() for v in values[:3])+',std::vector<'+element+'>('+a+','+a+'+sizeof('+a+')/sizeof('+a+'[0]))'
        if daytime:lines.append(typ+' row'+str(i)+'={'+args+'}; result.push_back(row'+str(i)+');')
        else:lines.append('result.push_back('+typ+'('+args+'));')
    lines.append('return result;}\n');declaration=init.parent
    insertion=next(n.start_byte for n in walk(PARSER.parse(raw).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.startswith(b'OnSpawnNighttimeGoldSkulltula')) if daytime else declaration.start_byte
    replacement=' = '+helper+'()'
    return edits_apply(raw,[(insertion,insertion,'\n'.join(lines)),(init.child_by_field_name('declarator').end_byte,value.end_byte,replacement)])

def warping(text):
    for typ in ('Vec3f','WarpPoint'):
        m=re.search(r'NLOHMANN_DEFINE_TYPE_NON_INTRUSIVE\('+typ+r', ([^\n]+)\)',text);fields=[v.strip() for v in m[1].split(',')]
        encoder='static nlohmann::json Encode'+typ+'(const '+typ+'& value){nlohmann::json result=nlohmann::json::object();'
        decoder='static '+typ+' Decode'+typ+'(const nlohmann::json& j){ '+typ+' value;'
        for field in fields:
            encoder+='result["'+field+'"]='+('EncodeVec3f(value.pos)' if field=='pos' else 'value.'+field)+';'
            fieldtype='f32' if typ=='Vec3f' else {'entranceId':'s32','roomNum':'s8','rotY':'s16','bootToPoint':'bool','pos':'Vec3f'}[field]
            decoder+='value.'+field+'='+('DecodeVec3f(j.at("pos"))' if field=='pos' else 'j.at("'+field+'").get<'+fieldtype+'>()')+';'
        text=text[:m.start()]+encoder+'return result;}\n'+decoder+'return value;}\n'+text[m.end():]
    at=text.index('std::map<std::string, WarpPoint> warpPoints;')
    helpers='''static nlohmann::json EncodeWarpPoints(const std::map<std::string,WarpPoint>& values){nlohmann::json result=nlohmann::json::object();for(std::map<std::string,WarpPoint>::const_iterator it=values.begin();it!=values.end();++it)result[it->first]=EncodeWarpPoint(it->second);return result;}
static std::map<std::string,WarpPoint> DecodeWarpPoints(const nlohmann::json& j){if(!j.is_object())throw nlohmann::json::type_error(302,"type must be object");std::map<std::string,WarpPoint> result;for(nlohmann::json::const_iterator it=j.begin();it!=j.end();++it)result[it.key()]=DecodeWarpPoint(it.value());return result;}
'''
    text=text[:at]+helpers+text[at:];text=text.replace('warpPoints = allConfig["WarpPoints"];','warpPoints = DecodeWarpPoints(allConfig["WarpPoints"]);').replace('allConfig["WarpPoints"] = warpPoints;','allConfig["WarpPoints"] = EncodeWarpPoints(warpPoints);').replace('SetBlock("WarpPoints", warpPoints)','SetBlock("WarpPoints", EncodeWarpPoints(warpPoints))')
    m=re.search(r'WarpPoint\{\s*\.entranceId = ([^,]+),\s*\.roomNum = ([^,]+),\s*\.pos = ([^,]+),\s*\.rotY = ([^,]+),\s*\}',text)
    if not m:raise ValueError('Warp point value drift')
    text=text[:m.start()]+'[&]() -> WarpPoint {WarpPoint point={};point.entranceId='+m[1]+';point.roomNum='+m[2]+';point.pos='+m[3]+';point.rotY='+m[4]+';return point;}()'+text[m.end():]
    return text
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());outputs={}
    for name,digest in lock.get('dependencies',{}).items():
        if sha((ROOT/name).read_text(encoding='utf-8-sig'))!=digest:raise ValueError('Gameplay dependency source drift '+name)
    macros=(ROOT/'soh/include/macros.h').read_text(encoding='utf-8-sig')
    start=macros.index('#ifndef NDEBUG\n#define OPEN_DISPS')
    scope=macros[start:macros.index('// #endregion',start)]
    for declaration in ('void FrameInterpolation_RecordOpenChild(const void* a, int b);',
                        'void FrameInterpolation_RecordCloseChild(void);'):
        assert scope.count(declaration)==2
        scope=scope.replace(declaration,'')
    # XDK loses C linkage for a block-scope declaration inside a lambda. Use
    # the actual namespace-scope C declarations; retain both original macro
    # bodies, including recording, debug scopes, source location and ordering.
    scope='#pragma once\n#include "macros.h"\n#include "soh/frame_interpolation.h"\n#undef OPEN_DISPS\n#undef CLOSE_DISPS\n'+scope
    stable(OUT/'generated/soh/gameplay-features/interpolation_scope.h',scope)
    outputs['soh/gameplay-features/interpolation_scope.h']=sha(scope)
    for name,digest in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if sha(text)!=digest:raise ValueError('Gameplay feature source drift '+name)
        text=project(name,text);stable(OUT/'generated'/name,text);outputs[name]=sha(text)
    helpers=[ROOT/'tools/shipyard'/n for n in ('prepare_archives.py','prepare_configuration.py','prepare_enhancements.py','prepare_game_interactor.py','prepare_resource_manager.py','prepare_custom_message.py','prepare_soh_ui.py','prepare_randomizer.py','cpp_ast.py')]+[ROOT/'platform/shipyard/imgui/projection.py',ROOT/'platform/shipyard/input/lowering.py',OWN/'support.h']
    stable(OUT/'manifest.json',json.dumps(dict(source_commit=lock['source_commit'],sources=lock['sources'],dependencies=lock.get('dependencies',{}),generated=outputs,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),projection_helpers={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}),indent=2)+'\n')
    return [n for n in outputs if n.endswith('.cpp')]
def includes():
    from prepare_application_editors import includes as base
    return [OUT/'generated/soh',ROOT/'scratch/save-manager-xdk/generated/soh',ROOT/'scratch/save-storage-xdk/generated/soh',ROOT/'scratch/object-extension-xdk/generated/soh']+base()
def build(only=None,failed=False):
    units=prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2];flags[1:1]=['/I'+str(p) for p in includes()]
    previous=json.loads((folder/'build.json').read_text()) if (only or failed) and (folder/'build.json').exists() else []
    if only:units=[n for n in units if only in n]
    if failed:units=[n for n in units if any(r.get('path')==n and (r['exit'] or r['source_sha256']!=hashlib.sha256((OUT/'generated'/n).read_bytes()).hexdigest()) for r in previous)]
    def compile(name):
        source=OUT/'generated'/name;obj=folder/(source.stem+'_'+hashlib.sha256(name.encode()).hexdigest()[:8]+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        row=dict(path=name,source=source.relative_to(ROOT).as_posix(),object=obj.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        return row
    rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(compile,n) for n in units]):
            row=f.result();rows.append(row)
            if row['exit']:print(row['path']+': FAILED',flush=True)
            elif len(rows)%10==0:print('Compiled '+str(len(rows))+'/'+str(len(units)),flush=True)
            changed={r['path'] for r in rows};stable(folder/'build.json',json.dumps(sorted([r for r in previous if r['path'] not in changed]+rows,key=lambda r:r['path']),indent=2)+'\n')
    changed={r['path'] for r in rows};rows=[r for r in previous if r['path'] not in changed]+rows
    errors=[dict(path=r['path'],errors=[s for s in (ROOT/r['object']).with_suffix('.log').read_text().splitlines() if 'error ' in s]) for r in rows if r['exit']]
    stable(folder/'errors.json',json.dumps(errors,indent=2)+'\n');print('Compiled '+str(len(rows)-len(errors))+'/'+str(len(rows))+' units.',flush=True)
    if errors:raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--only');p.add_argument('--failed',action='store_true');a=p.parse_args();build(a.only,a.failed) if a.build else prepare()
