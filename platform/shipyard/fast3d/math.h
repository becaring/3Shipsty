#pragma once
#include <cmath>

namespace Shipyard { namespace Fast3D {
// C99 round: halfway values go away from zero, independently of rounding mode.
// Splitting first avoids rounding x + 0.5 up for values just below a tie and
// retains signed zero, infinities and NaNs through the CRT modf contract.
inline double Round(double value) {
    double integral;
    double fraction=std::modf(value,&integral);
    if (fraction>=0.5) return integral+1.0;
    if (fraction<=-0.5) return integral-1.0;
    return integral;
}
inline float Round(float value) { return static_cast<float>(Round(static_cast<double>(value))); }

template<class T> const T& Clamp(const T& value,const T& low,const T& high) {
    return value<low ? low : high<value ? high : value;
}
} }
