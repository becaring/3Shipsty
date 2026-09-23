#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using zip_int64_t = int64_t;
using zip_uint64_t = uint64_t;
struct zip_t {};
struct zip_file {};
struct zip_stat { zip_uint64_t size; };

static zip_t archive;
static zip_file entry;
static zip_uint64_t entrySize = 5;
static std::vector<zip_int64_t> readResults;
static size_t readCall;
static size_t sourceOffset;
static std::vector<zip_uint64_t> requested;
static int closeCount;
static int openCount;

zip_int64_t zip_name_locate(zip_t*, const char*, int) { return 0; }
void zip_stat_init(zip_stat* stat) { stat->size = 0; }
int zip_stat_index(zip_t*, zip_int64_t, int, zip_stat* stat) { stat->size = entrySize; return 0; }
zip_file* zip_fopen_index(zip_t*, zip_int64_t, int) { ++openCount; return &entry; }
zip_int64_t zip_fread(zip_file*, void* buffer, zip_uint64_t length) {
    requested.push_back(length);
    assert(readCall < readResults.size());
    const zip_int64_t result = readResults[readCall++];
    if (result > 0) {
        assert(static_cast<zip_uint64_t>(result) <= length);
        std::memcpy(buffer, "abcde" + sourceOffset, static_cast<size_t>(result));
        sourceOffset += static_cast<size_t>(result);
    }
    return result;
}
int zip_fclose(zip_file*) { ++closeCount; return 0; }

#define SPDLOG_TRACE(...) ((void)0)
namespace Ship {
struct File {
    std::shared_ptr<std::vector<char>> Buffer;
    bool IsLoaded = false;
};
class O2rArchive {
public:
    O2rArchive() : mZipArchive(&archive) {}
    std::string GetPath() const { return "contract.o2r"; }
    std::shared_ptr<File> LoadFile(const std::string& filePath);
    zip_t* mZipArchive;
};
#include "method.inc"
}

int main() {
    Ship::O2rArchive reader;
    readResults = {5}; readCall = sourceOffset = 0; requested.clear(); closeCount = 0;
    auto complete = reader.LoadFile("asset");
    assert(complete && complete->IsLoaded && complete->Buffer->size() == 5);
    assert(std::memcmp(complete->Buffer->data(), "abcde", 5) == 0 && closeCount == 1);
    assert(readCall == 1 && requested == std::vector<zip_uint64_t>{5});

#ifdef SHIPYARD_PROJECTED
    readResults = {2, 2, 1}; readCall = sourceOffset = 0; requested.clear(); closeCount = 0;
    auto chunked = reader.LoadFile("asset");
    assert(chunked && chunked->IsLoaded && closeCount == 1);
    assert(std::memcmp(chunked->Buffer->data(), "abcde", 5) == 0);
    assert(readCall == 3 && (requested == std::vector<zip_uint64_t>{5, 3, 1}));

    for (const auto& results : {std::vector<zip_int64_t>{3, 0},
                                std::vector<zip_int64_t>{2, -1},
                                std::vector<zip_int64_t>{0}}) {
        readResults = results; readCall = sourceOffset = 0; requested.clear(); closeCount = 0;
        assert(!reader.LoadFile("asset") && closeCount == 1);
        assert(readCall == readResults.size());
    }
    entrySize = static_cast<zip_uint64_t>(-1); openCount = closeCount = 0;
    assert(!reader.LoadFile("asset") && openCount == 0 && closeCount == 0);
    std::cout << "Projected O2R: chunked reads complete; incomplete and oversized entries rejected\n";
#else
    // Pin the inherited behavior so the regression demonstrates the projection fix.
    readResults = {3}; readCall = sourceOffset = 0; closeCount = 0;
    auto shortRead = reader.LoadFile("asset");
    assert(shortRead && shortRead->IsLoaded && readCall == 1 && closeCount == 1);
    std::cout << "Pinned upstream O2R: positive short read remains marked loaded\n";
#endif
}
