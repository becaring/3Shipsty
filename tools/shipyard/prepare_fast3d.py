"""Bring the complete pinned Fast3D interpreter through the native compiler."""
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
from prepare_graphics import feature_header,lower_api
from cpp_ast import PARSER,walk

OUT=ROOT/'scratch/fast3d-xdk'
OWN=ROOT/'platform/shipyard/fast3d'


def member_defaults(text,classname):
    """Move exact member defaults to constructor initializers, preserving order.

    Generic AST technique inspected in Smash360 prepare_fast3d_xdk.py; this
    implementation rejects nonempty array defaults rather than guessing them.
    """
    source=text.encode();edits=[];initializers=[];body=[]
    matches=[n for n in walk(PARSER.parse(source).root_node) if n.type in ('class_specifier','struct_specifier')
             and n.child_by_field_name('name') and n.child_by_field_name('name').text.decode()==classname]
    if len(matches)!=1:raise ValueError('Expected single class '+classname)
    for member in matches[0].child_by_field_name('body').named_children:
        if member.type!='field_declaration':continue
        if any(n.type=='storage_class_specifier' and n.text==b'static' for n in member.named_children):continue
        declarators=member.children_by_field_name('declarator')
        for value in member.children_by_field_name('default_value'):
            decl=next((d for d in reversed(declarators) if d.end_byte<=value.start_byte),None)
            if not decl or decl.type=='function_declarator':raise ValueError('Unsupported member default '+member.text.decode())
            names=[n for n in walk(decl) if n.type=='field_identifier']
            if len(names)!=1:raise ValueError('Ambiguous member name')
            name=names[0].text.decode();literal=value.text.decode()
            if decl.type=='array_declarator':
                if literal!='{}':raise ValueError('Nonempty member array needs explicit projection')
                body.append('    std::fill('+name+', '+name+' + sizeof('+name+')/sizeof('+name+'[0]), 0);')
            else:
                if value.type=='initializer_list':literal=literal[1:-1].strip()
                initializers.append(name+'('+literal+')')
            edits.append((decl.end_byte,value.end_byte))
    for start,end in sorted(edits,reverse=True):source=source[:start]+source[end:]
    return source.decode(),initializers,body


def header(text):
    # Share the real current shader constants/features with the decoder/backend.
    start=text.index('enum {\n    SHADER_0,');end=text.index('\nunion Gfx;',start)
    key_start=text.index('struct ColorCombinerKey {',start);key_end=text.index('#define SHADER_MAX_TEXTURES',key_start)
    key=text[key_start:key_end]
    text=text[:start]+'#include "fast/cc_features.h"\n'+key+text[end:]
    text=once(text,'#include <compare>','// Explicit lexicographic comparison preserves the two current fields.')
    text=once(text,'auto operator<=>(const ColorCombinerKey&) const = default;',
              'bool operator==(const ColorCombinerKey& rhs) const { return combine_mode==rhs.combine_mode && options==rhs.options; }\n'
              '    bool operator<(const ColorCombinerKey& rhs) const { return combine_mode!=rhs.combine_mode ? combine_mode<rhs.combine_mode : options<rhs.options; }')
    text=once(text,'bool operator==(const TextureCacheKey&) const noexcept = default;',
              'bool operator==(const TextureCacheKey& rhs) const throw() {\n'
              '        return texture_addr==rhs.texture_addr && palette_addrs[0]==rhs.palette_addrs[0] && palette_addrs[1]==rhs.palette_addrs[1]\n'
              '            && fmt==rhs.fmt && siz==rhs.siz && palette_index==rhs.palette_index && size_bytes==rhs.size_bytes;\n    }')
    text,defaults,arrays=member_defaults(text,'GfxExecStack')
    if len(defaults)!=3 or arrays:raise ValueError('GfxExecStack defaults changed')
    # All three defaults are empty standard containers, including disp_stack.
    text=once(text,'float h_byte_scale = 1, v_pixel_scale = 1;',
              'float h_byte_scale, v_pixel_scale;\n    RawTexMetadata() : width(0), height(0), h_byte_scale(1), v_pixel_scale(1), type(TextureType::Error) {}')
    text=once(text,'bool enabled = false;','bool enabled;\n    ShaderMod(bool enabledValue=false, int16_t idValue=0, uint8_t typeValue=0) : enabled(enabledValue), id(idValue), type(typeValue) {}')
    text,defaults,arrays=member_defaults(text,'Interpreter')
    text=text.replace('constexpr size_t','const size_t').replace(' noexcept',' throw()').replace('#include <stdbool.h>','')
    text=once(text,'#include "backends/gfx_rendering_api.h"','#include "fast/backends/gfx_rendering_api.h"')
    return text,defaults,arrays


def opcode_tables(text):
    start=text.index('class UcodeHandler {');end=text.index('\n};',start)+3
    cls=text[start:end]
    old='''    inline constexpr UcodeHandler(
        std::initializer_list<std::pair<int8_t, std::pair<const char*, GfxOpcodeHandlerFunc>>> initializer) {
        std::fill(std::begin(mHandlers), std::end(mHandlers),
                  std::pair<const char*, GfxOpcodeHandlerFunc>(nullptr, nullptr));

        for (const auto& [opcode, handler] : initializer) {
            mHandlers[static_cast<uint8_t>(opcode)] = handler;
        }
    }'''
    new='''    UcodeHandler(const UcodeEntry* initializer, size_t count) {
        std::fill(mHandlers, mHandlers + sizeof(mHandlers)/sizeof(mHandlers[0]),
                  std::pair<const char*, GfxOpcodeHandlerFunc>(nullptr, nullptr));
        for (size_t i=0; i<count; ++i) {
            const UcodeEntry& entry=initializer[i];
            mHandlers[static_cast<uint8_t>(entry.opcode)] = std::make_pair(entry.name, entry.handler);
        }
    }'''
    cls=once(cls,old,new)
    cls=once(cls,'std::numeric_limits<uint8_t>::max() + 1','256 /* complete uint8_t opcode domain */')
    text=text[:start]+'struct UcodeEntry { int8_t opcode; const char* name; GfxOpcodeHandlerFunc handler; };\n'+cls+text[end:]
    source=text.encode();edits=[];tables=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='declaration' or not node.text.startswith(b'static constexpr UcodeHandler '):continue
        declarator=node.child_by_field_name('declarator');name=declarator.child_by_field_name('declarator').text.decode()
        values=declarator.child_by_field_name('value');rows=[]
        for entry in values.named_children:
            if entry.type=='comment':continue
            fields=[n for n in entry.named_children if n.type!='comment']
            if len(fields)!=2 or fields[1].type!='initializer_list':raise ValueError('Opcode entry shape drift')
            pair=[n for n in fields[1].named_children if n.type!='comment']
            if len(pair)!=2:raise ValueError('Opcode pair shape drift')
            rows.append('{ '+fields[0].text.decode()+', '+pair[0].text.decode()+', '+pair[1].text.decode()+' }')
        tables.append(dict(name=name,count=len(rows)))
        replacement='static const UcodeEntry '+name+'Entries[] = {\n    '+',\n    '.join(rows)+'\n};\n'
        replacement+='static const UcodeHandler '+name+'('+name+'Entries, sizeof('+name+'Entries)/sizeof('+name+'Entries[0]));'
        edits.append((node.start_byte,node.end_byte,replacement.encode()))
    if len(tables)!=6:raise ValueError('Current opcode table count drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode(),tables


def static_arrays(text):
    source=text.encode();edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='declaration' or not node.text.startswith(b'static constexpr std::array '):continue
        decl=node.child_by_field_name('declarator');name=decl.child_by_field_name('declarator').text.decode()
        values=decl.child_by_field_name('value');count=len([n for n in values.named_children if n.type!='comment'])
        if name=='tbl':typ='const char*'
        elif name=='ucode_attr_handlers':typ='UcodeAttributePointer'
        elif name=='ucode_handlers':typ='const UcodeHandler*'
        else:raise ValueError('Unreviewed deduced static array '+name)
        replacement=('typedef const uint32_t (*UcodeAttributePointer)[7];\n' if name=='ucode_attr_handlers' else '')
        replacement+='static const std::array<'+typ+', '+str(count)+'> '+name+' = { '+values.text.decode()+' };'
        edits.append((node.start_byte,node.end_byte,replacement.encode()))
    if len(edits)!=4:raise ValueError('Static array inventory drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def local_array_initializers(text):
    source=text.encode();edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='init_declarator':continue
        decl=node.child_by_field_name('declarator');value=node.child_by_field_name('value')
        if decl and value and decl.type=='array_declarator' and value.type=='initializer_list':
            gap=source[decl.end_byte:value.start_byte]
            if b'=' not in gap:edits.append((decl.end_byte,value.start_byte,b' = '))
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def if_initializers(text):
    source=text.encode();edits=[]
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='if_statement':continue
        condition=node.child_by_field_name('condition');init=condition.child_by_field_name('initializer')
        if not init:continue
        value=condition.child_by_field_name('value')
        replacement=b'{ '+init.text+b' if ('+value.text+b')'+source[condition.end_byte:node.end_byte]+b' }'
        edits.append((node.start_byte,node.end_byte,replacement))
    if len(edits)!=2:raise ValueError('Current if-initializer inventory drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def aggregate_assignments(text):
    source=text.encode();edits=[]
    types={'key':'TextureCacheKey','default_viewport':'XYWidthHeight',
           'gfx->mRenderingState.viewport':'XYWidthHeight','gfx->mRenderingState.scissor':'XYWidthHeight',
           'mRenderingState.viewport':'XYWidthHeight','mRenderingState.scissor':'XYWidthHeight','mFrameBuffers[fb]':'FBInfo',
           'gfx->mRsp->current_shader':'ShaderMod','gfx->mRdp->current_shader':'ShaderMod'}
    for node in walk(PARSER.parse(source).root_node):
        if node.type!='assignment_expression':continue
        rhs=node.child_by_field_name('right')
        if not rhs or rhs.type!='initializer_list':continue
        lhs=node.child_by_field_name('left').text.decode()
        if lhs not in types or node.parent.type!='expression_statement':raise ValueError('Unreviewed aggregate assignment: '+node.text.decode())
        typ=types[lhs];initializer=rhs.text.decode()
        if typ=='ShaderMod':initializer='ShaderMod('+initializer[1:-1]+')'
        replacement='{ '+typ+' shipyardAggregate = '+initializer+'; '+lhs+' = shipyardAggregate; }'
        edits.append((node.parent.start_byte,node.parent.end_byte,replacement.encode()))
    if len(edits)!=13:raise ValueError('Current aggregate assignment inventory drift')
    for start,end,replacement in sorted(edits,reverse=True):source=source[:start]+replacement+source[end:]
    return source.decode()


def prepare():
    sources={}
    for name,expected in json.loads((OWN/'sources.lock.json').read_text())['sources'].items():
        text=(ROOT/'libultraship'/name).read_text(encoding='utf-8-sig')
        if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Fast3D input drift: '+name)
        sources[name]=text
    pending=dict(sources)
    interp='include/fast/interpreter.h'
    pending[interp],defaults,arrays=header(sources[interp])
    pending['include/fast/cc_features.h']=feature_header(sources[interp])
    for filename,classname in [('gfx_rendering_api.h','GfxRenderingAPI'),('gfx_window_manager_api.h','GfxWindowBackend')]:
        name='include/fast/backends/'+filename;pending[name]=lower_api(sources[name],classname)
    for filename in ('lus_gbi.h','f3dex.h','f3dex2.h'):
        name='include/fast/'+filename
        pending[name]=re.sub(r'\bconstexpr\b','const',sources[name])
    light='include/fast/resource/type/Light.h'
    pending[light]=once(sources[light],'using Resource::Resource;','Light(std::shared_ptr<Ship::ResourceInitData> initData) : Resource<LightEntry>(initData) {}').replace(' final :',' :')
    text=sources['src/fast/interpreter.cpp']
    text=once(text,'#include <any>','#include "fast3d/value_init.h"\n#include "fast3d/math.h"\n#include <array>')
    text=text.replace('#include <stdbool.h>','')
    text=once(text,'Interpreter::Interpreter() {','Interpreter::Interpreter() : '+', '.join(defaults)+' {\n'+'\n'.join(arrays))
    text=once(text,'mRsp = new RSP();','mRsp = Shipyard::Fast3D::NewValueInitializedRSP();')
    text=once(text,'mRdp = new RDP();','mRdp = Shipyard::Fast3D::NewValueInitializedRDP();')
    text,tables=opcode_tables(text)
    text=static_arrays(text)
    text=local_array_initializers(text)
    text=if_initializers(text)
    text=aggregate_assignments(text)
    text,count=re.subn(r'RawTexMetadata (rawTexMetadata|rawTexMetdata) = \{\};',r'RawTexMetadata \1;',text)
    if count!=5:raise ValueError('Raw texture local initialization inventory drift')
    text=text.replace('[[maybe_unused]]','')
    text=once(text,'disp_stack.push_back({ file, line });','CodeDisp entry = { file, line };\n    disp_stack.push_back(entry);')
    if text.count('mGetPixelDepthPending.emplace(x, y);')!=2:raise ValueError('Depth insertion inventory drift')
    text=text.replace('mGetPixelDepthPending.emplace(x, y);','mGetPixelDepthPending.insert(std::make_pair(x, y));')
    # res is a local map destroyed immediately afterwards. Range insert retains
    # existing destination keys, just as merge does; no source nodes escape.
    text=once(text,'mGetPixelDepthCached.merge(res);','mGetPixelDepthCached.insert(res.begin(), res.end());')
    text=once(text,'mMaskedTextures[name] = MaskedTextureEntry{ mask, replacement };',
              'MaskedTextureEntry entry = { mask, replacement };\n    mMaskedTextures[name] = entry;')
    if text.count('= round(')!=2 or text.count('std::clamp(')!=2:raise ValueError('Math compatibility inventory drift')
    text=text.replace('= round(','= Shipyard::Fast3D::Round(').replace('std::clamp(','Shipyard::Fast3D::Clamp(')
    text=once(text,'node->second.lru_location = mTextureCache.lru.insert(mTextureCache.lru.end(), { it });',
              'TextureCacheMapIter location = { it };\n    node->second.lru_location = mTextureCache.lru.insert(mTextureCache.lru.end(), location);')
    text=once(text,'path.starts_with(Ship::IResource::gAltAssetPrefix)', 'Shipyard::Resources::starts_with(path, Ship::IResource::gAltAssetPrefix)')
    text=once(text,'switch (type) {','switch (type.GetValue()) {')
    text=text.replace('[[fallthrough]]','/* fall through */')
    text=once(text,'#include <spdlog/fmt/fmt.h>','#include <spdlog/spdlog.h>')
    lower=runpy.run_path(str(ROOT/'platform/shipyard/imgui/projection.py'))['lower_ranges']
    text=lower(text.encode(),'Shipyard::Resources::begin','Shipyard::Resources::end').decode()
    text=text.replace('constexpr size_t','const size_t')
    text=re.sub(r'using (\w+) = ([^;]+?)\(\*\)(\([^;]*\));',r'typedef \2 (*\1)\3;',text)
    pending['src/fast/interpreter.cpp']=text
    pending['include/stdbool.h']='#pragma once\n#ifndef __cplusplus\n#error Use the application C boolean projection for C sources\n#endif\n'
    for name,text in pending.items():stable(OUT/'generated'/name,text)
    stable(OUT/'manifest.json',json.dumps(dict(outputs={n:hashlib.sha256(t.encode()).hexdigest() for n,t in pending.items()},
           interpreter_initializers=defaults,interpreter_array_initialization=arrays,opcode_tables=tables),indent=2)+'\n')


def build():
    prepare();folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    from prepare_window import includes
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    flags=['/nologo','/c','/TP','/EHsc','/MT','/D_XBOX','/D_XBOX_VER=200','/DNOMINMAX','/DSPDLOG_ACTIVE_LEVEL=0',
           '/Dnssv_CONFIG_SELECT_STRING_VIEW=1','/FI'+str(ROOT/'scratch/configuration-xdk/generated/include/compile_definitions.h'),'/I'+str(sdk/'include/xbox')]
    flags+=['/I'+str(p) for p in [OUT/'generated/include',ROOT/'scratch/gui-resources-xdk/generated/include',ROOT/'scratch/context-xdk/generated/include']+includes()+[ROOT/'scratch/async-xdk/generated']]
    source=OUT/'generated/src/fast/interpreter.cpp';obj=folder/'interpreter.obj'
    command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'interpreter.log',result.stdout+result.stderr)
    stable(folder/'build.json',json.dumps(dict(source=source.relative_to(ROOT).as_posix(),exit=result.returncode,command=command),indent=2)+'\n')
    if result.returncode:
        print('\n'.join(line for line in result.stdout.splitlines() if 'error ' in line)[:4500]);raise SystemExit(result.returncode)
    if struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
    # Check the actual include composition, not a standalone forced endian flag.
    probe=folder/'endian_contract.cpp'
    stable(probe,'#include "fast/interpreter.h"\n#include "ship/utils/binarytools/endianness.h"\n'
           '#if !defined(IS_BIGENDIAN) || !SHIPYARD_BIG_ENDIAN\n#error Xenon framebuffer values already have BE byte order\n#endif\n'
           'typedef char NativeIsBig[(Ship::Endianness::Native==Ship::Endianness::Big)?1:-1];\n')
    command=[str(sdk/'bin/win32/cl.exe')]+flags+[str(probe),'/Fo'+str(folder/'endian_contract.obj')]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'endian_contract.log',result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Actual interpreter endian composition failed; see endian_contract.log')
    print('Complete current Fast3D interpreter compiles for Xenon')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
