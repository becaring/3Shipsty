"""Borrow settled resource keys instead of allocating owned keys for every lookup.
Alternate precedence, dirty-resource fallback and owner/archive identity are preserved.
"""


def replace_function(text, signature, replacement):
    begin = text.index(signature)
    end = text.index("\n}", begin) + 2
    return text[:begin] + replacement + text[end:]


def source(text):
    signature = "ResourceManager::CheckCache(const ResourceIdentifier& identifier, bool loadExact)"
    text = replace_function(text, signature, '''ResourceManager::CheckCache(const ResourceIdentifier& identifier, bool loadExact) {
    const Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(mMutex);
    const std::string& prefix = IResource::gAltAssetPrefix;
    if (!loadExact && mAltAssetsEnabled && !Shipyard::Resources::starts_with(identifier.Path, prefix)) {
        ResourceIdentifier alternate(identifier.Path.c_str(), identifier.Owner, identifier.Parent,
            ResourceIdentifier::BorrowedLookup(), prefix.data(), prefix.size());
        if (alternate.mBorrowedLength != identifier.Path.size()) {
            alternate.mBorrowedLength = identifier.Path.size();
            alternate.mHash = alternate.CalculateHash();
        }
        const auto found = mResourceCache.find(alternate);
        if (found != mResourceCache.end() &&
            xbox_compat::holds_alternative<std::shared_ptr<IResource>>(found->second))
            return found->second;
    }
    const auto found = mResourceCache.find(identifier);
    if (found == mResourceCache.end()) return ResourceLoadError::NotCached;
    return found->second;
}''')
    signature = "ResourceManager::CheckCache(const std::string& filePath, bool loadExact)"
    text = replace_function(text, signature, '''ResourceManager::CheckCache(const std::string& filePath, bool loadExact) {
    const Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(mMutex);
    const std::string& prefix = IResource::gAltAssetPrefix;
    if (!loadExact && mAltAssetsEnabled && !Shipyard::Resources::starts_with(filePath, prefix)) {
        ResourceIdentifier alternate(filePath.c_str(), mDefaultCacheOwner, mDefaultCacheArchive,
            ResourceIdentifier::BorrowedLookup(), prefix.data(), prefix.size());
        if (alternate.mBorrowedLength != filePath.size()) {
            alternate.mBorrowedLength = filePath.size();
            alternate.mHash = alternate.CalculateHash();
        }
        const auto found = mResourceCache.find(alternate);
        if (found != mResourceCache.end() &&
            xbox_compat::holds_alternative<std::shared_ptr<IResource>>(found->second))
            return found->second;
    }
    ResourceIdentifier key(filePath.c_str(), mDefaultCacheOwner, mDefaultCacheArchive,
        ResourceIdentifier::BorrowedLookup());
    if (key.mBorrowedLength != filePath.size()) {
        key.mBorrowedLength = filePath.size();
        key.mHash = key.CalculateHash();
    }
    const auto found = mResourceCache.find(key);
    if (found == mResourceCache.end()) return ResourceLoadError::NotCached;
    return found->second;
}''')
    signature = "std::shared_ptr<IResource> ResourceManager::GetCachedResource(const std::string& filePath, bool loadExact)"
    text = replace_function(text, signature, '''std::shared_ptr<IResource> ResourceManager::GetCachedResource(const std::string& filePath, bool loadExact) {
    return GetCachedResource(CheckCache(filePath, loadExact));
}''')
    signature = "std::shared_ptr<IResource> ResourceManager::LoadResource(const std::string& filePath, bool loadExact,"
    return replace_function(text, signature, '''std::shared_ptr<IResource> ResourceManager::LoadResource(const std::string& filePath, bool loadExact,
                                                         std::shared_ptr<ResourceInitData> initData) {
    auto cachedResource = GetCachedResource(filePath, loadExact);
    if (cachedResource != nullptr) return cachedResource;
    std::shared_ptr<IResource> resource;
    {
#ifdef _XBOX
        ModernFrameProfile::ResourceWaitScope resourceWait;
#endif
        resource = LoadResourceProcess(filePath, loadExact, initData);
    }
    if (resource == nullptr) SPDLOG_TRACE("Failed to load resource file at path {}", filePath);
    return resource;
}''')
