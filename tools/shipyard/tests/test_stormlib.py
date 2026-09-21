"""Exercise the exact release-patched MPQ library and retained codecs."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'scratch/stormlib-xdk'


def main():
    compiler,env=runpy.run_path(str(Path(__file__).with_name('test_binary.py')))['host_environment']()
    folder=OUT/'host'
    command=[str(compiler),'/nologo','/EHsc','/MD','/D_CRT_SECURE_NO_WARNINGS','/DSTORMLIB_NO_AUTO_LINK',
             '/I'+str(OUT/'generated/src'),str(Path(__file__).with_name('test_stormlib_contract.cpp')),
             str(folder/'storm.lib'),str(ROOT/'scratch/libzip-xdk/host/zlib.lib'),'user32.lib',
             '/Fe:'+str(folder/'storm-contract.exe'),'/Fo:'+str(folder)+'/']
    result=subprocess.run(command,env=env,cwd=ROOT,capture_output=True,text=True)
    (folder/'contract-build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('See StormLib contract-build.log')
    result=subprocess.run([str(folder/'storm-contract.exe'),str(folder/'contract.otr'),str(folder/'contract.bin')],
                          cwd=folder,capture_output=True,text=True)
    (folder/'verification.json').write_text(json.dumps(dict(command=command,exit=result.returncode,stdout=result.stdout,
        stderr=result.stderr,target_runtime_executed=False),indent=2)+'\n')
    print(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('StormLib contract failed')


if __name__=='__main__':main()
