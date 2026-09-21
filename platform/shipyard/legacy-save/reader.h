#pragma once
#include <stddef.h>
#include <string.h>
#include <stdexcept>
#include <vector>
#include <fstream>
#include <iterator>
#include <string>
#include <limits>
namespace Shipyard { namespace LegacySave {
enum Order { Little, Big };
class Bytes {
    const unsigned char* bytes_;
    size_t size_;
public:
    Bytes(const void* bytes, size_t size) : bytes_(static_cast<const unsigned char*>(bytes)), size_(size) {}
    void Require(size_t offset, size_t count) const {
        if (offset > size_ || count > size_ - offset) throw std::runtime_error("Truncated legacy save");
    }
    const unsigned char* At(size_t offset, size_t count) const { Require(offset,count); return bytes_ + offset; }
    unsigned Value(size_t offset, size_t width, Order order) const {
        if (width!=1 && width!=2 && width!=4) throw std::invalid_argument("Legacy scalar width");
        Require(offset,width);
        unsigned value = 0;
        for (size_t i=0; i<width; ++i) value = (value << 8) | bytes_[offset + (order == Little ? width-i-1 : i)];
        return value;
    }
    template<class T> void Scalar(size_t offset, T& out, Order order) const {
        typedef char Width[(sizeof(T)==1 || sizeof(T)==2 || sizeof(T)==4) ? 1 : -1];
        typedef char NativeWidths[(sizeof(unsigned)==4 && sizeof(unsigned short)==2)?1:-1];
        (void)sizeof(Width); (void)sizeof(NativeWidths);
        unsigned value=Value(offset,sizeof(T),order);
        if (sizeof(T)==1) { unsigned char bits=static_cast<unsigned char>(value); memcpy(&out,&bits,1); }
        else if (sizeof(T)==2) { unsigned short bits=static_cast<unsigned short>(value); memcpy(&out,&bits,2); }
        else { memcpy(&out,&value,4); }
    }
};
inline std::vector<unsigned char> Read(const std::string& path) {
    std::ifstream input(path.c_str(), std::ios::binary);
    if (!input) throw std::runtime_error("Cannot read legacy save");
    input.seekg(0,std::ios::end);
    const std::streamoff length=input.tellg();
    if (length<0 || static_cast<unsigned long long>(length)>static_cast<unsigned long long>((std::numeric_limits<size_t>::max)()) ||
        length>(std::numeric_limits<std::streamsize>::max)()) throw std::runtime_error("Cannot size legacy save");
    input.seekg(0,std::ios::beg);
    if (!input) throw std::runtime_error("Cannot seek legacy save");
    std::vector<unsigned char> data(static_cast<size_t>(length));
    if (length) {
        input.read(reinterpret_cast<char*>(&data[0]),static_cast<std::streamsize>(length));
        if (!input || input.gcount()!=length) throw std::runtime_error("Legacy save read failed");
    }
    return data;
}
inline size_t Slot(unsigned index) { return 0x20 + static_cast<size_t>(index)*0x1450; }
inline bool Occupied(const Bytes& bytes, unsigned index) { return memcmp(bytes.At(Slot(index)+0x1C,6),"ZELDAZ",6)==0; }
inline bool Checksum(const Bytes& bytes, unsigned index, Order order) {
    const size_t base=Slot(index); unsigned sum=0;
    for (size_t offset=0; offset<0x1352; offset+=2) sum += bytes.Value(base+offset,2,order);
    return (sum & 0xffffu)==bytes.Value(base+0x1352,2,order);
}
inline bool VanillaCapacity(const Bytes& bytes, unsigned index, Order order) {
    const unsigned capacity=bytes.Value(Slot(index)+0x2E,2,order);
    return capacity>=0x30 && capacity<=0x140 && (capacity&15)==0;
}
inline Order Validate(const Bytes& bytes) {
    static const unsigned char magic[]={0x98,0x09,0x10,0x21,'Z','E','L','D','A'};
    bytes.Require(0,Slot(2)+0x1428);
    if (memcmp(bytes.At(3,9),magic,9)) throw std::runtime_error("Invalid legacy save magic");
    bool little=true,big=true,vanillaLittle=true,vanillaBig=true,occupied=false;
    for (unsigned i=0;i<3;++i) {
      if (!Occupied(bytes,i)) {
        static const unsigned char empty[6]={0,0,0,0,0,0};
        if (memcmp(bytes.At(Slot(i)+0x1C,6),empty,6)) throw std::runtime_error("Corrupt legacy save slot marker");
        continue;
      }
        occupied=true;
        little=little && Checksum(bytes,i,Little) && bytes.Value(Slot(i)+4,4,Little)<=1;
        big=big && Checksum(bytes,i,Big) && bytes.Value(Slot(i)+4,4,Big)<=1;
        vanillaLittle=vanillaLittle && VanillaCapacity(bytes,i,Little);
        vanillaBig=vanillaBig && VanillaCapacity(bytes,i,Big);
    }
    if (!occupied) return Little; // No typed slot data will be consumed.
    if (little!=big) return little ? Little : Big;
    if (little && vanillaLittle!=vanillaBig) return vanillaLittle ? Little : Big;
    throw std::runtime_error(little ? "Ambiguous legacy save byte order" : "Corrupt or unsupported legacy save representation");
}
}}
