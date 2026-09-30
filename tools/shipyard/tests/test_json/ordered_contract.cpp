#include <nlohmann/json.hpp>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <string>
#include <type_traits>
using nlohmann::ordered_json;
static void show(const ordered_json &j) {
    std::cout << j.dump() << "|";
    for (ordered_json::const_iterator i = j.begin(); i != j.end(); ++i)
        if (j.is_object())
            std::cout << i.key() << ",";
    std::cout << "\n";
}
int main() {
    static_assert(std::is_const<decltype(static_cast<ordered_json::object_t::value_type *>(0)->first)>::value,
                  "ordered key stays const");
    static_assert(!std::is_same<nlohmann::json, ordered_json>::value, "ordered must be a distinct DOM");
    static_assert(std::is_same<nlohmann::json::exception, ordered_json::exception>::value, "exceptions are shared");
    ordered_json j;
    j["z"] = 1;
    j["a"] = 2;
    j["m"]["y"] = 3;
    j["m"]["b"] = 4;
    show(j);
    j["a"] = 5;
    j.emplace("z", 99);
    j.emplace("b", 6);
    show(j);
    j.erase("a");
    j["a"] = 7;
    show(j);
    ordered_json copy = j;
    copy["m"]["y"] = 30;
    show(j);
    show(copy);
    ordered_json moved = std::move(copy);
    show(moved);
    show(copy);
    ordered_json::iterator it = j.find("m");
    it = j.erase(it);
    std::cout << it.key() << ":" << it.value().dump() << "\n";
    show(j);
    show(ordered_json::parse("{\"z\":1,\"a\":2,\"z\":3,\"arr\":[{\"y\":4,\"b\":5}]}"));
    ordered_json p = ordered_json::parse("{\"z\":{\"c\":1,\"a\":2},\"b\":3}");
    show(p.flatten());
    show(p.flatten().unflatten());
    ordered_json other = ordered_json::parse("{\"b\":8,\"x\":9,\"z\":{\"k\":2}}");
    p.update(other, true);
    show(p);
    ordered_json a = ordered_json::parse("{\"x\":1,\"y\":2}"), b = ordered_json::parse("{\"y\":2,\"x\":1}");
    std::cout << "equality:" << (a == b) << ":" << (a != b) << "\n";
    std::vector<ordered_json> entries;
    entries.push_back(j);
    entries.push_back(p);
    ordered_json array = entries;
    show(array);
    std::vector<ordered_json> back = array.get<std::vector<ordered_json>>();
    show(back[1]);
    std::istringstream stream("{\"z\":1,\"a\":2}[]");
    ordered_json from;
    stream >> from;
    show(from);
    std::cout << stream.peek() << "\n";
    std::cout << std::setw(2) << from << "\n";
    try {
        std::istringstream bad("{\"z\":1,\"a\":}tail");
        bad >> from;
    } catch (const nlohmann::json::parse_error &e) {
        std::cout << e.what() << "\n";
        show(from);
    }
    for (int n = 0; n < 100; ++n) {
        std::ostringstream key;
        key << n;
        j[key.str()] = n;
    }
    ordered_json snapshot = j;
    for (int n = 0; n < 100; n += 2) {
        std::ostringstream key;
        key << n;
        j.erase(key.str());
    }
    show(j);
    show(snapshot);
    j.clear();
    show(j);
    j["new"] = 1;
    show(j);
}
