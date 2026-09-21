"""Real Settings constructor and every list value; full source registration audit."""
import hashlib,json,re,runpy,subprocess
from prepare_randomizer_settings import ROOT,OUT,OWN,BASE,prepare,includes,methods
from prepare_randomizer import default_arguments,edits_apply
from prepare_archives import stable
from cpp_ast import PARSER,walk
from test_randomizer_options import friend
from prepare_custom_message import literal_bytes

def signature(n):return n.child_by_field_name('declarator').text.decode()
def calls(text):
    out=[]
    for n in walk(PARSER.parse(text.encode()).root_node):
        if n.type!='call_expression':continue
        fn=n.child_by_field_name('function').text.decode()
        if fn.startswith('OPT_'):
            args=n.child_by_field_name('arguments');out.append((fn,args.named_children[0].text.decode()))
    return out
def cvars(text):
    return [n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='call_expression' and n.child_by_field_name('function').text.startswith(b'CVAR_')]
def main():
    prepare();original=(ROOT/(BASE+'settings.cpp')).read_text(encoding='utf-8');projected=(OUT/'generated'/(BASE+'settings.cpp')).read_text()
    assert [signature(n) for n in methods(default_arguments(original))]==[signature(n) for n in methods(projected)]
    assert calls(original)==calls(projected);assert cvars(original)==cvars(projected)
    assert re.findall(r'^#define OPT_.+$',original,re.M)==re.findall(r'^#define OPT_.+$',projected,re.M)
    desc_original=(ROOT/(BASE+'option_descriptions.cpp')).read_text(encoding='utf-8')
    desc_projected=(OUT/'generated'/(BASE+'option_descriptions.cpp')).read_text()
    def literals(text):return [literal_bytes(n.text.decode()) for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='string_literal' and n.parent.type!='preproc_include']
    assert literals(desc_original)==literals(desc_projected)
    canonical=(ROOT/'scratch/randomizer-options-xdk/generated'/BASE/'SettingsConstructor.cpp').read_text()
    actual_ctor=next(n.text.decode() for n in methods(projected) if signature(n)=='Settings::Settings()')
    canonical_ctor=next(n.text.decode() for n in methods(canonical) if signature(n)=='Settings::Settings()')
    assert re.sub(r'\s+','',actual_ctor)==re.sub(r'\s+','',canonical_ctor)
    manifest=json.loads((OUT/'manifest.json').read_text());rows=[]
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    for projected_flag in (False,True):
        folder=OUT/('host-projected' if projected_flag else 'host-original');folder.mkdir(exist_ok=True)
        base=ROOT/'scratch/randomizer-options-xdk/generated' if projected_flag else ROOT
        for name in ('settings.h','option.h','tricks.h'):
            header=(base/BASE/name).read_text(encoding='utf-8').replace('#include "randomizerTypes.h"','#include "soh/Enhancements/randomizer/randomizerTypes.h"').replace('#include "soh/SohGui/MenuTypes.h"','#include "MenuTypes.h"')
            if name=='settings.h':header=header.replace('#include "SeedContext.h"','namespace Rando { class Context; }').replace('#include "3drando/spoiler_log.hpp"','')
            stable(folder/name,friend(header))
        src=projected if projected_flag else original
        functions=[n.text.decode() for n in methods(src) if signature(n).split('(')[0] in ('Settings::Settings','NumOpts','MultiVecOpts')]
        assert len(functions)==3
        evals=[]
        for i,row in enumerate(manifest['list_initializers']):
            typ=row['type'];value=row['replacement'] if projected_flag else row['source']
            if typ=='vector-copy':typ='std::string'
            if typ.startswith('std::unordered_map') or typ=='std::vector<uint8_t>':
                evals.append('{ '+typ+' values='+value+'; assert(values.empty()); printf("E 0\\n"); }');continue
            container=('std::set<' if row['kind']=='Set' else 'std::vector<')+typ+'> '
            scope=''
            if typ=='OptionValue*':scope='std::array<OptionValue,RSK_MAX> contextOptions={};auto& mOptions=contextOptions;'
            dump='Dump(values);'
            if typ=='Option*':dump='DumpPointers(values,&mOptions[0],mOptions.size());'
            elif typ=='OptionGroup*':dump='DumpPointers(values,&mOptionGroups[0],mOptionGroups.size());'
            elif typ=='OptionValue*':dump='DumpPointers(values,&contextOptions[0],contextOptions.size());'
            evals.append('{ '+scope+container+'values='+value+'; '+dump+' }')
        contract=(OWN/'value_contract.cpp').read_text().replace('/* LIST_EXPRESSIONS */','\n'.join(evals))
        source='#include "settings.h"\n#include "randomizer-settings/lists.h"\n#include "input/compiler.h"\nnamespace Rando {\n'+'\n'.join(functions)+'\n}\n'+contract
        stable(folder/'contract.cpp',source)
        ui=ROOT/'scratch/soh-ui-xdk'/('generated/soh/soh/SohGui' if projected_flag else 'host-original')
        command=[str(compiler),'/nologo','/std:c++20','/utf-8','/EHsc','/GR','/MD','/Od','/DNOMINMAX','/DSHIPYARD_AUDIO_TEST','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t','/I'+str(folder),'/I'+str(ui)]+['/I'+str(p) for p in includes()]
        if projected_flag:command+=['/DSHIPYARD_SETTINGS_PROJECTED']
        command+=[str(folder/'contract.cpp'),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe')]
        r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',r.stdout+r.stderr);assert not r.returncode,folder/'build.log'
        r=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        row=dict(projected=projected_flag,command=command,exit=r.returncode,stdout=r.stdout,stderr=r.stderr);rows.append(row);assert not r.returncode,row
    assert rows[0]['stdout']==rows[1]['stdout']
    native=json.loads((OUT/'xdk/build.json').read_text())
    for row in native:
        assert not row['exit'];assert row['source_sha256']==hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest()
    counts={name:sum(c[0]==name for c in calls(original)) for name in sorted(set(c[0] for c in calls(original)))}
    stable(OUT/'verification.json',json.dumps(dict(host=rows,native=native,original_functions=len(methods(original)),list_expressions=len(manifest['list_initializers']),registration_counts=counts,cvar_expressions=len(cvars(original)),description_literals=len(literals(desc_original)),constructor_matches_canonical=True,real_create_options_or_callbacks_executed=False),indent=2)+'\n')
    print('Settings constructor and '+str(len(manifest['list_initializers']))+' original/projected list values match; numeric/flattening contracts pass')
    print('Full '+str(len(methods(original)))+' definitions retained; registrations '+json.dumps(counts)+'; CVars '+str(len(cvars(original))))
if __name__=='__main__':main()
