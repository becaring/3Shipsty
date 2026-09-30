"""Extract current ordered JSON consumer statements and an XDK compiler projection."""

from pathlib import Path
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def generate(output, source_root=ROOT):
    evidence = json.loads((HERE / "ordered-consumer-source.json").read_text())
    sources = {}
    for rel, digest in evidence["sources"].items():
        raw = (Path(source_root) / rel).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("ordered consumer SHA-256 mismatch: " + rel)
        sources[Path(rel).name] = raw.decode("utf-8-sig").replace("\r\n", "\n")
    enum = re.search(r"enum class EntranceType \{.*?\n\};", sources["entrance.h"], re.S).group()
    body = enum[enum.index("{") + 1 : enum.rindex("}")]
    if not re.fullmatch(r"[\s,A-Za-z_]+", body):
        raise ValueError("unsupported EntranceType grammar")
    statements = []

    def take(name, text):
        if text not in sources[name]:
            raise ValueError("ordered statement changed: " + text)
        statements.append(text)
        return text

    init = take("hint.cpp", "    nlohmann::ordered_json log = {};")
    hints = [
        take("hint.cpp", x)
        for x in [
            '            log["messages"] = hintMessages;',
            '            log["distribution"] = distribution;',
            '            log["itemNameChosen"] = itemNamesChosen[0];',
            '            log["hintKey"] = hintKeys[0];',
            '            log["num"] = num;',
        ]
    ]
    nested = take("spoiler_log.cpp", '    jsonData["entrancesMap"][sphereString][name] = text;')
    push = take("spoiler_log.cpp", '    jsonData["entrances"].push_back(entranceJson);')
    write_signature = take("SeedContext.cpp", "void Context::WriteHintJson(nlohmann::ordered_json& spoilerFileJson) {")
    entries = re.search(
        r"    json entranceJson = json::object\(\{.*?\n    \}\);", sources["spoiler_log.cpp"], re.S
    ).group()
    statements.append(entries)
    header = """#include <nlohmann/json.hpp>
#include <iostream>
#include <vector>
#include <cstdint>
#include <type_traits>
#ifdef SHIPYARD_ORDERED_PROJECTED
#include "json/ordered_projection.hpp"
#endif
"""
    fixture = (
        """
using json = nlohmann::ordered_json;
struct EntranceFixture {
    ENTRANCE_TYPE GetType() const { return Rando::EntranceType::Dungeon; }
};
// Context here is a fixture to compile the exact reached signature and JSON
// writes. It is not the production Context or Hint implementation.
struct Context { void WriteHintJson(nlohmann::ordered_json& spoilerFileJson); };
"""
        + write_signature
        + """
    nlohmann::ordered_json log;
    log["type"] = "fixture";
    spoilerFileJson["Static Hints"]["Temple"] = log;
}
int main(){
    EntranceFixture fixture; EntranceFixture* entrance=&fixture;
    int16_t originalIndex=12,destinationIndex=-1,replacementIndex=45,replacementDestinationIndex=46;
    json jsonData;
    std::string sphereString="sphere 01",name="Market",text="Temple";
"""
        + entries
        + "\n"
        + push
        + "\n"
        + nested
        + "\n"
        + init
        + """
    std::vector<std::string> hintMessages;hintMessages.push_back("z");hintMessages.push_back("a");
    std::string distribution="woth";std::vector<uint8_t> itemNamesChosen(1,2);std::vector<uint32_t> hintKeys(1,88);uint32_t num=4;
"""
        + "\n".join(hints)
        + """
    jsonData["hint"] = log;
    Context context;context.WriteHintJson(jsonData);
    std::cout<<jsonData.dump()<<"\\n";
    // Explicit duplicate keys verify first-insertion behavior of object({...}).
    json duplicate = DUPLICATE_OBJECT;
    std::cout<<duplicate.dump()<<"\\n";
}
"""
    )
    original = (
        header
        + "namespace Rando {\n"
        + enum
        + '\n}\nstatic_assert(std::is_same<std::underlying_type<Rando::EntranceType>::type,int>::value,"EntranceType underlying type changed");\n'
        + fixture.replace("ENTRANCE_TYPE", "Rando::EntranceType").replace(
            "DUPLICATE_OBJECT", 'json::object({{"z",1},{"a",2},{"z",3}})'
        )
    )
    projected_enum = enum.replace("enum class EntranceType {", "struct EntranceType { enum type {").replace(
        "\n};", "\n}; };"
    )
    # The enum trait can also be included by application projection after its
    # own verified lowering of the same enum. No application source is edited.
    traits = "#pragma once\nnamespace nlohmann { namespace detail { template<> struct enum_underlying<Rando::EntranceType::type> { typedef int type; }; }}\n"
    projection = (
        fixture.replace("using json = nlohmann::ordered_json;", "typedef nlohmann::ordered_json json;")
        .replace("ENTRANCE_TYPE", "Rando::EntranceType::type")
        .replace(init, "    nlohmann::ordered_json log;")
    )
    members = entries[entries.index("json::object({") + len("json::object({") : entries.rindex("});")]
    replacement = (
        "    ShipyardJsonProjection::OrderedMember entranceMembers[] = {"
        + members
        + "};\n    json entranceJson = ShipyardJsonProjection::ordered_object(entranceMembers, sizeof(entranceMembers)/sizeof(entranceMembers[0]));"
    )
    projection = projection.replace(entries, replacement)
    projection = projection.replace(
        "    json duplicate = DUPLICATE_OBJECT;",
        """    ShipyardJsonProjection::OrderedMember duplicateMembers[] = {{"z",1},{"a",2},{"z",3}};
    json duplicate = ShipyardJsonProjection::ordered_object(duplicateMembers,3);""",
    )
    projected = (
        "#define SHIPYARD_ORDERED_PROJECTED\n"
        + header
        + "namespace Rando {\n"
        + projected_enum
        + '\n}\n#include "ordered_entrance_traits.hpp"\n'
        + projection
    )
    files = {
        "ordered_consumer_original.cpp": original,
        "ordered_consumer_projected.cpp": projected,
        "ordered_entrance_traits.hpp": traits,
    }
    for name, text in files.items():
        (output / name).write_text(text, newline="\n")
    return {
        "sources": evidence["sources"],
        "extracted_statements": statements,
        "generated_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files},
        "full_application_classes": False,
    }
