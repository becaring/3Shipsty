#pragma once
#include <memory>
#include "resources/runtime_support.h"
#include "ship/utils/color.h"
namespace Shipyard { namespace GuiCompat {
template<class T,class U> std::shared_ptr<T> ReinterpretPointerCast(const std::shared_ptr<U>& owner){
    return std::shared_ptr<T>(owner,reinterpret_cast<T*>(owner.get()));
}
inline Color_RGB8 Rgb(uint8_t r,uint8_t g,uint8_t b){Color_RGB8 result={r,g,b};return result;}
}}
