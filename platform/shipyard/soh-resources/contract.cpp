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
#include "soh/resource/type/CollisionHeader.h"
#include "soh/resource/type/SkeletonLimb.h"
#include "soh/resource/importer/CollisionHeaderFactory.h"
#include "soh/resource/importer/SkeletonLimbFactory.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <tinyxml2.h>
#include <spdlog/spdlog.h>
#include <cassert>
#include <cstring>
#include <cstdio>

// The original libultra umbrella exposes scalar shorthand macros after Array's
// definition; the serialization assertions address the actual union members.
#undef s16
#undef u16

// Independent serialization oracle. Do not use the reader's paired BinaryWriter.
struct Bytes {
    bool big;
    std::vector<char> data;
    Bytes(bool b) : big(b) {}
    void byte(unsigned v) { data.push_back(static_cast<char>(v)); }
    void number(uint32_t v, int width) {
        for (int i = 0; i < width; ++i)
            byte(v >> (8 * (big ? width - 1 - i : i)));
    }
    void half(uint16_t v) { number(v, 2); }
    void word(uint32_t v) { number(v, 4); }
    void string(const std::string &s) {
        word(static_cast<uint32_t>(s.size()));
        data.insert(data.end(), s.begin(), s.end());
    }
    std::shared_ptr<Ship::File> file() const {
        std::shared_ptr<Ship::File> f = std::make_shared<Ship::File>();
        f->Buffer = std::make_shared<std::vector<char>>(data);
        std::shared_ptr<Ship::BinaryReader> r =
            std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(f->Buffer));
        r->SetEndianness(big ? Ship::Endianness::Big : Ship::Endianness::Little);
        f->Reader = r;
        return f;
    }
};

static uint16_t halfAt(uint32_t word, size_t offset) {
    uint16_t result;
    std::memcpy(&result, reinterpret_cast<const char *>(&word) + offset, 2);
    return result;
}
static uint8_t byteAt(uint32_t word, size_t offset) { return reinterpret_cast<const uint8_t *>(&word)[offset]; }

template <class T, class Factory>
static std::shared_ptr<T> read(Factory &factory, Bytes &bytes, std::shared_ptr<Ship::ResourceInitData> init) {
    std::shared_ptr<T> result = std::dynamic_pointer_cast<T>(factory.ReadResource(bytes.file(), init));
    assert(result && result->GetInitData() == init);
    return result;
}

int main() {
    spdlog::set_level(spdlog::level::off);
    std::shared_ptr<Ship::ResourceInitData> init = std::make_shared<Ship::ResourceInitData>();
    init->Format = RESOURCE_FORMAT_BINARY;
    init->Path = "SoH leaf contract";
    SOH::ResourceFactoryBinaryBackgroundV0 backgrounds;
    SOH::ResourceFactoryBinaryPlayerAnimationV0 animations;
    SOH::ResourceFactoryBinaryTextV0 texts;
    SOH::ResourceFactoryXMLTextV0 xmltexts;
    SOH::ResourceFactoryBinaryArrayV0 arrays;
    SOH::ResourceFactoryBinaryCutsceneV0 cutscenes;
    SOH::ResourceFactoryBinaryCollisionHeaderV0 collisions;
    SOH::ResourceFactoryXMLCollisionHeaderV0 xmlcollisions;
    SOH::ResourceFactoryBinarySkeletonLimbV0 limbs;
    SOH::ResourceFactoryXMLSkeletonLimbV0 xmllimbs;
    for (int big = 0; big < 2; ++big) {
        Bytes co(big != 0);
        for (int j = 0; j < 6; ++j)
            co.half(0xff00 + j);
        co.word(1);
        co.half(0xffff);
        co.half(0x1234);
        co.half(0x8000);
        co.word(1);
        for (int j = 0; j < 8; ++j)
            co.half(0x8000 + j);
        co.word(1);
        co.word(0x12345678);
        co.word(0x90abcdef);
        co.word(1);
        co.half(0x8123);
        co.half(1);
        co.word(0);
        co.word(1);
        co.half(0xfffe);
        co.half(0x3456);
        co.half(0x8001);
        co.word(1);
        for (int j = 0; j < 5; ++j)
            co.half(0xffff - j);
        co.word(0x12345678);
        std::shared_ptr<SOH::CollisionHeader> collision = read<SOH::CollisionHeader>(collisions, co, init);
        const SOH::CollisionHeaderData &cd = *collision->GetPointer();
        assert(cd.minBounds.x == -256 && cd.maxBounds.z == -251 && cd.vtxList == collision->vertices.data());
        assert(cd.vtxList[0].x == -1 && cd.vtxList[0].y == 0x1234 && cd.vtxList[0].z == -32768);
        assert(cd.polyList[0].vtxData[1] == 0x8002 && cd.polyList[0].normal.x == -32764 &&
               cd.polyList[0].dist == -32761);
        assert(cd.surfaceTypeList[0].data[0] == 0x90abcdef && cd.surfaceTypeList[0].data[1] == 0x12345678);
        assert(cd.cameraDataListLen == 1 && cd.cameraDataList[0].cameraSType == 0x8123);
        assert(cd.cameraDataList[0].camPosData == collision->camPosData.data() &&
               cd.cameraDataList[0].camPosData[0].x == -2);
        assert(cd.waterBoxes[0].zLength == -5 && cd.waterBoxes[0].properties == 0x12345678);
        assert(collision->GetPointerSize() == sizeof(SOH::CollisionHeaderData));
        Bytes cz(big != 0);
        for (int j = 0; j < 6; ++j)
            cz.half(0);
        cz.word(0);
        cz.word(0);
        cz.word(0);
        cz.word(1);
        cz.half(0);
        cz.half(0);
        cz.word(0);
        cz.word(0);
        cz.word(0);
        std::shared_ptr<SOH::CollisionHeader> zeroCam = read<SOH::CollisionHeader>(collisions, cz, init);
        assert(zeroCam->camData[0].camPosData == &zeroCam->camPosDataZero && zeroCam->camData[0].camPosData->z == 0);
        for (int kind = 1; kind <= 4; ++kind) {
            Bytes li(big != 0);
            li.byte(kind);
            li.byte(4);
            li.string("skin");
            li.half(1);
            li.word(1);
            li.half(0x4321);
            li.word(1);
            li.half(0x1234);
            li.half(0xffff);
            li.half(0x8000);
            li.byte(0x80);
            li.byte(0xff);
            li.byte(0x7f);
            li.byte(0xef);
            li.word(1);
            li.byte(3);
            li.half(0xffff);
            li.half(0x1234);
            li.half(0x8000);
            li.byte(0xfe);
            li.string("skin2");
            li.word(0x3fc00000);
            li.word(0xc0000000);
            li.word(0);
            li.half(0xffff);
            li.half(0x1234);
            li.half(0x8000);
            li.string("");
            li.string("");
            li.string("near");
            li.string("far");
            li.half(0xffff);
            li.half(0x1234);
            li.half(0x8000);
            li.byte(0x81);
            li.byte(0xfe);
            std::shared_ptr<SOH::SkeletonLimb> limb = read<SOH::SkeletonLimb>(limbs, li, init);
            assert(limb->legTransX == 1.5f && limb->legTransY == -2 && limb->rotX == 0xffff);
            assert(limb->transX == -1 && limb->transZ == -32768 && limb->childIndex == 0x81);
            if (kind == 1)
                assert(std::string((char *)limb->limbData.standardLimb.dList) == "__OTR__near");
            if (kind == 2)
                assert(std::string((char *)limb->limbData.lodLimb.dLists[1]) == "__OTR__far");
            if (kind == 4)
                assert(std::string((char *)limb->limbData.skelCurveLimb.dList[0]) == "__OTR__near");
            if (kind == 3) {
                assert(limb->limbData.skinLimb.segment == &limb->skinAnimLimbData);
                const SOH::SkinLimbModif &sm = limb->skinAnimLimbData.limbModifications[0];
                assert(sm.unk_4 == 0x4321 && sm.vtxCount == 1 && sm.transformCount == 1);
                assert(sm.skinVertices[0].s == -1 && sm.skinVertices[0].normX == -128 &&
                       sm.skinVertices[0].alpha == 0xef);
                assert(sm.limbTransformations[0].scale == 0xfe && sm.limbTransformations[0].z == -32768);
            }
        }
        Bytes b(big != 0);
        b.word(4);
        b.byte(0);
        b.byte(0x12);
        b.byte(0x80);
        b.byte(0xff);
        std::shared_ptr<SOH::Background> bg = read<SOH::Background>(backgrounds, b, init);
        assert(bg->GetPointerSize() == 4 && bg->GetPointer()[2] == 0x80 && bg->GetPointer()[3] == 0xff);
        Bytes p(big != 0);
        p.word(4);
        p.half(0x8000);
        p.half(0xffff);
        p.half(0x1234);
        p.half(0x7fff);
        std::shared_ptr<SOH::PlayerAnimation> pa = read<SOH::PlayerAnimation>(animations, p, init);
        assert(pa->GetPointerSize() == 8 && pa->GetPointer()[0] == -32768 && pa->GetPointer()[1] == -1);
        assert(pa->GetPointer()[2] == 0x1234 && pa->GetPointer()[3] == 32767);
        Bytes t(big != 0);
        t.word(2);
        t.half(0xabcd);
        t.byte(3);
        t.byte(2);
        t.string(std::string("a\0\x80\x02", 4));
        t.half(0x1234);
        t.byte(1);
        t.byte(0);
        t.string("");
        std::shared_ptr<SOH::Text> txt = read<SOH::Text>(texts, t, init);
        assert(txt->GetPointerSize() == 2 * sizeof(SOH::MessageEntry) && txt->messages[0].id == 0xabcd);
        assert(txt->messages[0].textboxType == 3 && txt->messages[0].textboxYPos == 2);
        assert(txt->messages[0].msg == std::string("a\0\x80\x02", 4) && txt->messages[1].msg.empty());

        Bytes a(big != 0);
        a.word(16);
        a.word(2);
        a.word(4);
        a.half(0x8123);
        a.word(4);
        a.half(0x4567);
        std::shared_ptr<SOH::Array> scalar = read<SOH::Array>(arrays, a, init);
        assert(scalar->Scalars.size() == 2 && scalar->Scalars[0].s16 == -32477 && scalar->Scalars[1].s16 == 0x4567);
        assert(scalar->GetPointerSize() == 4 && scalar->GetPointer() == scalar->Scalars.data());
        // ArrayCount describes outer records; the modern factory reads a type for each outer record.
        Bytes v(big != 0);
        v.word(24);
        v.word(1);
        v.word(5);
        v.word(3);
        v.half(0xfedc);
        v.half(0x0123);
        v.half(0x8000);
        std::shared_ptr<SOH::Array> vector = read<SOH::Array>(arrays, v, init);
        assert(vector->Scalars.size() == 3 && vector->Scalars[0].u16 == 0xfedc && vector->Scalars[2].u16 == 0x8000);
        assert(vector->GetPointerSize() == 2); // Preserve current ArrayCount-based size behavior.
        Bytes vertex(big != 0);
        vertex.word(25);
        vertex.word(1);
        vertex.half(0xffff);
        vertex.half(0x1234);
        vertex.half(0x8000);
        vertex.half(0xabcd);
        vertex.half(0x4567);
        vertex.half(0xfffe);
        vertex.byte(1);
        vertex.byte(0x80);
        vertex.byte(0xfe);
        vertex.byte(0xff);
        std::shared_ptr<SOH::Array> verts = read<SOH::Array>(arrays, vertex, init);
        assert(verts->GetPointerSize() == sizeof(Fast::F3DVtx));
        const Fast::F3DVtx &vx = verts->Vertices[0];
        assert(vx.v.ob[0] == -1 && vx.v.ob[1] == 0x1234 && vx.v.ob[2] == -32768 && vx.v.flag == 0xabcd);
        assert(vx.v.tc[0] == 0x4567 && vx.v.tc[1] == -2 && vx.v.cn[1] == 0x80 && vx.v.cn[3] == 0xff);

        // Cmd09 hits all three active mixed-width helpers; camera tests byte sentinel termination.
        Bytes c(big != 0);
        c.word(32);
        c.word(2);
        c.word(0x12345678);
        c.word(9);
        c.word(1);
        c.half(0x1234);
        c.half(0xabcd);
        c.half(0x5678);
        c.byte(0x9a);
        c.byte(0xbc);
        c.byte(0xde);
        c.byte(0xf0);
        c.half(0x1357);
        c.word(1);
        c.half(0x0123);
        c.half(0x4567);
        c.half(0x89ab);
        c.half(0xcdef);
        c.byte(0xff);
        c.byte(0x88);
        c.half(0x2468);
        c.word(0x3fc00000);
        c.half(0xfffe);
        c.half(0x1234);
        c.half(0xabcd);
        c.half(0x5678);
        c.word(0xffffffff);
        c.word(0x10203040);
        std::shared_ptr<SOH::Cutscene> cs = read<SOH::Cutscene>(cutscenes, c, init);
        assert(cs->numCommands == 2 && cs->endFrame == 0x12345678 && cs->commands.size() == 16);
        assert(cs->GetPointerSize() == 16 * sizeof(uint32_t));
        assert(halfAt(cs->commands[4], 0) == 0x1234 && halfAt(cs->commands[4], 2) == 0xabcd);
        assert(halfAt(cs->commands[5], 0) == 0x5678 && byteAt(cs->commands[5], 2) == 0x9a &&
               byteAt(cs->commands[5], 3) == 0xbc);
        assert(byteAt(cs->commands[6], 0) == 0xde && byteAt(cs->commands[6], 1) == 0xf0 &&
               halfAt(cs->commands[6], 2) == 0x1357);
        assert(byteAt(cs->commands[10], 0) == 0xff && byteAt(cs->commands[10], 1) == 0x88 &&
               halfAt(cs->commands[10], 2) == 0x2468);
        assert(cs->commands[11] == 0x3fc00000 && cs->commands[14] == 0xffffffff && cs->commands[15] == 0x10203040);

        Bytes empty(big != 0);
        empty.word(0);
        assert(read<SOH::Background>(backgrounds, empty, init)->GetPointerSize() == 0);
        assert(read<SOH::PlayerAnimation>(animations, empty, init)->GetPointerSize() == 0);
        assert(read<SOH::Text>(texts, empty, init)->GetPointerSize() == 0);
        Bytes shortData(big != 0);
        shortData.word(1);
        bool threw = false;
        try {
            animations.ReadResource(shortData.file(), init);
        } catch (...) {
            threw = true;
        }
        assert(threw);
    }
    std::shared_ptr<Ship::File> xml = std::make_shared<Ship::File>();
    std::shared_ptr<tinyxml2::XMLDocument> doc = std::make_shared<tinyxml2::XMLDocument>();
    assert(doc->Parse("<Text><TextEntry ID='4660' TextboxType='2' TextboxYPos='3' Message='a &amp; "
                      "b'/><Ignored/><TextEntry ID='9' Message='' /></Text>") == tinyxml2::XML_SUCCESS);
    xml->Reader = doc;
    assert(!backgrounds.ReadResource(xml, init));
    assert(!animations.ReadResource(xml, init));
    assert(!texts.ReadResource(xml, init));
    assert(!arrays.ReadResource(xml, init));
    assert(!cutscenes.ReadResource(xml, init));
    assert(!xmltexts.ReadResource(xml, init));
    init->Format = RESOURCE_FORMAT_XML;
    std::shared_ptr<SOH::Text> text = std::dynamic_pointer_cast<SOH::Text>(xmltexts.ReadResource(xml, init));
    assert(text && text->messages.size() == 2 && text->messages[0].id == 4660);
    assert(text->messages[0].textboxType == 2 && text->messages[0].textboxYPos == 3);
    assert(text->messages[0].msg == "a & b\x02" && text->messages[1].msg == "\x02");
    doc->Parse(
        "<Collision MinBoundsX='-1'><Vertex X='-2' Y='4660' Z='-32768'/><Polygon NormalX='-5' Dist='-9'/><PolygonType "
        "Data1='305419896' Data2='2427178479'/><CameraData SType='7' CameraPosDataSeg='0'/><CameraPositionData "
        "PosX='-4' RotY='6' FOV='90'/><WaterBox XMin='-7' Properties='123'/></Collision>");
    std::shared_ptr<SOH::CollisionHeader> xc =
        std::dynamic_pointer_cast<SOH::CollisionHeader>(xmlcollisions.ReadResource(xml, init));
    assert(xc->GetPointer()->minBounds.x == -1 && xc->vertices[0].z == -32768 && xc->polygons[0].dist == -9);
    assert(xc->surfaceTypes[0].data[0] == 0x12345678 && xc->camPosData.size() == 3);
    assert(xc->camData[0].camPosData[0].x == -4 && xc->camData[0].camPosData[1].y == 6 && xc->waterBoxes[0].xMin == -7);
    doc->Parse("<Limb Type='Standard' LegTransX='-1.5' LegTransY='2.5' LegTransZ='-3' RotX='65535' ChildIndex='129' "
               "SiblingIndex='254' DisplayList1='gEmptyDL'/>");
    std::shared_ptr<SOH::SkeletonLimb> xl =
        std::dynamic_pointer_cast<SOH::SkeletonLimb>(xmllimbs.ReadResource(xml, init));
    assert(xl->limbType == SOH::LimbType::LOD && xl->transX == -1 && xl->transY == 2 && xl->rotX == 0xffff);
    assert(xl->limbData.lodLimb.dLists[0] == nullptr && xl->limbData.lodLimb.dLists[1] == nullptr);
    Bytes empty(false);
    empty.word(0);
    assert(!xmltexts.ReadResource(empty.file(), init));
    assert(!backgrounds.ReadResource(empty.file(), init));
    assert(!animations.ReadResource(empty.file(), init));
    assert(!texts.ReadResource(empty.file(), init));
    assert(!arrays.ReadResource(empty.file(), init));
    assert(!cutscenes.ReadResource(empty.file(), init));
    std::puts("Seven current SoH resources: LE/BE, XML, collision relocation/zero-camera, skin/LOD/curve limbs, arrays "
              "and cutscene contracts agree");
}
