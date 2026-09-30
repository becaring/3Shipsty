"""Execute the actual projected Context destructor when configuration persistence fails."""
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from prepare_context import prepare, OUT
from prepare_archives import stable
from cpp_ast import PARSER, walk


def main():
    prepare()
    source = (OUT / 'generated/src/ship/Context.cpp').read_bytes()
    matches = [node.text.decode() for node in walk(PARSER.parse(source).root_node)
               if node.type == 'function_definition' and
               node.child_by_field_name('declarator').text.decode().startswith('Context::~Context(')]
    assert len(matches) == 1
    folder = OUT / 'host-shutdown'
    folder.mkdir(parents=True, exist_ok=True)
    fixture = r"""
#include <memory>
#include <stdexcept>
#include <cstdio>
#include <cstdlib>
#include <exception>
static int saved, destroyed, stopped, reported, windowSaved;
static bool failSave=true;
#define SPDLOG_TRACE(...) ((void)0)
namespace Shipyard { namespace Platform {
void RecordStartupFailure(const char*) { ++reported; }
}}
namespace spdlog { void shutdown(){++stopped;} }
struct Config {
    void Save(){++saved;if(failSave)throw std::runtime_error("disk full");}
    ~Config(){++destroyed;}
};
struct Window { void SaveWindowToConfig(){++windowSaved;} };
class Context {
public:
    std::shared_ptr<int> mAudio,mConsole,mCrashHandler,mControlDeck,mResourceManager,mConsoleVariables;
    std::shared_ptr<Window> mWindow;
    std::shared_ptr<Config> mConfig;
    Context():mWindow(new Window),mConfig(new Config){}
    std::shared_ptr<Window> GetWindow(){return mWindow;}
    std::shared_ptr<Config> GetConfig(){return mConfig;}
    ~Context();
};
""" + matches[0] + r"""
int main(){
    // A terminate handler makes the pre-fix failure deterministic without a crash dialog.
    std::set_terminate([](){std::fprintf(stderr,"destructor escaped Save failure\n");std::_Exit(86);});
    {std::shared_ptr<Context> context(new Context);}
    if(saved!=1 || destroyed!=1 || stopped!=1 || reported!=1 || windowSaved!=1)return 1;
    try {std::shared_ptr<Context> context(new Context);throw std::runtime_error("startup failure");}
    catch(const std::runtime_error&){}
    if(saved!=2 || destroyed!=2 || stopped!=2 || reported!=2)return 2;
    failSave=false;
    {std::shared_ptr<Context> context(new Context);}
    if(saved!=3 || destroyed!=3 || stopped!=3 || reported!=2)return 3;
    std::puts("Actual Context destructor preserves cleanup after config-save failure, including unwinding");
}
"""
    stable(folder / 'contract.cpp', fixture)
    helper = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler, environment = helper['host_environment']()
    helper['invoke']([compiler, '/nologo', '/std:c++20', '/EHsc', '/MD',
                      folder / 'contract.cpp', '/Fo:' + str(folder) + '/',
                      '/Fe:' + str(folder / 'contract.exe')], folder, 'build', environment)
    result = helper['invoke']([folder / 'contract.exe'], folder, 'run')
    print(result['stdout'])


if __name__ == '__main__':
    main()
