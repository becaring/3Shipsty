#include <memory>
#include <stdexcept>
#include <cstdio>
#ifdef TEST_ORIGINAL
#include <variant>
namespace values = std;
#else
#include "resources/variant.h"
namespace values = Shipyard::Resources;
#endif
static void check(bool value) { if (!value) throw std::runtime_error("variant contract"); }
struct Failure {
    Failure() {}
    Failure(const Failure&) { throw std::runtime_error("copy failure"); }
    Failure(Failure&&) { throw std::runtime_error("move failure"); }
    Failure& operator=(const Failure&) { throw std::runtime_error("assign failure"); }
    Failure& operator=(Failure&&) { throw std::runtime_error("assign failure"); }
};
int main() {
    try {
        values::variant<int, std::shared_ptr<int> > value;
        check(values::holds_alternative<int>(value) && values::get<int>(value) == 0);
        std::shared_ptr<int> owner(new int(7));
        value = owner; check(owner.use_count() == 2 && *values::get<std::shared_ptr<int> >(value) == 7);
        values::variant<int, std::shared_ptr<int> > copy(value);
        check(owner.use_count() == 3); copy = 9;
        check(owner.use_count() == 2 && values::get<int>(copy) == 9);
        values::variant<int, std::shared_ptr<int> > moved(std::move(value));
        check(value.index() == 1 && !values::get<std::shared_ptr<int> >(value));
        moved = nullptr; check(!values::get<std::shared_ptr<int> >(moved) && owner.use_count() == 1);
        bool bad = false; try { values::get<int>(moved); } catch (const values::bad_variant_access&) { bad = true; }
        check(bad);
        values::variant<int, Failure> failed;
        Failure error;
        try { failed = error; } catch (const std::runtime_error&) {}
        check(failed.valueless_by_exception());
        failed = 4; check(values::get<int>(failed) == 4);
        std::puts("PASS variant ownership/default/type-switch/move/null/bad-access/valueless recovery");
        return 0;
    } catch (const std::exception& e) { std::fprintf(stderr, "%s\n", e.what()); return 1; }
}
