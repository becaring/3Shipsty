"""Recycle retired interpolation maps without sharing outstanding outputs.

A map is acquired only when every prepared destination is present. Replay
overwrites those values before publication; cached values are never consumed.
The bounded pool owns only maps returned at the frame retirement boundary.
"""

from prepare_configuration import once


POOL = r"""class RecycledInterpolationMaps {
    typedef std::unordered_map<Mtx*, MtxF> Map;
    enum { MapCount = 8, MapLimit = 1024, EntryLimit = 4096 };
    Map maps[MapCount];
    size_t entries;
    unsigned next;
#ifdef _XBOX
    CRITICAL_SECTION gate;
    void Lock() { EnterCriticalSection(&gate); }
    void Unlock() { LeaveCriticalSection(&gate); }
#else
    std::mutex gate;
    void Lock() { gate.lock(); }
    void Unlock() { gate.unlock(); }
#endif
    struct Guard {
        RecycledInterpolationMaps& pool;
        explicit Guard(RecycledInterpolationMaps& value) : pool(value) { pool.Lock(); }
        ~Guard() { pool.Unlock(); }
    };
    void Drop(unsigned index) {
        entries -= maps[index].size();
        maps[index].clear();
    }
public:
    RecycledInterpolationMaps() : entries(0), next(0) {
#ifdef _XBOX
        InitializeCriticalSection(&gate);
#endif
    }
    ~RecycledInterpolationMaps() {
#ifdef _XBOX
        DeleteCriticalSection(&gate);
#endif
    }
    bool Acquire(Map& output, const std::vector<Mtx*>& destinations,
                 std::vector<MtxF*>& slots) {
        if (destinations.empty() || destinations.size() > MapLimit) return false;
        Guard guard(*this);
        for (unsigned index = 0; index < MapCount; ++index) {
            Map& candidate = maps[index];
            if (candidate.size() != destinations.size()) continue;
            slots.clear();
            for (size_t i = 0; i < destinations.size(); ++i) {
                Map::iterator found = candidate.find(destinations[i]);
                if (found == candidate.end()) break;
                slots.push_back(&found->second);
            }
            if (slots.size() == destinations.size()) {
                entries -= candidate.size();
                output.swap(candidate);
                return true;
            }
        }
        slots.clear();
        return false;
    }
    void Recycle(Map& input) {
        if (input.empty() || input.size() > MapLimit) return;
        Guard guard(*this);
        unsigned index = 0;
        while (index < MapCount && !maps[index].empty()) ++index;
        if (index == MapCount) {
            index = next;
            next = (next + 1) % MapCount;
            Drop(index);
        }
        while (entries + input.size() > EntryLimit) {
            Drop(next);
            next = (next + 1) % MapCount;
        }
        entries += input.size();
        maps[index].swap(input);
    }
};
static RecycledInterpolationMaps recycled_interpolation_maps;
"""


def interpolation(source):
    source = once(source, "struct InterpolateCtx {", POOL + "\nstruct InterpolateCtx {")
    source = once(
        source,
        """        for (size_t i = 0; i < prepared_destinations.size(); ++i)
            slots.push_back(&mtx_replacements[prepared_destinations[i]]);""",
        """        if (!recycled_interpolation_maps.Acquire(mtx_replacements, prepared_destinations, slots)) {
            for (size_t i = 0; i < prepared_destinations.size(); ++i)
                slots.push_back(&mtx_replacements[prepared_destinations[i]]);
        }""",
    )
    source = once(
        source,
        "unordered_map<Mtx*, MtxF> FrameInterpolation_Interpolate(float step) {",
        """void FrameInterpolation_Recycle(std::unordered_map<Mtx*, MtxF>& replacements) {
    recycled_interpolation_maps.Recycle(replacements);
}

unordered_map<Mtx*, MtxF> FrameInterpolation_Interpolate(float step) {""",
    )
    return '#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <mutex>\n#endif\n' + source


def application(source):
    return once(
        source,
        "    RunCommands(commands, mtx_replacements);",
        """    RunCommands(commands, mtx_replacements);
    for (size_t i = 0; i < mtx_replacements.size(); ++i)
        FrameInterpolation_Recycle(mtx_replacements[i]);""",
    )
