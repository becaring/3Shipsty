#pragma once
#include "filesystem/filesystem.h"
namespace Shipyard { namespace Storage {
// Caller serializes competing publication and owns any XContent commit.
void WriteAtomicFile(const xbox_compat::filesystem::path& destination, const std::string& bytes);
}}
