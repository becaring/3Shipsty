#include "ship/resource/ResourceManager.h"
#include "async/native.h"
#include <cassert>
#include <memory>
#include <cstdio>
namespace Ship {
struct ResourceShutdownFixture {
    static void Setup(ResourceManager& manager,unsigned count){manager.mThreadPool=std::make_shared<BS::thread_pool>(count);}
    static BS::thread_pool& Pool(ResourceManager& manager){return *manager.mThreadPool;}
    static Shipyard::Async::mutex& Mutex(ResourceManager& manager){return manager.mMutex;}
};
}
using namespace Shipyard::Async;
struct ResourceCapture {
    Ship::ResourceManager* manager;
    manual_reset_event *entered,*release,*finished;
    ResourceCapture(Ship::ResourceManager* m,manual_reset_event* e,manual_reset_event* r,manual_reset_event* f):manager(m),entered(e),release(r),finished(f){}
    ~ResourceCapture(){entered->set();release->wait();lock_guard<mutex> lock(Ship::ResourceShutdownFixture::Mutex(*manager));finished->set();}
};
struct Drain {
    Ship::ResourceManager* manager;bool destroy;
    manual_reset_event entered,done;
    static void Run(void* pointer){Drain* p=static_cast<Drain*>(pointer);p->entered.set();if(p->destroy)delete p->manager;else p->manager->WaitForPendingTasks();p->done.set();}
};
int main(){
    {Ship::ResourceManager uninitialized;uninitialized.WaitForPendingTasks();}
    for(unsigned destroy=0;destroy<2;++destroy){
        Ship::ResourceManager* manager=new Ship::ResourceManager;
        Ship::ResourceShutdownFixture::Setup(*manager,2);
        manual_reset_event entered,release,finished;
        {std::shared_ptr<ResourceCapture> capture(new ResourceCapture(manager,&entered,&release,&finished));
         Ship::ResourceShutdownFixture::Pool(*manager).detach_task([capture](){});}
        entered.wait();Drain drain;drain.manager=manager;drain.destroy=destroy!=0;
        joining_thread worker(Drain::Run,&drain);drain.entered.wait();assert(!drain.done.wait_for_ms(20));
        release.set();worker.join();assert(finished.wait_for_ms(0)&&drain.done.wait_for_ms(0));
        if(!destroy)delete manager;
    }
    // BS wait ordinarily treats paused queued tasks as finished. The public
    // shutdown boundary must drain those accepted jobs, not abandon captures.
    Ship::ResourceManager manager;Ship::ResourceShutdownFixture::Setup(manager,2);
    BS::thread_pool& pool=Ship::ResourceShutdownFixture::Pool(manager);pool.pause();
    volatile LONG count=0;
    for(unsigned i=0;i<1000;++i)pool.detach_task([&manager,&count](){lock_guard<mutex> lock(Ship::ResourceShutdownFixture::Mutex(manager));InterlockedIncrement(&count);});
    manager.WaitForPendingTasks();assert(count==1000 && pool.get_tasks_total()==0);
    puts("PASS real ResourceManager drain: null pool, live mutex in capture destruction, destructor barrier, 1000 paused jobs");
}
