#include "ship-utils/support.h"
#include <stdexcept>
#ifdef _XBOX
#include <xtl.h>
#else
#include <random>
#endif

uint32_t Shipyard::Utils::DeviceRandom() {
#ifdef _XBOX
    // Match random_device's 32-bit result. XNet initialization belongs to the
    // application, as with the existing native libzip entropy boundary.
    uint32_t seed;
    if (XNetRandom(reinterpret_cast<BYTE*>(&seed), sizeof(seed)) != 0) {
        throw std::runtime_error("XNetRandom failed to seed ShipUtils");
    }
    return seed;
#else
    return std::random_device()();
#endif
}
