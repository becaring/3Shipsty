#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include "storage/device.h"
#include "xenos/native_display.h"
#include "xenos/services.h"
namespace Shipyard { namespace Storage {
namespace {
Async::mutex mutex;
bool mounted;
const char* const root = "shipyard";
void Check(DWORD result, const char* operation) {
    if (result != ERROR_SUCCESS) throw Async::native_error(operation, result);
}
void RequireMounted() {
    if (!mounted) throw std::logic_error("Shipyard save storage is not mounted");
}
void FlushMounted() { Check(Shipyard::Storage::Flush(root), "XContentFlush"); }
}
void Mount(unsigned userIndex) {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (mounted) return;
    const MountPolicy policy = { userIndex, 16 * 1024 * 1024, root, "3Shipsty", L"Ship of Harkinian" };
    const StartupDisplay display = { Fast::InitializeNativeDisplay, Fast::PresentNativeStartupUI };
    const MountResult result = SelectAndMount(policy, display);
    Check(result.status, result.stage == ContainerStage ? "XContentCreate" : "save device selection");
    mounted = true;
}
std::string SaveDirectory() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    return "shipyard:\\Save";
}
void Commit() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted(); FlushMounted();
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
    FlushMounted();
}
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    WriteAtomicFile(destination, bytes); FlushMounted();
}

void Shutdown() {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (!mounted) return;
    FlushMounted(); Check(Shipyard::Storage::Close(root), "XContentClose"); mounted = false;
}
}}
