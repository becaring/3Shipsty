"""Source-locked full modern SaveManager and native XContent storage boundary."""
import argparse, hashlib, json, re, runpy, struct, subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import syntax
from prepare_game_interactor import call_sites
from cpp_ast import PARSER,walk
OWN=ROOT/'platform/shipyard/save-storage';OUT=ROOT/'scratch/save-storage-xdk'
SOURCES=['soh/soh/SaveManager.h','soh/soh/SaveManager.cpp','soh/soh/SohGui/SohGui.hpp']
METHODS=['LoadBaseVersion1','LoadBaseVersion2','LoadBaseVersion3','LoadBaseVersion4','SaveBase',
         'SaveArray','SaveStruct','LoadArray','LoadStruct','LoadCharArray','AddInitFunction',
         'AddLoadFunction','AddSaveFunction','AddPostFunction','GetSaveSectionID',
         'ThreadPoolWait','WriteSaveFile','ReadSaveFile','GetFileName','GetFileTempName',
         'SaveGlobal','CreateDefaultGlobal','SaveFile_Exist']
METHODS+=['SaveManager','SaveFileThreaded','SaveSection','SaveFile','LoadFile','DeleteZeldaFile','CopyZeldaFile','IsRandoFile','InitFile','InitFileImpl','InitFileNormal','InitFileDebug','InitFileMaxed','StartupCheckAndInitMeta','Init']
def methods(text):
    return {re.search(r'SaveManager::(\w+)\(',n.child_by_field_name('declarator').text.decode()).group(1):n.text.decode()
            for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition'
            and n.child_by_field_name('declarator') is not None
            and re.search(r'SaveManager::(\w+)\(',n.child_by_field_name('declarator').text.decode())}
def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def project(name,text):
    if name.endswith('SohGui.hpp'):
        declaration=re.search(r'void RegisterPopup\([\s\S]*?;',text).group()
        return '#pragma once\n#include <string>\n#include <functional>\nnamespace SohGui {\n'+declaration+'\n}\n'
    text=text.replace('#include <filesystem>','#include "save-storage/storage.h"').replace('std::filesystem','xbox_compat::filesystem')
    text=syntax(text)
    text=re.sub(r'using (\w+) = (.*?);',r'typedef \2 \1;',text)
    text=text.replace('typedef void (*)(bool isDebug) InitFunc;','typedef void (*InitFunc)(bool isDebug);')
    for alias,args in [('LoadFunc',''),('SaveFunc','SaveContext* saveContext, int sectionID, bool fullSave'),('PostFunc','int version')]:
        text=text.replace('typedef void (*)('+args+') '+alias+';','typedef void (*'+alias+')('+args+');')
    text=text.replace('T{}','T()')
    if name.endswith('.h'):
        text=text.replace('int sectionIndex = SECTION_ID_MAX;','int sectionIndex;').replace('nlohmann::json* currentJsonContext = nullptr;','nlohmann::json* currentJsonContext;')
        text=text.replace('#include <map>','#include <cassert>\n#include <array>\n#include "async/native.h"\n#include <map>')
    else:
        text=call_sites(text,name)
        text=once(text,'SaveManager::SaveManager() {','SaveManager::SaveManager() : sectionIndex(SECTION_ID_MAX), currentJsonContext(nullptr) {')
        text=text.replace('#include <libultraship/libultraship.h>','#include <libultraship/bridge.h>\n#include <ship/Context.h>')
        text=once(text,'#include "soh/SohGui/SohGui.hpp"','#include "save-storage/popup.h"')
        text=text.replace('using namespace std::string_literals;','')
        text=re.sub(r'std::to_string\((version|fileNum \+ 1|fileNum|sectionVersion|GetUnixTimestamp\(\)|saveBlock\["version"\].get<int>\(\))\)',r'std::to_string(static_cast<long long>(\1))',text)
        text=text.replace('sectionSaveHandlers.emplace(index, sfi);','sectionSaveHandlers.insert(std::make_pair(index, sfi));')
        text=text.replace('sectionRegistry.emplace(name, index);','sectionRegistry.insert(std::make_pair(name, index));')
        text=text.replace('SPDLOG_ERROR("Adding load function for section and version that already has one: " +', 'SPDLOG_ERROR("{}", "Adding load function for section and version that already has one: " +')
        text=text.replace('SPDLOG_ERROR("Adding save function for section that already has one: " +','SPDLOG_ERROR("{}", "Adding save function for section that already has one: " +')
        text=text.replace('SPDLOG_ERROR("Adding post function for section that already has one: " +','SPDLOG_ERROR("{}", "Adding post function for section that already has one: " +')
        text=text.replace('SPDLOG_ERROR("Save at " +','SPDLOG_ERROR("{}", "Save at " +').replace('SPDLOG_WARN("Save " +','SPDLOG_WARN("{}", "Save " +').replace('SPDLOG_ERROR("Save " +','SPDLOG_ERROR("{}", "Save " +').replace('SPDLOG_ERROR("Unrecognized save version " +','SPDLOG_ERROR("{}", "Unrecognized save version " +')
        text=text.replace('SaveManager::Instance->', 'ShipyardSaveInstance()->')
        text='#include "save-storage/save_support.h"\n'+text
        for owner,key in [('sectionLoadHandlers','name'),('sectionLoadHandlers[name]','version'),('sectionRegistry','name'),('coreSectionIDsByName','name'),('postHandlers','name'),('sectionRegistry','sectionName'),('sectionLoadHandlers','sectionName'),('handler','sectionVersion')]:
            text=text.replace('!'+owner+'.contains('+key+')',owner+'.find('+key+') == '+owner+'.end()')
            text=text.replace(owner+'.contains('+key+')',owner+'.find('+key+') != '+owner+'.end()')
        text=text.replace('Ship::Context::GetPathRelativeToAppDirectory("Save")','Shipyard::Storage::SaveDirectory()')
        text=once(text,'Ship::Context::GetPathRelativeToAppDirectory("oot_save.sav")','Shipyard::LegacySave::Path()')
        text=once(text,'Ship::Context::GetPathRelativeToAppDirectory("oot_save.bak")','Shipyard::LegacySave::BackupPath()')
        text='#include "legacy-save/storage_path.h"\n'+text
        text=once(text,'        ConvertFromUnversioned();\n        xbox_compat::filesystem::rename(sOldSavePath, sOldBackupSavePath);',
                  '        if (xbox_compat::filesystem::exists(sOldBackupSavePath)) throw std::runtime_error("Legacy save backup already exists; preserve both files before importing");\n        ConvertFromUnversioned();\n        xbox_compat::filesystem::rename(sOldSavePath, sOldBackupSavePath);\n        Shipyard::Storage::Commit();')
        text=text.replace('std::ofstream(savePath,','std::ofstream(savePath.c_str(),').replace('std::ifstream(savePath,','std::ifstream(savePath.c_str(),')
        text=re.sub(r'(std::(?:i|o)fstream \w+\()((?:sGlobalPath|fileName|tempFile|GetFileName\(fileNum\)))\)',r'\1\2.c_str())',text)
        text=text.replace('std::vector<char> data(std::istreambuf_iterator<char>(input), {});','std::vector<char> data((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());')
        # The modern worker still owns serialization and callbacks. Only durable
        # byte publication crosses the native platform boundary.
        text=once(text,'xbox_compat::filesystem::rename(tempFile, fileName);','if (!output) throw std::runtime_error("save temporary write failed");\n    Shipyard::Storage::Replace(tempFile, fileName);')
        text=once(text,'    std::ofstream output(sGlobalPath.c_str());\n    output << std::setw(1) << globalBlock << std::endl;',
                  '    Shipyard::Storage::WriteAtomic(sGlobalPath, globalBlock.dump(1) + "\\n");')
        text=once(text,'            std::ofstream output(GetFileName(fileNum).c_str());\n            output << metaSaveBlock.dump(1);\n            output.close();',
                  '            Shipyard::Storage::WriteAtomic(GetFileName(fileNum), metaSaveBlock.dump(1));')
        # Preserve upstream data and hooks, release the copied context/mutex on
        # real I/O errors rather than leaving subsequent save/load deadlocked.
        text=once(text,'void SaveManager::SaveFileThreaded(int fileNum, SaveContext* saveContext, int sectionID) {\n    saveMtx.lock();',
                  'void SaveManager::SaveFileThreaded(int fileNum, SaveContext* saveContext, int sectionID) {\n    std::unique_ptr<SaveContext> ownedContext(saveContext);\n    Shipyard::Async::lock_guard<Shipyard::Async::mutex> saveLock(saveMtx);')
        text=once(text,'    delete saveContext;','    ownedContext.reset();')
        text=once(text,'    SPDLOG_INFO("Save File Finish - fileNum: {}", fileNum);\n    saveMtx.unlock();','    SPDLOG_INFO("Save File Finish - fileNum: {}", fileNum);')
        text=text.replace('xbox_compat::filesystem::rename(fileName, newFileName);','xbox_compat::filesystem::rename(fileName, newFileName);\n        Shipyard::Storage::Commit();')
        text=text.replace('xbox_compat::filesystem::copy_file(GetFileName(from), GetFileName(to));','xbox_compat::filesystem::copy_file(GetFileName(from), GetFileName(to));\n    Shipyard::Storage::Commit();')
        text=text.replace('xbox_compat::filesystem::remove(GetFileName(fileNum));','xbox_compat::filesystem::remove(GetFileName(fileNum));\n        Shipyard::Storage::Commit();')
        text=once(text,'for (auto& block : saveBlock["sections"].items()) {','for (nlohmann::json::iterator block = saveBlock["sections"].begin(); block != saveBlock["sections"].end(); ++block) {')
        text=text.replace('randoBlock["masterQuestDungeonCount"] > 0','Shipyard::Storage::JsonGreaterThanInt(randoBlock["masterQuestDungeonCount"], 0)').replace('randoBlock["masterQuestDungeonCount"] < 12','Shipyard::Storage::JsonLessThanInt(randoBlock["masterQuestDungeonCount"], 12)')
        lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
        text='#include "resources/runtime_support.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    return text
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text());generated={}
    for name,expected in lock.get('evidence',{}).items():
        if sha((ROOT/name).read_text(encoding='utf-8-sig'))!=expected:raise ValueError('Save evidence drift '+name)
    for name,expected in lock['sources'].items():
        original=(ROOT/name).read_text(encoding='utf-8-sig')
        if sha(original)!=expected:raise ValueError('Save source drift '+name)
        result=project(name,original)
        output='include/save-storage/popup.h' if name.endswith('SohGui.hpp') else name
        stable(OUT/'generated'/output,result);generated[output]=sha(result)
    full=(OUT/'generated/soh/soh/SaveManager.cpp').read_text();bodies=methods(full)
    prefix='''#include "resources/runtime_support.h"
#include "soh/SaveManager.h"
#include "save-storage/save_support.h"
#include "legacy-save/storage_path.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/randomizer/SeedContext.h"
#include "OTRGlobals.h"
#include "ResourceManagerHelpers.h"
#include "save-storage/popup.h"
#include "soh/util.h"
#include "z64.h"
#include "cvar_prefixes.h"
#include "functions.h"
#include "macros.h"
#include <variables.h>
#include <libultraship/bridge.h>
#include <spdlog/spdlog.h>
#include <fstream>
#include <iomanip>
#include <memory>
extern "C" SaveContext gSaveContext;
'''
    bridges=[]
    for node in walk(PARSER.parse(full.encode()).root_node):
        if node.type!='linkage_specification' or not node.text.startswith(b'extern "C"'):continue
        if re.search(rb'\bSave_(?!LoadFile\b)\w+\(',node.text):bridges.append(node.text.decode())
    if len(bridges)!=11:raise ValueError('Save C bridge inventory changed')
    fragment=prefix+'\n'.join(bodies[n] for n in METHODS)+'\n'+'\n'.join(bridges)+'\n'
    stable(OUT/'generated/SaveSerialization.cpp',fragment)
    stable(OUT/'manifest.json',json.dumps(dict(sources=lock,generated=generated,
        generator_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        helpers={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OWN.iterdir() if p.suffix in ('.h','.cpp')},
        source_fragments={'SaveSerialization.cpp':dict(original=SOURCES[1],methods=METHODS,c_bridges=11,sha256=sha(fragment))},
        full_tu_status='retained; native compile requires remaining modern randomizer headers'),indent=2)+'\n')
def includes():
    from prepare_ship_utils import includes as base
    return [OUT/'generated/soh',OUT/'generated/include',ROOT/'scratch/randomizer-xdk/generated/soh',ROOT/'scratch/randomizer-xdk/generated/soh/soh',ROOT/'scratch/application-xdk/generated/soh/soh',ROOT/'scratch/game-interactor-xdk/generated/soh/soh',ROOT/'scratch/ship-utils-xdk/generated/soh/soh',ROOT/'scratch/game-xdk/full/source/soh/soh',ROOT/'soh/soh']+base()
def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    flags=json.loads((ROOT/'scratch/ship-utils-xdk/xdk/build.json').read_text())[0]['command'][:-3]
    flags[1:1]=['/I'+str(p) for p in includes()]
    rows=[]
    for source in [OUT/'generated/SaveSerialization.cpp',OWN/'storage.cpp',OWN/'atomic_file.cpp']:
        obj=folder/(source.stem+'.obj');command=flags+['/TP',str(source),'/Fo'+str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=result.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        if not result.returncode:row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        if source.name=='SaveSerialization.cpp':row['source_fragment']=dict(original=SOURCES[1],methods=METHODS)
        rows.append(row)
        print(source.name+': '+str(result.returncode),flush=True)
        if result.returncode:print('\n'.join(s for s in (result.stdout+result.stderr).splitlines() if 'error ' in s)[:6500],flush=True)
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(r['exit'] for r in rows):raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');a=p.parse_args();build() if a.build else prepare()
