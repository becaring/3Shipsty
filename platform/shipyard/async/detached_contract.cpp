#include "async/detached.h"
#include "async/native.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <cstdlib>
#ifdef TEST_UPSTREAM
#include <thread>
#endif
static void launch(const std::function<void()>& call) {
#ifdef TEST_UPSTREAM
    std::thread worker(call); worker.detach();
#else
    Shipyard::Async::launch_detached(call);
#endif
}
struct Owned {
    HANDLE destroyed;
    explicit Owned(HANDLE event):destroyed(event){}
    ~Owned(){SetEvent(destroyed);}
};
static void terminate_worker(){std::_Exit(73);}
int main(int argc,char** argv){
    if(argc==2 && strcmp(argv[1],"--throws")==0){
        // MSVC's terminate handler is per-thread; install it in the worker.
        launch([](){std::set_terminate(terminate_worker);throw 42;});Sleep(10000);return 1;
    }
    HANDLE release=CreateEvent(NULL,TRUE,FALSE,NULL);
    HANDLE entered=CreateEvent(NULL,TRUE,FALSE,NULL);
    HANDLE destroyed=CreateEvent(NULL,TRUE,FALSE,NULL);
    assert(release&&entered&&destroyed);
    std::shared_ptr<Owned> owned(new Owned(destroyed));
    std::weak_ptr<Owned> weak=owned;
    DWORD calling=GetCurrentThreadId();
    launch([owned,release,entered,calling](){
        assert(GetCurrentThreadId()!=calling);SetEvent(entered);
        assert(WaitForSingleObject(release,10000)==WAIT_OBJECT_0);
    });
    owned.reset();
    assert(WaitForSingleObject(entered,10000)==WAIT_OBJECT_0);
    assert(!weak.expired()&&WaitForSingleObject(destroyed,0)==WAIT_TIMEOUT);
    SetEvent(release);
    assert(WaitForSingleObject(destroyed,10000)==WAIT_OBJECT_0);
    assert(weak.expired());
    CloseHandle(release);CloseHandle(entered);CloseHandle(destroyed);
    // Exercise workers that can finish before the launching call returns.
    for(int i=0;i<1000;++i){
        HANDLE done=CreateEvent(NULL,TRUE,FALSE,NULL);assert(done);
        {std::shared_ptr<Owned> fast(new Owned(done));launch([fast](){});}
        assert(WaitForSingleObject(done,10000)==WAIT_OBJECT_0);CloseHandle(done);
    }
    puts("Detached execution, captured lifetime, 1000 fast completions pass");
}
