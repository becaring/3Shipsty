#ifdef _XBOX
#include <xtl.h>
#else
#include <windows.h>
#endif
#include "context/platform.h"

namespace Shipyard { namespace Platform {
// The executable/content root matches the primary SoH360 native window.
// XContent device selection and the writable configuration root are not yet
// integrated; startup must supply that before claiming save support.
std::string ApplicationDirectory() { return "game:"; }
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
