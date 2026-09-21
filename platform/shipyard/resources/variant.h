#ifndef SHIPYARD_RESOURCES_VARIANT_H
#define SHIPYARD_RESOURCES_VARIANT_H
#include <type_traits>
#include <utility>
#include <stdexcept>
#include <new>
#include <cstddef>

namespace Shipyard { namespace Resources {
class bad_variant_access : public std::exception {
public:
    const char* what() const throw() { return "bad variant access"; }
};

// Exactly the two-alternative storage used by current LUS File and cache.
// Unsupported ambiguous conversions fail at compile time, never select by guess.
template<class A, class B> class variant {
    enum { bytes = sizeof(A) > sizeof(B) ? sizeof(A) : sizeof(B),
           alignment = std::alignment_of<A>::value > std::alignment_of<B>::value
                     ? std::alignment_of<A>::value : std::alignment_of<B>::value };
    typedef typename std::aligned_storage<bytes, alignment>::type storage_type;
    storage_type storage_;
    std::size_t index_;
    A* first() { return reinterpret_cast<A*>(&storage_); }
    B* second() { return reinterpret_cast<B*>(&storage_); }
    const A* first() const { return reinterpret_cast<const A*>(&storage_); }
    const B* second() const { return reinterpret_cast<const B*>(&storage_); }
    void clear() {
        if (index_ == 0) first()->~A();
        if (index_ == 1) second()->~B();
        index_ = static_cast<std::size_t>(-1);
    }
    template<class U> void set(U&& value, std::true_type) {
        if (index_ == 0) *first() = std::forward<U>(value);
        else { clear(); new (&storage_) A(std::forward<U>(value)); index_ = 0; }
    }
    template<class U> void set(U&& value, std::false_type) {
        if (index_ == 1) *second() = std::forward<U>(value);
        else { clear(); new (&storage_) B(std::forward<U>(value)); index_ = 1; }
    }
    template<class U> void convert(U&& value) {
        static_assert(std::is_convertible<U,A>::value != std::is_convertible<U,B>::value,
                      "two-alternative variant requires exactly one convertible alternative");
        set(std::forward<U>(value), typename std::is_convertible<U,A>::type());
    }
public:
    variant() : index_(static_cast<std::size_t>(-1)) { new (&storage_) A(); index_ = 0; }
    variant(const variant& other) : index_(static_cast<std::size_t>(-1)) {
        if (other.index_ == 0) { new (&storage_) A(*other.first()); index_ = 0; }
        if (other.index_ == 1) { new (&storage_) B(*other.second()); index_ = 1; }
    }
    variant(variant&& other) : index_(static_cast<std::size_t>(-1)) {
        if (other.index_ == 0) { new (&storage_) A(std::move(*other.first())); index_ = 0; }
        if (other.index_ == 1) { new (&storage_) B(std::move(*other.second())); index_ = 1; }
    }
    template<class U> variant(U&& value, typename std::enable_if<!std::is_same<typename std::decay<U>::type,variant>::value>::type* = 0)
        : index_(static_cast<std::size_t>(-1)) { convert(std::forward<U>(value)); }
    ~variant() { clear(); }
    variant& operator=(const variant& other) {
        if (this != &other) {
            if (other.index_ == 0) set(*other.first(), std::true_type());
            else if (other.index_ == 1) set(*other.second(), std::false_type());
            else clear();
        }
        return *this;
    }
    variant& operator=(variant&& other) {
        if (this != &other) {
            if (other.index_ == 0) set(std::move(*other.first()), std::true_type());
            else if (other.index_ == 1) set(std::move(*other.second()), std::false_type());
            else clear();
        }
        return *this;
    }
    template<class U> typename std::enable_if<!std::is_same<typename std::decay<U>::type,variant>::value,variant&>::type operator=(U&& value) {
        convert(std::forward<U>(value)); return *this;
    }
    std::size_t index() const { return index_; }
    bool valueless_by_exception() const { return index_ == static_cast<std::size_t>(-1); }
    template<class T> T& get() {
        static_assert(std::is_same<T,A>::value || std::is_same<T,B>::value, "alternative not present");
        if (index_ != (std::is_same<T,A>::value ? 0 : 1)) throw bad_variant_access();
        return *reinterpret_cast<T*>(&storage_);
    }
    template<class T> const T& get() const {
        static_assert(std::is_same<T,A>::value || std::is_same<T,B>::value, "alternative not present");
        if (index_ != (std::is_same<T,A>::value ? 0 : 1)) throw bad_variant_access();
        return *reinterpret_cast<const T*>(&storage_);
    }
};
template<class T,class A,class B> T& get(variant<A,B>& value) { return value.template get<T>(); }
template<class T,class A,class B> const T& get(const variant<A,B>& value) { return value.template get<T>(); }
template<class T,class A,class B> bool holds_alternative(const variant<A,B>& value) {
    static_assert(std::is_same<T,A>::value || std::is_same<T,B>::value, "alternative not present");
    return value.index() == (std::is_same<T,A>::value ? 0 : 1);
}
} }
#endif
