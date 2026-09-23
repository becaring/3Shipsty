#include "audio_log.h"
#include "context/platform.h"
#include <spdlog/spdlog.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>

void ShipyardAudioLog(const char* format, ...) {
    char buffer[2048];
    va_list args;
    va_start(args, format);
    _vsnprintf_s(buffer, sizeof(buffer), _TRUNCATE, format, args);
    va_end(args);
    spdlog::info("{}", buffer);
}
__declspec(noreturn) void ShipyardAudioFatal(const char* operation, HRESULT result) {
    Shipyard::Platform::RecordStartupFatal(operation, static_cast<unsigned long>(result));
    try {
        spdlog::critical("XAudio2 failure: {} ({:08x})", operation, static_cast<unsigned>(result));
        spdlog::default_logger()->flush();
    } catch (...) {
        OutputDebugStringA("Shipyard: fatal XAudio2 failure while logging\n");
    }
    // Never unwind a C++ exception through an XAudio2 callback ABI.
    std::abort();
}
double ShipyardAudioTime() {
    LARGE_INTEGER ticks, frequency;
    QueryPerformanceCounter(&ticks);
    QueryPerformanceFrequency(&frequency);
    return static_cast<double>(ticks.QuadPart) / static_cast<double>(frequency.QuadPart);
}
