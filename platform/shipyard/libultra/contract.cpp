#include "libultraship/libultra.h"
#include <cassert>
#include <cstdio>
#include <cstring>

extern "C" uintptr_t osVirtualToPhysical(void*);
static OSMesg message(uint32_t value) { OSMesg m; memset(&m,0,sizeof(m)); m.data32=value; return m; }
static uint64_t digest=UINT64_C(1469598103934665603);
static void record(uint64_t v) { digest^=v; digest*=UINT64_C(1099511628211); }
int main() {
    OSMesg storage[17]; OSMesgQueue queue;
    uint32_t rng=0x329ab45;
    unsigned operations=0;
    for (int capacity=1;capacity<=16;++capacity) {
        memset(storage,0,sizeof(storage)); memset(&queue,0,sizeof(queue));
        osCreateMesgQueue(&queue,storage,capacity);
        assert(queue.validCount==0&&queue.first==0&&queue.msgCount==capacity&&queue.msg==storage);
        // Upstream deliberately preserved: jam on an empty queue rejects.
        assert(osJamMesg(&queue,message(1),OS_MESG_NOBLOCK)==-1);
        for (int i=0;i<4096;++i) {
            rng=rng*1664525+1013904223; int action=(rng>>16)%4;
            OSMesg value=message((rng&0xffff)+1),received=message(0);
            int result;
            if(action==0)result=osSendMesg(&queue,value,OS_MESG_NOBLOCK);
            else if(action==1&&queue.validCount<queue.msgCount) result=osJamMesg(&queue,value,OS_MESG_BLOCK);
            else result=osRecvMesg(&queue,action==3?NULL:&received,OS_MESG_BLOCK);
            record(result);record(received.data32);record(queue.first);record(queue.validCount);
            for(int j=0;j<capacity;++j)record(storage[j].data32);
            ++operations;
        }
    }
    osCreateMesgQueue(&queue,storage,2);
    osSendMesg(&queue,message(1),0);osSendMesg(&queue,message(2),0);
    // Existing upstream jam condition also permits full queues; do not repair
    // its semantics as an undocumented side effect of platform projection.
    assert(osJamMesg(&queue,message(3),0)==0&&queue.validCount==3);
    osSetEventMesg(OS_EVENT_VI,&queue,message(123));
    assert(__osEventStateTab[OS_EVENT_VI].queue==&queue&&__osEventStateTab[OS_EVENT_VI].msg.data32==123);
    char input[512],output[512];for(int i=0;i<512;++i)input[i]=(char)(i*37);
    memset(output,0,sizeof(output));
    assert(osPiStartDma(NULL,0,0,(uintptr_t)input,output,sizeof(output),NULL)==0);
    assert(memcmp(input,output,sizeof(input))==0);
    assert(osVirtualToPhysical(input)==(uintptr_t)input);
    for(int i=0;i<512;++i)record((unsigned char)output[i]);
    osWritebackDCacheAll();osInvalICache(input,512);osWritebackDCache(input,512);osInvalDCache(input,512);
    printf("%u queue operations; DMA bytes=512; digest=%llu\n",operations,(unsigned long long)digest);
}
