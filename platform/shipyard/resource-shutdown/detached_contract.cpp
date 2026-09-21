#include "async/native.h"
#include "async/detached.h"
#include <cassert>
#include <memory>
#include <cstdio>
#include <exception>
#include <cstdlib>
#include <cstring>
using namespace Shipyard::Async;
struct Events {
    manual_reset_event entered,release,destroyed,destructorEntered,destructorRelease;
    volatile LONG count;
    Events():count(0){}
};
struct Capture {
    Events* state;
    bool blockDestructor;
    Capture(Events* s,bool block):state(s),blockDestructor(block){}
    ~Capture(){
        if(blockDestructor){state->destructorEntered.set();state->destructorRelease.wait();}
        InterlockedIncrement(&state->count);state->destroyed.set();
    }
};
struct Waiting {
    manual_reset_event entered,done;
    static void Run(void* p){Waiting* self=static_cast<Waiting*>(p);self->entered.set();wait_for_detached();self->done.set();}
};
static volatile LONG failCreate;
HANDLE WINAPI ContractCreateThread(LPSECURITY_ATTRIBUTES attributes,SIZE_T size,LPTHREAD_START_ROUTINE entry,LPVOID arg,DWORD flags,LPDWORD id){
    if(InterlockedExchange(&failCreate,0)){SetLastError(ERROR_NOT_ENOUGH_MEMORY);return NULL;}
    return CreateThread(attributes,size,entry,arg,flags,id);
}
static void Terminate(){std::_Exit(73);}
struct CopyFailure {
    static bool fail;
    CopyFailure(){}
    CopyFailure(const CopyFailure&){if(fail)throw 123;}
    void operator()()const{}
};
bool CopyFailure::fail=false;
int main(int argc,char** argv){
    if(argc==2 && !strcmp(argv[1],"--throws")){
        launch_detached([](){std::set_terminate(Terminate);throw 42;});Sleep(10000);return 1;
    }
    wait_for_detached();
    Events state;
    std::shared_ptr<Capture> capture(new Capture(&state,true));
    launch_detached([capture,&state](){state.entered.set();state.release.wait();});
    capture.reset();state.entered.wait();
    Waiting waiters[2];joining_thread waits[2];
    for(unsigned i=0;i<2;++i){waits[i]=joining_thread(Waiting::Run,&waiters[i]);waiters[i].entered.wait();}
    assert(!waiters[0].done.wait_for_ms(20));
    state.release.set();state.destructorEntered.wait();
    assert(!waiters[1].done.wait_for_ms(20)); // Callable return is not completion.
    state.destructorRelease.set();
    for(unsigned i=0;i<2;++i){waits[i].join();assert(waiters[i].done.wait_for_ms(0));}
    assert(state.count==1 && state.destroyed.wait_for_ms(0));
    for(unsigned i=0;i<1000;++i){
        Events fast;{std::shared_ptr<Capture> value(new Capture(&fast,false));launch_detached([value](){});}
        wait_for_detached();assert(fast.count==1 && fast.destroyed.wait_for_ms(0));
    }
    Events failed;
    {std::shared_ptr<Capture> value(new Capture(&failed,false));
     InterlockedExchange(&failCreate,1);bool caught=false;
     try{launch_detached([value](){});}catch(const native_error& e){caught=e.native_code()==ERROR_NOT_ENOUGH_MEMORY;}
     assert(caught);}
    wait_for_detached();assert(failed.count==1);
    std::function<void()> throwsCopy((CopyFailure()));CopyFailure::fail=true;bool caught=false;
    try{launch_detached(throwsCopy);}catch(int value){caught=value==123;}assert(caught);CopyFailure::fail=false;
    wait_for_detached();
    // A worker may enqueue child work before releasing its own capture.
    Events parent,child;
    {std::shared_ptr<Capture> value(new Capture(&parent,false));
     launch_detached([value,&child](){std::shared_ptr<Capture> nested(new Capture(&child,false));launch_detached([nested](){});});}
    wait_for_detached();assert(parent.count==1 && child.count==1);
    puts("PASS detached drain: 2 waiters, blocked capture destructor, 1000 immediate completions, creation/copy failure, child work");
}
