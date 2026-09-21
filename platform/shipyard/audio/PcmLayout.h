#ifndef SHIPYARD_AUDIO_PCM_LAYOUT_H
#define SHIPYARD_AUDIO_PCM_LAYOUT_H
#include "ship/audio/AudioChannelsSetting.h"
#include "PcmBufferPool.h"
#include <stdint.h>

namespace ShipyardAudio {
enum { PcmMinimumRate = 1000, PcmMaximumRate = 200000, PcmMaximumBlockFrames = 16384 };
struct PcmLayout {
    unsigned sampleRate, channels, frameBytes, blockFrames, capacityFrames;
};
inline bool ComputePcmLayout(int32_t rate, int32_t channels, AudioChannelsSetting setting,
                             int32_t sampleLength, int32_t desired, PcmLayout& out) {
    // Honor the current AudioPlayer input contract: raw51 is already six-channel
    // PCM; matrix51 is expanded by the real upstream matrix decoder.
    if (setting != audioStereo && setting != audioMatrix51 && setting != audioRaw51) return false;
    if (channels != (setting == audioStereo ? 2 : 6)) return false;
    if (rate < PcmMinimumRate || rate > PcmMaximumRate || sampleLength <= 0 ||
        sampleLength > PcmMaximumBlockFrames || desired < 0 ||
        desired > PcmMaximumBlockFrames * PcmBufferPool::BlockCount) return false;
    out.sampleRate = rate; out.channels = channels;
    out.frameBytes = channels * sizeof(int16_t);
    unsigned reservePerBlock = (static_cast<unsigned>(desired) + PcmBufferPool::BlockCount - 1) / PcmBufferPool::BlockCount;
    out.blockFrames = static_cast<unsigned>(sampleLength) > reservePerBlock ? sampleLength : reservePerBlock;
    out.capacityFrames = out.blockFrames * PcmBufferPool::BlockCount;
    return true;
}
}
#endif
