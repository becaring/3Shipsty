#pragma once
#include <stdint.h>
#include <functional>
#include <string>

namespace Shipyard { namespace SohResources {
// SceneCommandID's fixed uint8_t representation includes truncation on casts.
// Keep comparisons strongly typed and never introduce an implicit integer cast.
template<class Derived> class ByteEnum {
  public:
    bool operator==(const Derived& other) const { return mValue == other.GetValue(); }
    bool operator!=(const Derived& other) const { return mValue != other.GetValue(); }
    bool operator<(const Derived& other) const { return mValue < other.GetValue(); }
    bool operator<=(const Derived& other) const { return mValue <= other.GetValue(); }
    bool operator>(const Derived& other) const { return mValue > other.GetValue(); }
    bool operator>=(const Derived& other) const { return mValue >= other.GetValue(); }
    uint8_t GetValue() const { return mValue; }
  protected:
    ByteEnum() : mValue(0) {}
    explicit ByteEnum(int value) : mValue(static_cast<uint8_t>(value)) {}
  private:
    uint8_t mValue;
};

inline std::string UIntToString(uint32_t value) {
    char buffer[11];
    char* end = buffer + sizeof(buffer);
    char* pos = end;
    do { *--pos = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    return std::string(pos, end);
}
} }
