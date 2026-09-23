#pragma once
#include <string>

namespace Shipyard { namespace Platform {
std::string ApplicationDirectory();
std::string BundleDirectory();
void ShowError(const wchar_t* title, const wchar_t* message);
// Best-effort, on-failure-only receipt outside the unflushed save container.
void RecordStartupFailure(const char* message);
} }
