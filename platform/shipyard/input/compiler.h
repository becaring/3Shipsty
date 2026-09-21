#ifndef SHIPYARD_INPUT_COMPILER_COMPILER_H
#define SHIPYARD_INPUT_COMPILER_COMPILER_H
#include "resources/runtime_support.h"
#include <stdint.h>
#ifndef CONTROLLERBUTTONS_T
#define CONTROLLERBUTTONS_T uint32_t
#endif
typedef char ShipyardInputRequiresModernButtonWidth[(sizeof(CONTROLLERBUTTONS_T)==4)?1:-1];
#include <sstream>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <cmath>
#include <float.h>
namespace ShipyardInputCompiler {
template<class C, class K> bool Contains(const C& c, const K& k) { return c.find(k) != c.end(); }
template<class T> std::string ToString(T value) { std::ostringstream out; out << value; return out.str(); }
template<class T> T Clamp(T value, T low, T high) { return value < low ? low : (high < value ? high : value); }
inline double Round(double value) {
    if (!_finite(value) || value == 0) return value;
    const double magnitude = fabs(value);
    double integral = floor(magnitude);
    if (magnitude - integral >= 0.5) integral += 1.0;
    return _copysign(integral, value);
}
template<class C> struct Append { static void Put(C& c, const typename C::value_type& value) { c.insert(value); } };
template<class T, class A> struct Append<std::vector<T,A> > { static void Put(std::vector<T,A>& c, const T& value) { c.push_back(value); } };
template<class C> class Build {
    C value_;
public:
    Build& Add(const typename C::value_type& value) { Append<C>::Put(value_, value); return *this; }
    C Get() const { return value_; }
};
}
#endif
