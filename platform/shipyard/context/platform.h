#pragma once
#include <string>

namespace Shipyard { namespace Platform {
std::string ApplicationDirectory();
std::string BundleDirectory();
// On the console an error is fatal: the message goes into the startup receipt, and closing the dialog leaves for
// the dashboard.
void ShowError(const wchar_t* title, const wchar_t* message);
// Temporary hardware-startup diagnostics. The game trace is flushed at each
// boundary into game:\logs, including failures before logger initialization.
void RecordBootStage(const char* stage, bool commitToSave);
void RecordStartupFailure(const char* message);
void RecordStartupFatal(const char* operation, unsigned long code);
// The mod menu's Apply & Close asks for a relaunch; ExitTitle then starts 3Shipsty.xex again
// instead of the dashboard. ExitTitle returns only if no launch succeeded.
void RequestRelaunch();
void ExitTitle();
} }
