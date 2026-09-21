#include <nlohmann/json.hpp>
#include <array>
#include <iostream>
#include <map>
#include <vector>
typedef nlohmann::json J;
enum CheckCode { CheckUnknown, CheckDone = 4 };
enum SmallCode : unsigned char { SmallMax = 255 };
enum SignedCode : signed char { SignedMin = -128 };
enum WideCode : unsigned long long { WideMax = 0xffffffffffffffffULL };
#if defined(_XBOX)
namespace nlohmann { namespace detail {
template <> struct enum_underlying<CheckCode> { typedef int type; };
template <> struct enum_underlying<SmallCode> { typedef unsigned char type; };
template <> struct enum_underlying<SignedCode> { typedef signed char type; };
template <> struct enum_underlying<WideCode> { typedef unsigned long long type; };
} }
#endif
template <class T> void print(const char* name, const T& v) {
    std::cout << name << ':' << J(v).dump() << '\n';
}
void error(const J::exception& e) { std::cout << e.id << ':' << e.what() << '\n'; }
int main() {
    std::map<std::string, std::vector<unsigned short> > m;
    m["z"].push_back(65535); m["a"].push_back(0); m["a"].push_back(258);
    J j = m; print("map", j);
    m = j.get<std::map<std::string, std::vector<unsigned short> > >();
    print("map-get", m);
    std::map<std::string, int> target; target["old"] = 9;
    J::parse("{\"new\":2}").get_to(target); print("map-replace", target);
    try { J::parse("{\"a\":1,\"z\":\"bad\"}").get_to(target); }
    catch (const J::exception& e) { error(e); print("map-unchanged", target); }
    std::map<std::string, int> implicit = J::parse("{\"x\":3}"); print("map-implicit", implicit);
    implicit = J::parse("{\"y\":4}"); print("map-assign", implicit);
    J empty = std::map<std::string, int>(); print("empty-map", empty);
    std::array<int, 3> a = {{8,8,8}};
    j = a; print("array", j); a = J::parse("[1,2,3,4]").get<std::array<int,3> >(); print("array-get", a);
    try { J::parse("[4,\"bad\",6]").get_to(a); }
    catch (const J::exception& e) { error(e); print("array-partial", a); }
    try { J::parse("[7]").get_to(a); }
    catch (const J::exception& e) { error(e); print("array-short", a); }
    std::array<int,0> zero; print("empty-array", J::array().get<std::array<int,0> >());
    unsigned char c[3] = {0,128,255}; j = c; print("carray", j); j.get_to(c); print("carray-get", c);
    try { J::parse("[7]").get_to(c); }
    catch (const J::exception& e) { error(e); print("carray-short", c); }
    int matrix[2][2] = {{1,2},{3,4}}; print("matrix", matrix);
    J::parse("[[5,6],[7,8]]").get_to(matrix); print("matrix-get", matrix);
    int cube[1][1][1] = {{{3}}}; J(cube).get_to(cube); print("cube", cube);
    char text[] = "text"; print("char-string", text);
    signed char bytes[2] = {-1,127}; print("signed-bytes", bytes);
    const char* wrong[] = {"null", "{}", "true", "1", "\"s\""};
    for (size_t i=0; i<5; ++i) {
        J w = J::parse(wrong[i]);
        try { w.get_to(target); } catch (const J::exception& e) { error(e); }
        try { w.get_to(a); } catch (const J::exception& e) { error(e); }
        try { w.get_to(c); } catch (const J::exception& e) { error(e); }
        try { w.get_to(zero); } catch (const J::exception& e) { error(e); }
    }
    CheckCode code = CheckDone; j = code; print("enum", j);
    const char* enumValues[] = {"0", "-1", "42", "4.75", "4294967295", "true", "null", "\"4\"", "[]", "{}"};
    for (size_t i=0; i<10; ++i) {
        try { J::parse(enumValues[i]).get_to(code); print("enum-get", code); }
        catch (const J::exception& e) { error(e); }
    }
    unsigned char narrow[3] = {0,0,0}; J::parse("[true,257,-1]").get_to(narrow); print("numeric-elements", narrow);
    std::vector<bool> bits; bits.push_back(true); bits.push_back(false); print("vector-bool", bits);
    j = SmallMax; print("enum-small", j); std::cout << "unsigned:" << j.is_number_unsigned() << '\n';
    j = SignedMin; print("enum-signed", j); std::cout << "unsigned:" << j.is_number_unsigned() << '\n';
    j = WideMax; print("enum-wide", j); std::cout << "unsigned:" << j.is_number_unsigned() << '\n';
    print("enum-small-narrow", J(256).get<SmallCode>());
    print("enum-signed-narrow", J(255).get<SignedCode>());
    print("enum-wide-get", J::parse("18446744073709551615").get<WideCode>());
    std::cout << "references:" << (&j.get_to(code) == &code);
    j = J::parse("[1,2,3]");
    std::cout << (&j.get_to(a) == &a) << (&j.get_to(c) == &c) << '\n';
}
