#include "save-storage/atomic_file.h"
#include "save-storage/json_compare.h"
#include <fstream>
#include <sstream>
#include <cassert>
#include <iostream>
#include <limits>
std::string Read(const char* path) {
    std::ifstream input(path, std::ios::binary); std::ostringstream bytes; bytes << input.rdbuf(); return bytes.str();
}
int main(int argc, char** argv) {
    assert(argc == 2); const std::string path = argv[1];
    const std::string temporary = path + ".tmp";
    std::string bytes;
    for (unsigned n = 0; n < 65536; ++n) bytes += char(n);
    Shipyard::Storage::WriteAtomicFile(path, bytes);
    assert(Read(path.c_str()) == bytes);
    HANDLE deny = CreateFileA(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    assert(deny != INVALID_HANDLE_VALUE);
    bool threw = false;
    try { Shipyard::Storage::WriteAtomicFile(path, "replacement blocked by sharing"); }
    catch (const Shipyard::Async::native_error&) { threw = true; }
    assert(threw); CloseHandle(deny);
    assert(Read(path.c_str()) == bytes);
    assert(GetFileAttributesA(temporary.c_str()) == INVALID_FILE_ATTRIBUTES);
    Shipyard::Storage::WriteAtomicFile(path, std::string()); assert(Read(path.c_str()).empty());
    Shipyard::Storage::WriteAtomicFile(path, "short"); assert(Read(path.c_str()) == "short");
    SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_READONLY); threw = false;
    try { Shipyard::Storage::WriteAtomicFile(path, bytes); }
    catch (const Shipyard::Async::native_error&) { threw = true; }
    SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
    assert(threw && Read(path.c_str()) == "short");
    DeleteFileA(path.c_str());
    nlohmann::json values[13];
    values[0] = nullptr; values[1] = true; values[2] = nlohmann::json::object();
    values[3] = nlohmann::json::array(); values[4] = "hello";
    values[5] = -1; values[6] = 0; values[7] = 12; values[8] = 13;
    values[9] = std::numeric_limits<unsigned long long>::max();
    values[10] = -0.5; values[11] = 12.5;
    values[12] = std::numeric_limits<double>::quiet_NaN();
    for (unsigned i = 0; i < 13; ++i) {
        bool less = Shipyard::Storage::JsonLessThanInt(values[i], 12);
        bool greater = Shipyard::Storage::JsonGreaterThanInt(values[i], 0);
#if defined(SHIPYARD_COMPARE_ORIGINAL)
        assert(less == (values[i] < 12)); assert(greater == (values[i] > 0));
#endif
        std::cout << less << greater;
    }
    std::cout << " atomic publication and failure preservation passed\n";
}
