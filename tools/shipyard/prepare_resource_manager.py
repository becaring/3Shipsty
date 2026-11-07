"""Project the complete current archive/loader/cache classes, never substitutes."""

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
from prepare_filesystem import project_boundary, transform as directory_transform
from cpp_ast import PARSER, walk

OUT = ROOT / "scratch/resource-manager-xdk"
OWN = ROOT / "platform/shipyard/resources"
UNITS = [
    "resource/ResourceLoader.cpp",
    "resource/ResourceManager.cpp",
    *[
        "resource/archive/" + n + ".cpp"
        for n in (
            "Archive",
            "ArchiveManager",
            "O2rArchive",
            "FolderArchive",
            "OtrArchive",
        )
    ],
    "utils/StringHelper.cpp",
    "utils/Utils.cpp",
    "utils/glob.c",
    "utils/StrHash64.cpp",
]


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Expected exact single source pattern: " + old[:90])
    return text.replace(old, new)


def archive_hash_epoch_header(source):
    source = once(
        source,
        "    const char* HashToCString(uint64_t hash) const;",
        "    const char* HashToCString(uint64_t hash) const;\n"
        "    unsigned GetXboxHashEpoch() const;",
    )
    return once(
        source,
        "    std::unordered_map<uint64_t, std::string> mHashes;",
        "    volatile long mXboxHashEpoch;\n    std::unordered_map<uint64_t, std::string> mHashes;",
    )


def archive_hash_epoch_source(source):
    # Keep the pinned archive sources intact. Fail when a new hash-map write
    # appears so the epoch cannot silently miss an invalidation path.
    if source.count("mHashes[") != 2 or source.count("mHashes.clear();") != 1:
        raise ValueError("Archive hash map mutation inventory changed")
    source = once(
        source,
        "ArchiveManager::ArchiveManager() {",
        "ArchiveManager::ArchiveManager() : mXboxHashEpoch(1) {",
    )
    source = once(
        source,
        "    mHashes.clear();",
        "    InterlockedIncrement(&mXboxHashEpoch);\n    mHashes.clear();",
    )
    source = once(
        source,
        "            mHashes[hash] = filePath;",
        "            InterlockedIncrement(&mXboxHashEpoch);\n            mHashes[hash] = filePath;",
    )
    source = once(
        source,
        "    for (auto& [hash, filename] : *fileList.get()) {",
        "    InterlockedIncrement(&mXboxHashEpoch);\n"
        "    for (auto& [hash, filename] : *fileList.get()) {",
    )
    source = once(
        source,
        "const std::string* ArchiveManager::HashToString(uint64_t hash) const {",
        "unsigned ArchiveManager::GetXboxHashEpoch() const {\n"
        "    return static_cast<unsigned>(InterlockedCompareExchange(\n"
        "        const_cast<volatile long*>(&mXboxHashEpoch), 0, 0));\n"
        "}\n\n"
        "const std::string* ArchiveManager::HashToString(uint64_t hash) const {",
    )
    return (
        "#ifdef _XBOX\n#include <xtl.h>\n#else\n#include <windows.h>\n#endif\n" + source
    )


def syntax(text):
    # These are contextual specifiers, also legal identifiers. A textual
    # replacement corrupts e.g. EntranceHints' overrideIndex and data.override.
    raw = text.encode("utf-8")
    specifiers = [
        n
        for n in walk(PARSER.parse(raw).root_node)
        if n.type == "virtual_specifier" and n.text in (b"override", b"final")
    ]
    for node in sorted(specifiers, key=lambda n: n.start_byte, reverse=True):
        start = node.start_byte - (raw[node.start_byte - 1 : node.start_byte] == b" ")
        raw = raw[:start] + raw[node.end_byte :]
    text = raw.decode("utf-8")
    text = text.replace("std::variant<", "xbox_compat::variant<").replace(
        "std::get<", "xbox_compat::get<"
    )
    text = text.replace(
        "std::holds_alternative<", "xbox_compat::holds_alternative<"
    ).replace("std::bad_variant_access", "xbox_compat::bad_variant_access")
    text = text.replace(
        "#include <variant>", "#include <xbox_compat/variant.h>"
    ).replace("#include <mutex>", '#include "async/native.h"')
    text = text.replace("#include <thread>", '#include "thread-pool/native_support.h"')
    for name in ("mutex", "lock_guard", "shared_future", "promise"):
        text = text.replace("std::" + name, "Shipyard::Async::" + name)
    text = text.replace(
        "std::thread::hardware_concurrency()", "Shipyard::Async::hardware_concurrency()"
    )
    return text


def concurrent_cache(text):
    # SoH itself only ever runs one load at a time; object and scene prefetch
    # run several. Every cache map access takes mMutex, and the first
    # published instance of a path wins: game code keeps raw pointers into
    # cached resources (OTRPlay_LoadFile, scene commands), so replacing an
    # entry would free the instance it holds.
    text = once(
        text,
        "        mResourceCache[identifier] = ResourceLoadError::NotFound;\n"
        "        InterlockedIncrement(&mXboxLookupGeneration);\n"
        "        return nullptr;",
        "        {\n"
        "            const Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(mMutex);\n"
        "            mResourceCache[identifier] = ResourceLoadError::NotFound;\n"
        "        }\n"
        "        InterlockedIncrement(&mXboxLookupGeneration);\n"
        "        return nullptr;",
    )
    text = once(
        text,
        "        if (cachedResource != nullptr) {\n            // If another thread has already"
        " loaded this resource, discard the work we already did and return from\n            //"
        " cache.\n",
        "        const auto published = mResourceCache.find(identifier);\n        if (published !="
        " mResourceCache.end()) {\n            const std::shared_ptr<IResource> current ="
        " GetCachedResource(published->second);\n            if (current != nullptr) {\n           "
        "     cachedResource = current;\n            }\n        }\n        if (cachedResource !="
        " nullptr) {\n            // If another thread has already loaded this resource, discard"
        " the work we already did and return from\n            // cache.\n",
    )
    # Erase under the lock and destroy after it: a resource destructor may
    # load other resources.
    return once(
        text,
        "    if (Shipyard::Resources::contains(mResourceCache, identifier)) {\n"
        "        const Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(mMutex);\n"
        "        mResourceCache.erase(identifier);\n"
        "        InterlockedIncrement(&mXboxLookupGeneration);\n"
        "    }",
        "    {\n"
        "        const Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(mMutex);\n"
        "        const auto found = mResourceCache.find(identifier);\n"
        "        if (found != mResourceCache.end()) {\n"
        "            value = found->second;\n"
        "            mResourceCache.erase(found);\n"
        "            InterlockedIncrement(&mXboxLookupGeneration);\n"
        "        }\n"
        "    }",
    )


def transform(name, original):
    if name.endswith(("/glob.c", "/glob.h")):
        return original
    text = syntax(original)
    if "<filesystem>" in original or "__has_include" in original:
        text = syntax(project_boundary("libultraship/" + name, original))
    if name.endswith("/ArchiveManager.h"):
        text = archive_hash_epoch_header(text)
    if name.endswith("/ArchiveManager.cpp"):
        text = archive_hash_epoch_source(text)
    if name.endswith("/Context.h"):
        text = once(
            text,
            '#include "ship/audio/Audio.h"',
            '#include "ship/audio/AudioSettings.h"',
        )
        text = once(text, "class Console;", "class Audio;\nclass Console;")
        text = text.replace(
            "archivePaths = {}", "archivePaths = std::vector<std::string>()"
        )
        text = text.replace(
            "validHashes = {}", "validHashes = std::unordered_set<uint32_t>()"
        )
        text = text.replace(
            "audioSettings = {}", "audioSettings = AudioSettings()"
        ).replace("Context() = default;", "Context() {}")
    if name.endswith("/ResourceManager.h"):
        text = once(
            text,
            "    ~ResourceManager();",
            "    ~ResourceManager();\n"
            "    // Stop external producers and retain Context strongly while draining.\n"
            "    // Application thread only; never call from this pool.\n"
            "    void WaitForPendingTasks();",
        )
        for old, new in [
            ("Owner = 0", "Owner"),
            ("Parent = nullptr", "Parent"),
            ('Path = ""', "Path"),
            ("mAltAssetsEnabled = false", "mAltAssetsEnabled"),
            ("mDefaultCacheOwner = 0", "mDefaultCacheOwner"),
            ("mDefaultCacheArchive = nullptr", "mDefaultCacheArchive"),
        ]:
            text = text.replace(old, new)
        text = once(
            text,
            "typedef enum class ResourceLoadError { None, NotCached, NotFound } ResourceLoadError;",
            "struct ResourceLoadError : Shipyard::Binary::ScopedEnum<ResourceLoadError> {\nenum"
            " Value { None, NotCached, NotFound };\nResourceLoadError() {}\nResourceLoadError(Value"
            " value) : Shipyard::Binary::ScopedEnum<ResourceLoadError>(value) {}\n};",
        )
    if name.endswith("/ResourceManager.cpp"):
        text = once(
            text,
            "ResourceManager::~ResourceManager() {",
            "void ResourceManager::WaitForPendingTasks() {\n"
            "    if (mThreadPool != nullptr) {\n"
            "        // BS wait treats a paused queue as complete. Accepted jobs\n"
            "        // must run and release their captures while Context is alive.\n"
            "        mThreadPool->unpause();\n"
            "        mThreadPool->wait();\n"
            "    }\n"
            "}\n\n"
            "ResourceManager::~ResourceManager() {\n"
            "    WaitForPendingTasks();\n"
            "    // mMutex follows the pool in declaration order. Join the actual\n"
            "    // pool before automatic member destruction reaches that mutex.\n"
            "    mThreadPool.reset();",
        )
        text = once(
            text,
            '#include "ship/config/ConsoleVariable.h"',
            "// No ConsoleVariable symbols are used by this TU.",
        )
        text = once(
            text,
            "ResourceManager::ResourceManager() {",
            "ResourceManager::ResourceManager() : mAltAssetsEnabled(false), mDefaultCacheOwner(0),"
            " mDefaultCacheArchive(nullptr) {",
        )
        text = once(
            text,
            "    auto resource = LoadResourceAsync(identifier, loadExact, BS::pr::highest,"
            " initData).get();",
            "    // Synchronous cached callers need no promise, future or worker handoff.\n    //"
            " GetCachedResource applies the same alt-asset and dirty checks as\n    // the first"
            " step of LoadResourceAsync; misses retain its path.\n    auto cachedResource ="
            " GetCachedResource(identifier, loadExact);\n    if (cachedResource != nullptr) {\n    "
            "    return cachedResource;\n    }\n    auto resource = LoadResourceAsync(identifier,"
            " loadExact, BS::pr::highest, initData).get();",
        )
        text = text.replace(
            "std::hash<std::string>{}", "std::hash<std::string>()"
        ).replace("std::hash<std::uintptr_t>{}", "std::hash<uintptr_t>()")
        text = re.sub(
            r"\{ (\w+), (identifier\.Owner|filter\.Owner|mDefaultCacheOwner),"
            r" (identifier\.Parent|filter\.Parent|mDefaultCacheArchive) \}",
            r"ResourceIdentifier(\1, \2, \3)",
            text,
        )
        text = text.replace(
            "{ { searchMask }, {}, mDefaultCacheOwner, mDefaultCacheArchive }",
            "ResourceFilter(std::list<std::string>(1, searchMask), std::list<std::string>(),"
            " mDefaultCacheOwner, mDefaultCacheArchive)",
        )
        text = text.replace(
            "identifier.Path.starts_with(IResource::gAltAssetPrefix)",
            "Shipyard::Resources::starts_with(identifier.Path, IResource::gAltAssetPrefix)",
        )
    if name.endswith("/ResourceLoader.cpp"):
        text = text.replace(
            "ResourceFactoryKey key{ .resourceFormat = format, .resourceType = type,"
            " .resourceVersion = version };",
            "ResourceFactoryKey key = { format, type, version };",
        )
    if name.endswith("/ResourceLoader.h"):
        text = text.replace(
            '#include "ResourceType.h"', '#include "ship/resource/ResourceType.h"'
        )
    if name.endswith(("/Archive.cpp", "/O2rArchive.cpp", "/OtrArchive.cpp")):
        text = text.replace(
            '#include "ship/window/Window.h"',
            '#include "ship/resource/ResourceManager.h"',
        )
    if name.endswith("/O2rArchive.cpp"):
        # libzip may return a positive partial chunk. Keep the pinned upstream
        # source intact and complete the declared entry in the XDK projection.
        text = once(
            text,
            "    // Filesize 0, no logging needed\n"
            "    if (zipEntryStat.size == 0) {\n"
            '        SPDLOG_TRACE("Failed to load file {}; filesize 0", filePath, GetPath());\n'
            "        return nullptr;\n"
            "    }",
            "    // Filesize 0, no logging needed\n    if (zipEntryStat.size == 0) {\n       "
            ' SPDLOG_TRACE("Failed to load file {}; filesize 0", filePath, GetPath());\n       '
            " return nullptr;\n    }\n    if (zipEntryStat.size > std::vector<char>().max_size())"
            ' {\n        SPDLOG_TRACE("Failed to load file {}; filesize too large", filePath,'
            " GetPath());\n        return nullptr;\n    }",
        )
        text = once(
            text,
            "    fileToLoad->Buffer = std::make_shared<std::vector<char>>(zipEntryStat.size);\n\n  "
            "  if (zip_fread(zipEntryFile, fileToLoad->Buffer->data(), zipEntryStat.size) < 0) {\n "
            '       SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath,'
            " GetPath());\n    }",
            "    fileToLoad->Buffer ="
            " std::make_shared<std::vector<char>>(static_cast<size_t>(zipEntryStat.size));\n\n   "
            " zip_uint64_t bytesRead = 0;\n    while (bytesRead < zipEntryStat.size) {\n       "
            " const zip_uint64_t remaining = zipEntryStat.size - bytesRead;\n        const auto"
            " chunk = zip_fread(zipEntryFile, fileToLoad->Buffer->data() +"
            " static_cast<size_t>(bytesRead),\n                                     remaining);\n  "
            "      if (chunk <= 0 || static_cast<zip_uint64_t>(chunk) > remaining) {\n           "
            ' SPDLOG_TRACE("Error reading file {} in zip archive  {}.", filePath, GetPath());\n    '
            "        zip_fclose(zipEntryFile);\n            return nullptr;\n        }\n       "
            " bytesRead += static_cast<zip_uint64_t>(chunk);\n    }",
        )
        # libzip supports one thread per zip_t, and this archive has a single
        # shared handle. Object and scene prefetch load on several resource
        # workers at once; interleaved reads return failed or foreign entry
        # data, and the cache then records the path as NotFound for good (a
        # scene's collision header resolving to NULL in BgCheck_Allocate).
        # The mutex is at namespace scope, so it exists before any worker.
        text = once(
            text,
            "namespace Ship {\nO2rArchive::O2rArchive(",
            "namespace Ship {\nnamespace {\nShipyard::Async::mutex"
            " sXboxZipMutex;\n}\n\nO2rArchive::O2rArchive(",
        )
        for signature in (
            "std::shared_ptr<File> O2rArchive::LoadFile(const std::string& filePath) {\n",
            (
                "bool O2rArchive::WriteFile(const std::string& filePath, const"
                " std::vector<uint8_t>& data) {\n"
            ),
        ):
            text = once(
                text,
                signature,
                signature
                + "    const Shipyard::Async::lock_guard<Shipyard::Async::mutex>"
                " zipLock(sXboxZipMutex);\n",
            )
        text = '#include "async/native.h"\n' + text
    if name.endswith("/ArchiveManager.cpp"):
        # Lookups must not insert. operator[] adds an empty entry for every
        # missing hash (each alt/ probe of every load), mutating the map while
        # other resource workers read it; with prefetch that corrupted it.
        # Archives are added only during setup, so find() keeps runtime
        # lookups read-only and returns the same null for a missing file.
        text = once(
            text,
            "    auto archive = mFileToArchive[hash];\n    if (archive == nullptr) {",
            "    std::shared_ptr<Archive> archive;\n"
            "    const auto found = mFileToArchive.find(hash);\n"
            "    if (found != mFileToArchive.end()) {\n"
            "        archive = found->second;\n"
            "    }\n"
            "    if (archive == nullptr) {",
        )
        text = once(
            text,
            "    return mFileToArchive[CRC64(filePath.c_str())];",
            "    const auto found = mFileToArchive.find(CRC64(filePath.c_str()));\n"
            "    if (found == mFileToArchive.end()) {\n"
            "        return std::shared_ptr<Archive>();\n"
            "    }\n"
            "    return found->second;",
        )
        # Size both indices once per archive (oot.o2r holds tens of thousands
        # of entries) instead of rehashing repeatedly while inserting at boot.
        # VC10's unordered_map has rehash() but no reserve().
        text = once(
            text,
            "    const auto fileList = archive->ListFiles();\n   "
            " InterlockedIncrement(&mXboxHashEpoch);",
            "    const auto fileList = archive->ListFiles();\n   "
            " InterlockedIncrement(&mXboxHashEpoch);\n   "
            " mHashes.rehash(static_cast<size_t>((mHashes.size() + fileList->size()) /"
            " mHashes.max_load_factor()) + 1);\n   "
            " mFileToArchive.rehash(static_cast<size_t>((mFileToArchive.size() + fileList->size())"
            " / mFileToArchive.max_load_factor()) + 1);",
        )
        text = text.replace(
            "dynamic_pointer_cast<Archive>", "std::dynamic_pointer_cast<Archive>"
        )
        text = text.replace(
            "mValidGameVersions.contains(archive->GetGameVersion())",
            "Shipyard::Resources::contains(mValidGameVersions, archive->GetGameVersion())",
        )
        text = text.replace(
            "Init(archivePaths, {});",
            "Init(archivePaths, std::unordered_set<uint32_t>());",
        )
        text = text.replace(
            "std::vector<std::string> fileList = {};",
            "std::vector<std::string> fileList;",
        )
        text = text.replace(
            "ListFiles(includes, {});", "ListFiles(includes, std::list<std::string>());"
        )
        text = text.replace(
            "std::list<std::string> includes = {};", "std::list<std::string> includes;"
        )
        text = once(
            text,
            "for (const auto& p : xbox_compat::filesystem::directory_iterator(archivePath)) {",
            "for (xbox_compat::filesystem::directory_iterator cursor(archivePath), finish; cursor"
            " != finish; ++cursor) {\nconst xbox_compat::filesystem::directory_entry& p=*cursor;",
        )
        text = once(
            text,
            "for (const auto& [hash, path] : mHashes) {",
            "for (const auto& entry : mHashes) {\nconst uint64_t& hash=entry.first; const"
            " std::string& path=entry.second;",
        )
        text = once(
            text,
            "for (auto& [hash, filename] : *fileList.get()) {",
            "for (auto& entry : *fileList.get()) {\nconst uint64_t& hash=entry.first; std::string&"
            " filename=entry.second;",
        )
    if name.endswith("/Directory.h"):
        text = directory_transform(original).replace(
            '#include "filesystem.h"', '#include "filesystem/filesystem.h"'
        )
    if name.endswith("/Utils.cpp"):
        text = once(
            text, "if constexpr (sizeof(size_t) >= 8)", "if (sizeof(size_t) >= 8)"
        )
    if name.endswith("/FileHelper.h"):
        # XDK streams accept native narrow paths, not filesystem::path objects.
        text = text.replace("file(filePath,", "file(filePath.string(),")
        # These two overloads already accept std::string.
        text = text.replace(
            "std::ofstream file(filePath.string(), std::ios::binary);",
            "std::ofstream file(filePath, std::ios::binary);",
        )
        text = once(
            text,
            "static void WriteAllBytes(const fs::path& filePath, const std::vector<uint8_t>& data)"
            " {\n        std::ofstream file(filePath,",
            "static void WriteAllBytes(const fs::path& filePath, const std::vector<uint8_t>& data)"
            " {\n        std::ofstream file(filePath.string(),",
        )
    if name.endswith(("/StringHelper.h", "/StringHelper.cpp")):
        text = text.replace(
            "#include <string_view>", "#include <nonstd/string_view.hpp>"
        ).replace("std::string_view", "nonstd::string_view")
        text = text.replace("std::strtoull(", "_strtoui64(")
        text = text.replace(
            "std::equal(a.begin(), a.end(), b.begin(), b.end(),",
            "(a.size() == b.size()) && std::equal(a.begin(), a.end(), b.begin(),",
        )
    if name.endswith("/OtrArchive.cpp"):
        text = text.replace("std::string_view", "nonstd::string_view").replace(
            "std::string(line);", "std::string(line.data(), line.size());"
        )
        # XDK CreateFile rejects '/', and mod paths arrive as game:/mods/...;
        # libzip gets the same conversion in Shipyard's native boundary.
        text = once(
            text,
            "    const bool opened = SFileOpenArchive(GetPath().c_str(), 0, MPQ_OPEN_READ_ONLY, &mHandle);",
            "    std::string nativePath = GetPath();\n"
            "    std::replace(nativePath.begin(), nativePath.end(), '/', '\\\\');\n"
            "    const bool opened = SFileOpenArchive(nativePath.c_str(), 0, MPQ_OPEN_READ_ONLY, &mHandle);",
        )
        text = once(text, '#include "spdlog/spdlog.h"', '#include "spdlog/spdlog.h"\n#include <algorithm>')
    # Only container lookups (not JSON) in these locked current TUs.
    text = re.sub(
        r"\b(mResourceTypes|mFactories|mResourceCache|mValidGameVersions|mHashes|mFileToArchive|mDirectories)\.contains\(([^()]*)\)",
        r"Shipyard::Resources::contains(\1, \2)",
        text,
    )
    lower_ranges = runpy.run_path(str(ROOT / "platform/shipyard/imgui/projection.py"))[
        "lower_ranges"
    ]
    text = lower_ranges(
        text.encode(), "Shipyard::Resources::begin", "Shipyard::Resources::end"
    ).decode()
    if name.endswith("/ResourceManager.h"):
        from platform_base import resolve

        resolve(ROOT)
        from xbox360_platform.resource_lookup import (
            borrowed_cache_header,
            lookup_generation_header,
            settled_alternate_header,
        )

        text = settled_alternate_header(
            lookup_generation_header(borrowed_cache_header(text))
        )
    if name.endswith("/ResourceManager.cpp"):
        from platform_base import resolve

        resolve(ROOT)
        from xbox360_platform.resource_lookup import (
            path_hash,
            borrowed_cache_source,
            lookup_generation_source,
            settled_alternate_source,
        )

        # lookup_cost_projection applies this game's settled fills to the per-load form.
        text = settled_alternate_source(
            lookup_generation_source(borrowed_cache_source(path_hash(text)), stable_fills=False)
        )
        from frame_profile_projection import resource_lookup as profile_resource_lookup

        text = profile_resource_lookup(text)
        text = '#ifdef _XBOX\n#include "application/frame_profile.h"\n#endif\n' + text
        text = once(
            text,
            "            return LoadResourceProcess(identifier, loadExact, initData);",
            """#ifdef _XBOX
            ModernFrameProfile::ObserveResourceWorker();
#endif
            return LoadResourceProcess(identifier, loadExact, initData);""",
        )
        # A synchronous miss loads on the calling thread. Handing it to a pool
        # worker and blocking on the future adds two cross-core wakeups per
        # resource and waits for a worker to finish its current (prefetch)
        # job; an actor's first draw can need a hundred resources in a row.
        # LoadResourceProcess is the worker body itself: the cache and zip
        # locks make it safe on any thread, and the first published instance
        # still wins a race with a concurrent prefetch of the same path.
        text = once(
            text,
            "    auto resource = LoadResourceAsync(identifier, loadExact, BS::pr::highest,"
            " initData).get();",
            """    std::shared_ptr<IResource> resource;
    {
#ifdef _XBOX
        ModernFrameProfile::ResourceWaitScope resourceWait;
#endif
        resource = LoadResourceProcess(identifier, loadExact, initData);
    }""",
        )
        text = concurrent_cache(text)
        from overlap_lifetime_projection import resource_manager as overlap_resources

        text = overlap_resources(text)
        from resource_return_projection import resource_manager as resource_returns

        text = resource_returns(text)
        from resource_cpu_projection import source as resource_cpu

        text = resource_cpu(text)
        from lookup_cost_projection import resource_manager as lookup_cost

        text = lookup_cost(text)
    return '#include "resources/runtime_support.h"\n' + text


def prepare_lifecycle():
    """Update only the two canonical ResourceManager lifecycle projections."""
    lock = json.loads((OWN / "runtime-sources.lock.json").read_text())
    for name, expected in lock["helpers"].items():
        if (
            hashlib.sha256(
                (ROOT / name).read_text(encoding="utf-8-sig").encode()
            ).hexdigest()
            != expected
        ):
            raise ValueError("Resource projection helper drift: " + name)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in [
        "include/ship/resource/ResourceManager.h",
        "src/ship/resource/ResourceManager.cpp",
    ]:
        original = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(original.encode()).hexdigest() != lock["sources"][name]:
            raise ValueError("Resource source drift: " + name)
        projected = transform(name, original)
        stable(OUT / "generated" / name, projected)
        manifest[name] = hashlib.sha256(projected.encode()).hexdigest()
    stable(manifest_path, json.dumps(manifest, indent=2) + "\n")


def prepare():
    lock = json.loads((OWN / "runtime-sources.lock.json").read_text())
    for name, expected in lock["helpers"].items():
        if (
            hashlib.sha256(
                (ROOT / name).read_text(encoding="utf-8-sig").encode()
            ).hexdigest()
            != expected
        ):
            raise ValueError("Resource projection helper drift: " + name)
    pending = {}
    for name, expected in lock["sources"].items():
        original = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(original.encode()).hexdigest() != expected:
            raise ValueError("Source drift: " + name)
        pending[name] = transform(name, original)
    # Extract the actual value type, avoiding Audio's unnecessary transitive
    # backend headers in Context. AudioPlayer will consume this same definition.
    original = (ROOT / "libultraship/include/ship/audio/AudioPlayer.h").read_text()
    if hashlib.sha256(original.encode()).hexdigest() != lock["audio_player_sha256"]:
        raise ValueError("AudioSettings source drift")
    block = re.search(r"struct AudioSettings \{.*?\n\};", original, re.S)[0]
    members = re.findall(r"^    (\w+) (\w+) = ([^;]+);", block, re.M)
    if len(members) != 4:
        raise ValueError("AudioSettings members changed")
    block = re.sub(r" = [^;]+;", ";", block)
    block = block.replace(
        "struct AudioSettings {",
        "struct AudioSettings {\n    AudioSettings() : "
        + ", ".join(n + "(" + v + ")" for t, n, v in members)
        + " {}",
    )
    pending["include/ship/audio/AudioSettings.h"] = (
        '#pragma once\n#include <stdint.h>\n#include "ship/audio/AudioChannelsSetting.h"\nnamespace'
        " Ship {\n" + block + "\n}\n"
    )
    channels = (
        ROOT / "libultraship/include/ship/audio/AudioChannelsSetting.h"
    ).read_text()
    if hashlib.sha256(channels.encode()).hexdigest() != lock["audio_channels_sha256"]:
        raise ValueError("Audio channels declaration drift")
    pending["include/ship/audio/AudioChannelsSetting.h"] = channels
    # Exact official string_view backport; no injection into namespace std.
    view = verified("string-view-lite")
    pending["include/nonstd/string_view.hpp"] = (
        view / "include/nonstd/string_view.hpp"
    ).read_text()
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            {
                name: hashlib.sha256(text.encode()).hexdigest()
                for name, text in pending.items()
            },
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_resources.py"))
    inc = (
        [OUT / "generated/include", ROOT / "platform/shipyard/game/include"]
        + env["includes"](True)
        + [
            ROOT / "scratch/async-xdk/generated",
            ROOT / "scratch/libzip-xdk/generated",
            ROOT / "scratch/deps/tinyxml2",
            ROOT / "scratch/stormlib-xdk/generated/src",
            ROOT / "libultraship/include",
        ]
    )
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = [
        "/nologo",
        "/c",
        "/EHsc",
        "/GR",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DINCLUDE_MPQ_SUPPORT",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/Dnssv_CONFIG_SELECT_STRING_VIEW=1",
        "/I" + str(sdk / "include/xbox"),
    ] + ["/I" + str(p) for p in inc]
    records = []
    for name in UNITS:
        source = OUT / "generated/src/ship" / name
        obj = folder / (name.replace("/", "__").rsplit(".", 1)[0] + ".obj")
        if source.suffix == ".c":
            # Keep real C semantics (glob uses a local named `class`). Reuse
            # the already-verified semantic C projection after preprocessing.
            preprocessed = obj.with_suffix(".i")
            precommand = (
                [str(sdk / "bin/win32/cl.exe")]
                + [f for f in flags if f != "/c"]
                + ["/TC", "/P", "/Fi" + str(preprocessed), str(source)]
            )
            result = subprocess.run(
                precommand, cwd=ROOT, capture_output=True, text=True
            )
            stable(obj.with_suffix(".preprocess.log"), result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError("C preprocessing failed: " + name)
            from prepare_game import lower_c

            projected, statistics = lower_c(preprocessed.read_bytes())
            source = obj.with_suffix(".c")
            source.write_bytes(projected)
        command = (
            [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        )
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        records.append(dict(source=name, exit=result.returncode, command=command))
        if (
            not result.returncode
            and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2
        ):
            raise ValueError("Not a Xenon object")
    stable(folder / "report.json", json.dumps(records, indent=2) + "\n")
    for record in records:
        print(str(record["exit"]) + " " + record["source"])
    if any(r["exit"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--lifecycle-only", action="store_true")
    args = parser.parse_args()
    if args.build and args.lifecycle_only:
        parser.error("Choose --build or --lifecycle-only")
    if args.lifecycle_only:
        prepare_lifecycle()
    elif args.build:
        build()
    else:
        prepare()
