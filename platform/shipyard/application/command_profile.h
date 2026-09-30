#pragma once
#include <stdint.h>
#include <string.h>

namespace ModernFrameProfile {
struct CommandStats {
    uint64_t ticks, maximum;
    unsigned calls, samples, ucodes;
};
class CommandSampler {
  public:
    struct Token {
        uint64_t start;
        unsigned opcode;
        bool sampled;
        Token() : start(0), opcode(0), sampled(false) {}
    };
    explicit CommandSampler(uint64_t (*clock)()) : enabled(false), readClock(clock) {
        for (unsigned i=0;i<256;++i) randomState[i]=i+1;
        Reset();
    }
    void Reset() { memset(commands, 0, sizeof(commands)); }
    Token Begin(unsigned opcode, unsigned ucode) {
        Token token;
        if (!enabled) return token;
        token.opcode = opcode & 255;
        CommandStats& stats = commands[token.opcode];
        ++stats.calls;
        stats.ucodes |= ucode < 32 ? (1u << ucode) : 0x80000000u;
        // Independent streams avoid locking the sample to a repeating command position.
        uint32_t& state=randomState[token.opcode];
        state^=state<<13; state^=state>>17; state^=state<<5;
        token.sampled = (state & 63u) == 0;
        if (token.sampled) token.start = readClock();
        return token;
    }
    void End(const Token& token) {
        if (!token.sampled) return;
        const uint64_t now = readClock();
        const uint64_t elapsed = now >= token.start ? now - token.start : 0;
        CommandStats& stats = commands[token.opcode];
        stats.ticks += elapsed;
        if (elapsed > stats.maximum) stats.maximum = elapsed;
        ++stats.samples;
    }
    bool enabled;
    CommandStats commands[256];
  private:
    uint64_t (*readClock)();
    uint32_t randomState[256];
};
extern CommandSampler commandSampler;
}
