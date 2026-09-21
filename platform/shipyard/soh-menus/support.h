#pragma once
#include "soh-ui/value_init.h"
#include <utility>
namespace Shipyard { namespace SohMenus {
// operator[] value-initializes an absent mapped value. XDK's explicit generated
// constructors require the tag to retain this behavior for these menu types.
template<class Map,class Key> typename Map::mapped_type& ValueIndex(Map& map,const Key& key) {
    typename Map::iterator found=map.find(key);
    if(found!=map.end())return found->second;
    return map.insert(std::make_pair(typename Map::key_type(key),
        typename Map::mapped_type(Shipyard::SohUI::ValueInit()))).first->second;
}
} }
