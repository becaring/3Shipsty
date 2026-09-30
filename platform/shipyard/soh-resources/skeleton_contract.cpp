#include <cassert>
#include <cstdio>
int main() {
    SOH::Skeleton resource(std::make_shared<Ship::ResourceInitData>());
    assert(resource.GetPointer() == &resource.skeletonData);
    resource.type = SOH::SkeletonType::Normal;
    assert(resource.GetPointerSize() == sizeof(SOH::SkeletonHeader));
    resource.type = SOH::SkeletonType::Flex;
    assert(resource.GetPointerSize() == sizeof(SOH::FlexSkeletonHeader));
    resource.type = SOH::SkeletonType::Curve;
    assert(resource.GetPointerSize() == sizeof(SOH::SkelCurveLimbList));
    resource.type = (SOH::SkeletonType)99;
    assert(resource.GetPointerSize() == 0);
    SkelAnime values[3];
    for (int i = 0; i < 4; ++i) {
        SOH::SkeletonPatchInfo entry;
        entry.skelAnime = &values[i % 3];
        entry.isLocalPlayer = (i == 0);
        entry.vanillaSkeletonPath = std::string(i + 1, 'x');
        SOH::SkeletonPatcher::skeletons.push_back(entry);
    }
    SOH::SkeletonPatcher::UnregisterSkeleton(&values[0]);
    assert(SOH::SkeletonPatcher::skeletons.size() == 3);
    assert(SOH::SkeletonPatcher::skeletons.front().vanillaSkeletonPath == "xx");
    assert(SOH::SkeletonPatcher::skeletons.back().skelAnime == &values[0]);
    SOH::SkeletonPatcher::UnregisterSkeleton(NULL);
    assert(SOH::SkeletonPatcher::skeletons.size() == 3);
    SOH::SkeletonPatcher::UnregisterSkeleton(&values[0]);
    assert(SOH::SkeletonPatcher::skeletons.size() == 2);
    SOH::SkeletonPatcher::ClearSkeletons();
    assert(SOH::SkeletonPatcher::skeletons.empty());
    puts("Skeleton pointer/size, first-match removal, stable remaining order, clear agree");
}
