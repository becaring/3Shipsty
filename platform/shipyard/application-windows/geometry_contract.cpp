static void Geometry(const std::vector<Vtx>& vertices,const std::vector<Gfx>& commands) {
    printf("Geometry %u %u\n",(unsigned)vertices.size(),(unsigned)commands.size());
    for(size_t i=0;i<vertices.size();++i) {
        const Vtx& v=vertices[i];printf("V %d %d %d %u %d %d %d %d %d %u\n",v.n.ob[0],v.n.ob[1],v.n.ob[2],v.n.flag,v.n.tc[0],v.n.tc[1],v.n.n[0],v.n.n[1],v.n.n[2],v.n.a);
    }
    for(size_t i=0;i<commands.size();++i) {
        uintptr_t word=commands[i].words.w1;
        if(((commands[i].words.w0>>24)&255)==G_VTX) {
            assert(word>=(uintptr_t)vertices.data() && word<(uintptr_t)(vertices.data()+vertices.size()));
            word-=(uintptr_t)vertices.data();
        }
        printf("G %llu %llu\n",(unsigned long long)commands[i].words.w0,(unsigned long long)word);
    }
}
template<class T> static void Icons(const T& map) {
    for(auto it=map.begin();it!=map.end();++it) {
        const auto& v=it->second;printf("I %u %u %s %s %s\n",(unsigned)it->first,v.id,v.name.c_str(),v.nameFaded.c_str(),v.texturePath.c_str());
    }
}
int main() {
    typedef decltype(GetPerformanceTimer(PT_WHOLE_SEED)) Duration;
    for(int i=0;i<PT_MAX;++i) {totalTimes[i]=Duration(i+0.25);assert(GetPerformanceTimer((TimerID)i).count()==i+0.25);}
    ResetPerformanceTimer(PT_LOGIC_RESET);assert(GetPerformanceTimer(PT_LOGIC_RESET).count()==0);
    assert(GetPerformanceTimer(PT_WHOLE_SEED).count()==0.25);ResetPerformanceTimers();
    for(int i=0;i<PT_MAX;++i) assert(GetPerformanceTimer((TimerID)i).count()==0);
    StartPerformanceTimer(PT_WHOLE_SEED);Sleep(2);StopPerformanceTimer(PT_WHOLE_SEED);
    double first=GetPerformanceTimer(PT_WHOLE_SEED).count();assert(first>0 && first<10000);
    StartPerformanceTimer(PT_WHOLE_SEED);Sleep(2);StopPerformanceTimer(PT_WHOLE_SEED);
    assert(GetPerformanceTimer(PT_WHOLE_SEED).count()>first);ResetPerformanceTimers();puts("Timer values/reset/real clock accumulation pass");
    CreateCylinderData();CreateSphereData();Geometry(cylinderVtx,cylinderGfx);Geometry(sphereVtx,sphereGfx);
    Icons(itemMapping);Icons(gregMapping);Icons(customItemsMapping);Icons(actionShuffleMapping);Icons(jabbernutMapping);Icons(questMapping);
    for(auto i=songMapping.begin();i!=songMapping.end();++i) {const auto& s=i->second;printf("S %u %s %s %.9g %.9g %.9g %.9g\n",s.id,s.name.c_str(),s.nameFaded.c_str(),s.color.x,s.color.y,s.color.z,s.color.w);}
    for(size_t i=0;i<vanillaSongMapping.size();++i) {const auto& s=vanillaSongMapping[i];printf("N %u %s %s %.9g %.9g %.9g %.9g\n",s.id,s.name.c_str(),s.nameFaded.c_str(),s.color.x,s.color.y,s.color.z,s.color.w);}
    for(unsigned i=0;i<65536;++i) {const char* texture=GetTextureForItemId(i);assert((texture!=nullptr)==(itemMapping.count(i)!=0));}
    for(unsigned i=0;i<65536;++i) {uint32_t value=i|(i<<16);assert(Shipyard::ApplicationWindows::Popcount(value)==std::popcount(value));}
    for(int s=-512;s<=512;++s) {
        Vtx expected=gdSPDefVtxN(-32768,32767,(int16_t)s,s,(-s),-128,127,-1,255);
        Vtx actual=Shipyard::ApplicationWindows::NormalVertex(-32768,32767,(int16_t)s,qs105(s),qs105(-s),-128,127,-1,255);
        assert(expected.n.tc[0]==actual.n.tc[0] && expected.n.tc[1]==actual.n.tc[1] && expected.n.flag==actual.n.flag && expected.n.n[2]==actual.n.n[2]);
    }
    puts("65536 icon lookups/popcounts and 1025 signed vertex coordinate cases pass");
}
