#include "libultra/platform.h"
#include "async/native.h"
#include <cassert>
#include <cstdio>
#include <chrono>
#include <limits>

struct CallbackState { volatile LONG calls; DWORD mainThread; bool worker; };
uint32_t callback(uint32_t interval,void* context) {
    CallbackState* state=static_cast<CallbackState*>(context);
    assert(interval==2||interval==3);state->worker=GetCurrentThreadId()!=state->mainThread;
    LONG count=InterlockedIncrement(&state->calls);
    return count<4?3:0;
}
uint32_t endless(uint32_t interval,void* context) { InterlockedIncrement(static_cast<volatile LONG*>(context)); return interval; }
int main() {
    using namespace Shipyard::Libultra;
    typedef std::chrono::duration<int64_t,std::ratio<8,375000000>> Cycles;
    unsigned cases=0;
    for(int64_t value=-100000;value<100000;++value) {
        assert(NanosecondsToCycles(value)==std::chrono::duration_cast<Cycles>(std::chrono::nanoseconds(value)).count());++cases;
    }
    const int64_t limits[]={INT64_MAX,INT64_MIN,INT64_MAX-1,INT64_MIN+1};
    const int64_t expected[]={INT64_C(432345564227567615),-INT64_C(432345564227567616),INT64_C(432345564227567615),-INT64_C(432345564227567615)};
    for(int i=0;i<4;++i) {
        const int64_t v=limits[i];
        const int64_t result=NanosecondsToCycles(v);
        // Constants independently calculated with Python arbitrary integers.
        assert(result==expected[i]);++cases;
    }
    uint64_t before=NowCycles();Sleep(20);uint64_t after=NowCycles();assert(after>before);
    assert(!AddTimer(0,callback,NULL));assert(!AddTimer(1,NULL,NULL));
    CallbackState state={0,GetCurrentThreadId(),false};assert(AddTimer(2,callback,&state));
    DWORD start=GetTickCount();while(InterlockedCompareExchange(&state.calls,0,0)<4&&GetTickCount()-start<5000)Sleep(1);
    StopTimers();assert(state.calls==4&&state.worker);
    volatile LONG continuous=0;assert(AddTimer(1,endless,(void*)&continuous));
    start=GetTickCount();while(InterlockedCompareExchange(&continuous,0,0)<3&&GetTickCount()-start<5000)Sleep(1);
    StopTimers();LONG stopped=continuous;Sleep(20);assert(stopped>=3&&continuous==stopped);
    StopTimers(); // Joining and destruction are idempotent at the registry boundary.
    puts("200004 exact N64 clock conversions; real native timers repeat, change interval, cancel, stop and join");
}
