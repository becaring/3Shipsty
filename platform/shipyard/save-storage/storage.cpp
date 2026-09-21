#include "save-storage/atomic_file.h"
#include "save-storage/storage.h"
#include "async/native.h"
#include <limits.h>
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
void Flush() { Check(XContentFlush(root, NULL), "XContentFlush"); }
}
void Mount(unsigned userIndex) {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (mounted) return;
    XCONTENT_DATA content = {0};
    content.DeviceID = XCONTENTDEVICE_ANY;
    ULARGE_INTEGER requested = {0}; requested.QuadPart = 16 * 1024 * 1024;
    XOVERLAPPED selection = {0};
    selection.hEvent = CreateEvent(NULL, FALSE, FALSE, NULL);
    if (!selection.hEvent) throw Async::native_error("save device selection event", GetLastError());
    DWORD result = XShowDeviceSelectorUI(userIndex, XCONTENTTYPE_SAVEDGAME, 0,
                                        requested, &content.DeviceID, &selection);
    if (result == ERROR_IO_PENDING) result = XGetOverlappedResult(&selection, NULL, TRUE);
    CloseHandle(selection.hEvent);
    Check(result, "save device selection");
    if (content.DeviceID == XCONTENTDEVICE_ANY)
        throw Async::native_error("no save device selected", ERROR_CANCELLED);
    content.dwContentType = XCONTENTTYPE_SAVEDGAME;
    strcpy_s(content.szFileName, "3Shipsty");
    wcscpy_s(content.szDisplayName, L"Ship of Harkinian");
    Check(XContentCreate(userIndex, root, &content, XCONTENTFLAG_OPENALWAYS, NULL, NULL, NULL), "XContentCreate");
    mounted = true;
}
std::string SaveDirectory() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    return "shipyard:\\Save";
}
void Commit() {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted(); Flush();
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
    Flush();
}
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes) {
    Async::lock_guard<Async::mutex> lock(mutex); RequireMounted();
    WriteAtomicFile(destination, bytes); Flush();
}

void Shutdown() {
    Async::lock_guard<Async::mutex> lock(mutex);
    if (!mounted) return;
    Flush(); Check(XContentClose(root, NULL), "XContentClose"); mounted = false;
}
}}
