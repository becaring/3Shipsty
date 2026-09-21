"""Source-locked 9.2.3 legacy conversion and explicit producer-order byte reader."""
import argparse,ctypes,hashlib,json,re,struct,subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_save_storage import includes,methods
OWN=ROOT/'platform/shipyard/legacy-save';OUT=ROOT/'scratch/legacy-save-xdk'
SOURCE='soh/soh/SaveManager.cpp'
PRODUCER='73ff7ef3dae83ec85afb20ec6453c69967bb0b96'
SCALARS={'u8':ctypes.c_uint8,'s8':ctypes.c_int8,'char':ctypes.c_char,'u16':ctypes.c_uint16,'s16':ctypes.c_int16,'u32':ctypes.c_uint32,'s32':ctypes.c_int32,'f32':ctypes.c_float}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def git_source(path):
    return subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=ROOT).decode('utf8')
def declarations(text):
    return {name:body for body,name in re.findall(r'typedef struct\s*{([^{}]*?)}\s*(\w+);',text,re.S)}
def layout(decls):
    types=dict(SCALARS);result={}
    def get(name):
        if name in types:return types[name]
        rows=[];fields=[]
        clean=re.sub(r'/\*.*?\*/|//[^\n]*','',decls[name],flags=re.S)
        for kind,names in re.findall(r'(\w+)\s+([^;]+);',clean):
            for n in names.split(','):
                field,count=re.fullmatch(r'(\w+)(?:\[(.+)\])?',n.strip()).groups()
                count=2 if count=='TIMER_ID_MAX' else int(count,0) if count else 1
                scalar=get(kind);ft=scalar*count if '[' in n else scalar
                fields.append((field,ft));rows.append(dict(name=field,kind=kind,count=count,array='[' in n))
        cls=type(name,(ctypes.Structure,),{'_fields_':fields});types[name]=cls
        for row in rows:row.update(offset=getattr(cls,row['name']).offset,size=getattr(cls,row['name']).size)
        result[name]=dict(size=ctypes.sizeof(cls),alignment=ctypes.alignment(cls),fields=rows)
        return cls
    for name in decls:get(name)
    return result
def scalar_fields(model,name,prefix='',base=0):
    for f in model[name]['fields']:
        for i in range(f['count']):
            target=prefix+f['name']+('['+str(i)+']' if f['array'] else '')
            offset=base+f['offset']+i*(f['size']//f['count'])
            if f['kind'] in SCALARS:yield target,offset,f['kind']
            else:yield from scalar_fields(model,f['kind'],target+'.',offset)
def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text())
    source=(ROOT/SOURCE).read_text(encoding='utf8')
    for path,expected in lock['sources'].items():assert sha((ROOT/path).read_text(encoding='utf8'))==expected,'Pinned source drift: '+path
    for path,expected in lock['producer']['files'].items():assert sha(git_source(path))==expected,path
    start=source.index('typedef struct {',source.index('// Functionality required'))
    structs=source[start:source.index('void CopyV0Save')]
    decls=declarations(structs);model=layout(decls)
    assert model['SaveContext_v0']['size']==0x1428 and model['Inventory_v0']['size']==0x60
    assertions=[]
    for name,entry in model.items():
        assertions.append('typedef char Size_'+name+'[(sizeof('+name+')=='+str(entry['size'])+')?1:-1];')
        for f in entry['fields']:
            assertions.append('typedef char Offset_'+name+'_'+f['name']+'[(offsetof('+name+','+f['name']+')=='+str(f['offset'])+')?1:-1];')
    header='#pragma once\n#include "z64.h"\n#include "legacy-save/reader.h"\nnamespace Shipyard { namespace LegacySave {\n'+structs+'\n'+'\n'.join(assertions)+'''
void Decode(const Bytes& bytes, unsigned index, Order order, SaveContext_v0& output);
void CopyV0Save(SaveContext_v0& source, ::SaveContext& destination);
}}
'''
    stable(OUT/'generated/legacy-save/format.h',header)
    decode='void Decode(const Bytes& bytes,unsigned index,Order order,SaveContext_v0& output) {\nif(index>=3) throw std::out_of_range("Legacy slot");\nconst size_t base=Slot(index); bytes.Require(base,0x1428);\nmemset(&output,0,sizeof(output));\n'
    fields=[]
    for target,offset,kind in scalar_fields(model,'SaveContext_v0'):
        if offset>=0x1354:continue
        decode+='bytes.Scalar(base+'+hex(offset)+',output.'+target+',order);\n';fields.append(dict(field=target,offset=offset,type=kind))
    decode+='}\n'
    copy=source[source.index('void CopyV0Save'):source.index('void SaveManager::ConvertFromUnversioned')]
    songfix=''
    for old,count,base in [('scarecrowCustomSong',108,0xf41),('scarecrowSpawnSong',16,0x12c6)]:
        songfix+='for(size_t i=0;i<'+str(count)+';++i) { unsigned short duration; bytes.Scalar(base+'+hex(base)+'+i*8+2,duration,order); memcpy(&output.'+old+'[i*8+2],&duration,2); }\n'
    decode=decode[:-2]+songfix+'}\n'
    stable(OUT/'generated/LegacyDecode.cpp','#include "legacy-save/format.h"\n#include "macros.h"\nnamespace Shipyard { namespace LegacySave {\n'+decode+copy+'}}\n')
    method=methods(source)['ConvertFromUnversioned']
    settings=method[method.index('    gSaveContext.audioSetting'):method.index('    for (int fileNum')]
    body='''void SaveManager::ConvertFromUnversioned() {
    using namespace Shipyard::LegacySave;
    const std::vector<unsigned char> data=Read(Shipyard::LegacySave::Path().string());
    const Bytes bytes(&data[0],data.size());
    const Order order=Validate(bytes); // Complete validation before any writes.
    if (SECTION_ID_BASE >= sectionIndex) throw std::runtime_error("Base save section is not registered");
    struct RestoreContext {
        SaveContext saved;
        RestoreContext() : saved(gSaveContext) {}
        ~RestoreContext() { gSaveContext=saved; }
    };
'''+settings+'''
    for (int fileNum=0;fileNum<3;++fileNum) if (Occupied(bytes,fileNum)) {
        SaveContext_v0 file;
        Decode(bytes,fileNum,order,file);
        RestoreContext restore;
        InitFile(false);
        Shipyard::LegacySave::CopyV0Save(file,gSaveContext);
        SaveSection(fileNum,SECTION_ID_BASE,false);
        InitMeta(fileNum);
    }
    Shipyard::Storage::Commit(); // Return only after durable modern output.
}
'''
    # Do not form a pointer to an absent element on an empty/truncated input.
    body=body.replace('Bytes bytes(&data[0],data.size())','Bytes bytes(data.empty()?NULL:&data[0],data.size())')
    prefix='''#include "resources/runtime_support.h"
#include "soh/SaveManager.h"
#include "legacy-save/format.h"
#include "legacy-save/storage_path.h"
#include "cvar_prefixes.h"
#include <libultraship/bridge.h>
extern "C" SaveContext gSaveContext;
'''
    stable(OUT/'generated/LegacyConversion.cpp',prefix+body)
    stable(OUT/'manifest.json',json.dumps(dict(sources=lock,layout=model,decoded_fields=fields,
        source_fragments={'LegacyConversion.cpp':dict(original=SOURCE,methods=['ConvertFromUnversioned']),
                          'LegacyDecode.cpp':dict(original=SOURCE,helpers=['CopyV0Save'],generated_decoder=True)},
        generated={p.relative_to(OUT/'generated').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'generated').rglob('*')) if p.is_file()},
        owned={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OWN.iterdir() if p.suffix in ('.h','.cpp')},
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    flags=json.loads((ROOT/'scratch/ship-utils-xdk/xdk/build.json').read_text())[0]['command'][:-3]
    flags[1:1]=['/I'+str(OUT/'generated')]+['/I'+str(p) for p in includes()]
    rows=[]
    for source in [OUT/'generated/LegacyDecode.cpp',OUT/'generated/LegacyConversion.cpp']:
        obj=folder/(source.stem+'.obj');command=flags+['/TP',str(source),'/Fo'+str(obj)]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(obj.with_suffix('.log'),run.stdout+run.stderr)
        row=dict(source=source.relative_to(ROOT).as_posix(),command=command,exit=run.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        row['source_fragment']=dict(original=SOURCE,methods=['ConvertFromUnversioned'] if source.stem=='LegacyConversion' else [],helpers=['CopyV0Save'] if source.stem=='LegacyDecode' else [])
        if run.returncode:print(run.stdout+run.stderr)
        else:assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2;row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
        rows.append(row);print(source.name,run.returncode,flush=True)
    stable(folder/'build.json',json.dumps(rows,indent=2)+'\n')
    if any(row['exit'] for row in rows):raise SystemExit(1)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args();build() if args.build else prepare()
