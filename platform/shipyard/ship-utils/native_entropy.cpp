#include "ship-utils/support.h"
#include "entropy/native.h"
#include <stdexcept>
#ifndef _XBOX
#include <random>
#endif

uint32_t Shipyard::Utils::DeviceRandom() {
#ifdef _XBOX
    // Match random_device's 32-bit result. XNet initialization belongs to the
    // application, as with the native libzip entropy boundary.
    uint32_t seed;
    if (!Shipyard::Entropy::FillBytes(reinterpret_cast<unsigned char*>(&seed), sizeof(seed))) {
        throw std::runtime_error("XNetRandom failed to seed ShipUtils");
    }
    return seed;
#else
    return std::random_device()();
#endif
}
