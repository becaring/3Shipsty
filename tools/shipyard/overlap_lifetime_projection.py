"""Retain replay inputs and marshal native graphics mutations to the render owner.

Skin buffer writes wait for their last reader. Rare mutable buffers drain replay
before writes; common geometry getters consume the idle handoff snapshot.
"""

import re
from cpp_ast import PARSER, walk


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected one lifetime anchor: " + old)
    return text.replace(old, new)


def functions(text, name):
    raw = text.encode()
    return [
        node
        for node in walk(PARSER.parse(raw).root_node)
        if node.type == "function_definition"
        and re.search(
            r"\b" + re.escape(name) + r"\s*\(",
            node.child_by_field_name("declarator").text.decode(),
        )
    ]


def before(text, name, code):
    nodes = functions(text, name)
    if len(nodes) != 1:
        raise ValueError("Expected one lifetime function: " + name)
    raw = text.encode()
    offset = nodes[0].child_by_field_name("body").start_byte + 1
    return (raw[:offset] + ("\n    " + code).encode() + raw[offset:]).decode()


def native(text, name, fields):
    (node,) = functions(text, name)
    raw = text.encode()
    body = node.child_by_field_name("body")
    signature = raw[node.start_byte : body.start_byte].decode()
    original = raw[body.start_byte : body.end_byte].decode()
    linkage = node.parent
    if (
        linkage.type != "linkage_specification"
        or raw[linkage.start_byte : node.start_byte].decode().strip() != 'extern "C"'
    ):
        raise ValueError("Expected a C graphics export: " + name)
    impl = "ShipyardNative_" + name
    native_signature = signature.replace('extern "C" ', "").replace(
        name + "(", impl + "("
    )
    params = ", ".join(field[1] for field in fields)
    members = "\n".join("        " + typ + " " + key + ";" for typ, key in fields)
    arguments = ", ".join("job->" + key for _, key in fields)
    values = ", ".join(key for _, key in fields)
    wrapper = (
        """{
    struct RenderJob {
MEMBERS
        static void Run(void* opaque) {
            RenderJob* job = static_cast<RenderJob*>(opaque);
            IMPL(ARGUMENTS);
        }
    };
    RenderJob job = { VALUES };
    Shipyard_OverlapRunOnRender(RenderJob::Run, &job);
}
""".replace(
            "MEMBERS", members
        )
        .replace("IMPL", impl)
        .replace("ARGUMENTS", arguments)
        .replace("VALUES", values)
    )
    if not fields:
        wrapper = wrapper.replace("RenderJob job = {  };", "RenderJob job;")
    replacement = (
        "static "
        + native_signature
        + original
        + '\n\nextern "C" '
        + signature
        + wrapper
    )
    return (
        raw[: linkage.start_byte] + replacement.encode() + raw[node.end_byte :]
    ).decode()


def graphics(text):
    getters = {
        "OTRGetCurrentWidth": "width",
        "OTRGetCurrentHeight": "height",
        "OTRGetGameRenderWidth": "renderWidth",
        "OTRGetGameRenderHeight": "renderHeight",
        "OTRGetAspectRatio": "aspect",
    }
    for name, member in getters.items():
        text = before(
            text,
            name,
            "if (Shipyard_OverlapIsGameWorker()) return shipyardGraphics."
            + member
            + ";",
        )
    text = (
        """#include "application/overlap.h"
struct ShipyardGraphicsSnapshot {
    unsigned width, height, renderWidth, renderHeight;
    float aspect;
};
static ShipyardGraphicsSnapshot shipyardGraphics = { 320, 240, 320, 240, 4.0f / 3.0f };
"""
        + text
    )
    text += """
extern "C" void Shipyard_OverlapCaptureGraphics(void) {
    shipyardGraphics.width = OTRGetCurrentWidth();
    shipyardGraphics.height = OTRGetCurrentHeight();
    shipyardGraphics.renderWidth = OTRGetGameRenderWidth();
    shipyardGraphics.renderHeight = OTRGetGameRenderHeight();
    shipyardGraphics.aspect = OTRGetAspectRatio();
}
"""
    for name, fields in [
        (
            "Gfx_RegisterBlendedTexture",
            [("const char*", "name"), ("u8*", "mask"), ("u8*", "replacement")],
        ),
        ("Gfx_UnregisterBlendedTexture", [("const char*", "name")]),
        ("Gfx_TextureCacheDelete", [("const uint8_t*", "texAddr")]),
    ]:
        text = native(text, name, fields)
    return text


def resource_manager(text):
    # Retaining owners never waits, including return sites that hold mMutex.
    text = '#include "application/overlap_resource.h"\n' + text
    text = re.sub(
        r"return (resource|cachedResource);",
        r"return Shipyard_OverlapKeepResource(\1);",
        text,
    )
    for name in ("UnloadResource", "WriteResource", "SetAltAssetsEnabled"):
        nodes = functions(text, name)
        for node in reversed(nodes):
            raw = text.encode()
            offset = node.child_by_field_name("body").start_byte + 1
            text = (
                raw[:offset] + b"\n    Shipyard_OverlapFence();" + raw[offset:]
            ).decode()
    # Directory mutation must complete on its caller; a queued dirty write can
    # otherwise outlive the boundary that fenced it and race later replay.
    unload = "mThreadPool->submit_task([this, filter]() -> void { UnloadResourcesProcess(filter); }, priority);"
    text = once(
        text,
        unload,
        """if (Shipyard_OverlapIsGameWorker()) {
        Shipyard_OverlapFence();
        UnloadResourcesProcess(filter);
    } else {
        """
        + unload
        + "\n    }",
    )
    nodes = functions(text, "DirtyResources")
    (node,) = [
        n
        for n in nodes
        if "ResourceFilter" in n.child_by_field_name("declarator").text.decode()
    ]
    body = node.child_by_field_name("body")
    old = body.text.decode()
    synchronous = once(
        old,
        "mThreadPool->submit_task([this, filter]() -> void {",
        "Shipyard_OverlapFence();\n    {",
    )
    synchronous = once(synchronous, "    });", "    }")
    new = (
        "{\n    if (Shipyard_OverlapIsGameWorker()) "
        + synchronous
        + "\n    else "
        + old
        + "\n}"
    )
    raw = text.encode()
    return (raw[: body.start_byte] + new.encode() + raw[body.end_byte :]).decode()


FENCED = {
    "soh/src/code/z_actor.c": ("Actor_Destroy", "Actor_FreeOverlay"),
    "soh/src/code/z_play.c": ("Play_Init", "Play_Destroy"),
    "soh/src/code/game.c": ("GameState_Init", "GameState_Destroy", "GameState_Realloc"),
    "soh/src/code/z_scene.c": ("Scene_ExecuteCommands",),
    "soh/src/code/z_vismono.c": ("VisMono_Draw",),
    "soh/src/code/z_fbdemo.c": (
        "TransitionUnk_Init",
        "TransitionUnk_Destroy",
        "TransitionUnk_SetData",
        "TransitionUnk_Draw",
        "TransitionUnk_Update",
    ),
    "soh/soh/SaveManager.cpp": (
        "SaveManager::SaveSection",
        "SaveManager::LoadFile",
        "SaveManager::SaveGlobal",
        "Save_LoadFile",
    ),
    "soh/soh/Enhancements/nametag.cpp": ("FreeNameTag",),
    "soh/soh/Enhancements/kaleido.cpp": ("Kaleido::RebuildVertices",),
}


def project(name, text):
    name = name.replace("\\", "/")
    original = text
    if name == "soh/soh/OTRGlobals.cpp":
        return graphics(text)
    if name == "soh/soh/Enhancements/savestates.cpp":
        text = before(text, "SaveState::Save", "Shipyard_OverlapSaveStateBoundary(0);")
        text = before(text, "SaveState::Load", "Shipyard_OverlapSaveStateBoundary(1);")
    if name.endswith("/src/fast/interpreter.cpp"):
        text = before(
            text,
            "Interpreter::TextureCacheClear",
            """if (Shipyard_OverlapIsGameWorker()) {
        struct RenderClear {
            Interpreter* interpreter;
            static void Run(void* opaque) {
                static_cast<RenderClear*>(opaque)->interpreter->TextureCacheClear();
            }
        } job = { this };
        Shipyard_OverlapRunOnRender(RenderClear::Run, &job);
        return;
    }""",
        )
    for function in FENCED.get(name, ()):
        text = before(text, function, "Shipyard_OverlapFence();")
    if name == "soh/src/code/z_skin.c":
        text = once(
            text,
            "    vtxBuf = vtxEntry->buf[vtxEntry->index];",
            """    vtxBuf = vtxEntry->buf[vtxEntry->index];
    Shipyard_OverlapTouchWritableSpan(vtxBuf, data->totalVtxCount * sizeof(Vtx));""",
        )
    if name == "soh/soh/ResourceManagerHelpers.cpp":
        text = before(
            text,
            "ResourceMgr_IsGameMasterQuest",
            """uint32_t frozen;
    if (Shipyard_OverlapMasterQuest(&frozen)) return frozen;""",
        )
        for target, value in (
            ("gfx", "instruction"),
            ("destinationGfx", "sourceGfx"),
            ("gfx", "patch.instruction"),
        ):
            old = "*" + target + " = " + value + ";"
            expected = 2 if value == "instruction" else 1
            if text.count(old) != expected:
                raise ValueError("Display-list mutation inventory changed: " + old)
            new = """if (memcmp(TARGET, &VALUE, sizeof(Gfx)) != 0) {
        Shipyard_OverlapFence();
        *TARGET = VALUE;
    }""".replace(
                "TARGET", target
            ).replace(
                "VALUE", value
            )
            text = text.replace(old, new)
    if name == "soh/soh/Enhancements/nametag.cpp":
        text = once(
            text,
            "    nameTagDl.clear();",
            "    if (!nameTagDl.empty()) Shipyard_OverlapFence();\n    nameTagDl.clear();",
        )
    if name == "soh/soh/Enhancements/debugger/colViewer.cpp":
        text = before(
            text,
            "DrawColViewer",
            """// Pending replays may still borrow these lists while the viewer is disabled.
    if (!CVarGetInteger(CVAR_DEVELOPER_TOOLS("ColViewer.Enabled"), 0)) return;""",
        )
        text = (
            once(
                text,
                "    ResetVector(opaDl);",
                """    if (!opaDl.empty() || !xluDl.empty()) Shipyard_OverlapFence();
    ResetVector(opaDl);""",
            )
            if text.count("    ResetVector(opaDl);") == 1
            else text.replace(
                "    ResetVector(opaDl);",
                "    if (!opaDl.empty() || !xluDl.empty()) Shipyard_OverlapFence();\n    ResetVector(opaDl);",
                1,
            )
        )
    if name == "soh/soh/Enhancements/kaleido.cpp":
        text = once(
            text,
            "    mEntryDl.clear();",
            "    if (!mEntryDl.empty()) Shipyard_OverlapFence();\n    mEntryDl.clear();",
        )
    if name == "soh/soh/Enhancements/cosmetics/authenticGfxPatches.cpp":
        for pointer in ("mirroredSoldOutVtx", "mirroredSunSongVtx"):
            text = once(
                text,
                "free(" + pointer + ");",
                "Shipyard_OverlapFence();\n            free(" + pointer + ");",
            )
    if name.startswith("soh/src/overlays/") and "ResourceMgr_LoadVtxByName(" in text:
        # Actor/effect callers write shared resource vertices. The GbiWrap
        # accessor used to record ordinary read-only draws remains unfenced.
        nodes = [
            n
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "function_definition"
        ]
        for node in reversed(nodes):
            body = node.child_by_field_name("body")
            if "ResourceMgr_LoadVtxByName(" not in body.text.decode():
                continue
            raw = text.encode()
            text = (
                raw[: body.start_byte + 1]
                + b"\n    Shipyard_OverlapFence();"
                + raw[body.start_byte + 1 :]
            ).decode()
    hazards = (
        "ovl_Boss_Dodongo/",
        "ovl_Boss_Ganon/",
        "ovl_Boss_Ganondrof/",
        "ovl_Boss_Goma/",
        "ovl_En_Ganon_Mant/",
    )
    if any(part in name for part in hazards):
        # These actor paths mutate persistent masks, texture bytes and vertices.
        # Restrict draining to their execution so village/Field frames overlap.
        nodes = [
            n
            for n in walk(PARSER.parse(text.encode()).root_node)
            if n.type == "function_definition"
        ]
        for node in reversed(nodes):
            body = node.child_by_field_name("body")
            content = body.text.decode()
            if not re.search(
                r"sMaskTex|sLava|sDecayTex|sClearPixelTex|sWindowShatterTex|sVertices|gMantVtx",
                content,
            ):
                continue
            raw = text.encode()
            text = (
                raw[: body.start_byte + 1]
                + b"\n    Shipyard_OverlapFence();"
                + raw[body.start_byte + 1 :]
            ).decode()
    if name.endswith("/ovl_kaleido_scope/kaleido_scope_PAL.c"):
        text = once(
            text,
            "        free(mapLeftTexModifiedRaw);",
            "        Shipyard_OverlapFence();\n        free(mapLeftTexModifiedRaw);",
        )
        text = once(
            text,
            "        free(mapRightTexModifiedRaw);",
            "        Shipyard_OverlapFence();\n        free(mapRightTexModifiedRaw);",
        )
    if name == "soh/src/code/z_kanfont.c":
        # Glyph and icon slots hold texture paths that later frames keep drawing.
        text, count = re.subn(
            r"memcpy\(([^,]+), ([^,]+), strlen\(\2\) \+ 1\);",
            r"if (memcmp(\1, \2, strlen(\2) + 1) != 0) {"
            r" Shipyard_OverlapFence(); memcpy(\1, \2, strlen(\2) + 1); }",
            text,
        )
        if count != 5:
            raise ValueError("Font texture path copy inventory changed")
    if name == "soh/src/code/z_message_PAL.c":
        # Message lookup stores typePos in glyph slot 0 while the previous text may still replay.
        old = "font->charTexBuf[0] = messageTableEntry->typePos;"
        if text.count(old) != 5:
            raise ValueError("Message type position inventory changed")
        text = text.replace(
            old,
            "if (font->charTexBuf[0] != messageTableEntry->typePos) {"
            " Shipyard_OverlapFence(); " + old + " }",
        )
        old = "for (j = 0; j < FONT_CHAR_TEX_SIZE; j += 4) {"
        if text.count(old) != 5:
            raise ValueError("Name glyph copy inventory changed")
        text = text.replace(old, "Shipyard_OverlapFence();\n" + old)
    if text != original:
        text = '#include "application/overlap.h"\n' + text
    return text
