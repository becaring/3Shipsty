"""Keep per-frame resource name lookups on settled cache hits.

Misses and first loads do not move the lookup generation: they only fill keys
a settled lookup could not have consulted. Recorded misses stay misses, the game
thread memoizes the static names draw code resolves every frame, and texture
loads reuse each resource's blended-mask answer.
"""


def once(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError("Expected lookup anchor %d time(s): %s" % (count, old))
    return text.replace(old, new)


MEMO = r'''
extern "C" int Shipyard_OverlapIsGameWorker(void);
static Ship::ResourceManager* sMemoManager;
namespace {
struct NameMemo {
    const char* name;
    unsigned generation, variant;
    std::string path;
    std::shared_ptr<Ship::IResource> resource;
};
// Never destroyed: resources may call back into a manager torn down first at exit.
NameMemo* const sNameMemo = new NameMemo[1024]();
}
// Game-thread memo for names draw code resolves every frame. Pointers key the
// slot; the text and generation decide validity, and entries own their resource.
std::shared_ptr<Ship::IResource> Shipyard_MemoResource(const char* name, unsigned variant,
    std::shared_ptr<Ship::IResource> (*resolve)(const char*)) {
    if (!sMemoManager || !Shipyard_OverlapIsGameWorker())
        return resolve ? resolve(name) : Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess(name);
    const uintptr_t address = reinterpret_cast<uintptr_t>(name);
    NameMemo& memo = sNameMemo[((address >> 2) ^ (address >> 12) ^ (variant * 977)) & 1023];
    const unsigned generation = sMemoManager->GetXboxLookupGeneration();
    if (memo.name == name && memo.variant == variant && memo.generation == generation && memo.resource &&
        memo.path == name)
        return Shipyard_OverlapKeepResource(memo.resource);
    std::shared_ptr<Ship::IResource> resource = resolve ? resolve(name) : sMemoManager->LoadResourceProcess(name);
    if (!resource) return resource;
    memo.name = name;
    memo.variant = variant;
    memo.generation = generation;
    memo.path = name;
    memo.resource = resource;
    return resource;
}
'''

DECLARATION = (
    "std::shared_ptr<Ship::IResource> Shipyard_MemoResource(const char* name, unsigned variant,\n"
    "    std::shared_ptr<Ship::IResource> (*resolve)(const char*));\n"
)


def resource_manager(text):
    text = once(text, "\nnamespace Ship {\n", MEMO + "\nnamespace Ship {\n")
    text = once(text, "mDefaultCacheArchive(nullptr) {\n", "mDefaultCacheArchive(nullptr) {\n    sMemoManager = this;\n")
    text = once(text, "ResourceManager::~ResourceManager() {\n",
                "ResourceManager::~ResourceManager() {\n    if (sMemoManager == this) sMemoManager = NULL;\n")
    text = once(text, """\
    // Check for resource load errors which can indicate an alternate asset.""", """\
    // Archives do not change under a recorded miss; unloads erase the entry first.
    if (xbox_compat::holds_alternative<ResourceLoadError>(cacheLine) &&
        xbox_compat::get<ResourceLoadError>(cacheLine) == ResourceLoadError::NotFound) {
        return nullptr;
    }

    // Check for resource load errors which can indicate an alternate asset.""")
    text = once(text, """\
        }
        InterlockedIncrement(&mXboxLookupGeneration);
        return nullptr;""", """\
        }
        return nullptr;""")
    text = once(text, """\
        const auto published = mResourceCache.find(identifier);
""", """\
        const auto published = mResourceCache.find(identifier);
        // Filling an absent or missing key cannot change a settled lookup.
        const bool replaces = published != mResourceCache.end() &&
            xbox_compat::holds_alternative<std::shared_ptr<IResource>>(published->second);
""")
    text = once(text, """\
        }
        InterlockedIncrement(&mXboxLookupGeneration);
    }

    if (resource != nullptr) {""", """\
        }
        if (replaces) InterlockedIncrement(&mXboxLookupGeneration);
    }

    if (resource != nullptr) {""")
    text = once(text, "    auto resource = LoadResource(name);\n",
                "    auto resource = Shipyard_MemoResource(name, 0, NULL);\n", count=3)
    return text


def resource_bridge(text):
    text = once(text, "std::shared_ptr<Ship::IResource> ResourceLoad(const char* name) {\n"
                "    return Ship::Context::GetInstance()->GetResourceManager()->LoadResource(name);",
                DECLARATION + "std::shared_ptr<Ship::IResource> ResourceLoad(const char* name) {\n"
                "    return Shipyard_MemoResource(name, 0, NULL);")
    return text


def helpers(text):
    text = once(text, """\
std::shared_ptr<Ship::IResource> ResourceMgr_GetResourceByNameHandlingMQ(const char* path) {
    std::string Path = path;
    if (ResourceMgr_IsGameMasterQuest()) {""", DECLARATION + """\
static std::shared_ptr<Ship::IResource> ResolveNameHandlingMQ(const char* path) {
    std::string Path = path;
    {""")
    text = once(text, """\
    return Ship::Context::GetInstance()->GetResourceManager()->LoadResource(Path);
}
""", """\
    return Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess(Path.c_str());
}

std::shared_ptr<Ship::IResource> ResourceMgr_GetResourceByNameHandlingMQ(const char* path) {
    if (ResourceMgr_IsGameMasterQuest()) return Shipyard_MemoResource(path, 1, ResolveNameHandlingMQ);
    return Shipyard_MemoResource(path, 0, NULL);
}
""")
    start = text.index('extern "C" Gfx* ResourceMgr_LoadGfxByName(const char* path) {')
    end = text.index("\n}\n", start) + 3
    body = text[start:end]
    body = once(body, 'extern "C" Gfx* ResourceMgr_LoadGfxByName(const char* path) {',
                "static std::shared_ptr<Ship::IResource> ResolveGfx(const char* path) {")
    body = once(body, """\
        if (cached) {
            auto displayList = std::static_pointer_cast<Fast::DisplayList>(cached);
            return (Gfx*)&displayList->Instructions[0];
        }""", "        if (cached) return cached;")
    body = once(body, """\
        auto raw = std::static_pointer_cast<Fast::DisplayList>(manager->GetCachedResource(std::string(path)));
        if (raw != nullptr) return (Gfx*)&raw->Instructions[0];
        auto res = std::static_pointer_cast<Fast::DisplayList>(manager->LoadResourceProcess(path + 7));
        return (Gfx*)&res->Instructions[0];""", """\
        auto raw = manager->GetCachedResource(std::string(path));
        if (raw != nullptr) return raw;
        return manager->LoadResourceProcess(path + 7);""")
    body = once(body, """\
    auto res = std::static_pointer_cast<Fast::DisplayList>(ResourceMgr_GetResourceByNameHandlingMQ(path));
    return (Gfx*)&res->Instructions[0];""", "    return ResourceMgr_GetResourceByNameHandlingMQ(path);")
    body += """
extern "C" Gfx* ResourceMgr_LoadGfxByName(const char* path) {
    auto res = std::static_pointer_cast<Fast::DisplayList>(
        Shipyard_MemoResource(path, ResourceMgr_IsGameMasterQuest() ? 3 : 2, ResolveGfx));
    return (Gfx*)&res->Instructions[0];
}
"""
    return text[:start] + body + text[end:]


MASK_BLOCK = """\
        const std::string& texPath =
            mRdp->texture_to_load.raw_tex_metadata.resource != nullptr
                ? GetBaseTexturePath(mRdp->texture_to_load.raw_tex_metadata.resource->GetInitData()->Path)
                : "";
        auto maskedTextureIter = mMaskedTextures.find(texPath);
        if (maskedTextureIter != mMaskedTextures.end()) {
            mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].masked = true;
            mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].blended =
                maskedTextureIter->second.replacementData != nullptr;
        } else {
            mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].masked = false;
            mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].blended = false;
        }
"""

MASK_MEMO = """\
        const std::shared_ptr<Fast::Texture>& resource = mRdp->texture_to_load.raw_tex_metadata.resource;
        XboxMaskMemo& memo = sXboxMaskMemo[(reinterpret_cast<uintptr_t>(resource.get()) >> 4) & 255];
        if (memo.epoch != sXboxMaskEpoch || memo.resource != resource.get() ||
            (resource != nullptr && memo.path != resource->GetInitData()->Path)) {
            const std::string& texPath = resource != nullptr ? GetBaseTexturePath(resource->GetInitData()->Path) : "";
            auto maskedTextureIter = mMaskedTextures.find(texPath);
            memo.epoch = sXboxMaskEpoch;
            memo.resource = resource.get();
            memo.path = resource != nullptr ? resource->GetInitData()->Path : std::string();
            memo.masked = maskedTextureIter != mMaskedTextures.end();
            memo.blended = memo.masked && maskedTextureIter->second.replacementData != nullptr;
        }
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].masked = memo.masked;
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].blended = memo.blended;
"""


def interpreter(text):
    text = once(text, "std::string Interpreter::GetBaseTexturePath(const std::string& path) {", """\
// Blended-texture registrations persist for the session and rarely change, so
// each texture load reuses its resource's answer. Paths guard reused addresses.
static unsigned sXboxMaskEpoch = 1;
namespace {
struct XboxMaskMemo {
    unsigned epoch;
    const void* resource;
    std::string path;
    bool masked, blended;
};
XboxMaskMemo* const sXboxMaskMemo = new XboxMaskMemo[256]();
}

std::string Interpreter::GetBaseTexturePath(const std::string& path) {""")
    text = once(text, MASK_BLOCK, MASK_MEMO, count=2)
    text = once(text, "    MaskedTextureEntry entry = { mask, replacement };\n    mMaskedTextures[name] = entry;\n", """\
    MaskedTextureEntry entry = { mask, replacement };
    const auto current = mMaskedTextures.find(name);
    if (current != mMaskedTextures.end() && current->second.mask == mask &&
        current->second.replacementData == replacement)
        return;
    mMaskedTextures[name] = entry;
    ++sXboxMaskEpoch;
""")
    return once(text, "    mMaskedTextures.erase(name);\n",
                "    if (mMaskedTextures.erase(name)) ++sXboxMaskEpoch;\n")
