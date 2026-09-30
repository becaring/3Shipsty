template <class T> json WriteJson(const T &value) {
    json result;
    to_json(result, value);
    return result;
}
void Show(const json &value) { puts(value.dump().c_str()); }
int main() {
    SaveContext source = {};
    source.healthCapacity = 320;
    source.magicLevel = 2;
    source.magicCapacity = 96;
    source.isMagicAcquired = 1;
    source.isDoubleMagicAcquired = 1;
    source.isDoubleDefenseAcquired = 1;
    source.bgsFlag = 1;
    source.swordHealth = 7;
    for (size_t i = 0; i < 124; ++i) {
        source.sceneFlags[i].chest = i * 100 + 1;
        source.sceneFlags[i].swch = i * 100 + 2;
        source.sceneFlags[i].clear = i * 100 + 3;
        source.sceneFlags[i].collect = i * 100 + 4;
    }
    for (size_t i = 0; i < sizeof(source.inventory.items); ++i)
        source.inventory.items[i] = i * 7;
    for (size_t i = 0; i < sizeof(source.inventory.ammo); ++i)
        source.inventory.ammo[i] = i - 8;
    source.inventory.equipment = 0xf0f0;
    source.inventory.upgrades = 0xFEDCBA98;
    source.inventory.questItems = 0x12345678;
    source.ship.stats.fileCreatedAt = 9007199254740993ULL;
    source.ship.stats.firstInput = 87654321;
    source.ship.quest.data.randomizer.triforcePiecesCollected = 12;
    source.ship.quest.data.randomizer.bombchuUpgradeLevel = 2;
    json value = WriteJson(source);
    Show(value);
    SaveContext destination = {};
    destination.health = 1234;
    destination.dayTime = 2345;
    destination.entranceIndex = 135;
    memset(destination.playerName, 0x7b, sizeof(destination.playerName));
    value.get_to(destination);
    assert(destination.health == 1234 && destination.dayTime == 2345 && destination.entranceIndex == 135);
    for (size_t i = 0; i < sizeof(destination.playerName); ++i)
        assert(destination.playerName[i] == 0x7b);
    assert(WriteJson(destination).dump() == value.dump());
    SaveContext created = value.get<SaveContext>();
    assert(created.health == 0 && created.entranceIndex == 0);
    Show(WriteJson(created));
    AnchorClient client = {};
    client.player = reinterpret_cast<Player *>(size_t(0x1234));
    client.posRot.pos.x = 1.25f;
    client.linkAge = 1;
    json state = json::object();
    state["name"] = "retained bytes";
    state["clientId"] = 4294967295U;
    state.get_to(client);
    assert(client.player == reinterpret_cast<Player *>(size_t(0x1234)) && client.posRot.pos.x == 1.25f &&
           client.linkAge == 1);
    assert(client.clientId == 4294967295U && client.name == "retained bytes" && client.color.r == 255 &&
           client.color.g == 255 && client.color.b == 255);
    printf("%u:%s:%s:%s:%u:%u:%d\n", client.clientId, client.name.c_str(), client.teamId.c_str(),
           client.clientVersion.c_str(), client.color.r, client.color.g, client.sceneNum);
    AnchorClient fresh = state.get<AnchorClient>();
    assert(fresh.player == nullptr && fresh.posRot.pos.x == 0 && fresh.linkAge == 0);
    for (int v = -32768; v < 32768; ++v) {
        Vec3s s = {short(v), short(-1 - v), short(v / 2)};
        Vec3f f = {float(v) / 8, float(v) / 4, float(v) / 2};
        PosRot p = {f, s};
        json j = WriteJson(p);
        PosRot r = j.get<PosRot>();
        assert(r.rot.x == s.x && r.rot.y == s.y && r.rot.z == s.z && r.pos.x == f.x && r.pos.y == f.y &&
               r.pos.z == f.z);
        if ((v & 1023) == 0)
            Show(j);
    }
    for (int v = 0; v < 256; ++v) {
        Color_RGB8 c = {u8(v), u8(255 - v), u8(v / 2)};
        json j = WriteJson(c);
        Color_RGB8 r = j.get<Color_RGB8>();
        assert(r.r == c.r && r.g == c.g && r.b == c.b);
        if ((v & 15) == 0)
            Show(j);
    }
    try {
        json empty = json::object();
        empty.get<Vec3s>();
        assert(false);
    } catch (const json::exception &e) {
        printf("missing:%d\n", e.id);
    }
    Vec3s partial = {9, 8, 7};
    json invalid = json::object();
    invalid["x"] = 123;
    invalid["y"] = "wrong type";
    invalid["z"] = 456;
    try {
        invalid.get_to(partial);
        assert(false);
    } catch (const json::exception &e) {
        printf("partial-error:%d:%d:%d:%d\n", e.id, partial.x, partial.y, partial.z);
    }
    assert(partial.x == 123 && partial.y == 8 && partial.z == 7);
    puts("65536 transforms, 256 colors, full synchronized save schema and partial updates preserved");
}
