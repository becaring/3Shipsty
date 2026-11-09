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
#include "presentation/xenos_swap_chain.h"
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

volatile LONG* workerFaultSignal = NULL;
DWORD workerFaultOwner = 0;

// Return addresses from the faulting frame outward. Each frame saves its caller's LR 8 bytes below the back chain.
void FormatCallChain(const CONTEXT& context, char* text, size_t size) {
    int length = _snprintf_s(text, size, _TRUNCATE, "lr=%08lx chain=", context.Lr);
    DWORD sp = static_cast<DWORD>(context.Gpr1);
    for (int frame = 0; frame < 12 && length > 0 && static_cast<size_t>(length) < size; ++frame) {
        DWORD next = 0, lr = 0;
        bool valid = false;
        __try {
            next = *reinterpret_cast<const DWORD*>(sp);
            valid = next > sp && next - sp <= 0x100000 && !(next & 3);
            if (valid) lr = *reinterpret_cast<const DWORD*>(next - 8);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            valid = false;
        }
        if (!valid) break;
        const int added = _snprintf_s(text + length, size - length, _TRUNCATE, "%08lx,", lr);
        if (added < 0) break;
        length += added;
        sp = next;
    }
}

LONG WINAPI ShipyardUnhandledFault(EXCEPTION_POINTERS* information) {
    const EXCEPTION_RECORD* record = information ? information->ExceptionRecord : NULL;
    char chain[192] = "";
    if (information && information->ContextRecord) FormatCallChain(*information->ContextRecord, chain, sizeof(chain));
    RecordNativeFault("seh", record ? record->ExceptionCode : 0,
                      record ? record->ExceptionAddress : NULL, chain);
    volatile LONG* signal = workerFaultSignal;
    if (signal && GetCurrentThreadId() != workerFaultOwner) {
        // The owner thread recovers from the failed work; this worker stops here for good.
        InterlockedExchange(signal, 1);
        for (;;) Sleep(INFINITE);
    }
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

namespace {
bool relaunchRequested;
}
void RequestRelaunch() { relaunchRequested = true; }
#ifdef _XBOX
// Launchers often rename the XEX, so relaunch the one in the game folder.
// ponytail: with several XEX files and no 3Shipsty.xex, the first one found wins.
static bool FindTitleImage(char* path, size_t size) {
    WIN32_FIND_DATAA found;
    HANDLE search = FindFirstFileA("game:\\3Shipsty.xex", &found);
    if (search == INVALID_HANDLE_VALUE) search = FindFirstFileA("game:\\*.xex", &found);
    if (search == INVALID_HANDLE_VALUE) return false;
    FindClose(search);
    _snprintf_s(path, size, _TRUNCATE, "game:\\%s", found.cFileName);
    return true;
}
#endif
void ExitTitle() {
#ifdef _XBOX
    char image[MAX_PATH];
    if (relaunchRequested && FindTitleImage(image, sizeof(image))) XLaunchNewImage(image, 0);
    XLaunchNewImage(XLAUNCH_KEYWORD_DEFAULT_APP, 0);
#endif
}

void CatchWorkerFaults(volatile long* signal) {
#ifdef _XBOX
    workerFaultOwner = GetCurrentThreadId();
    workerFaultSignal = reinterpret_cast<volatile LONG*>(signal);
#else
    (void)signal;
#endif
}

std::string ApplicationDirectory() { return "game:"; }
std::string BundleDirectory() { return "game:"; }

#ifdef _XBOX
// One black frame behind a system dialog. Storage startup presents before the game owns framebuffers; after that
// the device's own Present resolves into a NULL front buffer, so the frame goes through the title's swap chain.
static HRESULT PresentErrorFrame() {
    HRESULT presented = Fast::PresentNativeStartupUI();
    if (presented != E_UNEXPECTED || !Fast::xenos_device) return presented;
    IDirect3DSurface9* back = NULL;
    if (SUCCEEDED(Fast::xenos_device->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &back))) {
        Fast::xenos_device->SetRenderTarget(0, back);
        back->Release();
    }
    Fast::xenos_device->SetDepthStencilSurface(NULL);
    presented = Fast::xenos_device->Clear(0, NULL, D3DCLEAR_TARGET, 0xff000000, 1, 0);
    return FAILED(presented) ? presented : ::Shipyard::XenosPresentationChain().Present();
}
#endif

void ShowError(const wchar_t* title, const wchar_t* message) {
#ifdef _XBOX
    // The receipt names the error even when the dialog cannot be shown.
    char detail[256];
    unsigned length = 0;
    for (; length < sizeof(detail) - 1 && message[length]; ++length)
        detail[length] = message[length] < 0x80 ? static_cast<char>(message[length]) : '?';
    detail[length] = 0;
    RecordNativeFault("handled", 0, NULL, detail);
    // XAM rejects a title over 32 characters or text over 256, and then shows nothing.
    wchar_t shortTitle[33], shortMessage[256];
    wcsncpy_s(shortTitle, title, _TRUNCATE);
    wcsncpy_s(shortMessage, message, _TRUNCATE);
    // XShow functions require the GPU-owned constants to be released first.
    if (Fast::xenos_device) Fast::xenos_device->GpuDisownAll();
    const wchar_t* buttons[] = { L"OK" };
    MESSAGEBOX_RESULT result = { 0 };
    XOVERLAPPED operation = { 0 };
    DWORD status = ERROR_ACCESS_DENIED;
    // A system UI that just closed, such as the storage selector, refuses a new dialog until it is gone.
    const DWORD started = GetTickCount();
    while (status == ERROR_ACCESS_DENIED && DWORD(GetTickCount() - started) < 10000) {
        status = XShowMessageBoxUI(XUSER_INDEX_ANY, shortTitle, shortMessage, 1, buttons, 0,
                                   XMB_ERRORICON, &result, &operation);
        if (status == ERROR_ACCESS_DENIED && FAILED(PresentErrorFrame())) break;
    }
    if (status == ERROR_IO_PENDING) {
        const DWORD shown = GetTickCount();
        while (!XHasOverlappedIoCompleted(&operation)) {
            if (FAILED(PresentErrorFrame()) || DWORD(GetTickCount() - shown) >= 90000) {
                XCancelOverlapped(&operation);
                while (!XHasOverlappedIoCompleted(&operation)) Sleep(1);
                break;
            }
        }
        status = XGetOverlappedResult(&operation, NULL, FALSE);
    }
    char line[64];
    _snprintf_s(line, sizeof(line), _TRUNCATE, "dialog status=%lu\n", (unsigned long)status);
    WriteFlushedFile("game:\\logs\\startup-fault.txt", line, true);
    // Every console error is fatal, and a process exit powers the console off.
    ExitTitle();
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
