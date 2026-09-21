#include <nlohmann/json.hpp>
#include <vector>
#include <string>
void ActualReachedApi() {
    nlohmann::json j = nlohmann::json::parse("{\"a\":1.0,\"s\":\"text\"}");
    std::string text = j["s"];
    float f = j["a"];
    bool b = nlohmann::json(true);
    std::vector<std::string> strings;
    strings.push_back(text);
    nlohmann::json array(strings);
    strings = array.get<std::vector<std::string>>();
    nlohmann::json flat = j.flatten();
    j = flat.unflatten();
    nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<nlohmann::json>> proxy = j.items();
    nlohmann::detail::iteration_proxy_value<nlohmann::json::iterator> i = proxy.begin();
    if (i != proxy.end()) {
        text = i.key();
        i.value() = f;
    }
    std::string implicit_assignment;
    implicit_assignment = j["s"];
    (void)b;
}
