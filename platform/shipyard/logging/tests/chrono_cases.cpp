#include "platform/shipyard/async/native.h"
#if USE_STD_CHRONO
#include <chrono>
namespace C = std::chrono;
typedef std::ratio<1, 3> Third;
typedef std::ratio<1, 5> Fifth;
#else
#include "platform/shipyard/logging/chrono/chrono.h"
namespace C = Shipyard::Async::chrono;
typedef Shipyard::Logging::chrono::ratio<1, 3> Third;
typedef Shipyard::Logging::chrono::ratio<1, 5> Fifth;
#endif
#include <cassert>
#include <cstdio>
#include <stdint.h>
#include <type_traits>
int main() {
    const int64_t values[] = {-2147483647, -1000001, -1501, -1000, -999,    -1,        0,
                              1,           999,      1000,  1501,  1000001, 2147483647};
    for (int i = 0; i < 13; ++i) {
        C::milliseconds ms(values[i]);
        printf("%lld,%lld,%lld\n", (long long)C::duration_cast<C::seconds>(ms).count(),
               (long long)C::duration_cast<C::microseconds>(ms).count(), (long long)(ms + C::seconds(2)).count());
        C::system_clock::time_point t(ms);
        assert((t + C::milliseconds(8) - t) == C::milliseconds(8));
        assert((t - C::milliseconds(8)) < t);
        C::milliseconds frac = C::duration_cast<C::milliseconds>(t.time_since_epoch()) -
                               C::duration_cast<C::seconds>(t.time_since_epoch());
        printf("fraction %lld\n", (long long)frac.count());
    }
    C::duration<int64_t, Third> thirds(-7);
    C::duration<int64_t, Fifth> fifths = C::duration_cast<C::duration<int64_t, Fifth>>(thirds);
    printf("ratio %lld\n", (long long)fifths.count());
    C::duration<double> fractional(C::milliseconds(-1500));
    assert(fractional.count() == -1.5);
    assert(C::duration_cast<C::seconds>(C::duration<double>(-1.9)).count() == -1);
    static_assert(!std::is_convertible<C::milliseconds, C::seconds>::value, "implicit truncation forbidden");
    static_assert(std::is_convertible<C::seconds, C::milliseconds>::value, "exact period expansion allowed");
    for (int value = -10000; value < 10000; value += 999) {
        assert(C::system_clock::to_time_t(C::system_clock::from_time_t(value)) == value);
    }
    C::steady_clock::time_point before = C::steady_clock::now();
    Sleep(10);
    C::steady_clock::time_point after = C::steady_clock::now();
    assert(after >= before);
    assert(C::duration_cast<C::milliseconds>(after - before).count() >= 5);
    std::time_t now = std::time(0), native = C::system_clock::to_time_t(C::system_clock::now());
    assert(native >= now - 2 && native <= now + 2);
    puts("PASS duration casts, signed fractions, ratio arithmetic, UTC epoch, monotonic native clock");
}
