#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include <mutex>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cassert>
#include "xbox_compat/variant.h"
#include "resources/path_span.h"
#define SPDLOG_TRACE(...) ((void)0)
static size_t allocations, locks, probes;
void* operator new(size_t n){++allocations;if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete(void* p,size_t) noexcept {std::free(p);}
namespace Shipyard { namespace Async {
struct mutex { std::mutex native; void lock(){++locks;native.lock();} void unlock(){native.unlock();} bool try_lock(){return native.try_lock();} };
using std::lock_guard;
} namespace Resources {
bool starts_with(const std::string& value,const std::string& prefix){return value.compare(0,prefix.size(),prefix)==0;}
}}
namespace Math {size_t HashCombine(size_t a,size_t b){return a^(b+0x9e3779b9u+(a<<6)+(a>>2));}}
namespace Ship {
struct Archive {std::string path;const std::string& GetPath()const{return path;}};
struct ResourceInitData {};
struct IResource {bool dirty=false;bool IsDirty(){return dirty;}static const std::string gAltAssetPrefix;};
const std::string IResource::gAltAssetPrefix="alt/";
// SELECTED KEY
class ResourceManager {
public:
    enum class ResourceLoadError {None,NotCached,NotFound};
    typedef xbox_compat::variant<ResourceLoadError,std::shared_ptr<IResource>> Line;
    struct Cache : std::unordered_map<ResourceIdentifier,Line,ResourceIdentifierHash> {
        iterator find(const ResourceIdentifier& key){++probes;return std::unordered_map<ResourceIdentifier,Line,ResourceIdentifierHash>::find(key);}
    } mResourceCache;
    Shipyard::Async::mutex mMutex;
    bool mAltAssetsEnabled=true;
    uintptr_t mDefaultCacheOwner=0;
    std::shared_ptr<Archive> mDefaultCacheArchive;
    std::vector<std::string> reads,loads;
    std::shared_ptr<ResourceInitData> lastInit;
    std::shared_ptr<IResource> loaded;
    bool files=true;
    bool OtrSignatureCheck(const char* p){return std::strncmp(p,"__OTR__",7)==0;}
    std::shared_ptr<int> LoadFileProcess(const std::string& path){
        assert(mMutex.try_lock());mMutex.unlock();reads.push_back(path);
        return files?std::make_shared<int>(1):nullptr;
    }
    ResourceManager* GetResourceLoader(){return this;}
    std::shared_ptr<IResource> LoadResource(const std::string& path,std::shared_ptr<int>,std::shared_ptr<ResourceInitData> init){loads.push_back(path);lastInit=init;return loaded;}
    // ACTUAL DECLARATIONS
};
// ACTUAL METHODS
}
int main(){
    using namespace Ship;
    const std::string path="objects/very_long_resource_path/texture_123456789";
    auto clean=std::make_shared<IResource>(),dirty=std::make_shared<IResource>(),loaded=std::make_shared<IResource>();dirty->dirty=true;
    auto archive=std::make_shared<Archive>();archive->path="archive.otr";
    auto init=std::make_shared<ResourceInitData>();
    unsigned cases=0;
    // Absent, None, NotFound, NotCached, clean, dirty, null on each side.
    for(int alt=0;alt<7;++alt)for(int base=0;base<7;++base)
    for(int mode=0;mode<5;++mode)for(int load=0;load<3;++load)for(int owner=0;owner<2;++owner){
        ResourceManager expected,actual;
        for(auto* m:{&expected,&actual}){
            m->mDefaultCacheOwner=owner?7:0;m->mDefaultCacheArchive=owner?archive:nullptr;
            m->mAltAssetsEnabled=mode!=4;m->files=load!=0;m->loaded=load==2?loaded:nullptr;
            for(int side=0;side<2;++side){
                int state=side?alt:base;
                ResourceIdentifier key((side?IResource::gAltAssetPrefix:std::string())+path,m->mDefaultCacheOwner,m->mDefaultCacheArchive);
                if(state==1)m->mResourceCache[key]=ResourceManager::ResourceLoadError::None;
                if(state==2)m->mResourceCache[key]=ResourceManager::ResourceLoadError::NotFound;
                if(state==3)m->mResourceCache[key]=ResourceManager::ResourceLoadError::NotCached;
                if(state==4)m->mResourceCache[key]=clean;
                if(state==5)m->mResourceCache[key]=dirty;
                if(state==6)m->mResourceCache[key]=std::shared_ptr<IResource>();
            }
        }
        std::string request=(mode==2?"__OTR____OTR__":mode==3?"alt/":"")+path;
        bool exact=mode==1||mode==2;
        auto reference=expected.LoadResourceProcess(request,exact,init);
        auto result=actual.LoadResourceProcess(request.c_str(),exact,init);
        assert(result==reference && actual.reads==expected.reads && actual.loads==expected.loads && actual.lastInit==expected.lastInit);
        assert(actual.mResourceCache.size()==expected.mResourceCache.size());
        for(const auto& entry:expected.mResourceCache){
            auto found=actual.mResourceCache.find(entry.first);assert(found!=actual.mResourceCache.end());
            if(xbox_compat::holds_alternative<std::shared_ptr<IResource>>(entry.second))
                assert(xbox_compat::holds_alternative<std::shared_ptr<IResource>>(found->second)&&xbox_compat::get<std::shared_ptr<IResource>>(entry.second)==xbox_compat::get<std::shared_ptr<IResource>>(found->second));
            else assert(xbox_compat::holds_alternative<ResourceManager::ResourceLoadError>(found->second)&&xbox_compat::get<ResourceManager::ResourceLoadError>(entry.second)==xbox_compat::get<ResourceManager::ResourceLoadError>(found->second));
        }
        ++cases;
    }
    ResourceManager warm;
    warm.mResourceCache[ResourceIdentifier(path,0,{})]=clean;
    warm.mResourceCache[ResourceIdentifier("alt/"+path,0,{})]=ResourceManager::ResourceLoadError::NotFound;
    locks=probes=0;size_t before=allocations;
    assert(warm.LoadResourceProcess(path.c_str())==clean);
    assert(locks==1&&probes==2&&allocations==before);
    locks=probes=0;assert(warm.LoadResourceProcess(path)==clean);assert(locks==3&&probes==3);
    warm.mResourceCache[ResourceIdentifier("alt/"+path,0,{})]=loaded;
    locks=probes=0;before=allocations;
    assert(warm.LoadResourceProcess(path.c_str())==loaded);assert(locks==1&&probes==1&&allocations==before);
    for(size_t n=0;n<128;++n){std::string bytes(n,'x');for(size_t i=0;i<n;++i)bytes[i]=char(i*71);
        for(size_t split=0;split<=n;++split){Shipyard::Resources::PathSpan span(bytes.data(),split,bytes.data()+split,n-split);
            assert(span.Owned()==bytes&&span.Hash()==Shipyard::Resources::PathHash()(bytes));
            for(size_t other=0;other<=n;++other)assert(span==Shipyard::Resources::PathSpan(bytes.data(),other,bytes.data()+other,n-other));
            for(size_t changed=0;changed<n;++changed){std::string different=bytes;different[changed]^=1;
                assert(!(span==Shipyard::Resources::PathSpan(different.data(),split,different.data()+split,n-split)));
            }
        }
    }
    std::printf("PASS %u actual-loader differential cases; negative alt/base hit 3 probes/3 locks -> 2/1, zero allocations; clean alt 1/1 zero allocations\n",cases);
}
