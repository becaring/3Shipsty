#include "save-storage/atomic_file.h"
#include <limits.h>
namespace Shipyard { namespace Storage {
void WriteAtomicFile(const xbox_compat::filesystem::path& destination, const std::string& bytes) {
    if (bytes.size() > UINT_MAX) throw std::length_error("save exceeds native write size");
    const std::string temporary = destination.string() + ".tmp";
    HANDLE file = CreateFileA(temporary.c_str(), GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) throw Async::native_error("create save temporary", GetLastError());
    DWORD written = 0;
    DWORD error = WriteFile(file, bytes.data(), (DWORD)bytes.size(), &written, NULL) ? ERROR_SUCCESS : GetLastError();
    if (error == ERROR_SUCCESS && written != bytes.size()) error = ERROR_WRITE_FAULT;
    if (error == ERROR_SUCCESS && !FlushFileBuffers(file)) error = GetLastError();
    if (!CloseHandle(file) && error == ERROR_SUCCESS) error = GetLastError();
    if (error == ERROR_SUCCESS && !MoveFileExA(temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) error = GetLastError();
    if (error != ERROR_SUCCESS) { DeleteFileA(temporary.c_str()); throw Async::native_error("write save atomic", error); }
}
}}
