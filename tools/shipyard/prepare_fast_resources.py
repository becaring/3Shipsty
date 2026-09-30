"""Complete pinned Fast3D resource factories, retaining binary/XML command paths."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_configuration import once
from prepare_resource_manager import syntax
from prepare_binary import strong_enum
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/fast-resources"
OUT = ROOT / "scratch/fast-resources-xdk"


SHARED_VERTEX_REPAIR = """namespace {
// Known extractor defect (SoH 9.2.3 archives, and 4.0.5 before them): a display
// list whose G_VTX loads shared gameplay_keep vertices (segment 4) is exported
// as a bare G_VTX_OTR_HASH with its vertex count and hash missing. The reader
// then takes the next real command as the hash, so the vertices never load and
// that command never runs: the Zora's Domain and fishing-pond water ripples.
// In every supported ROM both lists begin with 01004008 0401A120, four
// vertices at index 0 from gameplay_keep 0x1A120, and that exact span is
// exported as its own resource. Only the damaged shape is rebuilt; a correctly
// exported archive does not match and is left unchanged.
struct XboxSharedVertexRepair {
    const char* list;
    const char* vertices;
    int count;
};
const XboxSharedVertexRepair kXboxSharedVertexRepairs[] = {
    { "objects/object_zo/gZoraRipplesModelDL", "objects/gameplay_keep/gameplay_keepVtx_01A120", 4 },
    { "objects/object_fish/gFishingRippleModelDL", "objects/gameplay_keep/gameplay_keepVtx_01A120", 4 },
};

void XboxRepairSharedVertexLoads(std::vector<Gfx>& commands, const std::string& path) {
    for (size_t r = 0; r < sizeof(kXboxSharedVertexRepairs) / sizeof(kXboxSharedVertexRepairs[0]); ++r) {
        const XboxSharedVertexRepair& repair = kXboxSharedVertexRepairs[r];
        if (path != repair.list) {
            continue;
        }
        for (size_t i = 0; i + 1 < commands.size(); ++i) {
            const uint32_t w0 = (uint32_t)commands[i].words.w0;
            if ((int8_t)(w0 >> 24) != G_VTX_OTR_HASH || (w0 & 0x00FFFFFF) != 0 || commands[i].words.w1 != 0) {
                continue;
            }
            // The command the reader consumed as this load's hash.
            const Gfx swallowed = commands[i + 1];
            commands[i] = GsSpVertexOtR2P1(const_cast<char*>(repair.vertices));
            commands[i + 1] = GsSpVertexOtR2P2(repair.count, 0, 0);
            commands.insert(commands.begin() + (i + 2), swallowed);
            i += 2;
        }
        return;
    }
}
}

"""


def transform(name, text):
    types = {"DisplayList": "Gfx", "Matrix": "Mtx", "Vertex": "Vtx", "Light": "LightEntry"}
    if name.endswith("/ResourceType.h"):
        begin = text.index("enum class ResourceType {")
        end = text.index("\n};", begin) + 3
        text = (
            text[:begin]
            + strong_enum("ResourceType", text[begin:end].split("{", 1)[1].rsplit("}", 1)[0])
            + text[end:]
        )
        text = '#include "binary/compat.h"\n' + text
    elif "/type/" in name and name.endswith(".h") and Path(name).stem in types:
        kind = Path(name).stem
        text = once(
            text,
            "using Resource::Resource;",
            kind
            + "(std::shared_ptr<Ship::ResourceInitData> initData) : Ship::Resource<"
            + types[kind]
            + ">(initData) {}",
        )
        if kind == "Vertex":
            text = once(text, "union Vtx;", '#include "libultraship/libultra/gbi.h"')
    if name.endswith("/DisplayListFactory.cpp"):
        source = text.encode()
        edits = []
        count = 0
        for node in walk(PARSER.parse(source).root_node):
            if node.type == "declaration" and b"renderModes =" in node.text[:90]:
                values = next(n for n in walk(node) if n.type == "initializer_list")
                if len(values.named_children) != 33:
                    raise ValueError("Render mode table count changed")
                replacement = "static std::unordered_map<std::string,uint32_t> MakeRenderModes(){\n"
                replacement += (
                    "    const struct Mode { const char* first; uint32_t second; } values[]="
                    + values.text.decode()
                    + ";\n"
                )
                replacement += (
                    (
                        '    std::unordered_map<std::string,uint32_t> result;\n'
                        '    for(size_t i=0;i<sizeof(values)/sizeof(values[0]);++i)result.insert(std::mak'
                        'e_pair(std::string(values[i].first),values[i].second));\n'
                        '    return result;\n'
                        '}\n'
                    )
                )
                replacement += (
                    "std::unordered_map<std::string,uint32_t> renderModes=MakeRenderModes();"
                )
                edits.append((node.start_byte, node.end_byte, replacement.encode()))
            if (
                node.type != "assignment_expression"
                or node.child_by_field_name("left").text != b"g"
            ):
                continue
            rhs = node.child_by_field_name("right")
            if not (
                rhs.type == "initializer_list"
                or (
                    rhs.type == "call_expression"
                    and rhs.child_by_field_name("function").text.startswith(b"gs")
                )
            ):
                continue
            if node.parent.type != "expression_statement":
                raise ValueError("GBI assignment needs a statement scope")
            value = "{ Gfx generatedCommand = " + rhs.text.decode() + "; g=generatedCommand; }"
            edits.append((node.parent.start_byte, node.parent.end_byte, value.encode()))
            count += 1
        if count != 57:
            raise ValueError("GBI assignment inventory changed")
        for a, b, v in sorted(edits, reverse=True):
            source = source[:a] + v + source[b:]
        text = source.decode()
        text = once(text, "std::size(values)", "(sizeof(values)/sizeof(values[0]))")
        text = once(
            text,
            "std::shared_ptr<Ship::IResource>\nResourceFactoryBinaryDisplayListV0::ReadResource(",
            SHARED_VERTEX_REPAIR
            + "std::shared_ptr<Ship::IResource>\nResourceFactoryBinaryDisplayListV0::ReadResource(",
        )
        text = once(
            text,
            "    return"
            " displayList;\n}\n\nstd::shared_ptr<Ship::IResource>\nResourceFactoryXMLDisplayListV0::ReadResource(",
            "    XboxRepairSharedVertexLoads(displayList->Instructions, initData->Path);\n"
            "    return"
            " displayList;\n}\n\nstd::shared_ptr<Ship::IResource>\nResourceFactoryXMLDisplayListV0::ReadResource(",
        )
    if name.endswith("/TextureFactory.cpp"):
        old = "(TextureType)reader->ReadUInt32()"
        if text.count(old) != 2:
            raise ValueError("Texture type boundary inventory changed")
        text = text.replace(
            old, "TextureType(static_cast<TextureType::Value>(reader->ReadUInt32()))"
        )
    if name.endswith(".cpp"):
        lower_ranges = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
            "lower_ranges"
        ]
        text = lower_ranges(
            text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
        ).decode()
        text = '#include "resources/runtime_support.h"\n' + text
    return syntax(text)


def prepare():
    pending = {}
    for name, sha in json.loads((OWN / "sources.lock.json").read_text())["sources"].items():
        text = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != sha:
            raise ValueError("Fast3D resource input drift " + name)
        pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            {n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()}, indent=2
        )
        + "\n",
    )


def includes():
    from prepare_gui import includes as gui_includes

    return [OUT / "generated/include", verified("tinyxml2")] + gui_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    flags = [
        "/nologo",
        "/c",
        "/TP",
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DF3DEX_GBI_2",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/I" + str(sdk / "include/xbox"),
    ] + ["/I" + str(p) for p in includes()]
    rows = []
    names = [
        n
        for n in json.loads((OWN / "sources.lock.json").read_text())["sources"]
        if n.endswith(".cpp")
    ]
    for name in names:
        source = OUT / "generated" / name
        obj = folder / (source.stem + ".obj")
        command = [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(), exit=result.returncode, command=command
            )
        )
        print(source.name + ": " + str(result.returncode))
        if result.returncode:
            print("\n".join(l for l in result.stdout.splitlines() if "error " in l)[:3500])
        elif struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not Xenon")
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
