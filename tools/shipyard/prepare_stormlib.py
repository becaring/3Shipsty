"""Generate exact LUS-patched StormLib with explicit Xenon platform boundaries."""
import hashlib
import json
import argparse
import os
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable

OUT=ROOT/'scratch/stormlib-xdk'


def prepare():
    source=verified('stormlib')
    receipt=json.loads((ROOT/'scratch/deps/stormlib-receipt.json').read_text())
    for name in receipt['files']:
        path=source/name
        if path.suffix in ('.h','.c','.cpp') or name in ('CMakeLists.txt','LICENSE'):
            stable(OUT/'generated'/name,path.read_text(encoding='utf-8-sig'))
    patch=ROOT/'libultraship/cmake/dependencies/patches/stormlib-optimizations.patch'
    patch_text=patch.read_text(encoding='utf-8-sig')
    digest=hashlib.sha256(patch_text.encode()).hexdigest()
    lock=json.loads((ROOT/'platform/shipyard/resources/runtime-sources.lock.json').read_text())
    if digest!=lock['stormlib_patch_sha256']: raise ValueError('Pinned LUS StormLib patch changed')
    stable(OUT/'lus.patch',patch_text)
    command=['git','apply','--directory=scratch/stormlib-xdk/generated',str(OUT/'lus.patch')]
    subprocess.run(command[:2]+['--check']+command[2:],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(command,cwd=ROOT,check=True,capture_output=True)
    path=OUT/'generated/src/StormPort.h';text=path.read_text()
    old='  #include <windows.h>\n\n  #include <wininet.h>\n  #define STORMLIB_LITTLE_ENDIAN'
    if text.count(old)!=1: raise ValueError('StormLib Windows platform block changed')
    text=text.replace(old,'#ifdef _XBOX\n  #include <xtl.h>\n  #include <stdint.h>\n  #define STORMLIB_BIG_ENDIAN\n#else\n'+old+'\n#endif')
    stable(path,text)
    path=OUT/'generated/src/lzma/C/Types.h';text=path.read_text()
    old='#ifdef _WIN32\n#include <windows.h>\n#endif'
    if text.count(old)!=1:raise ValueError('LZMA native include block changed')
    stable(path,text.replace(old,'#ifdef _XBOX\n#include <xtl.h>\n#elif defined(_WIN32)\n#include <windows.h>\n#endif'))
    path=OUT/'generated/src/bzip2/bzlib.h';text=path.read_text()
    old='#   include <windows.h>'
    if text.count(old)!=1:raise ValueError('BZip2 native include changed')
    stable(path,text.replace(old,'#   ifdef _XBOX\n#     include <xtl.h>\n#   else\n'+old+'\n#   endif'))
    path=OUT/'generated/src/FileStream.cpp';text=path.read_text()
    start=text.index('// Local functions - base memory-mapped file support')
    end=text.index('// Local functions - base block-based support')
    block=text[start:end]
    if block.count('#ifdef STORMLIB_WINDOWS')!=6:raise ValueError('StormLib mapping/HTTP guards changed')
    # Native file streams remain unchanged. XDK has neither Win32 mapped views
    # nor WinInet; use StormLib's own unsupported-provider branches. Current
    # OtrArchive uses MPQ_OPEN_READ_ONLY, whose provider bits select plain files.
    block=block.replace('#ifdef STORMLIB_WINDOWS','#if defined(STORMLIB_WINDOWS) && !defined(_XBOX)')
    text=text[:start]+block+text[end:]
    old='#pragma comment(lib, "wininet.lib")             // Internet functions for HTTP stream'
    if text.count(old)!=1:raise ValueError('StormLib WinInet link pragma changed')
    text=text.replace(old,'#ifndef _XBOX\n'+old+'\n#endif')
    stable(path,text)
    path=OUT/'generated/src/SBaseCommon.cpp';text=path.read_text()
    # The MPQ ciphertext is converted to native DWORDs before these helpers
    # run. The pinned unaligned path reconstructs its return value as
    # little-endian bytes, corrupting the rolling key on big-endian Xenon.
    # memcpy preserves native word order without unaligned PPC accesses.
    for name, body in (
        ('EncryptUInt32Unaligned', '''    DWORD plain;
    DWORD encrypted;
    memcpy(&plain, pbDataPointer, sizeof(plain));
    encrypted = plain ^ dwXorKey;
    memcpy(pbDataPointer, &encrypted, sizeof(encrypted));
    return plain;'''),
        ('DecryptUInt32Unaligned', '''    DWORD decrypted;
    memcpy(&decrypted, pbDataPointer, sizeof(decrypted));
    decrypted ^= dwXorKey;
    memcpy(pbDataPointer, &decrypted, sizeof(decrypted));
    return decrypted;'''),
    ):
        pattern=(r'static DWORD '+name+
                 r'\(LPDWORD DataPointer, DWORD i, DWORD dwXorKey\)\n\{.*?\n\}')
        matches=list(re.finditer(pattern,text,re.S))
        if len(matches)!=1:raise ValueError('StormLib unaligned '+name+' changed')
        replacement=('static DWORD '+name+
                     '(LPDWORD DataPointer, DWORD i, DWORD dwXorKey)\n{\n'+
                     '    LPBYTE pbDataPointer = (LPBYTE)DataPointer + i * sizeof(DWORD);\n'+
                     body+'\n}')
        text=text[:matches[0].start()]+replacement+text[matches[0].end():]
    stable(path,text)
    stable(OUT/'manifest.json',json.dumps(dict(commit=receipt['commit'],lus_patch_sha256=digest,
        scope='Pinned upstream patch, Xenon headers, and endian-safe unaligned MPQ cipher words'),indent=2)+'\n')
    return source


def build(host=False):
    source=prepare()
    cmake=(source/'CMakeLists.txt').read_text()
    units=[]
    for group in ('SRC_FILES','TOMCRYPT_FILES','TOMMATH_FILES','BZIP2_FILES'):
        match=re.search(r'set\('+group+r'\s+(.*?)\n\)',cmake,re.S)
        if not match:raise ValueError('StormLib source manifest group missing: '+group)
        names=match[1].split()
        if not all(n.endswith(('.c','.cpp')) for n in names):raise ValueError('Unexpected StormLib source manifest')
        units.extend(names)
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    environment=os.environ.copy()
    if host:
        compiler,environment=runpy.run_path(str(ROOT/'tools/shipyard/tests/test_binary.py'))['host_environment']()
    else:compiler=sdk/'bin/win32/cl.exe'
    folder=OUT/('host' if host else 'xdk');folder.mkdir(parents=True,exist_ok=True)
    flags=['/nologo','/c','/O2','/MD' if host else '/MT','/D_7ZIP_ST','/DBZ_STRICT_ANSI','/D__SYS_ZLIB',
           '/DSTORMLIB_NO_AUTO_LINK','/D_CRT_SECURE_NO_WARNINGS','/I'+str(OUT/'generated/src'),'/I'+str(verified('zlib'))]
    if not host:flags+=['/D_XBOX','/DLTC_NO_ASM','/I'+str(sdk/'include/xbox')]
    records=[];objects=[]
    for name in units:
        obj=folder/(name[4:].replace('/','__').rsplit('.',1)[0]+'.obj')
        command=[str(compiler)]+flags+(['/EHsc', '/GR','/TP'] if name.endswith('.cpp') else ['/TC'])+[str(OUT/'generated'/name),'/Fo'+str(obj)]
        result=subprocess.run(command,env=environment,cwd=ROOT,capture_output=True,text=True)
        stable(obj.with_suffix('.log'),result.stdout+result.stderr)
        records.append(dict(source=name,exit=result.returncode,command=command))
        if not result.returncode:
            if not host and struct.unpack_from('<H',obj.read_bytes())[0]!=0x1f2:raise ValueError('Not a Xenon object')
            objects.append(obj)
    stable(folder/'build.json',json.dumps(dict(objects=records,target_runtime_executed=False),indent=2)+'\n')
    errors=[r for r in records if r['exit']]
    print(str(len(objects))+'/'+str(len(units))+' StormLib objects compile')
    for error in errors:print(error['source'])
    if errors:raise SystemExit(1)
    response=folder/'library.rsp';library=folder/'storm.lib'
    stable(response,'/nologo\n/OUT:"'+str(library)+'"\n'+'\n'.join('"'+str(p)+'"' for p in objects))
    result=subprocess.run([str(compiler.parent/'lib.exe'),'@'+str(response)],env=environment,cwd=ROOT,capture_output=True,text=True)
    stable(folder/'library.log',result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('StormLib librarian failed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true');parser.add_argument('--host',action='store_true');args=parser.parse_args()
    if args.build:build(args.host)
    else:prepare()
