#include <nlohmann/json.hpp>
enum UnregisteredEnum { UnregisteredValue = 1 };
void probe() { nlohmann::json j = UnregisteredValue; j.get<UnregisteredEnum>(); }
