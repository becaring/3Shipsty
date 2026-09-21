#pragma once
#include <string>
#include <sstream>
#include <locale>
#include <algorithm>
#include <set>
#include <vector>
#include <stdint.h>
namespace Shipyard { namespace Generation {
template<class T> std::string Decimal(T value) {
    std::ostringstream out;out.imbue(std::locale::classic());out<<static_cast<int64_t>(value);return out.str();
}
template<class T> void Merge(std::set<T>& to,std::set<T>& from) {
    typename std::set<T>::iterator it=from.begin();
    while(it!=from.end()) { typename std::set<T>::iterator current=it++;if(to.insert(*current).second)from.erase(current); }
}
template<class T> size_t Erase(std::vector<T>& values,const T& value) {
    const size_t oldSize=values.size();values.erase(std::remove(values.begin(),values.end(),value),values.end());return oldSize-values.size();
}
} }
