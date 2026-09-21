#pragma once
#include "network/transport.h"
#include "thread-pool/native_support.h"
#include "soh-ui/value_init.h"

namespace Shipyard { namespace Network {
// Existing public logical flags are read by the worker and application hooks.
// Interlocked access supplies real synchronization instead of a volatile poll.
class Flag {
public:
    Flag() {} // Preserve default initialization's indeterminate storage.
    Flag(bool value) : value_(value?1:0) {}
    Flag(const Flag& value) : value_(value?1:0) {}
    Flag& operator=(bool value) { InterlockedExchange(&value_,value?1:0); return *this; }
    Flag& operator=(const Flag& value) { return operator=(bool(value)); }
    operator bool() const { return InterlockedCompareExchange(&value_,0,0)!=0; }
private:
    mutable volatile LONG value_;
};
} }
