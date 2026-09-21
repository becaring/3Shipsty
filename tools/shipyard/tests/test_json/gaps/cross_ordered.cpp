#include <nlohmann/json.hpp>
void probe() { nlohmann::json sorted; nlohmann::ordered_json ordered = sorted; sorted = ordered; }
