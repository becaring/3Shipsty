"""Project complete modern menu implementations against the canonical UI types."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from prepare_soh_ui import ROOT,BASE,common,maps,includes as ui_includes,WIDGETS,constructors
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from cpp_ast import PARSER,walk
from prepare_custom_message import escape_literal,literal_bytes

OWN=ROOT/'platform/shipyard/soh-menus';OUT=ROOT/'scratch/soh-menus-xdk'

def contains(text):
    raw=text.encode();edits=[]
    for n in walk(PARSER.parse(raw).root_node):
        if n.type!='call_expression':continue
        f=n.child_by_field_name('function');args=n.child_by_field_name('arguments')
        if f.type!='field_expression' or f.child_by_field_name('field').text!=b'contains':continue
        obj=f.child_by_field_name('argument').text.decode()
        if b'->' in f.text:obj='*('+obj+')'
        edits.append((n.start_byte,n.end_byte,'Shipyard::Resources::contains('+obj+','+args.text.decode()[1:-1]+')'))
    return edits_apply(raw,edits)

def inherited(name,extra='',skip_two=False):
    header=(ROOT/'scratch/window-xdk/generated/include/ship/window/gui/GuiWindow.h').read_text()
    result=[]
    for signature in re.findall(r'GuiWindow(\([^;{}]*\));',header):
        if skip_two and signature.count(',')==1:continue
        args=[re.search(r'(\w+)\s*$',p)[1] for p in signature[1:-1].split(',')]
        result.append(name+signature+' : GuiWindow('+','.join(args)+')'+extra+' {}')
    assert len(result)==(5 if skip_two else 6)
    return '\n'.join(result)

def project(name,text):
    text=text.replace('#include <libultraship/libultraship.h>','#include "UIWidgets.hpp"\n#include <cassert>')
    if name=='SohGui.hpp':
        # These include-only dependencies declare no part of the SohGui API.
        text='\n'.join(l for l in text.splitlines() if not l.startswith('#include "soh/Enhancements/'))+'\n'
    if name=='Menu.h':
        text=once(text,'using GuiWindow::GuiWindow;',inherited('Menu',', searchSidebarEntry(MakeSearchSidebarEntry()), allowPopout(true)',True))
        a=text.index('    const SidebarEntry searchSidebarEntry = {');b=text.index('\n\n  private:',a)
        original=text[a:b]
        assert 'Searches all menus for the given text, including tooltips.' in original
        text=text[:a]+'    static SidebarEntry MakeSearchSidebarEntry();\n    const SidebarEntry searchSidebarEntry;'+text[b:]
        text=once(text,'bool allowPopout = true;','bool allowPopout;')
    if name=='SohMenu.h':
        text=once(text,'bool mMenuElementsInitialized = false;','bool mMenuElementsInitialized;')
    if name=='SohModals.h':
        text=text.replace(' final :',' :')
        text=once(text,'using GuiWindow::GuiWindow;','SohModalWindow() : GuiWindow() {}\n'+inherited('SohModalWindow'))
    if name in ('TimeDisplay.h','Notification.h'):
        text=text.replace(' final :',' :')
        cls='TimeDisplayWindow' if name=='TimeDisplay.h' else 'Window'
        text=once(text,'using GuiWindow::GuiWindow;',cls+'() : GuiWindow() {}\n'+inherited(cls))
        if name=='Notification.h':text,_=constructors(text,['Options'])
    if name=='SohModals.cpp':
        text=once(text,'modals.push_back({ title, message, button1, button2, button1callback, button2callback });','SohModal value;value.title_=title;value.message_=message;value.button1_=button1;value.button2_=button2;value.button1callback_=button1callback;value.button2callback_=button2callback;modals.push_back(value);')
        nav='''static void RefreshModalGamepadNavigation() {
    auto& io = ImGui::GetIO();
    auto gui = Ship::Context::GetInstance()->GetWindow()->GetGui();
    if (CVarGetInteger(CVAR_IMGUI_CONTROLLER_NAV, 0) &&
        (!modals.empty() || gui->GetMenuOrMenubarVisible())) {
        io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad;
    } else {
        io.ConfigFlags &= ~ImGuiConfigFlags_NavEnableGamepad;
    }
}
'''
        text=once(text,'bool closePopup = false;','bool closePopup = false;\n'+nav)
        text=once(text,'    DrawElement();\n    // Sync up the IsVisible flag if it was changed by ImGui','    RefreshModalGamepadNavigation();\n    DrawElement();\n    RefreshModalGamepadNavigation();\n    // Sync up the IsVisible flag if it was changed by ImGui')
        text=once(text,'            if (ImGui::Button(curModal.button1_.c_str())) {',
                  '            const bool primaryPressed = ImGui::Button(curModal.button1_.c_str());\n            ImGui::SetItemDefaultFocus();\n            if (primaryPressed) {')
    if name=='SohMenu.cpp':
        text=once(text,': Menu(consoleVariable, name, 0, UIWidgets::Colors::LightBlue) {',': Menu(consoleVariable, name, 0, UIWidgets::Colors::LightBlue), mMenuElementsInitialized(false) {')
        text=once(text,'SidebarEntry{ .columnCount = columnCount }','MakeSidebarEntry(columnCount)')
        text=once(text,'push_back({});','push_back(std::vector<WidgetInfo>());')
        text=once(text,'entry.columnWidgets.at(column).push_back({ .name = widgetName, .type = widgetType });','entry.columnWidgets.at(column).push_back(MakeWidgetInfo(widgetName,widgetType));')
        helpers='static SidebarEntry MakeSidebarEntry(uint32_t columns){SidebarEntry r((Shipyard::SohUI::ValueInit()));r.columnCount=columns;return r;}\nstatic WidgetInfo MakeWidgetInfo(const std::string& name,WidgetType type){WidgetInfo r((Shipyard::SohUI::ValueInit()));r.name=name;r.type=type;return r;}\n'
        text=once(text,'using namespace UIWidgets;','using namespace UIWidgets;\n'+helpers)
        for typ in WIDGETS:text=text.replace('std::make_shared<'+typ+'>()','std::make_shared<'+typ+'>(Shipyard::SohUI::ValueInit())')
        raw=text.encode();nodes=[n for n in walk(PARSER.parse(raw).root_node) if n.type=='assignment_expression' and n.child_by_field_name('left').text==b'disabledMap']
        assert len(nodes)==1
        n=nodes[0];rows=n.child_by_field_name('right').named_children;body='std::unordered_map<uint32_t,disabledInfo> disabledValues;\n'
        for row in rows:
            key,value=row.named_children;body+='disabledValues.insert(std::make_pair(uint32_t('+key.text.decode()+'),disabledInfo('+value.text.decode()[1:-1]+')));\n'
        text=edits_apply(raw,[(n.start_byte,n.end_byte,body+'disabledMap=std::move(disabledValues)')])
    if name=='Menu.cpp':
        text=text.replace('#include <variant>','#include <xbox_compat/variant.h>').replace('std::get<','xbox_compat::get<')
        text=once(text,'std::vector<ImVec2> windowTypeSizes = { {} };','std::vector<ImVec2> windowTypeSizes(1);')
        text=once(text,'std::vector<SearchWidget> extraSearchWidgets = {};','std::vector<SearchWidget> extraSearchWidgets;')
        text=once(text,'defaultThemeIndex(defaultThemeIndex_) {','defaultThemeIndex(defaultThemeIndex_), searchSidebarEntry(MakeSearchSidebarEntry()), allowPopout(true) {')
        helper='SidebarEntry Menu::MakeSearchSidebarEntry(){SidebarEntry r((Shipyard::SohUI::ValueInit()));r.columnCount=1;r.columnWidgets.resize(1);WidgetInfo w((Shipyard::SohUI::ValueInit()));w.name="Sidebar Search";w.type=WIDGET_SEARCH;w.options=std::make_shared<UIWidgets::WidgetOptions>(UIWidgets::WidgetOptions(Shipyard::SohUI::ValueInit()).Tooltip("Searches all menus for the given text, including tooltips."));r.columnWidgets[0].push_back(w);return r;}\n'
        text=once(text,'namespace Ship {','namespace Ship {\n'+helper)
        text=once(text,'std::erase_if(menuEntries["Settings"].sidebarOrder, [](std::string& name) { return name == "Search"; });','std::vector<std::string>& order=menuEntries["Settings"].sidebarOrder;order.erase(std::remove_if(order.begin(),order.end(),[](std::string& name){return name=="Search";}),order.end());')
        text=once(text,'MainMenuEntry{ entryName, entryCvar }','MainMenuEntry(entryName, entryCvar)')
        text=once(text,'for (auto& [reason, info] : disabledMap) {','for (auto& disabledPair : disabledMap) {\nconst auto& reason=disabledPair.first;auto& info=disabledPair.second;')
        text=re.sub(r'(ImVec2|ImRect) (\w+) = \{([^;{}]*)\};',r'\1 \2(\3);',text)
        text=text.replace(' noexcept',' throw()')
        text='#include "ship/config/Config.h"\n#include "ship/window/gui/IconsFontAwesome4.h"\n#include "ship/window/gui/ConsoleWindow.h"\n#include "gui/compat.h"\n#include "soh-menus/support.h"\n'+text
        text=once(text,'(int32_t)(configWindowBackend)','configWindowBackend.GetValue()')
        text=once(text,'std::fminf(windowWidth * 0.9f, (windowHeight * 1.77f))','static_cast<float>(Shipyard::SohUI::FMin(windowWidth * 0.9f, (windowHeight * 1.77f)))')
        text=text.replace('static_pointer_cast<Menu>','std::static_pointer_cast<Menu>').replace('std::reinterpret_pointer_cast<','Shipyard::GuiCompat::ReinterpretPointerCast<')
        text=text.replace('menuEntries["Settings"]','Shipyard::SohMenus::ValueIndex(menuEntries,"Settings")')
        text=once(text,'menuEntry.sidebars[sidebarLabel]','Shipyard::SohMenus::ValueIndex(menuEntry.sidebars,sidebarLabel)')
    if name in ('Menu.cpp','SohMenu.cpp'):
        raw=text.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type=='call_expression':
                f=n.child_by_field_name('function');a=n.child_by_field_name('arguments')
                if f.type=='field_expression' and f.child_by_field_name('field').text==b'emplace' and len(a.named_children)==2:
                    edits.append((f.child_by_field_name('field').start_byte,f.end_byte,'insert'))
                    edits.append((a.start_byte,a.end_byte,'(std::make_pair('+a.text.decode()[1:-1]+'))'))
            if n.type=='compound_literal_expression' and n.child_by_field_name('type').text in (b'ImVec2',b'ImVec4'):
                v=n.child_by_field_name('value');edits.append((v.start_byte,v.end_byte,'('+v.text.decode()[1:-1]+')'))
            if n.type=='initializer_list' and n.parent.type=='argument_list':
                call=n.parent.parent.child_by_field_name('function').text.decode()
                vector2={'ImGui::SetNextWindowSizeConstraints','ImGui::BeginChild','ImGui::SetNextWindowSize','ImGui::SetNextWindowPos','ImGui::SetCursorPos','ImGui::Dummy'}
                vector4={'ImGui::PushStyleColor','ImGui::GetColorU32'}
                if call in vector2:typ='ImVec2'
                elif call in vector4:typ='ImVec4'
                else:raise ValueError('Unmapped menu aggregate argument '+call+': '+n.text.decode())
                edits.append((n.start_byte,n.end_byte,typ+'('+n.text.decode()[1:-1]+')'))
        text=edits_apply(raw,edits)
    if name in ('SohMenuEnhancements.cpp','SohMenuSettings.cpp','SohMenuDevTools.cpp'):
        text=re.sub(r'WidgetPath path = \{([^{}]*)\};',r'WidgetPath path(\1);',text)
    if name=='SohMenuEnhancements.cpp':
        text='#include "soh/Enhancements/randomizer/SeedContext.h"\n#include "macros.h"\n#include "ship/window/gui/IconsFontAwesome4.h"\n#include "ship/window/gui/ConsoleWindow.h"\n#include "gui/compat.h"\n'+text
        text=text.replace('std::reinterpret_pointer_cast<','Shipyard::GuiCompat::ReinterpretPointerCast<')
    if name=='SohMenuSettings.cpp':
        text='#include "ship/controller/controldeck/ControlDeck.h"\n'+text
        a=text.index('        .Callback([](WidgetInfo& info) {\n            std::string filesPath');b=text.index('\n        .Options(',a)
        text=text[:a]+'#if !defined(_XBOX)\n'+text[a:b]+'\n#endif'+text[b:]
        text=once(text,'ButtonOptions().Tooltip("Opens the folder that contains the save and mods folders, etc.")','ButtonOptions().Tooltip("Opens the folder that contains the save and mods folders, etc.").Disabled(true).DisabledTooltip("Opening folders is unavailable on Xbox 360.")')
        a=text.index('            Notification::Emit({');b=text.index('            });',a)+len('            });')
        text=text[:a]+'            Notification::Options notification;\n            notification.itemIcon="__OTR__textures/icon_item_24_static/gQuestIconGoldSkulltulaTex";\n            notification.prefix="This";notification.message="is a";notification.suffix="test.";\n            Notification::Emit(notification);'+text[b:]
    return common(contains(maps(text)))

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());outputs={};literals=[];widgets={}
    for path,expected in lock['sources'].items():
        text=(ROOT/path).read_text(encoding='utf-8-sig');assert hashlib.sha256(text.encode()).hexdigest()==expected,path
        projected=project(Path(path).name,text);raw=projected.encode();edits=[]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type=='string_literal' and any(b>=128 for b in n.text):
                value=n.text.decode();escaped=escape_literal(value);edits.append((n.start_byte,n.end_byte,escaped));literals.append(dict(path=path,original=value,projected=escaped,bytes=literal_bytes(value).hex()))
        projected=edits_apply(raw,edits)
        def widget_inventory(source):
            values=[]
            for n in walk(PARSER.parse(source.encode()).root_node):
                if n.type!='call_expression' or n.child_by_field_name('function').text!=b'AddWidget':continue
                args=n.child_by_field_name('arguments');raw_args=args.text;edits_args=[]
                for child in walk(args):
                    if child.type=='string_literal':edits_args.append((child.start_byte-args.start_byte,child.end_byte-args.start_byte,escape_literal(child.text.decode())))
                values.append(edits_apply(raw_args,edits_args))
            return values
        original_widgets=widget_inventory(text);assert original_widgets==widget_inventory(projected),path
        if original_widgets:widgets[path]=original_widgets
        target=OUT/'generated'/path;stable(target,projected);outputs[path]=hashlib.sha256(target.read_bytes()).hexdigest()
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=lock['upstream_commit'],sources=lock['sources'],generated=outputs,widgets=widgets,literals=literals,native_ui_executed=False),indent=2)+'\n')

def build(names):
    prepare();folder=OUT/'xdk';folder.mkdir(exist_ok=True)
    flags=json.loads((ROOT/'scratch/soh-ui-xdk/xdk/build.json').read_text())[0]['command'][:-2]
    flags[1:1]=['/I'+str(OUT/'generated'/BASE),'/I'+str(OUT/'generated/soh'),'/I'+str(ROOT/'scratch/soh-ui-xdk/generated'/BASE)]
    previous=json.loads((folder/'build.json').read_text()) if (folder/'build.json').exists() else []
    records=[]
    for name in names:
        path=BASE+name+'.cpp';source=OUT/'generated'/path;obj=folder/(name+'.obj');command=flags+[str(source),'/Fo'+str(obj)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),r.stdout+r.stderr)
        records.append(dict(path=path,command=command,exit=r.returncode));print(name,r.returncode)
        if r.returncode:print('\n'.join(s for s in r.stdout.splitlines() if 'error ' in s)[:7000])
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    changed={r['path'] for r in records};records=[r for r in previous if r['path'] not in changed]+records
    stable(folder/'build.json',json.dumps(records,indent=2)+'\n')
    if any(r['exit'] for r in records):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--units',nargs='+',default=['Menu','SohMenu','SohModals']);a=p.parse_args()
    build(a.units) if a.build else prepare()
