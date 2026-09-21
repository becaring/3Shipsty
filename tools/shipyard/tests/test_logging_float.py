"""Whole-output fmt12/compiler differential, including portable Dragonbox math."""
from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'scratch/logging-xdk/float-tests'
def run(args,log):
    p=subprocess.run(args,capture_output=True,timeout=180)
    (OUT/(log+'.log')).write_bytes(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError((p.stdout+p.stderr).decode(errors='replace'))
    return p.stdout
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'platform/shipyard/logging/tests/float_cases.cpp'
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    outputs=[]
    for original in (1,0):
        sub=OUT/str(original);sub.mkdir(exist_ok=True)
        inc=[ROOT/'scratch/deps/spdlog/include'] if original else [ROOT/'scratch/logging-xdk/core-include',ROOT/'scratch/logging-xdk/include',ROOT/'scratch/deps/fmt-xdk']
        command=f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /O2 /EHsc /std:c++20 /utf-8 /MT /D_CRT_SECURE_NO_WARNINGS /DORIGINAL_SPDLOG={original} /I"{ROOT}" '+ ' '.join('/I"'+str(p)+'"' for p in inc)+f' "{source}" /Fo"{sub}/float.obj" /Fe"{sub}/float.exe"\nexit /b %errorlevel%\n'
        batch=sub/'build.cmd';batch.write_text(command)
        run(['cmd','/d','/c',str(batch)],f'{original}-compile')
        outputs.append(run([str(sub/'float.exe')],f'{original}-run'))
    if outputs[0]!=outputs[1]:
        a=outputs[0].splitlines();b=outputs[1].splitlines()
        for i,(x,y) in enumerate(zip(a,b)):
            if x!=y:raise RuntimeError(f'Float difference line {i+1}: original={x!r}, projected={y!r}')
        raise RuntimeError('Float output length differs')
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    obj=OUT/'float-xdk.obj'
    run([str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/O2','/EHsc','/GR','/D_XBOX','/DORIGINAL_SPDLOG=0','/c','/I'+str(ROOT),'/I'+str(ROOT/'scratch/logging-xdk/core-include'),'/I'+str(ROOT/'scratch/logging-xdk/include'),'/I'+str(ROOT/'scratch/deps/fmt-xdk'),'/I'+str(xdk/'include/xbox'),'/Fo'+str(obj),str(source)],'native')
    assert int.from_bytes(obj.read_bytes()[:2],'little')==0x1f2
    report={'cases':len(outputs[0].splitlines()),'sha256':hashlib.sha256(outputs[0]).hexdigest(),'native_compile':'PPC COFF','native_execution':False,'algorithm':'actual fmt12 binary32/64 Dragonbox; portable full-cache path'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()

