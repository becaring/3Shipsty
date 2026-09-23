#include "services.h"
#include "metrics.h"
#include "context/platform.h"
#include <spdlog/spdlog.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
__declspec(thread) ShipyardPerfSample shipyard_graphics_samples[SHIPYARD_PERF_COUNT]={};
static bool verifyReuse=false;
void Shipyard_SetGraphicsVerification(bool enabled){verifyReuse=enabled;}
bool Shipyard_VerifyFast3DReuse(){return verifyReuse;}
void Shipyard_Log(const char* format,...) {
    char buffer[2048];va_list args;va_start(args,format);_vsnprintf_s(buffer,sizeof(buffer),_TRUNCATE,format,args);va_end(args);
    spdlog::info("{}",buffer);
}
// Legacy bounded bring-up call sites remain linkable, but release builds do
// not format or emit their high-volume diagnostic events.
extern "C" void Shipyard_RuntimeTrace(const char*,...) {}
void Shipyard_Fatal(const char* operation,HRESULT result){
    Shipyard::Platform::RecordStartupFatal(operation,static_cast<unsigned long>(result));
    try{spdlog::critical("Xenos failure: {} ({:08x})",operation,static_cast<unsigned>(result));spdlog::default_logger()->flush();}
    catch(...){OutputDebugStringA("Shipyard fatal graphics failure while logging\n");}
    std::abort();
}
double Shipyard_Time(){LARGE_INTEGER tick,freq;QueryPerformanceCounter(&tick);QueryPerformanceFrequency(&freq);return double(tick.QuadPart)/double(freq.QuadPart);}
bool Shipyard_WriteFile(const char* relative,const void* bytes,size_t size){
    // Diagnostic only. Modern writable storage owns future shader persistence.
    std::string path="game:\\";path+=relative;FILE* file=fopen(path.c_str(),"wb");if(!file)return false;
    bool ok=fwrite(bytes,1,size,file)==size;return fclose(file)==0 && ok;
}
