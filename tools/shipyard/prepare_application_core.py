"""Project complete modern scene/message/resource bridges and application utilities."""

import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from prepare_randomizer import edits_apply
from prepare_application_windows import containers, includes as window_includes, SYNTAX
from prepare_enhancements import transform as enhancement_syntax
from prepare_custom_message import escape_literal
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/application-core"
OUT = ROOT / "scratch/application-core-xdk"
UNITS = [
    "soh/soh/" + n
    for n in (
        "ResourceManagerHelpers.cpp",
        "z_message_OTR.cpp",
        "z_play_otr.cpp",
        "z_scene_otr.cpp",
        "GbiWrap.cpp",
        "util.cpp",
        "CrashHandlerExt.cpp",
        "Notification/Notification.cpp",
    )
]


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


PREFETCH_FEEDER = """namespace {
// Directory prefetch runs on one service thread. The game thread only hands
// over a directory prefix (a lock and an append). Building the sorted archive
// index (tens of thousands of names) and queueing a directory's entries one
// by one both cost far more than a frame: the first scene entry used to pay
// for the index, and every entry for the queueing. The feeder loads one
// resource at a time on its own thread through the same synchronous path as a
// draw, so at most one archive read competes with a foreground load, and the
// cache keeps a single instance either way. A directory prefetched once is
// skipped until an eviction (ResourceMgr_EvictUnusedDirectories) frees
// directories, and prefetch only runs while physical memory has headroom;
// below it, files load on first use exactly as without prefetch.
bool ShipyardPrefetchHeadroom() {
#ifdef _XBOX
    MEMORYSTATUS memory;
    memory.dwLength = sizeof(memory);
    GlobalMemoryStatus(&memory);
    return memory.dwAvailPhys >= 64u * 1024u * 1024u;
#else
    return true;
#endif
}

// Sorted archive names, built once by the feeder and read-only afterwards.
// Eviction on the game thread uses it once it has been published.
const std::vector<std::string>* volatile sShipyardArchiveIndex = NULL;
// Advanced by each eviction; the feeder forgets its completed directories.
volatile long sShipyardEvictionEpoch = 0;

class ShipyardPrefetchFeeder {
  public:
    ShipyardPrefetchFeeder() : mStopping(0), mStarted(false) {
    }
    ~ShipyardPrefetchFeeder() {
        {
            Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(mMutex);
            InterlockedExchange(&mStopping, 1);
        }
        mWake.notify_all();
        if (mWorker.joinable()) {
            mWorker.join();
        }
    }
    void Queue(const std::vector<std::string>& prefixes) {
        if (prefixes.empty()) {
            return;
        }
        {
            Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(mMutex);
            for (size_t i = 0; i < prefixes.size(); ++i) {
                if (std::find(mQueue.begin(), mQueue.end(), prefixes[i]) == mQueue.end()) {
                    mQueue.push_back(prefixes[i]);
                }
            }
            if (!mStarted) {
                mStarted = true;
#ifdef _XBOX
                mWorker = Shipyard::Async::joining_thread(Run, this, Shipyard::Async::ServiceProcessorFor(1));
#else
                mWorker = Shipyard::Async::joining_thread(Run, this);
#endif
            }
        }
        mWake.notify_one();
    }

  private:
    static void Run(void* context) {
        static_cast<ShipyardPrefetchFeeder*>(context)->Loop();
    }
    bool Stopping() {
        return InterlockedCompareExchange(&mStopping, 0, 0) != 0;
    }
    void Loop() {
        auto manager = Ship::Context::GetInstance()->GetResourceManager();
        // Archives are only added during setup. The index is built here, off
        // the game thread, before the first directory is walked.
        std::vector<std::string>* index = new std::vector<std::string>();
        {
            auto files = manager->GetArchiveManager()->ListFiles("");
            index->assign(files->begin(), files->end());
        }
        std::sort(index->begin(), index->end());
        // Publish only a complete index.
        MemoryBarrier();
        sShipyardArchiveIndex = index;
        const std::vector<std::string>& names = *index;
        std::set<std::string> completed;
        long epoch = InterlockedCompareExchange(&sShipyardEvictionEpoch, 0, 0);
        Shipyard::Async::unique_lock<Shipyard::Async::mutex> lock(mMutex);
        for (;;) {
            while (mQueue.empty() && !Stopping()) {
                mWake.wait(lock);
            }
            if (Stopping()) {
                return;
            }
            const std::string start = mQueue.front();
            mQueue.pop_front();
            lock.unlock();
            const long currentEpoch = InterlockedCompareExchange(&sShipyardEvictionEpoch, 0, 0);
            if (currentEpoch != epoch) {
                completed.clear();
                epoch = currentEpoch;
            }
            if (completed.find(start) == completed.end() && ShipyardPrefetchHeadroom()) {
                bool complete = true;
                unsigned walked = 0;
                for (std::vector<std::string>::const_iterator it = std::lower_bound(names.begin(), names.end(), start);
                     it != names.end() && it->compare(0, start.size(), start) == 0; ++it) {
                    if (Stopping() || ((++walked & 15) == 0 && !ShipyardPrefetchHeadroom())) {
                        complete = false;
                        break;
                    }
                    try {
                        manager->LoadResource(*it);
                    } catch (...) {
                    }
                }
                if (complete) {
                    completed.insert(start);
                }
            }
            lock.lock();
        }
    }
    Shipyard::Async::mutex mMutex;
    Shipyard::Async::condition_variable mWake;
    std::deque<std::string> mQueue;
    volatile long mStopping;
    bool mStarted;
    Shipyard::Async::joining_thread mWorker;
};
ShipyardPrefetchFeeder sShipyardPrefetchFeeder;

// Shared resources that nearly every scene draws on first use: the gameplay
// keep, and the HUD, text box and pause menu textures. Queued once, after the
// first scene's own directories.
const char* const sShipyardSharedPrefetch[] = {
    "objects/gameplay_keep/",
    "textures/parameter_static/",
    "textures/do_action_static/",
    "textures/message_static/",
    "textures/message_texture_static/",
    "textures/nes_font_static/",
    "textures/icon_item_static/",
    "textures/icon_item_24_static/",
    "textures/icon_item_field_static/",
    "textures/icon_item_dungeon_static/",
    "textures/icon_item_nes_static/",
    "textures/item_name_static/",
    "textures/map_name_static/",
    "textures/map_i_static/",
    "textures/map_48x85_static/",
};

// Game thread only. A scene's directories are handed over when Play_Init
// finishes, so its own synchronous loads never share the archive with them.
bool sShipyardPrefetchHeld = false;
bool sShipyardSharedQueued = false;
std::vector<std::string> sShipyardHeldPrefetch;
// Game thread only: every scene and object directory the game has used since
// the last eviction, the current scene's directory, and game frames since the
// current scene finished Play_Init.
std::vector<std::string> sShipyardResidentDirectories;
std::string sShipyardCurrentScene;
unsigned sShipyardFramesInScene = 0;
}

extern "C" void ResourceMgr_SetCurrentSceneDirectory(const char* prefix) {
    sShipyardCurrentScene = prefix;
}

extern "C" void ResourceMgr_HoldPrefetch(void) {
    sShipyardPrefetchHeld = true;
}

extern "C" void ResourceMgr_ReleasePrefetch(void) {
    sShipyardPrefetchHeld = false;
    sShipyardFramesInScene = 0;
    std::vector<std::string> held;
    held.swap(sShipyardHeldPrefetch);
    if (!sShipyardSharedQueued) {
        sShipyardSharedQueued = true;
        for (size_t i = 0; i < sizeof(sShipyardSharedPrefetch) / sizeof(sShipyardSharedPrefetch[0]); ++i) {
            held.push_back(sShipyardSharedPrefetch[i]);
        }
    }
    sShipyardPrefetchFeeder.Queue(held);
}

extern "C" void ResourceMgr_PrefetchDirectory(const char* prefix) {
    const std::string start(prefix);
    if ((start.compare(0, 7, "scenes/") == 0 || start.compare(0, 8, "objects/") == 0) &&
        std::find(sShipyardResidentDirectories.begin(), sShipyardResidentDirectories.end(), start) ==
            sShipyardResidentDirectories.end()) {
        sShipyardResidentDirectories.push_back(start);
    }
    if (sShipyardPrefetchHeld) {
        if (std::find(sShipyardHeldPrefetch.begin(), sShipyardHeldPrefetch.end(), start) ==
            sShipyardHeldPrefetch.end()) {
            sShipyardHeldPrefetch.push_back(start);
        }
        return;
    }
    sShipyardPrefetchFeeder.Queue(std::vector<std::string>(1, start));
}

// Every spawned object, including the keeps: a keep is walked once per
// session and then skipped.
extern "C" void ResourceMgr_PrefetchObject(const char* name) {
    if (name == NULL || name[0] == '\\0') {
        return;
    }
    ResourceMgr_PrefetchDirectory((std::string("objects/") + name + "/").c_str());
}

"""

EVICTION = """
extern "C" void gfx_texture_cache_clear();

// Nothing else frees cached resources, and a long session visits most of the
// game. Below a memory floor, whole scene and object directories that nothing
// can still point at are dropped. This runs on the game thread before an
// update records, at least 32 game frames into a scene and never during a
// transition, so no recorded or replayed frame references the scene that was
// left. Kept: the current scene, every object in the bank now, the keeps,
// Link's and get-item objects (drawn outside the bank), and any directory
// holding a patched display list (a reload would lose the patch). Resources
// that game code still shares stay alive through their references. Fast3D
// caches textures by address and freed memory is reused, so its cache is
// cleared afterwards, as an alt-asset toggle does; prefetch forgets the
// directories it had completed.
extern "C" void ResourceMgr_EvictUnusedDirectories(void) {
    if (sShipyardFramesInScene < 0x10000) {
        ++sShipyardFramesInScene;
    }
    if (sShipyardFramesInScene < 32 || (sShipyardFramesInScene & 31) != 0) {
        return;
    }
    if (gPlayState == NULL || gPlayState->transitionTrigger != TRANS_TRIGGER_OFF ||
        gPlayState->transitionMode != TRANS_MODE_OFF) {
        return;
    }
#ifdef _XBOX
    MEMORYSTATUS memory;
    memory.dwLength = sizeof(memory);
    GlobalMemoryStatus(&memory);
    if (memory.dwAvailPhys >= 48u * 1024u * 1024u) {
        return;
    }
#else
    return;
#endif
    const std::vector<std::string>* index = sShipyardArchiveIndex;
    if (index == NULL) {
        return;
    }
    MemoryBarrier();
    std::vector<std::string> evict;
    std::vector<std::string> keep;
    const ObjectContext& objects = gPlayState->objectCtx;
    for (size_t d = 0; d < sShipyardResidentDirectories.size(); ++d) {
        const std::string& directory = sShipyardResidentDirectories[d];
        bool retain = directory == sShipyardCurrentScene || directory.compare(0, 17, "objects/gameplay_") == 0 ||
                      directory.compare(0, 20, "objects/object_link_") == 0 ||
                      directory.compare(0, 18, "objects/object_gi_") == 0;
        if (!retain && directory.compare(0, 8, "objects/") == 0) {
            for (int i = 0; i < objects.num && !retain; ++i) {
                const int id = objects.status[i].id < 0 ? -objects.status[i].id : objects.status[i].id;
                if (id > 0 && id < OBJECT_ID_MAX && gObjectTable[id].fileName != NULL &&
                    directory == std::string("objects/") + gObjectTable[id].fileName + "/") {
                    retain = true;
                }
            }
        }
        for (std::unordered_map<std::string, std::unordered_map<std::string, GfxPatch>>::const_iterator patched =
                 originalGfx.begin();
             !retain && patched != originalGfx.end(); ++patched) {
            const std::string& path = patched->first;
            const size_t start = path.compare(0, 7, "__OTR__") == 0 ? 7 : 0;
            if (path.compare(start, directory.size(), directory) == 0) {
                retain = true;
            }
        }
        (retain ? keep : evict).push_back(directory);
    }
    if (evict.empty()) {
        return;
    }
    auto manager = Ship::Context::GetInstance()->GetResourceManager();
    for (size_t d = 0; d < evict.size(); ++d) {
        const std::string& start = evict[d];
        for (std::vector<std::string>::const_iterator it = std::lower_bound(index->begin(), index->end(), start);
             it != index->end() && it->compare(0, start.size(), start) == 0; ++it) {
            manager->UnloadResource(*it);
        }
    }
    sShipyardResidentDirectories.swap(keep);
    InterlockedIncrement(&sShipyardEvictionEpoch);
    gfx_texture_cache_clear();
    SPDLOG_INFO("Evicted {} resource directories below the memory floor", evict.size());
}
"""


def project(name, text):
    # Canonical projected headers are selected by full application include paths.
    directory = Path(name).parent.as_posix().removeprefix("soh/")
    text = re.sub(
        r'#include "([^/\"]+\.h)"',
        lambda m: (
            '#include "' + directory + "/" + m[1] + '"'
            if (ROOT / Path(name).parent / m[1]).exists()
            else m[0]
        ),
        text,
    )
    text = re.sub(r'#include "((?:Enhancements|resource)/[^\"]+)"', r'#include "soh/\1"', text)
    text = text.replace(
        "#include <libultraship/libultraship.h>",
        "#include <ship/Context.h>\n#include <ship/resource/ResourceManager.h>\n#include"
        " <ship/window/gui/Gui.h>\n#include <libultraship/bridge.h>",
    )
    text = enhancement_syntax(name, text)
    if name.endswith("/z_message_OTR.cpp"):
        text = once(
            text,
            "auto existingEntry = std::find_if(table, table + tableSize, [id ="
            " file->messages[j].id](const auto& entry)",
            "const uint16_t id = file->messages[j].id;\n            auto existingEntry ="
            " std::find_if(table, table + tableSize, [id](const MessageTableEntry& entry)",
        )
    if name.endswith("/ResourceManagerHelpers.cpp"):
        text = once(text, "->LoadResource(Path.c_str());", "->LoadResource(Path);")
        text = once(
            text,
            'extern "C" Gfx* ResourceMgr_LoadGfxByName(const char* path) {',
            "\n".join(
                [
                    'extern "C" Gfx* ResourceMgr_LoadGfxByName(const char* path) {',
                    "    // MQ remapping keeps the authoritative preflight/load path.",
                    "    const bool isMq = ResourceMgr_IsGameMasterQuest() != 0;",
                    "    if (!isMq) {",
                    "        auto manager = Ship::Context::GetInstance()->GetResourceManager();",
                    "        auto cached = manager->GetSettledAlternate(path);",
                    "        if (cached) {",
                    (
                        "            auto displayList ="
                        " std::static_pointer_cast<Fast::DisplayList>(cached);"
                    ),
                    "            return (Gfx*)&displayList->Instructions[0];",
                    "        }",
                    "    }",
                ]
            ),
        )
        text = once(
            text,
            "    auto res ="
            " std::static_pointer_cast<Fast::DisplayList>(ResourceMgr_GetResourceByNameHandlingMQ(path));\n"
            "    return (Gfx*)&res->Instructions[0];",
            "\n".join(
                [
                    (
                        "    // Preserve raw-name cache precedence, then normalize the resource"
                        " signature."
                    ),
                    (
                        "    // Resident normalized resources need no ready future; cold loads take"
                        " the synchronous path."
                    ),
                    '    if (!isMq && std::strncmp(path, "__OTR__", 7) == 0 &&',
                    '        std::strncmp(path + 7, "__OTR__", 7) != 0 &&',
                    '        std::strncmp(path + 7, "alt/", 4) != 0) {',
                    "        auto manager = Ship::Context::GetInstance()->GetResourceManager();",
                    (
                        "        auto raw ="
                        " std::static_pointer_cast<Fast::DisplayList>(manager->GetCachedResource(std::string(path)));"
                    ),
                    "        if (raw != nullptr) return (Gfx*)&raw->Instructions[0];",
                    "        const std::string normalized(path + 7);",
                    (
                        "        auto res ="
                        " std::static_pointer_cast<Fast::DisplayList>(manager->LoadResource(normalized));"
                    ),
                    "        return (Gfx*)&res->Instructions[0];",
                    "    }",
                    (
                        "    auto res ="
                        " std::static_pointer_cast<Fast::DisplayList>(ResourceMgr_GetResourceByNameHandlingMQ(path));"
                    ),
                    "    return (Gfx*)&res->Instructions[0];",
                ]
            ),
        )
        text = (
            '#include "soh/Enhancements/randomizer/SeedContext.h"\n#include'
            " <fast/resource/type/Texture.h>\n#include <fast/interpreter.h>\n#include"
            " <stb_image.h>\n"
            + text
        )
        text = once(
            text, "pathStr.starts_with(sOtr)", "Shipyard::Resources::starts_with(pathStr,sOtr)"
        )
        raw = text.encode()
        edits = []
        for n in walk(PARSER.parse(raw).root_node):
            if n.type != "assignment_expression":
                continue
            right = n.child_by_field_name("right")
            left = n.child_by_field_name("left")
            if right.type == "initializer_list" and left.text.startswith(b"originalGfx["):
                assert n.parent.type == "expression_statement"
                edits.append(
                    (
                        n.parent.start_byte,
                        n.parent.end_byte,
                        "{ const GfxPatch patch = "
                        + right.text.decode()
                        + "; "
                        + left.text.decode()
                        + " = patch; }",
                    )
                )
        assert len(edits) == 3
        text = edits_apply(raw, edits)
    if name.endswith("/ResourceManagerHelpers.cpp"):
        # First draws of a new object or room otherwise load every skeleton,
        # display list and texture synchronously on the game thread.
        text = (
            "#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <windows.h>\n#endif\n#include"
            ' "async/native.h"\n#include <ship/resource/archive/ArchiveManager.h>\n#include'
            " <algorithm>\n#include <deque>\n#include <set>\n"
            + text
        )
        text = once(
            text,
            'extern "C" void ResourceMgr_LoadDirectory(const char* resName) {',
            PREFETCH_FEEDER + 'extern "C" void ResourceMgr_LoadDirectory(const char* resName) {',
        )
        text = text.rstrip("\n") + "\n" + EVICTION
    if name.endswith("/z_play_otr.cpp"):
        text = once(
            text,
            "    play->sceneSegment = OTRPlay_LoadFile(play, scenePath.c_str());",
            """    // Rooms, their display lists and textures are prefetched on the service
    // thread once Play_Init finishes; the scene file itself loads below. The
    // directory is also the current scene's, which eviction always keeps.
    const std::string xboxSceneDirectory =
        StringHelper::Sprintf("scenes/%s/%s/", sceneVersion.c_str(), scene->sceneFile.fileName);
    ResourceMgr_SetCurrentSceneDirectory(xboxSceneDirectory.c_str());
    ResourceMgr_PrefetchDirectory(xboxSceneDirectory.c_str());
    play->sceneSegment = OTRPlay_LoadFile(play, scenePath.c_str());""",
        )
        # The same directory OTRPlay_SpawnScene selects, for a scene that is
        # not yet current: master quest is decided for that scene (randomizer
        # MQ dungeons included), not for the scene being left.
        text = once(
            text,
            'extern "C" void OTRPlay_SpawnScene(PlayState* play, s32 sceneId, s32 spawn) {',
            """extern "C" void ResourceMgr_PrefetchDirectory(const char* prefix);
extern "C" void ResourceMgr_SetCurrentSceneDirectory(const char* prefix);

// A transition's destination, queued before the screen fades out.
extern "C" void OTRPlay_PrefetchScene(s32 sceneId) {
    if (sceneId < 0 || sceneId >= SCENE_ID_MAX) {
        return;
    }
    const SceneTableEntry* scene = &gSceneTable[sceneId];
    const bool inNonSharedScene = (sceneId >= SCENE_DEKU_TREE && sceneId <= SCENE_ICE_CAVERN) ||
                                  sceneId == SCENE_GERUDO_TRAINING_GROUND || sceneId == SCENE_INSIDE_GANONS_CASTLE;
    std::string sceneVersion = "shared";
    if (inNonSharedScene) {
        sceneVersion = ResourceMgr_IsSceneMasterQuest(static_cast<s16>(sceneId)) ? "mq" : "nonmq";
    }
    ResourceMgr_PrefetchDirectory(
        StringHelper::Sprintf("scenes/%s/%s/", sceneVersion.c_str(), scene->sceneFile.fileName).c_str());
}

extern "C" void OTRPlay_SpawnScene(PlayState* play, s32 sceneId, s32 spawn) {""",
        )
    if name.endswith("/CrashHandlerExt.cpp"):
        text = re.sub(r"(static std::array<[^;{}]+> \w+)\{", r"\1 = {", text)
        text = text.replace("snprintf(", "Shipyard::SohResources::snprintf(")
        text = '#include "soh-resources/format.h"\n' + text
    if name.endswith("/z_scene_otr.cpp"):
        text = text.replace("(int)cmdCode", "static_cast<int>(cmdCode.GetValue())")
    text = containers(text)
    text = SYNTAX(text, set())
    raw = text.encode()
    edits = []
    for n in walk(PARSER.parse(raw).root_node):
        if n.type == "string_literal" and any(b >= 128 for b in n.text):
            edits.append((n.start_byte, n.end_byte, escape_literal(n.text.decode())))
    text = edits_apply(raw, edits)
    return (
        '#include "input/compiler.h"\n#include "application-windows/support.h"\n#include'
        ' "resources/runtime_support.h"\n#include "soh/cvar_prefixes.h"\n#include'
        " <spdlog/spdlog.h>\n"
        + text
    )


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    generated = {}
    for n, digest in lock["sources"].items():
        text = (ROOT / n).read_text(encoding="utf-8-sig")
        assert sha(text) == digest, n
        text = project(n, text)
        stable(OUT / "generated" / n, text)
        generated[n] = sha(text)
    helpers = [
        ROOT / "tools/shipyard" / n
        for n in (
            "prepare_application_windows.py",
            "prepare_enhancements.py",
            "prepare_custom_message.py",
            "prepare_randomizer.py",
            "prepare_resource_manager.py",
            "cpp_ast.py",
        )
    ] + [ROOT / "platform/shipyard/input/lowering.py"]
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated=generated,
                full_units=UNITS,
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
    return [OUT / "generated/soh"] + window_includes()


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
    for n in UNITS:
        source = OUT / "generated" / n
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        row = dict(
            source=source.relative_to(ROOT).as_posix(),
            command=command,
            exit=r.returncode,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        if not r.returncode:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
            row["object_sha256"] = hashlib.sha256(obj.read_bytes()).hexdigest()
        else:
            print("\n".join(s for s in (r.stdout + r.stderr).splitlines() if "error " in s)[:2400])
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
