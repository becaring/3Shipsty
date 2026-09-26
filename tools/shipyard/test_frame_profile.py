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
#include "application/command_profile.h"
#include <cassert>
#include <cstdarg>
#include <thread>
struct FILETIME { unsigned dwLowDateTime,dwHighDateTime; };
unsigned cpuReads=0, processor=0;
bool failCpu=false;
typedef long LONG;
LONG InterlockedExchange(volatile LONG* p,LONG value){LONG old=*p;*p=value;return old;}
LONG InterlockedCompareExchange(volatile LONG* p,LONG value,LONG expected){LONG old=*p;if(old==expected)*p=value;return old;}
LONG InterlockedOr(volatile LONG* p,LONG value){LONG old=*p;*p=old|value;return old;}
LONG InterlockedIncrement(volatile LONG* p){LONG value=*p+1;*p=value;return value;}
void* GetCurrentThread(){return 0;}
unsigned GetCurrentThreadId(){return 42;}
unsigned GetCurrentProcessorNumber(){return processor;}
unsigned GetLastError(){return 5;}
bool GetThreadTimes(void*,FILETIME*,FILETIME*,FILETIME* kernel,FILETIME* user){
    ++cpuReads;
    if(failCpu)return false;
    kernel->dwHighDateTime=user->dwHighDateTime=0;
    kernel->dwLowDateTime=cpuReads*1000;user->dwLowDateTime=0;
    return true;
}
struct LARGE_INTEGER { long long QuadPart; };
unsigned clockReads=0, frequencyReads=0, logCalls=0;
void QueryPerformanceCounter(LARGE_INTEGER* v) { v->QuadPart=++clockReads; }
void QueryPerformanceFrequency(LARGE_INTEGER* v) { ++frequencyReads; v->QuadPart=1000; }
void Shipyard_Log(const char*, ...) { ++logCalls; }
namespace Fast { namespace ShipyardXenos {
struct NativeTimingCounters {
uint64_t drawTicks,uploadTicks,framebufferSetupTicks,framebufferResolveTicks,framebufferClearTicks,depthReadTicks,depthLockTicks,uploadBytes,frequency;
unsigned drawCalls,uploadCalls,framebufferSetupCalls,framebufferResolveCalls,framebufferClearCalls,depthReadCalls,depthLockCalls,depthSamples,preparationRebuilt,preparationReused;
unsigned activeWidth,activeHeight,activeSamples,activeTiles,presentationWidth,presentationHeight,buffer2Frames,presentationInterval;
};
struct NativeCounters {
unsigned samplerAttempted,samplerWritten,samplerSuppressed,constantsAttempted,constantsWritten,constantsSuppressed;
unsigned bindingAttempted,bindingWritten,bindingSuppressed,uploadRequests,uploadReused,uploadSavedBytes,clears,restoresAvoided,depthRestoresAvoided;
unsigned depthResolves,depthResolvesSkipped,earlyDepthFences,tilingDrawRestarts,tilingPeakBytes;
};
unsigned timingTransitions=0,captures=0;
void SetTimingEnabled(bool) { ++timingTransitions; }
void CaptureAndResetCounters(NativeCounters* p) { ++captures; memset(p,0,sizeof(*p)); }
void CaptureAndResetTimingCounters(NativeTimingCounters* p) { ++captures; memset(p,0,sizeof(*p)); }
}}
namespace ModernFrameProfile {
''' + runtime + '''
int main() {
    using namespace ModernFrameProfile;
    for(unsigned i=0;i<240;++i) {
        BeginFrame(false); Begin(Graphics); End(Graphics); Begin(Interpreter); End(Interpreter);
        Settings(60,60,20,3,60,0,0,1); Batch(3,2,10);
        Dimensions(1280,720,1280,720,1280,720,1,1); EndFrame();
        { ResourceLookupScope lookup(true); lookup.Probe(); lookup.Resolved(); }
        if (CaptureResourceLookups()) ObserveTextureHashCache(true);
        { PhaseScope recording(RecordingRotate); }
    }
    assert(clockReads==0 && frequencyReads==0 && logCalls==0 && cpuReads==0);
    ObserveResourceWorker(); assert(workerJobs==0 && workerProcessorMask==0);
    assert(resourceLookups.calls==0);
    assert(resourceLookups.textureHits==0 && resourceLookups.textureMisses==0);
    assert(!CaptureTrianglePipeline() && trianglePipeline.hits==0 && trianglePipeline.misses==0);
    Shipyard_FrameProfileGameUpdateBegin();
    Shipyard_FrameProfileDustDraw(0,0,0,0,0,0,1,0);
    Shipyard_FrameProfileGameUpdateEnd();
    assert(dust.draws==0);
    assert(Fast::ShipyardXenos::captures==0 && Fast::ShipyardXenos::timingTransitions==0);
    for(unsigned i=0;i<119;++i) { BeginFrame(true); Begin(Interpreter); End(Interpreter); EndFrame(); }
    assert(renderCpu.samples==119 && renderCpu.ticks==119000 && renderCpu.processorMask==1);
    assert(!BeginResourceWait());
    Begin(Interpreter);
    unsigned waits=accumulator.phases[ResourceWait].calls;
    std::thread worker([](){ assert(!BeginResourceWait()); }); worker.join();
    std::thread lookupWorker([](){ ResourceLookupScope lookup(true); lookup.Probe(); lookup.Resolved(); }); lookupWorker.join();
    assert(resourceLookups.calls==0);
    unsigned lookupClockReads=clockReads;
    { ResourceLookupScope lookup(true); lookup.Probe(); lookup.Probe(); lookup.Resolved(); }
    { ResourceLookupScope lookup(false); lookup.Probe(); }
    if (CaptureResourceLookups()) { ObserveTextureHashCache(true); ObserveTextureHashCache(false); }
    if (CaptureTrianglePipeline()) { ObserveTrianglePipeline(true); ObserveTrianglePipeline(false); }
    assert(trianglePipeline.hits==1 && trianglePipeline.misses==1);
    assert(resourceLookups.calls==2 && resourceLookups.alternate==1 && resourceLookups.resolved==1);
    assert(resourceLookups.fallback==1 && resourceLookups.probes==3 && clockReads==lookupClockReads);
    assert(resourceLookups.textureHits==1 && resourceLookups.textureMisses==1);
    Shipyard_FrameProfileGameUpdateBegin();
    Shipyard_FrameProfileDustDraw(5,0,0,0,0,0,1,0);
    Shipyard_FrameProfileDustDraw(200,0,0,0,0,0,2,0);
    Shipyard_FrameProfileGameUpdateEnd();
    assert(dust.draws==2 && dust.updatesWithDust==1 && dust.maxDrawsPerUpdate==2);
    assert(dust.near100==1 && dust.near250==2 && dust.minDistanceSquared==25 && dust.maxScale==2);
    { ResourceWaitScope wait; }
    assert(accumulator.phases[ResourceWait].calls==waits+1);
    End(Interpreter);
    assert(!BeginResourceWait());
    processor=2; Begin(AudioGenerate); End(AudioGenerate);
    ObserveResourceWorker(); processor=4; ObserveResourceWorker();
    assert(workerJobs==2 && workerProcessorMask==20);
    assert(audioCpu.samples==1 && audioCpu.ticks==1000 && audioCpu.processorMask==4);
    failCpu=true; Begin(AudioGenerate); End(AudioGenerate); failCpu=false;
    assert(audioCpu.failures==1 && audioCpu.lastError==5 && audioCpu.samples==1);
    assert(logCalls==0 && frequencyReads==1);
    { PhaseScope recording(RecordingRotate); }
    assert(accumulator.phases[RecordingRotate].calls==1);
    BeginFrame(true); EndFrame(); assert(logCalls==17+PhaseCount);
    assert(dust.draws==0 && dust.updatesWithDust==0);
    assert(trianglePipeline.hits==0 && trianglePipeline.misses==0);
    assert(resourceLookups.calls==0 && resourceLookups.probes==0);
    assert(resourceLookups.textureHits==0 && resourceLookups.textureMisses==0);
    assert(workerJobs==0 && workerProcessorMask==0);
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
