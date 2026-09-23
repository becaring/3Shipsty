#include "ship/resource/factory/BlobFactory.h"
#include "ship/resource/factory/JsonFactory.h"
#include "ship/resource/factory/ShaderFactory.h"
#include "ship/resource/ResourceFactoryXML.h"
#include "ship/resource/type/Blob.h"
#include "ship/resource/type/Json.h"
#include "ship/resource/type/Shader.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <iostream>
#include <stdexcept>

class XmlProbe : public Ship::ResourceFactoryXML {
public:
    bool valid(std::shared_ptr<Ship::File> file, std::shared_ptr<Ship::ResourceInitData> init) {
        return FileHasValidFormatAndReader(file, init);
    }
    std::shared_ptr<Ship::IResource> ReadResource(std::shared_ptr<Ship::File>, std::shared_ptr<Ship::ResourceInitData>) {
        return std::shared_ptr<Ship::IResource>();
    }
};

static std::shared_ptr<Ship::File> fileOf(const char* bytes, size_t size, Ship::Endianness endian) {
    std::shared_ptr<Ship::File> file = std::make_shared<Ship::File>();
    assert(!file->IsLoaded);
    file->Buffer = std::make_shared<std::vector<char>>(bytes, bytes + size);
    std::shared_ptr<Ship::BinaryReader> reader = std::make_shared<Ship::BinaryReader>(
        std::make_shared<Ship::MemoryStream>(file->Buffer));
    reader->SetEndianness(endian);
    file->Reader = reader;
    return file;
}

int main() {
    spdlog::set_level(spdlog::level::off);
    std::shared_ptr<Ship::ResourceInitData> init = std::make_shared<Ship::ResourceInitData>();
    assert(init->Parent == nullptr && init->Path.empty());
    assert(init->ByteOrder == Ship::Endianness::Native && init->Type == 0);
    assert(init->ResourceVersion == 0 && init->Id == 0 && !init->IsCustom);
    assert(init->Format == RESOURCE_FORMAT_BINARY);
    init->Path = "contract";
    init->Format = RESOURCE_FORMAT_BINARY;
    Ship::ResourceFactoryBinaryBlobV0 blobs;
    const char little[] = {3, 0, 0, 0, 1, 2, char(255)};
    const char big[] = {0, 0, 0, 3, 1, 2, char(255)};
    for (int i=0; i<2; ++i) {
        std::shared_ptr<Ship::File> file = fileOf(i ? big : little, sizeof(big),
            i ? Ship::Endianness::Big : Ship::Endianness::Little);
        std::shared_ptr<Ship::Blob> blob = std::dynamic_pointer_cast<Ship::Blob>(blobs.ReadResource(file,init));
        assert(blob && blob->Data.size()==3 && blob->Data[0]==1 && blob->Data[2]==255);
        assert(blob->GetPointerSize()==3 && blob->GetRawPointer()==blob->Data.data());
        assert(blob->GetInitData()==init && !blob->IsDirty());
        blob->Dirty(); assert(blob->IsDirty());
    }
    const char shaderBytes[] = "void main(){}";
    Ship::ResourceFactoryBinaryShaderV0 shaders;
    std::shared_ptr<Ship::Shader> shader = std::dynamic_pointer_cast<Ship::Shader>(
        shaders.ReadResource(fileOf(shaderBytes,sizeof(shaderBytes),Ship::Endianness::Little),init));
    assert(shader->Data==std::string(shaderBytes,sizeof(shaderBytes)) &&
           shader->GetPointerSize()==sizeof(shaderBytes) && shader->GetPointer()==&shader->Data);
    const char jsonBytes[] = "{/* comment */\"n\":7,\"v\":[true,\"text\"]}";
    Ship::ResourceFactoryBinaryJsonV0 jsons;
    std::shared_ptr<Ship::Json> json = std::dynamic_pointer_cast<Ship::Json>(
        jsons.ReadResource(fileOf(jsonBytes,sizeof(jsonBytes),Ship::Endianness::Little),init));
    assert(json->Data["n"].get<int>()==7 && json->Data["v"][1].get<std::string>()=="text");
    assert(json->GetPointer()==&json->Data && json->GetPointerSize()==sizeof(jsonBytes));
    std::shared_ptr<Ship::File> empty = std::make_shared<Ship::File>();
    assert(!blobs.ReadResource(empty,init));
    XmlProbe xml;
    assert(!xml.valid(empty,init));
    init->Format=RESOURCE_FORMAT_XML;
    assert(xml.valid(empty,init)); // The modern validator tests alternative type, not pointer non-nullness.
    assert(!blobs.ReadResource(empty,init));
    init->Format=RESOURCE_FORMAT_BINARY;
    const char invalid[]="{";
    bool threw=false;
    try { jsons.ReadResource(fileOf(invalid,sizeof(invalid),Ship::Endianness::Little),init); }
    catch (const std::exception&) { threw=true; }
    assert(threw);
    const char shortBlob[] = {3,0,0,0,1};
    threw=false;
    try { blobs.ReadResource(fileOf(shortBlob,sizeof(shortBlob),Ship::Endianness::Little),init); }
    catch (const std::exception&) { threw=true; }
    assert(threw);
    assert(Ship::IResource::gAltAssetPrefix=="alt/");
    std::cout << "resource factories: endian payload, exact sizes, dirty state, format/type rejection, JSON comments and exceptions agree\n";
}
