// Included after mechanically extracted complete upstream/projected methods.
// No Context, archive or CVar substitutes are linked into this audit.
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    using namespace SOH;
    for (int stereo=0;stereo<2;++stereo) for (int loop=0;loop<2;++loop)
    for (unsigned delay=0;delay<65536;delay+=127) {
        Ship::BinaryWriter writer;
        writer.SetEndianness(Ship::Endianness::Big);
        if(stereo) WriteStereoSingleSeq(&writer,(uint16_t)delay,1,loop!=0);
        else WriteMonoSingleSeq(&writer,(uint16_t)delay,1,loop!=0);
        std::vector<char> data=writer.ToVector();
        assert((unsigned char)data[0]==0xd3 && (unsigned char)data[1]==0x20);
        assert((unsigned char)data[4]==0xd7 && data[5]==0 && data[6]==3);
        assert((unsigned char)data[7]==0x90 && data[8]==0);
        unsigned channel=(unsigned char)data[9];
        assert(channel<data.size() && ((unsigned char)data[channel]==0x88 || (unsigned char)data[channel]==0xc4));
        uint64_t hash=1469598103934665603ULL;
        for(size_t i=0;i<data.size();++i) {hash^=(unsigned char)data[i];hash*=1099511628211ULL;}
        std::printf("seq %u %d %d %zu %016llx\n",delay,stereo,loop,data.size(),(unsigned long long)hash);
    }
    assert(ResourceFactoryXMLSoundFontV0::MediumStrToInt("Cart","fixture")==2);
    assert(ResourceFactoryXMLSoundFontV0::CachePolicyToInt("Permanent","fixture")==3);
    for(int kind=0;kind<2;++kind) {
        bool threw=false;
        try {
            if(kind) ResourceFactoryXMLSoundFontV0::MediumStrToInt("Bad","fixture");
            else ResourceFactoryXMLSoundFontV0::CachePolicyToInt("Bad","fixture");
        } catch(const std::runtime_error& e) { threw=true;std::printf("error %s\n",e.what()); }
        assert(threw);
    }
    tinyxml2::XMLDocument envelope;
    envelope.Parse("<Envelopes><Envelope Delay='4660' Arg='-2'/><Envelope Delay='-1' Arg='32767'/></Envelopes>");
    unsigned count=0;
    std::vector<AdsrEnvelope> env=ParseEnvelopes(nullptr,envelope.RootElement(),&count);
    assert(count==2 && env.size()==2);
    const unsigned char* bytes=reinterpret_cast<const unsigned char*>(env.data());
    const unsigned char expected[]={0x12,0x34,0xff,0xfe,0xff,0xff,0x7f,0xff};
    assert(memcmp(bytes,expected,sizeof(expected))==0);
    std::shared_ptr<Ship::File> file=std::make_shared<Ship::File>();
    std::shared_ptr<tinyxml2::XMLDocument> doc=std::make_shared<tinyxml2::XMLDocument>();
    doc->Parse("<Path><PathData><Point X='-1' Y='4660' Z='-32768'/><Point X='2'/></PathData><PathData/></Path>");
    file->Reader=doc;
    std::shared_ptr<Ship::ResourceInitData> init=std::make_shared<Ship::ResourceInitData>();
    init->Format=RESOURCE_FORMAT_XML;
    ResourceFactoryXMLPathV0 factory;
    std::shared_ptr<Path> path=std::dynamic_pointer_cast<Path>(factory.ReadResource(file,init));
    assert(path && path->numPaths==2 && path->pathData[0].count==2 && path->pathData[1].count==0);
    assert(path->pathData[0].points==path->paths[0].data());
    assert(path->pathData[0].points[0].x==-1 && path->pathData[0].points[0].z==-32768);
    assert(path->GetPointer()==path->pathData.data() && path->GetPointerSize()==2*sizeof(PathData));
    char small[4]; assert(Shipyard::SohResources::snprintf(small,sizeof(small),"%s","abcdef")==6);
    assert(strcmp(small,"abc")==0);
    assert(Shipyard::SohResources::snprintf(nullptr,0,"%s:%d","abc",123)==7);
    std::puts("Path XML, audio opcode builders, envelope BE bytes, enum errors and bounded formatting agree");
}
