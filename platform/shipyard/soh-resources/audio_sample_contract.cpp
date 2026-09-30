// Appended after the complete service-independent original/projected factory
// methods. Only XML's real Context/archive acquisition is outside this host audit.
#include "ship/utils/binarytools/MemoryStream.h"
#include <cassert>
#include <fstream>
#include <cstdio>
#include <vector>
#include <cstring>
static uint64_t sampleHash = 1469598103934665603ULL;
static void sampleDigest(const void *bytes, size_t size) {
    const uint8_t *p = (const uint8_t *)bytes;
    while (size--) {
        sampleHash ^= *p++;
        sampleHash *= 1099511628211ULL;
    }
}
static std::shared_ptr<Ship::File> sampleFile(const char *path) {
    std::ifstream input(path, std::ios::binary);
    assert(input.good());
    auto f = std::make_shared<Ship::File>();
    f->Buffer =
        std::make_shared<std::vector<char>>(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
    return f;
}
static void pcm(const uint8_t *bytes, size_t size) {
    assert(bytes && size > 0);
    bool nonzero = false;
    for (size_t i = 0; i < size; ++i)
        nonzero |= bytes[i] != 0;
    assert(nonzero);
    sampleDigest(bytes, size);
}
static void number(std::vector<char> &data, uint32_t v, int size, bool big) {
    for (int i = 0; i < size; ++i)
        data.push_back(static_cast<char>(v >> (8 * (big ? size - 1 - i : i))));
}
int main(int argc, char **argv) {
    assert(argc == 5);
    auto init = std::make_shared<Ship::ResourceInitData>();
    init->Format = RESOURCE_FORMAT_BINARY;
    init->Path = "AudioSample contract";
    SOH::ResourceFactoryBinaryAudioSampleV2 factory;
    for (int big = 0; big < 2; ++big) {
        std::vector<char> bytes;
        number(bytes, 2, 1, big);
        number(bytes, 1, 1, big);
        number(bytes, 0, 1, big);
        number(bytes, 1, 1, big);
        number(bytes, 4, 4, big);
        for (int i = 0; i < 4; ++i)
            number(bytes, 0x80 + i, 1, big);
        number(bytes, 0x12345678, 4, big);
        number(bytes, 0x87654321, 4, big);
        number(bytes, 1, 4, big);
        number(bytes, 16, 4, big);
        for (int i = 0; i < 16; ++i)
            number(bytes, 0x8000 + i, 2, big);
        number(bytes, 2, 4, big);
        number(bytes, 1, 4, big);
        number(bytes, 16, 4, big);
        for (int i = 0; i < 16; ++i)
            number(bytes, 0xfff0 + i, 2, big);
        auto f = std::make_shared<Ship::File>();
        f->Buffer = std::make_shared<std::vector<char>>(bytes);
        auto reader = std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(f->Buffer));
        reader->SetEndianness(big ? Ship::Endianness::Big : Ship::Endianness::Little);
        f->Reader = reader;
        auto resource = std::dynamic_pointer_cast<SOH::AudioSample>(factory.ReadResource(f, init));
        assert(resource);
        assert(resource->sample.codec == 2 && resource->sample.medium == 1 && resource->sample.isRelocated == 1 &&
               resource->sample.size == 4);
        assert(resource->sample.loop == &resource->loop && resource->sample.book == &resource->book &&
               resource->loop.start == 0x12345678 && resource->loop.end == 0x87654321);
        assert(resource->loop.state[0] == -32768 && resource->book.book[0] == -16 && resource->book.book[15] == -1 &&
               resource->tuning == -1.f);
        assert(memcmp(resource->sample.sampleAddr, "\x80\x81\x82\x83", 4) == 0);
    }
    auto wavFile = sampleFile(argv[1]);
    drwav wav;
    assert(drwav_init_memory(&wav, wavFile->Buffer->data(), wavFile->Buffer->size(), nullptr));
    drwav_uint64 frames;
    assert(drwav_get_length_in_pcm_frames(&wav, &frames) == DRWAV_SUCCESS);
    assert(frames == 8192 && wav.channels == 1 && wav.sampleRate == 32000);
    std::vector<int16_t> expected(frames);
    assert(drwav_read_pcm_frames_s16(&wav, frames, expected.data()) == frames);
    drwav_uninit(&wav);
    pcm((uint8_t *)expected.data(), frames * 2);
    auto mp3 = std::make_shared<SOH::AudioSample>(init);
    memset(&mp3->sample, 0, sizeof(mp3->sample));
    Mp3DecoderWorker(mp3, sampleFile(argv[2]));
    pcm(mp3->sample.sampleAddr, 8192 * 2);
    auto flac = std::make_shared<SOH::AudioSample>(init);
    memset(&flac->sample, 0, sizeof(flac->sample));
    FlacDecoderWorker(flac, sampleFile(argv[3]));
    pcm(flac->sample.sampleAddr, 8192 * 2);
    assert(memcmp(expected.data(), flac->sample.sampleAddr, 8192 * 2) == 0);
    auto oggFile = sampleFile(argv[4]);
    auto ogg = std::make_shared<SOH::AudioSample>(init);
    memset(&ogg->sample, 0, sizeof(ogg->sample));
    OggDecoderWorker(ogg, oggFile, init);
    pcm(ogg->sample.sampleAddr, 8192 * 2);
    // The production worker now asks for native order. Prove the Vorbis API's
    // BE and LE modes represent exactly the same numeric signed samples.
    std::vector<char> orders[2];
    for (int big = 0; big < 2; ++big) {
        OggFileData data = {oggFile->Buffer->data(), 0, oggFile->Buffer->size()};
        OggVorbis_File vf;
        assert(ov_open_callbacks(&data, &vf, nullptr, 0, vorbisCallbacks) == 0);
        char buffer[4096];
        int stream;
        long count;
        while ((count = ov_read(&vf, buffer, sizeof(buffer), big, 2, 1, &stream)) > 0)
            orders[big].insert(orders[big].end(), buffer, buffer + count);
        assert(count == 0);
        ov_clear(&vf);
    }
    assert(orders[0].size() == 8192 * 2 && orders[1].size() == orders[0].size());
    for (size_t i = 0; i < orders[0].size(); i += 2)
        assert(orders[0][i] == orders[1][i + 1] && orders[0][i + 1] == orders[1][i]);
    printf("AudioSample binary LE/BE, actual WAV/MP3/FLAC/Vorbis decode, native PCM boundary; hash %llu\n", sampleHash);
}
