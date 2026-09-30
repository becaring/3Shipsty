"""Project the complete pinned SoH frame recorder/interpolator for XDK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_binary import strong_enum
from cpp_ast import PARSER,walk

OWN=ROOT/'platform/shipyard/interpolation'
OUT=ROOT/'scratch/interpolation-xdk'

def recording_ownership(text):
    # XDK does not synthesize aggregate moves. Keep copies available, but move
    # recording containers rather than recursively copying populated subtrees.
    text='#include "interpolation/recording_memory.h"\n'+text
    text=once(text,'struct Path {','struct RecordingInPlace {};\nstruct Path {')
    text=once(text,'''    map<label, vector<Path>> children;
    map<Op, vector<Data>> ops;
    vector<pair<Op, size_t>> items;''','''    typedef vector<Path, Shipyard::Interpolation::RecordingAllocator<Path>> Paths;
    typedef vector<Data, Shipyard::Interpolation::RecordingAllocator<Data>> Operations;
    typedef pair<Op, size_t> Item;
    map<label, Paths, less<label>, Shipyard::Interpolation::RecordingAllocator<pair<const label, Paths>>> children;
    map<Op, Operations, less<Op>, Shipyard::Interpolation::RecordingAllocator<pair<const Op, Operations>>> ops;
    vector<Item, Shipyard::Interpolation::RecordingAllocator<Item>> items;
    Path() {}
    explicit Path(RecordingInPlace) {}
    Path(const Path& other) : children(other.children), ops(other.ops), items(other.items) {}
    void swap(Path& other) { children.swap(other.children); ops.swap(other.ops); items.swap(other.items); }
    Path& operator=(const Path& other) {
        if (this != &other) { Path copy(other); swap(copy); }
        return *this;
    }
    Path(Path&& other) { swap(other); }
    Path& operator=(Path&& other) {
        if (this != &other) {
            swap(other);
            other.children.clear(); other.ops.clear(); other.items.clear();
        }
        return *this;
    }''')
    text=once(text,'    previous_recording = std::move(current_recording);\n    current_recording = {};',
        '    previous_recording.root_path.swap(current_recording.root_path);\n'
        '    current_recording.root_path.children.clear();\n'
        '    current_recording.root_path.ops.clear();\n'
        '    current_recording.root_path.items.clear();')
    text=once(text,'current_path.push_back(&m.emplace_back());',
        'm.emplace_back(RecordingInPlace());\n    current_path.push_back(&m.back());')
    return text

def recording_op_index(text):
    # Map nodes remain stable. Cache their operation-vector addresses within
    # each Path and rebind after every ownership transfer or copy.
    text=once(text,'    Path() {}\n    explicit Path(RecordingInPlace) {}', '''    Operations* opIndex[Op::SkinMatrixMtxFToMtx + 1];
    void ClearIndex() { memset(opIndex, 0, sizeof(opIndex)); }
    void RebindIndex() {
        ClearIndex();
        for (auto it = ops.begin(); it != ops.end(); ++it)
            opIndex[static_cast<unsigned>(it->first.GetValue())] = &it->second;
    }
    Operations& AppendOperations(Op op) {
        Operations*& found = opIndex[static_cast<unsigned>(op.GetValue())];
        if (!found) found = &ops[op];
        return *found;
    }
    Path() { ClearIndex(); }
    explicit Path(RecordingInPlace) { ClearIndex(); }''')
    text=once(text,'items(other.items) {}','items(other.items) { RebindIndex(); }')
    text=once(text,'void swap(Path& other) { children.swap(other.children); ops.swap(other.ops); items.swap(other.items); }',
        'void swap(Path& other) { children.swap(other.children); ops.swap(other.ops); items.swap(other.items); RebindIndex(); other.RebindIndex(); }')
    text=once(text,'            other.children.clear(); other.ops.clear(); other.items.clear();',
        '            other.children.clear(); other.ops.clear(); other.items.clear(); other.ClearIndex();')
    text=once(text,'    current_recording.root_path.items.clear();',
        '    current_recording.root_path.items.clear();\n    current_recording.root_path.ClearIndex();')
    text=once(text,'auto& m = current_path.back()->ops[op];',
        'auto& m = current_path.back()->AppendOperations(op);')
    return text

def replay_op_index(text):
    # Every item is appended after its operation vector exists. RebindIndex
    # restores these addresses whenever ownership of a Path changes.
    start=text.index('    void interpolate_branch(')
    end=text.index('\n};',start)
    body=text[start:end]
    body=once(body,'            Data& new_op = new_path->ops[item.first][item.second];',
              '            const unsigned op_index = static_cast<unsigned>(item.first.GetValue());\n'
              '            Data& new_op = (*new_path->opIndex[op_index])[item.second];')
    body=once(body,'''            if (auto it = old_path->ops.find(item.first); it != old_path->ops.end()) {
                if (item.second < it->second.size()) {
                    Data& old_op = it->second[item.second];''',
              '''            Path::Operations* old_operations = old_path->opIndex[op_index];
            if (old_operations && item.second < old_operations->size()) {
                    Data& old_op = (*old_operations)[item.second];''')
    body=once(body,'''                    }
                }
            }
        }
    }''','''                    }
            }
        }
    }''')
    return text[:start]+body+text[end:]


def reuse_child_lookup(text):
    expression='&new_path->children.find(new_op.open_child.key)->second[new_op.open_child.idx]'
    start=text.index('    void interpolate_branch(')
    end=text.index('            if (auto it = old_path->ops.find',start)
    body=text[start:end]
    if body.count(expression)!=3:
        raise ValueError('Interpolation child lookup inventory drift')
    body=body.replace(expression,'new_child')
    anchor='            if (item.first == Op::OpenChild) {'
    body=once(body,anchor,anchor+'\n                Path* new_child = '+expression+';')
    return text[:start]+body+text[end:]

def transform(text):
    text=reuse_child_lookup(text)
    text=recording_ownership(text)
    text=once(text,'void FrameInterpolation_StartRecord(void) {',
        'void FrameInterpolation_StartRecord(void) {\n#ifdef _XBOX\n'
        '    ModernFrameProfile::PhaseScope recordingRotate(ModernFrameProfile::RecordingRotate);\n#endif')
    # The context dies on return; transfer its replacement nodes to the caller.
    text=once(text,'return ctx.mtx_replacements;','return std::move(ctx.mtx_replacements);')
    text=once(text,'#include <libultraship/bridge.h>','// No LUS bridge symbols are used by this translation unit.')
    text=once(text,'#include "soh/OTRGlobals.h"','extern "C" uint32_t Ship_GetInterpolationFPS();')
    text=once(text,'OTRGlobals::Instance->GetInterpolationFPS()','Ship_GetInterpolationFPS()')
    match=re.search(r'enum class Op \{(.*?)\n\};',text,re.S)
    text=once(text,match[0],strong_enum('Op',match[1]))
    text=recording_op_index(text)
    text=replay_op_index(text)
    text=once(text,'switch (item.first)','switch (item.first.GetValue())')
    from platform_base import resolve
    resolve(ROOT)
    from xbox360_platform.interpolation_pairing import project as prepare_pairing
    text=prepare_pairing(text, value_expression='{value}.GetValue()')
    text=once(text,'typedef pair<const void*, int> label;',
              'struct label { const void* first; int second;\n'
              'bool operator<(const label& rhs) const { return first < rhs.first || (!(rhs.first < first) && second < rhs.second); }\n};')
    text=once(text,'return m.emplace_back();','m.push_back(Data());\n    return m.back();')
    text=once(text,'current_path.back()->items.emplace_back(op, m.size());','current_path.back()->items.push_back(std::make_pair(op, m.size()));')
    # Give anonymous recording payloads names without changing their layout.
    start=text.index('union Data {')
    end=text.index('\nstruct Path {',start)
    data=text[start:end]
    parts={}
    declarations=[]
    def named(match):
        part='RecordPart'+str(len(parts))
        body=match[1]
        names=match[2].strip()
        fields=[]
        for line in re.sub(r'//[^\n]*','',body).split(';'):
            line=line.strip()
            if not line:
                continue
            found=re.fullmatch(r'([\w:*]+)\s+([\w, ]+)',line)
            if not found:
                raise ValueError('Recording field drift: '+line)
            fields += [(found[1],n.strip()) for n in found[2].split(',')]
        declarations.append('struct '+part+' {'+body+'};\n')
        for name in names.split(','):
            parts[name.strip()]=(part,fields)
        return '    '+part+' '+names+';'
    data,n=re.subn(r'    struct \{(.*?)\}\s*([\w, ]+);',named,data,flags=re.S)
    if n!=12:raise ValueError('Recording payload inventory changed: '+str(n))
    text=text[:start]+''.join(declarations)+data+text[end:]
    source=text.encode()
    edits=[]
    factories={}
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='assignment_expression':
            continue
        left=node.child_by_field_name('left')
        right=node.child_by_field_name('right')
        if right.type!='initializer_list' or left.type!='field_expression':
            continue
        field=left.child_by_field_name('field').text.decode()
        if field not in parts:
            raise ValueError('Unknown recording payload '+field)
        part,fields=parts[field]
        values=[c.text.decode() for c in right.named_children]
        factory='Make'+part
        params=', '.join(t+' const& '+n for t,n in fields[:len(values)])
        factories[factory]='static '+part+' '+factory+'('+params+') { '+part+' result = { '+', '.join(n for t,n in fields[:len(values)])+' }; return result; }\n'
        edits.append((right.start_byte,right.end_byte,(factory+'('+', '.join(values)+')').encode()))
    if len(edits)!=13:raise ValueError('Recording initializer inventory changed: '+str(len(edits)))
    for a,b,v in sorted(edits,reverse=True):
        source=source[:a]+v+source[b:]
    text=source.decode()
    text=once(text,'struct Path {',''.join(factories.values())+
        '\n#if defined(_XBOX)\ntypedef char RecordPayloadSizeIs72[(sizeof(Data)==72)?1:-1];\n'
        'typedef char RecordLabelSizeIs8[(sizeof(label)==8)?1:-1];\n#endif\nstruct Path {')
    # C++17 condition initializers retain their complete lexical lifetime.
    source=text.encode()
    edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='if_statement':
            continue
        condition=node.child_by_field_name('condition')
        initializer=next((n for n in condition.named_children if n.type=='init_statement'),None)
        if initializer:
            edits += [(node.start_byte,node.start_byte,b'{ '+initializer.text+b' '),
                      (initializer.start_byte,initializer.end_byte,b''),(node.end_byte,node.end_byte,b' }')]
    for a,b,v in sorted(edits,reverse=True):
        source=source[:a]+v+source[b:]
    text=source.decode()
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    return '#ifdef _XBOX\n#include "application/frame_profile.h"\n#endif\n#include "resources/runtime_support.h"\n#include "binary/compat.h"\n'+lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()

def prepare():
    lock=json.loads((OWN/'sources.lock.json').read_text())
    pending={}
    for name,expected in lock['sources'].items():
        text=(ROOT/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Interpolation source drift '+name)
        if name=='soh/soh/OTRGlobals.cpp':
            match=re.search(r'extern "C" uint32_t Ship_GetInterpolationFPS\(\) \{\s*return OTRGlobals::Instance->GetInterpolationFPS\(\);\s*\}',text)
            if not match:raise ValueError('Existing interpolation bridge is no longer identical')
            continue
        pending[name]=transform(text) if name.endswith('.cpp') else text
    for name,text in pending.items():
        stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps({n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},indent=2)+'\n')

def includes():
    from prepare_fast_resources import includes as fast_includes
    return [OUT/'generated/soh',ROOT/'scratch/game-xdk/full/source/soh',ROOT/'scratch/game-xdk/full/source/soh/include']+fast_includes()

def build():
    prepare()
    folder=OUT/'xdk'
    folder.mkdir(parents=True,exist_ok=True)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    source=OUT/'generated/soh/soh/frame_interpolation.cpp'
    obj=folder/'frame_interpolation.obj'
    command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TP','/EHsc','/GR','/MT','/fp:precise','/D_XBOX','/D_XBOX_VER=200','/DF3DEX_GBI_2','/DNOMINMAX',
             '/DCONTROLLERBUTTONS_T=uint32_t','/FI'+str(ROOT/'platform/shipyard/game/include/xdk_math_boundary.h'),'/I'+str(sdk/'include/xbox')]
    command+=['/I'+str(p) for p in includes()]+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    stable(folder/'build.log',result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps([dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command)],indent=2)+'\n')
    if result.returncode:
        print('\n'.join(l for l in result.stdout.splitlines() if 'error ' in l)[:5000])
        raise SystemExit(1)
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    print('Full current frame_interpolation.cpp: native PowerPC object')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true')
    args=parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
