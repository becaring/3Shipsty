"""Fresh differential and PowerPC object evidence for bounded JSON only."""
from pathlib import Path
import subprocess,os,json,hashlib,runpy,difflib
ROOT=Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0,str(ROOT/'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE=resolve_platform_base(ROOT)
OUT=ROOT/'scratch/json-xdk'; TESTS=Path(__file__).parent/'test_json'; BACKEND=PLATFORM_BASE/'sources/json'
ORIGINAL=ROOT/'platform/shipyard/json/upstream'
def execute(args,label,env=None,success=True):
    folder=OUT/label;folder.mkdir(parents=True,exist_ok=True)
    r=subprocess.run(list(map(str,args)),cwd=folder,env=env,text=True,capture_output=True)
    (folder/'command.json').write_text(json.dumps(list(map(str,args)),indent=2)+'\n')
    (folder/'result.log').write_text(r.stdout+r.stderr)
    if success and r.returncode:raise AssertionError(label+':\n'+r.stdout+r.stderr)
    return r
def host():
    msvc=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808');sdk=Path('C:/Program Files (x86)/Windows Kits/10')
    env=os.environ.copy();env['PATH']=str(msvc/'bin/Hostx64/x64')+os.pathsep+env['PATH']
    env['INCLUDE']=';'.join(map(str,[msvc/'include']+[sdk/'Include/10.0.26100.0'/p for p in ('ucrt','shared','um')]))
    env['LIB']=';'.join(map(str,[msvc/'lib/x64']+[sdk/'Lib/10.0.26100.0'/p/'x64' for p in ('ucrt','um')]))
    return msvc/'bin/Hostx64/x64/cl.exe',env
INCLUDES=['/I'+str(BACKEND/'include'),'/I'+str(BACKEND.parent),'/I'+str(OUT/'backend-generated')]
def build(source,label,backend=True,syntax=False,success=True,extra=None):
    compiler,env=host();folder=OUT/label
    args=[compiler,'/nologo','/std:c++20','/EHsc','/MD','/W4']+(INCLUDES if backend else ['/I'+str(ORIGINAL/'include')])
    args+=['/Zs'] if syntax else ['/Fo'+str(folder)+'\\','/Fe'+str(folder/'test.exe')]
    args += list(extra or [])
    args += [source]
    if backend and not syntax:args+=[BACKEND/'json.cpp']
    r=execute(args,label,env,success)
    if syntax or r.returncode:return r
    return execute([folder/'test.exe'],label+'-run')
def main():
    runpy.run_path(str(ROOT/'tools/shipyard/prepare_json.py'))['generate']()
    checks={}
    for case in ['reference','edge_contract','modern_save_contract','extended_contract','container_contract','stream_contract','ordered_contract']:
        before=build(TESTS/(case+'.cpp'),case+'-official',False)
        after=build(TESTS/(case+'.cpp'),case+'-backend')
        if before.stdout!=after.stdout:raise AssertionError(''.join(difflib.unified_diff(before.stdout.splitlines(True),after.stdout.splitlines(True))))
        checks[case]=hashlib.sha256(before.stdout.encode()).hexdigest()
    generated=OUT/'backend-generated/json/generated'
    ordered_stream=generated/'ordered_stream_contract.cpp'
    ordered_stream.write_text((TESTS/'stream_contract.cpp').read_text().replace('nlohmann::json','nlohmann::ordered_json').replace('using nlohmann::ordered_json;','typedef nlohmann::ordered_json json;'),newline='\n')
    for label,original,projected in [('ordered_stream_contract',ordered_stream,ordered_stream),('ordered_consumer_contract',generated/'ordered_consumer_original.cpp',generated/'ordered_consumer_projected.cpp')]:
        before=build(original,label+'-official',False)
        after=build(projected,label+'-backend')
        assert before.stdout==after.stdout,''.join(difflib.unified_diff(before.stdout.splitlines(True),after.stdout.splitlines(True)))
        lowered=build(projected,label+'-entry-projection',extra=['/DSHIPYARD_JSON_ORDERED_ENTRY_PROJECTION'])
        assert before.stdout==lowered.stdout
        checks[label]=hashlib.sha256(before.stdout.encode()).hexdigest()
    lowered=build(TESTS/'ordered_contract.cpp','ordered-entry-projection',extra=['/DSHIPYARD_JSON_ORDERED_ENTRY_PROJECTION'])
    assert lowered.stdout==(OUT/'ordered_contract-official-run/result.log').read_text()
    stream_termination={}
    for mode in ['extract','parse']:
        for variant in ['official','backend']:
            label='stream-contract-termination-'+mode+'-'+variant
            r=execute([OUT/('stream_contract-'+variant)/'test.exe',mode],label,success=False)
            assert r.returncode==73,(label,r.returncode,r.stdout,r.stderr)
            stream_termination[mode+'-'+variant]=r.returncode
    modern=OUT/'backend-generated/json/generated/modern_enum_contract.cpp'
    before=build(modern,'modern-enum-official',False)
    after=build(modern,'modern-enum-backend')
    assert before.stdout==after.stdout
    checks['modern_enum_contract']=hashlib.sha256(before.stdout.encode()).hexdigest()
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    base=[sdk/'bin/win32/cl.exe','/nologo','/EHsc','/GR','/D_XBOX','/D_XBOX_VER=200','/I'+str(sdk/'include/xbox')]+INCLUDES
    objects={}
    for name,source in [('backend',BACKEND/'json.cpp'),('api',TESTS/'xdk_api.cpp'),('containers',TESTS/'container_contract.cpp'),('modern-enum',modern),('streams',TESTS/'stream_contract.cpp'),('ordered',TESTS/'ordered_contract.cpp'),('ordered-consumer',generated/'ordered_consumer_projected.cpp')]:
        target=OUT/('xdk-'+name)/(name+'.obj')
        execute(base+['/c','/Fo'+str(target),source],'xdk-'+name)
        raw=target.read_bytes();assert int.from_bytes(raw[:2],'little')==0x1f2;objects[name]=hashlib.sha256(raw).hexdigest()
    unknown=execute(base+['/Zs',TESTS/'unsupported_get.cpp'],'xdk-unsupported-get',success=False)
    assert unknown.returncode!=0 and 'UnregisteredValue' in unknown.stdout
    unknown_enum=execute(base+['/Zs',TESTS/'unsupported_enum.cpp'],'xdk-unsupported-enum',success=False)
    assert unknown_enum.returncode!=0 and 'UnregisteredEnum' in unknown_enum.stdout
    for source in sorted((TESTS/'supported').glob('*.cpp')):
        build(source,'supported-'+source.stem+'-official',False,True)
        build(source,'supported-'+source.stem+'-backend',True,True)
        execute(base+['/Zs',source],'supported-'+source.stem+'-xdk')
    gaps={}
    for source in sorted((TESTS/'gaps').glob('*.cpp')):
        build(source,'gap-'+source.stem+'-official',False,True)
        r=build(source,'gap-'+source.stem+'-backend',True,True,False)
        assert r.returncode!=0,'Gap is implemented; update audit: '+source.stem
        gaps[source.stem]={'official_compiles':True,'backend_compiles':False}
    (OUT/'verification.json').write_text(json.dumps({'host_differential_sha256':checks,'float_bit_patterns':4000,'stream_eof_exception_termination':stream_termination,'ordered_entry_projection_host_tested':True,'xdk_objects':objects,'powerpc_machine':'0x1f2','unknown_conversion_rejected':True,'modern_api_gaps':gaps,'full_modern_application_integrated':False,'console_execution_tested':False},indent=2)+'\n')
    print('PASS: ten host differentials; seven PowerPC objects; fail-closed modern API and enum probes')
if __name__=='__main__':main()
