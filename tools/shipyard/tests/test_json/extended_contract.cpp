#include <nlohmann/json.hpp>
#include <iostream>
#include <limits>
using nlohmann::json;
template <class F> void Case(const char *n, F f) {
    std::cout << n << ":";
    try {
        f();
    } catch (const json::exception &e) {
        std::cout << e.what();
    }
    std::cout << "\n";
}
int main() {
    Case("narrow", [] {
        json j = 255;
        unsigned char b = j;
        short s = j;
        json t = std::numeric_limits<unsigned long long>::max();
        unsigned long long u = t;
        std::cout << int(b) << ":" << s << ":" << u;
    });
    Case("narrow-error", [] {
        json j = "s";
        short s = j;
        std::cout << s;
    });
    Case("predicates", [] {
        const char *v[] = {"null", "{}", "[]", "1", "1.0", "true", "\"a\""};
        for (int i = 0; i < 7; ++i) {
            json j = json::parse(v[i]);
            std::cout << j.is_structured() << j.is_number();
        }
    });
    Case("value", [] {
        json j = json::parse("{\"n\":4,\"s\":\"Link\",\"null\":null}");
        std::cout << j.value("n", 1) << j.value("missing", 7) << j.value("s", "???") << j.value("name", "???");
    });
    Case("value-type", [] {
        json j = 3;
        std::cout << j.value("n", 1);
    });
    Case("value-null", [] {
        json j = json::parse("{\"n\":null}");
        std::cout << j.value("n", 1);
    });
    Case("erase-object", [] {
        json j = json::parse("{\"a\":1,\"b\":2}");
        json::iterator i = j.erase(j.find("a"));
        std::cout << i.key() << ":" << j.dump() << ":" << (j.find("missing") == j.end());
        const json c = j;
        std::cout << ":" << c.find("b").value().dump();
    });
    Case("erase-array", [] {
        json j = json::parse("[1,2]");
        json::iterator i = j.erase(j.begin());
        std::cout << i.value().dump() << ":" << j.dump();
    });
    Case("erase-other-owner", [] {
        json j = 1, k = 2;
        j.erase(k.begin());
    });
    Case("erase-primitive", [] {
        json j = "text";
        j.erase(j.begin());
        std::cout << j.dump();
    });
    Case("erase-end-primitive", [] {
        json j = 3;
        j.erase(j.end());
    });
    Case("erase-null", [] {
        json j;
        j.erase(j.begin());
    });
    Case("find-nonobject", [] {
        json j = json::array();
        std::cout << (j.find("x") == j.end());
    });

    Case("update-recursive", [] {
        json j = json::parse("{\"a\":{\"x\":1},\"b\":7}");
        j.update(json::parse("{\"a\":{\"y\":2},\"c\":[1]}"), true);
        std::cout << j.dump();
    });
    Case("update-replace", [] {
        json j = json::parse("{\"a\":{\"x\":1}}");
        j.update(json::parse("{\"a\":{\"y\":2}}"));
        std::cout << j.dump();
    });
    Case("update-conflict", [] {
        json j = json::parse("{\"a\":1}");
        j.update(json::parse("{\"a\":{\"y\":2}}"), true);
    });
    Case("update-null", [] {
        json j;
        j.update(json::object());
        std::cout << j.dump();
    });
    Case("update-null-source", [] {
        json j;
        try {
            j.update(json());
        } catch (const json::exception &e) {
            std::cout << e.what() << ":" << j.dump();
        }
    });
    Case("update-self", [] {
        json j = json::parse("{\"a\":1}");
        j.update(j, true);
        std::cout << j.dump();
    });
}
