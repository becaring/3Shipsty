#include "platform/shipyard/async/native.h"
#include <spdlog/details/mpmc_blocking_q.h>
#include <cassert>
#include <cstdio>
#include <memory>

typedef spdlog::details::mpmc_blocking_queue<int> Queue;
struct Producer {
    Queue* queue;
    Shipyard::Async::manual_reset_event started,done;
    int start,count;
    Producer(Queue* q,int s,int n):queue(q),started(false),done(false),start(s),count(n){}
    static void run(void* p){
        Producer* self=static_cast<Producer*>(p);self->started.set();
        for(int i=0;i<self->count;++i){int value=self->start+i;self->queue->enqueue(std::move(value));}
        self->done.set();
    }
};
int main(){
    Queue bounded(2);int one=1,two=2,three=3,value=0;
    bounded.enqueue(std::move(one));bounded.enqueue(std::move(two));
    bounded.enqueue_nowait(std::move(three));assert(bounded.overrun_counter()==1);
    bounded.dequeue(value);assert(value==2);bounded.dequeue(value);assert(value==3);
    bounded.reset_overrun_counter();assert(bounded.overrun_counter()==0);
    one=1;two=2;three=3;bounded.enqueue(std::move(one));bounded.enqueue(std::move(two));
    bounded.enqueue_if_have_room(std::move(three));assert(bounded.discard_counter()==1);
    bounded.dequeue(value);assert(value==1);bounded.dequeue(value);assert(value==2);
    bounded.reset_discard_counter();assert(bounded.discard_counter()==0);
    Queue queue(8192);for(int i=0;i<8192;++i){int n=i;queue.enqueue(std::move(n));}
    Producer blocked(&queue,8192,1);Shipyard::Async::joining_thread worker(&Producer::run,&blocked);
    blocked.started.wait();assert(!blocked.done.wait_for_ms(25));assert(queue.size()==8192);
    queue.dequeue(value);assert(value==0);blocked.done.wait();worker.join();
    for(int i=1;i<=8192;++i){queue.dequeue(value);assert(value==i);}assert(queue.size()==0);
    Producer p0(&queue,0,1000),p1(&queue,1000,1000),p2(&queue,2000,1000),p3(&queue,3000,1000);
    // Explicit declarations avoid copying synchronization primitives on XDK.
    Shipyard::Async::joining_thread a(&Producer::run,&p0),b(&Producer::run,&p1),c(&Producer::run,&p2),d(&Producer::run,&p3);
    bool seen[4000]={};for(int i=0;i<4000;++i){queue.dequeue(value);assert(value>=0&&value<4000&&!seen[value]);seen[value]=true;}
    a.join();b.join();c.join();d.join();assert(queue.size()==0);
    typedef std::shared_ptr<int> Ptr;spdlog::details::mpmc_blocking_queue<Ptr> owned(1);
    Ptr ptr(new int(42));std::weak_ptr<int> weak(ptr);owned.enqueue(std::move(ptr));assert(!weak.expired());
    Ptr result;owned.dequeue(result);assert(*result==42);result.reset();assert(weak.expired());
    puts("PASS actual spdlog queue: 8192 blocking/FIFO, overrun/discard counters, 4 producers, owned payload lifetime");
}

