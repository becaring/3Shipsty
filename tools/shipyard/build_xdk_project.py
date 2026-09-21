"""Run the generated full compile target and record verified native objects."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import generate_xdk_project as gen


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=gen.collect()
    if manifest['missing_subsystem_recipes']:
        raise ValueError('Missing production recipes: '+repr(manifest['missing_subsystem_recipes']))
    gen.write(manifest)
    project=gen.OUT/'ShipyardCompile.vcxproj'
    command=['C:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe',str(project),
             '/t:ClCompile','/p:Configuration=Release','/p:Platform=Xbox 360','/nologo','/verbosity:minimal']
    log=gen.OUT/'complete-application-build.log'
    with log.open('w',encoding='utf-8') as output:
        result=subprocess.run(command,cwd=gen.ROOT,stdout=output,stderr=subprocess.STDOUT)
    report=dict(command=command,build_exit=result.returncode,log=gen.relative(log),
                manifest_sha256=sha(gen.OUT/'manifest.json'),project_sha256=sha(project),
                application_counts=manifest['application_counts'],runtime_executed=False,sources=[])
    if result.returncode==0:
        for row in manifest['sources']:
            source=gen.ROOT/row['source'];obj=gen.OUT/'build/obj'/row['object']
            if sha(source)!=row['sha256']:
                raise ValueError('Source changed during build: '+row['source'])
            data=obj.read_bytes()
            offset=6 if data[:4]==b'\0\0\xff\xff' else 0
            if struct.unpack_from('<H',data,offset)[0]!=0x1f2:
                raise ValueError('Not a PowerPC BE COFF object: '+str(obj))
            report['sources'].append(dict(source=row['source'],source_sha256=row['sha256'],
                object=gen.relative(obj),object_sha256=hashlib.sha256(data).hexdigest()))
        # Record the actual compiler's owned header closure, not hypothetical
        # include-path candidates. Link must reject later header drift too.
        selected={str((gen.ROOT/r['source']).resolve()).casefold() for r in manifest['sources']}
        headers={};active=False
        for line in (gen.OUT/'build/obj/CL.read.1.tlog').read_text(encoding='utf-16').splitlines():
            if line.startswith('^'):
                active=any(str(Path(s).resolve()).casefold() in selected for s in line[1:].split('|'))
            elif active:
                path=Path(line)
                if path.suffix.lower() in ('.h','.hpp','.inl','.inc') and path.is_relative_to(gen.ROOT) and path.is_file():
                    headers[gen.relative(path)]=sha(path)
        if not headers:raise ValueError('Actual owned header dependency closure is absent')
        report['header_sha256']=dict(sorted(headers.items()))
    report['objects']=len(report['sources'])
    (gen.OUT/'complete-application-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Full application compile:',result.returncode,'verified PPC objects:',report['objects'],flush=True)
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
