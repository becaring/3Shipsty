#if ORIGINAL_SPDLOG
#include <spdlog/fmt/fmt.h>
#else
#include "platform/shipyard/logging/format/format.h"
#endif
#include <cstdio>
int main() { std::puts(fmt::format("{}",1.23456789012345).c_str()); }
