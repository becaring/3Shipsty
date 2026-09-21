#include <espeak-ng/espeak_ng.h>
#include <espeak-ng/speak_lib.h>
#include "speech/SpeechQueue.h"
#include "speech/data_boundary.h"
#include <vector>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <algorithm>
#include <thread>
#include <atomic>

static std::vector<short> pcm;
static int calls,stopAfter;
static int Callback(short* input,int count,espeak_EVENT*){
    if(!input)return 0;
    ++calls;if(stopAfter&&calls>=stopAfter)return 1;
    size_t begin=pcm.size();pcm.resize(begin+count);ShipyardSpeechPcmToNative(pcm.data()+begin,reinterpret_cast<const unsigned char*>(input),count);return 0;
}
static void Put32(FILE* f,uint32_t value){for(unsigned i=0;i<4;++i)fputc((value>>(i*8))&255,f);}
static void Wav(const char* name,int rate){FILE* f=fopen(name,"wb");fwrite("RIFF",1,4,f);Put32(f,36+pcm.size()*2);fwrite("WAVEfmt ",1,8,f);Put32(f,16);fputc(1,f);fputc(0,f);fputc(1,f);fputc(0,f);Put32(f,rate);Put32(f,rate*2);fputc(2,f);fputc(0,f);fputc(16,f);fputc(0,f);fwrite("data",1,4,f);Put32(f,pcm.size()*2);for(short sample:pcm){fputc(sample&255,f);fputc((sample>>8)&255,f);}fclose(f);}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(int argc,char** argv){
    CHECK(argc==2);
    ShipyardSpeech::Queue queue;CHECK(queue.Valid());
    char text[]="Copied input",language[]="fr";queue.Submit(text,language);text[0]='X';language[0]='x';ShipyardSpeech::Job job;CHECK(queue.Take(job));CHECK(job.text=="Copied input"&&job.language=="fr"&&queue.Current(job.generation));
    LONG old=job.generation;queue.Submit("superseded","en");queue.Submit("latest","de");CHECK(!queue.Current(old));CHECK(queue.Take(job)&&job.text=="latest"&&job.language=="de");
    old=job.generation;queue.Submit("","de");CHECK(!queue.Current(old));CHECK(queue.Take(job)&&job.text.empty());
    std::atomic<bool> finished(false);std::thread waiter([&](){ShipyardSpeech::Job next;finished=!queue.Take(next);});queue.Stop();waiter.join();CHECK(finished);
    puts("queue: copied text/language, latest-request replacement, empty cancellation, joined stop");
    // Exact locale strings returned by the genuine 9.2.3 TTS application.
    const char* languages[]={"en-US","de-DE","fr-FR"};const char* phrases[]={"Welcome to Hyrule. Open the file selection menu.","Willkommen in Hyrule. Öffne das Menü.","Bienvenue à Hyrule. Ouvrez le menu de sélection."};
    for(int cycle=0;cycle<2;++cycle){
        espeak_ng_InitializePath(argv[1]);espeak_ng_ERROR_CONTEXT context=NULL;CHECK(espeak_ng_Initialize(&context)==ENS_OK);CHECK(espeak_ng_SetRandSeed(0x123456)==ENS_OK);CHECK(espeak_ng_InitializeOutput(ENOUTPUT_MODE_SYNCHRONOUS,60,NULL)==ENS_OK);espeak_SetSynthCallback(Callback);int rate=espeak_ng_GetSampleRate();CHECK(rate>=8000&&rate<=48000);
        for(int lang=0;lang<3;++lang){
            espeak_VOICE voice={};voice.languages=languages[lang];CHECK(espeak_SetVoiceByProperties(&voice)==EE_OK);pcm.clear();calls=0;stopAfter=0;
            CHECK(espeak_Synth(phrases[lang],strlen(phrases[lang])+1,0,POS_CHARACTER,0,espeakCHARS_UTF8,NULL,NULL)==EE_OK);
            unsigned peak=0;size_t nonzero=0;uint64_t hash=1469598103934665603ULL;for(short value:pcm){unsigned magnitude=value<0?-int(value):int(value);peak=(std::max)(peak,magnitude);nonzero+=value!=0;hash=(hash^uint16_t(value))*1099511628211ULL;}
            CHECK(nonzero>rate/4&&pcm.size()>rate&&peak>100);printf("%d:%s rate=%d samples=%zu nonzero=%zu peak=%u hash=%016llx\n",cycle,languages[lang],rate,pcm.size(),nonzero,peak,(unsigned long long)hash);
            if(cycle==0){char path[40];sprintf(path,"speech-%s.wav",languages[lang]);Wav(path,rate);}
            size_t full=pcm.size();pcm.clear();calls=0;stopAfter=2;CHECK(espeak_Synth(phrases[lang],strlen(phrases[lang])+1,0,POS_CHARACTER,0,espeakCHARS_UTF8,NULL,NULL)==EE_OK);CHECK(calls==2&&pcm.size()<full);printf("cancel:%s callbacks=%d samples=%zu\n",languages[lang],calls,pcm.size());stopAfter=0;
        }
        CHECK(espeak_ng_Terminate()==ENS_OK);
    }
}
