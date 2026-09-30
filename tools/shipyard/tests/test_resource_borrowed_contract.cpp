#include <memory>
#include <string>
#include <unordered_map>
#include "xbox_compat/variant.h"
#include <mutex>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cassert>
#include "resources/path_hash.h"
#include "resources/path_span.h"
namespace Shipyard { namespace Async { using std::mutex; using std::lock_guard; } }
static size_t allocations;
void* operator new(size_t n) { ++allocations; if(void* p=std::malloc(n))return p; throw std::bad_alloc(); }
void operator delete(void* p) noexcept {std::free(p);}
void operator delete(void* p,size_t) noexcept {std::free(p);}
namespace Math {
size_t HashCombine(size_t a,size_t b){return a^(b+0x9e3779b9u+(a<<6)+(a>>2));}
}
namespace Ship {
struct Archive { std::string path; const std::string& GetPath()const{return path;} };
struct ResourceInitData {};
struct IResource { bool dirty; std::weak_ptr<IResource> self; long observedOwners;
    static const std::string gAltAssetPrefix;
    IResource():dirty(false),observedOwners(0){} bool IsDirty(){observedOwners=self.use_count();return dirty;} };
const std::string IResource::gAltAssetPrefix="alt/";
// SELECTED KEY
class ResourceManager {
public:
    enum class ResourceLoadError {None,NotCached,NotFound};
    bool mAltAssetsEnabled=false;
    uintptr_t mDefaultCacheOwner=0;
    std::shared_ptr<Archive> mDefaultCacheArchive;
    std::mutex mMutex;
    std::unordered_map<ResourceIdentifier,xbox_compat::variant<ResourceLoadError,std::shared_ptr<IResource>>,ResourceIdentifierHash> mResourceCache;
    unsigned slowLoads=0;
    bool lastExact=false;
    std::string lastPath;
    std::shared_ptr<ResourceInitData> lastInit;
    std::shared_ptr<IResource> fallback=std::make_shared<IResource>();
    bool OtrSignatureCheck(const char* p){return std::strncmp(p,"__OTR__",7)==0;}
    std::shared_ptr<IResource> LoadResourceProcess(const std::string& p,bool exact=false,std::shared_ptr<ResourceInitData> init={}) {
        std::unique_lock<std::mutex> lock(mMutex,std::try_to_lock);
        assert(lock.owns_lock());
        ++slowLoads;lastPath=p;lastExact=exact;lastInit=init;return fallback;
    }
    // FAST DECLARATION
    // CACHE DECLARATION
    void InsertBorrowed(const char* p, const std::shared_ptr<IResource>& resource) {
        ResourceIdentifier key(p,mDefaultCacheOwner,mDefaultCacheArchive,ResourceIdentifier::BorrowedLookup());
        mResourceCache.emplace(key,resource);
    }
    void InsertAlternateBorrowed(const char* p, const std::shared_ptr<IResource>& resource) {
        ResourceIdentifier key(p,mDefaultCacheOwner,mDefaultCacheArchive,ResourceIdentifier::BorrowedLookup(),
                               IResource::gAltAssetPrefix.data(),IResource::gAltAssetPrefix.size());
        mResourceCache.emplace(key,resource);
    }
};
// SELECTED METHODS
// CACHE METHOD
}
int main() {
    using namespace Ship;
    ResourceManager manager;
    const std::string path="objects/test_object/a_long_texture_path_with_a_distinct_resource_name";
    auto resource=std::make_shared<IResource>();
    resource->self=resource;
    manager.mResourceCache[ResourceIdentifier(path,0,{})]=resource;
    {
        xbox_compat::variant<ResourceManager::ResourceLoadError,std::shared_ptr<IResource>> line(resource);
        const long owners=resource.use_count();
        auto hit=manager.GetCachedResource(line);
        assert(hit==resource);
        if(resource->observedOwners!=owners) {std::puts("FAIL cache validation copied resource ownership");return 1;}
    }
    size_t before=allocations;
    for(unsigned i=0;i<1000;++i) {
        auto hit=manager.LoadResourceProcess(path.c_str());
        if(hit!=resource) {std::puts("FAIL cached C-string load used slow loader");return 1;}
    }
    assert(allocations==before && manager.slowLoads==0);
    std::printf("1000 warm C-string lookups: %u slow loads, %u allocations\n",manager.slowLoads,unsigned(allocations-before));
    std::string tagged="__OTR____OTR__"+path;
    before=allocations;
    assert(manager.LoadResourceProcess(tagged.c_str(),true)==resource);
    assert(allocations==before && manager.slowLoads==0);
    resource->dirty=true;
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback && manager.slowLoads==1);
    resource->dirty=false;
    manager.mAltAssetsEnabled=true;
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback && manager.slowLoads==2);
    assert(manager.LoadResourceProcess(path.c_str(),true)==resource && manager.slowLoads==2);
    assert(manager.LoadResourceProcess(tagged.c_str(),true)==manager.fallback && !manager.lastExact);
    manager.mResourceCache[ResourceIdentifier(IResource::gAltAssetPrefix+path,0,{})]=ResourceManager::ResourceLoadError::NotFound;
    before=allocations;
    assert(manager.LoadResourceProcess(path.c_str())==resource && allocations==before);
    manager.mResourceCache[ResourceIdentifier(IResource::gAltAssetPrefix+path,0,{})]=manager.fallback;
    before=allocations;
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback && allocations==before);
    manager.mAltAssetsEnabled=false;
    manager.mResourceCache.erase(ResourceIdentifier(path,0,{}));
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback);
    manager.mResourceCache[ResourceIdentifier(path,0,{})]=std::shared_ptr<IResource>();
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback);
    manager.mResourceCache[ResourceIdentifier(path,0,{})]=ResourceManager::ResourceLoadError::NotFound;
    auto init=std::make_shared<ResourceInitData>();
    assert(manager.LoadResourceProcess(path.c_str(),false,init)==manager.fallback && manager.lastInit==init);
    auto parent=std::make_shared<Archive>();parent->path="archive.otr";
    manager.mResourceCache[ResourceIdentifier(path,7,parent)]=resource;
    assert(manager.LoadResourceProcess(path.c_str())==manager.fallback);
    manager.mDefaultCacheOwner=7;manager.mDefaultCacheArchive=parent;
    before=allocations;
    assert(manager.LoadResourceProcess(path.c_str())==resource && allocations==before);
    ResourceIdentifier copy(ResourceIdentifier(path,7,parent));
    assert(copy.Path==path && copy.Owner==7 && copy.Parent==parent);
    auto replacement=std::make_shared<IResource>();
    manager.mResourceCache[copy]=replacement;
    assert(manager.LoadResourceProcess(path.c_str())==replacement);
    std::string transient=path+"_temporary";
    const std::string retained=transient;
    manager.InsertBorrowed(transient.c_str(),resource);
    transient.assign(transient.size(),'!');
    auto stored=manager.mResourceCache.find(ResourceIdentifier(retained,7,parent));
    assert(stored!=manager.mResourceCache.end() && stored->first.Path==retained);
    assert(manager.LoadResourceProcess(retained.c_str())==resource);
    transient=retained+"_alternate";
    const std::string retainedAlternate=IResource::gAltAssetPrefix+transient;
    manager.InsertAlternateBorrowed(transient.c_str(),resource);
    transient.assign(transient.size(),'!');
    stored=manager.mResourceCache.find(ResourceIdentifier(retainedAlternate,7,parent));
    assert(stored!=manager.mResourceCache.end() && stored->first.Path==retainedAlternate);
    ResourceIdentifier alternateCopy(stored->first);
    assert(alternateCopy==stored->first && alternateCopy.Path==retainedAlternate);
    std::string binary("abc\0def",7);
    ResourceIdentifier binaryKey(binary,7,parent), shortKey("abc",7,parent);
    assert(!(binaryKey==shortKey));
    ResourceIdentifier binaryCopy(binaryKey);
    assert(binaryCopy==binaryKey && binaryCopy.Path.size()==7);
    std::puts("PASS dirty/missing/null/alt/exact/prefix/owner/archive/unload/replacement contracts");
}
