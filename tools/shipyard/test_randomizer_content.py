"""Native content implementations plus original and projected content contracts."""

import hashlib, json, re, runpy, unittest
from pathlib import Path
from prepare_randomizer_content import ROOT, OUT, OWN, BASE, UNITS, prepare, build
from prepare_archives import stable
from prepare_randomizer import edits_apply
from cpp_ast import PARSER, walk
from test_custom_message import bounded_source
from test_randomizer_data import functions, sig, name, cls, strip_includes

ENV = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))


def read(path):
    return path.read_text(encoding="utf-8-sig")


def cpp(projected, short):
    return read((OUT / "generated" if projected else ROOT) / BASE / short)


def without(text, excluded):
    return edits_apply(
        text.encode(), [(n.start_byte, n.end_byte, "") for n in functions(text) if any(x in sig(n) for x in excluded)]
    )


def invoke_host(source, projected, label):
    folder = OUT / (label + ("-projected" if projected else "-original"))
    folder.mkdir(parents=True, exist_ok=True)
    stable(folder / "contract.cpp", source)
    compiler, env = ENV["host_environment"]()
    includes = [
        p
        for p in json.loads((OUT / "xdk/build.json").read_text())[0]["command"]
        if p.startswith("/I") and "Microsoft Xbox 360 SDK" not in p
    ]
    command = (
        [
            compiler,
            "/nologo",
            "/std:c++20",
            "/utf-8",
            "/EHsc",
            "/GR",
            "/MD",
            "/bigobj",
            "/DNOMINMAX",
            "/DSHIPYARD_AUDIO_TEST",
            "/DF3DEX_GBI_2",
            "/DCONTROLLERBUTTONS_T=uint32_t",
            "/I" + str(ROOT / "scratch/deps/spdlog/include"),
        ]
        + includes
        + [folder / "contract.cpp", "/Fo" + str(folder / "contract.obj"), "/Fe" + str(folder / "contract.exe")]
    )
    if label == "enums-host":
        command.insert(1, "/Zc:preprocessor")
    result = ENV["invoke"](command, folder, "compile", env, success=False)
    assert result["returncode"] == 0, "\n".join(
        l for l in (result["stdout"] + result["stderr"]).splitlines() if "error " in l
    )[:6500]
    result = ENV["invoke"]([folder / "contract.exe"], folder, "run", env, success=False)
    assert result["returncode"] == 0, result["stderr"] + result["stdout"][-500:]
    return result["stdout"]


def content_host(projected):
    # Complete value declarations; only service-dependent methods are omitted
    # from this bounded host executable. Production compiles every method.
    bundle, _, _ = bounded_source(projected)
    source = (
        """#include <tuple>
#include <variant>
#include <iostream>
#include <sstream>
#include "soh/Enhancements/randomizer/option.h"
#include "z64actor_enum.h"
#include "z64scene.h"
#include "z64save.h"
#include "randomizer-content/support.h"
#include "resources/runtime_support.h"
"""
        + bundle
        + "\n"
    )
    spoiler = read(ROOT / BASE / "3drando/spoiler_log.hpp")
    source += (
        next(
            n.text.decode()
            for n in PARSER.parse(spoiler.encode()).root_node.named_children
            if n.type == "type_definition" and b"SpoilerCollectionCheckType" in n.text
        )
        + "\n"
    )
    hints = read(
        (ROOT / "scratch/randomizer-item-xdk/generated" / BASE / "3drando/HintText.h")
        if projected
        else ROOT / BASE / "3drando/hints.hpp"
    )
    source += cls(hints, "HintText").replace("  private:", "  public:") + ";\n"
    methods = read(ROOT / BASE / "3drando/hints.cpp")
    source += (
        "\n".join(
            n.text.decode() for n in functions(methods) if name(n) in ["HintText::HintText", "& HintText::GetClear"]
        )
        + "\n"
    )
    source += (
        cls(read(ROOT / BASE / "3drando/hints.hpp"), "StaticHintInfo")
        + ";\n"
        + next(n.text.decode() for n in functions(methods) if name(n) == "StaticHintInfo::StaticHintInfo")
        + "\n"
    )
    util = read(ROOT / "soh/soh/util.cpp")
    source += (
        "\n".join(
            n.text.decode()
            for n in PARSER.parse(util.encode()).root_node.named_children
            if n.type == "declaration"
            and (b" rcareaPrefixes =" in n.text or n.text.startswith(b"std::string invalidString ="))
        )
        + "\nnamespace SohUtils {const std::string& GetRandomizerCheckAreaPrefix(int32_t rcarea);}\n"
    )
    source += (
        next(n.text.decode() for n in functions(util) if "SohUtils::GetRandomizerCheckAreaPrefix(" in sig(n)) + "\n"
    )
    loc = read((ROOT / "scratch/randomizer-item-xdk/generated" if projected else ROOT) / BASE / "location.h")
    source += (
        "namespace Rando {\n"
        + cls(loc, "SpoilerCollectionCheck")
        + ";\n"
        + cls(loc, "Location")
        + ";\nclass Item;\n"
        + cls(read(ROOT / "scratch/randomizer-item-xdk/generated" / BASE / "static_data.h"), "StaticData")
        + ";\n}\n"
    )
    option = read(ROOT / "scratch/randomizer-options-xdk/generated" / BASE / "option.cpp")
    source += (
        "namespace Rando {\n"
        + "\n".join(
            n.text.decode()
            for n in functions(option)
            if name(n)
            in [
                "Option::Option",
                "& Option::operator=",
                "Option::RebindCopiedPointers",
                "LocationOption::LocationOption",
                "Option::PopulateTextToNum",
                "Option::GetOptionCount",
            ]
        )
        + "\n}\n"
    )
    source += (
        strip_includes(
            read((ROOT / "scratch/randomizer-data-xdk/generated" if projected else ROOT) / BASE / "location.cpp")
        )
        + "\n"
    )
    source += """std::array<HintText,RHT_MAX> Rando::StaticData::hintTextTable;
std::unordered_map<std::string,RandomizerCheck> Rando::StaticData::locationNameToEnum;
"""
    source += strip_includes(without(cpp(projected, "location_list.cpp"), ["GetAllDungeonLocations("])) + "\n"
    source += (
        strip_includes(read(ROOT / "scratch/application-gui-xdk/generated" / BASE / "randomizer_check_objects.h"))
        + "\n"
    )
    source += strip_includes(without(cpp(projected, "randomizer_check_objects.cpp"), ["UpdateImGuiVisibility("])) + "\n"
    controls = read(ROOT / BASE / "3drando/custom_messages.cpp")
    source += (
        "namespace CustomMessages {\n"
        + next(n.text.decode() for n in functions(controls) if name(n) == "TWO_WAY_CHOICE")
        + "\n}\n"
    )
    for short in UNITS:
        if short.startswith("3drando/"):
            source += strip_includes(cpp(projected, short)) + "\n"
    driver = read(OWN / "content_contract.cpp")
    filters = [
        name(n).split("::")[-1]
        for n in functions(cpp(False, "location_list.cpp"))
        if name(n).startswith("Rando::StaticData::Get") and "GetAllDungeon" not in name(n)
    ]
    driver = driver.replace(
        "SHIPYARD_FILTER_CALLS", "\n".join('Locations("' + f + '",StaticData::' + f + "());" for f in filters)
    )
    return invoke_host(source + "\n" + driver, projected, "content-host")


def literals_host(projected):
    source = """#include <string>
#include <cstdio>
using namespace std::literals::string_literals;
void show(const std::string& s){printf("%zu:",s.size());for(unsigned char c:s)printf("%02x",c);puts("");}
int main(){
"""
    audit = json.loads((OUT / "manifest.json").read_text())["audit"]
    count = 0
    for info in audit.values():
        for literal in info["literals"]:
            spelling = literal["projected"] if projected else literal["original"]
            count += 1
            if spelling.startswith("std::string("):
                source += "show(" + spelling + ");\n"
            else:
                source += "show(std::string(" + spelling + ",sizeof(" + spelling + ")-1));\n"
    return invoke_host(source + "}\n", projected, "literals-host"), count


def enums_host(projected):
    # Keep the repeated X-macro includes intact; both versions instantiate every
    # enum map. Unknown names/values and valid round trips are exercised.
    header = read((OUT / "generated" if projected else ROOT) / BASE / "randomizerEnumStrings.h")
    text = cpp(projected, "randomizerEnumStrings.cpp")
    text = re.sub(
        r'^#include "(?:randomizer-content/support.h|resources/runtime_support.h|(?:soh/Enhancements/randomizer/)?randomizerEnumStrings.h)"\n',
        "",
        text,
        flags=re.M,
    )
    text = re.sub(
        r'#include "(?:soh/Enhancements/randomizer/)?randomizerEnums.h"',
        '#include "' + (ROOT / BASE / "randomizerEnums.h").as_posix() + '"',
        text,
    )
    enum_names = []
    for p in sorted((ROOT / BASE / "randomizerEnums").glob("*.h")):
        enum_names += re.findall(r"^RANDO_ENUM_BEGIN\((\w+)\)", read(p), re.M)
    source = "#include <iostream>\n#include <map>\n" + header + "\n" + text + "\n"
    source += (
        """template<class E> bool Check(const char* name){
      const auto& values=GetEnumToStringMap<E>();const auto& names=GetStringToEnumMap<E>();
      std::map<int,std::string> ordered;for(const auto& p:values){std::string s(p.second.data(),\
p.second.size());ordered[int(p.first)]=s;auto parsed=StringToEnum<E>(p.second);\
if(!parsed||*parsed!=p.first)return false;}
      for(const auto& p:names){auto named=EnumToString<E>(p.second);if(!named)return false;}
      if(StringToEnum<E>("SHIPYARD_INVALID_ENUM_NAME")||EnumToString<E>(E(-98765)))return false;
      std::cout<<name<<":"<<values.size()<<":"<<names.size()<<"\\n";for(const auto& \
p:ordered)std::cout<<p.first<<":"<<p.second<<"\\n";return true;}
      int main(){"""
        + "".join("if(!Check<" + n + '>("' + n + '"))return 1;' for n in enum_names)
        + "}\n"
    )
    return invoke_host(source, projected, "enums-host"), len(enum_names)


def items_host(projected):
    bundle, _, _ = bounded_source(projected)
    bundle = re.sub(r"typedef enum \{\s*LANGUAGE_ENG,.*?\} Language;", "", bundle, flags=re.S)
    source = (
        """#include <array>
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerTypes.h"
#include "soh/Enhancements/item-tables/ItemTableTypes.h"
#include "z64object.h"
#include "soh_assets.h"
#include "textures/icon_item_24_static/icon_item_24_static.h"
#include "textures/icon_item_static/icon_item_static.h"
#include "soh/Enhancements/custom-message/CustomMessageTypes.h"
#include "resources/runtime_support.h"
"""
        + bundle
        + "\n"
    )
    header = read((ROOT / "scratch/randomizer-item-xdk/generated" if projected else ROOT) / BASE / "item.h")
    root = PARSER.parse(header.encode()).root_node
    source += (
        "\n".join(n.text.decode() + ";" for n in root.named_children if n.type == "enum_specifier")
        + "\nclass HintText;\nnamespace Rando {\n"
        + cls(header, "Item").replace("  private:", "  public:")
        + ";\n"
    )
    methods = read((ROOT / "scratch/randomizer-item-xdk/generated" if projected else ROOT) / BASE / "item.cpp")
    omitted = ["ApplyEffect", "UndoEffect", "GetGIEntry", "GetGIEntry_Copy", "IsMajorItem", "GetHint"]
    source += (
        "\n".join(n.text.decode() for n in functions(methods) if sig(n).split("::")[-1].split("(")[0] not in omitted)
        + "\n}\n"
    )
    init = next(n for n in functions(cpp(projected, "item_list.cpp")) if name(n) == "Rando::StaticData::InitItemTable")
    statements = []
    assignments = 0
    draws = []
    for n in init.child_by_field_name("body").named_children:
        if n.type == "comment":
            continue
        if n.type == "declaration" and b"Context::GetInstance" in n.text:
            continue
        if b".SetCustomDrawFunc(" in n.text:
            draws.append(n.text.decode())
            continue
        statements.append(n.text.decode())
        if n.type == "expression_statement" and n.text.startswith(b"itemTable["):
            assignments += 1
    source += (
        "using namespace Rando;\nstd::array<Item,RG_MAX> itemTable;\nstd::unordered_map<std::string,RandomizerGet> itemNameToEnum;\nvoid InitValues(){\n"
        + "\n".join(statements)
        + "\n}\n"
    )
    inventory = read(ROOT / "soh/src/code/z_inventory.c")
    source += (
        "SaveContext gSaveContext;\n"
        + next(
            n.text.decode()
            for n in PARSER.parse(inventory.encode()).root_node.named_children
            if n.type == "declaration" and n.text.startswith(b"u8 gItemSlots[]")
        )
        + "\n"
    )
    source += strip_includes(cpp(projected, "item_category_adj.cpp")) + "\n"
    tricks = read((ROOT / "scratch/randomizer-options-xdk/generated" if projected else ROOT) / BASE / "tricks.h")
    source += "#include <imgui.h>\n#include <set>\nnamespace Rando {\n" + cls(tricks, "Tricks") + ";\n}\n"
    if projected:
        source += strip_includes(read(OWN / "tag_hash.h")) + "\n"
    source += (
        strip_includes(without(cpp(projected, "tricks.cpp"), ["Tricks::GetTagColor(", "Tricks::DrawTagChips("])) + "\n"
    )
    source += read(OWN / "item_contract.cpp")
    return invoke_host(source, projected, "items-host"), assignments, draws


class ContentContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build()

    def test_native_complete_units(self):
        rows = json.loads((OUT / "xdk/build.json").read_text())
        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertEqual(row["exit"], 0)
            self.assertEqual(hashlib.sha256((ROOT / row["source"]).read_bytes()).hexdigest(), row["source_sha256"])

    def test_all_definitions_retained(self):
        for short in UNITS:
            if short == "randomizerEnumStrings.cpp":
                continue
            self.assertEqual(
                [sig(n) for n in functions(cpp(False, short))],
                [sig(n) for n in functions(cpp(True, short)) if not name(n).startswith(("Build_", "ShipyardHint_"))],
            )

    def test_hint_chunk_execution_order(self):
        methods = {
            "3drando/hint_list.cpp": ("HintTable_Init", "Main"),
            "3drando/hint_list/hint_list_item.cpp": ("HintTable_Init_Item", "Item"),
            "3drando/hint_list/hint_list_exclude_overworld.cpp": ("HintTable_Init_Exclude_Overworld", "Overworld"),
            "3drando/hint_list/hint_list_exclude_dungeon.cpp": ("HintTable_Init_Exclude_Dungeon", "Dungeon"),
        }
        audit = json.loads((OUT / "manifest.json").read_text())["audit"]
        for short, (method, label) in methods.items():
            originals = functions(cpp(False, short))
            projected = functions(cpp(True, short))
            original = next(n for n in originals if name(n) == "StaticData::" + method)
            current = next(n for n in projected if name(n) == "StaticData::" + method)
            helpers = {name(n): n for n in projected if name(n).startswith("ShipyardHint_" + label + "_")}
            expected = []
            actual = []
            sizes = []

            def steps(node):
                return [
                    n.text.decode()
                    for n in node.child_by_field_name("body").named_children
                    if n.type == "expression_statement"
                ]

            def key(statement):
                match = re.match(r"hintTextTable\[(RHT_\w+)\]", statement)
                return match[1] if match else statement

            expected = [key(s) for s in steps(original)]
            for statement in steps(current):
                match = re.fullmatch(r"(ShipyardHint_" + label + r"_\d+)\(hintTextTable\);", statement)
                if match:
                    chunk = steps(helpers[match[1]])
                    sizes.append(len(chunk))
                    actual.extend(key(s) for s in chunk)
                else:
                    actual.append(key(statement))
            self.assertEqual(expected, actual, short)
            self.assertEqual(sizes, audit[short]["hint_chunks"], short)
            self.assertEqual(len(helpers), len(sizes), short)
            self.assertTrue(all(1 <= size <= 16 for size in sizes), short)

    def test_actual_location_and_hint_tables(self):
        a = content_host(False)
        b = content_host(True)
        self.assertEqual(a, b)
        stable(
            OUT / "content-verification.json",
            json.dumps(
                dict(
                    lines=len(a.splitlines()),
                    stdout_sha256=hashlib.sha256(a.encode()).hexdigest(),
                    runtime_services_executed=False,
                ),
                indent=2,
            )
            + "\n",
        )

    def test_all_execution_literal_bytes(self):
        a, count = literals_host(False)
        b, other = literals_host(True)
        self.assertEqual(count, other)
        self.assertEqual(a, b)
        stable(
            OUT / "literal-verification.json",
            json.dumps(dict(literals=count, stdout_sha256=hashlib.sha256(a.encode()).hexdigest()), indent=2) + "\n",
        )

    def test_all_enum_maps(self):
        a, count = enums_host(False)
        b, other = enums_host(True)
        self.assertEqual(count, other)
        self.assertEqual(a, b)
        stable(
            OUT / "enum-verification.json",
            json.dumps(
                dict(enum_types=count, lines=len(a.splitlines()), stdout_sha256=hashlib.sha256(a.encode()).hexdigest()),
                indent=2,
            )
            + "\n",
        )

    def test_actual_item_table_values(self):
        a, count, draws = items_host(False)
        b, other, projected_draws = items_host(True)
        self.assertEqual(count, other)
        self.assertEqual(a, b)
        self.assertEqual(draws, projected_draws)
        stable(
            OUT / "item-verification.json",
            json.dumps(
                dict(
                    item_assignments=count,
                    draw_callbacks_preserved=len(draws),
                    stdout_sha256=hashlib.sha256(a.encode()).hexdigest(),
                    runtime_services_executed=False,
                ),
                indent=2,
            )
            + "\n",
        )

    def test_repeatability(self):
        before = (OUT / "manifest.json").read_bytes()
        prepare()
        self.assertEqual(before, (OUT / "manifest.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
