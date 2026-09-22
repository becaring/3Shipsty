"""Complete current randomizer hooks, messages, gameplay and tracker application."""
import argparse,hashlib,json,re,struct,subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_gameplay_features import project as feature_project,includes as feature_includes
from prepare_application_windows import containers
from prepare_randomizer import lower_defaults,edits_apply
from prepare_randomizer_item import inventory
from prepare_custom_message import lower_literals
from cpp_ast import PARSER,walk
from prepare_randomizer_content import expressions as content_expressions,kids
from prepare_filesystem import project_boundary
OWN=ROOT/'platform/shipyard/randomizer-application';OUT=ROOT/'scratch/randomizer-application-xdk';BASE='soh/soh/Enhancements/randomizer/'

def sha(t):return hashlib.sha256(t.encode()).hexdigest()

def values(node,typ):
    fields=kids(node)
    return ('Shipyard::RandomizerContent::Values<'+typ+'>('+str(len(fields))+')'+''.join('.Add('+c.text.decode()+')' for c in fields)+'.Finish()') if fields else 'std::vector<'+typ+'>()'

def initializers(name,text):
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='alias_declaration':
            ident=n.child_by_field_name('name');typ=n.child_by_field_name('type')
            edits.append((n.start_byte,n.end_byte,'typedef '+typ.text.decode()+' '+ident.text.decode()+';'))
        if n.type=='assignment_expression':
            left=n.child_by_field_name('left');right=n.child_by_field_name('right')
            if right.type=='initializer_list':
                if name.endswith('/ItemMessages.cpp') and left.text==b'msg':replacement='CustomMessage('+','.join(c.text.decode() for c in kids(right))+')'
                elif name.endswith('/Traps.cpp') and left.text.startswith(b'trickNameTable['):replacement=values(right,'Text')
                elif name.endswith('/draw.cpp') and left.text==b'aButtonColor':replacement='Shipyard::GameplayFeatures::Rgb('+','.join(c.text.decode() for c in kids(right))+')'
                else:continue
                edits.append((right.start_byte,right.end_byte,replacement))
            elif right.text in (b'GET_ITEM_NONE',b'GET_ITEM_MYSTERY'):
                assert n.parent.type=='expression_statement'
                edits.append((n.parent.start_byte,n.parent.end_byte,'{ const GetItemEntry value = '+right.text.decode()+'; '+left.text.decode()+' = value; }'))
        if n.type=='declaration' and n.child_by_field_name('type') is not None:
            typ=n.child_by_field_name('type').text
            if typ==b'CustomMessage':
                init=n.child_by_field_name('declarator')
                if init is not None and init.type=='init_declarator' and init.child_by_field_name('declarator').type=='array_declarator':
                    for row in kids(init.child_by_field_name('value')):
                        if row.type=='initializer_list':edits.append((row.start_byte,row.end_byte,'CustomMessage('+','.join(c.text.decode() for c in kids(row))+')'))
            if typ.startswith((b'std::map<',b'std::unordered_map<',b'std::vector<')):
                init=n.child_by_field_name('declarator')
                if init is not None and init.type=='init_declarator':
                    val=init.child_by_field_name('value')
                    if val is not None and val.type=='initializer_list' and not any(c.type=='=' for c in init.children):edits.append((val.start_byte,val.start_byte,' = '))
                    if typ==b'std::map<SceneDoorParamsPair, RandomizerInf>' and val is not None:
                        for row in kids(val):
                            key=kids(row)[0]
                            edits.append((key.start_byte,key.end_byte,'SceneDoorParamsPair('+','.join(c.text.decode() for c in kids(key))+')'))
                    if typ==b'std::map<RandomizerGet, ImVec4>' and val is not None:
                        for row in kids(val):
                            value=kids(row)[1]
                            if value.type=='initializer_list':edits.append((value.start_byte,value.end_byte,'ImVec4('+','.join(c.text.decode() for c in kids(value))+')'))
        if n.type=='call_expression':
            fn=n.child_by_field_name('function');args=n.child_by_field_name('arguments')
            if fn.text.startswith(b'Rando::Location::'):
                for arg in kids(args):
                    if arg.type in ('string_literal','concatenated_string'):edits.append((arg.start_byte,arg.end_byte,'std::string('+arg.text.decode()+')'))
            if fn.type=='field_expression' and fn.child_by_field_name('field').text==b'InsertNames':
                for arg in kids(args):
                    if arg.type=='initializer_list':edits.append((arg.start_byte,arg.end_byte,values(arg,'CustomMessage')))
            if fn.text==b'lookupTable.find':
                for arg in kids(args):
                    if arg.type=='initializer_list':edits.append((arg.start_byte,arg.end_byte,'SceneDoorParamsPair('+','.join(c.text.decode() for c in kids(arg))+')'))
        if n.type=='compound_literal_expression' and n.child_by_field_name('type').text in (b'CheckIdentity',b'DnsItemEntry'):
            val=n.child_by_field_name('value');fields=kids(val)
            typ=n.child_by_field_name('type').text.decode()
            if typ=='CheckIdentity':
                assert [c.child_by_field_name('designator').text if c.child_by_field_name('designator') else c.named_children[0].text for c in fields]==[b'.randomizerInf',b'.randomizerCheck']
                args=','.join(c.child_by_field_name('value').text.decode() for c in fields)
            else:args=','.join(c.text.decode() for c in fields)
            replacement='Shipyard::RandomizerApplication::Identity('+args+')' if typ=='CheckIdentity' else '[&]() -> '+typ+' { '+typ+' value = {'+args+'}; return value; }()'
            edits.append((n.start_byte,n.end_byte,replacement))
    return edits_apply(raw,edits)

def ui_values(text):
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='call_expression':
            fn=n.child_by_field_name('function');args=n.child_by_field_name('arguments')
            if fn.text==b'ImGui::PushStyleColor':
                for a in kids(args):
                    if a.type=='initializer_list':edits.append((a.start_byte,a.end_byte,'ImVec4('+','.join(c.text.decode() for c in kids(a))+')'))
            for arg in kids(args):
                if arg.type!='initializer_list':continue
                f=fn.text.decode()
                if f.endswith('Options'):
                    fields=[x for x in walk(arg) if x.type=='initializer_pair']
                    if fields:
                        expression='UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit())'
                        for field in fields:
                            ident=next(c for c in walk(field) if c.type=='field_identifier').text.decode();value=field.child_by_field_name('value').text.decode()
                            expression+='.'+ident[0].upper()+ident[1:]+'('+value+')'
                        edits.append((arg.start_byte,arg.end_byte,expression))
                elif f in ('CVarGetColor','CVarColorPicker') or f.endswith('.DefaultValue') and 'ColorPickerOptions' in f:
                    edits.append((arg.start_byte,arg.end_byte,'ShipyardRGBA('+','.join(c.text.decode() for c in kids(arg))+')'))
                elif f.endswith('->AddSearchWidget'):
                    edits.append((arg.start_byte,arg.end_byte,'SearchWidget('+','.join(c.text.decode() for c in kids(arg))+')'))
                elif f=='ImGui::PushStyleVar' or f.endswith(('.Size','.Padding')):
                    edits.append((arg.start_byte,arg.end_byte,'ImVec2('+','.join(c.text.decode() for c in kids(arg))+')'))
            if fn.text in (b'ITEM_TRACKER_ITEM',b'ITEM_TRACKER_ITEM_CUSTOM') and n.parent.type=='argument_list':
                edits.append((n.start_byte,n.end_byte,'[&]() -> ItemTrackerItem { ItemTrackerItem value='+n.text.decode()+'; return value; }()'))
        if n.type=='assignment_expression':
            left=n.child_by_field_name('left');right=n.child_by_field_name('right')
            if right.type=='call_expression' and right.child_by_field_name('function').text in (b'ITEM_TRACKER_ITEM',b'ITEM_TRACKER_ITEM_CUSTOM'):
                assert n.parent.type=='expression_statement'
                edits.append((n.parent.start_byte,n.parent.end_byte,'{ const ItemTrackerItem assigned='+right.text.decode()+'; '+left.text.decode()+'=assigned; }'));continue
            if right.type!='initializer_list':continue
            if left.text.startswith((b'presetPos',b'presetSize')):
                edits.append((right.start_byte,right.end_byte,'ImVec2('+','.join(c.text.decode() for c in kids(right))+')'));continue
            if left.text==b'gEntranceTrackingData':
                assert right.text.replace(b' ',b'')==b'{0}'
                assert n.parent.type=='expression_statement'
                edits.append((n.parent.start_byte,n.parent.end_byte,'{ const EntranceTrackingData empty = {0}; gEntranceTrackingData = empty; }'));continue
            fields=kids(right)
            if fields and fields[0].type=='initializer_pair':
                named={next(c for c in walk(f) if c.type=='field_identifier').text.decode():f.child_by_field_name('value').text.decode() for f in fields}
                if set(named)=={'name','type'}:
                    edits.append((right.start_byte,right.end_byte,'Shipyard::ApplicationEditors::Widget('+named['name']+','+named['type']+')'));continue
            if left.text in (b'filterAreasHidden',b'filterChecksHidden'):
                assert right.text.replace(b' ',b'')==b'{0}'
                edits.append((n.start_byte,n.end_byte,left.text.decode()+'.fill(false)'))
            elif left.text.endswith(b'Color') or left.text in (b'textColor',b'color'):
                if len(kids(right))==4:edits.append((right.start_byte,right.end_byte,'ImVec4('+','.join(c.text.decode() for c in kids(right))+')'))
    return edits_apply(raw,edits)

def entrance_tables(text):
    text=once(text,'exclude = {}','exclude = std::vector<std::pair<RandomizerRegion,RandomizerRegion> >()')
    text=text.replace('[] { return false; }','ShipyardEntranceNever').replace('[] { return logic->IsChild; }','ShipyardEntranceChild')
    text=text.replace('ReachabilitySearch({})','ReachabilitySearch(std::vector<RandomizerCheck>())')
    text=once(text,'[&exclude](Entrance* entrance) {','[&exclude](Entrance* entrance) -> bool {')
    text=once(text,'return { restrictiveEntrances, softEntrances };','const std::array<std::vector<Entrance*>,2> result = { restrictiveEntrances, softEntrances }; return result;')
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type=='declaration':
            typ=n.child_by_field_name('type');init=n.child_by_field_name('declarator')
            if typ is None or init is None or init.type!='init_declarator':continue
            val=init.child_by_field_name('value')
            if val is None or val.type!='initializer_list':continue
            if not kids(val) and (typ.text.startswith((b'std::vector<',b'std::set<',b'std::map<')) or typ.text==b'EntrancePools'):
                edits.append((val.start_byte,val.end_byte,typ.text.decode()+'()'));continue
            if typ.text==b'std::vector<EntranceInfoPair>':
                for row in kids(val):
                    parts=[]
                    for entry in kids(row):
                        parts.append('ShipyardEntranceLink('+','.join(c.text.decode() for c in kids(entry))+')' if entry.type=='initializer_list' else entry.text.decode())
                    edits.append((row.start_byte,row.end_byte,'EntranceInfoPair('+','.join(parts)+')'))
            if typ.text==b'std::vector<EntrancePair>':
                for row in kids(val):
                    if row.type=='initializer_list':edits.append((row.start_byte,row.end_byte,'EntrancePair('+','.join(c.text.decode() for c in kids(row))+')'))
            if typ.text==b'std::map<std::string, PriorityEntrance>':
                for row in kids(val):
                    for i,v in enumerate(kids(kids(row)[1])):
                        t=['RandomizerRegion','EntranceType'][i]
                        expression='Shipyard::RandomizerApplication::SequenceValues<std::list<'+t+'> >()'+''.join('.Add('+c.text.decode()+')' for c in kids(v))+'.Finish()'
                        edits.append((v.start_byte,v.end_byte,expression))
        if n.type=='compound_literal_expression' and n.child_by_field_name('type').text==b'EntrancePair':
            val=n.child_by_field_name('value');edits.append((n.start_byte,n.end_byte,'EntrancePair('+','.join(c.text.decode() for c in kids(val))+')'))
        if n.type=='assignment_expression':
            left=n.child_by_field_name('left');right=n.child_by_field_name('right')
            if right.type!='initializer_list':continue
            if left.text==b'validTargetTypes':edits.append((right.start_byte,right.end_byte,values(right,'EntranceType')))
            elif left.text.startswith(b'entranceOverrides['):
                fields=kids(right);names=[next(c for c in walk(f) if c.type=='field_identifier').text.decode() for f in fields]
                assert names==['type','index','destination','override','overrideDestination']
                expression='ShipyardEntranceOverride('+','.join(f.child_by_field_name('value').text.decode() for f in fields)+')'
                edits.append((right.start_byte,right.end_byte,expression))
            elif not kids(right) and left.text==b'itemPool':
                edits.append((n.start_byte,n.end_byte,'itemPool.clear()'))
        if n.type=='call_expression':
            fn=n.child_by_field_name('function');args=kids(n.child_by_field_name('arguments'))
            if fn.text==b'BuildOneWayTargets' and len(args)==2 and args[1].type=='initializer_list':
                edits.append((args[1].start_byte,args[1].end_byte,values(args[1],'std::pair<RandomizerRegion,RandomizerRegion> ')))
            if fn.text==b'entranceOverrides.fill' and args[0].type=='initializer_list':edits.append((args[0].start_byte,args[0].end_byte,'ShipyardEntranceOverride('+','.join(c.text.decode() for c in kids(args[0]))+')'))
    text=edits_apply(raw,edits)
    text=text.replace('(uint8_t)entrance->GetType()','(uint8_t)entrance->GetType().GetValue()')
    return '#include "soh/Enhancements/randomizer/entrance.h"\n#include "soh/Enhancements/randomizer/location_access.h"\n#include "soh/Enhancements/randomizer/logic.h"\n#include "soh/Enhancements/randomizer/3drando/random.hpp"\nnamespace Rando { static bool ShipyardEntranceNever(){return false;} static bool ShipyardEntranceChild(){return logic->IsChild;} static EntranceLinkInfo ShipyardEntranceLink(EntranceType type,RandomizerRegion parent,RandomizerRegion connected,int16_t index){EntranceLinkInfo value={type,parent,connected,index};return value;} static EntranceOverride ShipyardEntranceOverride(uint8_t type,int16_t index,int16_t destination,int16_t replacement,int16_t replacementDestination){EntranceOverride value={type,index,destination,replacement,replacementDestination};return value;} }\n'+text

def tracker_tables(name,text):
    if not name.endswith(('/randomizer_item_tracker.cpp','/randomizer_entrance_tracker.cpp')):return text
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='declaration':continue
        typ=n.child_by_field_name('type');d=n.child_by_field_name('declarator')
        if typ is None or d is None or d.type!='init_declarator':continue
        val=d.child_by_field_name('value')
        if val is None or val.type!='initializer_list':continue
        if typ.text==b'std::vector<ItemTrackerDungeon>':
            for row in kids(val):
                fields=kids(row);assert len(fields)==2
                edits.append((fields[1].start_byte,fields[1].end_byte,values(fields[1],'uint32_t')))
        if typ.text==b'EntranceData':
            for row in kids(val):
                fields=kids(row);scenes=fields[2]
                if scenes.type!='initializer_list':continue
                result='Shipyard::RandomizerContent::Values<EntranceDataSceneAndSpawn>('+str(len(kids(scenes)))+')'
                for scene in kids(scenes):
                    if scene.type=='initializer_list':
                        args=','.join(c.text.decode() for c in kids(scene))
                        result+='.Add(ShipyardTrackerScene('+args+'))'
                    else:
                        assert scene.text.startswith(b'SCENE_NO_SPAWN(')
                        result+='.Add(ShipyardTrackerScene('+kids(scene.child_by_field_name('arguments'))[0].text.decode()+',-1))'
                edits.append((scenes.start_byte,scenes.end_byte,result+'.Finish()'))
    text=edits_apply(raw,edits)
    if name.endswith('/randomizer_entrance_tracker.cpp'):
        text=text.replace('SINGLE_SCENE_INFO(', 'SHIPYARD_SINGLE_SCENE_INFO(')
        text='#include "soh/Enhancements/randomizer/randomizer_entrance_tracker.h"\nstatic EntranceDataSceneAndSpawn ShipyardTrackerScene(int8_t scene,int8_t spawn=0){EntranceDataSceneAndSpawn value={scene,spawn};return value;}\n#define SHIPYARD_SINGLE_SCENE_INFO(scene) std::vector<EntranceDataSceneAndSpawn>(1, ShipyardTrackerScene(scene,-1))\n'+text
    return text

def project(name,text):
    if 'std::filesystem' in text or '#include <filesystem>' in text:text=project_boundary(name,text)
    text=ui_values(text)
    if name.endswith('/entrance.cpp'):text=entrance_tables(text)
    def include(m):
        p=(ROOT/name).parent/m[1]
        if p.exists():
            resolved=p.resolve().relative_to(ROOT).as_posix()
            if resolved.startswith('soh/'):return '#include "'+resolved.removeprefix('soh/')+'"'
        return m[0]
    text=re.sub(r'#include "([^\"]+)"',include,text)
    text=tracker_tables(name,text)
    text=initializers(name,text)
    if name.endswith('/Traps.cpp'):
        # The first lookup stalled before even entering this unusually large
        # modern initializer in Xenia. Keep every assignment and its order,
        # but give the guest JIT bounded, non-inlined functions to translate.
        raw=text.encode()
        functions=[n for n in walk(PARSER.parse(raw).root_node)
                   if n.type=='function_definition' and
                   n.child_by_field_name('declarator').text==b'InitTrickNames()']
        assert len(functions)==1
        fn=functions[0]
        statements=[n for n in fn.child_by_field_name('body').named_children
                    if n.type=='expression_statement']
        assert len(statements)>100 and all(n.text.startswith(b'trickNameTable[') for n in statements)
        helpers=[];calls=[]
        for chunk_index in range(0,len(statements),8):
            index=chunk_index//8
            chunk='\n'.join('    '+n.text.decode() for n in statements[chunk_index:chunk_index+8])
            helpers.append('static __declspec(noinline) void ShipyardTrickNamesChunk'+str(index)+'() {\n'+chunk+'\n}\n')
            calls.append('    SPDLOG_INFO("RANDO trick names chunk={} begin", '+str(index)+');\n'
                         '    ShipyardTrickNamesChunk'+str(index)+'();\n'
                         '    SPDLOG_INFO("RANDO trick names chunk={} end", '+str(index)+');')
        replacement='\n'.join(helpers)+'\nstatic void InitTrickNames() {\n    SPDLOG_INFO("RANDO trick names begin");\n'+'\n'.join(calls)+'\n}\n'
        text=edits_apply(raw,[(fn.start_byte,fn.end_byte,replacement)])
        text='#include <spdlog/spdlog.h>\n'+text
    text,_=content_expressions(text)
    if name.endswith('/savefile.cpp'):
        raw=text.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type!='for_range_loop' or n.child_by_field_name('right').type!='initializer_list':continue
            right=n.child_by_field_name('right');loop=n.text.decode().replace(right.text.decode(),'trialFlags',1)
            edits.append((n.start_byte,n.end_byte,'{ const int trialFlags[] = '+right.text.decode()+'; '+loop+' }'))
        assert len(edits)==1
        text=edits_apply(raw,edits)
    if name.endswith('/entrance.cpp'):
        text=lower_defaults(text,inventory((ROOT/BASE/'entrance.h').read_text(encoding='utf-8-sig')),[])
        text=once(text,'[this](const auto entrance)','[this](Entrance* const entrance)')
        text=once(text,'[] { return true; }','ShipyardEntranceAlways')
        text='#include "soh/Enhancements/randomizer/location_access.h"\nstatic bool ShipyardEntranceAlways(){return true;}\n'+text
        text=text.replace('playthroughEntrances = {};','playthroughEntrances.clear();').replace('entranceOverrides = {};','{ const std::array<EntranceOverride, ENTRANCE_OVERRIDES_MAX_COUNT> empty = {}; entranceOverrides = empty; }')
    if name.endswith('/draw.cpp'):text=once(text,'pos = { 0.0f, -25.5f, -4.0f };','pos = Shipyard::ApplicationWindows::Vector3(0.0f, -25.5f, -4.0f);')
    if name.endswith('/randomizer_check_tracker.cpp'):
        text='#include "network-app/support.h"\n'+text
        text=once(text,'[&](const auto& x)','[&](const SceneID& x)')
        text=once(text,'checksByArea.emplace(static_cast<RandomizerCheckArea>(i), std::vector<RandomizerCheck>());','checksByArea.insert(std::make_pair(static_cast<RandomizerCheckArea>(i), std::vector<RandomizerCheck>()));')
        text=once(text,'entry.GetShortName().starts_with("Child")','Shipyard::Resources::starts_with(entry.GetShortName(),"Child")')
    if name.endswith('/randomizer.cpp'):
        text='#include "soh/Enhancements/randomizer/fishsanity.h"\n#include "thread-pool/native_support.h"\n'+text
        text=once(text,'std::thread randoThread;','Shipyard::Async::joining_thread randoThread;')
        text=once(text,'std::thread(&GenerateRandomizerImgui, seed)','Shipyard::Async::make_thread([seed]() { GenerateRandomizerImgui(seed); })')
        text=once(text,'void JoinRandoGenerationThread() {\n    if (generated) {\n        generated = 0;\n        randoThread.join();\n    }\n}',
                  'void JoinRandoGenerationThread() {\n    if (randoThread.joinable()) {\n        randoThread.join();\n        generated = 0;\n    }\n}')
    if name.endswith('/Plandomizer.cpp'):
        text=re.sub(r'for \(auto& \[key, value\] : (hints|locations)\.items\(\)\) \{',lambda m:'for (auto jsonCursor='+m[1]+'.begin();jsonCursor!='+m[1]+'.end();++jsonCursor){ const std::string key=jsonCursor.key(); auto& value=jsonCursor.value();',text)
        text=once(text,'[](const auto& a, const auto& b)','[](const std::pair<Rando::Item,int32_t>& a, const std::pair<Rando::Item,int32_t>& b) -> bool')
        raw=text.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type=='assignment_expression' and n.child_by_field_name('left').text.startswith(b'spoilerSave[') and n.child_by_field_name('right').type=='initializer_list':
                val=n.child_by_field_name('right');fields=kids(val);obj=all(f.type=='initializer_list' for f in fields)
                expression='[&]() -> nlohmann::json { nlohmann::json value=nlohmann::json::'+('object' if obj else 'array')+'();'
                for f in fields:
                    if obj:
                        k,v=kids(f);expression+='value['+k.text.decode()+']='+v.text.decode()+';'
                    else:expression+='value.push_back('+f.text.decode()+');'
                expression+='return value;}()';edits.append((val.start_byte,val.end_byte,expression))
            if n.type=='for_range_loop' and b'directory_iterator' in n.child_by_field_name('right').text:
                right=n.child_by_field_name('right');var=n.child_by_field_name('declarator').text.decode();body=n.child_by_field_name('body').text.decode()
                kind=right.child_by_field_name('function').text.decode()
                edits.append((n.start_byte,n.end_byte,'for('+kind+' cursor = '+right.text.decode()+',finish;cursor!=finish;++cursor){ const xbox_compat::filesystem::directory_entry& '+var.lstrip('&')+'=*cursor; '+body+' }'))
        text=edits_apply(raw,edits)
    if name.endswith('/randomizer_entrance_tracker.cpp'):
        for ident in ('original','override'):
            text=once(text,ident+'->metaTag.ends_with("bw")','Shipyard::RandomizerApplication::EndsWith('+ident+'->metaTag,"bw")')
    text=containers(text)
    text=re.sub(r'\bauto const\s*&\s*\[','const auto& [',text)
    text=feature_project(name,text)
    text,_=lower_literals(text)
    text=text.replace('using namespace std::literals::string_literals;','// String suffixes retain their encoded byte lengths in the projection.')
    return '#include "randomizer-application/support.h"\n'+text

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());generated={}
    for n,digest in lock['sources'].items():
        text=(ROOT/n).read_text(encoding='utf-8-sig');assert sha(text)==digest,n
        text=project(n,text);stable(OUT/'generated'/n,text);generated[n]=sha(text)
    helpers=[ROOT/'tools/shipyard'/n for n in ('prepare_gameplay_features.py','prepare_application_windows.py','prepare_enhancements.py','prepare_custom_message.py','prepare_randomizer.py','prepare_randomizer_context.py','prepare_randomizer_item.py','prepare_randomizer_content.py','prepare_filesystem.py','prepare_resource_manager.py','cpp_ast.py')]+[ROOT/'platform/shipyard/input/lowering.py',ROOT/BASE/'entrance.h',OWN/'support.h']
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated=generated,full_units=list(lock['sources']),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),helpers={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers}),indent=2)+'\n')
    return list(lock['sources'])

def includes():return [OUT/'generated/soh',ROOT/'scratch/randomizer-generation-xdk/generated/soh',ROOT/'scratch/randomizer-hints-xdk/generated/soh',ROOT/'scratch/randomizer-regions-xdk/generated/soh',ROOT/'scratch/randomizer-content-xdk/generated/soh',ROOT/'scratch/randomizer-context-xdk/generated/soh',ROOT/'scratch/randomizer-settings-xdk/generated/soh',ROOT/'scratch/application-windows-xdk/generated/soh',ROOT/'scratch/deps/string-view-lite/include']+feature_includes()

def build(selected=None,failed=False):
    units=prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/application-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    roots=list(dict.fromkeys(includes()+[Path(f[2:]) for f in flags if f.startswith('/I')]))
    roots.sort(key=lambda p:2 if p.is_relative_to(ROOT/'soh') else 1 if p.is_relative_to(ROOT/'scratch/game-xdk') else 0)
    flags=[f for f in flags if not f.startswith('/I')];flags[1:1]=['/Dnssv_CONFIG_SELECT_STRING_VIEW=1']+['/I'+str(p) for p in roots];rows=[]
    previous=json.loads((folder/'build.json').read_text()) if (selected or failed) and (folder/'build.json').exists() else []
    if selected:units=[n for n in units if Path(n).stem in selected]
    if failed:
        done={r['path']:r for r in previous}
        units=[n for n in units if n not in done or done[n]['exit'] or done[n]['source_sha256']!=hashlib.sha256((OUT/'generated'/n).read_bytes()).hexdigest()]
    def compile_unit(n):
        source=OUT/'generated'/n;obj=folder/(source.stem+'_'+hashlib.sha256(n.encode()).hexdigest()[:8]+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        row=dict(path=n,source=source.relative_to(ROOT).as_posix(),object=obj.relative_to(ROOT).as_posix(),command=command,exit=r.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not r.returncode:
            assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        return row
    with ThreadPoolExecutor(max_workers=3) as workers:
        for f in as_completed([workers.submit(compile_unit,n) for n in units]):
            row=f.result();rows.append(row);print(Path(row['path']).stem+': '+str(row['exit']),flush=True)
            changed={r['source'] for r in rows};stable(folder/'build.json',json.dumps([r for r in previous if r['source'] not in changed]+rows,indent=2)+'\n')
    changed={r['source'] for r in rows};rows=sorted([r for r in previous if r['source'] not in changed]+rows,key=lambda r:r['path'])
    errors=[dict(path=r['path'],errors=[s for s in (ROOT/r['object']).with_suffix('.log').read_text().splitlines() if 'error ' in s]) for r in rows if r['exit']]
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n');stable(folder/'errors.json',json.dumps(errors,indent=2)+'\n')
    print(str(len(rows)-len(errors))+'/'+str(len(rows))+' full randomizer units compile.',flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--units',nargs='+');p.add_argument('--failed',action='store_true');a=p.parse_args();build(a.units,a.failed) if a.build else prepare()
