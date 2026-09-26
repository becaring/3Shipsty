"""Keep resolution buttons on the existing percentage widget and update callback."""
from pathlib import Path
import sys
import runpy
import subprocess
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_soh_menus import project
from cpp_ast import PARSER, walk

def definition(text, kind, name):
    matches = []
    for node in walk(PARSER.parse(text.encode()).root_node):
        if node.type != kind:
            continue
        field = node.child_by_field_name('declarator' if kind == 'function_definition' else 'name')
        if field is not None and field.text.decode().split('(')[0].strip() == name:
            matches.append(node.text.decode())
    assert matches, name
    return '\n'.join(matches)

def exercise(widget, header):
    """Actual widget/dispatch bodies; external services and theme colors are fixtures."""
    body = (ROOT/'soh/soh/SohGui/UIWidgets.cpp').read_text()
    types = '\n'.join(definition(header, 'struct_specifier', name)+';'
                      for name in ('WidgetOptions', 'ButtonOptions', 'FloatSliderOptions'))
    methods = '\n'.join(definition(body, 'function_definition', name)
                        for name in ('PushStyleButton', 'PopStyleButton', 'PushStyleSlider', 'PopStyleSlider',
                                     'Button', 'ClampFloat', 'SliderFloat', 'CVarSliderFloat'))
    # Observe the real ImGui button rectangle for pointer clicks; retain its result.
    methods = methods.replace('bool dirty = ImGui::Button(label, options.size);',
        'bool dirty = ImGui::Button(label, options.size);\n'
        'buttonCenters[label] = (ImGui::GetItemRectMin()+ImGui::GetItemRectMax())*0.5f;')
    options = widget[widget.index('FloatSliderOptions('):].strip().removesuffix(');')
    options = options.replace('Shipyard::SohUI::ValueInit()', '')
    callback = widget[widget.index('.Callback(')+len('.Callback('):widget.index('\n        .PreFunc')].removesuffix(')')
    menu = (ROOT/'soh/soh/SohGui/Menu.cpp').read_text()
    dispatch = menu.split('case WIDGET_CVAR_SLIDER_FLOAT: {',1)[1].split('} break;',1)[0]
    text = r'''
#define IMGUI_DEFINE_MATH_OPERATORS
#include "imgui.h"
#include "imgui_internal.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <functional>
#include <map>
#include <memory>
#include <string>
static float stored=1, rendered=0;
static int writes=0, saves=0, callbacks=0, hooks=0;
#define CVAR_INTERNAL_RESOLUTION "gInternalResolution"
float CVarGetFloat(const char* name,float){assert(std::string(name)==CVAR_INTERNAL_RESOLUTION);return stored;}
void CVarSetFloat(const char* name,float value){assert(std::string(name)==CVAR_INTERNAL_RESOLUTION);stored=value;++writes;}
namespace Ship { struct Context {
 static Context* GetInstance(){static Context c;return &c;}
 Context* GetWindow(){return this;} Context* GetGui(){return this;}
 void SaveConsoleVariablesNextFrame(){++saves;}
 void SetResolutionMultiplier(float f){rendered=f;++callbacks;}
}; }
namespace ShipInit { void Init(const char*){++hooks;} }
namespace UIWidgets {
enum Colors { Gray, NoColor };
enum LabelPositions { Near, Far, Above, None, Within };
enum ComponentAlignments { Left, Right };
namespace Sizes { const ImVec2 Fill(-1,0), Inline(0,0); }
static std::map<std::string,ImVec2> buttonCenters;
static const std::map<Colors,ImVec4> ColorValues={{Gray,ImVec4(0.5f,0.5f,0.5f,1)}};
bool Ship_IsCStringEmpty(const char* s){return !s || !*s;}
std::string WrappedText(const char* s){return s;}
''' + types + '\n' + methods + r'''
}
using namespace UIWidgets;
struct WidgetInfo {
 std::string name="Internal Resolution"; const char* cVar=CVAR_INTERNAL_RESOLUTION;
 std::shared_ptr<FloatSliderOptions> options;
 std::function<void(WidgetInfo&)> callback;
};
static WidgetInfo widget;
static void frame(){
 ImGui::NewFrame();ImGui::SetNextWindowPos(ImVec2(10,10));ImGui::SetNextWindowSize(ImVec2(600,200));
 ImGui::Begin("Resolution");auto menuThemeIndex=Gray;
''' + dispatch + r'''
 ImGui::End();ImGui::Render();
}
static void click(const char* label){
 auto p=buttonCenters.at(label);auto& io=ImGui::GetIO();io.AddMousePosEvent(p.x,p.y);frame();
 io.AddMouseButtonEvent(0,true);frame();io.AddMouseButtonEvent(0,false);frame();
}
static void expect(float value,int changed){
 if(std::fabs(stored-value)>=0.00001f)std::fprintf(stderr,"stored=%f expected=%f writes=%d expected=%d\n",stored,value,writes,changed);
 assert(std::fabs(stored-value)<0.00001f);assert(writes==changed && saves==changed && callbacks==changed && hooks==changed);
 if(changed)assert(std::fabs(rendered-value)<0.00001f);
}
int main(){
 ImGui::CreateContext();auto& io=ImGui::GetIO();io.IniFilename=NULL;io.DisplaySize=ImVec2(1280,720);
 unsigned char* pixels;int w,h;io.Fonts->GetTexDataAsRGBA32(&pixels,&w,&h);
 widget.options=std::make_shared<FloatSliderOptions>(''' + options + ');\nwidget.callback=' + callback + r''';
 frame();frame();expect(1,0);
 click("+");expect(1.01f,1);click("-");expect(1,2);
 stored=1.99f;click("+");expect(2,3);click("+");expect(2,3);
 stored=0.51f;click("-");expect(0.5f,4);click("-");expect(0.5f,4);
 ImGui::DestroyContext();puts("Real resolution +/- clicks write CVar, schedule save, and update renderer within bounds");
}
'''
    folder=ROOT/'scratch/resolution-controls-test';folder.mkdir(exist_ok=True)
    (folder/'contract.cpp').write_text(text)
    compiler,env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    imgui=ROOT/'scratch/imgui-xdk/original'
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/I'+str(imgui),str(folder/'contract.cpp')]
    command += [str(imgui/(name+'.cpp')) for name in ('imgui','imgui_draw','imgui_widgets','imgui_tables')]
    command += ['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
    (folder/'build.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,folder/'build.log'
    result=subprocess.run([str(folder/'contract.exe')],cwd=folder,capture_output=True,text=True)
    (folder/'run.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,(result.returncode,result.stderr)
    print(result.stdout.strip())

def main():
    source = (ROOT / 'soh/soh/SohGui/SohMenuSettings.cpp').read_text(encoding='utf-8-sig')
    output = project('SohMenuSettings.cpp', source)
    def widget(text):
        start = text.index('    AddWidget(path, "Internal Resolution",')
        return text[start:text.index('\n#ifndef __WIIU__', start)]
    original, actual = widget(source), widget(output)
    # Exact comparison protects range, percentage formatting, CVar, disables,
    # and the immediate renderer callback from accidental replacement.
    expected = original.replace('.ShowButtons(false)', '.ShowButtons(true)')
    expected = expected.replace('FloatSliderOptions()', 'FloatSliderOptions(Shipyard::SohUI::ValueInit())')
    assert actual == expected
    assert '.Min(0.5f)' in actual and '.Max(2.0f)' in actual
    assert '.IsPercentage()' in actual and 'SetResolutionMultiplier(' in actual
    options = (ROOT / 'soh/soh/SohGui/UIWidgets.hpp').read_text()
    assert 'float step = 0.01f;' in options
    exercise(actual, options)
    print('Resolution controls: existing callback/range and one-percent step retained')

if __name__ == '__main__':
    main()
