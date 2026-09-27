"""Preserve current GUI functions and verify the full embedded font via ImGui."""
from pathlib import Path
from collections import Counter
import json
import re
import runpy
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from prepare_gui import prepare,OUT,OWN
from prepare_archives import stable
from cpp_ast import PARSER,walk


def functions(text):
    return {n.child_by_field_name('declarator').text.decode().split('(')[0].split()[-1]:n.text.decode()
            for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition'}


def main():
    prepare();folder=OUT/'host';folder.mkdir(exist_ok=True)
    manifest=(OUT/'manifest.json').read_bytes();prepare();assert manifest==(OUT/'manifest.json').read_bytes()
    unchanged=['GamepadNavigationEnabled','BlockGamepadNavigation','UnblockGamepadNavigation','CheckSaveCvars']
    original=(ROOT/'libultraship/src/ship/window/gui/Gui.cpp').read_text()
    current=functions(original);projected=functions((OUT/'generated/src/ship/window/gui/Gui.cpp').read_text())
    for name in unchanged:assert current['Gui::'+name]==projected['Gui::'+name],name
    reduced={'ApplyResolutionChanges':7,'GetIntegerScaleFactor':20,
             'CalculateGameViewport':16,'DrawGame':8}
    for name,original_locks in reduced.items():
        old=current['Gui::'+name];new=projected['Gui::'+name]
        assert old.count('mInterpreter.lock()')==original_locks,name
        expected_locals=2 if name=='GetIntegerScaleFactor' else 1
        assert new.count('auto interpreter = mInterpreter.lock();')==expected_locals,name
        assert new.count('mInterpreter.lock()')==expected_locals,name
        restored=re.sub(r'(?m)^[ \t]*auto interpreter = mInterpreter\.lock\(\);\n','',new)
        restored=restored.replace('interpreter->','mInterpreter.lock()->')
        assert restored==old,name
    draw=projected['Gui::DrawGame']
    assert draw.index('GetGameOverlay()->Draw();') < draw.index('auto interpreter = mInterpreter.lock();')
    # Every production method remains, including all complete concrete windows.
    for name in json.loads((OWN/'sources.lock.json').read_text())['sources']:
        if not name.endswith('.cpp'):continue
        def inventory(text):
            return Counter(n.child_by_field_name('declarator').text.decode().split('(')[0].split()[-1]
                           for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition')
        a=inventory((ROOT/'libultraship'/name).read_text());b=inventory((OUT/'generated'/name).read_text())
        assert all(b[k]>=count for k,count in a.items()),name
    font=(ROOT/'libultraship/include/ship/window/gui/Fonts.h').read_text()
    pieces=[m[0] for m in re.finditer(r'"(?:[^"\\]|\\.)*"',font[font.index('=')+1:])]
    # Compile each ORIGINAL literal separately, allowing the C++ compiler to
    # interpret C escapes independently of the generator's Python decoder.
    init=original[original.index('    // Add Font Awesome'):original.index('\n#if defined(__ANDROID__)',original.index('    // Add Font Awesome'))]
    init=init.replace('mImGuiIo->','io.')
    text='''#include "imgui.h"
#include "ship/window/gui/Fonts.h"
#include "ship/window/gui/IconsFontAwesome4.h"
#include <cstdio>
#include <cstring>
#include <string>
#include <stdexcept>
#define CHECK(c) do{if(!(c))throw std::runtime_error(#c);}while(0)
static const char* originalPieces[]={
'''+',\n'.join(pieces)+'''
};
static unsigned Build(const char* fontawesome_compressed_data_base85){
    ImGui::CreateContext();ImGuiIO& io=ImGui::GetIO();io.IniFilename=NULL;
'''+init+'''
    unsigned char* pixels;int width,height;io.Fonts->GetTexDataAsRGBA32(&pixels,&width,&height);
    CHECK(width>0 && height>0 && io.Fonts->Fonts.Size==1);
    CHECK(io.Fonts->Fonts[0]->FindGlyphNoFallback(ICON_MIN_FA)!=NULL);
    unsigned hash=2166136261u;
    for(size_t i=0;i<size_t(width)*height*4;++i)hash=(hash^pixels[i])*16777619u;
    std::printf("%dx%d atlas glyphs=%d hash=%08x\\n",width,height,io.Fonts->Fonts[0]->Glyphs.Size,hash);
    ImGui::DestroyContext();return hash;
}
int main(){
    std::string original;
    for(size_t i=0;i<sizeof(originalPieces)/sizeof(originalPieces[0]);++i)original+=originalPieces[i];
    CHECK(original.size()+1==sizeof(fontawesome_compressed_data_base85));
    CHECK(std::memcmp(original.c_str(),fontawesome_compressed_data_base85,original.size()+1)==0);
    CHECK(Build(original.c_str())==Build(fontawesome_compressed_data_base85));
    std::puts("155711 font bytes and real merged font atlas agree; complete current GUI methods retained");
}
'''
    stable(folder/'contract.cpp',text)
    env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')));compiler,environment=env['host_environment']()
    inc=[OUT/'generated/include',ROOT/'scratch/imgui-xdk/generated',ROOT/'libultraship/include']
    units=[ROOT/'scratch/imgui-xdk/generated'/(n+'.cpp') for n in ('imgui','imgui_draw','imgui_tables','imgui_widgets')]
    command=[compiler,'/nologo','/std:c++20','/EHsc','/MD','/O2']+['/I'+str(p) for p in inc]+[folder/'contract.cpp']+units+['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
    env['invoke'](command,folder,'build',environment)
    result=env['invoke']([folder/'contract.exe'],folder,'run')
    stable(OUT/'verification.json',json.dumps(dict(host_output=result['stdout'],unchanged_methods=unchanged,target_runtime_executed=False),indent=2)+'\n')
    print(result['stdout'])
if __name__=='__main__':main()
