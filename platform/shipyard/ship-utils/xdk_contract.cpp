#include "soh/ShipUtils.h"
#include "soh/Enhancements/randomizer/3drando/random.hpp"
#include <string>

typedef char uint64_width[sizeof(uint64_t) == 8 ? 1 : -1];
typedef char uint32_width[sizeof(uint32_t) == 4 ? 1 : -1];
typedef char float_width[sizeof(f32) == 4 ? 1 : -1];
typedef char vertex_width[sizeof(Vtx) == 16 ? 1 : -1];
typedef char reference_preserved[std::is_same<Shipyard::Utils::IndexedValue<std::vector<int> >::type, int>::value ? 1 : -1];
typedef char const_preserved[std::is_same<Shipyard::Utils::IndexedValue<const std::array<int, 3> >::type, const int>::value ? 1 : -1];

void shipyard_utils_container_probe() {
    uint64_t state = 0;
    std::vector<int> values(3, 7);
    const std::vector<int>& constant = values;
    std::array<int, 3> fixed = { 1, 2, 3 };
    std::array<int, 0> empty;
    std::array<int, 1> singleton = { 1 };
    const std::array<int, 3>& const_fixed = fixed;
    const char* words[] = { "one", "two" };
    const int raw[] = { 4, 5 };
    std::set<int> ordered; ordered.insert(1);
    int& selected = ShipUtils::RandomElement(values, &state);
    const int& stable = ShipUtils::RandomElement(constant, &state);
    const int& fixed_ref = RandomElement(const_fixed);
    const char*& word = ShipUtils::RandomElement(words, &state);
    const int& raw_ref = RandomElement(raw);
    RandomElement(values, false);
    ShipUtils::RandomElement(values, true, &state);
    ShipUtils::RandomElementFromSet(ordered, &state);
    RandomElementFromSet(ordered);
    ShipUtils::Shuffle(values, &state); ShipUtils::Shuffle(fixed, &state);
    Shuffle(values); Shuffle(fixed);
    ShipUtils::Shuffle(empty, &state); ShipUtils::Shuffle(singleton, &state);
}
