"""Host original/projected logger differential and native compiler evidence."""
from pathlib import Path
import subprocess
import json

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'scratch/logging-xdk/tests'
BASE=ROOT/'platform/shipyard/logging'
def run(command,name,cwd=None):
    p=subprocess.run(command,capture_output=True,text=True,cwd=cwd,timeout=90)
    (OUT/(name+'.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    run(['C:/Python313/python.exe','-B',str(ROOT/'tools/shipyard/prepare_logging.py')],'generate')
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    source=BASE/'tests/core_cases.cpp';native=ROOT/'platform/shipyard/async/native.cpp';chrono=BASE/'chrono/chrono.cpp';results=[];formats=[];gaps=[]
    for original in (1,0):
        target=OUT/str(original);target.mkdir(exist_ok=True);exe=target/'core.exe';batch=target/'build.cmd'
        for file in target.glob('rotation*.log'):file.unlink()
        includes=[ROOT/'scratch/deps/spdlog/include'] if original else [OUT.parent/'core-include',OUT.parent/'include',ROOT/'scratch/deps/fmt-xdk']
        batch.write_text(f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /utf-8 /MT /D_CRT_SECURE_NO_WARNINGS /DORIGINAL_SPDLOG={original} /DSPDLOG_EOL=\\\"\\n\\\" /I"{ROOT}" '+ ' '.join('/I"'+str(p)+'"' for p in includes)+f' "{source}" "{native}" "{chrono}" /Fo"{target}/" /Fe"{exe}"\nexit /b %errorlevel%\n')
        run(['cmd','/d','/c',str(batch)],str(original)+'-compile');results.append(run([str(exe),str(target)],str(original)+'-run'))
        format_source=BASE/'tests/format_cases.cpp';format_exe=target/'format.exe'
        batch.write_text(f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /utf-8 /MT /D_CRT_SECURE_NO_WARNINGS /DORIGINAL_SPDLOG={original} /I"{ROOT}" '+ ' '.join('/I"'+str(p)+'"' for p in includes)+f' "{format_source}" /Fo"{target}/format.obj" /Fe"{format_exe}"\nexit /b %errorlevel%\n')
        run(['cmd','/d','/c',str(batch)],str(original)+'-format-compile');formats.append(run([str(format_exe)],str(original)+'-format-run'))
        gap_source=BASE/'tests/default_float_gap.cpp';gap_exe=target/'default_float.exe'
        batch.write_text(batch.read_text().replace(str(format_source),str(gap_source)).replace(str(format_exe),str(gap_exe)).replace('format.obj','default_float.obj'))
        run(['cmd','/d','/c',str(batch)],str(original)+'-gap-compile');gaps.append(run([str(gap_exe)],str(original)+'-gap-run'))
    if results[0]!=results[1]:raise RuntimeError('Original/generated logger outputs differ: '+repr(results))
    if formats[0]!=formats[1]:raise RuntimeError('Original/generated SoH typed format corpus differs')
    if gaps[0]!=gaps[1]:raise RuntimeError('Default floating precision regression')
    (OUT/'format-limits.json').write_text(json.dumps(dict(default_double=1.23456789012345,original_fmt12=gaps[0].strip(),compiler_fmt4_with_fmt12_dragonbox=gaps[1].strip(),equal=True,status='Default binary32/64 float gap resolved; broad corpus in float-tests/verification.json. Explicit precision still uses CRT.'),indent=2)+'\n')
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    for name,src in [('core',source),('format',BASE/'tests/format_cases.cpp'),('chrono',chrono),('environment',BASE/'environment.cpp')]:
        obj=OUT/(name+'-xdk.obj')
        run([str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/EHsc','/D_XBOX','/DORIGINAL_SPDLOG=0','/c','/I'+str(ROOT),'/I'+str(OUT.parent/'core-include'),'/I'+str(OUT.parent/'include'),'/I'+str(ROOT/'scratch/deps/fmt-xdk'),'/I'+str(xdk/'include/xbox'),'/Fo'+str(obj),str(src)],'xdk-'+name)
        if int.from_bytes(obj.read_bytes()[:2],'little')!=0x1f2:raise RuntimeError('Expected PPC COFF')
    print(results[0]);print('PASS exact host logger and SoH typed formatting differentials, four XDK PPC objects; no Xbox execution')

if __name__=='__main__':main()
