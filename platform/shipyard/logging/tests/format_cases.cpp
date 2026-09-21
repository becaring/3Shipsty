#if ORIGINAL_SPDLOG
#include <spdlog/fmt/fmt.h>
#else
#include "platform/shipyard/logging/format/format.h"
#endif
#include <cstdio>
#include <string>
#include <cstdint>

// Source-derived caller forms in consumer-inventory.json. Typed boundary values
// cover modern time displays, seed sphere keys, preset paths/CVars and UI IDs.
int main() {
    const unsigned values[] = {0,1,9,10,59,60,255,65535,0xffffffffu};
    for (unsigned i=0;i<sizeof(values)/sizeof(values[0]);++i) {
        unsigned v=values[i];
        std::puts(fmt::format("{}:{:0>2}:{:0>2}.{}",v,v,v,v).c_str());
        std::puts(fmt::format("{:0>2}:{:0>2}",v,v).c_str());
        std::puts(fmt::format("sphere {:0>2}",v).c_str());
        std::puts(fmt::format("{:#x} ({:d})",v,v).c_str());
        std::puts(fmt::format("{:#x}",v,v).c_str());
        std::puts(fmt::format("0x{:02X} {}",v,"description").c_str());
        std::puts(fmt::format("{:<2X}",v).c_str());
        std::puts(fmt::format("0x{:04X} ({})",static_cast<unsigned short>(v),static_cast<short>(v)).c_str());
        std::puts(fmt::format("##{}{}","Flags",v).c_str());
        std::puts(fmt::format("{:s} Room {:d}","Market",v).c_str());
        std::puts(fmt::format("{} Column {}","Enhancements",v).c_str());
    }
    const char* strings[]={"","Vanilla","Test {braces}","Name With Spaces","\xC3\xA9"};
    for (unsigned i=0;i<sizeof(strings)/sizeof(strings[0]);++i) {
        const std::string name(strings[i]);
        std::puts(fmt::format("{}/{}.json","GAME:\\presets",name).c_str());
        std::puts(fmt::format("{}.{}","CVars",name).c_str());
        std::puts(fmt::format("gGeneral.{}SelectedPreset",name).c_str());
        std::puts(fmt::format("{}##header{}",name,name).c_str());
    }
    // Host extraction's sole direct float form is explicit fixed precision.
    const double progress[]={0.0,0.25,1.0,24.25,99.75,100.0};
    for (unsigned i=0;i<sizeof(progress)/sizeof(progress[0]);++i)
        std::puts(fmt::format("{:.0f}%",progress[i]).c_str());
    // Error wording varies by fmt version; both contracts reject invalid syntax.
    unsigned rejected=0;
    const char* invalid[]={"{","}","{:Q}","{1}"};
    for(unsigned i=0;i<4;++i) {
        try {
#if ORIGINAL_SPDLOG
            fmt::format(fmt::runtime(invalid[i]),42);
#else
            fmt::format(invalid[i],42);
#endif
        } catch(const std::exception&) {++rejected;}
    }
    if(rejected!=4)return 1;
    std::puts("PASS modern SoH typed time/seed/preset/UI formats and errors");
}
