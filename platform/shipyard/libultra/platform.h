#pragma once
#include <stdint.h>
namespace Shipyard { namespace Libultra {
// 46.875 MHz N64 cycles, truncating towards zero without overflowing ns*3.
inline int64_t NanosecondsToCycles(int64_t ns) { return (ns / 64) * 3 + ((ns % 64) * 3) / 64; }
uint64_t NowCycles();
typedef uint32_t (*TimerCallback)(uint32_t interval, void* context);
bool AddTimer(uint32_t interval, TimerCallback callback, void* context);
// Process timer shutdown. Stop and join before callback owners are destroyed.
void StopTimers();
} }
