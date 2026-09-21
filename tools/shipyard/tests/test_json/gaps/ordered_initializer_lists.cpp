#include <nlohmann/json.hpp>
void probe() { nlohmann::ordered_json ordered = nlohmann::ordered_json::object({{"z",1},{"a",2}}); }
