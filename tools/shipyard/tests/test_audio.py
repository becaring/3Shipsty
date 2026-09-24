"""Current matrix differential and AudioPlayer/native ownership unit contracts."""
import json
from pathlib import Path
import runpy
import subprocess

ROOT=Path(__file__).resolve().parents[3]
import sys
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
OUT=ROOT/'scratch/audio-xdk'


def main():
    env=runpy.run_path(str(Path(__file__).with_name('test_resources.py')))
    compiler,environment=env['ENV'].host_environment();records=[];outputs=[]
    for projected in (False,True):
        folder=OUT/('host-matrix-projected' if projected else 'host-matrix-original');folder.mkdir(parents=True,exist_ok=True)
        source=OUT/'generated' if projected else ROOT/'libultraship'
        command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/O2','/fp:precise','/I'+str(source/'include'),
                 str(source/'src/ship/audio/SoundMatrixDecoder.cpp'),str(Path(__file__).with_name('test_matrix_contract.cpp')),
                 '/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'matrix.exe')]
        result=subprocess.run(command,env=environment,cwd=ROOT,capture_output=True,text=True)
        (folder/'build.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('See '+str(folder/'build.log'))
        result=subprocess.run([str(folder/'matrix.exe')],capture_output=True,text=True,cwd=folder)
        if result.returncode:raise RuntimeError('Matrix contract failed: '+result.stderr)
        outputs.append(result.stdout);records.append(dict(command=command,exit=result.returncode,stdout=result.stdout))
    if outputs[0]!=outputs[1]:raise RuntimeError('Current original/projected matrix PCM differs')
    folder=OUT/'host-player';folder.mkdir(parents=True,exist_ok=True)
    includes=[OUT/'generated/include',ROOT/'scratch/resource-manager-xdk/generated/include',PLATFORM_BASE/'sources']+env['includes'](True)
    command=[str(compiler),'/nologo','/std:c++20','/EHsc','/MD','/O2','/fp:precise','/DSHIPYARD_AUDIO_TEST','/DNOMINMAX',
             '/DSPDLOG_ACTIVE_LEVEL=0']+['/I'+str(p) for p in includes]
    command += [str(OUT/'generated/src/ship/audio'/(n+'.cpp')) for n in ('AudioPlayer','SoundMatrixDecoder')]
    command += [str(PLATFORM_BASE/'sources/audio/PcmBufferPool.cpp')]
    command += [str(PLATFORM_BASE/'sources/clock/chrono.cpp'),str(ROOT/'platform/shipyard/logging/environment.cpp')]
    command += [str(PLATFORM_BASE/'sources/async/native.cpp')]
    command += [str(Path(__file__).with_name('test_audio_contract.cpp')),'/Fo:'+str(folder)+'/', '/Fe:'+str(folder/'player.exe')]
    result=subprocess.run(command,env=environment,cwd=ROOT,capture_output=True,text=True)
    (folder/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('See audio host-player/build.log')
    result=subprocess.run([str(folder/'player.exe')],cwd=folder,capture_output=True,text=True)
    (OUT/'verification.json').write_text(json.dumps(dict(matrix=records,player_command=command,player_exit=result.returncode,
        stdout=result.stdout,stderr=result.stderr,target_runtime_executed=False),indent=2)+'\n')
    print(outputs[0]+result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('AudioPlayer/PCM ownership contract failed')


if __name__=='__main__':main()
