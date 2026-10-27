"""Publish the immutable timer frequency once across service callers.

Interlocked publication keeps the 64-bit frequency initialized on Xenon before
another thread reads it. Tick sampling and seconds conversion stay unchanged.
"""
from source_anchor import replace_once


def project(source):
    return replace_once(source, '''double Shipyard_Time() {
    LARGE_INTEGER tick, freq;
    QueryPerformanceCounter(&tick);
    QueryPerformanceFrequency(&freq);
    return double(tick.QuadPart) / double(freq.QuadPart);
}''', '''double Shipyard_Time() {
    static volatile LONG frequencyReady = 0;
    static LARGE_INTEGER frequency;
    if (InterlockedCompareExchange(&frequencyReady, 2, 2) != 2) {
        if (InterlockedCompareExchange(&frequencyReady, 1, 0) == 0) {
            QueryPerformanceFrequency(&frequency);
            InterlockedExchange(&frequencyReady, 2);
        } else {
            while (InterlockedCompareExchange(&frequencyReady, 2, 2) != 2)
                YieldProcessor();
        }
    }
    LARGE_INTEGER tick;
    QueryPerformanceCounter(&tick);
    return double(tick.QuadPart) / double(frequency.QuadPart);
}''')
