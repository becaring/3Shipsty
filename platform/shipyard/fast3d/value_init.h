#pragma once
#include "fast/interpreter.h"
#include <cstring>
#include <new>

namespace Shipyard { namespace Fast3D {
namespace Detail {
// Only the two original aggregate state records below use this boundary.
// XDK can omit the zero-initialization preceding their nested non-POD member
// constructors. Zero raw storage before placement construction, never memset
// a live shared_ptr/container. Constructor failure releases the allocation.
template<class T> T* NewAggregateValue() {
    void* storage=::operator new(sizeof(T));
    std::memset(storage,0,sizeof(T));
    try { return new(storage) T(); }
    catch (...) { ::operator delete(storage); throw; }
}
}
inline Fast::RSP* NewValueInitializedRSP() { return Detail::NewAggregateValue<Fast::RSP>(); }
inline Fast::RDP* NewValueInitializedRDP() { return Detail::NewAggregateValue<Fast::RDP>(); }
} }
