#pragma once
#include "save-storage/storage.h"
namespace Shipyard { namespace LegacySave {
inline xbox_compat::filesystem::path Path() {
    return xbox_compat::filesystem::path(Storage::SaveDirectory()).parent_path() / "oot_save.sav";
}
inline xbox_compat::filesystem::path BackupPath() {
    return xbox_compat::filesystem::path(Storage::SaveDirectory()).parent_path() / "oot_save.bak";
}
}}
