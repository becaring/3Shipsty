#pragma once
#include <cstddef>
#include <utility>
#include <algorithm>
#include <stdint.h>
#include "randomizer-context/colors.h"
#include "soh/Enhancements/nametag.h"
namespace Shipyard { namespace ApplicationWindows {
inline int Popcount(uint32_t v) { int count=0;while(v){v&=v-1;++count;}return count; }
inline Vec3f Vector3(float x,float y,float z) { Vec3f v={x,y,z};return v; }
inline Vtx NormalVertex(int16_t x,int16_t y,int16_t z,int16_t s,int16_t t,int8_t nx,int8_t ny,int8_t nz,uint8_t a) {
    Vtx v={};v.n.ob[0]=x;v.n.ob[1]=y;v.n.ob[2]=z;v.n.flag=0;v.n.tc[0]=s;v.n.tc[1]=t;v.n.n[0]=nx;v.n.n[1]=ny;v.n.n[2]=nz;v.n.a=a;return v;
}
inline NameTagOptions NameOptions(const char* tag,bool noZ) { NameTagOptions o={tag,0,{0,0,0,0},static_cast<uint8_t>(noZ)};return o; }
template<class Map,class Row,size_t N> Map MapFromRows(const Row (&rows)[N]) {
    Map result;
    for(size_t i=0;i<N;++i) result.insert(std::make_pair(rows[i].first,rows[i].second));
    return result;
}
}}
