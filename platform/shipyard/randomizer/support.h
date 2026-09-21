#pragma once
#include <ship/utils/binarytools/endianness.h>
#include "soh-resources/format.h"
#include <string>
#include <vector>
namespace Shipyard { namespace Randomizer {
inline std::vector<std::string> MessageDefaults(const std::string& untranslated) {
    const std::string values[] = { "", untranslated, untranslated };
    return std::vector<std::string>(values, values + 3);
}
} }
