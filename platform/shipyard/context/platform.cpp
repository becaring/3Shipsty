#ifdef _XBOX
#include <xtl.h>
#include <xam.h>
#include <signal.h>
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
// A flushed file write takes ~40 ms on the console, so boot stages collect here
// and are written once, at the first completed frame or with a fault receipt.
// ponytail: a boot that hangs leaves no boot.txt; the debugger still gets each line.
char bootStages[4096];
size_t bootStagesLength = 0;

DWORD WriteFlushedFile(const char* path, const char* line, bool append) {
    HANDLE file = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, NULL,
                              append ? OPEN_ALWAYS : CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return GetLastError();
    DWORD error = ERROR_SUCCESS;
    if (append && SetFilePointer(file, 0, NULL, FILE_END) == INVALID_SET_FILE_POINTER)
        error = GetLastError();
    DWORD written = 0;
    const DWORD length = static_cast<DWORD>(strlen(line));
    if (error == ERROR_SUCCESS && (!WriteFile(file, line, length, &written, NULL) || written != length))
        error = GetLastError() ? GetLastError() : ERROR_WRITE_FAULT;
    if (error == ERROR_SUCCESS && !FlushFileBuffers(file)) error = GetLastError();
    if (!CloseHandle(file) && error == ERROR_SUCCESS) error = GetLastError();
    return error;
}

void RecordNativeFault(const char* kind, DWORD code, const void* address, const char* detail) {
    if (InterlockedCompareExchange(&faultReceiptClaimed, 1, 0) != 0) return;
    char line[384];
    _snprintf_s(line, sizeof(line), _TRUNCATE,
                "commit=%s kind=%s code=%08lx address=%08lx thread=%lu detail=%s\n",
                gGitCommitHash, kind, code, static_cast<DWORD>(reinterpret_cast<uintptr_t>(address)),
                GetCurrentThreadId(), detail ? detail : "");
    OutputDebugStringA(line);
    CreateDirectoryA("game:\\logs", NULL);
    if (bootStagesLength) WriteFlushedFile("game:\\logs\\boot.txt", bootStages, false);
    WriteFlushedFile("game:\\logs\\startup-fault.txt", line, false);
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

void __cdecl ShipyardAborted(int) {
    RecordNativeFault("abort", SIGABRT, NULL, "CRT abort signal");
    // A retail abort powers the console off; the receipts are written, so return to the dashboard instead.
    XLaunchNewImage(XLAUNCH_KEYWORD_DEFAULT_APP, 0);
}
}

extern "C" void Shipyard_InstallStartupFaultHandler() {
    previousFaultFilter = SetUnhandledExceptionFilter(ShipyardUnhandledFault);
    std::set_terminate(ShipyardTerminated);
    signal(SIGABRT, ShipyardAborted);
}
#endif

namespace Shipyard { namespace Platform {
void RecordBootStage(const char* stage, bool commitToSave) {
#ifdef _XBOX
    (void)commitToSave;
    char* line = bootStages + bootStagesLength;
    // Free memory per stage shows which startup step a mod's resources exhaust.
    MEMORYSTATUS memory;
    GlobalMemoryStatus(&memory);
    const int length = _snprintf_s(line, sizeof(bootStages) - bootStagesLength, _TRUNCATE,
                                   "commit=%s stage=%s tick=%lu thread=%lu free=%luMB\n", gGitCommitHash, stage,
                                   GetTickCount(), GetCurrentThreadId(), (unsigned long)(memory.dwAvailPhys >> 20));
    OutputDebugStringA(line);
    if (length > 0) bootStagesLength += length;
    if (strcmp(stage, "first-audio-complete") == 0) {
        CreateDirectoryA("game:\\logs", NULL);
        WriteFlushedFile("game:\\logs\\boot.txt", bootStages, false);
    }
#else
    (void)stage;
    (void)commitToSave;
#endif
}

std::string ApplicationDirectory() { return "game:"; }
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
            // Storage initialization creates the D3D device earlier. XAM dialogs
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
void RecordStartupFatal(const char* operation, unsigned long code) {
#ifdef _XBOX
    RecordNativeFault("fatal", static_cast<DWORD>(code), NULL, operation);
#else
    (void)operation;
    (void)code;
#endif
}
} }
