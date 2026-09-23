#include <StormLib.h>
#include <cstdio>
#include <vector>

int main(int argc, char** argv) {
    SetErrorMode(SEM_NOGPFAULTERRORBOX);
    if (argc != 2) return 2;
    HANDLE archive = NULL;
    if (!SFileOpenArchive(argv[1], 0, MPQ_OPEN_READ_ONLY, &archive)) {
        std::fprintf(stderr, "MPQ open failed: %lu\n", (unsigned long)GetLastError());
        return 1;
    }
    HANDLE list = NULL;
    if (!SFileOpenFileEx(archive, "(listfile)", 0, &list)) {
        std::fprintf(stderr, "MPQ listfile open failed: %lu\n", (unsigned long)GetLastError());
        SFileCloseArchive(archive);
        return 1;
    }
    const DWORD size = SFileGetFileSize(list, NULL);
    DWORD flags = 0;
    DWORD compressedSize = 0;
    SFileGetFileInfo(list, SFileInfoFlags, &flags, sizeof(flags), NULL);
    SFileGetFileInfo(list, SFileInfoCompressedSize, &compressedSize, sizeof(compressedSize), NULL);
    std::vector<char> contents(size);
    DWORD read = 0;
    if (!SFileReadFile(list, contents.data(), size, &read, NULL) || read != size) {
        std::fprintf(stderr, "MPQ listfile read failed: %lu (%lu/%lu bytes)\n",
                     (unsigned long)GetLastError(), (unsigned long)read, (unsigned long)size);
        SFileCloseFile(list);
        SFileCloseArchive(archive);
        return 1;
    }
    std::printf("MPQ listfile read: %s (%lu bytes, %lu compressed, flags 0x%08lX)\n",
                argv[1], (unsigned long)size, (unsigned long)compressedSize,
                (unsigned long)flags);
    SFileCloseFile(list);
    SFileCloseArchive(archive);
    return 0;
}
