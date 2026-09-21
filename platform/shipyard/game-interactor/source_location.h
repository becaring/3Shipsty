#pragma once
#include <stdint.h>
namespace Shipyard {
// Generated registration calls supply their actual caller location. There is
// deliberately no default current(): XDK cannot implement that C++20 intrinsic.
class SourceLocation {
public:
    SourceLocation(const char* file,uint32_t line,uint32_t column,const char* function)
        :file_(file),line_(line),column_(column),function_(function){}
    const char* file_name() const{return file_;}
    uint32_t line() const{return line_;}
    uint32_t column() const{return column_;}
    const char* function_name() const{return function_;}
private:
    const char* file_;uint32_t line_;uint32_t column_;const char* function_;
};
}
#define SHIPYARD_CURRENT_HOOK_LOCATION Shipyard::SourceLocation(__FILE__,__LINE__,0,__FUNCSIG__)
