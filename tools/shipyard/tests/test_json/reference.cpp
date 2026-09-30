#include <nlohmann/json.hpp>
#include <cstdint>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using nlohmann::json;
static void Check(bool value, const char *text) {
    if (!value)
        throw std::runtime_error(text);
}
template <class Fn> static void Error(int id, Fn fn) {
    try {
        fn();
    } catch (const json::exception &error) {
        Check(error.id == id, "exception ID changed");
        std::cout << error.what() << '\n';
        return;
    }
    throw std::runtime_error("expected exception was not thrown");
}

static void InspectCVars(nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<json>> items, std::string prefix,
                         std::vector<std::string> &found) {
    for (auto item : items) {
        std::string path = prefix + item.key();
        if (item.value().is_object())
            InspectCVars(item.value().items(), path + "/", found);
        else
            found.push_back(path + "=" + item.value().dump());
    }
}

int main() {
    try {
        json input = json::parse(
            R"({"CVars":{"Audio":{"Volume":0.75},"Enabled":true,"Name":"Smash","RGBA":{"Type":"RGBA","R":)"
        R"(255,"G":64,"B":0,"A":255}},"a/b":{"~key":[1,-2,3]},"":{"value":false}})");
        json flat = input.flatten();
        Check(flat["/a~1b/~0key/1"] == -2, "flatten escaped JSON Pointer");
        Check(flat.unflatten() == input, "unflatten round trip");
        std::cout << "flatten=" << flat.dump() << '\n';
        json::json_pointer pointer("/a~1b/~0key/1");
        Check(input.at(pointer) == -2, "JSON Pointer access");
        Check(pointer.to_string() == "/a~1b/~0key/1", "JSON Pointer string");
        input[pointer] = 42;
        Check(input["a/b"]["~key"][1] == 42, "JSON Pointer write");
        json empty = json::parse(R"({"array":[],"object":{}})");
        Check(empty.flatten() == json::parse(R"({"/array":null,"/object":null})"),
              "empty flatten loss is upstream semantics");
        Check(empty.flatten().unflatten() == json::parse(R"({"array":null,"object":null})"),
              "empty unflatten behavior");
        std::vector<std::string> cvars;
        InspectCVars(input["CVars"].items(), "", cvars);
        for (const auto &cvar : cvars)
            std::cout << "cvar=" << cvar << '\n';
        std::vector<int32_t> integers{-2, 0, 42, std::numeric_limits<int32_t>::max()};
        json array = integers;
        Check(array.get<std::vector<int32_t>>() == integers, "vector conversion");
        std::vector<std::string> strings{"", "a/b", "~key"};
        Check(json(strings).get<std::vector<std::string>>() == strings, "string vector conversion");
        json numeric = json::parse("[-9223372036854775808,9223372036854775807,18446744073709551615,"
                                   "18446744073709551616,-9223372036854775809]");
        Check(numeric[0].is_number_integer() && numeric[0].get<int64_t>() == std::numeric_limits<int64_t>::min(),
              "signed minimum");
        Check(numeric[1].get<int64_t>() == std::numeric_limits<int64_t>::max(), "signed maximum");
        Check(numeric[2].is_number_unsigned() && numeric[2].get<uint64_t>() == std::numeric_limits<uint64_t>::max(),
              "unsigned maximum");
        Check(numeric[3].is_number_float() && numeric[4].is_number_float(), "overflow uses float");
        std::cout << "numeric=" << numeric.dump() << '\n';
        json unicode = json::parse(R"({"text":"\u00e9\u20ac\ud83d\ude00","zero":"a\u0000b"})");
        Check(unicode["text"].get<std::string>() == "\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80", "Unicode/surrogate decode");
        Check(unicode["zero"].get<std::string>() == std::string("a\0b", 3), "embedded zero");
        Check(json::parse(unicode.dump(-1, ' ', true)) == unicode, "ASCII escape round trip");
        std::cout << "unicode=" << unicode.dump(-1, ' ', true) << '\n';
        std::istringstream stream("{\"path\":\"assets/reloc\",\"type\":\"RELO\",\"version\":0}");
        json resource = json::parse(stream);
        Check(resource.contains("path") && resource["path"].get<std::string>() == "assets/reloc", "resource metadata");
        Check(json::parse("{/*resource comment*/\"x\":1}", nullptr, true, true)["x"] == 1,
              "JsonFactory comment option");
        Error(101, [] { json::parse("{"); });
        Error(101, [] { json::parse("\"\\ud800\""); });
        Error(107, [] { json::json_pointer invalid("not/a/pointer"); });
        Error(108, [] { json::json_pointer invalid("/~2"); });
        Error(302, [] { json("text").get<int>(); });
        Error(313, [] { json::parse(R"({"/a":1,"/a/b":2})").unflatten(); });
        Error(314, [] { json::array().unflatten(); });
        Error(315, [] { json::parse(R"({"/a":{}})").unflatten(); });
        Error(316, [] { json(std::string("\xff", 1)).dump(); });
        std::cout << "rich-json-contract=ok\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
