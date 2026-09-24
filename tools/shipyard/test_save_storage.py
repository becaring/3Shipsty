"""Actual modern save schema/migration differential plus native recipe checks."""
import json,runpy,subprocess,hashlib,re
from prepare_save_storage import ROOT,OUT,OWN,prepare,methods,includes,METHODS
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
from prepare_archives import stable
from prepare_soh_resources import includes as resource_includes
from cpp_ast import PARSER,walk
RUNTIME=['LoadBaseVersion1','LoadBaseVersion2','LoadBaseVersion3','LoadBaseVersion4','SaveBase','SaveArray','SaveStruct','LoadArray','LoadStruct','LoadCharArray','ThreadPoolWait']
def main():
    prepare();compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']();records=[]
    def keys(text):
        result=[]
        for node in walk(PARSER.parse(text.encode()).root_node):
            if node.type!='call_expression':continue
            function=node.child_by_field_name('function');args=node.child_by_field_name('arguments')
            if function is None or args is None:continue
            if not re.search(rb'(SaveData|LoadData|SaveArray|LoadArray|SaveStruct|LoadStruct|LoadCharArray)$',function.text):continue
            if args.named_children and args.named_children[0].type=='string_literal':result.append(args.named_children[0].text)
        return result
    original=(ROOT/'soh/soh/SaveManager.cpp').read_text();projected_source=(OUT/'generated/soh/soh/SaveManager.cpp').read_text()
    assert keys(original)==keys(projected_source),'serialized keys changed'
    init=methods(projected_source)['Init']
    ordered=['Shipyard::LegacySave::Path()', 'Shipyard::LegacySave::BackupPath()',
             'if (xbox_compat::filesystem::exists(sOldSavePath))',
             'if (xbox_compat::filesystem::exists(sOldBackupSavePath)) throw',
             'ConvertFromUnversioned();', 'xbox_compat::filesystem::rename(sOldSavePath, sOldBackupSavePath);',
             'Shipyard::Storage::Commit();']
    positions=[init.index(s) for s in ordered]
    assert positions==sorted(positions),'Legacy path/validation/publication order changed'
    assert 'catch' not in init[positions[3]:positions[-1]],'Import failure must not fall through to backup'
    for projected in (False,True):
        folder=OUT/('host-projected' if projected else 'host-original');folder.mkdir(exist_ok=True)
        base=OUT/'generated' if projected else ROOT
        header=(base/'soh/soh/SaveManager.h').read_text()
        # Same complete class and storage. Test-only construction isolates the
        # serialized-data methods from application registration dependencies.
        header=header.replace('class SaveManager {','struct SaveSerializationFixtureTag {};\nclass SaveManager {\n    friend struct SaveSerializationAccess;')
        header=header.replace('    SaveManager();','    SaveManager();\n    explicit SaveManager(SaveSerializationFixtureTag) : sectionIndex(SECTION_ID_MAX), currentJsonContext(nullptr) {}')
        stable(folder/'soh/SaveManager.h',header)
        bodies=methods((base/'soh/soh/SaveManager.cpp').read_text())
        source='#include <mutex>\n#include "resources/runtime_support.h"\n#include "soh/SaveManager.h"\n#include "z64.h"\n#include "soh/util.h"\n#include "macros.h"\n'
        if projected:source+='#include "save-storage/instance.h"\n'
        source+='extern "C" SaveContext gSaveContext;\n'+'\n'.join(bodies[n] for n in RUNTIME)+'\n'
        utility=(ROOT/'soh/soh/util.cpp').read_text()
        leaf=[n.text.decode() for n in walk(PARSER.parse(utility.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator').text.startswith(b'SohUtils::CopyStringToCharArray(')]
        assert len(leaf)==1
        source+='\n'+leaf[0]+'\n'
        source+=(OWN/'serialization_contract.cpp').read_text().replace('SaveManager manager(SaveSerializationFixtureTag());','SaveManager manager((SaveSerializationFixtureTag()));')
        stable(folder/'contract.cpp',source)
        paths=[folder,ROOT/'platform/shipyard',PLATFORM_BASE,PLATFORM_BASE/'sources',ROOT/'scratch/async-xdk/generated']+(includes() if projected else resource_includes(False))
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/O2','/Gy','/DNOMINMAX','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']
        if not projected:command+=['/Zc:preprocessor','/I'+str(ROOT/'platform/shipyard/json/upstream/include')]
        command+=['/I'+str(p) for p in paths]
        units=[folder/'contract.cpp',PLATFORM_BASE / 'sources/async/native.cpp']
        if projected:
            units += [PLATFORM_BASE/'sources/json/json.cpp']
        command+=list(map(str,units))+['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe'),'/link','/OPT:REF']
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        if result.returncode:raise AssertionError(folder/'build.log')
        result=subprocess.run([str(folder/'contract.exe')],cwd=ROOT,capture_output=True,text=True)
        stable(folder/'output.txt',result.stdout)
        record=dict(command=command,exit=result.returncode,stdout_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),lines=len(result.stdout.splitlines()),stderr=result.stderr)
        stable(folder/'run.json',json.dumps(record,indent=2)+'\n');records.append(record)
        if result.returncode:raise AssertionError(record)
    assert records[0]['stdout_sha256']==records[1]['stdout_sha256'],records
    atomic=[]
    for projected in (False,True):
        folder=OUT/('atomic-projected' if projected else 'atomic-original');folder.mkdir(exist_ok=True)
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/O2','/Gy','/DNOMINMAX']
        if not projected:command+=['/DSHIPYARD_COMPARE_ORIGINAL','/I'+str(ROOT/'platform/shipyard/json/upstream/include')]
        command+=['/I'+str(p) for p in [PLATFORM_BASE]+includes()]
        command+=list(map(str,[OWN/'atomic_contract.cpp',PLATFORM_BASE/'sources/storage/atomic_file.cpp']))
        if projected:command+=[str(PLATFORM_BASE/'sources/json/json.cpp')]
        command+=['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe'),'/link','/OPT:REF']
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
        assert result.returncode==0,folder/'build.log'
        result=subprocess.run([str(folder/'contract.exe'),str(folder/'save-fixture.sav')],cwd=ROOT,capture_output=True,text=True)
        row=dict(command=command,exit=result.returncode,stdout=result.stdout,stderr=result.stderr);atomic.append(row)
        assert result.returncode==0,row
    assert atomic[0]['stdout']==atomic[1]['stdout'],atomic
    stable(OUT/'verification.json',json.dumps(dict(host=records,atomic=atomic,actual_methods=RUNTIME,fixture_scope='exact class plus test-only constructor; no game services linked',native_execution=False),indent=2)+'\n')
    print('Save schema and all four base-version loaders match: '+str(records[0]['lines'])+' complete serialized outputs')
if __name__=='__main__':main()
