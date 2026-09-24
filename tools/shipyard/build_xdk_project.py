"""Run the generated full compile target and record verified native objects."""
import argparse
import hashlib
import json
import generate_xdk_project as gen
from xbox360_platform import parallel_build


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_plan(manifest, jobs=8):
    project=gen.OUT/'ShipyardCompile.vcxproj'
    xml=gen.ET.parse(project).getroot()
    items=xml.findall('.//{'+gen.NS+'}ClCompile[@Include]')
    if len(items)!=len(manifest['sources']):
        raise ValueError('Generated project source count differs from manifest')
    rows=[]
    for record,item in zip(manifest['sources'],items):
        source=gen.source_path(record['source']).resolve()
        expected=('$(ShipyardPlatformBase)/'+record['source'][len('shipyard/'):] if record['source'].startswith('shipyard/')
                  else '$(ShipyardRoot)/'+record['source'])
        if item.attrib['Include']!=expected:
            raise ValueError('Generated project source order differs from manifest: '+record['source'])
        rows.append(dict(include=expected,source=str(source),
                         object=str(gen.OUT/'build/obj'/record['object']),sha256=record['sha256']))
    return parallel_build.plan(project,rows,gen.OUT/'build/shards',jobs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=8,help='Independent XDK compiler shards (default: 8)')
    args=parser.parse_args()
    if not 1<=args.jobs<=32:parser.error('--jobs must be between 1 and 32')
    manifest=gen.collect()
    if manifest['missing_subsystem_recipes']:
        raise ValueError('Missing production recipes: '+repr(manifest['missing_subsystem_recipes']))
    gen.write(manifest)
    build=project_plan(manifest,args.jobs)
    log=gen.OUT/'complete-application-build.log'
    proof_path=gen.OUT/'complete-application-verification.json'
    if proof_path.exists():proof_path.unlink()
    try:
        shared=parallel_build.run(
            build,['C:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe'],
            arguments=['/p:Configuration=Release','/p:Platform=Xbox 360','/nologo','/verbosity:minimal'],
            owned_roots=[gen.ROOT,gen.PLATFORM_BASE])
        builds=[dict(row,project=gen.relative(row['project']),log=gen.relative(row['log']))
                for row in shared['builds']]
        for index,row in enumerate(builds):
            print('XDK shard %02d/%02d: exit %s in %.1fs' %
                  (index+1,len(builds),row['exit'],row['seconds']),flush=True)
        log.write_text('Shared Xbox compiler shards: %d\n' % len(builds)+
                       ''.join('%s exit=%s seconds=%s\n' %
                               (row['log'],row['exit'],row['seconds']) for row in builds),encoding='utf-8')
        build_exit=shared['build_exit']
        report=dict(command=[row['command'] for row in builds],builds=builds,
                    build_exit=build_exit,log=gen.relative(log),
                    manifest_sha256=sha(gen.OUT/'manifest.json'),project_sha256=sha(build.project),
                    application_counts=manifest['application_counts'],runtime_executed=False,sources=[])
        if build_exit==0:
            parallel_build.verify_receipt(build,shared)
            by_source={str(gen.source_path(row['source']).resolve()):row for row in manifest['sources']}
            report['sources']=[dict(source=by_source[row['source']]['source'],
                                    source_sha256=row['source_sha256'],
                                    object=gen.relative(row['object']),object_sha256=row['object_sha256'])
                               for row in shared['sources']]
            report['header_sha256']={gen.relative(name):digest for name,digest in shared['headers'].items()}
            report['shared_compile_receipt']=gen.relative(build.output/'compile-receipt.json')
        report['objects']=len(report['sources'])
        proof_path.write_text(json.dumps(report,indent=2)+'\n')
        print('Full application compile:',build_exit,'verified PPC objects:',report['objects'],flush=True)
        return build_exit
    finally:
        parallel_build.remove_shards(build)


if __name__=='__main__':raise SystemExit(main())
