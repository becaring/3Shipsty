#pragma once
#include "soh/Enhancements/speechsynthesizer/SpeechSynthesizer.h"
#include "speech/SpeechQueue.h"
#include <xaudio2.h>
#include <espeak-ng/speak_lib.h>

class XboxSpeechSynthesizer : public SpeechSynthesizer,private IXAudio2VoiceCallback {
    struct Block {short* samples;size_t capacity;volatile LONG busy;XboxSpeechSynthesizer* owner;Block():samples(NULL),capacity(0),busy(0),owner(NULL){}};
    ShipyardSpeech::Queue* queue_;HANDLE thread_,available_;IXAudio2* engine_;IXAudio2MasteringVoice* master_;IXAudio2SourceVoice* voice_;
    Block blocks_[4];LONG speakingGeneration_;volatile LONG voiceError_;unsigned sampleRate_;bool synthesisReady_;
    static XboxSpeechSynthesizer* callbackOwner_;static volatile LONG ownerClaim_;
    static DWORD WINAPI WorkerEntry(void*);void Worker();static int SynthesisCallback(short*,int,espeak_EVENT*);
    int SubmitPcm(short*,int,espeak_EVENT*);bool OpenVoice(unsigned);void CloseVoice();
    void Log(const char*,long);
    void __stdcall OnVoiceProcessingPassStart(UINT32){} void __stdcall OnVoiceProcessingPassEnd(){}
    void __stdcall OnStreamEnd(){} void __stdcall OnBufferStart(void*){} void __stdcall OnLoopEnd(void*){}
    void __stdcall OnBufferEnd(void*);void __stdcall OnVoiceError(void*,HRESULT);
    XboxSpeechSynthesizer(const XboxSpeechSynthesizer&);XboxSpeechSynthesizer& operator=(const XboxSpeechSynthesizer&);
protected:
    bool DoInit();void DoUninitialize();
public:
    XboxSpeechSynthesizer();~XboxSpeechSynthesizer();void Speak(const char*,const char*);
};
// Base has no virtual destructor. This is the matching concrete deletion path.
void DestroyXboxSpeechSynthesizer(SpeechSynthesizer*);
