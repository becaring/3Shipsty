#ifdef SHIPYARD_ORIGINAL
#include <filesystem>
namespace fs = std::filesystem;
#else
#include "filesystem.h"
#include "Directory.h"
namespace fs = xbox_compat::filesystem;
#endif
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#ifdef SHIPYARD_ORIGINAL
#define NOMINMAX
#include <windows.h>
#endif

static void check(bool condition, const char* why) {
    if (!condition) throw std::runtime_error(why);
}
static void put(const fs::path& name, const std::string& bytes) {
    std::ofstream stream(name, std::ios::binary);
    stream << bytes; stream.close(); check(!stream.fail(), "fixture write");
}
static std::string get(const fs::path& name) {
    std::ifstream stream(name, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}
int main(int argc, char** argv) {
    try {
        check(argc == 2, "isolated fixture path required");
        fs::path root(argv[1]); std::error_code error;
#ifdef SHIPYARD_TEST_LOGICAL_CWD
        check(fs::current_path(error).empty() && error, "uninitialized logical cwd");
        fs::InitWorkingDirectory(root);
        check(fs::absolute("a/../b").lexically_normal() == (root / "b"), "logical cwd");
#endif
        check(fs::create_directory(root / "Save"), "new directory");
        check(!fs::create_directory(root / "Save", error) && !error, "existing directory");
        check(!fs::create_directory(root / "absent/child", error) && error, "nonrecursive creation");
        fs::path save = root / "Save/slot.sav", temp = root / "Save/slot.tmp";
        put(save, "old"); put(temp, "new modern save bytes");
        check(!fs::create_directory(save, error) && error, "file blocks directory");
        fs::rename(temp, save, error);
        check(!error && !fs::exists(temp) && get(save) == "new modern save bytes", "replace committed save");
        fs::rename(temp, save, error);
        check(error && get(save) == "new modern save bytes", "failed rename preserves destination");
        fs::path second = root / "Save/copy.sav";
        check(fs::copy_file(save, second), "copy to free slot");
        check(get(second) == get(save), "copy exact bytes");
        put(second, "occupied");
        check(!fs::copy_file(save, second, error) && error && get(second) == "occupied", "copy refuses overwrite");
        check(!fs::copy_file(save, save, error) && error && get(save) == "new modern save bytes", "self copy safe");
        bool threw = false;
        try { fs::copy_file(save, second); }
        catch (const fs::filesystem_error& ex) { threw = ex.code() && ex.path1() == save && ex.path2() == second; }
        check(threw, "copy exception carries both paths");
        check(!fs::copy_file(root / "missing", root / "new", error) && error, "missing copy source");
        check(!fs::copy_file(root / "Save", root / "new", error) && error, "directory copy rejected");
        put(temp, std::string(1024 * 1024 + 17, 'z'));
        check(fs::copy_file(temp, root / "large copy.bin", error) && !error &&
              get(temp) == get(root / "large copy.bin"), "large copy exact bytes");
        fs::remove(temp);
        check(fs::create_directories(root / "mods/nested with spaces"), "recursive creation");
        put(root / "mods/nested with spaces/test.o2r", "archive");
        std::set<std::string> names;
        for (fs::recursive_directory_iterator it(root / "mods"), end; it != end; ++it)
            names.insert(it->path().filename().string());
        check(names.size() == 2 && names.count("test.o2r"), "recursive enumeration");
#ifndef SHIPYARD_ORIGINAL
        check(Directory::ListFiles((root / "mods").string()).size() == 1, "actual projected Directory");
        check(fs::path("game:/assets/../mods/a.o2r").lexically_normal().generic_string() == "game:/mods/a.o2r", "Xbox mount normalization");
        check(fs::path("game:\\mods/a.o2r").filename() == "a.o2r", "slash variants");
        check(!fs::exists("bad?name", error) && error, "invalid native name");
        check(!fs::exists(fs::path(std::string("bad\0name", 8)), error) && error, "embedded NUL rejected");
        check(!fs::exists("\\\\server\\share", error) && error, "unsupported UNC reports error");
        check(!fs::exists("", error) && !error, "empty existence query");
        check(!fs::create_directory("", error) && error, "empty directory error");
        HANDLE held = CreateFileA(save.string().c_str(), GENERIC_READ, 0, NULL, OPEN_EXISTING,
                                  FILE_ATTRIBUTE_NORMAL, NULL);
        check(held != INVALID_HANDLE_VALUE, "hold destination without sharing");
        put(temp, "pending");
        fs::rename(temp, save, error);
        bool blocked = error && fs::exists(temp);
        CloseHandle(held);
        check(blocked && get(save) == "new modern save bytes", "sharing failure preserves committed and pending save");
        fs::remove(temp);
        check(SetFileAttributesA(second.string().c_str(), FILE_ATTRIBUTE_READONLY) != 0, "readonly fixture");
        bool denied = !fs::remove(second, error) && error;
        SetFileAttributesA(second.string().c_str(), FILE_ATTRIBUTE_NORMAL);
        check(denied && get(second) == "occupied", "readonly asset failure preserves bytes");
        std::vector<unsigned char> bytes;
        check(fs::write_file(temp, "flushed", 7, error) && !error, "native write");
        check(fs::read_file(temp, bytes, error) && bytes.size() == 7 && !error, "native read");
        fs::remove(temp);
#endif
        check(!fs::remove(root / "missing", error) && !error, "remove missing succeeds");
        check(!fs::remove(root / "Save", error) && error, "nonempty directory failure");
        check(fs::file_size(save) == 21, "file size");
        fs::file_time_type stamp = fs::last_write_time(save);
        check(stamp == fs::last_write_time(save, error) && !error, "unchanged spoiler timestamp cache hit");
        HANDLE timed = CreateFileA(save.string().c_str(), FILE_WRITE_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                  NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        check(timed != INVALID_HANDLE_VALUE, "open timestamp fixture");
        FILETIME changedTime; changedTime.dwHighDateTime = 0x01dd0000; changedTime.dwLowDateTime = 123456789;
        check(SetFileTime(timed, NULL, NULL, &changedTime) != 0, "set deterministic fixture time");
        CloseHandle(timed);
        fs::file_time_type changedStamp = fs::last_write_time(save);
        check(stamp != changedStamp && changedStamp == fs::last_write_time(save), "changed spoiler invalidates cache");
        check(fs::last_write_time(root / "missing", error) == fs::file_time_type::min() && error,
              "missing timestamp sentinel and error");
        threw = false;
        try { fs::last_write_time(root / "missing"); }
        catch (const fs::filesystem_error& ex) { threw = ex.code() && ex.path1() == root / "missing"; }
        check(threw, "timestamp throwing path");
#ifndef _XBOX
        // Runner creates a native junction entirely inside this owned fixture.
        put(root / "link-target/linked.o2r", "linked archive");
        unsigned plainCount = 0, followCount = 0;
        for (fs::recursive_directory_iterator it(root / "link-area"), end; it != end; ++it) ++plainCount;
        for (fs::recursive_directory_iterator it(root / "link-area", fs::directory_options::follow_directory_symlink), end;
             it != end; ++it) ++followCount;
        check(plainCount == 1 && followCount == 2, "mod link traversal respects option");
        check(fs::is_directory(root / "link-area/link"), "status follows directory link");
        check(fs::last_write_time(root / "link-area/link/linked.o2r") ==
              fs::last_write_time(root / "link-target/linked.o2r"), "linked timestamp refers to target");
        check(fs::last_write_time(root / "link-area/link") == fs::last_write_time(root / "link-target"),
              "directory link timestamp follows target");
        check(fs::remove(root / "link-target/linked.o2r") && fs::remove(root / "link-target"), "remove fixture target");
        check(!fs::exists(root / "link-area/link"), "dangling link target does not exist");
        followCount = 0;
        for (fs::recursive_directory_iterator it(root / "link-area", fs::directory_options::follow_directory_symlink), end;
             it != end; ++it) ++followCount;
        check(followCount == 1, "dangling link is listed but not descended");
        check(fs::last_write_time(root / "link-area/link", error) == fs::file_time_type::min() && error,
              "dangling link timestamp reports error");
        check(fs::remove(root / "link-area/link"), "remove dangling link itself");
#else
        fs::recursive_directory_iterator optionCompile(root, fs::directory_options::follow_directory_symlink, error);
        check(!fs::platform_properties::directory_symlinks, "Xbox exposes lack of filesystem symlink support");
#endif
        std::cout << "save copy/replace/errors, directory creation and recursive enumeration pass\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
