"""Actual pinned resource leaf TUs: original/projected contract and XDK evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/resources-xdk'
SPEC = importlib.util.spec_from_file_location('binary_environment', Path(__file__).with_name('test_binary.py'))
ENV = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ENV)
NAMES = ['Resource.cpp', 'ResourceFactoryBinary.cpp', 'ResourceFactoryXML.cpp',
         'type/Blob.cpp', 'type/Json.cpp', 'type/Shader.cpp',
         'factory/BlobFactory.cpp', 'factory/JsonFactory.cpp', 'factory/ShaderFactory.cpp']


def includes(projected):
    if projected:
        return [OUT/'generated/include', ROOT/'scratch/binary-xdk/generated/include',
                ROOT/'platform/shipyard/json/include', ROOT/'scratch/json-xdk/backend-generated',
                ROOT/'scratch/logging-xdk/core-include', ROOT/'scratch/logging-xdk/include',
                ROOT/'scratch/deps/fmt-xdk', ROOT/'platform/shipyard', ROOT]
    return [ROOT/'libultraship/include', ROOT/'platform/shipyard/json/upstream/include',
            ROOT/'scratch/deps/spdlog/include']


def xdk(projected):
    folder=OUT/('xdk-generated' if projected else 'xdk-original');folder.mkdir(parents=True,exist_ok=True)
    source=(OUT/'generated' if projected else ROOT/'libultraship')/'src/ship/resource'
    base=[ENV.XDK/'bin/win32/cl.exe','/nologo','/EHsc','/D_XBOX','/D_XBOX_VER=200',
          '/DSPDLOG_ACTIVE_LEVEL=0','/I'+str(ENV.XDK/'include/xbox')]
    base+=['/I'+str(p) for p in includes(projected)]
    records=[]
    for name in NAMES:
        label=name.replace('/','_').replace('.cpp','');obj=folder/(label+'.obj')
        result=ENV.invoke(base+['/c','/Fo'+str(obj),source/name],folder,label,success=projected)
        records.append(result)
        if projected: assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    if projected:
        obj=folder/'contract.obj'
        records.append(ENV.invoke(base+['/c','/Fo'+str(obj),Path(__file__).with_name('test_resources_contract.cpp')],
                                  folder,'contract'))
        assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    if not projected: assert all(r['returncode'] for r in records)
    return records


def host(projected):
    folder=OUT/('host-generated' if projected else 'host-original');folder.mkdir(parents=True,exist_ok=True)
    compiler,env=ENV.host_environment()
    source=(OUT/'generated' if projected else ROOT/'libultraship')/'src/ship/resource'
    binary=(ROOT/'scratch/binary-xdk/generated' if projected else ROOT/'libultraship')/'src/ship/utils/binarytools'
    command=[compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/DSPDLOG_ACTIVE_LEVEL=0',
             '/Fe:'+str(folder/'contract.exe'),'/Fo:'+str(folder)+'/']
    command+=['/I'+str(p) for p in includes(projected)]
    command+=[Path(__file__).with_name('test_resources_contract.cpp')]
    command+=[source/name for name in NAMES]
    command+=[binary/(name+'.cpp') for name in ('BinaryReader','BinaryWriter','MemoryStream','Stream')]
    if projected:
        # Windows folds Json.cpp and json.cpp to one basename; compile the backend separately.
        backend=folder/'json-backend.obj'
        ENV.invoke([compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/c','/Fo'+str(backend)]+
                   ['/I'+str(p) for p in includes(True)]+[ROOT/'platform/shipyard/json/json.cpp'],folder,'backend',env)
        command += [backend,ROOT/'platform/shipyard/async/native.cpp',
                    ROOT/'platform/shipyard/logging/chrono/chrono.cpp',ROOT/'platform/shipyard/logging/environment.cpp']
    ENV.invoke(command,folder,'compile',env)
    return ENV.invoke([folder/'contract.exe'],folder,'run')['stdout']


def integration_probe():
    """Compile remaining real, unprojected TUs with completed leaf dependencies.

    Failures are handoff evidence, not a resource-manager implementation claim.
    MPQ stays enabled so an empty conditional OTR TU cannot look successful.
    """
    folder=OUT/'integration-probe';folder.mkdir(parents=True,exist_ok=True)
    paths=['ResourceLoader.cpp','ResourceManager.cpp','archive/Archive.cpp',
           'archive/ArchiveManager.cpp','archive/FolderArchive.cpp','archive/O2rArchive.cpp','archive/OtrArchive.cpp']
    inc=includes(True)+[ROOT/'scratch/async-xdk/generated',ROOT/'scratch/libzip-xdk/generated',
                        ROOT/'scratch/deps/tinyxml2',ROOT/'libultraship/include']
    command=[ENV.XDK/'bin/win32/cl.exe','/nologo','/EHsc','/D_XBOX','/D_XBOX_VER=200',
             '/DINCLUDE_MPQ_SUPPORT','/I'+str(ENV.XDK/'include/xbox')]+['/I'+str(p) for p in inc]
    inventory={}
    for path in paths:
        label=path.replace('/','_').replace('.cpp','');source=ROOT/'libultraship/src/ship/resource'/path
        record=ENV.invoke(command+['/c','/Fo'+str(folder/(label+'.obj')),source],folder,label,success=False)
        inventory[path]={'source_sha256':hashlib.sha256(source.read_text(encoding='utf-8-sig').encode()).hexdigest(),
                         'returncode':record['returncode'],'evidence':label+'.json'}
    (folder/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Recorded seven real remaining-TU compile probes with MPQ enabled; this is unresolved integration evidence.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline-only',action='store_true')
    parser.add_argument('--integration-probe',action='store_true')
    args=parser.parse_args()
    if args.integration_probe:integration_probe();return
    if args.baseline_only:
        xdk(False);print('All nine original resource leaf TUs fail on XDK; exact diagnostics recorded.');return
    original=host(False);projected=host(True);assert original==projected
    xdk(True)
    evidence={'host_original':original,'host_projected':projected,'target_runtime_executed':False,
              'native_objects':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'xdk-generated').glob('*.obj')}}
    (OUT/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Actual resource factory host differential passes; nine real current resource TUs compile for XDK PPC BE.')

if __name__=='__main__':main()
