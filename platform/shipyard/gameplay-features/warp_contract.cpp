int main() {
    std::map<std::string, WarpPoint> values;
    for (int i = 0; i < 256; ++i) {
        WarpPoint v = {};
        v.entranceId = i * 257 - 30000;
        v.roomNum = static_cast<s8>(i);
        v.pos.x = i * 1.25f;
        v.pos.y = -i * 0.5f;
        v.pos.z = i - 128.0f;
        v.rotY = static_cast<s16>(i * 259);
        v.bootToPoint = (i % 3) == 0;
        values[std::to_string(i)] = v;
    }
    nlohmann::json serialized = EncodeWarpPoints(values);
    std::cout << serialized.dump() << '\n';
    auto decoded = DecodeWarpPoints(serialized);
    assert(decoded.size() == values.size());
    for (const auto &r : values) {
        const auto &d = decoded.at(r.first);
        const auto &v = r.second;
        assert(d.entranceId == v.entranceId && d.roomNum == v.roomNum && d.pos.x == v.pos.x && d.pos.y == v.pos.y &&
               d.pos.z == v.pos.z && d.rotY == v.rotY && d.bootToPoint == v.bootToPoint);
    }
    const char *keys[] = {"entranceId", "roomNum", "pos", "rotY", "bootToPoint"};
    for (const char *key : keys) {
        auto broken = serialized;
        broken["0"].erase(key);
        bool threw = false;
        try {
            DecodeWarpPoints(broken);
        } catch (const nlohmann::json::out_of_range &e) {
            threw = e.id == 403;
        }
        assert(threw);
    }
    auto broken = serialized;
    broken["0"]["pos"]["x"] = "invalid";
    bool threw = false;
    try {
        DecodeWarpPoints(broken);
    } catch (const nlohmann::json::type_error &e) {
        threw = e.id == 302;
    }
    assert(threw);
    assert(DecodeWarpPoints(nlohmann::json::object()).empty());
    std::cout << "256 actual warp values preserve JSON fields, signed values, positions and missing/type errors.\n";
}
