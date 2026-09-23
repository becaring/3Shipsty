#ifdef _XBOX
#include <xtl.h>
#else
#include <windows.h>
#endif
#include "context/platform.h"
#include "save-storage/storage.h"
#include <cstring>
#include <stdint.h>
#ifdef _XBOX
#include "xenos/native_display.h"
#include <exception>
#include <cstdlib>
#endif

#ifdef _XBOX
extern "C" const char gGitCommitHash[];
namespace {
volatile LONG faultReceiptClaimed = 0;
LPTOP_LEVEL_EXCEPTION_FILTER previousFaultFilter = NULL;

void RecordNativeFault(const char* kind, DWORD code, const void* address, const char* detail) {
    if (InterlockedCompareExchange(&faultReceiptClaimed, 1, 0) != 0) return;
    char line[384];
    _snprintf_s(line, sizeof(line), _TRUNCATE,
                "commit=%s kind=%s code=%08lx address=%08lx thread=%lu detail=%s\n",
                gGitCommitHash, kind, code, static_cast<DWORD>(reinterpret_cast<uintptr_t>(address)),
                GetCurrentThreadId(), detail ? detail : "");
    OutputDebugStringA(line);
    // This game: sidecar is independent of XContent's uncommitted STFS table.
    // It is created only after a fault, never on a successful startup.
    HANDLE file = CreateFileA("game:\\3Shipsty.startup-fault", GENERIC_WRITE, FILE_SHARE_READ,
                              NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    const DWORD length = static_cast<DWORD>(strlen(line));
    if (WriteFile(file, line, length, &written, NULL) && written == length)
        FlushFileBuffers(file);
    CloseHandle(file);
}

LONG WINAPI ShipyardUnhandledFault(EXCEPTION_POINTERS* information) {
    const EXCEPTION_RECORD* record = information ? information->ExceptionRecord : NULL;
    RecordNativeFault("seh", record ? record->ExceptionCode : 0,
                      record ? record->ExceptionAddress : NULL, "");
    if (previousFaultFilter) return previousFaultFilter(information);
    return EXCEPTION_CONTINUE_SEARCH;
}

void ShipyardTerminated() {
    RecordNativeFault("terminate", 0, NULL, "uncaught worker or C++ failure");
    std::abort();
}
}

extern "C" void Shipyard_InstallStartupFaultHandler() {
    previousFaultFilter = SetUnhandledExceptionFilter(ShipyardUnhandledFault);
    std::set_terminate(ShipyardTerminated);
}
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

void RecordStartupFailure(const char* message) {
#ifdef _XBOX
    RecordNativeFault("handled", 0, NULL, message);
#else
    (void)message;
#endif
}
} }
