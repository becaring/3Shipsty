using namespace Ship;
static bool sameLine(const ResourceManager::Line& a, const ResourceManager::Line& b) {
    if (xbox_compat::holds_alternative<std::shared_ptr<IResource>>(a))
        return xbox_compat::holds_alternative<std::shared_ptr<IResource>>(b) &&
            xbox_compat::get<std::shared_ptr<IResource>>(a) == xbox_compat::get<std::shared_ptr<IResource>>(b);
    return xbox_compat::holds_alternative<ResourceManager::ResourceLoadError>(b) &&
        xbox_compat::get<ResourceManager::ResourceLoadError>(a) == xbox_compat::get<ResourceManager::ResourceLoadError>(b);
}

int main() {
    const std::string path = "objects/long_resource_name_with_more_than_small_string_bytes";
    auto clean = std::make_shared<IResource>(), dirty = std::make_shared<IResource>();
    auto loaded = std::make_shared<IResource>(), decoy = std::make_shared<IResource>();
    dirty->dirty = true;
    auto archive = std::make_shared<Archive>(), otherArchive = std::make_shared<Archive>();
    archive->path = otherArchive->path = "identical_archive_path_distinct_identity";
    auto init = std::make_shared<ResourceInitData>();
    unsigned cases = 0;
    for (unsigned alt = 0; alt < 7; ++alt) for (unsigned base = 0; base < 7; ++base)
    for (unsigned mode = 0; mode < 6; ++mode) for (unsigned owner = 0; owner < 2; ++owner)
    for (unsigned enabled = 0; enabled < 2; ++enabled) for (unsigned exact = 0; exact < 2; ++exact)
    for (unsigned io = 0; io < 3; ++io) {
        ResourceManager expected, actual;
        std::string request = mode == 1 ? "__OTR__" + path : mode == 2 ? "__OTR____OTR__" + path :
                              mode == 3 ? "alt/" + path : mode == 4 ? path + std::string("\0suffix", 7) : path;
        if (mode == 5) request = std::string("\0", 1) + path;
        for (auto* manager : { &expected, &actual }) {
            manager->mDefaultCacheOwner = owner ? 17 : 0;
            manager->mDefaultCacheArchive = owner ? archive : nullptr;
            manager->mAltAssetsEnabled = enabled != 0;
            manager->files = io != 0;
            manager->loaded = io == 2 ? loaded : nullptr;
            for (unsigned side = 0; side < 2; ++side) {
                unsigned state = side ? alt : base;
                std::string name = (side ? "alt/" : "") + request;
                ResourceIdentifier key(name, manager->mDefaultCacheOwner, manager->mDefaultCacheArchive);
                if (state == 1) manager->mResourceCache[key] = ResourceManager::ResourceLoadError::None;
                if (state == 2) manager->mResourceCache[key] = ResourceManager::ResourceLoadError::NotFound;
                if (state == 3) manager->mResourceCache[key] = ResourceManager::ResourceLoadError::NotCached;
                if (state == 4) manager->mResourceCache[key] = clean;
                if (state == 5) manager->mResourceCache[key] = dirty;
                if (state == 6) manager->mResourceCache[key] = std::shared_ptr<IResource>();
                manager->mResourceCache[ResourceIdentifier(name, 999, manager->mDefaultCacheArchive)] = decoy;
                manager->mResourceCache[ResourceIdentifier(name, manager->mDefaultCacheOwner, otherArchive)] = decoy;
            }
        }
        auto reference = expected.ReferenceCheckCache(request, exact != 0);
        const size_t before = allocations;
        auto result = actual.CheckCache(request, exact != 0);
        assert(allocations == before && sameLine(reference, result));
        ResourceIdentifier key(request, actual.mDefaultCacheOwner, actual.mDefaultCacheArchive);
        reference = expected.ReferenceCheckCache(key, exact != 0);
        const size_t identifierBefore = allocations;
        result = actual.CheckCache(key, exact != 0);
        assert(allocations == identifierBefore && sameLine(reference, result));
        auto expectedResource = expected.ReferenceLoadResource(request, exact != 0, init);
        auto actualResource = actual.LoadResource(request, exact != 0, init);
        assert(expectedResource == actualResource);
        assert(expected.reads == actual.reads && expected.loads == actual.loads && expected.lastInit == actual.lastInit);
        assert(expected.mResourceCache.size() == actual.mResourceCache.size());
        for (const auto& entry : expected.mResourceCache) {
            auto found = actual.mResourceCache.find(entry.first);
            assert(found != actual.mResourceCache.end() && sameLine(entry.second, found->second));
        }
        ++cases;
    }
    ResourceManager warm;
    warm.mResourceCache[ResourceIdentifier(path, 0, {})] = clean;
    warm.mResourceCache[ResourceIdentifier("alt/" + path, 0, {})] = ResourceManager::ResourceLoadError::NotFound;
    const size_t before = allocations;
    for (unsigned i = 0; i < 1000; ++i) assert(warm.LoadResource(path) == clean);
    assert(allocations == before);
    std::printf("PASS %u resource differentials: all 49 cache states, prefixes/NUL, owner/archive identity, "
                "IO/dirty/null; warm lookup zero allocations\n", cases);

    ResourceOwners owners;
    ResourceOwners renderStorage;
    renderStorage.reserve(16);
    auto repeat = std::make_shared<IResource>();
    const size_t warmRenderAllocations = allocations;
    for (unsigned frame = 0; frame < 1000; ++frame) {
        {
            ResourceReaderScope reader(renderStorage);
            renderStorage.push_back(repeat);
            renderStorage.push_back(repeat);
            assert(renderStorage.size() == 1 && repeat.use_count() == 2);
        }
        assert(renderStorage.empty() && repeat.use_count() == 1);
    }
    assert(allocations == warmRenderAllocations);
    auto held = std::make_shared<IResource>(); std::weak_ptr<IResource> weak = held;
    owners.push_back(held);
    const long count = held.use_count(); const size_t retained = allocations;
    for (unsigned i = 0; i < 10000; ++i) owners.push_back(held);
    assert(owners.size() == 1 && held.use_count() == count && allocations == retained);
    owners.push_back({}); assert(owners.size() == 1);
    ResourceOwners copy(owners), assigned; assigned = owners;
    copy.push_back(held); assigned.push_back(held);
    assert(copy.size() == 1 && assigned.size() == 1);
    held.reset(); owners.clear(); assert(!weak.expired());
    copy.clear(); assert(!weak.expired()); assigned.clear(); assert(weak.expired());
    auto replacement = std::make_shared<IResource>();
    owners.push_back(replacement); owners.clear(); owners.push_back(replacement); assert(owners.size() == 1);
    assigned = owners; assigned = assigned; assigned.push_back(replacement); assert(assigned.size() == 1);
    assigned.clear(); assigned.push_back(replacement); assert(assigned.size() == 1);

    std::shared_ptr<IResource> slots[256];
    std::shared_ptr<IResource> first, second;
    for (unsigned i = 0; i < 257 && !second; ++i) {
        auto p = std::make_shared<IResource>();
        uintptr_t a = reinterpret_cast<uintptr_t>(p.get()); unsigned slot = unsigned(((a >> 4) ^ (a >> 12)) & 255);
        if (slots[slot]) { first = slots[slot]; second = p; } else slots[slot] = p;
    }
    assert(first && second && first != second);
    owners.clear(); owners.push_back(first); owners.push_back(second); owners.push_back(first); owners.push_back(first);
    assert(owners.size() == 3 && owners[0] == first && owners[1] == second && owners[2] == first);
    ResourceOwners collided(owners); collided.push_back(first); assert(collided.size() == 3);
    collided.push_back(second); assert(collided.size() == 4);
    puts("PASS resource owners: duplicates, null, copy/assignment, self-assignment, clear/reuse, lifetime and collisions");
}
