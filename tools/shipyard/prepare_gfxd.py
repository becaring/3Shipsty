"""Compile the exact release-enabled graphics disassembler as real C for XDK."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import re
from cpp_ast import walk
from tree_sitter import Language, Parser
import tree_sitter_c
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_game import lower_c

OUT = ROOT / "scratch/gfxd-xdk"
OWN = ROOT / "platform/shipyard/gfxd"
UNITS = ["gfxd.c", "uc.c", "uc_f3d.c", "uc_f3db.c", "uc_f3dex.c", "uc_f3dex2.c", "uc_f3dexb.c"]


def lower_tables(source):
    parser = Parser(Language(tree_sitter_c.language()))

    def view(data):
        return re.sub(rb"(?m)^[ \t]*#[^\r\n]*", lambda m: b" " * len(m[0]), data)

    root = parser.parse(view(source)).root_node
    enums = {}
    for node in walk(root):
        if node.type != "enumerator_list":
            continue
        value = 0
        for item in node.named_children:
            if item.type != "enumerator":
                continue
            name = item.child_by_field_name("name").text.decode()
            if not name.startswith("gfxd_"):
                continue
            if item.child_by_field_name("value"):
                raise ValueError("Non-sequential gfxd enum requires audit")
            enums[name] = value
            value += 1
    priv = verified("libgfxd").joinpath("priv.h").read_text()
    fields = {}
    for kind in ("gfxd_arg_type_t", "gfxd_macro_type_t", "gfxd_ucode", "gfxd_config"):
        pattern = (
            (r"typedef struct\s*\{([^{}]*)\}\s*" + kind + r";")
            if kind.endswith("_t")
            else (r"struct " + kind + r"\s*\{([^{}]*)\};")
        )
        body = re.search(pattern, priv)[1]
        fields[kind] = re.findall(r"(\w+)\s*;", body)
    types = {
        "arg_tbl": "gfxd_arg_type_t",
        "macro_tbl": "gfxd_macro_type_t",
        "uc": "gfxd_ucode",
        "gfxd_config__": "gfxd_config",
    }
    edits = []

    def record(node, kind):
        values = {}
        for pair in node.named_children:
            if pair.type == "comment":
                continue
            if pair.type != "initializer_pair":
                raise ValueError("Unexpected positional gfxd record")
            designator = next(
                n for n in pair.named_children if n.type == "field_designator"
            ).text.decode()[1:]
            if designator not in fields[kind]:
                raise ValueError("Unknown gfxd record field")
            values[designator] = pair.child_by_field_name("value").text.decode()
        return "{ " + ", ".join(values.get(f, "0") for f in fields[kind]) + " }"

    for node in walk(root):
        if node.type != "init_declarator":
            continue
        declarator = node.child_by_field_name("declarator")
        name = declarator.text.decode().split("[")[0]
        if name not in types:
            continue
        value = node.child_by_field_name("value")
        kind = types[name]
        if name in ("arg_tbl", "macro_tbl"):
            entries = {}
            for pair in value.named_children:
                if pair.type == "comment":
                    continue
                if pair.type != "initializer_pair":
                    raise ValueError("Unexpected positional gfxd table")
                designator = next(
                    n for n in pair.named_children if n.type == "subscript_designator"
                ).text.decode()[1:-1]
                entries[enums[designator]] = record(pair.child_by_field_name("value"), kind)
            replacement = (
                "{\n" + ",\n".join(entries.get(i, "{0}") for i in range(max(entries) + 1)) + "\n}"
            )
        else:
            replacement = record(value, kind)
        edits.append((value.start_byte, value.end_byte, replacement.encode()))
    for a, b, v in sorted(edits, reverse=True):
        source = source[:a] + v + source[b:]
    if any(n.type == "initializer_pair" for n in walk(parser.parse(view(source)).root_node)):
        raise ValueError("Unaudited gfxd designated initializer")
    return source


def prepare():
    src = verified("libgfxd")
    for file in sorted(src.glob("*")):
        if file.suffix not in (".c", ".h"):
            continue
        text = file.read_text()
        text = text.replace("static inline ", "static __inline ")
        # These gbi integer tokens use binary notation unsupported by XDK C.
        text = re.sub(r"\b0[bB]([01]+)([uUlL]*)\b", lambda m: hex(int(m[1], 2)) + m[2], text)
        if file.name == "gbi.h":
            if text.count("_Alignas(8)") != 12:
                raise ValueError("GBI alignment inventory drift")
            text = text.replace("_Alignas(8)", "__declspec(align(8))")
        if file.name == "priv.h":
            text = text.replace("#define UCFUNC static inline", "#define UCFUNC static __inline")
        if file.name == "uc_argfn.c":
            macros = dict(
                re.findall(
                    r"^#define (_?G_CC_\w+)\s+([^\n]+)",
                    (src / "gbi.h").read_text().replace("\\\n", ""),
                    re.M,
                )
            )

            def cc(match):
                value = match[1]
                seen = set()
                while value in macros:
                    if value in seen:
                        raise ValueError("Recursive combiner preset")
                    seen.add(value)
                    value = macros[value].strip()
                args = [v.strip() for v in value.split(",")]
                if len(args) != 8 or any(not re.fullmatch(r"\w+", v) for v in args):
                    raise ValueError("Combiner preset drift " + match[1])
                return "CC_(" + ", ".join(args) + ")"

            text, count = re.subn(r"\bCC\((_?G_CC_\w+)\)", cc, text)
            if count != 57:
                raise ValueError("Combiner preset count drift " + str(count))
        if file.name == "gfxd.c":
            text = '#include "gfxd/format.h"\n' + text.replace(
                "vsnprintf(s, sizeof(s), fmt, arg)", "ShipyardGfxdVsnprintf(s, sizeof(s), fmt, arg)"
            )
        stable(OUT / "source" / file.name, text)
    stable(
        OUT / "include/inttypes.h",
        '#pragma once\n#include <stdint.h>\n#define PRIi32 "i"\n#define PRIu32 "u"\n#define PRIX32'
        ' "X"\ntypedef char GfxdInt32IsInt[(sizeof(int32_t)==sizeof(int))?1:-1];\n',
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    flags = [
        "/nologo",
        "/MT",
        "/TC",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/D_WIN32",
        "/DNOMINMAX",
        "/I" + str(OUT / "include"),
        "/I" + str(ROOT / "platform/shipyard"),
        "/I" + str(sdk / "include/xbox"),
    ]
    rows = []
    for name in UNITS:
        source = OUT / "source" / name
        pre = folder / (source.stem + ".i")
        obj = folder / (source.stem + ".obj")
        precommand = [str(sdk / "bin/win32/cl.exe")] + flags + ["/P", "/Fi" + str(pre), str(source)]
        result = subprocess.run(precommand, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".pre.log"), result.stdout + result.stderr)
        if result.returncode:
            print(result.stdout[-2500:])
            raise SystemExit(1)
        data, stats = lower_c(lower_tables(pre.read_bytes()))
        generated = OUT / "generated" / name
        generated.parent.mkdir(exist_ok=True)
        generated.write_bytes(data)
        command = [
            str(sdk / "bin/win32/cl.exe"),
            "/nologo",
            "/MT",
            "/TC",
            "/O2",
            "/c",
            str(generated),
            "/Fo" + str(obj),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(folder / (source.stem + ".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=generated.relative_to(ROOT).as_posix(),
                preprocess_command=precommand,
                command=command,
                exit=result.returncode,
                statistics=stats,
                generated_sha256=hashlib.sha256(data).hexdigest(),
            )
        )
        print(name + ": " + str(result.returncode))
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:1500])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
