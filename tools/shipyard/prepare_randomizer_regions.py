"""Hash-locked reachability graph for the native XDK frontend."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import inventory, lower_defaults, edits_apply
from prepare_randomizer_context import includes as context_includes
from prepare_randomizer_dungeons import includes as dungeon_includes
from prepare_randomizer_item import methods
from cpp_ast import PARSER, walk

BASE = "soh/soh/Enhancements/randomizer/"
OWN = ROOT / "platform/shipyard/randomizer-regions"
OUT = ROOT / "scratch/randomizer-regions-xdk"
UNITS = [BASE + "location_access.cpp"] + [
    p.relative_to(ROOT).as_posix()
    for p in sorted((ROOT / (BASE + "location_access")).rglob("*.cpp"))
]
PREFIX = """#include "resources/runtime_support.h"
#include "soh/Enhancements/randomizer/location_access.h"
#include "soh/Enhancements/randomizer/entrance.h"
#include "soh/Enhancements/randomizer/item.h"
#include "soh/Enhancements/randomizer/trial.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "libultraship/luslog.h"
#include <algorithm>
#include <cassert>
using namespace Rando;
#define SHIPYARD_EVENT_ACCESS(event, condition, fn) EventAccess(event, #event, fn, CleanConditionString(#condition))
#define SHIPYARD_LOCATION(check, condition, fn) LocationAccess(check, fn, CleanConditionString(#condition))
#define SHIPYARD_ENTRANCE(check, condition, fn, ...) Entrance(check, fn, CleanConditionString(#condition), ##__VA_ARGS__)
"""


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def arguments(n):
    a = n.child_by_field_name("arguments")
    raw = a.text
    commas = [c.start_byte - a.start_byte for c in a.children if c.type == ","]
    bounds = [0] + commas + [len(raw) - 1]
    return [raw[x + 1 : y].decode().strip() for x, y in zip(bounds, bounds[1:])]


class Lower:
    def __init__(self):
        self.helpers = []
        self.predicates = []
        self.containers = []
        self.serial = 0

    def name(self, kind):
        self.serial += 1
        return "ShipyardRegion" + kind + str(self.serial)

    def lambdas(self, text):
        raw = text.encode()
        edits = []

        def visit(n):
            if n.type == "call_expression" and n.child_by_field_name("function").text.startswith(
                b"SHIPYARD_"
            ):
                return
            if n.type == "lambda_expression":
                capture = next(c for c in n.named_children if c.type == "lambda_capture_specifier")
                if capture.text != b"[]":
                    return
                body = n.child_by_field_name("body").text.decode()
                name = self.name("Predicate")
                body = self.lambdas(body)
                self.helpers.append("static bool " + name + "() " + body + "\n")
                self.predicates.append(
                    dict(
                        name=name,
                        body=n.child_by_field_name("body").text.decode(),
                        kind="lambda",
                        original=n.text.decode(),
                    )
                )
                edits.append((n.start_byte, n.end_byte, name))
                return
            for child in n.named_children:
                visit(child)

        visit(PARSER.parse(raw).root_node)
        return edits_apply(raw, edits)

    def macros(self, text):
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "call_expression":
                continue
            fn = n.child_by_field_name("function").text.decode()
            if fn not in ("EVENT_ACCESS", "LOCATION", "ENTRANCE"):
                continue
            args = arguments(n)
            assert len(args) >= 2
            name = self.name("Predicate")
            body = "{ return " + args[1] + "; }"
            self.helpers.append("static bool " + name + "() " + self.lambdas(body) + "\n")
            self.predicates.append(dict(name=name, body=body, kind=fn, key=args[0]))
            edits.append(
                (
                    n.start_byte,
                    n.end_byte,
                    "SHIPYARD_" + fn + "(" + ", ".join(args[:2] + [name] + args[2:]) + ")",
                )
            )
        return edits_apply(raw, edits)

    def container(self, kind, body):
        if not re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", body[1:-1]).strip():
            return kind + "()"
        name = self.name("Container")
        elem = kind.split("<", 1)[1][:-1]
        self.helpers.append(
            "static "
            + kind
            + " "
            + name
            + "() { const "
            + elem
            + " values[] = "
            + body
            + "; return "
            + kind
            + "(values,values+sizeof(values)/sizeof(values[0])); }\n"
        )
        self.containers.append(dict(name=name, type=kind, source=body))
        return name + "()"

    def containers_in(self, text):
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type == "call_expression" and n.child_by_field_name("function").text == b"Region":
                args = n.child_by_field_name("arguments")
                parts = arguments(n)
                assert len(parts) in (5, 7), parts
                types = (
                    {
                        2: "std::vector<EventAccess>",
                        3: "std::vector<LocationAccess>",
                        4: "std::list<Rando::Entrance>",
                    }
                    if len(parts) == 5
                    else {
                        3: "std::set<RandomizerArea>",
                        4: "std::vector<EventAccess>",
                        5: "std::vector<LocationAccess>",
                        6: "std::list<Rando::Entrance>",
                    }
                )
                for i, t in types.items():
                    if parts[i].startswith("{"):
                        parts[i] = self.container(t, parts[i])
                edits.append((args.start_byte, args.end_byte, "(" + ", ".join(parts) + ")"))
            elif (
                n.type == "assignment_expression"
                and n.child_by_field_name("left").text == b"grottoEvents"
            ):
                value = n.child_by_field_name("right")
                assert value.type == "initializer_list"
                edits.append(
                    (
                        value.start_byte,
                        value.end_byte,
                        self.container("std::vector<EventAccess>", value.text.decode()),
                    )
                )
        return edits_apply(raw, edits)


def header(text):
    text = lower_defaults(text, inventory(text), [])
    text = once(text, "enum class EntranceType;", "struct EntranceType;")
    text = text.replace(
        '#include "soh/Enhancements/randomizer/dungeon.h"',
        '#include "soh/Enhancements/randomizer/dungeon.h"\n#include'
        ' "soh/Enhancements/randomizer/entrance.h"',
    )
    text = (
        "#include <cassert>\ninline bool ShipyardSpiritOtherFalse() { return false; }\ninline bool"
        " ShipyardSpiritThirdFalse() { return false; }\n"
        + text
    )
    for name in ("Other", "Third"):
        text = text.replace("[] { return false; }", "ShipyardSpirit" + name + "False", 1)
    assert "[] { return false; }" not in text
    return text


def project(name, text, defaults):
    lower = Lower()
    audit = []
    text = lower.macros(text)
    text = lower.lambdas(text)
    text = lower.containers_in(text)
    if name == BASE + "location_access.cpp":
        text = lower_defaults(text, defaults, audit)
        text = once(text, "Region::~Region() = default;", "Region::~Region() {}")
        text = once(
            text,
            '#include "soh/Enhancements/debugger/performanceTimer.h"',
            '#include "randomizer-logic/performance_calls.h"',
        )
        text = once(
            text, "[exitToRemove](const auto exit)", "[exitToRemove](const Rando::Entrance exit)"
        )
        text = text.replace("std::to_string(", "ShipyardRegionBoolString(")
        lower.helpers.insert(
            0, 'static std::string ShipyardRegionBoolString(bool b) { return b ? "1" : "0"; }\n'
        )
        text = re.sub(
            r"return \{\s*(RA_\w+)\s*\};",
            lambda m: "return "
            + lower.container("std::set<RandomizerArea>", "{" + m[1] + "}")
            + ";",
            text,
        )
        text = text.replace("return {};", "return std::set<RandomizerArea>();")
        text = once(
            text,
            "auto GetAllRegions()",
            "std::array<RandomizerRegion, RR_MAX - (RR_NONE + 1)> GetAllRegions()",
        )
        text = once(
            text,
            "std::vector<Rando::Entrance*> entrancesToShuffle = {};",
            "std::vector<Rando::Entrance*> entrancesToShuffle;",
        )
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "declaration" or b"Region::spiritLogicData =" not in n.text[:120]:
                continue
            init = next(c for c in n.named_children if c.type == "init_declarator")
            value = init.child_by_field_name("value")
            body = value.text.decode()
            fn = "ShipyardSpiritData"
            lower.helpers.append(
                "static std::map<RandomizerRegion, SpiritLogicData> "
                + fn
                + "() { struct Row { RandomizerRegion first; SpiritLogicData second; }; const Row"
                " values[] = "
                + body
                + "; std::map<RandomizerRegion,SpiritLogicData> result; for(size_t"
                " i=0;i<sizeof(values)/sizeof(values[0]);++i)"
                " result.insert(std::make_pair(values[i].first,values[i].second)); return"
                " result; }\n"
            )
            lower.containers.append(
                dict(name=fn, type="std::map<RandomizerRegion,SpiritLogicData>", source=body)
            )
            edits.append((value.start_byte, value.end_byte, fn + "()"))
        assert len(edits) == 1
        text = edits_apply(raw, edits)
    ranges = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))["lower_ranges"]
    text = ranges(text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end").decode()
    return PREFIX + "\n" + "".join(lower.helpers) + "\n" + text, dict(
        predicates=lower.predicates, containers=lower.containers, constructors=audit
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    outputs = {}
    audits = {}
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if sha(text) != digest:
            raise ValueError("Region source drift " + name)
        texts[name] = text

    def emit(name, t):
        stable(OUT / "generated" / name, t)
        outputs[name] = sha(t)

    defaults = inventory(texts[BASE + "location_access.h"])
    emit(BASE + "location_access.h", header(texts[BASE + "location_access.h"]))
    emit(
        BASE + "3drando/shops.hpp",
        texts[BASE + "3drando/shops.hpp"].replace(
            '#include "../SeedContext.h"', '#include "soh/Enhancements/randomizer/SeedContext.h"'
        ),
    )
    for name in UNITS:
        text, audit = project(name, texts[name], defaults)
        emit(name, text)
        audits[name] = audit
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_randomizer.py",
            "prepare_randomizer_item.py",
            "prepare_randomizer_context.py",
            "prepare_randomizer_dungeons.py",
            "prepare_archives.py",
            "prepare_configuration.py",
            "cpp_ast.py",
        )
    ] + [ROOT / "platform/shipyard/imgui/projection.py"]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                source_commit=lock["source_commit"],
                sources=lock["sources"],
                generated=outputs,
                audit=audits,
                defaults=defaults,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                helpers={
                    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in helpers
                },
            ),
            indent=2,
        )
        + "\n",
    )


def includes():
    return (
        [OUT / "generated/soh", OUT / "generated" / BASE, OUT / "generated/include"]
        + context_includes()
        + dungeon_includes()
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(p) for p in includes()]
    rows = []
    for name in UNITS:
        source = OUT / "generated" / name
        stem = name[len(BASE) :].replace("/", "_").replace(".cpp", "")
        obj = folder / (stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (stem + ".log"), result.stdout + result.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=result.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if result.returncode == 0:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print(
                "\n".join(s for s in (result.stdout + result.stderr).splitlines() if "error " in s)[
                    :3000
                ]
            )
        rows.append(row)
        print(stem + ": " + str(result.returncode))
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
