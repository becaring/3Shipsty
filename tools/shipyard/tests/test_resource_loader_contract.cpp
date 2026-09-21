#include "ship/resource/ResourceLoader.h"
#include "ship/resource/factory/BlobFactory.h"
#include "ship/resource/type/Blob.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include "ship/utils/StringHelper.h"
#include "ship/utils/glob.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <iostream>
extern "C" unsigned char projected_glob_match(const char*,const char*);

class LoaderAccess : public Ship::ResourceLoader {
public:
    using Ship::ResourceLoader::GetFactory;
    using Ship::ResourceLoader::ReadResourceInitDataBinary;
};
static void put(std::vector<char>& bytes, size_t offset, uint64_t value, size_t size, bool big) {
    for(size_t i=0;i<size;++i) bytes[offset+i]=char(value>>((big ? size-1-i : i)*8));
}
int main() {
    spdlog::set_level(spdlog::level::off);
    for(int big=0;big<2;++big) {
        std::shared_ptr<std::vector<char>> bytes=std::make_shared<std::vector<char>>(64,0);
        (*bytes)[0]=char(big); (*bytes)[1]=1;
        put(*bytes,4,0x424c4f42,4,big!=0); put(*bytes,8,17,4,big!=0);
        put(*bytes,12,0x123456789abcdef0ULL,8,big!=0);
        std::shared_ptr<Ship::BinaryReader> reader=std::make_shared<Ship::BinaryReader>(
            std::make_shared<Ship::MemoryStream>(bytes));
        std::shared_ptr<Ship::ResourceInitData> init=LoaderAccess::ReadResourceInitDataBinary("object/test",reader);
        assert(init->Path=="object/test" && init->IsCustom);
        assert(init->Type==0x424c4f42 && init->ResourceVersion==17 && init->Id==0x123456789abcdef0ULL);
        assert(init->Format==RESOURCE_FORMAT_BINARY);
        assert(init->ByteOrder==(big ? Ship::Endianness::Big : Ship::Endianness::Little));
        assert(reader->ReadUByte()==big); // Modern reader rewinds the header.
    }
    std::shared_ptr<Ship::ResourceInitData> fallback=LoaderAccess::ReadResourceInitDataBinary(
        "missing",std::shared_ptr<Ship::BinaryReader>());
    assert(fallback->Path=="missing" && fallback->Id==0xDEADBEEFDEADBEEFULL);
    assert(fallback->ResourceVersion==uint32_t(-1) && !fallback->IsCustom);
    LoaderAccess loader;
    assert(loader.GetFactory(RESOURCE_FORMAT_BINARY,"Json",0));
    assert(loader.GetFactory(RESOURCE_FORMAT_BINARY,"Shader",0));
    assert(!loader.GetFactory(RESOURCE_FORMAT_BINARY,"unknown",0));
    std::shared_ptr<Ship::ResourceFactory> blob=std::make_shared<Ship::ResourceFactoryBinaryBlobV0>();
    assert(loader.RegisterResourceFactory(blob,RESOURCE_FORMAT_BINARY,"ContractBlob",0x424c4f42,0));
    assert(loader.GetFactory(RESOURCE_FORMAT_BINARY,"ContractBlob",0)==blob);
    assert(!loader.RegisterResourceFactory(blob,RESOURCE_FORMAT_BINARY,"ContractBlob",0x424c4f42,0));
    assert(!loader.RegisterResourceFactory(blob,RESOURCE_FORMAT_BINARY,"ContractBlob",0x424c4f43,1));
    assert(loader.RegisterResourceFactory(blob,RESOURCE_FORMAT_BINARY,"ContractBlob",0x424c4f42,1));
    assert(loader.GetResourceType("unknown")==0);
    const char text[]={'a','b',0,'c',':','d','e'};
    std::vector<nonstd::string_view> parts=StringHelper::Split(nonstd::string_view(text,sizeof(text)),":");
    assert(parts.size()==2 && parts[0].size()==4 && parts[1].size()==2);
    assert(parts[0].data()==text && parts[1].data()==text+5);
    assert(StringHelper::IEquals("Asset/TEST","asset/test"));
    assert(!StringHelper::IEquals("asset","assets") && !StringHelper::IEquals("assets","asset"));
    assert(StringHelper::IsValidHex(nonstd::string_view("0x7f")));
    assert(!StringHelper::IsValidHex(nonstd::string_view("0x7g")));
    assert(glob_match("objects/*.[ch]","objects/test.c"));
    assert(!glob_match("objects/*.[ch]","objects/test.o"));
    assert(glob_match("[!x]","b") && !glob_match("[!x]","x"));
    assert(glob_match("[abc","[abc") && glob_match("?", "x") && !glob_match("?", ""));
    const char* patterns[]={"*","?","objects/*.[ch]","[!x]","[abc","*x","a?"};
    // Padding keeps the inherited upstream negated-class/NUL behavior within
    // the allocation while comparing it; it is not advertised as POSIX glob.
    const char values[][32]={"","x","b","ab","ax","objects/test.c","[abc"};
    for(size_t p=0;p<sizeof(patterns)/sizeof(patterns[0]);++p)
        for(size_t v=0;v<sizeof(values)/sizeof(values[0]);++v)
            assert(glob_match(patterns[p],values[v])==projected_glob_match(patterns[p],values[v]));
    std::cout << "Current ResourceLoader: LE/BE headers, 64-bit IDs, rewind, null-header defaults, factory versions and conflict rejection pass\n";
    std::cout << "Current StringHelper and C glob: zero-copy bounded views, unequal lengths, hex and wildcard classes pass\n";
}
