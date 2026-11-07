"""Font, GUI and Fast3D texture resources and the pinned image decoder."""

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
from dependency_sources import ROOT, verified
from prepare_archives import stable
from prepare_configuration import once
from prepare_window import transform as window_transform
from prepare_context import transform as context_transform, scoped
from prepare_resource_manager import syntax

OUT = ROOT / "scratch/gui-resources-xdk"
OWN = ROOT / "platform/shipyard/gui-resources"


def transform(name, text):
    from overlap_gui_work_projection import project as overlap_gui_work

    text = overlap_gui_work(name, text)
    if name.endswith("/GuiTexture.h"):
        return window_transform(name, text)
    if name.endswith("/GameOverlay.h"):
        text = context_transform(name, text)
        text = once(
            text,
            "struct Overlay {",
            "struct Overlay {\n    Overlay() : fadeTime(0), duration(0) {}\n    Overlay(OverlayType"
            " type, const std::string& value, float fade, float length) : Type(type), Value(value),"
            " fadeTime(fade), duration(length) {}",
        )
    elif name.endswith("/GameOverlay.cpp"):
        text = once(
            text,
            "GameOverlay::GameOverlay() {",
            'GameOverlay::GameOverlay() : mCurrentFont("Default"), mNeedsCleanup(false) {',
        )
        text = once(
            text,
            '#include "ship/window/Window.h"',
            '#include "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"\n#include'
            ' "ship/resource/ResourceLoader.h"',
        )
        if text.count("ImFontConfig fontConf = {};") != 2:
            raise ValueError("Font config initialization drift")
        text = text.replace("ImFontConfig fontConf = {};", "ImFontConfig fontConf;")
        text = once(
            text,
            "Overlay({ OverlayType::NOTIFICATION, buf, duration, duration })",
            "Overlay(OverlayType::NOTIFICATION, buf, duration, duration)",
        )
        text = once(
            text,
            "for (auto& [name, font] : mFonts) {",
            "for (auto& entry : mFonts) {\n            const std::string& name=entry.first;\n      "
            "      ImFont*& font=entry.second;",
        )
        text = once(
            text,
            "for (auto& [key, overlay] : mRegisteredOverlays) {",
            "for (auto& entry : mRegisteredOverlays) {\n        const std::string&"
            " key=entry.first;\n        Overlay& overlay=entry.second;",
        )
        text = once(text, "switch (var->Type)", "switch (var->Type.GetValue())")
    elif name.endswith("/Font.h"):
        text = once(
            text,
            "using Resource::Resource;",
            "Font(std::shared_ptr<ResourceInitData> initData) : Resource<void>(initData),"
            " Data(nullptr) {}",
        )
        text = once(text, "char* Data = nullptr;", "char* Data;")
    elif name.endswith("/Font.cpp"):
        text = once(
            text,
            "Font::Font() : Resource(std::shared_ptr<ResourceInitData>())",
            "Font::Font() : Resource(std::shared_ptr<ResourceInitData>()), Data(nullptr)",
        )
    elif name.endswith("/Texture.h"):
        start = text.index("enum class TextureType {")
        end = text.index("\n};", start) + 3
        values = text[start:end].split("{", 1)[1].rsplit("}", 1)[0]
        text = text[:start] + scoped("TextureType", values) + text[end:]
        text = once(
            text,
            "using Resource::Resource;",
            "Texture(std::shared_ptr<Ship::ResourceInitData> initData) :"
            " Resource<uint8_t>(initData), Flags(0), HByteScale(1.0), VPixelScale(1.0),"
            " ImageData(nullptr) {}",
        )
        for old, new in [
            ("Flags = 0;", "Flags;"),
            ("HByteScale = 1.0;", "HByteScale;"),
            ("VPixelScale = 1.0;", "VPixelScale;"),
            ("ImageData = nullptr;", "ImageData;"),
        ]:
            text = once(text, old, new)
    elif name.endswith("/Texture.cpp"):
        text = once(
            text,
            "Texture::Texture() : Resource(std::shared_ptr<Ship::ResourceInitData>())",
            "Texture::Texture() : Resource(std::shared_ptr<Ship::ResourceInitData>()), Flags(0),"
            " HByteScale(1.0), VPixelScale(1.0), ImageData(nullptr)",
        )
    if name.endswith(("/GuiTexture.cpp", "/GuiTextureFactory.cpp")):
        text = "#include <stb_image.h>\n" + text
    lower = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
        "lower_ranges"
    ]
    return (
        '#include "resources/runtime_support.h"\n'
        + lower(
            syntax(text).encode(),
            "Shipyard::Resources::begin",
            "Shipyard::Resources::end",
        ).decode()
    )


def prepare():
    stb = verified("stb")
    pending = {}
    for name, expected in json.loads((OWN / "sources.lock.json").read_text())[
        "sources"
    ].items():
        text = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("GUI resource input drift: " + name)
        pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "generated/stb_impl.c",
        '#define STB_IMAGE_IMPLEMENTATION\n#include "stb_image.h"\n',
    )
    stable(
        OUT / "manifest.json",
        json.dumps(
            {n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()},
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    from prepare_window import includes

    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    flags = [
        "/nologo",
        "/c",
        "/EHsc",
        "/GR",
        "/MT",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/Dnssv_CONFIG_SELECT_STRING_VIEW=1",
        "/FI"
        + str(
            ROOT / "scratch/configuration-xdk/generated/include/compile_definitions.h"
        ),
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += [
        "/I" + str(p)
        for p in [
            OUT / "generated/include",
            ROOT / "scratch/context-xdk/generated/include",
            verified("stb"),
        ]
        + includes()
        + [ROOT / "scratch/async-xdk/generated"]
    ]
    sources = [
        OUT / "generated" / n
        for n in json.loads((OWN / "sources.lock.json").read_text())["sources"]
        if n.endswith(".cpp")
    ] + [OUT / "generated/stb_impl.c"]
    records = []
    for source in sources:
        obj = folder / (source.stem + ".obj")
        command = (
            [str(sdk / "bin/win32/cl.exe")]
            + flags
            + ["/TC" if source.suffix == ".c" else "/TP", str(source), "/Fo" + str(obj)]
        )
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        records.append(
            dict(
                source=source.relative_to(ROOT).as_posix(),
                exit=result.returncode,
                command=command,
            )
        )
        if (
            not result.returncode
            and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2
        ):
            raise ValueError("Not a Xenon object")
    stable(folder / "build.json", json.dumps(records, indent=2) + "\n")
    for row in records:
        print(str(row["exit"]) + " " + row["source"])
    if any(r["exit"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
