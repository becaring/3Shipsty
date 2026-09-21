#include <cassert>
#include <cstring>
#include <iostream>
#include <map>
int main() {
    ActorDBInit defaults;
    assert(defaults.name.empty() && defaults.desc.empty());
    assert(defaults.category==0 && defaults.flags==0 && defaults.objectId==0);
    assert(defaults.instanceSize==sizeof(Actor));
    assert(!defaults.init && !defaults.destroy && !defaults.update && !defaults.draw && !defaults.reset);
    ActorDB::Entry empty;
    assert(!empty.entry.name && !empty.entry.desc && !empty.entry.valid && !empty.entry.numLoaded);
    assert(!empty.entry.id && !empty.entry.category && !empty.entry.flags && !empty.entry.objectId);
    assert(!empty.entry.instanceSize && !empty.entry.init && !empty.entry.destroy && !empty.entry.update);
    assert(!empty.entry.draw && !empty.entry.reset);
    ActorDB::Entry a;
    a.SetName(std::string(512,'n')); a.SetDesc(std::string(1024,'d'));
    a.entry.id=213; a.entry.valid=1; a.entry.flags=712; a.entry.numLoaded=3;
    ActorDB::Entry b(a),c; c=a;
    a.SetName("changed"); a.SetDesc("changed");
    assert(b.name==std::string(512,'n') && c.desc==std::string(1024,'d'));
    assert(b.entry.name==b.name.c_str() && c.entry.desc==c.desc.c_str());
    assert(b.entry.name!=c.entry.name && b.entry.desc!=c.entry.desc);
    assert(b.entry.id==213 && c.entry.flags==712 && c.entry.numLoaded==3);
    c=c;
    assert(c.entry.name==c.name.c_str() && c.entry.desc==c.desc.c_str());
    std::vector<ActorDB::Entry> entries; entries.push_back(b);
    for(int i=0;i<100;++i) entries.push_back(c);
    for(size_t i=0;i<entries.size();++i) {
        assert(entries[i].entry.name==entries[i].name.c_str());
        assert(entries[i].entry.desc==entries[i].desc.c_str());
    }
    std::map<u16,std::string> sorted;
    for(size_t i=0;i<sizeof(actorDescriptionData)/sizeof(actorDescriptionData[0]);++i) {
        const auto& row=actorDescriptionData[i];
        assert(actorDescriptions.find(row.first)!=actorDescriptions.end());
        sorted[row.first]=actorDescriptions[row.first];
    }
    for(const auto& row:sorted)std::cout<<row.first<<':'<<row.second<<'\n';
    std::cout<<"ActorDB descriptions, defaults and owned Entry copies passed\n";
}
