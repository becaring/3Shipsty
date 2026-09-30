#pragma once
#include <string>

namespace Shipyard { namespace Platform {
std::string ApplicationDirectory();
std::string BundleDirectory();
void ShowError(const wchar_t* title, const wchar_t* message);
// Temporary hardware-startup diagnostics. The game trace is flushed at each
// boundary into game:\logs, including failures before logger initialization.
void RecordBootStage(const char* stage, bool commitToSave);
void RecordStartupFailure(const char* message);
void RecordStartupFatal(const char* operation, unsigned long code);
} }
