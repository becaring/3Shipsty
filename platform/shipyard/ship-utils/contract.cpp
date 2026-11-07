#include "soh/ShipUtils.h"
#include "soh/Enhancements/randomizer/3drando/random.hpp"
#include <bit>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <type_traits>

uint32_t next32(); // Wrapper definition from random.cpp.

static uint64_t digest = 1469598103934665603ULL;
static void record(uint64_t value) {
    for (int byte = 0; byte < 8; ++byte) {
        digest ^= (value >> (byte * 8)) & 255;
        digest *= 1099511628211ULL;
    }
}
static uint32_t reference_next(uint64_t& state) {
    state = state * 6364136223846793005ULL + 11634580027462260723ULL;
    uint32_t value = static_cast<uint32_t>(((state >> 18) ^ state) >> 27);
    return std::rotr(value, static_cast<int>(state >> 59));
}
static uint32_t reference_range(uint32_t min, uint32_t max, uint64_t& state) {
    if (min == max) return min;
    const uint32_t count = max - min;
    const uint32_t cutoff = UINT32_MAX - UINT32_MAX % count;
    for (;;) {
        const uint32_t candidate = reference_next(state);
        if (candidate <= cutoff) return min + candidate % count;
    }
}

int main() {
    const uint64_t seeds[] = { 0, 1, 2, 42, 0x123456789abcdef0ULL, 0xffffffffffffffffULL, 0x8000000000000000ULL, 0xffffffffULL };
    const uint32_t limits[] = { 0, 1, 2, 3, 17, 1000, 0x80000001U, UINT32_MAX };
    for (unsigned seed = 0; seed < sizeof(seeds) / sizeof(seeds[0]); ++seed) {
        uint64_t state, expected = seeds[seed];
        ShipUtils::RandInit(seeds[seed], &state);
        for (int i = 0; i < 4096; ++i) {
            const uint32_t result = ShipUtils::next32(&state);
            assert(result == reference_next(expected) && state == expected);
            record(result); record(state);
        }
        for (unsigned limit = 0; limit < sizeof(limits) / sizeof(limits[0]); ++limit) {
            ShipUtils::RandInit(seeds[seed], &state); expected = seeds[seed];
            for (int i = 0; i < 512; ++i) {
                const uint32_t result = ShipUtils::Random(0, limits[limit], &state);
                assert(result == reference_range(0, limits[limit], expected) && state == expected);
                record(result); record(state);
            }
        }
        ShipUtils::RandInit(seeds[seed], &state); expected = seeds[seed];
        for (int i = 0; i < 4096; ++i) {
            double result = ShipUtils::RandomDouble(&state);
            double wanted = static_cast<double>(reference_next(expected)) / 4294967296.0;
            assert(result == wanted && result >= 0 && result < 1 && state == expected);
            uint64_t bits; memcpy(&bits, &result, sizeof(bits)); record(bits);
        }
        Random_Init(seeds[seed]); ShipUtils::RandInit(seeds[seed], &state);
        for (int i = 0; i < 1024; ++i) {
            assert(next32() == ShipUtils::next32(&state));
            assert(Random(7, 99999) == ShipUtils::Random(7, 99999, &state));
            assert(RandomDouble() == ShipUtils::RandomDouble(&state));
            assert(rando_state == state); record(state);
        }
    }

    uint64_t state = 17;
    std::vector<int> values;
    for (int i = 0; i < 64; ++i) values.push_back(i);
    const std::vector<int>& constant = values;
    static_assert(std::is_same<decltype(ShipUtils::RandomElement(values, &state)), int&>::value);
    static_assert(std::is_same<decltype(ShipUtils::RandomElement(constant, &state)), const int&>::value);
    for (int i = 0; i < 256; ++i) {
        uint64_t expected = state;
        unsigned index = reference_range(0, static_cast<uint32_t>(values.size()), expected);
        int& element = ShipUtils::RandomElement(values, &state);
        assert(&element == &values[index] && state == expected);
        element += 100; record(element);
        expected = state;
        index = reference_range(0, static_cast<uint32_t>(values.size()), expected);
        assert(&ShipUtils::RandomElement(constant, &state) == &values[index] && state == expected);
    }
    while (!values.empty()) {
        uint64_t expected = state;
        unsigned index = reference_range(0, static_cast<uint32_t>(values.size()), expected);
        int wanted = values[index]; const size_t previous = values.size();
        assert(ShipUtils::RandomElement(values, true, &state) == wanted);
        assert(values.size() == previous - 1 && state == expected); record(wanted);
    }
    std::array<int, 4> fixed = { 1, 2, 3, 4 };
    const std::array<int, 4>& const_fixed = fixed;
    const char* words[] = { "one", "two", "three" };
    const int raw[] = { 7, 8, 9 };
    static_assert(std::is_same<decltype(ShipUtils::RandomElement(words, &state)), const char*&>::value);
    static_assert(std::is_same<decltype(ShipUtils::RandomElement(raw, &state)), const int&>::value);
    for (int i = 0; i < 128; ++i) {
        record(ShipUtils::RandomElement(fixed, &state));
        record(ShipUtils::RandomElement(const_fixed, &state));
        record(ShipUtils::RandomElement(raw, &state));
        record(ShipUtils::RandomElement(words, &state)[0]);
    }
    std::set<int> ordered; ordered.insert(77);
    uint64_t previous = state;
    assert(ShipUtils::RandomElementFromSet(ordered, &state) == 77 && state == previous);
    for (int i = 0; i < 64; ++i) ordered.insert(i * 2);
    for (int i = 0; i < 128; ++i) {
        int result = ShipUtils::RandomElementFromSet(ordered, &state);
        assert(ordered.count(result) == 1); record(result);
    }
    for (unsigned count = 0; count <= 64; ++count) {
        std::vector<int> shuffled(count), expected(count);
        for (unsigned i = 0; i < count; ++i) shuffled[i] = expected[i] = i;
        uint64_t wanted_state = state;
        for (unsigned i = 0; i + 1 < count; ++i) {
            std::swap(expected[i], expected[reference_range(i, count, wanted_state)]);
        }
        ShipUtils::Shuffle(shuffled, &state);
        assert(shuffled == expected && state == wanted_state);
        for (unsigned i = 0; i < count; ++i) record(shuffled[i]);
        Random_Init(91); uint64_t direct = 91;
        expected = shuffled;
        Shuffle(shuffled); ShipUtils::Shuffle(expected, &direct);
        assert(shuffled == expected && rando_state == direct);
    }
    Random_Init(19); uint64_t direct = 19;
    std::array<int, 4> copy = fixed;
    Shuffle(fixed); ShipUtils::Shuffle(copy, &direct);
    assert(fixed == copy && rando_state == direct);
    for (unsigned i = 0; i < 4; ++i) record(fixed[i]);
    std::array<int, 0> empty_array;
    std::array<int, 1> single_array = { 9 };
    previous = direct;
    ShipUtils::Shuffle(empty_array, &direct); ShipUtils::Shuffle(single_array, &direct);
    assert(direct == previous && single_array[0] == 9);
    Random_Init(201); direct = 201;
    values.assign(8, 11);
    for (unsigned i = 0; i < 8; ++i) values[i] = i;
    for (int i = 0; i < 64; ++i) {
        const int& a = RandomElement(const_fixed);
        const int& b = ShipUtils::RandomElement(const_fixed, &direct);
        assert(&a == &b && rando_state == direct);
        assert(RandomElement(words) == ShipUtils::RandomElement(words, &direct));
        assert(RandomElement(raw) == ShipUtils::RandomElement(raw, &direct));
        assert(RandomElementFromSet(ordered) == ShipUtils::RandomElementFromSet(ordered, &direct));
        unsigned length = static_cast<unsigned>(values.size());
        int value = RandomElement(values, false);
        assert(value == ShipUtils::RandomElement(values, false, &direct) && values.size() == length);
        assert(rando_state == direct); record(rando_state);
    }
    std::vector<int> values_copy = values;
    while (!values.empty()) {
        assert(RandomElement(values, true) == ShipUtils::RandomElement(values_copy, true, &direct));
        assert(values == values_copy && rando_state == direct);
    }

    // The original default generator initializes lazily even after RandInit.
    // Initialize it using the device once, then exercise deterministic
    // explicit default-state seeding without recording the entropy value.
    ShipUtils::next32();
    ShipUtils::RandInit(73); direct = 73;
    for (int i = 0; i < 256; ++i) assert(ShipUtils::next32() == ShipUtils::next32(&direct));

    assert(Ship_IsCStringEmpty(NULL) && Ship_IsCStringEmpty("") && !Ship_IsCStringEmpty("x"));
    for (int x = -50; x <= 50; x += 10) for (int y = -50; y <= 50; y += 10)
    for (int width = 0; width <= 31; ++width) for (int flip = 0; flip < 2; ++flip) {
        const int height = 31 - width;
        Vtx vertices[4]; memset(vertices, 0xa5, sizeof(vertices));
        Ship_CreateQuadVertexGroup(vertices, x, y, width, height, static_cast<u8>(flip));
        for (int i = 0; i < 4; ++i) {
            assert(vertices[i].v.ob[0] == x + ((i & 1) ? width : 0));
            assert(vertices[i].v.ob[1] == y + ((i & 2) ? height : 0));
            assert(vertices[i].v.tc[0] == (((i & 1) ? (flip ? width * 2 : width) : (flip ? width : 0)) << 5));
            assert(vertices[i].v.tc[1] == ((i & 2) ? height << 5 : 0));
            assert(static_cast<unsigned short>(vertices[i].v.ob[2]) == 0xa5a5);
            assert(vertices[i].v.flag == 0xa5a5);
            for (int c = 0; c < 4; ++c) assert(vertices[i].v.cn[c] == 0xa5);
            record(static_cast<uint16_t>(vertices[i].v.ob[0])); record(static_cast<uint16_t>(vertices[i].v.ob[1]));
            record(static_cast<uint16_t>(vertices[i].v.tc[0])); record(static_cast<uint16_t>(vertices[i].v.tc[1]));
        }
    }
#ifdef SHIPYARD_UTILS_PROJECTED
    for (uint32_t value = 0; value < 65536; ++value) for (unsigned shift = 0; shift < 64; ++shift)
        assert(Shipyard::Utils::RotateRight(value * 65537U, shift) == std::rotr(value * 65537U, static_cast<int>(shift)));
#endif
    printf("ShipUtils seeded/container/vertex digest %016llx\n", static_cast<unsigned long long>(digest));
}
