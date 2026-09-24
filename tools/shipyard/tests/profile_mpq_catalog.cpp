#include <StormLib.h>
#include <cstdio>

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    for (int index = 1; index < argc; ++index) {
        HANDLE archive = NULL;
        if (!SFileOpenArchive(argv[index], 0, MPQ_OPEN_READ_ONLY, &archive)) {
            std::fprintf(stderr, "open failed: %s (%lu)\n", argv[index], (unsigned long)GetLastError());
            return 1;
        }
        SFILE_FIND_DATA data = {};
        HANDLE scan = SFileFindFirstFile(archive, "*", &data, NULL);
        if (scan) {
            do {
                std::printf("%d\t%lu\t%lu\t%s\n", index - 1, (unsigned long)data.dwFileSize,
                            (unsigned long)data.dwCompSize, data.cFileName);
            } while (SFileFindNextFile(scan, &data));
            SFileFindClose(scan);
        }
        SFileCloseArchive(archive);
    }
    return 0;
}
