"""Resolve per-presentation OTR resource commands without upstream's lookup chain.

Every replayed G_DL_OTR_HASH, G_BRANCH_Z_OTR, G_MTX_OTR, G_MOVEMEM (OTR) and
OTR file-path command calls ResourceManager::GetResourceRawPointer, which
locks Context, copies the manager, resolves the CRC to a path, builds owning
ResourceIdentifier strings (plus an "alt/" string and second identifier while
alternate assets are enabled), locks the cache mutex per probe and copies the
result shared_ptr. Interpolation replays each display list per presentation.

Hits are certified exactly like the existing Xbox texture hash cache: the
archive hash-table epoch covers hash->path, and the manager lookup generation
plus the resource's dirty flag cover path->resource. Misses call upstream's
LoadResource unchanged. The G_VTX_OTR_HASH handler is left alone; it already
patches its own command with the resolved pointer after the first lookup.
"""


def _once(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Resource resolution anchor changed: ' + old[:90])
    return text.replace(old, new)


def _method(text, signature):
    if text.count(signature) != 1:
        raise ValueError('Resource resolution method changed: ' + signature)
    start = text.index(signature)
    end = text.index('\n}', start) + 2
    return start, end


def _edit_method(text, signature, edits):
    start, end = _method(text, signature)
    body = text[start:end]
    for old, new, count in edits:
        body = _once(body, old, new, count)
    return text[:start] + body + text[end:]


MEMBER = '    Shipyard::Resources::TextureHashCache<Ship::IResource> mXboxResolvedResources;\n'

HELPERS = r'''

// Run-scoped borrows of the Context-owned resource and archive managers.
// Upstream re-acquires both through Context::GetInstance and shared_ptr copies
// (atomic reference counts) in every resource command of every presentation.
static __declspec(thread) Ship::ResourceManager* sXboxRunResourceManager = 0;
static __declspec(thread) Ship::ArchiveManager* sXboxRunArchiveManager = 0;
struct XboxRunResourceScope {
    std::shared_ptr<Ship::ResourceManager> resources;
    std::shared_ptr<Ship::ArchiveManager> archives;
    Ship::ResourceManager* previousResources;
    Ship::ArchiveManager* previousArchives;
    XboxRunResourceScope()
        : previousResources(sXboxRunResourceManager), previousArchives(sXboxRunArchiveManager) {
        const std::shared_ptr<Ship::Context> context = Ship::Context::GetInstance();
        if (context) resources = context->GetResourceManager();
        if (resources) archives = resources->GetArchiveManager();
        sXboxRunResourceManager = resources.get();
        sXboxRunArchiveManager = archives.get();
    }
    ~XboxRunResourceScope() {
        sXboxRunResourceManager = previousResources;
        sXboxRunArchiveManager = previousArchives;
    }
  private:
    XboxRunResourceScope(const XboxRunResourceScope&);
    XboxRunResourceScope& operator=(const XboxRunResourceScope&);
};
static __declspec(noinline) Ship::ResourceManager* XboxResourceManagerFallback() {
    return Ship::Context::GetInstance()->GetResourceManager().get();
}
static __declspec(noinline) Ship::ArchiveManager* XboxArchiveManagerFallback(Ship::ResourceManager* manager) {
    return manager->GetArchiveManager().get();
}
static __forceinline Ship::ResourceManager* XboxRunResourceManager() {
    Ship::ResourceManager* const manager = sXboxRunResourceManager;
    return manager ? manager : XboxResourceManagerFallback();
}
static __forceinline Ship::ArchiveManager* XboxRunArchiveManager(Ship::ResourceManager* manager) {
    Ship::ArchiveManager* const archives = sXboxRunArchiveManager;
    return archives && manager == sXboxRunResourceManager ? archives : XboxArchiveManagerFallback(manager);
}

// Same result as ResourceManager::GetResourceRawPointer(hash). The cache entry
// owns the resource; its raw pointer is re-read on every hit.
static void* XboxResolveResourceHash(uint64_t hash) {
    Interpreter* gfx = XboxDispatchInterpreter();
    Ship::ResourceManager* const manager = XboxRunResourceManager();
    if (!gfx)
        return manager->GetResourceRawPointer(hash);
    Ship::ArchiveManager* const archives = XboxRunArchiveManager(manager);
    const unsigned epoch = archives->GetXboxHashEpoch();
    const unsigned generation = manager->GetXboxLookupGeneration();
    const auto* hit = gfx->mXboxResolvedResources.LookupArchive(hash, archives, epoch, generation);
    if (hit)
        return hit->texture->GetRawPointer();
    const std::shared_ptr<Ship::IResource> resource = manager->LoadResource(hash);
    if (!resource)
        return NULL;
    const char* path = archives->HashToCString(hash);
    if (path && !resource->IsDirty() && manager->GetXboxLookupGeneration() == generation &&
        archives->GetXboxHashEpoch() == epoch)
        gfx->mXboxResolvedResources.StoreArchive(hash, path, generation, archives, epoch, resource);
    return resource->GetRawPointer();
}

// Same result as ResourceManager::GetResourceRawPointer(path). Keys are the
// command's string address; every hit also compares the complete path text.
static void* XboxResolveResourcePath(const char* path) {
    Interpreter* gfx = XboxDispatchInterpreter();
    Ship::ResourceManager* const manager = XboxRunResourceManager();
    if (!gfx)
        return manager->GetResourceRawPointer(path);
    const unsigned generation = manager->GetXboxLookupGeneration();
    const uint64_t key = static_cast<uint64_t>(reinterpret_cast<uintptr_t>(path));
    const std::shared_ptr<Ship::IResource>* hit =
        path ? gfx->mXboxResolvedResources.LookupBorrowed(key, path, generation) : NULL;
    if (hit)
        return (*hit)->GetRawPointer();
    const std::shared_ptr<Ship::IResource> resource = manager->LoadResource(path);
    if (!resource)
        return NULL;
    if (!resource->IsDirty() && manager->GetXboxLookupGeneration() == generation)
        gfx->mXboxResolvedResources.Store(key, path, generation, resource);
    return resource->GetRawPointer();
}'''

UPSTREAM_HASH = 'Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash)'
UPSTREAM_PATH = 'Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer((const char*)fileName)'
UPSTREAM_PATH_WRAPPED = ('Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(\n'
                         '        (const char*)fileName)')


def header(text):
    anchor = '    Shipyard::Resources::TextureHashCache<Fast::Texture> mXboxTextureHashCache;\n'
    return _once(text, anchor, anchor + MEMBER)


def transform(text):
    text = _once(text, '    return XboxDispatchOwner::TemporaryBorrow(mInstance);\n}',
                 '    return XboxDispatchOwner::TemporaryBorrow(mInstance);\n}' + HELPERS)
    text = _once(text, '    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);\n',
                 '    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);\n'
                 '    XboxRunResourceScope xboxRunResources;\n')
    for signature in ('void Interpreter::TextureCacheClear() {', 'void Interpreter::RunGuiOnly() {'):
        text = _once(text, signature, signature + '\n    mXboxResolvedResources.Clear();')
    hash_resolution = [(UPSTREAM_HASH, 'XboxResolveResourceHash(hash)', 1)]
    for signature in ('bool gfx_mtx_otr_handler_custom_f3dex2(F3DGfx** cmd0) {',
                      'bool gfx_mtx_otr_handler_custom_f3d(F3DGfx** cmd0) {',
                      'bool gfx_dl_otr_hash_handler_custom(F3DGfx** cmd0) {',
                      'bool gfx_branch_z_otr_handler_f3dex2(F3DGfx** cmd0) {'):
        text = _edit_method(text, signature, hash_resolution)
    text = _edit_method(text, 'bool gfx_movemem_handler_otr(F3DGfx** cmd0) {',
                        [(UPSTREAM_HASH, 'XboxResolveResourceHash(hash)', 2)])
    for signature in ('bool gfx_mtx_otr_filepath_handler_custom_f3dex2(F3DGfx** cmd0) {',
                      'bool gfx_mtx_otr_filepath_handler_custom_f3d(F3DGfx** cmd0) {'):
        text = _edit_method(text, signature, [(UPSTREAM_PATH_WRAPPED,
                                               'XboxResolveResourcePath(\n        (const char*)fileName)', 1)])
    for signature in ('bool gfx_vtx_otr_filepath_handler_custom(F3DGfx** cmd0) {',
                      'bool gfx_dl_otr_filepath_handler_custom(F3DGfx** cmd0) {'):
        text = _edit_method(text, signature, [(UPSTREAM_PATH, 'XboxResolveResourcePath((const char*)fileName)', 1)])
    # Texture commands keep their existing cache; only the per-command manager
    # acquisitions become the Run-scoped borrows.
    text = _edit_method(text, 'bool gfx_set_timg_otr_hash_handler_custom(F3DGfx** cmd0) {', [
        ('    const auto resourceManager = Ship::Context::GetInstance()->GetResourceManager();',
         '    Ship::ResourceManager* const resourceManager = XboxRunResourceManager();', 1),
        ('    const auto archiveManager = resourceManager->GetArchiveManager();',
         '    Ship::ArchiveManager* const archiveManager = XboxRunArchiveManager(resourceManager);', 1),
        ('archiveManager.get()', 'archiveManager', 4),
    ])
    text = _edit_method(text, 'bool gfx_set_timg_handler_rdp(F3DGfx** cmd0) {', [
        ('            const auto resourceManager = Ship::Context::GetInstance()->GetResourceManager();',
         '            Ship::ResourceManager* const resourceManager = XboxRunResourceManager();', 1),
    ])
    if UPSTREAM_HASH not in text:
        raise ValueError('The self-patching vertex hash command should retain its upstream lookup')
    return text
