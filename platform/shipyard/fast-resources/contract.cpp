#include "fast/lus_gbi.h"
#include "fast/resource/type/DisplayList.h"
#include "fast/resource/type/Matrix.h"
#include "fast/resource/type/Vertex.h"
#include "fast/resource/type/Light.h"
#include "fast/resource/type/Texture.h"
#include "fast/resource/factory/DisplayListFactory.h"
#include "fast/resource/factory/MatrixFactory.h"
#include "fast/resource/factory/VertexFactory.h"
#include "fast/resource/factory/LightFactory.h"
#include "fast/resource/factory/TextureFactory.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <tinyxml2.h>
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>

// Test serialization is independent of the production BinaryWriter.
struct Bytes {
    bool big; std::vector<char> data;
    Bytes(bool b):big(b){}
    void byte(unsigned v){data.push_back(static_cast<char>(v));}
    void number(uint32_t v,int width){for(int i=0;i<width;++i)byte(v>>(8*(big?width-1-i:i)));}
    void half(uint16_t v){number(v,2);} void word(uint32_t v){number(v,4);}
    std::shared_ptr<Ship::File> file() const {
        auto f=std::make_shared<Ship::File>();f->Buffer=std::make_shared<std::vector<char>>(data);
        auto r=std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(f->Buffer));
        r->SetEndianness(big?Ship::Endianness::Big:Ship::Endianness::Little);f->Reader=r;return f;
    }
};
template<class T,class Factory> static std::shared_ptr<T> read(Factory& f,Bytes& b,std::shared_ptr<Ship::ResourceInitData> init){
    auto r=std::dynamic_pointer_cast<T>(f.ReadResource(b.file(),init));assert(r&&r->GetInitData()==init);return r;
}
static uint64_t hash=1469598103934665603ULL;
static void digest(const void* data,size_t n){auto p=static_cast<const unsigned char*>(data);while(n--){hash^=*p++;hash*=1099511628211ULL;}}
static void word(uint64_t v){digest(&v,sizeof(v));}
static int textureType(Fast::TextureType type){
#ifdef SHIPYARD_PROJECTION
    return type.GetValue();
#else
    return static_cast<int>(type);
#endif
}
static void display(const Fast::DisplayList& dl){
    word(dl.UCode);word(dl.Instructions.size());
    for(size_t i=0;i<dl.Instructions.size();++i){
        auto g=dl.Instructions[i];word(g.words.w0);
        bool pointer=false;
        for(size_t j=0;j<dl.Strings.size();++j)if(g.words.w1==reinterpret_cast<uintptr_t>(dl.Strings[j])){
            digest(dl.Strings[j],strlen(dl.Strings[j])+1);pointer=true;break;
        }
        if(!pointer)word(g.words.w1);
    }
}
static std::shared_ptr<Ship::File> xml(const char* text){
    auto f=std::make_shared<Ship::File>();auto doc=std::make_shared<tinyxml2::XMLDocument>();
    assert(doc->Parse(text)==tinyxml2::XML_SUCCESS);f->Reader=doc;return f;
}
int main(int argc,char** argv){
    spdlog::set_level(spdlog::level::off);
    auto init=std::make_shared<Ship::ResourceInitData>();init->Format=RESOURCE_FORMAT_BINARY;init->Path="Fast resource contract";
    Fast::ResourceFactoryBinaryDisplayListV0 dlFactory;Fast::ResourceFactoryBinaryMatrixV0 matrixFactory;
    Fast::ResourceFactoryBinaryVertexV0 vertexFactory;Fast::ResourceFactoryBinaryLightV0 lightFactory;
    Fast::ResourceFactoryBinaryTextureV0 texture0;Fast::ResourceFactoryBinaryTextureV1 texture1;
    for(int big=0;big<2;++big){
        Bytes m(big!=0);for(unsigned j=0;j<16;++j)m.word(0x80000000U+j*0x01234567U);
        auto matrix=read<Fast::Matrix>(matrixFactory,m,init);
        for(unsigned j=0;j<16;++j)assert(static_cast<uint32_t>(matrix->GetPointer()->m[j/4][j%4])==0x80000000U+j*0x01234567U);
        Bytes v(big!=0);v.word(1);v.half(0x8000);v.half(0xffff);v.half(0x7fff);v.half(0xa5a5);v.half(0xf123);v.half(0x4321);
        for(int j=0;j<4;++j)v.byte(0x80+j);
        auto vertex=read<Fast::Vertex>(vertexFactory,v,init);auto& vv=vertex->GetPointer()->v;
        assert(vv.ob[0]==-32768&&vv.ob[1]==-1&&vv.ob[2]==32767&&vv.flag==0xa5a5&&vv.tc[0]==static_cast<int16_t>(0xf123)&&vv.cn[3]==0x83);
        Bytes light(big!=0);for(size_t j=0;j<sizeof(Fast::LightEntry);++j)light.byte(j*17+3);
        auto l=read<Fast::Light>(lightFactory,light,init);assert(l->GetPointerSize()==light.data.size());
        assert(memcmp(l->GetPointer(),light.data.data(),light.data.size())==0); // Raw union contract, not a point-light endian claim.
        for(int version=0;version<2;++version){
            Bytes t(big!=0);t.word(2);t.word(2);t.word(1);
            if(version){t.word(1);t.word(0x3fc00000);t.word(0x40000000);}
            t.word(4);t.byte(0x12);t.byte(0x34);t.byte(0xab);t.byte(0xcd);
            auto texture=version?read<Fast::Texture>(texture1,t,init):read<Fast::Texture>(texture0,t,init);
            assert(texture->Type==Fast::TextureType::RGBA16bpp&&texture->Width==2&&texture->Height==1&&texture->GetPointerSize()==4);
            assert(texture->Flags==(version?1:0)&&texture->HByteScale==(version?1.5f:1.0f)&&texture->VPixelScale==(version?2.f:1.f));
            assert(memcmp(texture->GetPointer(),"\x12\x34\xab\xcd",4)==0);
        }
        const unsigned expanded[]={G_SETTIMG_OTR_HASH,G_DL_OTR_HASH,G_VTX_OTR_HASH,G_BRANCH_Z_OTR,G_MARKER,G_MTX_OTR,G_MOVEMEM_OTR};
        for(int u=0;u<ucode_max;++u){
            Bytes d(big!=0);d.byte(u);for(int j=0;j<7;++j)d.byte(0xcc);
            for(size_t j=0;j<7;++j){d.word((expanded[j]<<24)|0x1234);d.word(0x89abcdef);d.word(0xfedcba98);d.word(0x76543210);}
            unsigned end=(u==ucode_f3dex2||u==ucode_s2dex)?0xdf:0xb8;d.word(end<<24);d.word(0);
            auto dl=read<Fast::DisplayList>(dlFactory,d,init);assert(dl->UCode==u&&dl->Instructions.size()==15);
            for(size_t j=0;j<7;++j){assert(dl->Instructions[2*j].words.w0==((expanded[j]<<24)|0x1234));assert(dl->Instructions[2*j+1].words.w0==0xfedcba98);}
            display(*dl);
        }
    }
    init->Format=RESOURCE_FORMAT_XML;
    Fast::ResourceFactoryXMLVertexV0 xmlVertex;Fast::ResourceFactoryXMLDisplayListV0 xmlDL;
    auto vertex=std::dynamic_pointer_cast<Fast::Vertex>(xmlVertex.ReadResource(xml("<Vertex><Ignored/><Vtx X='-32768' Y='-1' Z='32767' S='-123' T='456' R='255' G='128' B='3' A='4'/></Vertex>"),init));
    assert(vertex&&vertex->VertexList.size()==1&&vertex->GetPointer()->v.flag==0&&vertex->GetPointer()->v.ob[0]==-32768&&vertex->GetPointer()->v.cn[0]==255);
    auto dl=std::dynamic_pointer_cast<Fast::DisplayList>(xmlDL.ReadResource(xml("<DisplayList><PipeSync/><SetPrimColor M='2' L='3' R='17' G='34' B='51' A='68'/><Texture S='100' T='200' Level='2' Tile='1' On='1'/><FogPosition Min='10' Max='100'/><SetRenderMode Mode1='G_RM_AA_ZB_OPA_SURF' Mode2='G_RM_AA_ZB_OPA_SURF2'/><CallDisplayList Path='test/path'/><CallDisplayList Path='&gt;0x06001234'/><EndDisplayList/></DisplayList>"),init));
    assert(dl&&dl->Instructions.size()==8&&dl->Strings.size()==1);display(*dl);
    init->Format=RESOURCE_FORMAT_BINARY;
    assert(!xmlDL.ReadResource(xml("<DisplayList/>"),init));
    assert(!dlFactory.ReadResource(xml("<DisplayList/>"),init));
    Bytes truncated(false);truncated.word(1);bool caught=false;
    try{matrixFactory.ReadResource(truncated.file(),init);}catch(const std::exception&){caught=true;}assert(caught);
    // Archive fixture framing is test-only; the runtime continues to use real O2R.
    unsigned records=0;
    if(argc==2){
        std::ifstream file(argv[1],std::ios::binary);assert(file.good());uint32_t header[4];
        while(file.read(reinterpret_cast<char*>(header),sizeof(header))){
            Bytes b(header[2]!=0);b.data.resize(header[3]);file.read(b.data.data(),header[3]);assert(file.good());
            if(header[0]==0x4f444c54){auto r=read<Fast::DisplayList>(dlFactory,b,init);display(*r);}
            else if(header[0]==0x4f544558){auto r=header[1]?read<Fast::Texture>(texture1,b,init):read<Fast::Texture>(texture0,b,init);word(textureType(r->Type));word(r->Width);word(r->Height);word(r->Flags);digest(&r->HByteScale,4);digest(&r->VPixelScale,4);digest(r->GetPointer(),r->GetPointerSize());}
            else if(header[0]==0x4f565458){auto r=read<Fast::Vertex>(vertexFactory,b,init);digest(r->GetPointer(),r->GetPointerSize());}
            else if(header[0]==0x4f4d5458){auto r=read<Fast::Matrix>(matrixFactory,b,init);digest(r->GetPointer(),r->GetPointerSize());}
            else assert(false);
            ++records;
        }
    }
    printf("LE/BE typed scalars, raw bytes, six ucodes, expanded commands, XML paths/modes, rejection, %u archive records; hash %llu\n",records,hash);
}
