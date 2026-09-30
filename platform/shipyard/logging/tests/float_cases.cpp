#if ORIGINAL_SPDLOG
#include <spdlog/fmt/fmt.h>
#else
#include "platform/shipyard/logging/format/format.h"
#endif
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
template <class T> std::string formatted(const char *pattern, T value) {
#if ORIGINAL_SPDLOG
    return fmt::format(fmt::runtime(pattern), value);
#else
    return fmt::format(pattern, value);
#endif
}
template <class T> void check(T value, unsigned index) {
    const char *formats[] = {"{}",      "{:}",      "{:+}",    "{: }",    "{:#}",   "{:20}",
                             "{:<20}",  "{:^21}",   "{:*>24}", "{:*^25}", "{:020}", "{:+020}",
                             "{:#020}", "{:+#020}", "{:.0f}",  "{:.3f}",  "{:.6e}", "{:.6g}"};
    for (unsigned i = 0; i < sizeof(formats) / sizeof(formats[0]); ++i)
        std::printf("%u:%u:%u:%s\n", static_cast<unsigned>(sizeof(T)), index, i, formatted(formats[i], value).c_str());
}
int main() {
    const unsigned __int64 d[] = {0,
                                  0x8000000000000000ULL,
                                  1,
                                  0x8000000000000001ULL,
                                  0x000fffffffffffffULL,
                                  0x0010000000000000ULL,
                                  0x7fefffffffffffffULL,
                                  0xffefffffffffffffULL,
                                  0x7ff0000000000000ULL,
                                  0xfff0000000000000ULL,
                                  0x7ff8000000000000ULL,
                                  0xfff8000000000000ULL,
                                  0x3ff0000000000000ULL,
                                  0x3fb999999999999aULL};
    const unsigned f[] = {0,          0x80000000, 1,          0x80000001, 0x007fffff, 0x00800000, 0x7f7fffff,
                          0xff7fffff, 0x7f800000, 0xff800000, 0x7fc00000, 0xffc00000, 0x3f800000, 0x3dcccccd};
    for (unsigned i = 0; i < sizeof(d) / sizeof(d[0]); ++i) {
        double x;
        std::memcpy(&x, d + i, 8);
        check(x, i);
    }
    for (unsigned i = 0; i < sizeof(f) / sizeof(f[0]); ++i) {
        float x;
        std::memcpy(&x, f + i, 4);
        check(x, i);
    }
    unsigned __int64 state = 0x123456789abcdef0ULL;
    for (unsigned i = 0; i < 10000; ++i) {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        double x;
        std::memcpy(&x, &state, 8);
        check(x, 100 + i);
        unsigned bits = static_cast<unsigned>(state >> 32);
        float y;
        std::memcpy(&y, &bits, 4);
        check(y, 100 + i);
    }
    const double thresholds[] = {0.00001, 0.0001,           0.001, 999999.9, 1000000, 9999999, 10000000, 1e15,
                                 1e16,    1.23456789012345, 0.5,   1.5,      2.5,     3.5};
    for (unsigned i = 0; i < sizeof(thresholds) / sizeof(thresholds[0]); ++i) {
        check(thresholds[i], 20000 + i);
        check(static_cast<float>(thresholds[i]), 20000 + i);
    }
    // Packed-argument boundary plus named floats and writer entry points.
    std::puts(fmt::format("{} {} {} {} {} {} {} {} {} {} {} {} {} {} {}", 0.1f, 0.1, 0.1f, 0.1, 0.1f, 0.1, 0.1f, 0.1,
                          0.1f, 0.1, 0.1f, 0.1, 0.1f, 0.1, 0.1f)
                  .c_str());
    std::puts(fmt::format("{value}", fmt::arg("value", 0.1f)).c_str());
    std::puts(fmt::format("{:{}}|{:{}}", 0.1f, 20, 0.1, 20).c_str());
    std::puts(fmt::format("{}", static_cast<long double>(1.23456789012345)).c_str());
#if ORIGINAL_SPDLOG
    std::puts(fmt::format("{}|{}", 0.1f, 0.1).c_str());
#else
    fmt::MemoryWriter writer;
    writer << 0.1f << '|' << 0.1;
    std::puts(writer.str().c_str());
#endif
}
