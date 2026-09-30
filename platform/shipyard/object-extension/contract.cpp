#ifdef TEST_UPSTREAM
#include <any>
namespace values = std;
#else
#include "object-extension/any.h"
namespace values = Shipyard;
#endif
#include <cassert>
#include <memory>
#include <stdexcept>
#include <cstdio>
struct Value {
    int number;
    explicit Value(int n) : number(n) {}
};
struct CopyError {
    static bool fail;
    int number;
    explicit CopyError(int n) : number(n) {}
    CopyError(const CopyError &other) : number(other.number) {
        if (fail)
            throw std::runtime_error("copy");
    }
};
bool CopyError::fail = false;
int main() {
    values::any a;
    assert(!a.has_value() && a.type() == typeid(void));
    assert(values::any_cast<int>((values::any *)NULL) == NULL);
    a = Value(7);
    assert(a.type() == typeid(Value) && values::any_cast<Value>(&a)->number == 7);
    assert(values::any_cast<int>(&a) == NULL);
    values::any b(a);
    values::any_cast<Value>(&b)->number = 9;
    assert(values::any_cast<const Value>(&a)->number == 7 && values::any_cast<Value>(&b)->number == 9);
    const values::any &fixed = b;
    assert(values::any_cast<Value>(&fixed)->number == 9);
    values::any moved(std::move(b));
    assert(values::any_cast<Value>(&moved)->number == 9);
    a = a;
    assert(values::any_cast<Value>(&a)->number == 7);
    values::any throwing = CopyError(11);
    CopyError::fail = true;
    bool caught = false;
    try {
        a = throwing;
    } catch (const std::runtime_error &) {
        caught = true;
    }
    assert(caught && values::any_cast<Value>(&a)->number == 7);
    CopyError::fail = false;
    std::shared_ptr<int> owner(new int(4));
    std::weak_ptr<int> weak = owner;
    {
        values::any first = owner;
        owner.reset();
        assert(!weak.expired());
        values::any second = first;
        first.reset();
        assert(!weak.expired());
        second.reset();
        assert(weak.expired());
    }
    moved.reset();
    assert(!moved.has_value() && moved.type() == typeid(void));
    a = "literal";
    assert(a.type() == typeid(const char *) && values::any_cast<const char *>(&a) != NULL);
    char mutableText[] = "text";
    a = mutableText;
    assert(a.type() == typeid(char *) && *values::any_cast<char *>(&a) == mutableText);
    values::any copyFromNonConst = a;
    assert(copyFromNonConst.type() == typeid(char *));
    puts("Any exact type, mutable/const pointer access, independent copies, move, lifetime and failed-copy guarantee "
         "agree");
}
