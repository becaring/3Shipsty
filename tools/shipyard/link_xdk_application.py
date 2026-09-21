"""Link the complete current application with normal native archive extraction.

No alternate entry point, unresolved-symbol suppression or old application
objects. Link errors remain errors and are saved for the integration audit.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import generate_xdk_project as gen

OUT=gen.ROOT/'scratch/link-integration'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(tool,arguments,name):
    # Standard linker response syntax preserves paths with spaces. Everything is
    # an argument, never shell command text.
    response=OUT/(name+'.rsp')
    response.write_text('\n'.join(subprocess.list2cmdline([str(a)]) for a in arguments)+'\n')
    command=[str(gen.SDK/'bin/win32'/tool),'@'+str(response)]
    result=subprocess.run(command,cwd=OUT,capture_output=True,text=True)
    (OUT/(name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    return dict(command=command,arguments=[str(a) for a in arguments],exit=result.returncode)


def main():
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((gen.OUT/'manifest.json').read_text())
    proof=json.loads((gen.OUT/'complete-application-verification.json').read_text())
    if proof['build_exit'] or proof['manifest_sha256']!=sha(gen.OUT/'manifest.json'):
        raise ValueError('Full current compile verification required before linking')
    if manifest!=gen.collect():raise ValueError('Current project configuration differs from the compiled manifest')
    if not proof.get('header_sha256'):raise ValueError('Actual compiled header closure is required')
    for name,digest in proof['header_sha256'].items():
        if sha(gen.ROOT/name)!=digest:raise ValueError('Header changed after compilation: '+name)
    if manifest['application_counts']!={'selected':1094}:
        raise ValueError('The genuine application source inventory is incomplete')
    unresolved=[r['path'] for r in manifest['coverage'] if r['status']=='pending']
    if unresolved:raise ValueError('Unresolved platform/application source decisions: '+repr(unresolved))
    records={r['source']:r for r in proof['sources']}
    application=[];library=[]
    for row in manifest['sources']:
        record=records[row['source']];obj=gen.ROOT/record['object']
        if sha(gen.ROOT/row['source'])!=record['source_sha256'] or sha(obj)!=record['object_sha256']:
            raise ValueError('Changed compiled input: '+row['source'])
        # Keep every application initializer linked. LUS and dependencies use
        # ordinary static archive extraction, including the os_pi/cache members
        # whose inactive symbols are already owned by modern application stubs.
        (application if (row['upstream_source'] or '').startswith('soh/') else library).append(obj)
    archive=OUT/'Shipyard.lib'
    result=dict(manifest_sha256=sha(gen.OUT/'manifest.json'),application_objects=len(application),
                archive_objects=len(library),runtime_executed=False)
    result['archive']=invoke('lib.exe',['/nologo','/out:'+str(archive)]+library,'archive')
    if not result['archive']['exit']:
        libraries=['xboxkrnl.lib','xapilib.lib','d3d9.lib','d3dx9.lib','xgraphics.lib','xaudio2.lib','xmcore.lib','xnet.lib']
        flags=['/nologo','/incremental:no','/out:'+str(OUT/'3Shipsty.exe'),'/libpath:'+str(gen.SDK/'lib/xbox'),
               '/debug','/pdb:'+str(OUT/'3Shipsty.pdb'),'/map:'+str(OUT/'3Shipsty.map'),
               '/stack:4194304,4194304','/opt:ref','/XEX:NO',
               # StormLib.h's desktop MSVC auto-link name. The complete real
               # pinned StormLib objects are already in the explicit archive.
               # This is the link equivalent of STORMLIB_NO_AUTO_LINK, not an
               # unresolved-symbol override or removal of MPQ functionality.
               '/nodefaultlib:StormLibRAS.lib']
        result['link']=invoke('link.exe',flags+application+[archive]+libraries,'application-link')
        if not result['link']['exit']:
            result['executable_sha256']=sha(OUT/'3Shipsty.exe')
            command=[str(gen.SDK/'bin/win32/imagexex.exe'),'/in:'+str(OUT/'3Shipsty.exe'),
                     '/out:'+str(OUT/'3Shipsty.xex'),'/config:'+str(gen.ROOT/'platform/shipyard/build/xex.xml')]
            image=subprocess.run(command,cwd=OUT,capture_output=True,text=True)
            (OUT/'imagexex.log').write_text(image.stdout+image.stderr)
            result['image']=dict(command=command,exit=image.returncode)
            if not image.returncode:result['xex_sha256']=sha(OUT/'3Shipsty.xex')
    (OUT/'link-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    code=result.get('image',result.get('link',result['archive']))['exit']
    print('Genuine application link:',code,'; see scratch/link-integration/application-link.log',flush=True)
    return code


if __name__=='__main__':raise SystemExit(main())
