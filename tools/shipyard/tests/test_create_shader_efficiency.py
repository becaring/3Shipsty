"""Exercise the selected CreateShader body, including its failed-load cost."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from cpp_ast import PARSER, walk
from prepare_fast3d import OUT, prepare


def main():
    prepare()
    source = (OUT / 'generated/src/fast/interpreter.cpp').read_text()
    functions = [n.text.decode() for n in walk(PARSER.parse(source.encode()).root_node)
                 if n.type == 'function_definition' and
                 n.child_by_field_name('declarator').text.decode().startswith('Interpreter::CreateShader(')]
    assert len(functions) == 1
    folder = OUT / 'host-create-shader-efficiency'
    folder.mkdir(exist_ok=True)
    code = r'''#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <new>
#include <string>
#include <vector>
static int allocations = 0;
void* operator new(size_t size) { ++allocations; if (void* p = std::malloc(size)) return p; throw std::bad_alloc(); }
void operator delete(void* p) noexcept { std::free(p); }
namespace Ship {
enum class Endianness { Native };
struct ResourceInitData { std::string Path; bool IsCustom; Endianness ByteOrder; };
struct Shader { bool IsLoaded; std::shared_ptr<std::vector<char>> Buffer; };
struct ArchiveManager {
    std::shared_ptr<Shader> response;
    int calls = 0;
    std::shared_ptr<Shader> LoadFile(const std::string&) { ++calls; return response; }
};
struct ResourceManager { ArchiveManager archive; ArchiveManager* GetArchiveManager() { return &archive; } };
struct Context {
    ResourceManager resources;
    static Context* GetInstance() { static Context instance; return &instance; }
    ResourceManager* GetResourceManager() { return &resources; }
};
}
class Interpreter {
public:
    std::vector<std::string> shader_ids;
    int16_t CreateShader(const std::string& path);
};
''' + functions[0] + r'''
int main() {
    Interpreter interpreter;
    const std::string path("missing");
    Ship::ArchiveManager& archive = Ship::Context::GetInstance()->resources.archive;
    int before = allocations;
    assert(interpreter.CreateShader(path) == -1);
    assert(archive.calls == 1 && interpreter.shader_ids.empty());
    assert(allocations == before && "failed resource lookup must not allocate discarded init data");
    auto shader = std::make_shared<Ship::Shader>();
    shader->IsLoaded = true;
    shader->Buffer = std::make_shared<std::vector<char>>(4, 0);
    (*shader->Buffer)[0] = 'f'; (*shader->Buffer)[1] = 'x';
    archive.response = shader;
    assert(interpreter.CreateShader(path) == 0);
    assert(interpreter.shader_ids.size() == 1 && interpreter.shader_ids[0] == "fx");
    assert(archive.calls == 2);
    shader->IsLoaded = false;
    assert(interpreter.CreateShader(path) == -1);
    assert(archive.calls == 3 && interpreter.shader_ids.size() == 1);
}
'''
    (folder / 'contract.cpp').write_text(code)
    env = runpy.run_path(str(Path(__file__).with_name('test_binary.py')))
    compiler, environment = env['host_environment']()
    command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/O2',
               str(folder / 'contract.cpp'), '/Fe:' + str(folder / 'contract.exe')]
    env['invoke'](command, folder, 'build', environment)
    env['invoke']([folder / 'contract.exe'], folder, 'run')
    print('selected CreateShader: failed/loaded/unloaded results and zero discarded allocation passed')


if __name__ == '__main__':
    main()
