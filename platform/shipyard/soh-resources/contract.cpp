#include <fast/lus_gbi.h>
#include "soh/resource/type/Background.h"
#include "soh/resource/type/PlayerAnimation.h"
#include "soh/resource/type/Text.h"
#include "soh/resource/type/Array.h"
#include "soh/resource/type/Cutscene.h"
#include "soh/resource/importer/BackgroundFactory.h"
#include "soh/resource/importer/PlayerAnimationFactory.h"
#include "soh/resource/importer/TextFactory.h"
#include "soh/resource/importer/ArrayFactory.h"
#include "soh/resource/importer/CutsceneFactory.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <tinyxml2.h>
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstring>
#include <cstdio>

// Independent serialization oracle. Do not use the reader's paired BinaryWriter.
struct Bytes {
    bool big;
    std::vector<char> data;
    Bytes(bool b) : big(b) {}
    void byte(unsigned v) { data.push_back(static_cast<char>(v)); }
    void number(uint32_t v, int width) {
        for (int i=0;i<width;++i) byte(v >> (8*(big?width-1-i:i)));
    }
    void half(uint16_t v) { number(v,2); }
    void word(uint32_t v) { number(v,4); }
    void string(const std::string& s) { word(static_cast<uint32_t>(s.size())); data.insert(data.end(),s.begin(),s.end()); }
    std::shared_ptr<Ship::File> file() const {
        std::shared_ptr<Ship::File> f=std::make_shared<Ship::File>();
        f->Buffer=std::make_shared<std::vector<char>>(data);
        std::shared_ptr<Ship::BinaryReader> r=std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(f->Buffer));
        r->SetEndianness(big?Ship::Endianness::Big:Ship::Endianness::Little); f->Reader=r; return f;
    }
};

static uint16_t halfAt(uint32_t word, size_t offset) {
    uint16_t result; std::memcpy(&result,reinterpret_cast<const char*>(&word)+offset,2); return result;
}
static uint8_t byteAt(uint32_t word, size_t offset) {
    return reinterpret_cast<const uint8_t*>(&word)[offset];
}

template<class T,class Factory> static std::shared_ptr<T> read(Factory& factory, Bytes& bytes,
                                                             std::shared_ptr<Ship::ResourceInitData> init) {
    std::shared_ptr<T> result=std::dynamic_pointer_cast<T>(factory.ReadResource(bytes.file(),init));
    assert(result && result->GetInitData()==init); return result;
}

int main() {
    spdlog::set_level(spdlog::level::off);
    std::shared_ptr<Ship::ResourceInitData> init=std::make_shared<Ship::ResourceInitData>();
    init->Format=RESOURCE_FORMAT_BINARY; init->Path="SoH leaf contract";
    SOH::ResourceFactoryBinaryBackgroundV0 backgrounds;
    SOH::ResourceFactoryBinaryPlayerAnimationV0 animations;
    SOH::ResourceFactoryBinaryTextV0 texts;
    SOH::ResourceFactoryXMLTextV0 xmltexts;
    SOH::ResourceFactoryBinaryArrayV0 arrays;
    SOH::ResourceFactoryBinaryCutsceneV0 cutscenes;
    for (int big=0;big<2;++big) {
        Bytes b(big!=0); b.word(4); b.byte(0); b.byte(0x12); b.byte(0x80); b.byte(0xff);
        std::shared_ptr<SOH::Background> bg=read<SOH::Background>(backgrounds,b,init);
        assert(bg->GetPointerSize()==4 && bg->GetPointer()[2]==0x80 && bg->GetPointer()[3]==0xff);
        Bytes p(big!=0); p.word(4); p.half(0x8000); p.half(0xffff); p.half(0x1234); p.half(0x7fff);
        std::shared_ptr<SOH::PlayerAnimation> pa=read<SOH::PlayerAnimation>(animations,p,init);
        assert(pa->GetPointerSize()==8 && pa->GetPointer()[0]==-32768 && pa->GetPointer()[1]==-1);
        assert(pa->GetPointer()[2]==0x1234 && pa->GetPointer()[3]==32767);
        Bytes t(big!=0); t.word(2); t.half(0xabcd); t.byte(3); t.byte(2); t.string(std::string("a\0\x80\x02",4));
        t.half(0x1234); t.byte(1); t.byte(0); t.string("");
        std::shared_ptr<SOH::Text> txt=read<SOH::Text>(texts,t,init);
        assert(txt->GetPointerSize()==2*sizeof(SOH::MessageEntry) && txt->messages[0].id==0xabcd);
        assert(txt->messages[0].textboxType==3 && txt->messages[0].textboxYPos==2);
        assert(txt->messages[0].msg==std::string("a\0\x80\x02",4) && txt->messages[1].msg.empty());

        Bytes a(big!=0); a.word(16); a.word(2); a.word(4); a.half(0x8123); a.word(4); a.half(0x4567);
        std::shared_ptr<SOH::Array> scalar=read<SOH::Array>(arrays,a,init);
        assert(scalar->Scalars.size()==2 && scalar->Scalars[0].s16==-32477 && scalar->Scalars[1].s16==0x4567);
        assert(scalar->GetPointerSize()==4 && scalar->GetPointer()==scalar->Scalars.data());
        // ArrayCount describes outer records; the modern factory reads a type for each outer record.
        Bytes v(big!=0); v.word(24); v.word(1); v.word(5); v.word(3); v.half(0xfedc); v.half(0x0123); v.half(0x8000);
        std::shared_ptr<SOH::Array> vector=read<SOH::Array>(arrays,v,init);
        assert(vector->Scalars.size()==3 && vector->Scalars[0].u16==0xfedc && vector->Scalars[2].u16==0x8000);
        assert(vector->GetPointerSize()==2); // Preserve current ArrayCount-based size behavior.
        Bytes vertex(big!=0); vertex.word(25); vertex.word(1);
        vertex.half(0xffff); vertex.half(0x1234); vertex.half(0x8000); vertex.half(0xabcd);
        vertex.half(0x4567); vertex.half(0xfffe); vertex.byte(1); vertex.byte(0x80); vertex.byte(0xfe); vertex.byte(0xff);
        std::shared_ptr<SOH::Array> verts=read<SOH::Array>(arrays,vertex,init);
        assert(verts->GetPointerSize()==sizeof(Fast::F3DVtx));
        const Fast::F3DVtx& vx=verts->Vertices[0];
        assert(vx.v.ob[0]==-1 && vx.v.ob[1]==0x1234 && vx.v.ob[2]==-32768 && vx.v.flag==0xabcd);
        assert(vx.v.tc[0]==0x4567 && vx.v.tc[1]==-2 && vx.v.cn[1]==0x80 && vx.v.cn[3]==0xff);

        // Cmd09 hits all three active mixed-width helpers; camera tests byte sentinel termination.
        Bytes c(big!=0); c.word(32); c.word(2); c.word(0x12345678);
        c.word(9); c.word(1); c.half(0x1234); c.half(0xabcd);
        c.half(0x5678); c.byte(0x9a); c.byte(0xbc); c.byte(0xde); c.byte(0xf0); c.half(0x1357);
        c.word(1); c.half(0x0123); c.half(0x4567); c.half(0x89ab); c.half(0xcdef);
        c.byte(0xff); c.byte(0x88); c.half(0x2468); c.word(0x3fc00000);
        c.half(0xfffe); c.half(0x1234); c.half(0xabcd); c.half(0x5678);
        c.word(0xffffffff); c.word(0x10203040);
        std::shared_ptr<SOH::Cutscene> cs=read<SOH::Cutscene>(cutscenes,c,init);
        assert(cs->numCommands==2 && cs->endFrame==0x12345678 && cs->commands.size()==16);
        assert(cs->GetPointerSize()==16*sizeof(uint32_t));
        assert(halfAt(cs->commands[4],0)==0x1234 && halfAt(cs->commands[4],2)==0xabcd);
        assert(halfAt(cs->commands[5],0)==0x5678 && byteAt(cs->commands[5],2)==0x9a && byteAt(cs->commands[5],3)==0xbc);
        assert(byteAt(cs->commands[6],0)==0xde && byteAt(cs->commands[6],1)==0xf0 && halfAt(cs->commands[6],2)==0x1357);
        assert(byteAt(cs->commands[10],0)==0xff && byteAt(cs->commands[10],1)==0x88 && halfAt(cs->commands[10],2)==0x2468);
        assert(cs->commands[11]==0x3fc00000 && cs->commands[14]==0xffffffff && cs->commands[15]==0x10203040);

        Bytes empty(big!=0); empty.word(0);
        assert(read<SOH::Background>(backgrounds,empty,init)->GetPointerSize()==0);
        assert(read<SOH::PlayerAnimation>(animations,empty,init)->GetPointerSize()==0);
        assert(read<SOH::Text>(texts,empty,init)->GetPointerSize()==0);
        Bytes shortData(big!=0); shortData.word(1);
        bool threw=false; try { animations.ReadResource(shortData.file(),init); } catch (...) { threw=true; }
        assert(threw);
    }
    std::shared_ptr<Ship::File> xml=std::make_shared<Ship::File>();
    std::shared_ptr<tinyxml2::XMLDocument> doc=std::make_shared<tinyxml2::XMLDocument>();
    assert(doc->Parse("<Text><TextEntry ID='4660' TextboxType='2' TextboxYPos='3' Message='a &amp; b'/><Ignored/><TextEntry ID='9' Message='' /></Text>")==tinyxml2::XML_SUCCESS);
    xml->Reader=doc;
    assert(!backgrounds.ReadResource(xml,init)); assert(!animations.ReadResource(xml,init));
    assert(!texts.ReadResource(xml,init)); assert(!arrays.ReadResource(xml,init)); assert(!cutscenes.ReadResource(xml,init));
    assert(!xmltexts.ReadResource(xml,init));
    init->Format=RESOURCE_FORMAT_XML;
    std::shared_ptr<SOH::Text> text=std::dynamic_pointer_cast<SOH::Text>(xmltexts.ReadResource(xml,init));
    assert(text && text->messages.size()==2 && text->messages[0].id==4660);
    assert(text->messages[0].textboxType==2 && text->messages[0].textboxYPos==3);
    assert(text->messages[0].msg=="a & b\x02" && text->messages[1].msg=="\x02");
    Bytes empty(false); empty.word(0);
    assert(!xmltexts.ReadResource(empty.file(),init));
    assert(!backgrounds.ReadResource(empty.file(),init)); assert(!animations.ReadResource(empty.file(),init));
    assert(!texts.ReadResource(empty.file(),init)); assert(!arrays.ReadResource(empty.file(),init)); assert(!cutscenes.ReadResource(empty.file(),init));
    std::puts("Five current SoH resources: binary LE/BE, XML text, scalar/vector/vertex arrays, mixed-width cutscene layout, empty/truncated/invalid inputs agree");
}
