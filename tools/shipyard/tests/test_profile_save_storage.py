"""Exercise the per-profile save container on host files, with the storage popup stubbed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment, PLATFORM_BASE


class ProfileSaveStorageTests(unittest.TestCase):
    def test_popup_mount_adopt_write_flush_cancel_and_remount(self):
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(prefix='profile-storage-', dir=ROOT / 'scratch') as temp:
            folder = Path(temp)
            install = folder / 'install'
            profile = folder / 'profile'
            # The device prefixes are the only production-source change.
            source = (ROOT / 'platform/shipyard/save-storage/storage.cpp').read_text()
            self.assertEqual(source.count('game:\\\\'), 6)
            self.assertEqual(source.count('shipyard:\\\\'), 3)
            source = source.replace('game:\\\\', install.as_posix() + '/')
            source = source.replace('shipyard:\\\\', profile.as_posix() + '/')
            audit = folder / 'storage.cpp'
            audit.write_text(source)
            include = folder / 'include'
            (include / 'xenos').mkdir(parents=True)
            (include / 'storage').mkdir()
            (include / 'xenos/native_display.h').write_text(
                '#pragma once\n#include <windows.h>\n'
                'namespace Fast { void InitializeNativeDisplay(); HRESULT PresentNativeStartupUI(); }\n')
            (include / 'storage/device.h').write_text('''#pragma once
#include <windows.h>
namespace Shipyard { namespace Storage {
struct MountPolicy { unsigned userIndex; unsigned long long requestedBytes; const char* mountName;
                     const char* containerFileName; const wchar_t* displayName; };
struct StartupDisplay { void (*initialize)(); HRESULT (*present)(); };
enum MountStage { SelectionStage, ContainerStage, MountedStage };
struct MountResult { DWORD status; MountStage stage; DWORD extendedStatus; DWORD deviceId; };
MountResult SelectAndMount(const MountPolicy& policy, const StartupDisplay& display);
DWORD Flush(const char* mountName);
DWORD Close(const char* mountName);
}}
''')
            contract = folder / 'contract.cpp'
            contract.write_text(r'''
#include "save-storage/storage.h"
#include "storage/device.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string.h>
namespace fs = xbox_compat::filesystem;
namespace storage = Shipyard::Storage;
fs::path profileRoot;
int displays = 0, selections = 0, flushes = 0, closes = 0;
DWORD nextSelection = ERROR_SUCCESS;
namespace Fast {
void InitializeNativeDisplay() { ++displays; }
HRESULT PresentNativeStartupUI() { return S_OK; }
}
namespace Shipyard { namespace Storage {
MountResult SelectAndMount(const MountPolicy& policy, const StartupDisplay& display) {
    ++selections;
    display.initialize();
    MountResult result = { nextSelection, SelectionStage, 0, 1 };
    if (strcmp(policy.mountName, "shipyard") || strcmp(policy.containerFileName, "3Shipsty"))
        result.status = ERROR_INVALID_PARAMETER;
    if (result.status == ERROR_SUCCESS) { fs::create_directories(profileRoot); result.stage = MountedStage; }
    return result;
}
DWORD Flush(const char* mountName) { ++flushes; return strcmp(mountName, "shipyard") ? ERROR_INVALID_NAME : 0; }
DWORD Close(const char* mountName) { ++closes; return strcmp(mountName, "shipyard") ? ERROR_INVALID_NAME : 0; }
}}
std::string bootStages;
namespace Shipyard { namespace Platform {
void RecordBootStage(const char* stage, bool) { bootStages += stage; bootStages += '\n'; }
}}
void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}
std::string read(const fs::path& path) {
    std::ifstream file(path.c_str(), std::ios::binary);
    require(file.is_open(), "could not read persisted file");
    return std::string(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}
void write(const fs::path& path, const std::string& bytes) {
    std::ofstream file(path.c_str(), std::ios::binary);
    file.write(bytes.data(), bytes.size());
    file.close();
    require(!file.fail(), "fixture write failed");
}
int main(int argc, char** argv) { try {
    const fs::path install(argv[1]);
    profileRoot = fs::path(argv[2]);
    fs::create_directories(install / "Save");
    write(install / "Save" / "file1.sav", "game folder save");

    nextSelection = ERROR_CANCELLED;
    storage::Mount();
    require(!fs::exists(profileRoot), "cancelled popup created the container");
    require(fs::path(storage::SaveDirectory()).generic_string() == (install / "Save").generic_string(),
            "cancelled popup did not fall back to the game folder");
    require(bootStages.find("saves-in-game-folder step=device-selection error=1223") != std::string::npos,
            "fallback reason was not recorded");
    storage::WriteAtomic(install / "Save" / "file2.sav", "fallback save");
    require(read(install / "Save" / "file2.sav") == "fallback save" && flushes == 0,
            "game folder save failed or flushed the container");
    storage::Shutdown();
    require(closes == 0, "game folder fallback closed a container");
    bool unmounted = false;
    try { storage::SaveDirectory(); } catch (const std::logic_error&) { unmounted = true; }
    require(unmounted, "shutdown left storage usable");

    nextSelection = ERROR_SUCCESS;
    storage::Mount();
    storage::Mount(1);
    require(selections == 2 && displays == 2, "repeat mount showed the popup again");
    require(fs::exists(profileRoot / "Save" / "file2.sav"), "fallback save was not adopted into the container");
    require(fs::is_directory(install / "config") && fs::is_directory(install / "logs"),
            "config and logs were not kept in the game folder");
    const fs::path saves(storage::SaveDirectory());
    require(saves.generic_string() == (profileRoot / "Save").generic_string(), "saves are not in the container");
    require(read(saves / "file1.sav") == "game folder save", "game folder saves were not adopted");
    require(read(install / "Save" / "file1.sav") == "game folder save", "adoption changed the game folder copy");

    const fs::path saveFile = saves / "file1.sav";
    const std::string saveBytes("save\0binary\xff", 12);
    int before = flushes;
    storage::WriteAtomic(saveFile, saveBytes);
    require(read(saveFile) == saveBytes && flushes == before + 1, "atomic write was not flushed");
    require(!fs::exists(fs::path(saveFile.string() + ".tmp")), "atomic temporary remains");
    const fs::path completed = saves / "completed.tmp";
    const std::string replacedBytes("replacement\0bytes", 17);
    write(completed, replacedBytes);
    before = flushes;
    storage::Replace(completed, saveFile);
    require(!fs::exists(completed) && read(saveFile) == replacedBytes, "Replace did not move completed bytes");
    require(flushes == before + 1, "Replace was not flushed");
    storage::Commit();
    storage::Shutdown();
    storage::Shutdown();
    require(closes == 1, "container was not closed exactly once");
    bool rejected = false;
    try { storage::WriteAtomic(saveFile, "must not replace"); }
    catch (const std::logic_error&) { rejected = true; }
    require(rejected, "unmounted storage accepted a write");

    write(install / "Save" / "file1.sav", "newer game folder save");
    storage::Mount();
    require(selections == 3, "remount did not show the popup");
    require(read(saveFile) == replacedBytes, "save lost across remount or adopted twice");
    storage::Shutdown();

    // A profile that launched before still takes PC saves into empty slots, once per copy.
    write(install / "Save" / "file3.sav", "pc save");
    storage::Mount();
    require(read(saves / "file3.sav") == "pc save", "PC save did not fill an empty slot");
    storage::Shutdown();
    fs::remove(saves / "file3.sav");
    storage::Mount();
    require(!fs::exists(saves / "file3.sav"), "save deleted in game came back");
    storage::Shutdown();
    write(install / "Save" / "file3.sav", "newer pc save");
    HANDLE pc = CreateFileA((install / "Save" / "file3.sav").string().c_str(), FILE_WRITE_ATTRIBUTES, 0, NULL,
                            OPEN_EXISTING, 0, NULL);
    FILETIME later = { 0, 0x7fffffff };
    require(pc != INVALID_HANDLE_VALUE && SetFileTime(pc, NULL, NULL, &later), "fixture stamp failed");
    CloseHandle(pc);
    storage::Mount();
    require(read(saves / "file3.sav") == "newer pc save", "newer PC save did not fill the empty slot");
    storage::Shutdown();
    std::cout << "profile storage popup/adopt/write/cancel/remount PASS\n";
    return 0;
} catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; } }
''')
            exe = folder / 'contract.exe'
            sources = [audit, contract, PLATFORM_BASE / 'sources/filesystem/filesystem.cpp',
                       PLATFORM_BASE / 'sources/storage/atomic_file.cpp', PLATFORM_BASE / 'sources/async/native.cpp']
            command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/DNOMINMAX',
                       '/I' + str(include), '/I' + str(ROOT / 'platform/shipyard'),
                       '/I' + str(PLATFORM_BASE), '/I' + str(PLATFORM_BASE / 'sources'), *map(str, sources),
                       '/Fo:' + str(folder) + '/', '/Fe:' + str(exe)]
            result = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe), str(install), str(profile)], cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('remount PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
