#pragma once
#include <typeinfo>
#include <type_traits>
#include <utility>
namespace Shipyard {
class any;
template<class T> T* any_cast(any* value);
template<class T> const T* any_cast(const any* value);
// The reached ObjectExtension contract: owning copyable values, exact RTTI and
// nonthrowing pointer casts. Unsupported std::any APIs deliberately do not exist.
class any {
    struct Value {
        virtual ~Value(){}
        virtual Value* Clone() const=0;
        virtual const std::type_info& Type() const=0;
    };
    template<class T> struct TypedValue : Value {
        T data;
        template<class V> explicit TypedValue(V&& value):data(std::forward<V>(value)){}
        Value* Clone() const{return new TypedValue(data);}
        const std::type_info& Type() const{return typeid(T);}
    };
    Value* value_;
    template<class T> friend T* any_cast(any* value);
    template<class T> friend const T* any_cast(const any* value);
public:
    any():value_(NULL){}
    any(const any& other):value_(other.value_?other.value_->Clone():NULL){}
    any(any&& other):value_(other.value_){other.value_=NULL;}
    template<class T> any(T&& value,typename std::enable_if<!std::is_same<typename std::decay<T>::type,any>::value>::type* =0)
        :value_(new TypedValue<typename std::decay<T>::type>(std::forward<T>(value))){}
    ~any(){delete value_;}
    any& operator=(const any& other){any copy(other);swap(copy);return *this;}
    any& operator=(any&& other){if(this!=&other){reset();value_=other.value_;other.value_=NULL;}return *this;}
    template<class T> typename std::enable_if<!std::is_same<typename std::decay<T>::type,any>::value,any&>::type
    operator=(T&& value){any copy(std::forward<T>(value));swap(copy);return *this;}
    void reset(){delete value_;value_=NULL;}
    void swap(any& other){std::swap(value_,other.value_);}
    bool has_value() const{return value_!=NULL;}
    const std::type_info& type() const{return value_?value_->Type():typeid(void);}
};
template<class T> T* any_cast(any* value){
    typedef typename std::remove_cv<T>::type Stored;
    if(!value||value->type()!=typeid(Stored))return NULL;
    return &static_cast<any::TypedValue<Stored>*>(value->value_)->data;
}
template<class T> const T* any_cast(const any* value){
    typedef typename std::remove_cv<T>::type Stored;
    if(!value||value->type()!=typeid(Stored))return NULL;
    return &static_cast<const any::TypedValue<Stored>*>(value->value_)->data;
}
}
