#include <nlohmann/json.hpp>
#include <iostream>
#include <cstring>
#include <limits>
#include <sstream>
#include <vector>
using nlohmann::json;
template <class F> void Case(const char *name, F f) {
    std::cout << name << ":";
    try {
        f();
    } catch (const json::exception &e) {
        std::cout << e.what();
    }
    std::cout << "\n";
}
int main() {
    const char *texts[] = {"",
                           " ",
                           "\n",
                           "{",
                           "[",
                           "[1,]",
                           "{\"x\":}",
                           "{\"x\" 1}",
                           "{1:2}",
                           "{\"x\":1,}",
                           "[1 2]",
                           "true false",
                           "1e9999",
                           "-0",
                           "-0.0",
                           "1.0",
                           "1e-9999",
                           "01",
                           "-01",
                           "1.",
                           "1e",
                           "1e+",
                           "/*x*/1",
                           "\"\\ud800\"",
                           "\"\\udc00\"",
                           "\"\\ud800\\u0000\"",
                           "{\"x\":1,\"x\":2}",
                           "9223372036854775808",
                           "18446744073709551615",
                           "18446744073709551616",
                           "-9223372036854775809"};
    for (size_t i = 0; i < sizeof(texts) / sizeof(*texts); ++i)
        Case(texts[i], [&] {
            json j = json::parse(texts[i]);
            std::cout << int(j.type()) << ":" << j.dump();
        });
    const char *pointers[] = {"",   "/",   "/0",  "/1", "/00", "/-", "/-1", "/+1", "/a", "/18446744073709551616",
                              "/~", "/~2", "/~01"};
    for (size_t i = 0; i < sizeof(pointers) / sizeof(*pointers); ++i)
        Case(pointers[i], [&] {
            json j = json::parse("[1,2]");
            std::cout << j.at(json::json_pointer(pointers[i])).dump();
        });
    const char *flats[] = {"{\"\":1}",    "{\"/0\":1,\"/2\":3}", "{\"/1\":1}",
                           "{\"/00\":1}", "{\"/0\":1,\"/a\":2}", "{\"/a\":1,\"/a/b\":2}"};
    for (size_t i = 0; i < sizeof(flats) / sizeof(*flats); ++i)
        Case(flats[i], [&] { std::cout << json::parse(flats[i]).unflatten().dump(); });
    const char *utf[] = {
        "\xff",         "\xc0\x80",    "\xc2", "\xe0\x80\x80", "\xed\xa0\x80", "\xf0\x80\x80\x80", "\xf4\x90\x80\x80",
        "\xf0\x9f\x98", "\xe2\x28\xa1"};
    for (size_t i = 0; i < sizeof(utf) / sizeof(*utf); ++i)
        Case("utf", [&] { std::cout << json(std::string(utf[i])).dump(); });
    Case("control", [] {
        std::string s;
        for (char c = 0; c < 32; ++c)
            s += c;
        std::cout << json(s).dump();
    });
    Case("nan", [] {
        json j = std::numeric_limits<double>::quiet_NaN();
        std::cout << int(j.type()) << ":" << j.dump() << ":" << (j == j);
    });
    Case("infinity", [] {
        json j = std::numeric_limits<double>::infinity();
        std::cout << int(j.type()) << ":" << j.dump();
    });
    Case("tuple", [] {
        json j = json::parse("{\"a\":1,\"b\":2}");
        for (auto &[k, v] : j.items())
            std::cout << k << "=" << v.dump() << ";";
    });
    Case("proxy-live", [] {
        json j = json::parse("[1]");
        auto items = j.items();
        j.push_back(2);
        for (const auto &p : items)
            std::cout << p.key() << "=" << p.value().dump() << ";";
    });
    Case("unsigned-comparison", [] {
        json j = -1;
        std::cout << (j == json(std::numeric_limits<unsigned long long>::max()));
    });
    Case("deep-parser", [] {
        std::string text(512, '[');
        text += "0";
        text.append(512, ']');
        json j = json::parse(text);
        std::cout << j.size();
    });
    Case("discarded", [] {
        json j = json::parse("[", nullptr, false);
        std::cout << j.is_discarded() << ":" << j.dump();
    });
    Case("unordered-values", [] {
        json n = std::numeric_limits<double>::quiet_NaN();
        json d = json::parse("[", nullptr, false);
        std::cout << (n != n) << ":" << (n != json(1)) << ":" << (n != json("x")) << ":" << d.is_primitive() << ":"
                  << (d != d) << ":" << (d != json(1));
    });
    Case("unflatten-discarded", [] {
        json flat = json::object();
        flat["/x"] = json::parse("[", nullptr, false);
        std::cout << flat.unflatten().dump();
    });
    unsigned long long bits = 1;
    for (int i = 0; i < 4000; ++i) {
        bits = bits * 6364136223846793005ULL + 1442695040888963407ULL;
        double d;
        std::memcpy(&d, &bits, 8);
        std::cout << json(d).dump() << "\n";
    }
}
