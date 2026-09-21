"""Independent historical raw-writer fixtures against the actual modern CopyV0Save."""
import hashlib,json,re,runpy,struct,subprocess
from pathlib import Path
from prepare_legacy_save import ROOT,OWN,OUT,PRODUCER,prepare,git_source,declarations,layout,scalar_fields,SCALARS,includes
from prepare_archives import stable
from cpp_ast import PARSER,walk
def definition(text,name):
    items=[n.text.decode() for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='function_definition' and n.child_by_field_name('declarator') is not None and re.search(rb'\b'+name.encode()+rb'\(',n.child_by_field_name('declarator').text)]
    assert len(items)==1,(name,len(items));return items[0]
def producer():
    source=git_source('soh/src/code/z_sram.c')
    original={}
    for path in ['soh/include/z64math.h','soh/include/z64save.h','soh/include/z64audio.h']:
        original.update(declarations(git_source(path)))
    original.update(declarations(source))
    selected={}
    def collect(name):
        if name in SCALARS or name in selected:return
        body=original[name]
        clean=re.sub(r'/\*.*?\*/|//[^\n]*','',body,flags=re.S)
        for kind,_ in re.findall(r'(\w+)\s+([^;]+);',clean):collect(kind)
        selected[name]=body
    for name in ['SaveContext','Save','OcarinaNote']:collect(name)
    model=layout(selected)
    output='namespace Producer {\n'+'\n'.join('typedef struct {\n'+body+'\n} '+name+';' for name,body in selected.items())
    output+='''
static_assert(sizeof(SaveContext)==0x1428,"historical context");
static_assert(sizeof(Inventory)==0x60,"historical inventory padding");
static_assert(sizeof(Save)==0x1354,"historical checksum range");
static_assert(sizeof(OcarinaNote)==8 && offsetof(OcarinaNote,unk_02)==2,"historical song record");
struct SramContext;
struct Backing { SaveContext context; unsigned char extra[0x28]; } backing;
unsigned char capture[0x8000];
#define gSaveContext backing.context
#define SLOT_SIZE (sizeof(SaveContext)+0x28)
#define CHECKSUM_SIZE (sizeof(Save)/2)
#define OS_WRITE 1
#undef OS_K1_TO_PHYSICAL
#define OS_K1_TO_PHYSICAL(address) 0 // exact historical producer convert.h contract
u16 gSramSlotOffsets[]={0x20,0x1470,0x28C0,0x3D10,0x5160,0x65B0};
void SsSram_ReadWrite(uintptr_t address,void* bytes,size_t count,s32 direction) {
    assert(direction==OS_WRITE && address+count<=sizeof(capture));
    memcpy(capture+address,bytes,count);
}
'''+definition(source,'Sram_WriteSave')+'\n'
    def emit(name,prefix,mode,depth=0):
        lines=[]
        for f in model[name]['fields']:
            if mode=='fill' and name=='SaveContext' and f['offset']>=0x1354:continue
            index='i'+str(depth)
            target=prefix+f['name']+('['+index+']' if f['array'] else '')
            if f['kind'] in SCALARS:
                if mode=='fill':body=target+'=static_cast<'+f['kind']+'>((round*2654435761u) ^ (slot*7919u) ^ (sequence++*7919u+0xa55af00du));'
                elif f['kind'] not in ('char','u8','s8') and f['name']!='fileNum':body='Reverse('+target+');'
                else:body=''
            else:body=emit(f['kind'],target+'.',mode,depth+1)
            if body:
                if f['array']:body='for(unsigned '+index+'=0;'+index+'<'+str(f['count'])+';++'+index+') { '+body+' }'
                lines.append(body)
        return '\n'.join(lines)
    output+='void Fill(unsigned round,unsigned slot) { memset(&backing,0,sizeof(backing)); unsigned sequence=0;\n'+emit('SaveContext','gSaveContext.','fill')+'\n'
    output+='''memcpy(gSaveContext.newf,"ZELDAZ",6);
gSaveContext.healthCapacity=0x30+((round+slot)%18)*0x10;
gSaveContext.linkAge=(round+slot)&1;
gSaveContext.fileNum=slot;
}
template<class T> void Reverse(T& value) {
    unsigned char bytes[sizeof(T)]; memcpy(bytes,&value,sizeof(T));
    for(size_t i=0;i<sizeof(T)/2;++i) { unsigned char t=bytes[i]; bytes[i]=bytes[sizeof(T)-1-i]; bytes[sizeof(T)-1-i]=t; }
    memcpy(&value,bytes,sizeof(T));
}
void ReverseFields() {
'''
    output+=emit('SaveContext','gSaveContext.','reverse')+'\n'
    for name,count in [('scarecrowCustomSong',108),('scarecrowSpawnSong',16)]:
        output+='for(unsigned i=0;i<'+str(count)+';++i) { u16 n; memcpy(&n,&gSaveContext.'+name+'[i*8+2],2); Reverse(n); memcpy(&gSaveContext.'+name+'[i*8+2],&n,2); }\n'
    output+='''}
void WriteBig(unsigned slot) {
    ReverseFields(); Sram_WriteSave(NULL);
    for(unsigned copy=0;copy<2;++copy) {
        unsigned base=gSramSlotOffsets[slot+copy*3],sum=0;
        // Independent byte arithmetic over the producer's actual output;
        // the native producer checksum's word order is corrected to BE.
        for(unsigned i=0;i<0x1352;i+=2) sum+=(unsigned(capture[base+i])<<8)|capture[base+i+1];
        capture[base+0x1352]=static_cast<unsigned char>(sum>>8);
        capture[base+0x1353]=static_cast<unsigned char>(sum);
        capture[base+0x1354]=0;capture[base+0x1355]=0;capture[base+0x1356]=0;capture[base+0x1357]=static_cast<unsigned char>(slot);
    }
}
#undef gSaveContext
#undef SLOT_SIZE
#undef CHECKSUM_SIZE
#undef OS_WRITE
#undef OS_K1_TO_PHYSICAL
}
'''
    return output,model
def native_references():
    obj=OUT/'xdk/LegacyConversion.obj'
    if not obj.exists():return []
    data=obj.read_bytes();offset,count=struct.unpack_from('<II',data,8);strings=offset+18*count
    found=[];i=0
    while i<count:
        row=data[offset+i*18:offset+(i+1)*18]
        if row[:4]==b'\0'*4:
            start=strings+struct.unpack_from('<I',row,4)[0];name=data[start:data.index(b'\0',start)].decode()
        else:name=row[:8].split(b'\0')[0].decode()
        if struct.unpack_from('<h',row,12)[0]==0 and row[16]==2 and any(v in name for v in ['SaveSection','InitMeta','SaveGlobal','InitFile','Commit@Storage','CopyV0Save','Decode@Legacy']):found.append(name)
        i+=1+row[17]
    assert len(found)==7,found
    return found
def main():
    prepare();folder=OUT/'host';folder.mkdir(parents=True,exist_ok=True)
    actual=(ROOT/'soh/soh/SaveManager.cpp').read_text(encoding='utf8')
    oldcopy=definition(actual,'CopyV0Save').replace('void CopyV0Save(','void OriginalCopy(').replace('SaveContext_v0&','Shipyard::LegacySave::SaveContext_v0&')
    historical,model=producer()
    # Compiler-generated producer offsets independently check the decoder's
    # generated format. There is no #pragma pack and no shared encoder schema.
    asserts=[]
    for f in model['SaveContext']['fields']:
        if f['offset']<0x1354:
            asserts.append('static_assert(offsetof(Producer::SaveContext,'+f['name']+')==offsetof(Shipyard::LegacySave::SaveContext_v0,'+f['name']+'),"producer offset '+f['name']+'");')
    contract='#include <cassert>\n#include <cstring>\n#include <iostream>\n#include <fstream>\n#include "legacy-save/format.h"\n#include "macros.h"\n'+historical+'\n'+oldcopy+'\n'+'\n'.join(asserts)+'\n'+(OWN/'contract.cpp').read_text()
    stable(folder/'contract.cpp',contract)
    compiler,env=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/GR','/MD','/O2','/Gy','/DNOMINMAX','/DF3DEX_GBI_2','/DCONTROLLERBUTTONS_T=uint32_t']
    command+=['/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h')]
    command+=['/I'+str(p) for p in [OUT/'generated']+includes()]
    command+=list(map(str,[folder/'contract.cpp',OUT/'generated/LegacyDecode.cpp']))+['/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'contract.exe'),'/link','/OPT:REF']
    run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True);stable(folder/'build.log',run.stdout+run.stderr)
    assert not run.returncode,folder/'build.log'
    run=subprocess.run([str(folder/'contract.exe'),str(folder/'producer.sav')],cwd=ROOT,capture_output=True,text=True)
    stable(folder/'output.txt',run.stdout+run.stderr);assert not run.returncode,folder/'output.txt'
    # The whole production method also receives a host compile, with its real
    # unresolved SaveManager/storage references. No fake providers are linked.
    method=folder/'LegacyConversion.obj'
    compile_command=command[:command.index(str(folder/'contract.cpp'))]+['/c',str(OUT/'generated/LegacyConversion.cpp'),'/Fo:'+str(method)]
    compile_run=subprocess.run(compile_command,cwd=ROOT,env=env,capture_output=True,text=True)
    stable(folder/'method-build.log',compile_run.stdout+compile_run.stderr);assert not compile_run.returncode,folder/'method-build.log'
    receipt=dict(command=command,exit=run.returncode,stdout=run.stdout,fixture_producer_commit=PRODUCER,
        fixture_sha256=hashlib.sha256((folder/'producer.sav').read_bytes()).hexdigest(),
        full_method_host_compile=compile_command,full_method_runtime=False,native_execution=False,
        native_actual_service_references=native_references(),test_generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        producer_layout=model,contract_sha256=hashlib.sha256((folder/'contract.cpp').read_bytes()).hexdigest())
    stable(OUT/'verification.json',json.dumps(receipt,indent=2)+'\n');print(run.stdout)
if __name__=='__main__':main()
