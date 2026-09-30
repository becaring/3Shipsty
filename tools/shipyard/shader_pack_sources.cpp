// Host generator for the prebuilt shader pack. For each key it runs exactly
// what the runtime's CreateShader runs before compiling: gfx_cc_get_features,
// the projected Prism builder (no root signature, three-point filtering and
// sRGB from the key) and Shipyard_LowerShader. Each distinct lowered source is
// written once, named by its FNV-1a 64 hash; stdout maps keys to their vertex
// float count and source name ("K id0 id1 tp srgb floats name").
//
// usage: shader_pack_sources <template> <keys> <out-dir>
// keys: one "<id0 hex> <id1 hex> <three-point 0|1> <srgb 0|1>" per line
#include "prism/processor.h"
#include "fast/cc_features.h"
#include "shader_lower.h"
#include "audit.h"
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <spdlog/spdlog.h>
#ifdef SHIPYARD_PROJECTED
namespace values = xbox_compat;
#else
namespace values = std;
#endif

std::string AuditTemplate;
values::optional<std::string> AuditInclude(const std::string&) {
    return values::nullopt;
}

static uint64_t Fnv64(const std::string& text) {
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < text.size(); ++i)
        hash = (hash ^ static_cast<unsigned char>(text[i])) * 1099511628211ULL;
    return hash;
}

int main(int argc, char** argv) {
    try {
        if (argc != 4)
            throw std::runtime_error("usage: shader_pack_sources <template> <keys> <out-dir>");
        spdlog::set_level(spdlog::level::off);
        std::ifstream templ(argv[1], std::ios::binary);
        std::ostringstream bytes;
        bytes << templ.rdbuf();
        AuditTemplate = bytes.str();
        if (AuditTemplate.empty())
            throw std::runtime_error("empty shader template");
        std::ifstream keys(argv[2]);
        const std::string out(argv[3]);
        unsigned long long id0 = 0;
        unsigned long id1 = 0;
        int threePoint = 0, srgb = 0;
        while (keys >> std::hex >> id0 >> id1 >> std::dec >> threePoint >> srgb) {
            CCFeatures features = {};
            gfx_cc_get_features(id0, static_cast<uint32_t>(id1), &features);
            size_t floats = 0;
            const std::string hlsl =
                Fast::gfx_direct3d_common_build_shader(floats, features, false, threePoint != 0, srgb != 0);
            std::string lowered, error;
            if (!Shipyard_LowerShader(hlsl, lowered, error, 2)) {
                std::printf("F %016llx %08lx %d %d %s\n", id0, id1, threePoint, srgb, error.c_str());
                continue;
            }
            char name[17];
            std::snprintf(name, sizeof(name), "%016llx", static_cast<unsigned long long>(Fnv64(lowered)));
            const std::string path = out + "/" + name + ".hlsl";
            std::ifstream existing(path.c_str(), std::ios::binary);
            if (!existing.good()) {
                std::ofstream file(path.c_str(), std::ios::binary);
                file << lowered;
                if (!file.good())
                    throw std::runtime_error("writing " + path);
            }
            std::printf("K %016llx %08lx %d %d %u %s\n", id0, id1, threePoint, srgb,
                        static_cast<unsigned>(floats), name);
        }
        return 0;
    } catch (const std::exception& failure) {
        std::fprintf(stderr, "%s\n", failure.what());
        return 1;
    }
}
