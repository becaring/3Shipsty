"""Strict pinned current-spdlog queue and core source projection for XDK."""
from pathlib import Path
import hashlib,json,argparse,re,importlib.util
ROOT=Path(__file__).resolve().parents[3];UP=ROOT/'scratch/deps/spdlog/include'
BASE=ROOT/'platform/shipyard/logging'
def digest(data):return hashlib.sha256(data).hexdigest()
def exact(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('Match failure: '+old[:120])
    return text.replace(old,new)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'scratch/logging-xdk/include');args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'scratch/logging-xdk'):raise ValueError('Output must be within scratch/logging-xdk')
    lock=json.loads((BASE/'source-lock.json').read_text());pending=[]
    for rel,sha in lock.items():
        p=UP/rel;raw=p.read_bytes()
        if digest(raw)!=sha:raise ValueError('Pinned source changed: '+rel)
        t=raw.decode().replace('\r\n','\n')
        if rel.endswith('circular_q.h'):
            t=exact(t,'#include "spdlog/common.h"','#include "'+(BASE/'native.h').as_posix()+'"')
            t=t.replace(' SPDLOG_NOEXCEPT','')
            for decl in ('size_t max_items_','typename std::vector<T>::size_type head_','typename std::vector<T>::size_type tail_','size_t overrun_counter_'):t=exact(t,'    '+decl+' = 0;','    '+decl+';',1)
            t=exact(t,'using value_type = T;','typedef T value_type;')
            t=exact(t,'circular_q() = default;','circular_q() : max_items_(0), head_(0), tail_(0), overrun_counter_(0) {}')
            t=exact(t,'v_(max_items_) {}','head_(0), tail_(0), overrun_counter_(0), v_(max_items_) {}')
            t=exact(t,'circular_q(const circular_q &) = default;','circular_q(const circular_q &other) : max_items_(other.max_items_), head_(other.head_), tail_(other.tail_), overrun_counter_(other.overrun_counter_), v_(other.v_) {}')
            t=exact(t,'circular_q &operator=(const circular_q &) = default;','circular_q &operator=(const circular_q &other) { max_items_=other.max_items_; head_=other.head_; tail_=other.tail_; overrun_counter_=other.overrun_counter_; v_=other.v_; return *this; }')
        elif rel.endswith('mpmc_blocking_q.h'):
            # The real thread_pool uses blocking dequeue; reject unneeded timed
            # consumers by omitting dequeue_for rather than silently ignoring time.
            start=t.index('#ifndef __MINGW32__');otherwise=t.index('\n#else',start);end=t.index('\n#endif',otherwise)
            t=t[:start]+t[start+len('#ifndef __MINGW32__'):otherwise]+t[end+len('\n#endif'):]
            start=t.index('    // dequeue with a timeout.');end=t.index('    // blocking dequeue without a timeout.',start);t=t[:start]+t[end:]
            for inc in ('atomic','condition_variable','mutex'):t=exact(t,'#include <'+inc+'>','')
            for name in ('mutex','unique_lock','lock_guard','condition_variable'):t=t.replace('std::'+name,'Shipyard::Logging::'+name)
            t=exact(t,'using item_type = T;','typedef T item_type;')
            t=exact(t,': q_(max_items) {}',': q_(max_items), discard_counter_(0) {}')
            t=exact(t,'++discard_counter_;','discard_counter_.increment();')
            t=exact(t,'std::atomic<size_t> discard_counter_{0};','Shipyard::Logging::logging_counter discard_counter_;')
            t=t.replace('.load(std::memory_order_relaxed)','.load()').replace('.store(0, std::memory_order_relaxed)','.store(0)')
        guard='SHIPYARD_SPDLOG_QUEUE_'+re.sub(r'\W','_',rel).upper()
        data=('#ifndef '+guard+'\n#define '+guard+'\n#line 1 "'+p.as_posix()+'"\n'+t+'\n#endif\n').encode();pending.append((rel,data,sha))
    manifest={'status':'actual current queue projection, consumed by current logger thread_pool','sources':[],'unsupported':['queue dequeue_for (not called by actual current thread_pool)']}
    for rel,data,sha in pending:
        target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        manifest['sources'].append({'path':rel,'source_sha256':sha,'output_sha256':digest(data)})
    out.mkdir(parents=True,exist_ok=True);(out/'logging-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Generated pinned current spdlog queue overlay:',out)
    spec=importlib.util.spec_from_file_location('smash360_logging_core',BASE/'generate_core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    core_out=out.parent/'core-include';texts=core.generate(core_out)
    records=[]
    for name in texts:
        original=UP/'spdlog'/name;target=core_out/'spdlog'/name
        records.append({'path':'spdlog/'+name,'source_sha256':digest(original.read_bytes()) if original.exists() else None,'output_sha256':digest(target.read_bytes())})
    report={'status':'current logger/core source projection; see README verification boundary','sources':records,
        'omitted_apis':['periodic flush/timed queue waits','variadic logger/sink factory convenience APIs','wide logging'],
        'maximum_format_arguments':39,
        'default_logger':'actual stdout_sink_mt using CRT fwrite; uncolored on Xbox',
        'native_process_id':'unavailable on Xbox; percent-P flag throws spdlog_ex instead of inventing a PID',
        'native_support_hashes':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for scope in ('logging','chrono','format') for p in sorted((BASE/(scope if scope != 'logging' else '.')).glob('*')) if p.is_file()}}
    (core_out/'logging-core-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Generated',len(texts),'current logger/core headers:',core_out)
if __name__=='__main__':main()
