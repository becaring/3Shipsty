"""Pinned seed, location, fish and collectibles runtime sources for XDK."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import lower_defaults, edits_apply, inventory as base_inventory
from prepare_randomizer_item import methods
from prepare_save_manager import includes as save_includes
from prepare_game_interactor import call_sites
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-context"
OUT = ROOT / "scratch/randomizer-context-xdk"
BASE = "soh/soh/Enhancements/randomizer/"
KALEIDO = "soh/soh/Enhancements/kaleido"
TABLE = "soh/soh/Enhancements/item-tables/ItemTableManager"
UNITS = [
    BASE + "SeedContext.cpp",
    BASE + "item_location.cpp",
    BASE + "fishsanity.cpp",
    KALEIDO + ".cpp",
    TABLE + ".cpp",
]
SYNTAX = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))["syntax"]
PREFIX = (
    '#include "input/compiler.h"\n#include "resources/runtime_support.h"\n#include'
    ' "soh/Enhancements/randomizer/static_data.h"\n#include'
    ' "soh/Enhancements/randomizer/item.h"\n#include'
    ' "soh/Enhancements/randomizer/randomizer.h"\n#include'
    ' "soh/Enhancements/randomizer/SeedContext.h"\n#include <cassert>\n'
)


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def inventory(text):
    # Ignore pure virtual '= 0' declarations; they are not member initializers.
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "field_declaration":
            continue
        decl = n.child_by_field_name("declarator")
        if decl is not None and decl.type == "function_declarator":
            edits.append((n.start_byte, n.end_byte, ""))
    return base_inventory(edits_apply(raw, edits))


def context(text, header):
    text = lower_defaults(text, base_inventory(header), [])
    text = once(
        text,
        '#include "3drando/hints.hpp"',
        "// Actual declarations from hints.hpp and its location_access.h dependency.\nextern"
        " Rando::Context* ctx;\nvoid CreateStaticHints();",
    )
    text = once(text, '#include "settings.h"', '#include "soh/Enhancements/randomizer/settings.h"')
    text = once(text, '#include "../kaleido.h"', '#include "soh/Enhancements/kaleido.h"')
    text = '#include "soh/Enhancements/randomizer/trial.h"\n' + text
    text = "#include <algorithm>\n" + text
    text = once(
        text, "[ctx, countShops](const auto loc)", "[ctx, countShops](const RandomizerCheck loc)"
    )
    text = once(text, "return count_if(", "return std::count_if(")
    match = re.search(r"VanillaLogicDefaults = (\{[\s\S]*?\});", text)
    assert match
    text = (
        text[: match.start()]
        + "OptionValue* const vanillaDefaults[] = "
        + match[1]
        + ";\n   "
        " VanillaLogicDefaults.assign(vanillaDefaults,vanillaDefaults+sizeof(vanillaDefaults)/sizeof(vanillaDefaults[0]));"
        + text[match.end() :]
    )
    for key in ("locKey", "static_cast<RandomizerCheck>(locKey)"):
        text = once(
            text,
            "overrides.emplace(" + key + ", ItemOverride());",
            "overrides.insert(std::make_pair(" + key + ", ItemOverride()));",
        )
    text = once(
        text,
        "std::ifstream spoilerFileStream(SohUtils::Sanitize(spoilerFileName));",
        "std::ifstream spoilerFileStream(SohUtils::Sanitize(spoilerFileName).c_str());",
    )
    for key in ("Gossip Stone Hints", "Static Hints"):
        container = 'spoilerFileJson["' + key + '"]'
        text = once(
            text,
            "for (auto hintData : " + container + ".items())",
            "for (nlohmann::json::iterator hintData = "
            + container
            + ".begin(); hintData != "
            + container
            + ".end(); ++hintData)",
        )
    text = once(
        text,
        "settings->GetRandomizerTrickByName(it)",
        "settings->GetRandomizerTrickByName(it.get<std::string>())",
    )
    text = once(text, "return {};", "return nlohmann::json();")
    return text


def fish(text):
    text = once(text, '#include "../../OTRGlobals.h"', '#include "soh/OTRGlobals.h"')
    text = once(text, '#include "draw.h"', '#include "soh/Enhancements/randomizer/draw.h"')
    text = once(
        text, '#include "3drando/pool_functions.hpp"', '#include "randomizer-context/pool_filter.h"'
    )
    text = once(text, "FishsanityPondOptions options{};", "FishsanityPondOptions options = {};")
    text = once(
        text,
        "randoItem = GET_ITEM_MYSTERY;",
        "{ const GetItemEntry mystery = GET_ITEM_MYSTERY; randoItem = mystery; }",
    )
    # XDK cannot implicitly materialize std::string for an rvalue-reference parameter.
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "call_expression" or n.child_by_field_name("function").text not in (
            b"Location::Fish",
            b"Location::GrottoFish",
        ):
            continue
        for arg in n.child_by_field_name("arguments").named_children:
            if arg.type == "string_literal":
                edits.append(
                    (arg.start_byte, arg.end_byte, "std::string(" + arg.text.decode() + ")")
                )
    text = edits_apply(raw, edits)
    text = '#include "game-interactor/varargs.h"\n#include "soh/ShipInit.hpp"\n' + text
    text = once(
        text,
        'static RegisterShipInitFunc registerShuffleFish(RegisterShuffleFish, { "IS_RANDO" });',
        'static const std::string fishUpdatePaths[] = { "IS_RANDO" };\nstatic RegisterShipInitFunc'
        " registerShuffleFish(RegisterShuffleFish,"
        " std::set<std::string>(fishUpdatePaths,fishUpdatePaths+1));",
    )
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "structured_binding_declarator":
            continue
        names = [c.text.decode() for c in n.named_children]
        assert len(names) == 3
        init = n.parent
        decl = init.parent
        value = init.child_by_field_name("value")
        assert value.text.startswith(b"GetOptions(")
        replacement = (
            "FishsanityPondOptions _fishOptions = "
            + value.text.decode()
            + "; "
            + "".join(
                "auto& " + name + " = _fishOptions." + field + "; "
                for name, field in zip(names, ("mode", "numFish", "ageSplit"))
            )
        )
        edits.append((decl.start_byte, decl.end_byte, replacement))
    assert len(edits) == 7
    text = edits_apply(raw, edits)
    text = once(
        text,
        "return { OTRGlobals::Instance->gRandomizer->GetRandomizerInfFromCheck(rc), rc };",
        "CheckIdentity identity = {"
        " OTRGlobals::Instance->gRandomizer->GetRandomizerInfFromCheck(rc), rc }; return identity;",
    )
    # Preserve the pair array's order and all enum values, with aggregate rows.
    m = re.search(
        r"(std::array<std::pair<RandomizerCheck, RandomizerCheck>, 17>)"
        r" (Rando::StaticData::randomizerFishingPondFish) = (\{[\s\S]*?\n\});",
        text,
    )
    assert m
    rows = re.findall(r"\{\s*(RC_\w+),\s*(RC_\w+)\s*\}", m[3])
    assert len(rows) == 17
    code = (
        "static "
        + m[1]
        + " ShipyardPondChecks() { const RandomizerCheck rows[][2] = {"
        + ",".join("{" + a + "," + b + "}" for a, b in rows)
        + "}; "
        + m[1]
        + " result; for(size_t i=0;i<17;++i) result[i]=std::make_pair(rows[i][0],rows[i][1]);"
        " return result; }\n"
        + m[1]
        + " "
        + m[2]
        + " = ShipyardPondChecks();"
    )
    text = text[: m.start()] + code + text[m.end() :]
    m = re.search(
        r"(std::unordered_map<int8_t, RandomizerCheck>)"
        r" (Rando::StaticData::randomizerGrottoFishMap) = (\{[\s\S]*?\n\});",
        text,
    )
    assert m
    code = (
        "static "
        + m[1]
        + " ShipyardGrottoChecks() { struct Row { int8_t first; RandomizerCheck second; }; const"
        " Row rows[]="
        + m[3]
        + "; "
        + m[1]
        + " result; for(size_t i=0;i<sizeof(rows)/sizeof(rows[0]);++i)"
        " result.insert(std::make_pair(rows[i].first,rows[i].second)); return result; }\n"
        + m[1]
        + " "
        + m[2]
        + " = ShipyardGrottoChecks();"
    )
    return text[: m.start()] + code + text[m.end() :]


def kaleido(text, header):
    text = lower_defaults(text, inventory(header), [])
    text = once(text, '#include "kaleido.h"', '#include "soh/Enhancements/kaleido.h"')
    text = re.sub(r"Color_RGBA8\{([^{}]+)\}", r"ShipyardRGBA(\1)", text)
    text = re.sub(
        r"(textColor|aButtonColor|mButtonColors\[\d\]) = \{([^{}]+)\};",
        lambda m: m[1]
        + " = "
        + ("ShipyardRGB" if m[2].count(",") == 2 else "ShipyardRGBA")
        + "("
        + m[2]
        + ");",
        text,
    )
    text = '#include "randomizer-context/colors.h"\n' + text
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "call_expression":
            continue
        fn = n.child_by_field_name("function")
        args = n.child_by_field_name("arguments").named_children
        if (
            not fn.text.endswith(b"push_back")
            or len(args) != 1
            or not args[0].text.startswith(b"gs")
        ):
            continue
        assert n.parent.type == "expression_statement"
        expr = fn.text.decode() + "(_gfx);"
        edits.append(
            (
                n.parent.start_byte,
                n.parent.end_byte,
                "{ const Gfx _gfx = " + args[0].text.decode() + "; " + expr + " }",
            )
        )
    text = edits_apply(raw, edits)
    return text


def kaleido_header(header):
    raw = header.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "field_declaration":
            continue
        decl = n.child_by_field_name("declarator")
        value = n.child_by_field_name("default_value")
        if decl is not None and decl.type == "function_declarator" and value is not None:
            assert value.text == b"0"
            eq = next(c for c in n.children if c.type == "=")
            edits.append((eq.start_byte, value.end_byte, "/*SHIPYARD_PURE_VIRTUAL*/"))
    assert len(edits) == 2
    result = lower_defaults(edits_apply(raw, edits), inventory(header), [])
    return SYNTAX(result, set()).replace("/*SHIPYARD_PURE_VIRTUAL*/", "= 0")


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    generated = {}
    for name, digest in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(t) != digest:
            raise ValueError("Runtime source drift: " + name)
        texts[name] = t

    def emit(name, t):
        stable(OUT / "generated" / name, t)
        generated[name] = sha(t)

    for name in UNITS:
        text = call_sites(texts[name], name)
        if name == BASE + "SeedContext.cpp":
            text = context(text, texts[BASE + "SeedContext.h"])
            hash_header = texts[BASE + "rando_hash.h"]
            declaration = re.search(
                r"inline std::array<Sprite, 100> gSeedTextures = [\s\S]*?\n\} \};", hash_header
            )
            assert declaration
            definition = declaration[0].replace("inline ", "", 1)
            emit(
                BASE + "rando_hash.h",
                hash_header[: declaration.start()]
                + "extern std::array<Sprite, 100> gSeedTextures;"
                + hash_header[declaration.end() :],
            )
            text = once(text, "namespace Rando {", definition + "\nnamespace Rando {")
        elif name == BASE + "item_location.cpp":
            text = lower_defaults(text, inventory(texts[BASE + "item_location.h"]), [])
            text = once(
                text, "areas.merge(newAreas);", "areas.insert(newAreas.begin(), newAreas.end());"
            )
            for field in ("areas", "hintedBy"):
                text = once(text, field + " = {};", field + ".clear();")
            text = once(
                text,
                "SPDLOG_DEBUG(Rando::StaticData::GetLocation(rc)->GetName());",
                "SPDLOG_DEBUG(spdlog::string_view_t(Rando::StaticData::GetLocation(rc)->GetName()));",
            )
            text = (
                "#include <spdlog/spdlog.h>\n#include"
                ' "soh/Enhancements/game-interactor/GameInteractor.h"\n#include'
                ' "soh/Enhancements/randomizer/3drando/random.hpp"\n'
                + text
            )
        elif name == BASE + "fishsanity.cpp":
            text = fish(text)
        elif name == KALEIDO + ".cpp":
            text = kaleido(text, texts[KALEIDO + ".h"])
        elif name == TABLE + ".cpp":
            text = once(
                text,
                '#include "ItemTableManager.h"',
                '#include "soh/Enhancements/item-tables/ItemTableManager.h"',
            )
            text = once(
                text,
                "itemTables.emplace(tableID, newItemTable)",
                "itemTables.insert(std::make_pair(tableID, newItemTable))",
            )
            text = once(
                text,
                "itemTable->emplace(getItemID, getItemEntry)",
                "itemTable->insert(std::make_pair(getItemID, getItemEntry))",
            )
            text = once(
                text,
                "return GET_ITEM_NONE;",
                "const GetItemEntry none = GET_ITEM_NONE; return none;",
            )
        text = PREFIX + text
        text = (
            text.replace("std::cbegin(", "Shipyard::Resources::begin(")
            .replace("std::cend(", "Shipyard::Resources::end(")
            .replace("std::begin(", "Shipyard::Resources::begin(")
            .replace("std::end(", "Shipyard::Resources::end(")
        )
        emit(name, SYNTAX(text, set()))
    header = texts[KALEIDO + ".h"]
    emit(KALEIDO + ".h", kaleido_header(header))
    emit(
        BASE + "fishsanity.h",
        texts[BASE + "fishsanity.h"].replace(
            '#include "randomizerTypes.h"',
            '#include "soh/Enhancements/randomizer/randomizerTypes.h"',
        ),
    )
    # These pool templates are used by this batch; IsAnyOf is not instantiated.
    pool = texts[BASE + "3drando/pool_functions.hpp"]
    pool = pool[: pool.index("template <typename First, typename... T>")]
    pool = once(pool, "std::vector<T> filteredPool = {};", "std::vector<T> filteredPool;")
    pool = pool.replace("std::cbegin(", "Shipyard::Resources::begin(").replace(
        "std::cend(", "Shipyard::Resources::end("
    )
    pool = pool.replace("begin(vector)", "Shipyard::Resources::begin(vector)").replace(
        "end(vector)", "Shipyard::Resources::end(vector)"
    )
    emit("include/randomizer-context/pool_filter.h", pool)
    stale = OUT / "generated" / (BASE + "3drando/pool_functions.hpp")
    if stale.exists():
        stale.unlink()
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_randomizer.py",
            "prepare_randomizer_item.py",
            "prepare_save_manager.py",
            "prepare_game_interactor.py",
            "prepare_archives.py",
            "prepare_configuration.py",
            "cpp_ast.py",
        )
    ] + [
        ROOT / "platform/shipyard/input/lowering.py",
        ROOT / "platform/shipyard/imgui/projection.py",
        OWN / "colors.h",
    ]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated=generated,
                full_units=UNITS,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helper_sha256={
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in helpers
                },
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return [
        OUT / "generated/soh",
        OUT / "generated" / BASE,
        OUT / "generated/include",
        ROOT / "platform/shipyard",
    ] + save_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    roots = list(dict.fromkeys(includes() + [Path(f[2:]) for f in flags if f.startswith("/I")]))
    roots.sort(
        key=lambda p: (
            2
            if p.is_relative_to(ROOT / "soh")
            else 1 if p.is_relative_to(ROOT / "scratch/game-xdk") else 0
        )
    )
    flags = [f for f in flags if not f.startswith("/I")]
    flags[1:1] = ["/I" + str(p) for p in roots]
    rows = []
    for name in UNITS:
        source = OUT / "generated" / name
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=r.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print("\n".join(s for s in (r.stdout + r.stderr).splitlines() if "error " in s)[:8500])
        rows.append(row)
        print(source.stem + ": " + str(r.returncode))
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
