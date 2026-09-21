"""Bounded real editor algorithms/defaults; full TU and member inventory audit."""
import hashlib,json,re,runpy,subprocess
from prepare_soh_input_editor import ROOT,OUT,OWN,BASE,prepare,includes
from prepare_archives import stable
from prepare_custom_message import literal_bytes
from cpp_ast import PARSER,walk
METHODS=['InitElement','addButtonName','TestingRumble','GetButtonColorsForDeviceType']
def fields(text):
    cls=next(n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='class_specifier' and n.child_by_field_name('name').text==b'SohInputEditorWindow')
    return [n.text.decode() for n in cls.child_by_field_name('body').named_children if n.type=='field_declaration' and not any(c.type=='function_declarator' for c in walk(n))]
def body(text,name):
    return next(n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.startswith(('SohInputEditorWindow::'+name+'(').encode()))
def signatures(text):
    return [n.child_by_field_name('declarator').text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition']
def cvarkeys(text):
    return [n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='call_expression' and n.child_by_field_name('function').text.startswith(b'CVAR_')]
def main():
    prepare();original=(ROOT/(BASE+'.cpp')).read_text(encoding='utf-8');projected=(OUT/'generated'/(BASE+'.cpp')).read_text()
    assert signatures(original)==signatures(projected)
    assert cvarkeys(original)==cvarkeys(projected)
    manifest=json.loads((OUT/'manifest.json').read_text());native=(OUT/'xdk/SohInputEditorWindow.obj').read_bytes()
    for literal in manifest['literals']:assert bytes.fromhex(literal['bytes']) in native
    original_fields=fields((ROOT/(BASE+'.h')).read_text());projected_fields=fields((OUT/'generated'/(BASE+'.h')).read_text())
    assert [s.replace('decltype(buttons)::iterator','std::list<std::pair<N64ButtonMask, const char*>>::iterator') for s in original_fields]==projected_fields
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();records=[]
    names=re.findall(r'\.name = ("[^"]+"), \.type = WidgetType::WIDGET_CVAR_CHECKBOX',original)
    assert len(names)==7
    for projected_flag in (False,True):
        folder=OUT/('host-projected' if projected_flag else 'host-original');folder.mkdir(exist_ok=True)
        # This fixture binds the exact four method bodies to their actual field
        # declarations. It does not instantiate, replace or render a game window.
        code=projected if projected_flag else original
        state='#include "soh/Enhancements/controls/SohInputEditorWindow.h"\n#include "z64.h"\n#include "soh/OTRGlobals.h"\n#include <iterator>\n'
        state+='\n'.join(s for s in code.splitlines() if s.startswith('#define BUTTON_COLOR_'))+'\n'
        state+='struct StateFixture {\n'+'\n'.join(projected_fields if projected_flag else original_fields)+'\n'
        state+='void InitElement(); void addButtonName(N64ButtonMask,const char*); bool TestingRumble();\nvoid GetButtonColorsForDeviceType(Ship::PhysicalDeviceType,ImVec4&,ImVec4&);\n};\n'
        state+='\n'.join(body(code,n).replace('SohInputEditorWindow::','StateFixture::') for n in METHODS)+'\n'+(OWN/'state_contract.cpp').read_text()
        stable(folder/'state.cpp',state)
        # Exact upstream widget declarations isolated from rendering includes,
        # as in the canonical UI value test. No dependency generators run here.
        if not projected_flag:
            ui=(ROOT/'soh/soh/SohGui/UIWidgets.hpp').read_text();a=ui.index('namespace UIWidgets {');b=ui.index('\nvoid PushStyleMenu(')
            generated=(ROOT/'scratch/soh-ui-xdk/generated/soh/soh/SohGui/UIWidgetTypes.h').read_text();prefix=generated[:generated.index('namespace UIWidgets {')]
            stable(folder/'UIWidgetTypes.h',prefix+ui[a:b]+'\n}\n')
            menu=(ROOT/'soh/soh/SohGui/MenuTypes.h').read_text().replace('#include <libultraship/libultraship.h>','#include <functional>\n#include <variant>\n#include "ship/window/WindowBackend.h"\n#include "ship/audio/Audio.h"').replace('#include "UIWidgets.hpp"','#include "UIWidgetTypes.h"')
            stable(folder/'MenuTypes.h',menu)
        widget='#include "MenuTypes.h"\n'
        if projected_flag:widget+='#include "soh-input-editor/support.h"\n'
        widget+='const char* editorWidgetNames[] = {'+','.join(names)+'};\n'+(OWN/'widget_contract.cpp').read_text()
        stable(folder/'widget.cpp',widget)
        for kind in ('state','widget'):
            command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']
            if projected_flag:command+=['/DSHIPYARD_EDITOR_PROJECTED']
            command+=['/I'+str(folder)]+['/I'+str(p) for p in includes()]+[str(folder/(kind+'.cpp')),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/(kind+'.exe'))]
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/(kind+'-build.log'),result.stdout+result.stderr)
            assert result.returncode==0,folder/(kind+'-build.log')
            result=subprocess.run([str(folder/(kind+'.exe'))],cwd=ROOT,capture_output=True,text=True)
            row=dict(kind=kind,projected=projected_flag,command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);records.append(row)
            assert result.returncode==0,row
    for kind in ('state','widget'):
        cases=[r for r in records if r['kind']==kind];assert cases[0]['stdout']==cases[1]['stdout'],cases
    stable(OUT/'verification.json',json.dumps(dict(host=records,full_function_definitions=len(signatures(original)),retained_field_declarations=len(original_fields),cvar_expressions=len(cvarkeys(original)),registered_search_widgets=7,native_literal_bytes_checked=len(manifest['literals']),native_ui_executed=False,scope='Exact data/method fixture, real WidgetInfo/CheckboxOptions/SearchWidget value semantics; no window/game services substituted'),indent=2)+'\n')
    print('Complete editor signatures/fields/CVars retained; original/projected initialization and widget value contracts match')
if __name__=='__main__':main()
