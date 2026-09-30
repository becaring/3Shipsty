"""Exercise the maintained raw storage implementation using real host files."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/shipyard'))
from tools.shipyard.tests.test_binary import host_environment, PLATFORM_BASE


class RawSaveStorageTests(unittest.TestCase):
    def test_mount_write_replace_shutdown_and_remount(self):
        compiler, env = host_environment()
        with tempfile.TemporaryDirectory(prefix='raw-storage-', dir=ROOT / 'scratch') as temp:
            folder = Path(temp)
            install = folder / 'install'
            # The target device prefix is the only production-source change.
            source = (ROOT / 'platform/shipyard/save-storage/storage.cpp').read_text()
            self.assertEqual(source.count('game:\\\\'), 4)
            source = source.replace('game:\\\\', install.as_posix() + '/')
            audit = folder / 'storage.cpp'
            audit.write_text(source)
            stub = folder / 'include/xenos/native_display.h'
            stub.parent.mkdir(parents=True)
            stub.write_text('#pragma once\nnamespace Fast { void InitializeNativeDisplay(); }\n')
            contract = folder / 'contract.cpp'
            contract.write_text(r'''
#include "save-storage/storage.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
namespace fs = xbox_compat::filesystem;
namespace storage = Shipyard::Storage;
int displayInitializations = 0;
namespace Fast { void InitializeNativeDisplay() { ++displayInitializations; } }
void require(bool condition, const char* reason) {
    if (!condition) throw std::runtime_error(reason);
}
std::string read(const fs::path& path) {
    std::ifstream file(path.c_str(), std::ios::binary);
    require(file.is_open(), "could not read persisted file");
    return std::string(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}
int main(int argc, char** argv) { try {
    const fs::path install(argv[1]);
    require(!fs::exists(install), "fixture install directory must start absent");
    storage::Mount();
    storage::Mount(1);
    require(displayInitializations == 1, "repeat mount was not idempotent");
    const fs::path config = install / "config";
    const fs::path logs = install / "logs";
    const fs::path saves(storage::SaveDirectory());
    require(fs::is_directory(config) && fs::is_directory(logs) && fs::is_directory(saves),
            "mount did not create config, logs and Save directories");
    require(saves.generic_string() == (install / "Save").generic_string(), "wrong save directory");
    const fs::path configFile = config / "shipofharkinian.json";
    const fs::path logFile = logs / "boot.log";
    const fs::path saveFile = saves / "slot1.sav";
    const std::string saveBytes("save\0binary\xff", 12);
    storage::WriteAtomic(configFile, "{\"volume\":25}");
    storage::WriteAtomic(logFile, "boot complete\n");
    storage::WriteAtomic(saveFile, "previous save");
    storage::WriteAtomic(saveFile, saveBytes);
    require(read(saveFile) == saveBytes, "atomic replacement changed binary bytes");
    require(!fs::exists(fs::path(saveFile.string() + ".tmp")), "atomic temporary remains");
    const fs::path completed = saves / "completed.tmp";
    const std::string replacedBytes("replacement\0bytes", 17);
    { std::ofstream file(completed.c_str(), std::ios::binary); file.write(replacedBytes.data(), replacedBytes.size());
      file.close(); require(!file.fail(), "fixture completed file write failed"); }
    storage::Replace(completed, saveFile);
    require(!fs::exists(completed) && read(saveFile) == replacedBytes, "Replace did not move completed bytes");
    storage::Commit();
    storage::Shutdown();
    storage::Shutdown();
    bool rejected = false;
    try { storage::WriteAtomic(saveFile, "must not replace"); }
    catch (const std::logic_error&) { rejected = true; }
    require(rejected, "unmounted storage accepted a write");
    require(read(saveFile) == replacedBytes, "Shutdown altered saved bytes");
    storage::Mount();
    require(displayInitializations == 2, "remount did not initialize");
    require(read(configFile) == "{\"volume\":25}", "config lost across remount");
    require(read(logFile) == "boot complete\n", "logs lost across remount");
    require(read(saveFile) == replacedBytes, "save lost across remount");
    require(!fs::exists(config / "slot1.sav") && !fs::exists(saves / "shipofharkinian.json") &&
            !fs::exists(saves / "boot.log"), "storage directories were mixed");
    storage::Shutdown();
    std::cout << "raw storage real-file mount/write/replace/remount PASS\n";
    return 0;
} catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; } }
''')
            exe = folder / 'contract.exe'
            sources = [audit, contract, PLATFORM_BASE / 'sources/filesystem/filesystem.cpp',
                       PLATFORM_BASE / 'sources/storage/atomic_file.cpp', PLATFORM_BASE / 'sources/async/native.cpp']
            command = [str(compiler), '/nologo', '/std:c++20', '/EHsc', '/MD', '/DNOMINMAX',
                       '/I' + str(folder / 'include'), '/I' + str(ROOT / 'platform/shipyard'),
                       '/I' + str(PLATFORM_BASE), '/I' + str(PLATFORM_BASE / 'sources'), *map(str, sources),
                       '/Fo:' + str(folder) + '/', '/Fe:' + str(exe)]
            result = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe), str(install)], cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('remount PASS', result.stdout)
