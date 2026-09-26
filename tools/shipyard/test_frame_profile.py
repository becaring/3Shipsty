"""Run the real coarse frame accumulator on an injected deterministic clock."""
import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'scratch/frame-profile'


def main():
    OUT.mkdir(exist_ok=True)
    compiler, env = runpy.run_path(str(ROOT / 'tools/shipyard/tests/test_binary.py'))['host_environment']()
    command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
               '/I' + str(ROOT / 'platform/shipyard'),
               str(ROOT / 'platform/shipyard/application/frame_profile_contract.cpp'),
               '/Fo:' + str(OUT) + '/', '/Fe:' + str(OUT / 'contract.exe')]
    result = subprocess.run(command, cwd=OUT, env=env, capture_output=True, text=True)
    (OUT / 'build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([str(OUT / 'contract.exe')], cwd=OUT, capture_output=True, text=True)
    (OUT / 'run.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout)
    runtime = (ROOT / 'platform/shipyard/xenos/services.cpp').read_text().split('namespace ModernFrameProfile {', 1)[1]
    harness = '''#include "application/frame_profile.h"
#include <cassert>
#include <cstdarg>
struct LARGE_INTEGER { long long QuadPart; };
unsigned clockReads=0, frequencyReads=0, logCalls=0;
void QueryPerformanceCounter(LARGE_INTEGER* v) { v->QuadPart=++clockReads; }
void QueryPerformanceFrequency(LARGE_INTEGER* v) { ++frequencyReads; v->QuadPart=1000; }
void Shipyard_Log(const char*, ...) { ++logCalls; }
namespace ModernFrameProfile {
''' + runtime + '''
int main() {
    using namespace ModernFrameProfile;
    for(unsigned i=0;i<240;++i) {
        BeginFrame(false); Begin(Graphics); End(Graphics);
        Settings(60,60,20,3,60,0,0,1); Batch(3,2,10);
        Dimensions(1280,720,1280,720,1280,720,1,1); EndFrame();
    }
    assert(clockReads==0 && frequencyReads==0 && logCalls==0);
    for(unsigned i=0;i<119;++i) { BeginFrame(true); EndFrame(); }
    assert(logCalls==0 && frequencyReads==1);
    BeginFrame(true); EndFrame(); assert(logCalls==2+PhaseCount);
    unsigned reads=clockReads, logs=logCalls;
    BeginFrame(false); Begin(Graphics); End(Graphics); EndFrame();
    assert(clockReads==reads && logCalls==logs);
    BeginFrame(true); EndFrame(); assert(logCalls==logs && frequencyReads==1);
}
'''
    generated = OUT / 'runtime_contract.cpp'
    generated.write_text(harness)
    command[-3] = str(generated)
    command[-1] = '/Fe:' + str(OUT / 'runtime_contract.exe')
    result = subprocess.run(command, cwd=OUT, env=env, capture_output=True, text=True)
    (OUT / 'runtime-build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([str(OUT / 'runtime_contract.exe')], cwd=OUT)
    assert result.returncode == 0
    print('Actual runtime: disabled zero QPC/frequency/log calls; first report at 120 frames; reenable clean')


if __name__ == '__main__':
    main()
