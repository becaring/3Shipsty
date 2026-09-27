extern "C" uint32_t Ship_GetInterpolationFPS() { return 60; }
static void require(bool value) { if(!value)throw std::runtime_error("ownership contract"); }
#if PROJECTED_OP_INDEX
static void checkIndex(const Path& path) {
    bool occupied[Op::SkinMatrixMtxFToMtx + 1] = {};
    for(auto it=path.ops.begin();it!=path.ops.end();++it) {
        unsigned index=static_cast<unsigned>(it->first.GetValue());
        occupied[index]=true;
        require(path.opIndex[index]==&it->second);
    }
    for(unsigned i=0;i<Op::SkinMatrixMtxFToMtx+1;++i)
        if(!occupied[i])require(path.opIndex[i]==nullptr);
    for(auto it=path.children.begin();it!=path.children.end();++it)
        for(const Path& child:it->second)checkIndex(child);
}
#endif
static Mtx destinations[40];
static int nodeIdentity;
static void record(float base,int count,int key=7,bool extraOperation=false) {
    FrameInterpolation_StartRecord();
    for(int i=0;i<count;++i) {
        FrameInterpolation_RecordOpenChild(&nodeIdentity,key);
        FrameInterpolation_RecordOpenChild(&nodeIdentity,11);
        MtxF matrix={};
        for(int r=0;r<4;++r)for(int c=0;c<4;++c)matrix.mf[r][c]=base+i+r*4+c;
        FrameInterpolation_RecordMatrixMtxFToMtx(&matrix,&destinations[i]);
        if(i==0 && extraOperation)FrameInterpolation_RecordMatrixPush();
        FrameInterpolation_RecordCloseChild();
        FrameInterpolation_RecordCloseChild();
    }
    FrameInterpolation_StopRecord();
}
static float check(float step,float base,int count) {
    auto result=FrameInterpolation_Interpolate(step);
    require(result.size()==count);float sum=0;
    for(int i=0;i<count;++i)for(int r=0;r<4;++r)for(int c=0;c<4;++c) {
        float value=result.at(&destinations[i]).mf[r][c];
        require(value==base+i+r*4+c);sum+=value;
    }
    return sum;
}
int main() {
    record(0,32);
    auto* recorded=&current_recording.root_path.children.begin()->second[0];
    copies=allocations=0;FrameInterpolation_StartRecord();
    size_t rotationCopies=copies,rotationAllocations=allocations;
    require(current_recording.root_path.children.empty());
#if PROJECTED_OP_INDEX
    checkIndex(previous_recording.root_path);
    checkIndex(current_recording.root_path);
#endif
#if IMPROVED
    require(&previous_recording.root_path.children.begin()->second[0]==recorded);
    require(rotationCopies==0 && rotationAllocations==0);
#else
    require(rotationCopies>0 && rotationAllocations>0);
#endif
    FrameInterpolation_StopRecord();
    record(0,32);record(12,32);
    float sum=check(0,0,32)+check(.25f,3,32)+check(.5f,6,32)+check(1,12,32);
    // Unmatched labels, excess siblings, removed children, empty frames.
    record(30,36,8);sum+=check(.5f,30,36);
    record(42,12,8);sum+=check(.5f,36,12);
    record(0,0);require(FrameInterpolation_Interpolate(.5f).empty());
    record(5,32);sum+=check(.5f,5,32);
    // The same child can gain an operation absent from the previous recording.
    // The missing-old operation must be skipped; the matching matrix still lerps.
    record(70,3);record(80,3,7,true);sum+=check(.5f,75,3);
    record(5,32);
    Path original=current_recording.root_path;
    Path copied(original);Path assigned;assigned=original;
    require(copied.children.size()==original.children.size());
    InterpolateCtx copiedReplay;
    copiedReplay.step=copiedReplay.w=.5f;
    copiedReplay.interpolate_branch(&copied,&assigned);
    require(copiedReplay.mtx_replacements.size()==32);
#if PROJECTED_OP_INDEX
    checkIndex(original);checkIndex(copied);checkIndex(assigned);
#endif
    copied=copied;
#if IMPROVED
    // Both empty-map sentinels must be constructed before the swap publishes
    // ownership. A failed move construction leaves its source intact.
    for(int failure=0;failure<2;++failure) {
        size_t size=original.children.begin()->second.size();
        Shipyard::Interpolation::TrimRecordingMemory();
        failAfter=failure;bool failed=false;
        try { Path attempted(std::move(original)); } catch(const std::bad_alloc&) { failed=true; }
        failAfter=-1;require(failed && original.children.begin()->second.size()==size);
#if PROJECTED_OP_INDEX
        checkIndex(original);
#endif
    }
    // The XDK vector::_Umove uses uninitialized_move, including when a
    // move can throw. Exercise that actual relocation primitive explicitly;
    // current host vector uses move_if_noexcept instead.
    auto* leaf=&original.children.begin()->second[0];
    void* storage=::operator new(sizeof(Path));copies=allocations=0;
    std::uninitialized_move(&original,&original+1,static_cast<Path*>(storage));
    auto* moved=static_cast<Path*>(storage);
    require(copies==0 && &moved->children.begin()->second[0]==leaf);
    size_t relocationAllocations=allocations;
    moved->operator=(std::move(*moved));require(!moved->children.empty());
    assigned=std::move(*moved);require(moved->children.empty());
#if PROJECTED_OP_INDEX
    checkIndex(*moved);checkIndex(assigned);
#endif
    moved->~Path();::operator delete(storage);
    // Copy assignment uses a complete temporary before publication.
    size_t before=assigned.children.begin()->second.size();
    Shipyard::Interpolation::TrimRecordingMemory();
    failAfter=0;bool failed=false;
    try { assigned=copied; } catch(const std::bad_alloc&) { failed=true; }
    failAfter=-1;require(failed && assigned.children.begin()->second.size()==before);
#if PROJECTED_OP_INDEX
    checkIndex(assigned);
#endif
#else
    void* storage=::operator new(sizeof(Path));copies=allocations=0;
    std::uninitialized_move(&original,&original+1,static_cast<Path*>(storage));
    require(copies>0 && allocations>0);
    size_t relocationAllocations=allocations;
    static_cast<Path*>(storage)->~Path();::operator delete(storage);
#endif
    printf("replay %.0f\ncounts rotation copies=%zu allocations=%zu relocation allocations=%zu\n",sum,rotationCopies,rotationAllocations,relocationAllocations);
#if IMPROVED
    Shipyard::Interpolation::RecordingMemoryCounts warmup, counts;
    Shipyard::Interpolation::GetRecordingMemoryCounts(&warmup);
    for(int iteration=0;iteration<80;++iteration)record(float(iteration),32);
#if PROJECTED_OP_INDEX
    checkIndex(previous_recording.root_path);
    checkIndex(current_recording.root_path);
#endif
    Shipyard::Interpolation::GetRecordingMemoryCounts(&counts);
    require(counts.requests>1000 && counts.hits*2>counts.requests);
    require(counts.retainedBytes<=2*1024*1024);
    printf("pool requests=%u hits=%u releases=%u retained=%zu\n",
           counts.requests,counts.hits,counts.releases,counts.retainedBytes);
    Shipyard::Interpolation::RecordingAllocator<unsigned char> allocator;
    std::vector<unsigned char*> blocks;
    for(int i=0;i<600;++i)blocks.push_back(allocator.allocate(4096));
    for(unsigned char* block:blocks)allocator.deallocate(block,4096);
    Shipyard::Interpolation::GetRecordingMemoryCounts(&counts);
    require(counts.retainedBytes<=2*1024*1024);
    Shipyard::Interpolation::TrimRecordingMemory();
    Shipyard::Interpolation::GetRecordingMemoryCounts(&counts);
    require(counts.retainedBytes==0);
#endif
}
