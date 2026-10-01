"""Project current enhancement units and their real ShipInit registration path."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_game_interactor import call_sites, includes as hook_includes
from prepare_resource_manager import syntax
from cpp_ast import PARSER, walk

OUT = ROOT / "scratch/enhancements-xdk"
OWN = ROOT / "platform/shipyard/enhancements"


def transform(name, text):
    from overlap_lifetime_projection import project as overlap_lifetime
    from overlap_gui_work_projection import project as overlap_gui_work

    text = overlap_lifetime(name, text)
    text = overlap_gui_work(name, text)
    if name.endswith("/ShipInit.hpp"):
        text = once(text, "updatePaths = {}", "updatePaths = std::set<std::string>()")
        lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
            "lower_ranges"
        ]
        return (
            '#include "resources/runtime_support.h"\n'
            + lower(
                text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
            ).decode()
        )
    original = text
    text = call_sites(text, name)
    if name.endswith("/EasyFrameAdvance.cpp"):
        text = once(
            text,
            "#include <libultraship/libultraship.h>",
            "#include <libultraship/bridge.h>",
        )
    if name.endswith("/Cheats/Infinite/Ammo.cpp"):
        text = once(
            text,
            '#include "soh/OTRGlobals.h"',
            '#include "soh/OTRGlobals.h"\n#include "soh/Enhancements/randomizer/SeedContext.h"',
        )
    raw = text.encode()
    edits = []
    for node in walk(PARSER.parse(raw).root_node):
        if node.type == "lambda_expression" and node.parent.type == "argument_list":
            init = node.parent.parent
            if (
                init.type == "init_declarator"
                and init.parent.type == "declaration"
                and init.parent.child_by_field_name("type").text
                == b"RegisterShipInitFunc"
            ):
                # XDK rejects __FUNCSIG__ inside a static-initializer lambda.
                # This real stateless void callback can be a named function;
                # registration still stores it and executes it at the same time.
                if init.parent.parent.type != "translation_unit":
                    raise ValueError("Local ShipInit lambda needs separate scope audit")
                captures = node.child_by_field_name("captures")
                body = node.child_by_field_name("body")
                if captures.text != b"[]":
                    raise ValueError(
                        "Captured ShipInit lambda needs separate projection"
                    )
                declarator = node.child_by_field_name("declarator")
                if declarator and declarator.text.strip() != b"()":
                    raise ValueError("ShipInit lambda signature changed")
                if any(
                    n.type == "return_statement" and n.named_children
                    for n in walk(body)
                ):
                    raise ValueError(
                        "Value-returning ShipInit lambda needs separate projection"
                    )
                helper = "ShipyardInitCallback" + str(node.start_byte)
                function = (
                    "static void "
                    + helper
                    + "() "
                    + body.text.decode()
                    + "\n#line "
                    + str(init.parent.start_point.row + 1)
                    + " "
                    + json.dumps((ROOT / name).as_posix())
                    + "\n"
                )
                edits.append(
                    (init.parent.start_byte, init.parent.start_byte, function.encode())
                )
                edits.append((node.start_byte, node.end_byte, helper.encode()))
        if node.type != "initializer_list" or node.parent.type != "argument_list":
            continue
        parent = node.parent.parent
        if parent.type != "init_declarator":
            continue
        declaration = parent.parent
        if (
            declaration.type != "declaration"
            or declaration.child_by_field_name("type").text != b"RegisterShipInitFunc"
        ):
            continue
        if node != node.parent.named_children[-1]:
            raise ValueError("ShipInit argument order changed")
        values = node.text.decode()[1:-1]
        if not values.strip():
            replacement = "std::set<std::string>()"
        else:
            helper = "ShipyardInitPaths" + str(node.start_byte)
            body = (
                "static std::set<std::string> "
                + helper
                + "(){ const std::string paths[] = {"
                + values
                + "}; return std::set<std::string>(paths,paths+sizeof(paths)/sizeof(paths[0])); }\n"
            )
            # Restore caller source lines after the generated helper. It retains
            # temporary-string lifetime and actual set deduplication/order.
            body += (
                "#line "
                + str(declaration.start_point.row + 1)
                + " "
                + json.dumps((ROOT / name).as_posix())
                + "\n"
            )
            edits.append(
                (declaration.start_byte, declaration.start_byte, body.encode())
            )
            replacement = helper + "()"
        edits.append((node.start_byte, node.end_byte, replacement.encode()))
    for a, b, value in sorted(edits, reverse=True):
        raw = raw[:a] + value + raw[b:]
    text = syntax(raw.decode()).replace(
        "static constexpr int32_t", "static const int32_t"
    )
    if name.endswith("/Fixes/DirtPathFix.cpp"):
        text = once(
            text, "static constexpr ZFightingFixType", "static const ZFightingFixType"
        )
    if name.endswith("/Fixes/HammerHandFix.cpp"):
        for index, macro in enumerate(
            (
                "gsSPDisplayListOTRFilePath(gLinkAdultLeftHandClosedNearDL)",
                "gsSPEndDisplayList()",
            )
        ):
            local = "hammerCommand" + str(index)
            line = (
                "        ResourceMgr_PatchGfxByName(gLinkAdultLeftHandHoldingHammerNearDL,"
                ' "hammerHand' + str(index + 1) + '"'
            )
            text = once(text, macro, local)
            text = once(
                text, line, "        Gfx " + local + " = " + macro + ";\n" + line
            )
    lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
        "lower_ranges"
    ]
    text = lower(
        text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
    ).decode()
    # Macro registration carries a real caller location even after loop/helper
    # lowering changes physical line counts in this generated translation unit.
    pattern = r"\b(?:COND_HOOK|COND_ID_HOOK|COND_VB_SHOULD|REGISTER_VB_SHOULD)\s*\("
    before = list(re.finditer(pattern, original))
    after = list(re.finditer(pattern, text))
    if [m[0] for m in before] != [m[0] for m in after]:
        raise ValueError("Conditional hook call inventory changed")
    for src, dst in reversed(list(zip(before, after))):
        location = (
            "\n#line "
            + str(original.count("\n", 0, src.start()) + 1)
            + " "
            + json.dumps((ROOT / name).as_posix())
            + "\n"
        )
        text = text[: dst.start()] + location + text[dst.start() :]
    return (
        '#include "game-interactor/varargs.h"\n#include "resources/runtime_support.h"\n#line 1 '
        + json.dumps((ROOT / name).as_posix())
        + "\n"
        + text
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    pending = {}
    for name, expected in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("Enhancement source drift " + name)
        pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                source_sha256=lock["sources"],
                generated_sha256={
                    n: hashlib.sha256(t.encode()).hexdigest()
                    for n, t in pending.items()
                },
            ),
            indent=2,
        )
        + "\n",
    )
    return [n for n in pending if n.endswith(".cpp")]


def includes():
    return [
        OUT / "generated/soh",
        ROOT / "scratch/application-xdk/generated/soh",
        ROOT / "scratch/randomizer-xdk/generated/soh",
    ] + hook_includes()


def build(group=None):
    units = prepare()
    folder = OUT / "xdk"
    folder.mkdir(exist_ok=True)
    rows = []
    recipe = json.loads(
        (ROOT / "scratch/game-interactor-xdk/xdk/build.json").read_text()
    )[0]["command"]
    flags = recipe[:-2]
    flags[1:1] = ["/I" + str(p) for p in includes()[:3]]
    previous = (
        json.loads((folder / "build.json").read_text())
        if group and (folder / "build.json").exists()
        else []
    )
    if group:
        units = [n for n in units if "/" + group + "/" in n]
    if not units:
        raise ValueError("No selected enhancement units")
    for name in units:
        source = OUT / "generated" / name
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(),
                command=command,
                exit=result.returncode,
            )
        )
        print(name + ": " + str(result.returncode), flush=True)
        if result.returncode:
            print(
                "\n".join(
                    line for line in result.stdout.splitlines() if "error " in line
                )[:1600],
                flush=True,
            )
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    changed = {r["source"] for r in rows}
    rows = [r for r in previous if r["source"] not in changed] + rows
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--group")
    args = parser.parse_args()
    if args.build:
        build(args.group)
    else:
        prepare()
