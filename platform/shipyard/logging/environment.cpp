// Xbox has no process environment. Explicit, immutable launch configuration.
// File handle/read pattern follows SoH360 platform/xbox360/platform.cpp ReadPath.
#include "environment.h"
#if defined(_XBOX)
#include <xtl.h>
#else
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include <string>
#include <vector>

namespace {
struct Entry {
    std::string name;
    std::string value;
    Entry(const std::string& n, const std::string& v) : name(n), value(v) {}
};
std::vector<Entry> values;
bool initialized = false;

struct FileHandle {
    HANDLE handle;
    explicit FileHandle(HANDLE h) : handle(h) {}
    ~FileHandle() { if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle); }
private:
    FileHandle(const FileHandle&);
    FileHandle& operator=(const FileHandle&);
};

bool valid_name(const std::string& name) {
    if (name.empty()) return false;
    for (size_t i = 0; i < name.size(); ++i) {
        const char c = name[i];
        if (c != '_' && !(c >= 'A' && c <= 'Z') && !(c >= 'a' && c <= 'z') &&
            !(i > 0 && c >= '0' && c <= '9')) return false;
    }
    return true;
}

bool parse(const std::string& text, std::vector<Entry>& result) {
    if (text.find('\0') != std::string::npos) return false;
    size_t cursor = 0;
    while (cursor < text.size()) {
        size_t end = text.find('\n', cursor);
        if (end == std::string::npos) end = text.size();
        std::string line = text.substr(cursor, end - cursor);
        cursor = end + 1;
        if (!line.empty() && line[line.size() - 1] == '\r') line.resize(line.size() - 1);
        const size_t first = line.find_first_not_of(" \t");
        if (first == std::string::npos || line[first] == '#') continue;
        const size_t equals = line.find('=');
        if (equals == std::string::npos) return false;
        const std::string name = line.substr(0, equals);
        if (!valid_name(name)) return false;
        for (size_t i = 0; i < result.size(); ++i)
            if (result[i].name == name) return false;
        result.push_back(Entry(name, line.substr(equals + 1)));
    }
    return true;
}
}

extern "C" int ShipyardEnv_LoadFromFile(const char* path) {
    if (initialized) return SHIPYARD_ENV_ALREADY_INITIALIZED;
    if (!path || !*path) return SHIPYARD_ENV_INVALID;
    FileHandle file(CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL));
    if (file.handle == INVALID_HANDLE_VALUE) {
        if (GetLastError() == ERROR_FILE_NOT_FOUND) {
            initialized = true;
            return SHIPYARD_ENV_ABSENT;
        }
        return SHIPYARD_ENV_IO_ERROR;
    }
    DWORD high = 0;
    DWORD length = GetFileSize(file.handle, &high);
    if (length == INVALID_FILE_SIZE || high != 0) return SHIPYARD_ENV_IO_ERROR;
    // Explicit configuration size limit; reject rather than truncate.
    if (length > 1024 * 1024) return SHIPYARD_ENV_INVALID;
    try {
        std::string text(length, '\0');
        DWORD actual = 0;
        if (length && (!ReadFile(file.handle, &text[0], length, &actual, NULL) || actual != length))
            return SHIPYARD_ENV_IO_ERROR;
        std::vector<Entry> candidate;
        if (!parse(text, candidate)) return SHIPYARD_ENV_INVALID;
        values.swap(candidate);
        initialized = true;
        return SHIPYARD_ENV_LOADED;
    } catch (...) {
        return SHIPYARD_ENV_IO_ERROR;
    }
}

extern "C" char* ShipyardEnv_Get(const char* name) {
    if (!name || !initialized) return NULL;
    for (size_t i = 0; i < values.size(); ++i)
        if (values[i].name == name) return const_cast<char*>(values[i].value.c_str());
    return NULL;
}
