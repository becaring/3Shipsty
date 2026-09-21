#include "ship/window/gui/resource/Font.h"
#include "ship/window/gui/resource/FontFactory.h"
#include "ship/window/gui/resource/GuiTexture.h"
#include "ship/window/gui/resource/GuiTextureFactory.h"
#include "fast/resource/type/Texture.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstring>
#include <fstream>
#include <iterator>
#include <cstdio>

static std::shared_ptr<Ship::File> fileOf(const std::vector<char>& bytes,Ship::Endianness endian) {
    std::shared_ptr<Ship::File> file=std::make_shared<Ship::File>();
    file->Buffer=std::make_shared<std::vector<char>>(bytes);
    std::shared_ptr<Ship::BinaryReader> reader=std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(file->Buffer));
    reader->SetEndianness(endian);file->Reader=reader;return file;
}

int main(int argc,char** argv) {
    assert(argc==2);spdlog::set_level(spdlog::level::off);
    std::ifstream input(argv[1],std::ios::binary);
    std::vector<char> png((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>());
    assert(!png.empty());
    const unsigned char rgba[]={255,0,0,255,0,255,0,128,0,0,255,0,1,2,3,4};
    std::shared_ptr<Ship::ResourceInitData> init=std::make_shared<Ship::ResourceInitData>();
    init->Format=RESOURCE_FORMAT_BINARY;init->Path="image/font contract";
    Ship::ResourceFactoryBinaryFontV0 fonts;
    Ship::ResourceFactoryBinaryGuiTextureV0 images;
    std::vector<char> fontBytes(513);
    for(size_t i=0;i<fontBytes.size();++i)fontBytes[i]=static_cast<char>((i*37)&255);
    for(int big=0;big<2;++big) {
        Ship::Endianness endian=big?Ship::Endianness::Big:Ship::Endianness::Little;
        std::shared_ptr<Ship::Font> font=std::dynamic_pointer_cast<Ship::Font>(fonts.ReadResource(fileOf(fontBytes,endian),init));
        assert(font && font->DataSize==fontBytes.size() && font->GetPointerSize()==fontBytes.size());
        assert(font->GetInitData()==init && std::memcmp(font->Data,&fontBytes[0],fontBytes.size())==0);
        std::shared_ptr<Ship::GuiTexture> image=std::dynamic_pointer_cast<Ship::GuiTexture>(images.ReadResource(fileOf(png,endian),init));
        assert(image && image->Metadata.Width==2 && image->Metadata.Height==2);
        assert(image->GetInitData()==init && std::memcmp(image->Data,rgba,sizeof(rgba))==0);
        // Current upstream reports encoded source size, not decoded byte size.
        assert(image->DataSize==png.size() && image->GetPointerSize()==png.size());
    }
    std::vector<char> invalid(16,'?');
    assert(!images.ReadResource(fileOf(invalid,Ship::Endianness::Little),init));
    init->Format=RESOURCE_FORMAT_XML;
    assert(!images.ReadResource(fileOf(png,Ship::Endianness::Little),init));
    assert(!fonts.ReadResource(fileOf(fontBytes,Ship::Endianness::Little),init));
    Fast::Texture texture(init);
    assert(texture.Flags==0 && texture.HByteScale==1 && texture.VPixelScale==1 && texture.ImageData==NULL);
    texture.ImageDataSize=7;texture.ImageData=new uint8_t[7];
    assert(texture.GetPointer()==texture.ImageData && texture.GetPointerSize()==7);
    std::puts("Current font bytes, PNG RGBA/alpha, format rejection and texture defaults agree for both reader endian modes");
}
