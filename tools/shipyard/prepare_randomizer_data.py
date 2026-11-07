"""Location factories and the StaticData table implementation."""

import argparse, hashlib, json, re, runpy, struct, subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/randomizer-data"
OUT = ROOT / "scratch/randomizer-data-xdk"
BASE = "soh/soh/Enhancements/randomizer/"


def children(node):
    return [n for n in node.named_children if n.type != "comment"]


def lower_tables(text):
    raw = text.encode()
    edits = []
    audit = []
    for declaration in walk(PARSER.parse(raw).root_node):
        if declaration.type != "declaration":
            continue
        typ = declaration.child_by_field_name("type")
        init = declaration.child_by_field_name("declarator")
        if typ is None or init is None or init.type != "init_declarator":
            continue
        value = init.child_by_field_name("value")
        name = init.child_by_field_name("declarator").text.decode()
        if value is None or value.type != "initializer_list" or not name.startswith("StaticData::"):
            continue
        typename = typ.text.decode()
        if typename.startswith("std::array<"):
            continue  # True std::array aggregate, no initializer_list API.
        rows = children(value)
        helper = "Build_" + name.split("::")[-1]
        code = ""
        if not rows:
            replacement = typename + "()"
        elif typename.startswith("std::vector<"):
            element = typename[12:-1]
            code = (
                "static "
                + typename
                + " "
                + helper
                + "(){ const "
                + element
                + " rows[]="
                + value.text.decode()
                + "; return "
                + typename
                + "(rows,rows+sizeof(rows)/sizeof(rows[0]));}\n"
            )
            replacement = helper + "()"
        elif typename.startswith("std::unordered_map<"):
            key, mapped = typename[19:-1].split(",")
            key = key.strip()
            mapped = mapped.strip()
            prefix = ""
            insertions = []
            for i, row in enumerate(rows):
                fields = children(row)
                assert len(fields) == 2, row.text
                entry = fields[1].text.decode()
                if mapped == "StaticHintInfo":
                    assert fields[1].type == "call_expression"
                    args = children(fields[1].child_by_field_name("arguments"))
                    out = []
                    for j, arg in enumerate(args):
                        if arg.type != "initializer_list":
                            out.append(arg.text.decode())
                            continue
                        element = {
                            1: "RandomizerHintTextKey",
                            4: "RandomizerCheck",
                            5: "RandomizerGet",
                            6: "RandomizerCheck",
                        }[j]
                        if not children(arg):
                            out.append("std::vector<" + element + ">()")
                            continue
                        vector = helper + "_" + str(i) + "_" + str(j)
                        prefix += (
                            "static std::vector<"
                            + element
                            + "> "
                            + vector
                            + "(){const "
                            + element
                            + " rows[]="
                            + arg.text.decode()
                            + ";return std::vector<"
                            + element
                            + ">(rows,rows+sizeof(rows)/sizeof(rows[0]));}\n"
                        )
                        out.append(vector + "()")
                    entry = "StaticHintInfo(" + ", ".join(out) + ")"
                insertions.append(
                    "result.insert(std::make_pair("
                    + key
                    + "("
                    + fields[0].text.decode()
                    + "),"
                    + entry
                    + "));"
                )
            code = (
                prefix
                + "static "
                + typename
                + " "
                + helper
                + "(){"
                + typename
                + " result;\n"
                + "\n".join(insertions)
                + "\nreturn result;}\n"
            )
            replacement = helper + "()"
        else:
            raise ValueError("Unexpected static table " + typename)
        # Some upstream maps use direct-list initialization without '='.
        if not any(n.type == "=" for n in init.children):
            replacement = "= " + replacement
        edits.append((declaration.start_byte, declaration.start_byte, code))
        edits.append((value.start_byte, value.end_byte, replacement))
        audit.append(
            dict(
                name=name,
                type=typename,
                rows=len(rows),
                source_sha256=hashlib.sha256(value.text).hexdigest(),
            )
        )
    return edits_apply(raw, edits), audit


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError("Randomizer data source drift: " + name)
        texts[name] = text
    item = ROOT / "scratch/randomizer-item-xdk"
    dependency = json.loads((item / "manifest.json").read_text())
    for header in ["location.h", "static_data.h"]:
        name = BASE + header
        assert dependency["sources"][name] == lock["sources"][name]
        assert (
            hashlib.sha256((item / "generated" / name).read_bytes()).hexdigest()
            == dependency["generated"][name]
        )
    location = texts[BASE + "location.cpp"]
    raw = location.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if (
            n.type == "return_statement"
            and len(children(n)) == 1
            and children(n)[0].type == "initializer_list"
        ):
            value = children(n)[0]
            edits.append(
                (
                    value.start_byte,
                    value.end_byte,
                    "Rando::Location(" + value.text.decode()[1:-1] + ")",
                )
            )
    location = edits_apply(raw, edits)
    static, audit = lower_tables(texts[BASE + "static_data.cpp"])
    static = static.replace(
        "std::unordered_map<std::string, uint32_t> output = {};",
        "std::unordered_map<std::string, uint32_t> output;",
    )
    for val in ["message", "text"]:
        static = once(
            static,
            "for (const auto& [key, " + val + "] : input) {",
            "for (const auto& pair : input) {\n        const auto& key=pair.first;const auto& "
            + val
            + "=pair.second;",
        )
    static = static.replace("output.contains(string)", "output.find(string) != output.end()")
    for expr in [
        '"REPEATED STRING IN " + message.GetEnglish(MF_CLEAN)',
        '"REPEATED STRING WITH " + string',
    ]:
        static = once(
            static,
            "SPDLOG_DEBUG(" + expr + ")",
            "SPDLOG_DEBUG(spdlog::string_view_t(" + expr + "))",
        )
    lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))["lower_ranges"]
    static = lower(
        static.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
    ).decode()
    static = (
        '#include "soh/Enhancements/randomizer/3drando/StaticHintInfo.h"\n#include'
        ' "resources/runtime_support.h"\n'
        + static
    )
    outputs = {BASE + "location.cpp": location, BASE + "static_data.cpp": static}
    for name, text in outputs.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated={n: hashlib.sha256(t.encode()).hexdigest() for n, t in outputs.items()},
                factory_returns=len(edits),
                tables=audit,
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
    flags = json.loads((ROOT / "scratch/randomizer-hints-xdk/xdk/build.json").read_text())[0][
        "command"
    ][:-2]
    flags[1:1] = ["/I" + str(OUT / "generated/soh")]
    rows = []
    for filename in ["location.cpp", "static_data.cpp"]:
        source = OUT / "generated" / BASE / filename
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
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
        print(filename, r.returncode)
        if r.returncode:
            print("\n".join(l for l in r.stdout.splitlines() if "error " in l)[:5500])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
