#include <nlohmann/json.hpp>
struct UnregisteredValue { int payload; };
void RejectedConversion() { nlohmann::json j; j.get<UnregisteredValue>(); }
