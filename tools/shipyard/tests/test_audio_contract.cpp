#include "ship/audio/AudioPlayer.h"
#include "audio/PcmLayout.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstring>
#include <thread>
#include <vector>
#include <iostream>

// This test-only abstract device observes the real AudioPlayer calls. It is
// never selected by the application or linked into the native backend.
class ObservedPlayer : public Ship::AudioPlayer {
public:
    int opens,closes;
    std::vector<uint8_t> last;
    ObservedPlayer(Ship::AudioSettings settings) : AudioPlayer(settings),opens(0),closes(0) {}
    int32_t Buffered() { return 0; }
protected:
    bool DoInit() { ++opens;return true; }
    void DoClose() { ++closes; }
    void DoPlay(const uint8_t* data,size_t length) { last.assign(data,data+length); }
};

int main() {
    spdlog::set_level(spdlog::level::off);
    Ship::AudioSettings settings;settings.SampleRate=32000;settings.SampleLength=1024;settings.DesiredBuffered=1680;
    ObservedPlayer player(settings);
    assert(!player.IsInitialized() && player.Init() && player.IsInitialized());
    assert(player.GetSampleRate()==32000 && player.GetDesiredBuffered()==1680 && player.GetSampleLength()==1024);
    std::vector<int16_t> input(544*2,1234);
    const uint8_t* bytes=reinterpret_cast<const uint8_t*>(input.data());size_t length=input.size()*sizeof(int16_t);
    player.Play(bytes,length);assert(player.last.size()==length && !std::memcmp(player.last.data(),bytes,length));
    assert(player.SetAudioChannels(audioMatrix51) && player.GetNumOutputChannels()==6);
    player.Play(bytes,length);assert(player.last.size()==length*3);
    assert(player.SetAudioChannels(audioMatrix51) && player.opens==2 && player.closes==1);
    assert(player.SetAudioChannels(audioRaw51) && player.GetNumOutputChannels()==6);
    player.Play(bytes,length);assert(player.last.size()==length && !std::memcmp(player.last.data(),bytes,length));
    assert(player.SetAudioChannels(audioStereo) && player.GetNumOutputChannels()==2);

    ShipyardAudio::PcmLayout layout;
    assert(ShipyardAudio::ComputePcmLayout(32000,2,audioStereo,1024,1680,layout));
    assert(layout.frameBytes==4 && layout.capacityFrames>=1680);
    assert(ShipyardAudio::ComputePcmLayout(32000,6,audioMatrix51,1024,1680,layout) && layout.frameBytes==12);
    assert(ShipyardAudio::ComputePcmLayout(32000,6,audioRaw51,1024,1680,layout));
    assert(!ShipyardAudio::ComputePcmLayout(32000,2,audioRaw51,1024,1680,layout));
    assert(!ShipyardAudio::ComputePcmLayout(32000,2,audioStereo,0,1680,layout));
    assert(!ShipyardAudio::ComputePcmLayout(32000,2,audioStereo,1024,-1,layout));

    ShipyardAudio::PcmBufferPool pool;
    assert(!pool.Initialize(0) && pool.Initialize(4096));
    ShipyardAudio::PcmBufferPool::Block* blocks[ShipyardAudio::PcmBufferPool::BlockCount];
    for(unsigned i=0;i<ShipyardAudio::PcmBufferPool::BlockCount;++i) {
        blocks[i]=pool.TryAcquire();assert(blocks[i] && uintptr_t(blocks[i]->samples)%16==0);
        std::memset(blocks[i]->samples,int(i),4096);
    }
    assert(!pool.TryAcquire() && !pool.WaitAvailable(0));
    std::thread completion([&pool,&blocks](){pool.Release(blocks[3]);});
    assert(pool.WaitAvailable(5000));completion.join();
    auto recycled=pool.TryAcquire();assert(recycled==blocks[3]);
    for(unsigned i=0;i<4096;++i)assert(recycled->samples[i]==3);
    for(unsigned i=0;i<ShipyardAudio::PcmBufferPool::BlockCount;++i)pool.Release(blocks[i]);
    pool.Close();assert(!pool.TryAcquire() && pool.CapacityBytes()==0);
    std::cout << "AudioPlayer stereo/matrix/raw51, settings, bounded aligned PCM ownership and callback-style wake pass\n";
}
