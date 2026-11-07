// Saves live in a per-profile container the player picks in the storage popup;
// config and logs stay in the game folder so they are easy to copy off.
// Every save write flushes the container, because XContent holds writes until a flush.
#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include "storage/device.h"
#include "xenos/native_display.h"
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
// Builds that kept saves in the game folder left them in game:\Save; the first mount copies them in.
void AdoptGameFolderSaves() {
    WIN32_FIND_DATAA found;
    HANDLE search = FindFirstFileA("game:\\Save\\*", &found);
    if (search == INVALID_HANDLE_VALUE) return;
    do {
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        const std::string name(found.cFileName);
        CopyFileA(("game:\\Save\\" + name).c_str(), ("shipyard:\\Save\\" + name).c_str(), TRUE);
    } while (FindNextFileA(search, &found));
    FindClose(search);
}
}
void Mount(unsigned userIndex) {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (mounted) return;
    xbox_compat::filesystem::create_directories("game:\\config");
    xbox_compat::filesystem::create_directories("game:\\logs");
    const MountPolicy policy = { userIndex, 16 * 1024 * 1024, root, "3Shipsty", L"Ship of Harkinian" };
    const StartupDisplay display = { Fast::InitializeNativeDisplay, Fast::PresentNativeStartupUI };
    const MountResult result = SelectAndMount(policy, display);
    Check(result.status, result.stage == ContainerStage ? "XContentCreate" : "save device selection");
    if (!xbox_compat::filesystem::is_directory("shipyard:\\Save")) {
        xbox_compat::filesystem::create_directories("shipyard:\\Save");
        AdoptGameFolderSaves();
    }
    mounted = true;
    FlushMounted();
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
