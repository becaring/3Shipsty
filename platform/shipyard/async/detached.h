#pragma once
#include <functional>
namespace Shipyard { namespace Async {
// Own the callable until the native worker finishes. Creation errors propagate;
// uncaught worker exceptions terminate, matching std::thread's contract.
void launch_detached(const std::function<void()>& callable);
} }
