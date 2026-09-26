#pragma once
#include <string>
#include "filesystem/filesystem.h"
namespace Shipyard { namespace Storage {
// Create the install-side config, logs and Save directories before Context/SaveManager.
void Mount(unsigned userIndex = 0);
// Call only after SaveManager::ThreadPoolWait and all other writers joined.
void Shutdown();
std::string SaveDirectory();
void Commit();
void Replace(const xbox_compat::filesystem::path& temporary,
             const xbox_compat::filesystem::path& destination);
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes);
}}
