"""Fail-closed projection of the complete pinned modern controller core for XDK."""

import argparse, hashlib, json, runpy, re, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from platform_base import resolve as resolve_platform_base

OUT = ROOT / "scratch/input-xdk"
OWN = ROOT / "platform/shipyard/input"
LOWER = runpy.run_path(str(OWN / "lowering.py"))
INITIALIZERS = runpy.run_path(str(OWN / "initializers.py"))
CONSTRUCTORS = runpy.run_path(str(OWN / "constructors.py"))


def transform(relative, text):
    resolve_platform_base(ROOT)
    from xbox360_platform.controller_routes import project as project_routes

    text = project_routes(relative, text)
    text = re.sub(r"#include <(?:SDL2/)?SDL(?:_events)?\.h>", '#include "input/sdl_bridge.h"', text)
    if relative.endswith(".cpp") and '#include "ship/Context.h"' in text:
        text = (
            '#include "ship/controller/controldeck/ControlDeck.h"\n#include'
            ' "ship/window/Window.h"\n'
            + text
        )
    if relative == "include/ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.h":
        text = once(
            text,
            "    void RefreshConnectedSDLGamepads();",
            "    void RefreshConnectedSDLGamepads();\n    void RefreshNativeGamepads(bool"
            " presentation = false);",
        )
        text = once(text, "  private:", "  private:\n    uint32_t mNativeTopologyGeneration;")
    if relative == "src/ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.cpp":
        text = once(
            text,
            "ConnectedPhysicalDeviceManager::ConnectedPhysicalDeviceManager() {",
            "ConnectedPhysicalDeviceManager::ConnectedPhysicalDeviceManager() :"
            " mNativeTopologyGeneration(0) {",
        )
        text = once(
            text,
            "ConnectedPhysicalDeviceManager::~ConnectedPhysicalDeviceManager() {",
            "ConnectedPhysicalDeviceManager::~ConnectedPhysicalDeviceManager() {\n   "
            " ShipyardInput_StopPhysicalRumble();",
        )
        text = once(
            text,
            "} // namespace Ship",
            """void ConnectedPhysicalDeviceManager::RefreshNativeGamepads(bool presentation) {
    if (presentation) ShipyardInput_RefreshGamepadsForGui(); else ShipyardInput_PumpGamepads();
    uint32_t generation = ShipyardInput_GamepadTopologyGeneration();
    if (generation != mNativeTopologyGeneration) {
        RefreshConnectedSDLGamepads();
        mNativeTopologyGeneration = generation;
    }
}
} // namespace Ship""",
        )
    if relative == "src/ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.cpp":
        a = text.index("    SDL_PumpEvents();")
        b = text.index("\n}\n} // namespace Ship", a)
        text = (
            text[:a]
            + "    Context::GetInstance()->GetControlDeck()->GetConnectedPhysicalDeviceManager()->RefreshNativeGamepads(true);"
            + text[b:]
        )
    if relative == "include/ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h":
        signatures = [
            ("", ""),
            (
                "const std::string& c, bool v, const std::string& n, ImVec2 s, uint32_t f",
                "c,v,n,s,f",
            ),
            ("const std::string& c, bool v, const std::string& n, ImVec2 s", "c,v,n,s"),
            ("const std::string& c, bool v, const std::string& n", "c,v,n"),
            ("const std::string& c, const std::string& n, ImVec2 s, uint32_t f", "c,n,s,f"),
            ("const std::string& c, const std::string& n, ImVec2 s", "c,n,s"),
            ("const std::string& c, const std::string& n", "c,n"),
        ]
        text = once(
            text,
            "    using GuiWindow::GuiWindow;",
            "\n".join(
                "    SDLAddRemoveDeviceEventHandler(" + p + ") : GuiWindow(" + a + ") {}"
                for p, a in signatures
            ),
        )
    if relative == "src/libultraship/controller/controldeck/ControlDeck.cpp":
        text = once(
            text,
            "    SDL_PumpEvents();",
            "    GetConnectedPhysicalDeviceManager()->RefreshNativeGamepads();",
        )
    for expression, element in [
        ("{ GetLeftStick(), GetRightStick() }", "std::shared_ptr<ControllerStick>"),
        ("{ LEFT, RIGHT, UP, DOWN }", "Direction"),
    ]:
        data = text.encode()
        edits = []
        for node in LOWER["walk"](LOWER["PARSER"].parse(data).root_node):
            if node.type != "for_range_loop":
                continue
            right = node.child_by_field_name("right")
            if right.text.decode() != expression:
                continue
            prefix = data[node.start_byte : right.start_byte].decode()
            suffix = data[right.end_byte : node.end_byte].decode()
            value = (
                "{ const "
                + element
                + " _controllerValues[] = "
                + expression
                + "; "
                + prefix
                + "_controllerValues"
                + suffix
                + " }"
            )
            edits.append((node.start_byte, node.end_byte, value.encode()))
        text = LOWER["apply"](data, edits).decode()
    if relative == "include/ship/controller/controldeck/ControlDeck.h":
        text = once(text, "mPorts = {};", "mPorts;")
        text = once(text, "mControllerBits = nullptr;", "mControllerBits;")
    elif relative == "src/ship/controller/controldeck/ControlDeck.cpp":
        text = once(
            text,
            "std::unordered_map<CONTROLLERBUTTONS_T, std::string> buttonNames) {",
            "std::unordered_map<CONTROLLERBUTTONS_T, std::string> buttonNames) :"
            " mControllerBits(nullptr) {",
        )
        # The existing keyboard path blocks input behind a modal. Do the same
        # for the gamepad so A activates only the selected ImGui popup button.
        text = once(
            text,
            "return AllGameInputBlocked() ||\n          "
            " Context::GetInstance()->GetWindow()->GetGui()->GetMenuOrMenubarVisible() &&",
            "return AllGameInputBlocked() || ImGui::GetTopMostPopupModal() != NULL ||\n          "
            " Context::GetInstance()->GetWindow()->GetGui()->GetMenuOrMenubarVisible() &&",
        )
    if relative.endswith(".cpp") and "->GetGui()->" in text:
        text = '#include "ship/window/gui/Gui.h"\n' + text
    for name, member in [
        ("Button", "mButtonMappings"),
        ("LED", "mLEDMappings"),
        ("Rumble", "mRumbleMappings"),
    ]:
        if relative.endswith("/Controller" + name + ".cpp"):
            text = once(
                text,
                "[physicalDeviceType](const auto& mapping)",
                "[physicalDeviceType](const std::unordered_map<std::string,"
                " std::shared_ptr<Controller"
                + name
                + "Mapping>>::value_type& mapping) -> bool",
            )
    if relative.endswith("/ControllerStick.cpp"):
        text = once(
            text,
            "[physicalDeviceType](const auto& directionMappings)",
            "[physicalDeviceType](const"
            " std::unordered_map<Direction,std::unordered_map<std::string,std::shared_ptr<ControllerAxisDirectionMapping>>>::value_type&"
            " directionMappings) -> bool",
        )
        text = once(
            text,
            "[physicalDeviceType](const auto& mappingPair)",
            "[nestedPhysicalDeviceType](const std::unordered_map<std::string,"
            " std::shared_ptr<ControllerAxisDirectionMapping>>::value_type& mappingPair) -> bool",
        )
        text = once(
            text,
            "                           return std::any_of(directionMappings.second.begin()",
            "                           const PhysicalDeviceType nestedPhysicalDeviceType ="
            " physicalDeviceType;\n                           return"
            " std::any_of(directionMappings.second.begin()",
        )
        text = once(
            text,
            "                                                         physicalDeviceType;",
            "                                                         nestedPhysicalDeviceType;",
        )
        text = once(
            text,
            "constexpr auto octagonAngle = M_TAU / 8;",
            "const double octagonAngle = M_TAU / 8;",
        )
        text = once(
            text,
            "std::round(angle / octagonAngle)",
            "ShipyardInputCompiler::Round(angle / octagonAngle)",
        )
        text = text.replace("copysign(", "_copysign(")
    if relative.endswith("/WheelHandler.cpp"):
        text = once(
            text,
            "mDirections = { LUS_WHEEL_NONE, LUS_WHEEL_NONE };",
            "mDirections.x = mDirections.y = LUS_WHEEL_NONE;",
        )
        text = once(
            text,
            "mBufferedCoords = { 0.0f, 0.0f };",
            "mBufferedCoords.x = mBufferedCoords.y = 0.0f;",
        )
        text = (
            text.replace("copysignf(", "static_cast<float>(_copysign(")
            .replace("_copysign(LIMIT, *buf);", "_copysign(LIMIT, *buf));")
            .replace("_copysign(REDUCE_STEP, *buf);", "_copysign(REDUCE_STEP, *buf));")
        )
    if relative.endswith(("/ControllerLEDMapping.cpp", "/LEDMappingFactory.cpp")):
        text = text.replace("Color_RGB8({ 0, 0, 0 })", "Color_RGB8()").replace(
            "c_str(), { 0, 0, 0 });", "c_str(), Color_RGB8());"
        )
    if relative.endswith("/SDLLEDMapping.cpp"):
        text = once(text, "color = { 0, 0, 0 };", "color = Color_RGB8();")
    text = CONSTRUCTORS["lower"](relative, text, LOWER)
    text = INITIALIZERS["lower"](text, relative, LOWER)
    return text


def prepare():
    originals = {}
    locked = json.loads((OWN / "sources.lock.json").read_text())["sources"]
    current = {
        p.relative_to(ROOT / "libultraship").as_posix()
        for prefix in (
            "include/ship/controller",
            "src/ship/controller",
            "include/libultraship/controller",
            "src/libultraship/controller",
        )
        for p in (ROOT / "libultraship" / prefix).rglob("*")
        if p.suffix in (".h", ".cpp")
    }
    if current != set(locked):
        raise ValueError("Controller source inventory changed")
    for name, expected in locked.items():
        text = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("Input source drift: " + name)
        originals[name] = text
    enums = set()
    for text in originals.values():
        for node in LOWER["walk"](LOWER["PARSER"].parse(text.encode()).root_node):
            if node.type == "enum_specifier":
                if b"enum class" in node.text[:20]:
                    raise ValueError("Scoped enum requires wrapper")
                name = node.child_by_field_name("name")
                if name:
                    enums.add(name.text.decode())
    pending = {
        name: '#include "input/compiler.h"\n' + LOWER["syntax"](transform(name, text), enums)
        for name, text in originals.items()
    }
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
    from prepare_window import includes as window_includes

    return [
        OUT / "generated/include",
        ROOT / "platform/shipyard/game/include",
        ROOT / "scratch/context-xdk/generated/include",
        resolve_platform_base(ROOT) / "sources",
    ] + window_includes()


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    from prepare_game import release_cvars

    cvars = OUT / "generated/include/compile_definitions.h"
    stable(
        cvars,
        "#pragma once\n"
        + "".join("#define " + n + ' "' + v + '"\n' for n, v in release_cvars().items()),
    )
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
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/DCONTROLLERBUTTONS_T=uint32_t",
        "/Dnssv_CONFIG_SELECT_STRING_VIEW=1",
        "/I" + str(sdk / "include/xbox"),
    ]
    flags += ["/FI" + str(cvars)] + ["/I" + str(p) for p in includes()]
    platform_base = resolve_platform_base(ROOT)
    sources = [
        OUT / "generated" / n
        for n in json.loads((OWN / "sources.lock.json").read_text())["sources"]
        if n.endswith(".cpp")
    ] + [platform_base / "sources/input/physical.cpp", platform_base / "sources/input/xinput.cpp"]
    records = []
    for i, source in enumerate(sources):
        obj = folder / (str(i) + "-" + source.stem + ".obj")
        command = [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        source_id = (
            ("shipyard/" + source.relative_to(platform_base).as_posix())
            if source.is_relative_to(platform_base)
            else source.relative_to(ROOT).as_posix()
        )
        records.append(dict(source=source_id, exit=result.returncode, command=command))
        if not result.returncode and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
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
