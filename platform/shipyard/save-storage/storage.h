#pragma once
#include <string>
#include "filesystem/filesystem.h"
namespace Shipyard { namespace Storage {
// Call on the application thread before SaveManager::Init; errors and user
// cancellation propagate. The application owns retry/abort policy.
void Mount(unsigned userIndex = 0);
// Call only after SaveManager::ThreadPoolWait and all other writers joined.
void Shutdown();
std::string SaveDirectory();
void Commit();
void Replace(const xbox_compat::filesystem::path& temporary,
             const xbox_compat::filesystem::path& destination);
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes);
}}
