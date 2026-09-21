#include "ship/debug/Console.h"
#include "fast/debug/GfxDebugger.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstdio>

int main() {
    spdlog::set_level(spdlog::level::off);
    Ship::Console console;
    console.Init();
    assert(!console.HasCommand("warp"));
    Ship::CommandEntry entry;
    entry.Description="first";
    Ship::CommandArgument required;
    required.Info="scene";
    assert(required.Type==Ship::ArgumentType::NUMBER && !required.Optional);
    Ship::CommandArgument optional;
    optional.Info="entrance"; optional.Optional=true;
    entry.Arguments.push_back(required); entry.Arguments.push_back(optional);
    console.AddCommand("warp",entry);
    entry.Description="ignored duplicate";
    console.AddCommand("warp",entry);
    assert(console.HasCommand("warp") && console.GetCommands().size()==1);
    assert(console.GetCommand("warp").Description=="first");
    assert(console.BuildUsage(std::string("warp"))=="<scene> [entrance] ");
    assert(console.BuildUsage(console.GetCommand("warp"))=="<scene> [entrance] ");

    Fast::GfxDebugger debugger;
    assert(!debugger.IsDebugging() && !debugger.IsDebuggingRequested() && !debugger.GetDisplayList());
    Fast::F3DGfx* address=reinterpret_cast<Fast::F3DGfx*>(0x1000);
    debugger.RequestDebugging(); assert(debugger.IsDebuggingRequested() && !debugger.IsDebugging());
    debugger.DebugDisplayList(address);
    assert(debugger.IsDebugging() && !debugger.IsDebuggingRequested() && debugger.GetDisplayList()==address);
    std::vector<const Fast::F3DGfx*> path(1,address);
    assert(debugger.HasBreakPoint(path));
    path.push_back(reinterpret_cast<Fast::F3DGfx*>(0x2000));
    assert(!debugger.HasBreakPoint(path));
    debugger.SetBreakPoint(path); assert(debugger.HasBreakPoint(path));
    debugger.ResumeGame();
    assert(!debugger.IsDebugging() && !debugger.IsDebuggingRequested() && !debugger.GetDisplayList());
    assert(debugger.HasBreakPoint(path)); // Current resume retains the breakpoint path.
    std::puts("Current console registration/usage and display-list debugger state contracts agree");
}
