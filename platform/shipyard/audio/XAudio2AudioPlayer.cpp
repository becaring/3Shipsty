#include "XAudio2AudioPlayer.h"
#include "audio_log.h"
#include "PcmLayout.h"
#include <algorithm>
#include <cstring>
#include <limits.h>

namespace Ship {
static_assert(ShipyardAudio::PcmMinimumRate == XAUDIO2_MIN_SAMPLE_RATE && ShipyardAudio::PcmMaximumRate == XAUDIO2_MAX_SAMPLE_RATE,
              "PCM validation bounds must match the installed XAudio2 SDK");
XAudio2AudioPlayer::XAudio2AudioPlayer(AudioSettings settings)
    : AudioPlayer(settings), engine_(NULL), master_(NULL), voice_(NULL), voiceError_(0),
      submittedFrames_(0), openedRate_(0), openedChannels_(0), frameBytes_(0),
      capacityFrames_(0), started_(false), diagnosticBlocks_(0), diagnosticNonzero_(0), diagnosticPeak_(0),
      reportStart_(0), lastSubmit_(0), maxSubmitGap_(0), maxStorageWait_(0), reportSubmits_(0),
      emptySubmits_(0), recoveries_(0), maxQueuedFrames_(0), previousGlitches_(0) {}
XAudio2AudioPlayer::~XAudio2AudioPlayer() { DoClose(); }
void XAudio2AudioPlayer::Check(HRESULT result, const char* operation) {
    if (FAILED(result)) ShipyardAudioFatal(operation, result);
}
void XAudio2AudioPlayer::CheckVoice() {
    Check(static_cast<HRESULT>(InterlockedCompareExchange(&voiceError_, 0, 0)), "XAudio2 voice callback");
}
void __stdcall XAudio2AudioPlayer::OnBufferEnd(void* context) {
    ShipyardAudio::PcmBufferPool::Block* block = static_cast<ShipyardAudio::PcmBufferPool::Block*>(context);
    // The voice owns the copied PCM until this callback, as in the SoH donor.
    try { block->owner->Release(block); }
    catch (...) { ShipyardAudioFatal("XAudio2 completion notification", E_FAIL); }
}
void __stdcall XAudio2AudioPlayer::OnVoiceError(void*, HRESULT result) {
    InterlockedExchange(&voiceError_, result);
    try { storage_.Wake(); }
    catch (...) { ShipyardAudioFatal("XAudio2 error notification", E_FAIL); }
}
bool XAudio2AudioPlayer::DoInit() {
    DoClose();
    const int32_t rate = GetSampleRate();
    const int32_t channels = GetNumOutputChannels();
    const int32_t sampleLength = GetSampleLength();
    const int32_t desired = GetDesiredBuffered();
    ShipyardAudio::PcmLayout layout;
    if (!ShipyardAudio::ComputePcmLayout(rate, channels, GetAudioChannels(), sampleLength, desired, layout)) {
        ShipyardAudioLog("XAudio2 rejected settings rate=%d channels=%d mode=%d length=%d desired=%d; AudioPlayer supports stereo, raw51 or matrix51",
            rate, channels, static_cast<int>(GetAudioChannels()), sampleLength, desired);
        return false;
    }
    openedRate_ = layout.sampleRate; openedChannels_ = layout.channels;
    frameBytes_ = layout.frameBytes; capacityFrames_ = layout.capacityFrames;
    if (!storage_.Initialize(layout.blockFrames * frameBytes_)) { DoClose(); return false; }
    HRESULT result = XAudio2Create(&engine_);
    if (SUCCEEDED(result)) result = engine_->CreateMasteringVoice(&master_);
    WAVEFORMATEXTENSIBLE format = {0};
    format.Format.wFormatTag = WAVE_FORMAT_EXTENSIBLE;
    format.Format.nChannels = static_cast<WORD>(channels);
    format.Format.nSamplesPerSec = rate;
    format.Format.wBitsPerSample = 16;
    format.Format.nBlockAlign = static_cast<WORD>(frameBytes_);
    format.Format.nAvgBytesPerSec = rate * frameBytes_;
    format.Format.cbSize = sizeof(WAVEFORMATEXTENSIBLE) - sizeof(WAVEFORMATEX);
    format.Samples.wValidBitsPerSample = 16;
    format.dwChannelMask = channels == 2 ? SPEAKER_STEREO : SPEAKER_5POINT1_SURROUND;
    format.SubFormat = KSDATAFORMAT_SUBTYPE_PCM;
    if (SUCCEEDED(result)) result = engine_->CreateSourceVoice(&voice_, &format.Format, 0, 1.0f, this);
    if (FAILED(result)) {
        ShipyardAudioLog("XAudio2 initialization failed HRESULT=%08x", static_cast<unsigned>(result));
        DoClose();
        return false;
    }
    // Native signed-16 PCM: current AudioPlayer performs matrix decoding before DoPlay.
    ShipyardAudioLog("XAudio2 PCM rate=%u channels=%u frame_bytes=%u storage=%u reserve_frames=%d",
        openedRate_, openedChannels_, frameBytes_, storage_.CapacityBytes() * ShipyardAudio::PcmBufferPool::BlockCount, desired);
    return true;
}
int32_t XAudio2AudioPlayer::Buffered() {
    if (!voice_) return 0;
    CheckVoice();
    XAUDIO2_VOICE_STATE state;
    voice_->GetState(&state);
    UINT64 queued = state.SamplesPlayed < submittedFrames_ ? submittedFrames_ - state.SamplesPlayed : 0;
    return queued > INT_MAX ? INT_MAX : static_cast<int32_t>(queued);
}
void XAudio2AudioPlayer::StartVoice() {
    if (!started_) { Check(voice_->Start(), "XAudio2 primed start"); started_ = true; }
}
void XAudio2AudioPlayer::DoPlay(const uint8_t* buffer, size_t length) {
    if (!voice_ || (length && !buffer) || length % frameBytes_ ||
        GetSampleRate() != static_cast<int32_t>(openedRate_) || GetNumOutputChannels() != static_cast<int32_t>(openedChannels_) ||
        GetDesiredBuffered() < 0 || static_cast<unsigned>(GetDesiredBuffered()) > capacityFrames_) {
        ShipyardAudioFatal("XAudio2 PCM/settings contract", E_INVALIDARG);
    }
    while (length) {
        CheckVoice();
        int32_t queued = Buffered();
        if (started_ && !queued) {
            Check(voice_->Stop(), "XAudio2 rebuffer stop");
            started_ = false;
            ++recoveries_;
        }
        ShipyardAudio::PcmBufferPool::Block* block = storage_.TryAcquire();
        double waitStart = block ? 0 : ShipyardAudioTime();
        while (!block) {
            CheckVoice();
            // Tiny submissions may occupy all slots before reaching the frame reserve.
            // Start preserved queued PCM so backpressure can make progress.
            StartVoice();
            if (!storage_.WaitAvailable(2000)) ShipyardAudioFatal("XAudio2 device stalled", E_FAIL);
            block = storage_.TryAcquire();
        }
        if (waitStart) maxStorageWait_ = (std::max)(maxStorageWait_, ShipyardAudioTime() - waitStart);
        CheckVoice();
        const unsigned bytes = static_cast<unsigned>((std::min)(length, static_cast<size_t>(storage_.CapacityBytes())));
        std::memcpy(block->samples, buffer, bytes);
        if (diagnosticBlocks_ < 600) {
            const int16_t* samples = reinterpret_cast<const int16_t*>(block->samples);
            unsigned nonzero = 0, peak = 0;
            for (unsigned i = 0; i < bytes / sizeof(int16_t); ++i) {
                int sample = samples[i];
                unsigned magnitude = static_cast<unsigned>(sample < 0 ? -sample : sample);
                if (magnitude) ++nonzero;
                if (magnitude > peak) peak = magnitude;
            }
            bool firstSound = nonzero && !diagnosticNonzero_;
            diagnosticNonzero_ += nonzero;
            if (peak > diagnosticPeak_) diagnosticPeak_ = peak;
            ++diagnosticBlocks_;
            if (diagnosticBlocks_ == 1 || diagnosticBlocks_ == 120 || diagnosticBlocks_ == 600 || firstSound)
                ShipyardAudioLog("AUDIO native blocks=%u nonzero_samples=%u peak=%u rate=%u channels=%u",
                    diagnosticBlocks_, diagnosticNonzero_, diagnosticPeak_, openedRate_, openedChannels_);
        }
        XAUDIO2_BUFFER packet = {0};
        packet.AudioBytes = bytes;
        packet.pAudioData = block->samples;
        packet.pContext = block;
        const double now = ShipyardAudioTime();
        if (lastSubmit_) {
            maxSubmitGap_ = (std::max)(maxSubmitGap_, now - lastSubmit_);
            if (!queued) ++emptySubmits_;
        }
        lastSubmit_ = now;
        if (!reportStart_) reportStart_ = now;
        HRESULT result = voice_->SubmitSourceBuffer(&packet);
        if (FAILED(result)) { storage_.Release(block); Check(result, "XAudio2 submit"); }
        submittedFrames_ += bytes / frameBytes_;
        if (!started_ && Buffered() >= GetDesiredBuffered()) StartVoice();
        maxQueuedFrames_ = (std::max)(maxQueuedFrames_, static_cast<unsigned>(queued) + bytes / frameBytes_);
        ++reportSubmits_;
        // SoH360 queue diagnostics, expressed in this voice's actual sample rate.
        if (now - reportStart_ >= 5) {
            XAUDIO2_PERFORMANCE_DATA performance;
            engine_->GetPerformanceData(&performance);
            ShipyardAudioLog("AUDIO queue submits=%u elapsed=%.3f queued_ms=%.2f max_queued_ms=%.2f empty_submits=%u max_submit_gap_ms=%.3f max_storage_wait_ms=%.3f recoveries=%u new_glitches=%u",
                reportSubmits_, now - reportStart_, queued * 1000.0 / openedRate_,
                maxQueuedFrames_ * 1000.0 / openedRate_, emptySubmits_, maxSubmitGap_ * 1000,
                maxStorageWait_ * 1000, recoveries_, performance.GlitchesSinceEngineStarted - previousGlitches_);
            previousGlitches_ = performance.GlitchesSinceEngineStarted;
            reportStart_ = now;
            reportSubmits_ = emptySubmits_ = recoveries_ = maxQueuedFrames_ = 0;
            maxSubmitGap_ = maxStorageWait_ = 0;
        }
        buffer += bytes;
        length -= bytes;
    }
}
void XAudio2AudioPlayer::DoClose() {
    // DestroyVoice completes callback use before storage/event teardown.
    if (voice_) { voice_->Stop(); voice_->DestroyVoice(); voice_ = NULL; }
    if (master_) { master_->DestroyVoice(); master_ = NULL; }
    if (engine_) { engine_->Release(); engine_ = NULL; }
    storage_.Close();
    submittedFrames_ = 0; voiceError_ = 0; started_ = false;
    diagnosticBlocks_ = diagnosticNonzero_ = diagnosticPeak_ = 0;
    reportStart_ = lastSubmit_ = maxSubmitGap_ = maxStorageWait_ = 0;
    reportSubmits_ = emptySubmits_ = recoveries_ = maxQueuedFrames_ = previousGlitches_ = 0;
    openedRate_ = openedChannels_ = frameBytes_ = capacityFrames_ = 0;
}
}
