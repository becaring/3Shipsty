"""Hash-locked current LUS resource leaf projection. Never writes upstream.

The independently owned two-alternative variant is deliberately narrower than
std::variant. Archive/Loader/Manager are not projected by this bounded increment.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'platform/shipyard/resources'
COMMIT = 'fdcaf6336776d24a6408d016b0a52243f108f250'


def normalize(data):
    return data.decode('utf-8-sig').replace('\r\n','\n')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def transform(relative, original):
    lines=original.splitlines(keepends=True)
    guard='SHIPYARD_RESOURCE_'+relative.upper().replace('/','_').replace('.','_')
    mapped='libultraship/'+relative
    output=['// Generated from hash-locked current LUS; do not edit.\n']
    if relative.endswith('.h'): output += ['#ifndef '+guard+'\n#define '+guard+'\n']
    output += ['#line 1 "'+mapped+'"\n']
    spans=[]
    for number,line in enumerate(lines,1):
        replacement=line.replace('#include <variant>','#include "resources/variant.h"')
        replacement=replacement.replace('std::variant<','Shipyard::Resources::variant<')
        replacement=replacement.replace('std::get<','Shipyard::Resources::get<')
        replacement=replacement.replace('std::holds_alternative<','Shipyard::Resources::holds_alternative<')
        replacement=replacement.replace(' final :',' :').replace(' override','')
        if relative.endswith('/ResourceType.h'):
            if line=='#pragma once\n': replacement+='#include "binary/compat.h"\n'
            if line=='enum class ResourceType {\n':
                replacement='struct ResourceType : public Shipyard::Binary::ScopedEnum<ResourceType> {\n    enum Value {\n'
            if line=='};\n':
                replacement=('    };\n    ResourceType() {}\n'
                    '    ResourceType(Value v) : Shipyard::Binary::ScopedEnum<ResourceType>(v) {}\n'
                    '    explicit ResourceType(int v) : Shipyard::Binary::ScopedEnum<ResourceType>(v) {}\n};\n')
        if relative.endswith('/File.h'):
            if line=='struct ResourceInitData {\n':
                replacement += ('    ResourceInitData() : Parent(), Path(), ByteOrder(Endianness::Native), Type(0), '
                                'ResourceVersion(0), Id(0), IsCustom(false), Format(RESOURCE_FORMAT_BINARY) {}\n')
            replacement=replacement.replace('    bool IsLoaded = false;','    File() : IsLoaded(false) {}\n    bool IsLoaded;')
        if relative.endswith('/Resource.h'):
            replacement=replacement.replace('inline static const std::string gAltAssetPrefix = "alt/";',
                                            'static const std::string gAltAssetPrefix;')
            replacement=replacement.replace('bool mIsDirty = false;','bool mIsDirty;')
            replacement=replacement.replace('using IResource::IResource;',
                'Resource(std::shared_ptr<ResourceInitData> initData) : IResource(initData) {}')
        if relative.endswith('/Resource.cpp'):
            replacement=replacement.replace('namespace Ship {','namespace Ship {\nconst std::string IResource::gAltAssetPrefix = "alt/";')
            replacement=replacement.replace(': mInitData(initData)',': mInitData(initData), mIsDirty(false)')
        if '/type/' in relative and relative.endswith('.h'):
            name=Path(relative).stem
            replacement=replacement.replace('using Resource::Resource;',
                name+'(std::shared_ptr<ResourceInitData> initData) : Resource<void>(initData) {}')
        if replacement!=line:
            spans.append({'source_line':number,'original':line,'replacement':replacement})
            output+=[replacement,'#line '+str(number+1)+' "'+mapped+'"\n']
        else: output.append(line)
    if relative.endswith('.h'): output+=['\n#endif // '+guard+'\n']
    return ''.join(output),spans


def generate(source_root=None, output=None, helper_root=None):
    source_root=Path(source_root or ROOT/'libultraship')
    helper_root=Path(helper_root or BASE)
    output=Path(output or ROOT/'scratch/resources-xdk/generated').resolve()
    scratch=(ROOT/'scratch').resolve()
    if not output.is_relative_to(scratch): raise ValueError('Generated output must remain beneath owned scratch')
    lock=json.loads((BASE/'sources.lock.json').read_text(encoding='utf-8'))
    if lock['lus_commit']!=COMMIT: raise ValueError('Unexpected LUS source pin')
    staged={};manifest={'lus_commit':COMMIT,'normalization':'UTF-8 BOM removed; CRLF to LF','files':{},'helpers':{}}
    # Verify every input before creating output or writing any generated file.
    for relative,expected in lock['sources'].items():
        original=normalize((source_root/relative).read_bytes())
        if digest(original)!=expected: raise ValueError('Source hash mismatch: '+relative)
        generated,spans=transform(relative,original)
        staged[relative]=generated
        manifest['files'][relative]={'source_sha256':expected,'generated_sha256':digest(generated),'edits':spans}
    for relative,expected in lock['helpers'].items():
        if digest(normalize((helper_root/relative).read_bytes()))!=expected:
            raise ValueError('Helper hash mismatch: '+relative)
        manifest['helpers'][relative]=expected
    for relative,text in staged.items():
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(text.encode('utf-8'))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=generate(output=args.output)
    print('Projected '+str(len(result['files']))+' hash-locked current resource files.')
