#include "async/detached.h"
#include "async/native.h"
#include <memory>
#include <exception>
namespace Shipyard { namespace Async {
static DWORD WINAPI run_detached(void* context){
    std::unique_ptr<std::function<void()> > callable(static_cast<std::function<void()>*>(context));
    try{(*callable)();}catch(...){std::terminate();}
    return 0;
}
void launch_detached(const std::function<void()>& callable){
    std::unique_ptr<std::function<void()> > pending(new std::function<void()>(callable));
    // A worker can complete before CreateThread returns: transfer first.
    std::function<void()>* raw=pending.release();
    HANDLE thread=CreateThread(NULL,128*1024,run_detached,raw,0,NULL);
    if(!thread){DWORD error=GetLastError();delete raw;throw native_error("CreateThread",error);}
    // A valid, freshly created handle must close. As with an immediately
    // detached std::thread whose detach fails, do not lose a joinable owner.
    if(!CloseHandle(thread))std::terminate();
}
} }
