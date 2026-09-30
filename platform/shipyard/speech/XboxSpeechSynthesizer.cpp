#include "speech/XboxSpeechSynthesizer.h"
#include "speech/data_boundary.h"
#include "async/native.h"
#include <espeak-ng/espeak_ng.h>
#include <cstdio>
#include <cstring>
#include <malloc.h>

XboxSpeechSynthesizer* XboxSpeechSynthesizer::callbackOwner_=NULL;
volatile LONG XboxSpeechSynthesizer::ownerClaim_=0;
XboxSpeechSynthesizer::XboxSpeechSynthesizer():queue_(NULL),thread_(NULL),available_(NULL),engine_(NULL),master_(NULL),voice_(NULL),speakingGeneration_(0),voiceError_(0),sampleRate_(0),synthesisReady_(false){for(unsigned i=0;i<4;++i)blocks_[i].owner=this;}
XboxSpeechSynthesizer::~XboxSpeechSynthesizer(){Uninitialize();for(unsigned i=0;i<4;++i)_aligned_free(blocks_[i].samples);}
void XboxSpeechSynthesizer::Log(const char* what,long code){char message[240];_snprintf(message,sizeof(message),"[3Shipsty speech] %s (%ld)\n",what,code);message[sizeof(message)-1]=0;OutputDebugStringA(message);fprintf(stderr,"%s",message);}
bool XboxSpeechSynthesizer::DoInit(){
    if(InterlockedCompareExchange(&ownerClaim_,1,0)!=0){Log("eSpeak singleton already owned",0);return false;}
    callbackOwner_=this;
    try{queue_=new ShipyardSpeech::Queue("en");}catch(...){Log("speech queue allocation failed",0);DoUninitialize();return false;}
    available_=CreateEvent(NULL,FALSE,FALSE,NULL);
    if(!queue_->Valid()||!available_){Log("worker event creation failed",GetLastError());DoUninitialize();return false;}
    // The legacy espeak_Initialize returns a rate even after some initialization
    // errors. Use its real checked NG initialization primitives instead.
    espeak_ng_InitializePath("game:\\espeak-ng-data");espeak_ng_ERROR_CONTEXT context=NULL;
    espeak_ng_STATUS status=espeak_ng_Initialize(&context);
    if(status!=ENS_OK){espeak_ng_PrintStatusCodeMessage(status,stderr,context);espeak_ng_ClearErrorContext(&context);Log("speech data initialization failed",status);DoUninitialize();return false;}
    synthesisReady_=true;status=espeak_ng_InitializeOutput(ENOUTPUT_MODE_SYNCHRONOUS,60,NULL);
    if(status!=ENS_OK){Log("synthesis buffer initialization failed",status);DoUninitialize();return false;}
    sampleRate_=espeak_ng_GetSampleRate();espeak_SetSynthCallback(SynthesisCallback);
    HRESULT result=XAudio2Create(&engine_);if(SUCCEEDED(result))result=engine_->CreateMasteringVoice(&master_);
    if(FAILED(result)){Log("XAudio2 speech initialization failed",result);DoUninitialize();return false;}
    thread_=CreateThread(NULL,256*1024,WorkerEntry,this,0,NULL);
    if(!thread_){Log("speech worker creation failed",GetLastError());DoUninitialize();return false;}
    // Synthesis runs on the service hardware thread rather than inheriting the
    // title thread's; placement is advisory and a refused move keeps it there.
    XSetThreadProcessor(thread_,Shipyard::Async::ServiceProcessor);
    Log("real eSpeak NG speech worker initialized",sampleRate_);return true;
}
void XboxSpeechSynthesizer::DoUninitialize(){
    if(callbackOwner_!=this)return;
    if(queue_)queue_->Stop();if(available_)SetEvent(available_);
    if(thread_){WaitForSingleObject(thread_,INFINITE);CloseHandle(thread_);thread_=NULL;}
    CloseVoice();if(master_){master_->DestroyVoice();master_=NULL;}if(engine_){engine_->Release();engine_=NULL;}
    // Safe also after partial initialization: the engine frees nullable state.
    espeak_SetSynthCallback(NULL);espeak_ng_Terminate();synthesisReady_=false;
    if(available_){CloseHandle(available_);available_=NULL;}delete queue_;queue_=NULL;
    callbackOwner_=NULL;InterlockedExchange(&ownerClaim_,0);
}
void XboxSpeechSynthesizer::Speak(const char* text,const char* language){if(IsInitialized()&&queue_)queue_->Submit(text,language);}
DWORD WINAPI XboxSpeechSynthesizer::WorkerEntry(void* self){static_cast<XboxSpeechSynthesizer*>(self)->Worker();return 0;}
void XboxSpeechSynthesizer::Worker(){
    ShipyardSpeech::Job job;
    while(queue_->Take(job)){
        CloseVoice();speakingGeneration_=job.generation;
        if(job.text.empty()||!queue_->Current(job.generation))continue;
        espeak_VOICE voice={0};voice.languages=job.language.c_str();
        if(espeak_SetVoiceByProperties(&voice)!=EE_OK){Log("requested speech language unavailable",0);continue;}
        if(!OpenVoice(sampleRate_))continue;
        espeak_ERROR result=espeak_Synth(job.text.c_str(),job.text.size()+1,0,POS_CHARACTER,0,espeakCHARS_UTF8,NULL,this);
        if(result!=EE_OK)Log("synthesis failed",result);
        if(result!=EE_OK||InterlockedCompareExchange(&voiceError_,0,0))CloseVoice();
        // The completed utterance keeps playing until its buffers finish or a
        // new request arrives; Take waits without owning synthesis/voice memory.
    }
    CloseVoice();
}
bool XboxSpeechSynthesizer::OpenVoice(unsigned rate){
    WAVEFORMATEX format={0};format.wFormatTag=WAVE_FORMAT_PCM;format.nChannels=1;format.nSamplesPerSec=rate;format.wBitsPerSample=16;format.nBlockAlign=2;format.nAvgBytesPerSec=rate*2;
    HRESULT result=engine_->CreateSourceVoice(&voice_,&format,0,1.0f,this);
    if(SUCCEEDED(result))result=voice_->Start();if(FAILED(result)){Log("speech source voice failed",result);CloseVoice();return false;}
    sampleRate_=rate;InterlockedExchange(&voiceError_,0);return true;
}
void XboxSpeechSynthesizer::CloseVoice(){if(voice_){voice_->Stop();voice_->DestroyVoice();voice_=NULL;}for(unsigned i=0;i<4;++i)InterlockedExchange(&blocks_[i].busy,0);}
void __stdcall XboxSpeechSynthesizer::OnBufferEnd(void* context){Block* block=static_cast<Block*>(context);InterlockedExchange(&block->busy,0);SetEvent(block->owner->available_);}
void __stdcall XboxSpeechSynthesizer::OnVoiceError(void*,HRESULT error){InterlockedExchange(&voiceError_,error);SetEvent(available_);}
int XboxSpeechSynthesizer::SynthesisCallback(short* samples,int count,espeak_EVENT* events){return callbackOwner_?callbackOwner_->SubmitPcm(samples,count,events):1;}
int XboxSpeechSynthesizer::SubmitPcm(short* samples,int count,espeak_EVENT* events){
    if(!queue_->Current(speakingGeneration_))return 1;
    if(InterlockedCompareExchange(&voiceError_,0,0)){Log("speech audio callback error",voiceError_);return 1;}
    for(espeak_EVENT* e=events;e&&e->type!=espeakEVENT_LIST_TERMINATED;++e){
        if(e->type==espeakEVENT_SAMPLERATE&&e->id.number!=sampleRate_){
            XAUDIO2_VOICE_STATE state;do{voice_->GetState(&state);if(!state.BuffersQueued)break;if(!queue_->Current(speakingGeneration_))return 1;WaitForSingleObject(available_,10);}while(true);
            CloseVoice();if(!OpenVoice(e->id.number))return 1;
        }
    }
    if(!samples||count<=0)return 0;
    Block* block=NULL;
    while(!block){
        if(!queue_->Current(speakingGeneration_)||InterlockedCompareExchange(&voiceError_,0,0))return 1;
        for(unsigned i=0;i<4;++i)if(InterlockedCompareExchange(&blocks_[i].busy,1,0)==0){block=&blocks_[i];break;}
        if(!block)WaitForSingleObject(available_,10);
    }
    if(block->capacity<static_cast<size_t>(count)){
        short* replacement=static_cast<short*>(_aligned_malloc(static_cast<size_t>(count)*2,16));
        if(!replacement){InterlockedExchange(&block->busy,0);InterlockedExchange(&voiceError_,E_OUTOFMEMORY);Log("speech PCM allocation failed",count);return 1;}
        _aligned_free(block->samples);block->samples=replacement;block->capacity=count;
    }
    ShipyardSpeechPcmToNative(block->samples,reinterpret_cast<const unsigned char*>(samples),count);
    XAUDIO2_BUFFER packet={0};packet.AudioBytes=count*2;packet.pAudioData=reinterpret_cast<const BYTE*>(block->samples);packet.pContext=block;
    HRESULT result=voice_->SubmitSourceBuffer(&packet);if(FAILED(result)){InterlockedExchange(&block->busy,0);InterlockedExchange(&voiceError_,result);Log("speech PCM submission failed",result);return 1;}return 0;
}
void DestroyXboxSpeechSynthesizer(SpeechSynthesizer* speech){delete static_cast<XboxSpeechSynthesizer*>(speech);}
