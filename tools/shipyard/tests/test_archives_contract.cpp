#include <zip.h>
#include <zlib.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include "filesystem/filesystem.h"

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    xbox_compat::filesystem::InitWorkingDirectory(argv[1]);
    const char* names[] = { "soh.o2r", "oot.o2r" };
    for (int a = 0; a < 2; ++a) {
        int error = 0;
        zip_t* archive = zip_open(names[a], ZIP_RDONLY | ZIP_CHECKCONS, &error);
        if (!archive) { std::printf("open failed %d\n", error); return 3; }
        zip_int64_t count = zip_get_num_entries(archive, 0);
        unsigned long long total = 0;
        std::vector<unsigned char> buffer(65536);
        for (zip_uint64_t i = 0; i < static_cast<zip_uint64_t>(count); ++i) {
            zip_stat_t info;
            if (zip_stat_index(archive, i, 0, &info)) return 4;
            zip_file_t* file = zip_fopen_index(archive, i, 0);
            if (!file) return 5;
            zip_uint64_t read = 0;
            uLong crc = crc32(0, Z_NULL, 0);
            for (;;) {
                zip_int64_t n = zip_fread(file, &buffer[0], buffer.size());
                if (n < 0) return 6;
                if (!n) break;
                read += static_cast<zip_uint64_t>(n);
                crc = crc32(crc, &buffer[0], static_cast<uInt>(n));
            }
            if (read != info.size || crc != info.crc || zip_fclose(file)) return 7;
            total += read;
        }
        zip_file_t* version = zip_fopen(archive, "portVersion", 0);
        unsigned char actual[8] = {};
        const unsigned char expected[] = {1, 0, 9, 0, 2, 0, 3};
        if (!version || zip_fread(version, actual, sizeof(actual)) != 7 ||
            std::memcmp(expected, actual, 7) || zip_fclose(version)) return 8;
        if (zip_fopen(archive, "shipyard-deliberately-absent", 0) != NULL ||
            zip_error_code_zip(zip_get_error(archive)) != ZIP_ER_NOENT) return 9;
        if (zip_close(archive)) return 10;
        std::printf("%s %lld entries %llu bytes all CRCs verified\n", names[a], count, total);
    }
    int error = 0;
    if (zip_open("shipyard-deliberately-absent.o2r", ZIP_RDONLY, &error) || error != ZIP_ER_NOENT) {
        std::printf("missing archive error %d\n", error); return 11;
    }
    const char* entryName = "assets/\xc3\xa9.txt";
    zip_t* write = zip_open(argv[2], ZIP_CREATE | ZIP_TRUNCATE, &error);
    if (!write) return 12;
    zip_source_t* bytes = zip_source_buffer(write, "first", 5, 0);
    if (!bytes || zip_file_add(write, entryName, bytes, ZIP_FL_ENC_UTF_8) < 0 || zip_close(write)) return 13;
    write = zip_open(argv[2], ZIP_CREATE, &error);
    if (!write) return 14;
    bytes = zip_source_buffer(write, "replacement", 11, 0);
    if (!bytes || zip_file_add(write, entryName, bytes, ZIP_FL_ENC_UTF_8 | ZIP_FL_OVERWRITE) < 0 || zip_close(write)) return 15;
    write = zip_open(argv[2], ZIP_RDONLY | ZIP_CHECKCONS, &error);
    if (!write || zip_get_num_entries(write, 0) != 1) return 16;
    zip_file_t* read = zip_fopen(write, entryName, 0);
    char result[12] = {};
    if (!read || zip_fread(read, result, 12) != 11 || std::strcmp(result, "replacement") || zip_fclose(read) || zip_close(write)) return 17;
    std::printf("archive create/UTF-8-entry/overwrite/reopen verified\n");
    return 0;
}
