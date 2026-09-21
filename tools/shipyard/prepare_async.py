"""Generate the source-locked BS v4.1.0 APIs reached by modern SoH and LUS.

No upstream files are modified. Unsupported APIs are absent, not success stubs.
"""
import hashlib
import json
from pathlib import Path

def normalized(raw):
    return raw.decode('utf-8-sig').replace('\r\n', '\n').encode('utf-8')

HELPERS = {'async/future.h': 'e26e1fc6583177e8432df0691a56e240b260d4f963513b65004c7a45dec1c801',
 'async/native.cpp': '1aed8dbeacb975c9aeac8eb9407254235515157e85ad8108c16a4b7a9369b2fe',
 'async/native.h': 'fa1f170965cf4d3b66e5e351b32f2c758b50e7bdcd31ae28075800ccf2923dcd',
 'thread-pool/native_support.h': 'e85815d392710bc0650388627df8a820312ecc1d851a33cf9798fb59f2e059c8'}

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "platform/shipyard/thread-pool/upstream/BS_thread_pool.hpp"
OUTPUT = ROOT / "scratch/async-xdk/generated"
SOURCE_HASH = "1da8bb1562433cb0759d774182d0d6fa3b87a04c26f64c6886f640445bf68efe"
SOURCE_COMMIT = "097aa718f25d44315cadb80b407144ad455ee4f9"


def main(source=SOURCE, output=OUTPUT):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not output.is_relative_to((ROOT / 'scratch/async-xdk').resolve()):
        raise ValueError('output must remain under owned scratch/async-xdk')
    for relative, expected in HELPERS.items():
        raw = normalized((ROOT / 'platform/shipyard' / relative).read_bytes())
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('helper SHA-256 mismatch: ' + relative)
    data = normalized(source.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_HASH:
        raise SystemExit(f"Refusing changed BS source: {digest}; review transformations first")
    source = data.decode().replace("\r\n", "\n")
    relative = "platform/shipyard/thread-pool/upstream/BS_thread_pool.hpp"
    chunks = []
    mappings = []

    def emit(text, line=1, label="generated support"):
        chunks.append(f'#line {line} "{relative}"\n{text}\n')
        mappings.append({"operation": label, "source_line": line})

    def extract(marker):
        if source.count(marker) != 1:
            raise ValueError(f"Ambiguous/missing marker: {marker}")
        start = source.index(marker)
        opening = source.index("{", start)
        depth = 1
        end = opening + 1
        while depth:
            if source[end] == "{": depth += 1
            elif source[end] == "}": depth -= 1
            end += 1
        if source[end:end+1] == ";": end += 1
        return source[start:end], source.count("\n", 0, start) + 1

    def lower(text):
        return (text.replace("[[nodiscard]] ", "")
                .replace("std::scoped_lock", "Shipyard::Async::lock_guard<Shipyard::Async::mutex>")
                .replace("std::unique_lock", "Shipyard::Async::unique_lock<Shipyard::Async::mutex>")
                .replace("std::future<", "Shipyard::Async::future<")
                .replace("std::promise<", "Shipyard::Async::promise<")
                .replace("std::thread::hardware_concurrency()", "Shipyard::Async::hardware_concurrency()"))

    def method(marker, transform=None):
        text, line = extract(marker)
        if transform: text = transform(text)
        emit(lower(text), line, marker.strip())

    emit("\n".join(source.splitlines()[:12]) + '''
#include "thread-pool/native_support.h"
#include <queue>
#include <vector>
#if !defined(BS_THREAD_POOL_ENABLE_PRIORITY) || !defined(BS_THREAD_POOL_ENABLE_PAUSE)
#error This audited BS subset requires priority and pause, as pinned ResourceManager does.
#endif
#if defined(BS_THREAD_POOL_DISABLE_EXCEPTION_HANDLING) || defined(BS_THREAD_POOL_ENABLE_WAIT_DEADLOCK_CHECK) || defined(BS_THREAD_POOL_ENABLE_NATIVE_HANDLES)
#error Unsupported BS configuration in the bounded XDK subset.
#endif
#define BS_THREAD_POOL_VERSION_MAJOR 4
#define BS_THREAD_POOL_VERSION_MINOR 1
#define BS_THREAD_POOL_VERSION_PATCH 0
#define BS_THREAD_POOL_PRIORITY_INPUT , const priority_t priority = 0
#define BS_THREAD_POOL_PRIORITY_OUTPUT , priority
#define BS_THREAD_POOL_PAUSED_OR_EMPTY (paused || tasks.empty())
namespace BS {
typedef std::size_t size_t;
typedef unsigned int concurrency_t;
typedef short priority_t;
namespace pr {
    const priority_t highest = 32767;
    const priority_t high = 16383;
    const priority_t normal = 0;
    const priority_t low = -16384;
    const priority_t lowest = -32768;
}
class thread_pool {
public:
''', label="bounded include/API/configuration projection")

    # VC2010 has neither delegating constructors nor in-class initializers.
    init = "paused(false), tasks_running(0), thread_count(determine_thread_count(NUM)), threads(new Shipyard::Async::joining_thread[thread_count]), waiting(false), workers_running(false)"
    for signature, number, task, line in [
        ("thread_pool()", "0", "[] {}", 301),
        ("explicit thread_pool(const concurrency_t num_threads)", "num_threads", "[] {}", 308),
        ("explicit thread_pool(const std::function<void()>& init_task)", "0", "init_task", 315),
        ("thread_pool(const concurrency_t num_threads, const std::function<void()>& init_task)", "num_threads", "init_task", 320),
    ]:
        emit(f"    {signature} : {init.replace('NUM', number)} {{ create_threads({task}); }}", line,
             "delegating constructor and member initialization lowering")

    for marker in ["    ~thread_pool()", "    [[nodiscard]] size_t get_tasks_queued()", "    [[nodiscard]] size_t get_tasks_running()",
                   "    [[nodiscard]] size_t get_tasks_total()", "    [[nodiscard]] concurrency_t get_thread_count()",
                   "    [[nodiscard]] bool is_paused()", "    void pause()", "    void purge()"]:
        method(marker)
    method("    template <typename F>\n    void detach_task", lambda text: text.replace(
        "tasks.emplace(std::forward<F>(task) BS_THREAD_POOL_PRIORITY_OUTPUT);",
        "tasks.push(pr_task(std::forward<F>(task) BS_THREAD_POOL_PRIORITY_OUTPUT));"))

    def lower_submit(text):
        text = text.replace("template <typename F, typename R = std::invoke_result_t<std::decay_t<F>>>", "template <typename F>")
        text = text.replace("std::future<R> submit_task", "std::future<typename Shipyard::Async::invoke_result<F>::type> submit_task")
        text = text.replace("        const std::shared_ptr<std::promise<R>>", "        typedef typename Shipyard::Async::invoke_result<F>::type R;\n        const typename std::decay<F>::type task_copy(std::forward<F>(task));\n        const std::shared_ptr<std::promise<R>>")
        text = text.replace("[task = std::forward<F>(task), task_promise]", "[task_copy, task_promise]")
        begin = text.index("                    if constexpr")
        end = text.index("#ifndef BS_THREAD_POOL_DISABLE_EXCEPTION_HANDLING", begin)
        text = text[:begin] + "                    Shipyard::Async::complete_promise<R>::run(task_copy, task_promise);\n" + text[end:]
        return text
    method("    template <typename F, typename R = std::invoke_result_t<std::decay_t<F>>>\n    [[nodiscard]] std::future<R> submit_task", lower_submit)
    method("    void unpause()")
    method("    void wait()\n")
    emit("private:\n    thread_pool(const thread_pool&);\n    thread_pool& operator=(const thread_pool&);", 327, "deleted special members lowered to inaccessible declarations")

    def lower_create(text):
        text = text.replace("threads[i] = std::thread(&thread_pool::worker, this, i, init_task);", "threads[i] = Shipyard::Async::make_thread(std::bind(&thread_pool::worker, this, i, init_task));")
        begin = text.index("        for (concurrency_t i")
        loop = text[begin:text.rfind("    }")]
        # Keep original worker creation; unwind already-created workers if native launch fails.
        return text[:begin] + "        try {\n" + loop + "        } catch (...) { destroy_threads(); throw; }\n    }"
    method("    void create_threads(", lower_create)
    method("    void destroy_threads()")
    method("    [[nodiscard]] static concurrency_t determine_thread_count(")

    def lower_worker(text):
        text = text.replace("while (true)", "for (;;)")
        text = text.replace("        this_thread::get_index.index = idx;", "        (void)idx; // Optional BS thread-info APIs are outside this projection.")
        text = text.replace("        this_thread::get_pool.pool = this;\n", "")
        text = text.replace("        this_thread::get_index.index = std::nullopt;\n", "")
        text = text.replace("        this_thread::get_pool.pool = std::nullopt;\n", "")
        old = """            tasks_lock.unlock();
            if (waiting && (tasks_running == 0) && BS_THREAD_POOL_PAUSED_OR_EMPTY)
                tasks_done_cv.notify_all();
            tasks_lock.lock();"""
        new = """            // Correct v4.1.0's unlocked predicate read: all shared state stays under tasks_mutex.
            if (waiting && (tasks_running == 0) && BS_THREAD_POOL_PAUSED_OR_EMPTY)
                tasks_done_cv.notify_all();"""
        if old not in text: raise ValueError("Worker synchronization correction no longer matches")
        text = text.replace(old, new)
        text = text.replace("std::remove_const_t<pr_task&>(tasks.top())", "const_cast<pr_task&>(tasks.top())")
        return text
    method("    void worker(", lower_worker)
    method("    class [[nodiscard]] pr_task", lambda text: text.replace("std::function<void()> task = {};", "std::function<void()> task;").replace("priority_t priority = 0;", "priority_t priority;"))
    emit('''
    bool paused;
    Shipyard::Async::condition_variable task_available_cv;
    Shipyard::Async::condition_variable tasks_done_cv;
    std::priority_queue<pr_task> tasks;
    size_t tasks_running;
    mutable Shipyard::Async::mutex tasks_mutex;
    concurrency_t thread_count;
    std::unique_ptr<Shipyard::Async::joining_thread[]> threads;
    bool waiting;
    bool workers_running;
};
} // namespace BS
#endif
''', 1098, "member types and constructor initialization lowering")
    generated = "\n".join(chunks)
    output.mkdir(parents=True, exist_ok=True)
    (output / "BS_thread_pool.hpp").write_text(generated, encoding="utf-8", newline="\n")
    manifest = {
        "source": relative, "source_commit": SOURCE_COMMIT, "source_sha256": digest,
        "helper_sha256": HELPERS,
        "generator_sha256": hashlib.sha256(normalized(Path(__file__).read_bytes())).hexdigest(),
        "generated_sha256": hashlib.sha256(generated.encode()).hexdigest(),
        "projection": mappings,
        "semantic_corrections": ["worker completion predicate remains under tasks_mutex", "failed worker creation signals stop and joins created workers before rethrow"],
        "unsupported": ["reset", "pool timed waits (future millisecond waits are supported)", "multi_future", "block/loop/sequence helpers", "this_thread optional TLS queries", "native handle/id queries", "wait deadlock-check option"],
    }
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    main(args.source, args.output)
    print('Generated owned BS v4.1.0 async projection')
