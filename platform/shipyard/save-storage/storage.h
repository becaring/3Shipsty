#pragma once
#include <string>
#include "filesystem/filesystem.h"
namespace Shipyard { namespace Storage {
// Call on the application thread before Context/SaveManager. Shows the storage popup;
// cancellation or a container error falls back to saves in game:\Save.
void Mount(unsigned userIndex = 0);
// Call only after SaveManager::ThreadPoolWait and all other writers joined.
void Shutdown();
std::string SaveDirectory();
void Commit();
void Replace(const xbox_compat::filesystem::path& temporary,
             const xbox_compat::filesystem::path& destination);
void WriteAtomic(const xbox_compat::filesystem::path& destination, const std::string& bytes);
}}
