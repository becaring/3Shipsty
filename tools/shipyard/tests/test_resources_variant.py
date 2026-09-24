import importlib.util
from pathlib import Path
import json
import subprocess
import struct
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT = ROOT / 'scratch/resources-xdk/variant'
SPEC = importlib.util.spec_from_file_location('binary_environment', Path(__file__).with_name('test_binary.py'))
ENV = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ENV)

def run(args, folder, name, env=None):
    result = subprocess.run(list(map(str,args)), cwd=folder, env=env, capture_output=True, text=True)
    (folder/(name+'.json')).write_text(json.dumps({'command':list(map(str,args)), 'exit':result.returncode,
        'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout

def main():
    compiler,env=ENV.host_environment();results=[]
    for label,flag in [('original','/DTEST_ORIGINAL'),('projected','/DTEST_PROJECTED')]:
        folder=OUT/label;folder.mkdir(parents=True,exist_ok=True)
        run([compiler,'/nologo','/std:c++20','/EHsc','/MD',flag,'/I'+str(ROOT/'platform/shipyard'),
             '/I'+str(PLATFORM_BASE/'sources'),
             '/I'+str(PLATFORM_BASE/'sources/value_types'),
             '/Fe:'+str(folder/'test.exe'),'/Fo:'+str(folder)+'/',Path(__file__).with_suffix('.cpp')],folder,'compile',env)
        results.append(run([folder/'test.exe'],folder,'run'))
    assert results[0]==results[1]
    folder=OUT/'xdk';folder.mkdir(parents=True,exist_ok=True)
    obj=folder/'variant.obj'
    run([ENV.XDK/'bin/win32/cl.exe','/nologo','/c','/EHsc','/D_XBOX','/I'+str(ENV.XDK/'include/xbox'),
         '/I'+str(PLATFORM_BASE/'sources'),
         '/I'+str(PLATFORM_BASE/'sources/value_types'),
         '/I'+str(ROOT/'platform/shipyard'),'/Fo'+str(obj),Path(__file__).with_suffix('.cpp')],folder,'compile')
    assert struct.unpack_from('<H',obj.read_bytes())[0]==0x1f2
    print('Variant host differential and native instantiation pass')
if __name__=='__main__':main()
