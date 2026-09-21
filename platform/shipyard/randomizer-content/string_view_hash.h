#pragma once
#include <nonstd/string_view.hpp>
#include <functional>
#include <string>
// string-view-lite omits std::hash on the XDK, although this STL has it.
// Match the library's own specialization and string/view equality contract.
#if !nssv_HAVE_STD_HASH
namespace std {
template<> struct hash<nonstd::string_view> {
    size_t operator()(nonstd::string_view value) const {
        return std::hash<std::string>()(std::string(value.data(), value.size()));
    }
};
}
#endif
