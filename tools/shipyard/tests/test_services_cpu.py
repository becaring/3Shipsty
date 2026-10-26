"""Exercise extracted time service under concurrent first use."""
import argparse
from pathlib import Path
from test_backend_cpu import function, host_environment, invoke, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    code = r'''
#include <atomic>
#include <cassert>
#include <thread>
#include <vector>
typedef long LONG;
struct LARGE_INTEGER { long long QuadPart; };
std::atomic<int> frequencyQueries(0);
void QueryPerformanceCounter(LARGE_INTEGER* value){value->QuadPart=3500000;}
void QueryPerformanceFrequency(LARGE_INTEGER* value){++frequencyQueries;std::this_thread::yield();value->QuadPart=1000000;}
LONG InterlockedCompareExchange(volatile LONG* p,LONG exchange,LONG comparison){
 std::atomic_ref<LONG> target(*const_cast<LONG*>(p));
 target.compare_exchange_strong(comparison,exchange);return comparison;
}
LONG InterlockedExchange(volatile LONG* p,LONG value){return std::atomic_ref<LONG>(*const_cast<LONG*>(p)).exchange(value);}
void YieldProcessor(){std::this_thread::yield();}
'''
    code += function(source, 'double Shipyard_Time()')
    code += r'''
int main(){
 std::atomic<bool> start(false);std::vector<std::thread> threads;
 for(int i=0;i<16;++i)threads.emplace_back([&](){while(!start.load())std::this_thread::yield();
  for(int j=0;j<1000;++j)assert(Shipyard_Time()==3.5);
 });
 start=true;for(auto& thread:threads)thread.join();
 assert(frequencyQueries.load()==1);
}
'''
    folder = ROOT / 'scratch/xenon-cpu-audit/services/host'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'contract.cpp'
    path.write_text(code)
    compiler, env = host_environment()
    invoke([compiler, '/nologo', '/std:c++20', '/EHsc', path,
            '/Fo:' + str(folder) + '/', '/Fe:' + str(folder / 'contract.exe')], folder, 'build', env)
    invoke([folder / 'contract.exe'], folder, 'run')
    print('Time service publishes one frequency query across concurrent first use.')


if __name__ == '__main__':
    main()
