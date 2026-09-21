#pragma once
#include "soh/Enhancements/randomizer/tricks.h"
#include <functional>
namespace std {
template<> struct hash<Rando::Tricks::Tag> {
    size_t operator()(Rando::Tricks::Tag value) const {
        return std::hash<int>()(value.GetValue());
    }
};
}
