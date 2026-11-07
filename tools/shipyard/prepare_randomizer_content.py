"""Pinned randomizer content tables, compiled with the XDK compiler."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_custom_message import lower_literals
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-content"
OUT = ROOT / "scratch/randomizer-content-xdk"
BASE = "soh/soh/Enhancements/randomizer/"
UNITS = [
    "item_list.cpp",
    "location_list.cpp",
    "item_category_adj.cpp",
    "randomizerEnumStrings.cpp",
    "randomizer_check_objects.cpp",
    "tricks.cpp",
    "3drando/hint_list.cpp",
] + [
    "3drando/hint_list/hint_list_" + n + ".cpp"
    for n in ["exclude_dungeon", "exclude_overworld", "item"]
]


def kids(n):
    return [c for c in n.named_children if c.type != "comment"]


def expressions(text):
    raw = text.encode()
    count = [0]

    def vector(n, t):
        values = kids(n)
        count[0] += 1
        if not values:
            return "std::vector<" + t + ">()"
        return (
            "Shipyard::RandomizerContent::Values<"
            + t
            + ">("
            + str(len(values))
            + ")"
            + "".join(".Add(" + visit(v) + ")" for v in values)
            + ".Finish()"
        )

    def visit(n):
        if (
            n.type == "compound_literal_expression"
            and n.child_by_field_name("type").text == b"Text"
        ):
            count[0] += 1
            return "Text(" + ", ".join(visit(c) for c in kids(n.child_by_field_name("value"))) + ")"
        if n.type == "call_expression":
            func = n.child_by_field_name("function")
            args = n.child_by_field_name("arguments")
            f = func.text.decode()
            values = kids(args)
            if f in ["Item", "HintText", "CustomMessage"] or f.startswith("Location::"):
                result = []
                for i, a in enumerate(values):
                    if a.type == "initializer_list":
                        if f == "Item":
                            assert i in (8, 15), (i, n.text[:90])
                            result.append("Text(" + ", ".join(visit(c) for c in kids(a)) + ")")
                        elif f == "HintText":
                            assert i in (1, 2), (i, n.text[:90])
                            result.append(vector(a, "CustomMessage"))
                        elif f == "CustomMessage":
                            assert i in (1, 2, 3, 4), (i, n.text[:90])
                            result.append(vector(a, "bool" if i in (2, 4) else "std::string"))
                        else:
                            raise ValueError("Location brace argument requires audit")
                    elif f.startswith("Location::") and a.type == "string_literal":
                        result.append("std::string(" + a.text.decode() + ")")
                    else:
                        result.append(visit(a))
                return f + "(" + ", ".join(result) + ")"
        result = n.text
        for c in reversed(n.named_children):
            changed = visit(c).encode()
            if changed != c.text:
                result = (
                    result[: c.start_byte - n.start_byte]
                    + changed
                    + result[c.end_byte - n.start_byte :]
                )
        return result.decode()

    return visit(PARSER.parse(raw).root_node), count[0]


def containers(text):
    raw = text.encode()
    edits = []
    audit = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type != "declaration":
            continue
        typ = n.child_by_field_name("type")
        d = n.child_by_field_name("declarator")
        if typ is None or d is None or d.type != "init_declarator":
            continue
        value = d.child_by_field_name("value")
        name = d.child_by_field_name("declarator").text.decode()
        t = typ.text.decode()
        if value is None or value.type != "initializer_list":
            continue
        if not t.startswith(("std::vector<", "std::map<", "std::unordered_map<")):
            continue
        rows = kids(value)
        if not rows:
            replacement = t + "()"
        else:
            helper = "Build_" + name.replace("::", "_")
            code = "static " + t + " " + helper + "(){" + t + " result;\n"
            for row in rows:
                if t.startswith("std::vector<"):
                    code += "result.push_back(" + row.text.decode() + ");\n"
                else:
                    fields = kids(row)
                    assert len(fields) == 2, row.text
                    code += (
                        "result.insert(std::make_pair("
                        + fields[0].text.decode()
                        + ","
                        + fields[1].text.decode()
                        + "));\n"
                    )
            code += "return result;}\n"
            edits.append((n.start_byte, n.start_byte, code))
            replacement = helper + "()"
        if not any(c.type == "=" for c in d.children):
            replacement = "= " + replacement
        edits.append((value.start_byte, value.end_byte, replacement))
        audit.append(dict(name=name, type=t, rows=len(rows)))
    return edits_apply(raw, edits), audit


def split_hint_initializer(text, method, label, chunk_size=16):
    """Bound Xenon/JIT function size without changing upstream hint order."""
    raw = text.encode()
    matches = []
    for node in walk(PARSER.parse(raw).root_node):
        if (
            node.type == "function_definition"
            and ("StaticData::" + method + "(").encode()
            in node.child_by_field_name("declarator").text
        ):
            matches.append(node)
    assert len(matches) == 1, (method, len(matches))
    function = matches[0]
    body = function.child_by_field_name("body")
    statements = [n for n in body.named_children if n.type == "expression_statement"]
    assert statements and all(
        n.text.startswith(b"hintTextTable[") or n.text.startswith(b"HintTable_Init_")
        for n in statements
    )
    chunks = []
    pending = []

    def flush():
        if pending:
            chunks.append(tuple(pending))
            pending.clear()

    for statement in statements:
        if statement.text.startswith(b"hintTextTable["):
            pending.append(statement)
            if len(pending) == chunk_size:
                flush()
        else:
            flush()
    flush()
    assert len(chunks) >= 8 and all(1 <= len(c) <= chunk_size for c in chunks), (
        method,
        len(chunks),
    )
    edits = []
    helpers = []
    for index, chunk in enumerate(chunks):
        name = "ShipyardHint_" + label + "_" + str(index)
        helpers.append(
            "static __declspec(noinline) void "
            + name
            + "(std::array<HintText, RHT_MAX>& hintTextTable) {\n"
            + "\n".join("    " + n.text.decode() for n in chunk)
            + "\n}\n"
        )
        edits.append((chunk[0].start_byte, chunk[0].end_byte, name + "(hintTextTable);"))
        edits.extend((n.start_byte, n.end_byte, "") for n in chunk[1:])
    edits.append((function.start_byte, function.start_byte, "\n".join(helpers) + "\n"))
    return edits_apply(raw, edits), [len(chunk) for chunk in chunks]


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    outputs = {}
    audits = {}
    for name, digest in lock["sources"].items():
        t = (ROOT / name).read_text(encoding="utf-8-sig")
        assert hashlib.sha256(t.encode()).hexdigest() == digest, name
        texts[name] = t
    for short in UNITS:
        text = texts[BASE + short]

        # Include spelling resolves complete providers before originals.
        def include(m):
            name = m[1]
            if name.endswith("hints.hpp"):
                return '#include "soh/Enhancements/randomizer/3drando/HintText.h"'
            if name.endswith("CustomMessageManager.h"):
                return '#include "soh/Enhancements/custom-message/CustomMessageManager.h"'
            if name.startswith("../"):
                name = name.split("/")[-1]
            if name in [
                "draw.h",
                "static_data.h",
                "SeedContext.h",
                "dungeon.h",
                "fishsanity.h",
                "tricks.h",
                "randomizerTypes.h",
                "randomizer_check_objects.h",
                "randomizerEnumStrings.h",
                "randomizerEnums.h",
                "item_category_adj.h",
            ]:
                return '#include "soh/Enhancements/randomizer/' + name + '"'
            if name == "custom_messages.hpp":
                return '#include "soh/Enhancements/randomizer/3drando/custom_messages.hpp"'
            return m[0]

        text = re.sub(r'#include "([^"]+)"', include, text)
        if short == "randomizerEnumStrings.cpp":
            text = (
                text.replace("std::string_view", "nonstd::string_view")
                .replace(
                    "m.emplace(#name, name);",
                    "m.insert(std::make_pair(nonstd::string_view(#name),name));",
                )
                .replace(
                    "m.emplace(name, #name);",
                    "m.insert(std::make_pair(name,nonstd::string_view(#name)));",
                )
            )
            assert text.count("map = [] {") == 2
            text = text.replace(
                "map = [] {", "map = []() -> std::unordered_map<nonstd::string_view, EnumName> {", 1
            )
            text = text.replace(
                "map = [] {", "map = []() -> std::unordered_map<EnumName, nonstd::string_view> {", 1
            )
        else:
            if short == "location_list.cpp":
                text = once(
                    text,
                    "CheckFromActorMultimap.emplace(",
                    "CheckFromActorMultimap.insert(std::make_pair(",
                )
                text = once(
                    text,
                    "            location.GetRandomizerCheck());",
                    "            location.GetRandomizerCheck()));",
                )
            text, count = expressions(text)
            text, tables = containers(text)
            text = text.replace(
                "using namespace std::literals::string_literals;",
                "// String suffixes lowered to exact byte-length construction.",
            )
            if short == "tricks.cpp":
                text = '#include "randomizer-content/tag_hash.h"\n' + text
                text = text.replace("switch (tag)", "switch (tag.GetValue())")
                text = re.sub(r"return \{ ([^{}]+) \};", r"return ImVec4(\1);", text)
            lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
                "lower_ranges"
            ]
            text = lower(
                text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
            ).decode()
            text, literals = lower_literals(text)
            audits[short] = dict(expressions=count, tables=tables, literals=literals)
            hint_methods = {
                "3drando/hint_list.cpp": ("HintTable_Init", "Main"),
                "3drando/hint_list/hint_list_item.cpp": ("HintTable_Init_Item", "Item"),
                "3drando/hint_list/hint_list_exclude_overworld.cpp": (
                    "HintTable_Init_Exclude_Overworld",
                    "Overworld",
                ),
                "3drando/hint_list/hint_list_exclude_dungeon.cpp": (
                    "HintTable_Init_Exclude_Dungeon",
                    "Dungeon",
                ),
            }
            if short in hint_methods:
                text, chunks = split_hint_initializer(text, *hint_methods[short])
                audits[short]["hint_chunks"] = chunks
        text = (
            '#include "randomizer-content/support.h"\n#include "resources/runtime_support.h"\n'
            + text
        )
        if short.startswith("3drando/"):
            text = '#include "CustomMessageManager.h"\n' + text
        outputs[BASE + short] = text
    header = (
        texts[BASE + "randomizerEnumStrings.h"]
        .replace("#include <string_view>", "#include <nonstd/string_view.hpp>")
        .replace("#include <optional>", '#include "xbox_compat/optional.h"')
        .replace("std::string_view", "nonstd::string_view")
        .replace("std::optional", "xbox_compat::optional")
        .replace("std::nullopt", "xbox_compat::nullopt")
    )
    header = header.replace(
        "#include <nonstd/string_view.hpp>", '#include "randomizer-content/string_view_hash.h"'
    )
    outputs[BASE + "randomizerEnumStrings.h"] = header
    custom = texts[BASE + "3drando/custom_messages.hpp"].replace(
        '#include "text.hpp"', '#include "soh/Enhancements/randomizer/3drando/text.hpp"'
    )
    outputs[BASE + "3drando/custom_messages.hpp"] = custom
    for name, text in outputs.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated={n: hashlib.sha256(t.encode()).hexdigest() for n, t in outputs.items()},
                audit=audits,
                native_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = json.loads((ROOT / "scratch/randomizer-data-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    roots = (
        [OUT / "generated/soh"]
        + [
            ROOT / ("scratch/" + n + "-xdk/generated/soh")
            for n in ["application-gui", "enhancements", "randomizer-context", "randomizer-logic"]
        ]
        + [
            ROOT / "scratch/deps/string-view-lite/include",
            ROOT / "scratch/custom-message-xdk/generated/include",
        ]
    )
    flags[1:1] = ["/Dnssv_CONFIG_SELECT_STRING_VIEW=1"] + ["/I" + str(p) for p in roots]
    rows = []
    for short in UNITS:
        source = OUT / "generated" / BASE / short
        obj = folder / (source.stem + ".obj")
        command = (
            flags
            + (["/bigobj"] if short == "randomizerEnumStrings.cpp" else [])
            + [str(source), "/Fo" + str(obj)]
        )
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(),
                command=command,
                exit=r.returncode,
                production=True,
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                object_sha256=(
                    hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None
                ),
            )
        )
        print(short, r.returncode, flush=True)
        if r.returncode:
            print("\n".join(l for l in r.stdout.splitlines() if "error " in l)[:5000], flush=True)
        else:
            raw = obj.read_bytes()
            machine = struct.unpack_from("<H", raw, 6 if raw[:4] == b"\0\0\xff\xff" else 0)[0]
            assert machine == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
