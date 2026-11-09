// Saves live in a per-profile container the player picks in the storage popup;
// config and logs stay in the game folder so they are easy to copy off.
// Every save write flushes the container, because XContent holds writes until a flush.
// If the popup is cancelled or the container cannot be opened, saves use game:\Save instead.
#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include "context/platform.h"
#include "storage/device.h"
#include "xenos/native_display.h"
#include <stdio.h>
namespace Shipyard { namespace Storage {
namespace {
Async::mutex mutex;
bool mounted;
bool inContainer;
const char* const root = "shipyard";
void Check(DWORD result, const char* operation) {
    if (result != ERROR_SUCCESS) throw Async::native_error(operation, result);
}
void RequireMounted() {
    if (!mounted) throw std::logic_error("Shipyard save storage is not mounted");
}
void FlushMounted() {
    if (inContainer) Check(Shipyard::Storage::Flush(root), "XContentFlush");
}
bool SameStamp(const std::string& marker, const FILETIME& stamp) {
    HANDLE file = CreateFileA(marker.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return false;
    FILETIME recorded = { 0, 0 };
    DWORD read = 0;
    const bool same = ReadFile(file, &recorded, sizeof(recorded), &read, NULL) && read == sizeof(recorded) &&
        CompareFileTime(&recorded, &stamp) == 0;
    CloseHandle(file);
    return same;
}
// Saves in game:\Save, from PC or from the game-folder fallback, fill empty slots at every mount.
// A marker with the copied file's write time keeps a save deleted in game from coming back.
void AdoptGameFolderSaves() {
    WIN32_FIND_DATAA found;
    HANDLE search = FindFirstFileA("game:\\Save\\*", &found);
    if (search == INVALID_HANDLE_VALUE) return;
    do {
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        const std::string name(found.cFileName);
        const std::string target = "shipyard:\\Save\\" + name, marker = target + ".imported";
        if (SameStamp(marker, found.ftLastWriteTime)) continue;
        if (CopyFileA(("game:\\Save\\" + name).c_str(), target.c_str(), TRUE))
            WriteAtomicFile(marker, &found.ftLastWriteTime, sizeof(found.ftLastWriteTime));
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
    inContainer = result.status == ERROR_SUCCESS;
    if (inContainer) {
        xbox_compat::filesystem::create_directories("shipyard:\\Save");
        AdoptGameFolderSaves();
    } else {
        // Some exploit loaders, BadAvatar among them, refuse the profile container; boot.txt keeps the reason.
        char stage[128];
        _snprintf_s(stage, sizeof(stage), _TRUNCATE, "saves-in-game-folder step=%s error=%lu extended=%08lx",
                    result.stage == ContainerStage ? "XContentCreate" : "device-selection",
                    (unsigned long)result.status, (unsigned long)result.extendedStatus);
        Shipyard::Platform::RecordBootStage(stage, false);
        xbox_compat::filesystem::create_directories("game:\\Save");
    }
    mounted = true;
    FlushMounted();
}
std::string SaveDirectory() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    if (!inContainer) return "game:\\Save";
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
    if (inContainer) { FlushMounted(); Check(Shipyard::Storage::Close(root), "XContentClose"); }
    mounted = false;
}
}}
