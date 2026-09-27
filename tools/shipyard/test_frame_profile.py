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
#include <algorithm>
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
bool tri2CVarOn=false;
unsigned tri2CVarReads=0;
bool vtxCVarOn=false;
unsigned vtxCVarReads=0;
int CVarGetInteger(const char* name,int fallback) {
    if (strcmp(name,"gSettings.XboxTri2PhaseProfile")==0) {
        ++tri2CVarReads;
        return tri2CVarOn ? 1 : 0;
    }
    if (strcmp(name,"gSettings.XboxVtxHashPhaseProfile")==0) {
        ++vtxCVarReads;
        return vtxCVarOn ? 1 : 0;
    }
    return fallback;
}
namespace Fast { namespace ShipyardXenos {
struct TilingGuardTrialStats {
unsigned beginCapacityRejected,candidates,continued,ineligibleFallbacks,oversizeFallbacks;
unsigned capacityFallbacks,cursorFallbacks,spaceFallbacks,postQueries,postFallbacks;
unsigned postCapacityChanges,postCursorRegressions,maxDrawBytes,maxUsed;
uint64_t totalDrawBytes;
};
struct Tile1PredicationTrialCounters {
unsigned candidates,eligible,applied,targetRejected,viewportRejected,geometryRejected;
};
struct NativeTimingCounters {
uint64_t drawTicks,uploadTicks,framebufferSetupTicks,framebufferResolveTicks,framebufferClearTicks,depthReadTicks,depthLockTicks,uploadBytes,frequency;
uint64_t tilingSpaceQueryTicks;
unsigned tilingSpaceQueryCalls;
unsigned drawCalls,uploadCalls,framebufferSetupCalls,framebufferResolveCalls,framebufferClearCalls,depthReadCalls,depthLockCalls,depthSamples;
unsigned depthBusyCalls,depthIdleCalls,depthBusy1080Calls,depthIdle1080Calls,preparationRebuilt,preparationReused;
unsigned activeWidth,activeHeight,activeSamples,activeTiles,presentationWidth,presentationHeight,buffer2Frames,presentationInterval;
};
struct NativeCounters {
unsigned samplerAttempted,samplerWritten,samplerSuppressed,constantsAttempted,constantsWritten,constantsSuppressed;
unsigned bindingAttempted,bindingWritten,bindingSuppressed,uploadRequests,uploadReused,uploadSavedBytes,clears,restoresAvoided,depthRestoresAvoided;
unsigned depthResolves,depthResolvesSkipped,earlyDepthFences,tilingDrawRestarts,tilingPeakBytes;
unsigned tiling1080Batches,tiling1080Tile1Batches,tiling1080Vertices,tiling1080Tile1Vertices;
unsigned tiling1080OversizeBatches;
unsigned ringSameSegmentDraws,ringAmbiguousDraws,ringSegmentChangedDraws,ringMaxSameSegmentBytes;
uint64_t ringSameSegmentBytes,ringSameSegmentEstimatedBytes;
struct { unsigned brackets,guardFinishes,normalFinishes,querySamples,capacityChanges;
unsigned usedRegressions;
unsigned maxUsed[4],minRemaining[4],phaseSamples[4],maxSetupBytes,maxFinishBytes; } tilingSpace;
TilingGuardTrialStats tilingGuardTrial;
Tile1PredicationTrialCounters tile1PredicationTrial;
unsigned presentationColorResolvesSkipped,presentationColorDiscardBlocked;
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
    PipelinePreparationSample disabledPrep;
    BeginPipelinePreparation(disabledPrep);
    AdvancePipelinePreparation(disabledPrep,PipelineGeometrySampler);
    EnterPipelineTextureImport(disabledPrep);
    ExitPipelineTextureImport(disabledPrep);
    EndPipelinePreparation(disabledPrep);
    assert(clockReads==0 && pipelinePrep.calls==0 && pipelinePrep.samples==0);
    TextureHashSample disabledHash;
    BeginTextureHash(disabledHash);
    AdvanceTextureHash(disabledHash,TextureHashOwningCache);
    EndTextureHash(disabledHash);
    assert(clockReads==0 && textureHash.calls==0 && textureHash.samples==0);
    Tri2Sample disabledTri2;
    BeginTri2(disabledTri2);
    AdvanceTri2(disabledTri2,Tri2Materialize);
    EndTri2(disabledTri2);
    assert(clockReads==0 && tri2.calls==0 && tri2.samples==0 && tri2CVarReads==0);
    VtxHashSample disabledVtx;
    BeginVtxHash(disabledVtx);
    AdvanceVtxHash(disabledVtx,VtxHashLookup);
    EndVtxHash(disabledVtx);
    BeginVtxTransform(disabledVtx,3);
    EnterVtxTransformLoop(&disabledVtx);
    EndVtxTransform(disabledVtx,false);
    assert(clockReads==0 && vtxHash.calls==0 && vtxHash.samples==0 && vtxCVarReads==0);
    assert(contextSearch.attempts==0 && contextSearch.slots==0);
    Shipyard_FrameProfileGameUpdateBegin();
    Shipyard_FrameProfilePlayUpdateBegin(); Shipyard_FrameProfilePlayUpdateEnd();
    Shipyard_FrameProfilePlayDrawRecordBegin(); Shipyard_FrameProfilePlayDrawRecordEnd();
    Shipyard_FrameProfileGameStateDrawBegin(); Shipyard_FrameProfileGameStateDrawEnd();
    Begin(GuiStartFrame); End(GuiStartFrame);
    Begin(GuiDrawMenu); End(GuiDrawMenu);
    Begin(GuiViewport); End(GuiViewport);
    Shipyard_FrameProfileDustDraw(0,0,0,0,0,0,1,0);
    Shipyard_FrameProfileGameUpdateEnd();
    assert(dust.draws==0 && clockReads==0);
    assert(Fast::ShipyardXenos::captures==0 && Fast::ShipyardXenos::timingTransitions==0);
    for(unsigned i=0;i<119;++i) { BeginFrame(true); Begin(Interpreter); End(Interpreter); EndFrame(); }
    assert(renderCpu.samples==119 && renderCpu.ticks==119000 && renderCpu.processorMask==1);
    assert(tri2CVarReads==1 && !tri2ProfileEnabled);
    assert(vtxCVarReads==1 && !vtxHashProfileEnabled);
    assert(!BeginResourceWait());
    Shipyard_FrameProfileGameUpdateBegin();
    Shipyard_FrameProfilePlayUpdateBegin(); Shipyard_FrameProfilePlayUpdateEnd();
    Shipyard_FrameProfilePlayDrawRecordBegin(); Shipyard_FrameProfilePlayDrawRecordEnd();
    Shipyard_FrameProfileGameStateDrawBegin(); Shipyard_FrameProfileGameStateDrawEnd();
    Shipyard_FrameProfileGameUpdateEnd();
    Begin(GuiStartFrame); End(GuiStartFrame);
    Begin(GuiDrawMenu); End(GuiDrawMenu);
    Begin(GuiViewport); End(GuiViewport);
    assert(accumulator.phases[PlayUpdate].calls==1);
    assert(accumulator.phases[PlayDrawRecord].calls==1);
    assert(accumulator.phases[GameStateDraw].calls==1);
    assert(accumulator.phases[GuiStartFrame].calls==1);
    assert(accumulator.phases[GuiDrawMenu].calls==1);
    assert(accumulator.phases[GuiViewport].calls==1);
    Begin(Interpreter);
    unsigned tri2OffClock=clockReads;
    BeginTri2(disabledTri2);
    EndTri2(disabledTri2);
    assert(tri2.calls==0 && tri2.samples==0 && clockReads==tri2OffClock);
    BeginVtxHash(disabledVtx);
    EndVtxHash(disabledVtx);
    assert(vtxHash.calls==0 && vtxHash.samples==0 && clockReads==tri2OffClock);
    unsigned waits=accumulator.phases[ResourceWait].calls;
    std::thread worker([](){ assert(!BeginResourceWait()); }); worker.join();
    std::thread lookupWorker([](){ ResourceLookupScope lookup(true); lookup.Probe(); lookup.Resolved(); }); lookupWorker.join();
    std::thread hashWorker([](){ TextureHashSample sample; BeginTextureHash(sample); EndTextureHash(sample); assert(!sample.sampled); }); hashWorker.join();
    assert(resourceLookups.calls==0);
    unsigned lookupClockReads=clockReads;
    { ResourceLookupScope lookup(true); lookup.Probe(); lookup.Probe(); lookup.Resolved(); }
    { ResourceLookupScope lookup(false); lookup.Probe(); }
    if (CaptureResourceLookups()) { ObserveTextureHashCache(true); ObserveTextureHashCache(false); }
    if (CaptureTrianglePipeline()) { ObserveTrianglePipeline(true); ObserveTrianglePipeline(false); }
    ObserveContextSearch(2,9,7);
    ObserveContextSearch(1,4,4);
    assert(contextSearch.attempts==3 && contextSearch.slots==13 && contextSearch.maximum==7);
    assert(trianglePipeline.hits==1 && trianglePipeline.misses==1);
    assert(resourceLookups.calls==2 && resourceLookups.alternate==1 && resourceLookups.resolved==1);
    assert(resourceLookups.fallback==1 && resourceLookups.probes==3 && clockReads==lookupClockReads);
    assert(resourceLookups.textureHits==1 && resourceLookups.textureMisses==1);
    pipelineRandomState=1;
    memset(&pipelinePrep,0,sizeof(pipelinePrep));
    const unsigned prepClockBefore=clockReads;
    unsigned expectedSamples=0,state=1;
    for(unsigned i=0;i<6400;++i) {
        state^=state<<13;state^=state>>17;state^=state<<5;
        expectedSamples+=(state&63u)==0;
        PipelinePreparationSample sample;
        BeginPipelinePreparation(sample);
        AdvancePipelinePreparation(sample,PipelineGeometrySampler);
        EnterPipelineTextureImport(sample);
        ExitPipelineTextureImport(sample);
        AdvancePipelinePreparation(sample,PipelineShaderTransitions);
        AdvancePipelinePreparation(sample,PipelineFinalCapture);
        EndPipelinePreparation(sample);
    }
    assert(expectedSamples>50 && expectedSamples<150);
    assert(pipelinePrep.calls==6400 && pipelinePrep.samples==expectedSamples);
    assert(clockReads-prepClockBefore==expectedSamples*7);
    assert(pipelinePrep.ticks[PipelineStateCombiner]==expectedSamples);
    assert(pipelinePrep.ticks[PipelineTextureImports]==expectedSamples);
    assert(pipelinePrep.ticks[PipelineGeometrySampler]==expectedSamples*2);
    assert(pipelinePrep.ticks[PipelineShaderTransitions]==expectedSamples);
    assert(pipelinePrep.ticks[PipelineFinalCapture]==expectedSamples);
    tri2ProfileEnabled=true;
    tri2RandomState=1;
    memset(&tri2,0,sizeof(tri2));
    const unsigned tri2ClockBefore=clockReads;
    unsigned expectedTri2Samples=0,tri2State=1;
    for(unsigned i=0;i<6400;++i) {
        tri2State^=tri2State<<13;tri2State^=tri2State>>17;tri2State^=tri2State<<5;
        expectedTri2Samples+=(tri2State&63u)==0;
        Tri2Sample sample;
        BeginTri2(sample);
        AdvanceTri2(sample,Tri2Materialize);
        AdvanceTri2(sample,Tri2Pipeline);
        AdvanceTri2(sample,Tri2Pack);
        AdvanceTri2(sample,Tri2Flush);
        AdvanceTri2(sample,Tri2Pack);
        AdvanceTri2(sample,Tri2Cull);
        EndTri2(sample);
    }
    assert(expectedTri2Samples>50 && expectedTri2Samples<150);
    assert(tri2.calls==6400 && tri2.samples==expectedTri2Samples);
    assert(clockReads-tri2ClockBefore==expectedTri2Samples*8);
    assert(tri2.ticks[Tri2Cull]==expectedTri2Samples*2);
    assert(tri2.ticks[Tri2Materialize]==expectedTri2Samples);
    assert(tri2.ticks[Tri2Pipeline]==expectedTri2Samples);
    assert(tri2.ticks[Tri2Pack]==expectedTri2Samples*2);
    assert(tri2.ticks[Tri2Flush]==expectedTri2Samples);
    vtxHashProfileEnabled=true;
    vtxHashRandomState=1;
    memset(&vtxHash,0,sizeof(vtxHash));
    const unsigned vtxClockBefore=clockReads;
    unsigned expectedVtxSamples=0,vtxState=1;
    for(unsigned i=0;i<6400;++i) {
        vtxState^=vtxState<<13;vtxState^=vtxState>>17;vtxState^=vtxState<<5;
        expectedVtxSamples+=(vtxState&63u)==0;
        VtxHashSample sample;
        BeginVtxHash(sample);
        if (sample.sampled) {
            sample.route=VtxHashPointer;
            sample.deferred=true;
            sample.vmx=true;
        }
        AdvanceVtxHash(sample,VtxHashLookup);
        AdvanceVtxHash(sample,VtxHashDeferred);
        AdvanceVtxHash(sample,VtxHashTransform);
        BeginVtxTransform(sample,3);
        if (sample.sampled) EnterVtxTransformLoop(&sample);
        EndVtxTransform(sample,true);
        AdvanceVtxHash(sample,VtxHashInsert);
        AdvanceVtxHash(sample,VtxHashFinish);
        EndVtxHash(sample);
    }
    assert(vtxHash.calls==6400 && vtxHash.samples==expectedVtxSamples);
    assert(clockReads-vtxClockBefore==expectedVtxSamples*10);
    assert(vtxHash.routes[VtxHashPointer]==expectedVtxSamples);
    assert(vtxHash.deferred==expectedVtxSamples && vtxHash.vmx==expectedVtxSamples);
    assert(vtxHash.vmxAttempts==expectedVtxSamples && vtxHash.vmxAccepted==expectedVtxSamples);
    assert(vtxHash.vmxVertices==expectedVtxSamples*3);
    assert(vtxHash.vmxSetupTicks==expectedVtxSamples);
    assert(vtxHash.vmxLoopTicks==expectedVtxSamples);
    for(unsigned i=0;i<VtxHashPhaseCount;++i)
        assert(vtxHash.ticks[i]==expectedVtxSamples*(i==VtxHashTransform ? 4 : 1));
    VtxHashSample rejected = {};
    rejected.sampled=true;
    const unsigned rejectedClockBefore=clockReads;
    BeginVtxTransform(rejected,2);
    EnterVtxTransformLoop(&rejected);
    EndVtxTransform(rejected,true);
    BeginVtxTransform(rejected,5);
    EndVtxTransform(rejected,false);
    assert(clockReads-rejectedClockBefore==5 && rejected.vmxAttempts==2);
    assert(rejected.vmxAccepted==1 && rejected.vmxVertices==2);
    assert(rejected.vmxSetupTicks==2 && rejected.vmxLoopTicks==1);
    textureHashRandomState=1;
    memset(&textureHash,0,sizeof(textureHash));
    const unsigned hashClockBefore=clockReads;
    unsigned expectedHashSamples=0,hashState=1;
    for(unsigned i=0;i<6400;++i) {
        hashState^=hashState<<13;hashState^=hashState>>17;hashState^=hashState<<5;
        expectedHashSamples+=(hashState&63u)==0;
        TextureHashSample sample;
        BeginTextureHash(sample,TextureHashOwningCache);
        AdvanceTextureHash(sample,TextureHashMapLookup);
        AdvanceTextureHash(sample,TextureHashFinal);
        AdvanceTextureHash(sample,TextureHashLoader);
        AdvanceTextureHash(sample,TextureHashFinal);
        EndTextureHash(sample);
    }
    assert(expectedHashSamples>50 && expectedHashSamples<150);
    assert(textureHash.calls==6400 && textureHash.samples==expectedHashSamples);
    assert(clockReads-hashClockBefore==expectedHashSamples*6);
    assert(textureHash.ticks[TextureHashMapLookup]==expectedHashSamples);
    assert(textureHash.ticks[TextureHashOwningCache]==expectedHashSamples);
    assert(textureHash.ticks[TextureHashLoader]==expectedHashSamples);
    assert(textureHash.ticks[TextureHashFinal]==expectedHashSamples*2);
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
    BeginFrame(true); EndFrame(); assert(logCalls==51+PhaseCount);
    assert(dust.draws==0 && dust.updatesWithDust==0);
    assert(trianglePipeline.hits==0 && trianglePipeline.misses==0);
    assert(contextSearch.attempts==0 && contextSearch.slots==0 && contextSearch.maximum==0);
    assert(pipelinePrep.calls==0 && pipelinePrep.samples==0);
    assert(tri2.calls==0 && tri2.samples==0);
    assert(vtxHash.calls==0 && vtxHash.samples==0);
    assert(textureHash.calls==0 && textureHash.samples==0);
    assert(resourceLookups.calls==0 && resourceLookups.probes==0);
    assert(resourceLookups.textureHits==0 && resourceLookups.textureMisses==0);
    assert(workerJobs==0 && workerProcessorMask==0);
    unsigned reads=clockReads, logs=logCalls;
    tri2CVarOn=true;
    vtxCVarOn=true;
    BeginFrame(false); Begin(Graphics); End(Graphics); EndFrame();
    assert(clockReads==reads && logCalls==logs);
    BeginFrame(true); EndFrame(); assert(logCalls==logs && frequencyReads==1);
    assert(tri2ProfileEnabled && tri2CVarReads==2);
    assert(vtxHashProfileEnabled && vtxCVarReads==2);
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
