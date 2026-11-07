// Included after complete, mechanically extracted methods. No fake services.
using namespace SOH;

template <class T, class Factory> std::shared_ptr<T> parse(const char *xml, unsigned id) {
    tinyxml2::XMLDocument doc;
    assert(doc.Parse(xml) == tinyxml2::XML_SUCCESS);
    std::shared_ptr<Ship::ResourceInitData> init = std::make_shared<Ship::ResourceInitData>();
    init->Path = "scene-fixture";
    init->Id = 0x12345678;
    init->ResourceVersion = 7;
    Factory factory;
    std::shared_ptr<T> value = std::dynamic_pointer_cast<T>(factory.ReadResource(init, doc.RootElement()));
    assert(value && value->GetInitData() == init && value->cmdId == static_cast<SceneCommandID>(id));
    assert(value->GetRawPointer() == value->GetPointer());
    return value;
}

int main() {
    spdlog::set_pattern("%v");
    spdlog::set_level(spdlog::level::info);
    assert(sizeof(SceneCommandID) == 1);
    // Value-initialization through the implicitly generated original defaults
    // zeroes scalar payload members as well as constructing the resource base.
    assert(std::make_shared<SetActorList>()->numActors == 0);
    assert(std::make_shared<SetTimeSettings>()->settings.hour == 0);
    assert(std::make_shared<SetMesh>()->meshHeader.base.type == 0);
    assert(Shipyard::SohResources::UIntToString(0) == "0");
    assert(Shipyard::SohResources::UIntToString(4294967295U) == "4294967295");
    std::shared_ptr<EndMarker> marker = parse<EndMarker, EndMarkerFactoryXML>("<EndMarker/>", 20);
    LogEndMarkerAsXML(marker);
    for (unsigned big = 0; big < 2; ++big)
        for (unsigned i = 0; i < 1024; ++i) {
            std::shared_ptr<std::vector<char>> data = std::make_shared<std::vector<char>>();
            for (unsigned b = 0; b < 4; ++b)
                data->push_back(static_cast<char>(i >> ((big ? 3 - b : b) * 8)));
            std::shared_ptr<Ship::BinaryReader> reader =
                std::make_shared<Ship::BinaryReader>(std::make_shared<Ship::MemoryStream>(data));
            reader->SetEndianness(big ? Ship::Endianness::Big : Ship::Endianness::Little);
            ReadBinaryCommandId(marker, reader);
            assert(marker->cmdId == static_cast<SceneCommandID>(i & 255));
        }
    for (unsigned i = 0; i < commandNames.size(); ++i)
        assert(GetCommandID(commandNames[i]) == static_cast<SceneCommandID>(i));
    assert(commandNames.size() == 26 && GetCommandID("unknown") == SceneCommandID::Error);
    assert(SceneCommandID::SetCameraSettings == SceneCommandID::SetWorldMapVisited);
    std::unordered_map<SceneCommandID, int> byId;
    for (unsigned i = 0; i < 256; ++i)
        byId[static_cast<SceneCommandID>(i)] = i + 1;
    for (unsigned i = 0; i < 1024; ++i)
        assert(byId[static_cast<SceneCommandID>(i)] == int((i & 255) + 1));

    std::shared_ptr<SetCsCamera> cs = parse<SetCsCamera, SetCsCameraFactoryXML>("<SetCsCamera/>", 2);
    LogCsCameraAsXML(cs);
    std::shared_ptr<SetCameraSettings> cam = parse<SetCameraSettings, SetCameraSettingsFactoryXML>(
        "<SetCameraSettings CameraMovement='-128' WorldMapArea='-123456'/>", 25);
    assert(cam->settings.cameraMovement == -128 && cam->settings.worldMapArea == -123456);
    LogCameraSettingsAsXML(cam);
    std::shared_ptr<SetEchoSettings> echo =
        parse<SetEchoSettings, SetEchoSettingsFactoryXML>("<SetEchoSettings Echo='-128'/>", 22);
    assert(echo->settings.echo == -128);
    LogEchoSettingsAsXML(echo);
    std::shared_ptr<SetRoomBehavior> room = parse<SetRoomBehavior, SetRoomBehaviorFactoryXML>(
        "<SetRoomBehavior GameplayFlags1='-1' GameplayFlags2='-123456'/>", 8);
    assert(room->roomBehavior.gameplayFlags == -1 && room->roomBehavior.gameplayFlags2 == -123456);
    LogRoomBehaviorAsXML(room);
    std::shared_ptr<SetSkyboxModifier> modifier = parse<SetSkyboxModifier, SetSkyboxModifierFactoryXML>(
        "<SetSkyboxModifier SkyboxDisabled='255' SunMoonDisabled='128'/>", 18);
    assert(modifier->modifier.skyboxDisabled == 255 && modifier->modifier.sunMoonDisabled == 128);
    LogSkyboxModifierAsXML(modifier);
    std::shared_ptr<SetSkyboxSettings> sky = parse<SetSkyboxSettings, SetSkyboxSettingsFactoryXML>(
        "<SetSkyboxSettings Unknown='255' SkyboxId='128' Weather='17' Indoors='3'/>", 17);
    assert(sky->settings.unk == 255 && sky->settings.skyboxId == 128 && sky->settings.weather == 17 &&
           sky->settings.indoors == 3);
    LogSkyboxSettingsAsXML(sky);
    std::shared_ptr<SetSoundSettings> sound = parse<SetSoundSettings, SetSoundSettingsFactoryXML>(
        "<SetSoundSettings Reverb='255' NatureAmbienceId='128' SeqId='17'/>", 21);
    assert(sound->settings.reverb == 255 && sound->settings.natureAmbienceId == 128 && sound->settings.seqId == 17);
    LogSoundSettingsAsXML(sound);
    std::shared_ptr<SetSpecialObjects> special = parse<SetSpecialObjects, SetSpecialObjectsFactoryXML>(
        "<SetSpecialObjects ElfMessage='-128' GlobalObject='-32768'/>", 7);
    assert(special->specialObjects.elfMessage == -128 && special->specialObjects.globalObject == -32768);
    LogSpecialObjectsAsXML(special);
    std::shared_ptr<SetTimeSettings> time = parse<SetTimeSettings, SetTimeSettingsFactoryXML>(
        "<SetTimeSettings Hour='255' Minute='128' TimeIncrement='17'/>", 16);
    assert(time->settings.hour == 255 && time->settings.minute == 128 && time->settings.timeIncrement == 17);
    LogTimeSettingsAsXML(time);
    std::shared_ptr<SetWindSettings> wind = parse<SetWindSettings, SetWindSettingsFactoryXML>(
        "<SetWind WindWest='-128' WindVertical='-1' WindSouth='127' WindSpeed='255'/>", 5);
    assert(wind->settings.windWest == -128 && wind->settings.windVertical == -1 && wind->settings.windSouth == 127 &&
           wind->settings.windSpeed == 255);
    LogWindSettingsAsXML(wind);

    const char *actorXml = "<SetActorList><Ignored/><ActorEntry Id='65535' PosX='-32768' PosY='-1' PosZ='4660' "
                           "RotX='-2' RotY='32767' RotZ='-3' Params='32768'/></SetActorList>";
    std::shared_ptr<SetActorList> actors = parse<SetActorList, SetActorListFactoryXML>(actorXml, 1);
    assert(actors->numActors == 1 && actors->actorList[0].id == -1 && actors->actorList[0].pos.x == -32768 &&
           actors->actorList[0].params == -32768);
    assert(actors->GetPointer() == actors->actorList.data() && actors->GetPointerSize() == sizeof(ActorEntry));
    LogActorListAsXML(actors);
    std::shared_ptr<SetStartPositionList> starts = parse<SetStartPositionList, SetStartPositionListFactoryXML>(
        "<SetStartPositionList><Ignored/><StartPositionEntry Id='65535' PosX='-32768' PosY='-1' PosZ='4660' RotX='-2' "
        "RotY='32767' RotZ='-3' Params='32768'/></SetStartPositionList>",
        0);
    assert(starts->startPositions.size() == 1 && starts->startPositions[0].rot.y == 32767);
    LogStartPositionListAsXML(starts);
    std::shared_ptr<SetEntranceList> entrances = parse<SetEntranceList, SetEntranceListFactoryXML>(
        "<SetEntranceList><Ignored/><EntranceEntry Spawn='255' Room='128'/></SetEntranceList>", 6);
    assert(entrances->numEntrances == 1 && entrances->entrances[0].spawn == 255 && entrances->entrances[0].room == 128);
    LogEntranceListAsXML(entrances);
    std::shared_ptr<SetExitList> exits = parse<SetExitList, SetExitListFactoryXML>(
        "<SetExitList><Ignored/><ExitEntry Id='65535'/><ExitEntry Id='4660'/></SetExitList>", 19);
    assert(exits->exits.size() == 2 && exits->exits[0] == 65535 && exits->exits[1] == 4660);
    LogExitListAsXML(exits);
    std::shared_ptr<SetObjectList> objects = parse<SetObjectList, SetObjectListFactoryXML>(
        "<SetObjectList><Ignored/><ObjectEntry Id='-32768'/><ObjectEntry Id='-1'/></SetObjectList>", 11);
    assert(objects->numObjects == 2 && objects->objects[0] == -32768 && objects->objects[1] == -1);
    LogObjectListAsXML(objects);
    std::shared_ptr<SetRoomList> rooms = parse<SetRoomList, SetRoomListFactoryXML>(
        "<SetRoomList><Ignored/><RoomEntry Path='room/path/long-enough-for-stable-storage' VromStart='305419896' "
        "VromEnd='123456789'/></SetRoomList>",
        4);
    assert(rooms->numRooms == 1 && rooms->rooms[0].vromStart == 0x12345678 && rooms->rooms[0].vromEnd == 123456789);
    assert(rooms->rooms[0].fileName == rooms->fileNames[0].c_str());
    LogRoomListAsXML(rooms);
    std::shared_ptr<SetTransitionActorList> transition =
        parse<SetTransitionActorList, SetTransitionActorListFactoryXML>(
            "<SetTransitionActorList><TransitionActorEntry FrontSideRoom='255' FrontSideEffects='128' "
            "BackSideRoom='17' BackSideEffects='3' Id='-1' PosX='-32768' PosY='4660' PosZ='-2' RotY='-3' "
            "Params='65535'/></SetTransitionActorList>",
            14);
    assert(transition->transitionActorList.size() == 1 && transition->transitionActorList[0].pos.x == -32768 &&
           transition->transitionActorList[0].params == -1);
    LogTransitionActorListAsXML(transition);
    std::shared_ptr<SetLightList> lights = parse<SetLightList, SetLightListFactoryXML>(
        "<SetLightList><LightInfo Type='1' X='-32768' Y='4660' Z='-1' ColorR='255' ColorG='128' ColorB='17' "
        "DrawGlow='3' Radius='-2'/></SetLightList>",
        12);
    assert(lights->numLights == 1 && lights->lightList[0].params.point.x == -32768 &&
           lights->lightList[0].params.point.color[0] == 255);
    LogLightListAsXML(lights);
    std::shared_ptr<SetLightingSettings> lighting = parse<SetLightingSettings, SetLightingSettingsFactoryXML>(
        "<SetLightingSettings><LightingSetting AmbientColorR='255' AmbientColorG='128' AmbientColorB='17' "
        "Light1DirX='-128' Light1DirY='-1' Light1DirZ='127' Light1ColorR='255' Light2DirX='-2' Light2ColorB='129' "
        "FogColorG='130' FogNear='-32768' FogFar='32767'/></SetLightingSettings>",
        15);
    assert(lighting->settings.size() == 1 && lighting->settings[0].light1Dir[0] == -128 &&
           lighting->settings[0].fogNear == -32768);
    LogLightingSettingsAsXML(lighting);
    for (unsigned kind = 0; kind < 3; ++kind) {
        std::string xml = "<SetMesh Data='129' MeshHeaderType='" + Shipyard::SohResources::UIntToString(kind) +
                          "' PolyNum='1'><Ignored/><Polygon PolyType='2' Format='2' BgImageCount='1' "
                          "MeshOpa='opaque-display-list-path' MeshXlu='translucent-display-list-path' PosX='-32768' "
                          "PosY='4660' PosZ='-1' Unknown='-2'><BgImage Unknown_00='65535' Id='255' "
                          "ImagePath='background-image-path' Unknown_0C='305419896' TLUT='123456789' Width='320' "
                          "Height='240' Fmt='2' Siz='3' Mode0='32768' TLUTCount='256'/></Polygon></SetMesh>";
        std::shared_ptr<SetMesh> mesh = parse<SetMesh, SetMeshFactoryXML>(xml.c_str(), 10);
        assert(mesh->data == 129 && mesh->meshHeader.base.type == kind);
        if (kind == 0)
            assert(mesh->meshHeader.polygon0.start == mesh->dlists.data() && mesh->meshHeader.polygon0.num == 1);
        if (kind == 1) {
            assert(mesh->meshHeader.polygon1.multi.count == 1 &&
                   mesh->meshHeader.polygon1.multi.list == mesh->images.data());
            assert(mesh->images[0].width == 320 && mesh->images[0].unk_0C == 0x12345678 &&
                   mesh->images[0].mode0 == 32768);
        }
        if (kind == 2)
            assert(mesh->meshHeader.polygon2.start == mesh->dlists2.data() && mesh->dlists2[0].pos.x == -32768);
        LogMeshAsXML(mesh);
    }
    // Service-dependent factories are not replaced. Their types and
    // loggers can still be exercised with directly owned resource references.
    std::shared_ptr<Ship::ResourceInitData> init = actors->GetInitData();
    std::shared_ptr<Scene> scene = std::make_shared<Scene>(init);
    assert(!scene->GetPointer() && !scene->GetPointerSize());
    std::shared_ptr<SetAlternateHeaders> alternate = std::make_shared<SetAlternateHeaders>(init);
    alternate->headers.push_back(scene);
    alternate->headerFileNames.push_back("alternate/header");
    assert(!alternate->GetPointer() && !alternate->GetPointerSize());
    LogAlternateHeadersAsXML(alternate);
    std::shared_ptr<SetCollisionHeader> collision = std::make_shared<SetCollisionHeader>(init);
    assert(!collision->GetPointer() && !collision->GetPointerSize());
    collision->fileName = "collision/path";
    collision->collisionHeader = std::make_shared<CollisionHeader>(init);
    assert(collision->GetPointer() == collision->collisionHeader->GetPointer() &&
           collision->GetPointerSize() == sizeof(CollisionHeaderData));
    LogSetCollisionHeaderAsXML(collision);
    std::shared_ptr<SetCutscenes> cutscene = std::make_shared<SetCutscenes>(init);
    assert(!cutscene->GetPointer() && !cutscene->GetPointerSize());
    cutscene->fileName = "cutscene/path";
    cutscene->cutscene = std::make_shared<Cutscene>(init);
    cutscene->cutscene->commands.push_back(0x12345678);
    assert(cutscene->GetPointer() == cutscene->cutscene->GetPointer() && cutscene->GetPointerSize() == 4);
    LogCutscenesAsXML(cutscene);
    std::shared_ptr<SetPathways> paths = std::make_shared<SetPathways>(init);
    paths->numPaths = 1;
    paths->pathFileNames.push_back("pathway/path");
    paths->paths.push_back(nullptr);
    assert(paths->GetPointer() == paths->paths.data() && paths->GetPointerSize() == sizeof(PathData *));
    LogPathwaysAsXML(paths);
    RegisterAuditXMLFactories();
    std::shared_ptr<Ship::ResourceInitData> sceneInit = std::make_shared<Ship::ResourceInitData>();
    sceneInit->Id = 0x12345678;
    sceneInit->ResourceVersion = 7;
    sceneInit->Path = "scene-parent/path";
    std::shared_ptr<Scene> parsedScene = std::make_shared<Scene>(sceneInit);
    std::shared_ptr<tinyxml2::XMLDocument> sceneDoc = std::make_shared<tinyxml2::XMLDocument>();
    sceneDoc->Parse("<Scene><SetTimeSettings Hour='255'/><SetActorList><ActorEntry Id='-1' "
                    "PosX='-32768'/></SetActorList><Unrecognized/><Unused09/><EndMarker/></Scene>");
    ParseSceneCommands(parsedScene, sceneDoc);
    assert(parsedScene->commands.size() == 5 && !parsedScene->commands[2] && !parsedScene->commands[3]);
    assert(std::static_pointer_cast<SetTimeSettings>(parsedScene->commands[0])->settings.hour == 255);
    assert(std::static_pointer_cast<SetActorList>(parsedScene->commands[1])->actorList[0].pos.x == -32768);
    for (unsigned i = 0; i < 5; ++i)
        if (parsedScene->commands[i]) {
            std::shared_ptr<Ship::ResourceInitData> metadata = parsedScene->commands[i]->GetInitData();
            assert(metadata->Id == sceneInit->Id && metadata->ResourceVersion == 7);
            assert(metadata->Type == static_cast<uint32_t>(SOH::ResourceType::SOH_SceneCommand));
            assert(metadata->Path == sceneInit->Path + "/SceneCommand" + Shipyard::SohResources::UIntToString(i));
        }
    std::puts("Scene XML payloads, mesh variants, complete loggers, command IDs and reference type contracts agree");
}
