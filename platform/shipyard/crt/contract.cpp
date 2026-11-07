#include <cmath>
#include <cfenv>
#include <cfloat>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include <limits>

extern "C" float shipyard_roundf(float);
extern "C" float shipyard_truncf(float);
extern "C" float shipyard_nearbyintf(float);
extern "C" int shipyard_snprintf(char*, size_t, const char*, ...);

static uint32_t bits(float value) { uint32_t result; memcpy(&result,&value,4); return result; }
static float value(uint32_t bits) { float result; memcpy(&result,&bits,4); return result; }
static uint64_t digest=1469598103934665603ULL;
static void hash(uint32_t x) { digest=(digest^x)*1099511628211ULL; }
static void require(bool ok, const char* what, uint32_t input=0, int mode=0) {
    if (!ok) { std::fprintf(stderr,"%s input=%08x mode=%d\n",what,input,mode);std::exit(1); }
}

int main() {
    std::vector<uint32_t> samples;
    // Every exponent, representative payloads, and both signs; includes all
    // zeros, subnormal/normal boundaries, half ties, infinities and NaNs.
    const uint32_t payloads[]={0,1,2,0x1fffff,0x200000,0x200001,0x3fffff,0x400000,0x400001,0x5fffff,0x600000,0x600001,0x7ffffe,0x7fffff};
    for(unsigned e=0;e<256;++e) for(auto p:payloads) for(unsigned s=0;s<2;++s) samples.push_back((s<<31)|(e<<23)|p);
    // Every half-integer around zero through +/-4096 and its adjacent floats.
    for(int n=-8192;n<=8192;++n) {
        float f=static_cast<float>(n)*0.5f;
        samples.push_back(bits(f)); samples.push_back(bits(std::nextafter(f,INFINITY)));samples.push_back(bits(std::nextafter(f,-INFINITY)));
    }
    uint32_t rng=0x5eeda11;
    for(unsigned n=0;n<262144;++n) {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;samples.push_back(rng);}
    const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    size_t cases=0;
    for(int mode:modes) {
        require(std::fesetround(mode)==0,"set rounding");
        for(uint32_t input:samples) {
            float f=value(input);
            float a=std::round(f), b=shipyard_roundf(f);
            const bool nan=(input&0x7f800000U)==0x7f800000U && (input&0x7fffffU)!=0;
            require(nan ? std::isnan(b) : bits(a)==bits(b),"round",input,mode);hash(bits(b));
            a=std::trunc(f); b=shipyard_truncf(f);
            require(nan ? std::isnan(b) : bits(a)==bits(b),"trunc",input,mode);hash(bits(b));
            a=std::nearbyint(f);
            std::feclearexcept(FE_ALL_EXCEPT);
            b=shipyard_nearbyintf(f);
            const int flags=std::fetestexcept(FE_ALL_EXCEPT);
            require((flags&FE_INEXACT)==0,"nearby inexact",input,mode);
            if(!nan) require(flags==0,"finite nearby exception",input,mode);
            if(nan && (input&0x00400000U)==0) require((flags&FE_INVALID)!=0,"signaling NaN invalid",input,mode);
            if(nan && (input&0x00400000U)!=0) require(flags==0,"quiet NaN exception",input,mode);
            require(nan ? std::isnan(b) : bits(a)==bits(b),"nearby",input,mode);
            require(std::fegetround()==mode,"rounding preserved",input,mode);
            if(nan) require((bits(b)&0x80400000U)==((input&0x80000000U)|0x00400000U),"NaN sign/quiet",input,mode);
            hash(bits(b));++cases;
        }
        // A sticky inexact flag that is already set must survive, and finite rounding must add
        // no flags when it was clear. Probe all directed modes and signed zero.
        std::feclearexcept(FE_ALL_EXCEPT); std::feraiseexcept(FE_INEXACT|FE_DIVBYZERO);
        const int before=std::fetestexcept(FE_ALL_EXCEPT);
        volatile float r=shipyard_nearbyintf(-1.25f); (void)r;
        require(std::fetestexcept(FE_ALL_EXCEPT)==before,"sticky flags preserved");
    }
    std::fesetround(FE_TONEAREST);
    size_t formats=0;
    for(size_t capacity=0;capacity<130;++capacity) for(int n=-257;n<=257;++n) {
        char original[160], projected[160]; memset(original,0x5a,sizeof(original));memset(projected,0x5a,sizeof(projected));
        const int a=std::snprintf(original+8,capacity,"%+08d|%#x|%.*s|%.3f|%c",n,static_cast<unsigned>(n),n&15,"a longer string",n*0.125,n&127);
        const int b=shipyard_snprintf(projected+8,capacity,"%+08d|%#x|%.*s|%.3f|%c",n,static_cast<unsigned>(n),n&15,"a longer string",n*0.125,n&127);
        require(a==b,"format required length");
        // Secure CRT may fill unused buffer bytes in debug mode; compare the
        // observable output including embedded NULs, terminator and boundaries.
        size_t written=capacity ? (static_cast<size_t>(a)<capacity?static_cast<size_t>(a):capacity-1)+1 : 0;
        require(memcmp(original+8,projected+8,written)==0,"format output");
        for(size_t j=0;j<8;++j) require(projected[j]==0x5a,"format prefix canary");
        for(size_t j=8+capacity;j<sizeof(projected);++j) require(projected[j]==0x5a,"format suffix canary");
        hash(static_cast<uint32_t>(b));for(size_t j=0;j<written;++j)hash(static_cast<unsigned char>(projected[j+8]));++formats;
    }
    require(shipyard_snprintf(NULL,0,"%s:%d","query",42)==8,"null length query");
    char empty='x';require(shipyard_snprintf(&empty,1,"")==0 && empty==0,"empty format");
    // Encoding failure must remain negative even when no output is requested.
    const wchar_t invalidText[]={0xd800,0};
    require(std::snprintf(NULL,0,"%ls",invalidText)<0,"standard encoding error fixture");
    require(shipyard_snprintf(NULL,0,"%ls",invalidText)<0,"encoding error length query");
    char invalid[8]; require(shipyard_snprintf(invalid,sizeof(invalid),"%ls",invalidText)<0,"encoding error write");
    std::printf("float_cases=%zu format_cases=%zu digest=%llu\n",cases,formats,static_cast<unsigned long long>(digest));
}
