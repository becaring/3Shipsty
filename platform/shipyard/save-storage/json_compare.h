#pragma once
#include <nlohmann/json.hpp>
namespace Shipyard { namespace Storage {
// Bounded adaptation of nlohmann 3.12 JSON_IMPLEMENT_OPERATOR and value_t's
// documented type ordering, for the two integer comparisons in save metadata.
// The upstream unsigned -> signed cast is intentional, including large values.
inline bool JsonLessThanInt(const nlohmann::json& value, int limit) {
    if (value.is_number_float()) return value.get<double>() < static_cast<double>(limit);
    if (value.is_number_integer()) return value.get<long long>() < static_cast<long long>(limit);
    return value.is_null() || value.is_boolean();
}
inline bool JsonGreaterThanInt(const nlohmann::json& value, int limit) {
    if (value.is_number_float()) return value.get<double>() > static_cast<double>(limit);
    if (value.is_number_integer()) return value.get<long long>() > static_cast<long long>(limit);
    return value.is_object() || value.is_array() || value.is_string() || (value.type() == nlohmann::detail::value_t::binary);
}
}}
