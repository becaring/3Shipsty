#ifdef _XBOX
#include <xtl.h>
#else
#include <windows.h>
#endif
#include "context/platform.h"
#include "save-storage/storage.h"
#ifdef _XBOX
#include "xenos/native_display.h"
#endif

namespace Shipyard { namespace Platform {
// Config, CVars, saves and user mods share the selected writable namespace.
// The release archives remain discoverable in the executable bundle directory.
std::string ApplicationDirectory() {
    return xbox_compat::filesystem::path(Storage::SaveDirectory()).root_name().string();
}
std::string BundleDirectory() { return "game:"; }

void ShowError(const wchar_t* title, const wchar_t* message) {
#ifdef _XBOX
    const wchar_t* buttons[] = { L"OK" };
    MESSAGEBOX_RESULT result = { 0 };
    XOVERLAPPED operation = { 0 };
    DWORD status = XShowMessageBoxUI(XUSER_INDEX_ANY, title, message, 1, buttons, 0,
                                   XMB_ERRORICON, &result, &operation);
    if (status == ERROR_IO_PENDING) {
        const DWORD started = GetTickCount();
        while (!XHasOverlappedIoCompleted(&operation)) {
            // The selector creates the same D3D device earlier. XAM dialogs
            // also need presentation after Context has allocated framebuffers.
            HRESULT presented = Fast::PresentNativeStartupUI();
            if (presented == E_UNEXPECTED && Fast::xenos_device)
                presented = Fast::xenos_device->Present(NULL, NULL, NULL, NULL);
            if (FAILED(presented) || DWORD(GetTickCount() - started) >= 90000) {
                XCancelOverlapped(&operation);
                while (!XHasOverlappedIoCompleted(&operation)) Sleep(1);
                break;
            }
            Sleep(1);
        }
        status = XGetOverlappedResult(&operation, NULL, FALSE);
    }
    if (status != ERROR_SUCCESS) OutputDebugStringA("Shipyard: native error dialog failed\n");
#else
    MessageBoxW(NULL, message, title, MB_OK | MB_ICONERROR);
#endif
}
} }
