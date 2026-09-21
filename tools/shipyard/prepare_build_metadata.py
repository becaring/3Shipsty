"""Configure the real pinned build.c.in in scratch, without running PC CMake."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
from source_inventory import ROOT,BASE
from prepare_archives import stable

OUT=ROOT/'scratch/build-metadata-xdk'


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def prepare():
    names=['CMakeLists.txt','soh/src/boot/build.c.in']
    inputs={}
    for name in names:
        source=(ROOT/name).read_text(encoding='utf-8-sig')
        pinned=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
        if source!=pinned:raise ValueError('Build metadata input differs from stable baseline: '+name)
        inputs[name]=hashlib.sha256(source.encode()).hexdigest()
    cmake=(ROOT/names[0]).read_text()
    version=re.search(r'project\(Ship VERSION (\d+)\.(\d+)\.(\d+) LANGUAGES',cmake).groups()
    words=re.findall(r'"([A-Za-z]+)"',re.search(r'set\(NATO_PHONETIC_ALPHABET(.*?)\)',cmake,re.S)[1])
    build=re.search(r'set\(PROJECT_BUILD_NAME "([^"]+)"',cmake)[1].replace('${PROJECT_PATCH_WORD}',words[int(version[2])])
    commit=git('rev-parse','HEAD');branch=git('branch','--show-current')
    tag=subprocess.run(['git','describe','--tags','--abbrev=0','--exact-match','HEAD'],cwd=ROOT,capture_output=True,text=True)
    values=dict(PROJECT_BUILD_NAME=build,PROJECT_TEAM=re.search(r'set\(PROJECT_TEAM "([^"]+)"',cmake)[1],
                CMAKE_PROJECT_GIT_BRANCH=branch,CMAKE_PROJECT_GIT_COMMIT_HASH=commit[:7],
                CMAKE_PROJECT_GIT_COMMIT_TAG=tag.stdout.strip() if not tag.returncode else '')
    values.update({'CMAKE_PROJECT_VERSION_'+n:v for n,v in zip(['MAJOR','MINOR','PATCH'],version)})
    source=(ROOT/names[1]).read_text()
    for name,value in values.items():
        source=source.replace('@'+name+'@',value.replace('\\','\\\\').replace('"','\\"'))
    if re.search(r'@\w+@',source):raise ValueError('Unconfigured metadata variable')
    # This template needs only libultra's u16 alias; use its exact 16-bit C type.
    source=source.replace('#include <libultraship/libultra.h>','#include <stdint.h>').replace('const u16 ','const uint16_t ')
    epoch=int(os.environ.get('SOURCE_DATE_EPOCH',git('show','-s','--format=%ct','HEAD')))
    date=datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc)
    stamp=date.strftime('%b ')+str(date.day).rjust(2)+date.strftime(' %Y %H:%M:%S')
    source=source.replace('__DATE__ " " __TIME__',json.dumps(stamp))
    OUT.mkdir(exist_ok=True);stable(OUT/'build.c',source)
    stable(OUT/'manifest.json',json.dumps(dict(upstream_commit=BASE,inputs=inputs,values=values,port_commit=commit,
        reproducible_date_epoch=epoch,date_policy='SOURCE_DATE_EPOCH or port commit time, UTC',
        generated_sha256=hashlib.sha256(source.encode()).hexdigest()),indent=2)+'\n')
    return values


def main():
    values=prepare();sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    folder=OUT/'xdk';folder.mkdir(exist_ok=True);source=OUT/'build.c';obj=folder/'build.obj'
    command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TC','/MT','/O2','/D_XBOX','/I'+str(sdk/'include/xbox'),str(source),'/Fo'+str(obj)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);stable(folder/'build.log',result.stdout+result.stderr)
    row=dict(command=command,exit=result.returncode,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    if result.returncode==0:
        assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
        from test_custom_message import coff_symbols
        symbols=coff_symbols(obj)
        for name,component in [('Major','MAJOR'),('Minor','MINOR'),('Patch','PATCH')]:
            assert struct.unpack('>H',symbols['gBuildVersion'+name][:2])[0]==int(values['CMAKE_PROJECT_VERSION_'+component])
        assert symbols['gBuildVersion'].split(b'\0')[0]==(values['PROJECT_BUILD_NAME']+' (9.2.3)').encode()
        assert symbols['gGitCommitHash'].split(b'\0')[0]==values['CMAKE_PROJECT_GIT_COMMIT_HASH'].encode()
        row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest()
    stable(folder/'build.json',json.dumps([row],indent=2)+'\n')
    print('Actual pinned build template/native metadata:',result.returncode,values['PROJECT_BUILD_NAME'],flush=True)
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
