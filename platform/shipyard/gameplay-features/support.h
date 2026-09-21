#pragma once
#include "resources/runtime_support.h"
#include "input/compiler.h"
#include "ship/utils/color.h"
namespace Shipyard { namespace GameplayFeatures {
inline Color_RGB8 Rgb(unsigned char r,unsigned char g,unsigned char b){Color_RGB8 v={r,g,b};return v;}
inline double Fmax(double a,double b) {
    if(a!=a)return b;
    if(b!=b)return a;
    if(a==0.0 && b==0.0)return a+b;
    return a>b?a:b;
}
}}
