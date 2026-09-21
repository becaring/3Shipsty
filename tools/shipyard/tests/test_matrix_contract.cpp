#include "ship/audio/SoundMatrixDecoder.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <stdint.h>

int main() {
    const int rates[]={32000,44100,48000};
    for(unsigned rate=0;rate<3;++rate) {
        Ship::SoundMatrixDecoder decoder(rates[rate]);
        uint32_t hash=2166136261u, state=923;
        for(unsigned block=0;block<65;++block) {
            if(block==31)decoder.ResetState();
            unsigned frames=block%3==0 ? 528 : block%3==1 ? 544 : 1024;
            std::vector<int16_t> input(frames*2);
            for(size_t i=0;i<input.size();++i) {
                state=state*1664525u+1013904223u;
                input[i]=int16_t(state>>16);
            }
            auto result=decoder.Process(reinterpret_cast<const uint8_t*>(input.data()),input.size()*sizeof(int16_t));
            assert(std::get<1>(result)==int(frames*6*sizeof(int16_t)));
            const int16_t* samples=reinterpret_cast<const int16_t*>(std::get<0>(result));
            for(unsigned i=0;i<frames*6;++i) { hash^=uint16_t(samples[i]);hash*=16777619u; }
        }
        std::printf("matrix %d %08x\n",rates[rate],hash);
    }
}
