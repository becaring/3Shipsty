#pragma once
#include "../async/native.h"
#include <cstddef>

namespace Shipyard { namespace Logging {
using namespace Shipyard::Async;
// Counter operations are serialized, preserving size_t width and atomic reads.
// No claim of lock-free progress is made or needed by spdlog's queue.
class logging_counter {
public:
    explicit logging_counter(std::size_t value=0):value_(value){}
    void increment(){lock_guard<mutex> hold(mutex_);++value_;}
    std::size_t load(){lock_guard<mutex> hold(mutex_);return value_;}
    void store(std::size_t value){lock_guard<mutex> hold(mutex_);value_=value;}
private:
    logging_counter(const logging_counter&);
    logging_counter& operator=(const logging_counter&);
    mutex mutex_;
    std::size_t value_;
};
}

} // namespace Shipyard
