#pragma once
#include "format/format.h"
#include "native.h"
#include "chrono/chrono.h"
#include <memory>
#include <functional>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

namespace Shipyard { namespace Logging {
class logging_recursive_mutex {
public:logging_recursive_mutex(){InitializeCriticalSection(&section_);}~logging_recursive_mutex(){DeleteCriticalSection(&section_);}
    void lock(){EnterCriticalSection(&section_);}void unlock(){LeaveCriticalSection(&section_);}
    bool try_lock(){return TryEnterCriticalSection(&section_)!=0;}
private:CRITICAL_SECTION section_;logging_recursive_mutex(const logging_recursive_mutex&);logging_recursive_mutex& operator=(const logging_recursive_mutex&);
};
class logging_view : public fmt::StringRef {
public:
    logging_view():fmt::StringRef("",0){}
    logging_view(const char* p,size_t n):fmt::StringRef(p,n){}
    logging_view(const char* p):fmt::StringRef(p){}
    logging_view(const std::string& p):fmt::StringRef(p){}
    const char* begin()const{return data();}const char* end()const{return data()+size();}
};
class logging_buffer : public fmt::internal::MemoryBuffer<char,250> {
    typedef fmt::internal::MemoryBuffer<char,250> Base;
public:
    logging_buffer(){}
    char* data(){return ptr_;}const char* data()const{return ptr_;}
    char* begin(){return data();}const char* begin()const{return data();}
    char* end(){return data()+size();}const char* end()const{return data()+size();}
    logging_buffer(logging_buffer&& other):Base(std::move(other)){Base empty;static_cast<Base&>(other)=std::move(empty);}
    logging_buffer& operator=(logging_buffer&& other){
        if(this!=&other){Base::operator=(std::move(other));Base empty;static_cast<Base&>(other)=std::move(empty);}return *this;
    }
private:logging_buffer(const logging_buffer&);logging_buffer& operator=(const logging_buffer&);
};
template<class T> class logging_atomic {
public:
    explicit logging_atomic(T value=T()):value_(value){}
    T load()const{lock_guard<mutex> hold(mutex_);return value_;}
    void store(T value){lock_guard<mutex> hold(mutex_);value_=value;}
    T exchange(T value){lock_guard<mutex> hold(mutex_);T old=value_;value_=value;return old;}
    logging_atomic& operator=(T value){store(value);return *this;}
private:mutable mutex mutex_;T value_;logging_atomic(const logging_atomic&);logging_atomic& operator=(const logging_atomic&);
};
template<class C> typename C::iterator LoggingBegin(C& c){return c.begin();}
template<class C> typename C::const_iterator LoggingBegin(const C& c){return c.begin();}
template<class C> typename C::iterator LoggingEnd(C& c){return c.end();}
template<class C> typename C::const_iterator LoggingEnd(const C& c){return c.end();}
template<class T,size_t N> T* LoggingBegin(T (&data)[N]){return data;}
template<class T,size_t N> T* LoggingEnd(T (&data)[N]){return data+N;}
inline void LoggingRunFunction(void* context){std::unique_ptr<std::function<void()> > call(static_cast<std::function<void()>*>(context));(*call)();}
inline joining_thread LoggingMakeThread(const std::function<void()>& call){
    std::unique_ptr<std::function<void()> > owned(new std::function<void()>(call));
    joining_thread thread(&LoggingRunFunction,owned.get());owned.release();return std::move(thread);
}
}

} // namespace Shipyard
