"""Complete pinned seed-generation translation units for the native XDK."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import inventory, lower_defaults, default_arguments, edits_apply
from prepare_randomizer_regions import includes as region_includes
from prepare_randomizer_settings import includes as settings_includes
from prepare_randomizer_item import methods
from prepare_custom_message import lower_literals
from cpp_ast import PARSER, walk

BASE = "soh/soh/Enhancements/randomizer/"
DIR = BASE + "3drando/"
OWN = ROOT / "platform/shipyard/randomizer-generation"
OUT = ROOT / "scratch/randomizer-generation-xdk"
NAMES = (
    "custom_messages fill hints item_pool menu playthrough rando_main shops spoiler_log"
    " starting_inventory".split()
)
HEADERS = (
    "fill hints item_pool menu playthrough rando_main starting_inventory pool_functions".split()
)
UNITS = [DIR + n + ".cpp" for n in NAMES]
SYNTAX = runpy.run_path(str(ROOT / "platform/shipyard/input/lowering.py"))["syntax"]
PREFIX = """#include "resources/runtime_support.h"
#include "input/compiler.h"
#include "randomizer-generation/support.h"
#include "soh/Enhancements/randomizer/location_access.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/Enhancements/randomizer/item.h"
#include "soh/Enhancements/randomizer/option.h"
#include "soh/Enhancements/randomizer/settings.h"
#include "soh/Enhancements/randomizer/trial.h"
#include "soh/ShipUtils.h"
#include "libultraship/luslog.h"
"""


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def kids(n):
    return [c for c in n.named_children if c.type != "comment"]


def scope(n):
    while n is not None:
        if n.type in ("function_definition", "lambda_expression"):
            return "&"
        n = n.parent
    return ""


def normalize_includes(text):
    def replace(m):
        path = m[1]
        if path.startswith("../"):
            target = Path(path).name
            if target == "CustomMessageManager.h":
                target = "soh/Enhancements/custom-message/" + target
            else:
                target = "soh/Enhancements/randomizer/" + target
            return '#include "' + target + '"'
        if "/" not in path and path.endswith(".hpp"):
            return '#include "soh/Enhancements/randomizer/3drando/' + path + '"'
        return m[0]

    return re.sub(r'#include "([^"]+)"', replace, text)


class Lists:
    def __init__(self):
        self.audit = []
        self.helpers = []

    def value(self, typ, node, visit=None):
        visit = visit or (lambda n: n.text.decode())
        vals = kids(node)
        capture = scope(node)
        self.audit.append(dict(type=typ, source=node.text.decode(), rows=len(vals)))
        if not vals:
            return typ + "()"
        if typ.startswith(("std::vector<", "std::set<")):
            elem = typ.split("<", 1)[1][:-1]
            vals = [visit(v) for v in vals]
            if typ.startswith("std::vector<") and len(vals) == 1:
                return typ + "(1, " + elem + "(" + vals[0] + "))"
            body = (
                "{ typedef "
                + elem
                + " Element; const Element values[] = {"
                + ", ".join(vals)
                + "}; return "
                + typ
                + "(values,values+sizeof(values)/sizeof(values[0])); }"
            )
            if "std::function<" in elem:
                # XDK /O2 drops nine of the twelve converting pair/lambda array
                # initializers in conditionalAlwaysHints, then copies all twelve.
                # Named elements and ordered insertion preserve every callable
                # without that defective nontrivial aggregate initialization.
                body = (
                    "{ typedef "
                    + elem
                    + " Element; "
                    + typ
                    + " result; result.reserve("
                    + str(len(vals))
                    + "); "
                )
                for index, value in enumerate(vals):
                    body += (
                        "const Element element"
                        + str(index)
                        + "("
                        + value
                        + "); result.push_back(element"
                        + str(index)
                        + "); "
                    )
                body += "return result; }"
            if not capture:
                name = "GenerationList" + str(len(self.audit))
                self.helpers.append("static " + typ + " " + name + "() " + body + "\n")
                return name + "()"
            return "([" + capture + "]() -> " + typ + " " + body + "())"
        if typ.startswith("std::map<"):
            code = ""
            for row in vals:
                fields = kids(row)
                assert len(fields) == 2
                code += "result.insert(std::make_pair(" + ",".join(visit(f) for f in fields) + "));"
            return (
                "(["
                + capture
                + "]() -> "
                + typ
                + " { "
                + typ
                + " result; "
                + code
                + "return result; }())"
            )
        raise ValueError(typ)

    def run(self, text):
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "declaration":
                continue
            typ = n.child_by_field_name("type")
            init = n.child_by_field_name("declarator")
            if not typ or not init or init.type != "init_declarator":
                continue
            value = init.child_by_field_name("value")
            if not value or value.type != "initializer_list":
                continue
            t = typ.text.decode()
            if t.startswith(("std::vector<", "std::set<", "std::map<")):
                v = self.value(t, value)
                if self.helpers:
                    edits.append((n.start_byte, n.start_byte, "".join(self.helpers)))
                    self.helpers = []
                if not any(c.type == "=" for c in init.children):
                    v = "= " + v
                edits.append((value.start_byte, value.end_byte, v))
            elif t == "PriceSettingsStruct":
                edits.append(
                    (
                        value.start_byte,
                        value.end_byte,
                        t + "(" + ", ".join(c.text.decode() for c in kids(value)) + ")",
                    )
                )
        return edits_apply(raw, edits)

    def calls(self, text):
        # Parameter types come from the full actual local declarations. Hint's
        # overloads are disambiguated by their upstream argument positions.
        raw = text.encode()
        types = {
            "ReachabilitySearch": ["std::vector<RandomizerCheck>"],
            "IsReachableWithout": ["std::vector<RandomizerCheck>"],
        }
        edits = []
        for n in methods(text):
            d = n.child_by_field_name("declarator")
            p = d.child_by_field_name("parameters")
            if p is not None:
                types[d.child_by_field_name("declarator").text.decode()] = [
                    c.child_by_field_name("type").text.decode()
                    for c in kids(p)
                    if c.child_by_field_name("type")
                ]
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "call_expression":
                continue
            f = n.child_by_field_name("function").text.decode()
            args = kids(n.child_by_field_name("arguments"))
            if f == "json::object":
                continue
            for index, arg in enumerate(args):
                if arg.type != "initializer_list":
                    continue
                if f.startswith("std::max"):
                    assert len(args) == 1 and len(kids(arg)) == 2
                    edits.append(
                        (
                            arg.start_byte,
                            arg.end_byte,
                            ", ".join(c.text.decode() for c in kids(arg)),
                        )
                    )
                    continue
                if f == "Hint":
                    # Every braced Hint call in this unit selects the HintType
                    # overload (no distribution string in argument position 2).
                    offset = 1 if args[2].type == "string_literal" else 0
                    t = {
                        2: "std::vector<RandomizerHintTextKey>",
                        3: "std::vector<RandomizerCheck>",
                        4: "std::vector<RandomizerArea>",
                        5: "std::vector<TrialKey>",
                    }[index - offset]
                else:
                    if f not in types:
                        raise ValueError("Unaudited braced call " + f + ": " + arg.text.decode())
                    t = types[f][index]
                edits.append((arg.start_byte, arg.end_byte, self.value(t, arg)))
        assert not self.helpers
        return edits_apply(raw, edits)


def header(name, text):
    text = normalize_includes(text)
    text = seed_set_references(name, text)
    if name == "hints":
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type not in ("class_specifier", "struct_specifier"):
                continue
            ident = n.child_by_field_name("name")
            if ident and ident.text in (b"HintText", b"StaticHintInfo"):
                edits.append(
                    (
                        n.start_byte,
                        n.end_byte + 1,
                        '#include "soh/Enhancements/randomizer/3drando/'
                        + ident.text.decode()
                        + '.h"',
                    )
                )
        assert len(edits) == 2
        text = edits_apply(raw, edits).replace(
            "#include <variant>", "// Canonical StaticHintInfo owns the variant definition."
        )
    if name == "fill":
        text = lower_defaults(text, inventory(text), [])
        text = once(text, "regionPool = { RR_ROOT };", "regionPool.assign(1, RR_ROOT);")
    if name == "pool_functions":
        # The named operands of the original fold are lvalues. XDK overloads
        # preserve forwarding-reference deduction and left-to-right || order.
        start = text.index("template <typename First, typename... T>")
        original = text[start:]
        overloads = []
        for count in range(17):
            types = ["typename First"] + ["typename T" + str(i) for i in range(count)]
            args = ["First&& first"] + ["T" + str(i) + "&& t" + str(i) for i in range(count)]
            overloads.append(
                "template <"
                + ", ".join(types)
                + "> bool IsAnyOf("
                + ", ".join(args)
                + ") { return "
                + (" || ".join("(first == t" + str(i) + ")" for i in range(count)) or "false")
                + "; }"
            )
        text = (
            text[:start]
            + "#ifdef _XBOX\n"
            + "\n".join(overloads)
            + "\n#else\n"
            + original
            + "\n#endif\n"
        )
        text = (
            text.replace("begin(vector)", "vector.begin()")
            .replace("end(vector)", "vector.end()")
            .replace("std::cbegin(fromPool)", "Shipyard::Resources::begin(fromPool)")
            .replace("std::cend(fromPool)", "Shipyard::Resources::end(fromPool)")
            .replace("std::vector<T> filteredPool = {};", "std::vector<T> filteredPool;")
        )
    return '#include "resources/runtime_support.h"\n' + SYNTAX(default_arguments(text), set())


def seed_set_references(name, text):
    expected = {"menu": 1, "playthrough": 2, "rando_main": 1}.get(name, 0)
    if not expected:
        return text
    for value in ("RandomizerCheck> excludedLocations", "RandomizerTrick> enabledTricks"):
        old = "std::set<" + value
        if text.count(old) != expected:
            raise ValueError("Seed set signature drift: " + name)
        text = text.replace(old, "const std::set<" + value.replace("> ", ">& ", 1))
    return text


def project(name, text):
    text = normalize_includes(text)
    lists = Lists()
    audit = {}
    text = seed_set_references(name, text)
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "lambda_expression":
            continue
        decl = n.child_by_field_name("declarator")
        body = n.child_by_field_name("body")
        if decl is not None and any(c.type == "trailing_return_type" for c in decl.named_children):
            continue
        edits.append((body.start_byte, body.start_byte, " -> bool "))
    text = edits_apply(raw, edits)
    text = (
        text.replace("std::variant<bool, uint8_t>", "xbox_compat::variant<bool, uint8_t>")
        .replace("std::holds_alternative<", "xbox_compat::holds_alternative<")
        .replace("std::get<", "xbox_compat::get<")
    )
    text = (
        text.replace("(const auto loc)", "(const RandomizerCheck loc)")
        .replace("(const auto i)", "(const RandomizerGet i)")
        .replace("(const auto item)", "(const RandomizerGet item)")
    )
    text = text.replace(
        "using namespace std::literals::string_literals;",
        "// String suffixes preserve their exact byte length.",
    )
    if name == "hints":
        # Aggregate HintSetting rows keep their original designated-field order.
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if (
                n.type != "init_declarator"
                or n.child_by_field_name("declarator").text != b"hintSettingTable"
            ):
                continue
            value = n.child_by_field_name("value")
            rows = kids(kids(value)[0])
            out = []
            for row in rows:
                fields = kids(row)
                assert [f.child_by_field_name("designator").text for f in fields] == [
                    b".alwaysCopies",
                    b".trialCopies",
                    b".junkWeight",
                    b".distTable",
                ]
                vals = [f.child_by_field_name("value") for f in fields]
                dist = lists.value(
                    "std::vector<HintDistributionSetting>",
                    vals[3],
                    lambda v: "HintDistributionSetting("
                    + ", ".join(c.text.decode() for c in kids(v))
                    + ")",
                )
                out.append("{" + ", ".join(v.text.decode() for v in vals[:3]) + ", " + dist + "}")
            replacement = "= {{" + ", ".join(out) + "}}"
            edits.append((value.start_byte, value.end_byte, replacement))
            edits.append((n.parent.start_byte, n.parent.start_byte, "".join(lists.helpers)))
            lists.helpers = []
        assert len(edits) == 2
        text = edits_apply(raw, edits)
    text = lists.calls(text)
    text = lists.run(text)
    if name == "fill":
        text = once(
            text, "std::vector rewardLocations(", "std::vector<RandomizerCheck> rewardLocations("
        )
        text = once(
            text, "areas.merge(otherAreas);", "Shipyard::Generation::Merge(areas, otherAreas);"
        )
    if name == "item_pool":
        text = text.replace("std::erase(", "Shipyard::Generation::Erase(")
    if name == "playthrough":
        text = once(
            text,
            "#include <libultraship/libultraship.h>",
            "#include <libultraship/bridge/consolevariablebridge.h>\n#include <spdlog/spdlog.h>",
        )
    if name == "rando_main":
        text = "#include <ship/window/Window.h>\n#include <ship/window/gui/Gui.h>\n" + text
    if name == "shops":
        text = text.replace("static constexpr ", "static const ")
    if name == "hints":
        text = once(
            text,
            "SPDLOG_DEBUG(Rando::StaticData::GetLocation(loc)->GetName());",
            "SPDLOG_DEBUG(spdlog::string_view_t(Rando::StaticData::GetLocation(loc)->GetName()));",
        )
    if name == "spoiler_log":
        text = "#include <iomanip>\n" + text
        text = once(
            text,
            'jsonData["fileType"] = FILE_TYPE_SPOILER;',
            'jsonData["fileType"] = static_cast<int>(FILE_TYPE_SPOILER);',
        )
        text = once(
            text,
            "#include <filesystem>",
            '#include "filesystem/filesystem.h"\n#include <nonstd/string_view.hpp>',
        )
        text = (
            text.replace("std::filesystem::", "xbox_compat::filesystem::")
            .replace("using json = nlohmann::ordered_json;", "typedef nlohmann::ordered_json json;")
            .replace("static auto Get", "static const char* Get")
        )
        text = text.replace("std::string_view", "nonstd::string_view").replace(
            "placementtxt += msg;", "placementtxt.append(msg.data(),msg.size());"
        )
        text = once(
            text,
            "hintedLocations.emplace(Rando::StaticData::GetLocation(key)->GetHintKey(), location);",
            "hintedLocations.insert(std::make_pair(Rando::StaticData::GetLocation(key)->GetHintKey(),"
            " location));",
        )
        text = once(
            text,
            '(std::string("Randomizer/") + fileName + std::string(".json")).c_str()));',
            '(std::string("Randomizer/") + fileName + std::string(".json")).c_str()).c_str());',
        )
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if (
                n.type != "call_expression"
                or n.child_by_field_name("function").text != b"json::object"
            ):
                continue
            args = kids(n.child_by_field_name("arguments"))
            if not args:
                continue
            assert len(args) == 1 and args[0].type == "initializer_list"
            code = "([&]() -> json { json result=json::object(); "
            for row in kids(args[0]):
                key, value = kids(row)
                v = value.text.decode()
                if key.text == b'"type"':
                    v += " .GetValue()"
                code += "result[" + key.text.decode() + "] = " + v + "; "
            code += "return result; }())"
            edits.append((n.start_byte, n.end_byte, code))
        assert len(edits) == 2
        text = edits_apply(raw, edits)
    text = default_arguments(text)
    text = SYNTAX(text, set())
    text = text.replace("ShipyardInputCompiler::ToString(", "Shipyard::Generation::Decimal(")
    text, literals = lower_literals(text)
    return PREFIX + text, dict(lists=lists.audit, literals=literals)


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    generated = {}
    audits = {}
    for name, digest in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(t) != digest:
            raise ValueError("Seed generation source drift " + name)
        texts[name] = t

    def emit(name, text):
        stable(OUT / "generated" / name, text)
        generated[name] = sha(text)

    for name in HEADERS:
        emit(DIR + name + ".hpp", header(name, texts[DIR + name + ".hpp"]))
    for name in NAMES:
        text, audit = project(name, texts[DIR + name + ".cpp"])
        emit(DIR + name + ".cpp", text)
        audits[name] = audit
    emit("include/randomizer-generation/support.h", (OWN / "support.h").read_text())
    canonical = {
        "HintText": "scratch/randomizer-item-xdk/generated/" + DIR + "HintText.h",
        "StaticHintInfo": "scratch/randomizer-hints-xdk/generated/" + DIR + "StaticHintInfo.h",
        "Context": "scratch/randomizer-context-xdk/generated/" + BASE + "SeedContext.h",
        "Region": "scratch/randomizer-regions-xdk/generated/" + BASE + "location_access.h",
        "Entrance": "scratch/save-manager-xdk/generated/" + BASE + "entrance.h",
    }
    # Context's full declaration may be canonical in the earlier foundation.
    if not (ROOT / canonical["Context"]).exists():
        canonical["Context"] = "scratch/randomizer-xdk/generated/" + BASE + "SeedContext.h"
    for provider in ("randomizer-item", "randomizer-hints"):
        prior = json.loads((ROOT / ("scratch/" + provider + "-xdk/manifest.json")).read_text())
        assert prior["sources"][DIR + "hints.hpp"] == lock["sources"][DIR + "hints.hpp"]
    for label, logical in {
        "Settings": "soh/Enhancements/randomizer/settings.h",
        "Hint": "soh/Enhancements/randomizer/hint.h",
        "StaticData": "soh/Enhancements/randomizer/static_data.h",
        "PerformanceTimer": "soh/Enhancements/debugger/performanceTimer.h",
        "Random": "soh/Enhancements/randomizer/3drando/random.hpp",
    }.items():
        found = next(p / logical for p in includes() if (p / logical).exists())
        canonical[label] = found.relative_to(ROOT).as_posix()
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_randomizer.py",
            "prepare_randomizer_regions.py",
            "prepare_randomizer_settings.py",
            "prepare_randomizer_item.py",
            "prepare_custom_message.py",
            "prepare_archives.py",
            "prepare_configuration.py",
            "cpp_ast.py",
        )
    ] + [
        ROOT / "platform/shipyard/input/lowering.py",
        ROOT / "platform/shipyard/imgui/projection.py",
        OWN / "support.h",
    ]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                generated=generated,
                audit=audits,
                constructor_defaults=inventory(texts[DIR + "fill.hpp"]),
                canonical_headers={
                    n: dict(path=p, sha256=hashlib.sha256((ROOT / p).read_bytes()).hexdigest())
                    for n, p in canonical.items()
                },
                helpers={
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in helpers
                },
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    roots = [
        OUT / "generated/soh",
        OUT / "generated" / DIR,
        OUT / "generated/include",
        ROOT / "scratch/application-windows-xdk/generated/soh",
        ROOT / "scratch/randomizer-hints-xdk/generated/soh",
        ROOT / "scratch/randomizer-hints-xdk/generated" / BASE,
    ]
    return (
        roots
        + [
            ROOT / "scratch/randomizer-content-xdk/generated/soh",
            ROOT / "scratch/randomizer-content-xdk/generated/include",
        ]
        + region_includes()
        + settings_includes()
    )


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
    probe = folder / "declarations.cpp"
    stable(
        probe,
        (
            '#include "soh/Enhancements/randomizer/3drando/hints.hpp"\n'
            '#include "soh/Enhancements/randomizer/3drando/fill.hpp"\n'
            '#include "soh/Enhancements/randomizer/3drando/pool_functions.hpp"\n'
            'extern "C" const unsigned long GenerationABI[]={sizeof(GetAccessibleLocationsStr'
            'uct),sizeof(HintDistributionSetting),sizeof(HintSetting),sizeof(StaticHintInfo)}'
            ';\n'
            'bool GenerationTemplateProbe(){int a=1;const int b=2;GetAccessibleLocationsStruc'
            't state(100);return IsAnyOf(a,b,1)&&!IsAnyOf(a)&&!state.calculatingAvailableChec'
            'ks;}\n'
        ),
    )
    for source in [OUT / "generated" / name for name in UNITS] + [probe]:
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=r.returncode,
            production=source != probe,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print(
                "\n".join(s for s in (r.stdout + r.stderr).splitlines() if "error " in s)[:9000],
                flush=True,
            )
        rows.append(row)
        print(source.stem + ": " + str(r.returncode), flush=True)
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
