#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include "xenos/native_display.h"
namespace Shipyard { namespace Storage {
namespace {
Async::mutex mutex;
bool mounted;
void Check(DWORD result, const char* operation) {
    if (result != ERROR_SUCCESS) throw Async::native_error(operation, result);
}
void RequireMounted() {
    if (!mounted) throw std::logic_error("Shipyard save storage is not mounted");
}
}
void Mount(unsigned userIndex) {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (mounted) return;
    (void)userIndex;
    Fast::InitializeNativeDisplay();
    xbox_compat::filesystem::create_directories("game:\\config");
    xbox_compat::filesystem::create_directories("game:\\logs");
    xbox_compat::filesystem::create_directories("game:\\Save");
    mounted = true;
}
std::string SaveDirectory() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    return "game:\\Save";
}
void Commit() {
    // Raw files are flushed before replacement; there is no container to commit.
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
}
void Replace(const xbox_compat::filesystem::path& temporary,
             const xbox_compat::filesystem::path& destination) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    HANDLE file = CreateFileA(temporary.c_str(), GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) throw Async::native_error("open completed save", GetLastError());
    DWORD error = FlushFileBuffers(file) ? ERROR_SUCCESS : GetLastError();
    if (!CloseHandle(file) && error == ERROR_SUCCESS) error = GetLastError();
    Check(error, "flush completed save");
    if (!MoveFileExA(temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw Async::native_error("replace completed save", GetLastError());
}
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    WriteAtomicFile(destination, bytes);
}

void Shutdown() {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (!mounted) return;
    mounted = false;
}
}}
