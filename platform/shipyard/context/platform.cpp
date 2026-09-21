#ifdef _XBOX
#include <xtl.h>
#else
#include <windows.h>
#endif
#include "context/platform.h"
#include "save-storage/storage.h"

namespace Shipyard { namespace Platform {
// Config, CVars, saves and user mods share the selected writable namespace.
// The release archives remain discoverable in the executable bundle directory.
std::string ApplicationDirectory() {
    return xbox_compat::filesystem::path(Storage::SaveDirectory()).parent_path().string();
}
std::string BundleDirectory() { return "game:"; }

void ShowError(const wchar_t* title, const wchar_t* message) {
#ifdef _XBOX
    const wchar_t* buttons[] = { L"OK" };
    MESSAGEBOX_RESULT result = { 0 };
    XOVERLAPPED operation = { 0 };
    DWORD status = XShowMessageBoxUI(XUSER_INDEX_ANY, title, message, 1, buttons, 0,
                                   XMB_ERRORICON, &result, &operation);
    if (status == ERROR_IO_PENDING) status = XGetOverlappedResult(&operation, NULL, TRUE);
    if (status != ERROR_SUCCESS) OutputDebugStringA("Shipyard: native error dialog failed\n");
#else
    MessageBoxW(NULL, message, title, MB_OK | MB_ICONERROR);
#endif
}
} }
