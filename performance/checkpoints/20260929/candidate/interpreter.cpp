#include "direct_transform.h"
#include "sources/fast3d/numeric.h"
#include "application/frame_profile.h"
#include "application/command_profile.h"
#include "fast3d/dispatch_owner.h"
#include "fast3d/projection_cache.h"
#include <float.h>
#include "fast3d/material_value_cache.h"
#include "fast3d/coordinate.h"
#include "fast3d/unit_color.h"
#include "fast3d/clip_quantize.h"
#include "fast3d/vertex_transform.h"
#define NOMINMAX
#include "fast3d/game_fill_discard_certificate.h"
#include "xenos/depth_discard.h"
#include "xenos/tiling_guard_trial.h"
#include "xenos/tile1_predication_trial.h"
#include "libultraship/bridge/consolevariablebridge.h"

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include <assert.h>
#include <stdio.h>

#include "fast3d/value_init.h"
#include "fast3d/math.h"
#include <array>
#include <map>
#include <set>
#include <unordered_map>
#include <vector>
#include <list>
#include <stack>
#include "fast/resource/type/Light.h"

#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif
#include "fast/debug/GfxDebugger.h"
#include "fast/types.h"
#include <string>

#include "fast/interpreter.h"
#include "fast/lus_gbi.h"
#include "fast/backends/gfx_window_manager_api.h"
#include "fast/backends/gfx_rendering_api.h"

#include "ship/window/gui/Gui.h"
#include "ship/resource/ResourceManager.h"
#include "ship/utils/Utils.h"
#include "ship/Context.h"
#include "ship/config/ConsoleVariable.h"

#include "libultraship/libultra/os.h"

#include <spdlog/spdlog.h>



#define SEG_ADDR(seg, addr) (addr | (seg << 24) | 1)
#define SUPPORT_CHECK(x) assert(x)

// SCALE_M_N: upscale/downscale M-bit integer to N-bit
#define SCALE_5_8(VAL_) (((VAL_)*0xFF) / 0x1F)
#define SCALE_8_5(VAL_) ((((VAL_) + 4) * 0x1F) / 0xFF)
#define SCALE_4_8(VAL_) ((VAL_)*0x11)
#define SCALE_8_4(VAL_) ((VAL_) / 0x11)
#define SCALE_3_8(VAL_) ((VAL_)*0x24)
#define SCALE_8_3(VAL_) ((VAL_) / 0x24)

// Based off the current set native dimensions or active framebuffer
#define HALF_SCREEN_WIDTH(activeFb) ((mFbActive ? activeFb->second.orig_width : mNativeDimensions.width) / 2)
#define HALF_SCREEN_HEIGHT(activeFb) ((mFbActive ? activeFb->second.orig_height : mNativeDimensions.height) / 2)

// Ratios for current window dimensions or active framebuffer scaled size
#define RATIO_X(activeFb, dims) \
    ((mFbActive ? activeFb->second.applied_width : dims.width) / (2.0f * HALF_SCREEN_WIDTH(activeFb)))
#define RATIO_Y(activeFb, dims) \
    ((mFbActive ? activeFb->second.applied_height : dims.height) / (2.0f * HALF_SCREEN_HEIGHT(activeFb)))

#include "fast3d/update_instruction.h"
#include "fast3d/instruction_buffer.h"
#define TEXTURE_CACHE_MAX_SIZE 1024

// This scratch trial removes only telemetry stores. Validation modes and all
// input/output oracles retain their original execution and fallback behavior.
#ifndef SHIPYARD_CAMPAIGN_DIAGNOSTIC_COUNTERS
#define SHIPYARD_CAMPAIGN_DIAGNOSTIC_COUNTERS 0
#endif
#if SHIPYARD_CAMPAIGN_DIAGNOSTIC_COUNTERS
#define CAMPAIGN_DIAGNOSTIC_COUNT(statement) do { statement; } while (0)
#else
#define CAMPAIGN_DIAGNOSTIC_COUNT(statement) do {} while (0)
#endif


namespace CampaignTriRun {
struct Rows {
    unsigned epoch, stamps[256], starts[256], stride, lodW; bool lodMaterial;
    unsigned mode, presentations;
    unsigned long long rows, hits, triangles, full, checks, mismatches, additional;
    void Reset() { if(!++epoch) { memset(stamps,0,sizeof(stamps)); ++epoch; } }
    bool Has(unsigned index) const { return stamps[index]==epoch; }
};
static __declspec(thread) Rows cache;
}

namespace CampaignPreparedPack {
struct CoordinatePlan {
    float shiftScale,start,dimension,reciprocal;
    bool shifted,powerOfTwo;
    void Prepare(unsigned shift,float origin,unsigned extent) {
        shifted=shift!=0;
        shiftScale=shift<=10 ? 1.0f/float(1U<<shift):float(1U<<(16-shift));
        start=origin/4.0f;dimension=float(extent);
        powerOfTwo=extent && !(extent&(extent-1));
        reciprocal=powerOfTwo ? 1.0f/dimension:0.0f;
    }
    __forceinline float Apply(float raw,bool half) const {
        float value=raw/32.0f;
        // All shifts are exact powers of two. Preserve the original operation
        // ordering and every single-precision rounding boundary.
        if(shifted)value*=shiftScale;
        value-=start;
        if(half)value+=0.5f;
        return powerOfTwo ? value*reciprocal:value/dimension;
    }
};
struct Layout {
    const void* owner;
    unsigned epoch, stride, textureOffset[2], fogOffset;
    unsigned shadeRgb[7], shadeAlpha[7], rgbCount, alphaCount;
    bool halfTexel, pending;
    float row[32], expected[96];
    CoordinatePlan uv[2][2];
    unsigned long long triangles, misses, checks, failures;
};
static __declspec(thread) Layout layout;
}


namespace CampaignDeferredState {
struct Snapshot {
    const void* owner; void* context;
    unsigned epoch,captured;
    unsigned long long reused,created,checks,failures;
    void Invalidate(){if(!++epoch){epoch=1;owner=NULL;context=NULL;}}
};
static __declspec(thread) Snapshot snapshot;
}


// Packet ownership is explicitly bracketed by RunCommands, never inferred
// from a display-list address or interpolation index that may be skipped.

namespace LaneWork {
enum Stage { TransformVertices,DeferredSetup,StaticAttributes,Cull,Materialize,MaterialClassify,
    GeometryPrepare,LayoutPrepare,StaticPack,DynamicPack,ResourceResolve,TextureMetadata,
    TextureImport,NativeDraw,LightSetup,MaterialReuse,GeometryReuse,DependencyCheck,SourceDecode,FuturePrepared,FutureConsumed,MatrixGuardMiss,LayoutReuse,TextureSearch,TextureNodeReuse,LightEvaluate,LightReuse,FogEvaluate,AttributeEvaluate,Count };
static const char* names[]={"transform_vertices","deferred_setup","static_attributes","cull","materialize","material_classify",
    "geometry_prepare","layout_prepare","pack_static","pack_dynamic","resource_resolve","texture_metadata",
    "texture_import","native_draw","light_setup","material_reuse","geometry_reuse","dependency_check","source_decode","future_prepared","future_consumed","matrix_guard_miss","layout_reuse","texture_search","texture_node_reuse","light_evaluate","light_reuse","fog_evaluate","attribute_evaluate"};
static unsigned lane=3,updates,mode,geometryMode,laneCount;static const void* matrixMaps;static bool enabled;
static unsigned long long counts[4][Count];
static __forceinline void Add(Stage stage,unsigned count=1){if(enabled)counts[lane][stage]+=count;}
static void EndUpdate(){if(!enabled||++updates!=120)return;
    for(unsigned p=0;p<4;++p)for(unsigned k=0;k<Count;++k)
        SPDLOG_INFO("lane-work lane={} stage={} count={}",p,names[k],counts[p][k]);
    memset(counts,0,sizeof(counts));updates=0;
}
}
namespace Fast { namespace LaneSemantic {void BeginUpdate();} namespace LaneGeometry {void Begin();} }
extern "C" void XboxSetUpdateLaneMatrices(const void* maps,unsigned count){LaneWork::matrixMaps=maps;LaneWork::laneCount=count;Fast::LaneGeometry::Begin();}

namespace StreamOutputOracle {
static bool enabled;
static unsigned pass,update,hash=2166136261U,draws,triangles,words;
static void Mix(unsigned v){hash=(hash^v)*16777619U;}
static void Begin(unsigned p){pass=p;hash=2166136261U;draws=triangles=words=0;}
static void Draw(const float* data,unsigned count,unsigned tris){
    if(!enabled)return;++draws;triangles+=tris;words+=count;Mix(count);Mix(tris);
    for(unsigned i=0;i<count;++i){unsigned v;memcpy(&v,data+i,4);Mix(v);}
}
static void End(){if(enabled)SPDLOG_INFO("stream-output update={} presentation={} hash={} draws={} triangles={} words={}",update,pass,hash,draws,triangles,words);}
}
namespace StreamEntryCounts {
static unsigned bucket=3,updates;
static unsigned long long entries[4][105],walk[4],prepared[4];
static bool enabled;
static __forceinline void Handler(unsigned id){if(enabled)++entries[bucket][id];}
static void EndUpdate(){
    if(!enabled || ++updates!=120)return;
    for(unsigned b=0;b<4;++b){
        unsigned long long total=0;
        for(unsigned i=0;i<105;++i)total+=entries[b][i];
        SPDLOG_INFO("stream-entries presentation={} generic={} walk={} prepared={}",b,total,walk[b],prepared[b]);
        for(unsigned i=0;i<105;++i)if(entries[b][i])SPDLOG_INFO("stream-handler presentation={} id={} entries={}",b,i,entries[b][i]);
    }
    memset(entries,0,sizeof(entries));memset(walk,0,sizeof(walk));memset(prepared,0,sizeof(prepared));updates=0;
}
}

namespace Fast {namespace LaneLighting {void Begin();void BeginPass();}}
namespace UpdateStream {
enum Kind { Generic, Flow, EndList, Ucode, Vertices, TextureImage, TrianglePair,LoadBlock,LoadTile,SetTile,TileSize,LoadTlut,EnvColor,PrimColor,FogColor,BlendColor,FillColor,Scissor,FillRect,PopMatrix,Geometry,MoveWord,TextureScale,OtherLow,OtherHigh,RdpOther,Combine,Grayscale,InterpolationTarget,Intensity,Marker,DisplayAnnotation,ResetFog,NoWork,SpNoop,CullNoop,PrimDepthNoop,Triangle,Quad,Directory,DepthImage,ColorImage,WideFill,WideTexture,InterpolatedTile,InvalidateTexture,TextureRectangle,Matrix,MoveMemory };
struct TextureInput {
    unsigned format,size,width,flags;const void* address;
    Fast::RawTexMetadata metadata;
};
struct Arguments { unsigned value[12]; };
typedef Shipyard::Fast3D::UpdateInstruction<Fast::F3DGfx,Fast::F3DVtx> Instruction;
static_assert(sizeof(Instruction)==48,"Xbox update instruction ABI");
static_assert(offsetof(Instruction,word0)==4 && offsetof(Instruction,word1)==8 &&
              offsetof(Instruction,ucode)==12 && offsetof(Instruction,kind)==16 &&
              offsetof(Instruction,payload)==20 && offsetof(Instruction,vertexSource)==32 &&
              offsetof(Instruction,materialPlan)==36 && offsetof(Instruction,positionPlan)==40 &&
              offsetof(Instruction,lightPlan)==44,"Xbox update instruction fields");
struct Packet {
    Shipyard::Fast3D::InstructionBuffer<Instruction,65536> instructions;
    std::vector<Arguments> arguments;
    std::vector<unsigned> executable;
    bool sealed,supported;
    unsigned long long inputChecks,inputFailures,omitted;
    std::vector<Fast::F3DVtx> vertices;
    std::vector<TextureInput> textures;
    std::vector<std::shared_ptr<Ship::IResource> > owners;
    unsigned current,resourceGeneration,archiveEpoch;
    unsigned long long replayed,typedVertices,typedTextures,typedTriangles;
    bool replaying;
    bool active,recording,matching,overflow,conditional;
    unsigned pass,cursor;
    unsigned long long updates,stable,variant,commands,repeated,skipped,conditionalUpdates;
    unsigned long long mismatches[256];
    Packet():active(false),recording(false),matching(true),overflow(false),conditional(false),
        pass(0),cursor(0),updates(0),stable(0),variant(0),commands(0),repeated(0),skipped(0),conditionalUpdates(0) {
        memset(mismatches,0,sizeof(mismatches));instructions.reserve(16384);
        vertices.reserve(16384);textures.reserve(1024);owners.reserve(1024);
        executable.reserve(16384);sealed=false;supported=true;inputChecks=inputFailures=omitted=0;arguments.reserve(16384);current=~0U;replaying=false;replayed=typedVertices=typedTextures=typedTriangles=0;
    }
};
// One render thread owns the selected interpreter. No cross-update retention.
static Packet packet;
static unsigned mode;
static void BeginPass(unsigned presentation) {
    Fast::LaneLighting::BeginPass();
    LaneWork::lane=presentation<3?presentation:3;
    StreamEntryCounts::bucket=presentation<3?presentation:3;StreamOutputOracle::Begin(presentation);
    Packet& p=packet;if(!p.active)return;
    p.recording=p.pass++==0;p.cursor=0;
}
static void EndPass() {
    Packet& p=packet;if(!p.active)return;
    if(!p.recording && p.cursor!=p.instructions.size())p.matching=false;
    p.recording=false;p.replaying=false;p.current=~0U;
}
static void Observe(Fast::F3DGfx* command,unsigned ucode) {
    Packet& p=packet;if(!p.active)return;
    const unsigned opcode=unsigned(command->words.w0>>24);
    CAMPAIGN_DIAGNOSTIC_COUNT(++p.commands;);
    if(p.recording) {
        if(p.overflow){p.current=~0U;return;}
        Instruction* destination=p.instructions.AppendUninitialized();
        if(!destination){p.overflow=true;p.current=~0U;return;}
        Instruction& op=*destination;
        op.Initialize(command,unsigned(command->words.w0),unsigned(command->words.w1),
                      ucode,opcode==0xdd ? Ucode:Generic);
        if(ucode!=4)p.conditional=true; // This executable prototype targets F3DEX2 only.
        p.current=unsigned(p.instructions.size());
        p.instructions.PublishAppend();
    } else {
        CAMPAIGN_DIAGNOSTIC_COUNT(++p.repeated;);
        if(p.cursor>=p.instructions.size())p.matching=false;
        else {
            const Instruction& expected=p.instructions[p.cursor];
            // Pointer patching by the original VTX/TIMG loaders is legal.
            // This oracle checks path, ucode and immutable command-header identity;
            // resource operands require explicit pins in the executable packet.
            if(expected.source!=command || expected.word0!=command->words.w0 || expected.ucode!=ucode) {
                if(p.matching)++p.mismatches[opcode];
                p.matching=false;
            }
        }
        ++p.cursor;
    }
}
}

namespace UpdateStream {
static void CaptureVertices(size_t count,size_t first,const Fast::F3DVtx* data,const void* rsp,size_t rspSize) {
    Packet& p=packet;if(!p.active||!p.recording||p.current>=p.instructions.size())return;
    Instruction& op=p.instructions[p.current];const unsigned code=op.word0>>24;
    if(code!=0x01 && code!=0x32)return;
    if(!data || count>64 || first>64 || count>64-first ||
       !Shipyard::Fast3D::VertexSourceDisjoint(data,count*sizeof(*data),rsp,rspSize) || p.vertices.size()+count>65536) {
        p.conditional=true;return;
    }
    op.kind=Vertices;op.payload[0]=unsigned(count);op.payload[1]=unsigned(first);op.payload[2]=unsigned(p.vertices.size());
    op.vertexSource=data;
    p.vertices.insert(p.vertices.end(),data,data+count);
}
static void CaptureTexture(unsigned format,unsigned size,unsigned width,unsigned flags,
                           const Fast::RawTexMetadata& metadata,const void* address) {
    Packet& p=packet;if(!p.active||!p.recording||p.current>=p.instructions.size())return;
    Instruction& op=p.instructions[p.current];
    // Only these single-image commands are lowered to one resolved texture op.
    const unsigned code=op.word0>>24;if(code!=0x20 && code!=0xfd)return;
    if(p.textures.size()==4096){p.conditional=true;return;}
    TextureInput input;input.format=format;input.size=size;input.width=width;input.flags=flags;
    input.address=address;input.metadata=metadata;
    op.kind=TextureImage;op.payload[0]=unsigned(p.textures.size());p.textures.push_back(input);
}
}

extern "C" void XboxBeginUpdateStream() {
    LaneWork::geometryMode=CVarGetInteger("gSettings.XboxLaneGeometry",0);
    LaneWork::mode=CVarGetInteger("gSettings.XboxLaneSemantic",0);
    LaneWork::enabled=CVarGetInteger("gSettings.XboxLaneWorkProfile",0)!=0;
    Fast::LaneSemantic::BeginUpdate();
    ++StreamOutputOracle::update;StreamOutputOracle::enabled=CVarGetInteger("gSettings.XboxPreparedStreamOracle",0)!=0;
    StreamEntryCounts::enabled=CVarGetInteger("gSettings.XboxPreparedStreamProfile",0)!=0;
    UpdateStream::mode=CVarGetInteger("gSettings.XboxPreparedStream",0);
    UpdateStream::Packet& p=UpdateStream::packet;
    Fast::LaneLighting::Begin();
    p.active=UpdateStream::mode!=0;p.instructions.clear();p.executable.clear();p.sealed=false;p.supported=true;p.pass=0;p.cursor=0;
    p.matching=true;p.overflow=false;p.conditional=false;p.recording=false;p.replaying=false;p.current=~0U;
    p.vertices.clear();p.textures.clear();p.owners.clear();p.arguments.clear();
}
extern "C" void XboxEndUpdateStream() {
    LaneWork::EndUpdate();LaneWork::lane=3;
    StreamEntryCounts::EndUpdate();StreamEntryCounts::bucket=3;
    UpdateStream::Packet& p=UpdateStream::packet;if(!p.active)return;
    p.active=false;++p.updates;
    if(p.pass<2)++p.skipped;
    else if(p.matching&&!p.overflow)++p.stable;
    else ++p.variant;
    if(p.conditional)++p.conditionalUpdates;
    if(p.updates==120) {
        SPDLOG_INFO("update-stream mode={} updates={} stable={} variant={} single={} conditional={} commands={} repeated={} scope=authentic_update_path_oracle",
            UpdateStream::mode,p.updates,p.stable,p.variant,p.skipped,p.conditionalUpdates,p.commands,p.repeated);
        for(unsigned i=0;i<256;++i)if(p.mismatches[i])SPDLOG_INFO("update-stream divergence opcode={} updates={}",i,p.mismatches[i]);
        SPDLOG_INFO("update-stream prepared replayed={} vertex_ops={} texture_ops={} tri_pairs={} instruction_bytes={}",
            p.replayed,p.typedVertices,p.typedTextures,p.typedTriangles,sizeof(UpdateStream::Instruction));
        SPDLOG_INFO("stream-input checks={} failures={} omitted={}",p.inputChecks,p.inputFailures,p.omitted);
        p.inputChecks=p.inputFailures=p.omitted=0;
        p.replayed=p.typedVertices=p.typedTextures=p.typedTriangles=0;
        p.updates=p.stable=p.variant=p.skipped=p.conditionalUpdates=p.commands=p.repeated=0;
        memset(p.mismatches,0,sizeof(p.mismatches));
    }
    p.instructions.clear();p.vertices.clear();p.textures.clear();p.owners.clear();p.arguments.clear();
}

namespace Fast {


namespace CampaignLightMath {
static __declspec(thread) int mode;
static __declspec(thread) unsigned long long calls,fallbacks,checks,mismatches;
struct Eligibility { const void* context; bool valid; };
static __declspec(thread) Eligibility eligible[64];
static __forceinline float Truncate(float value) {
    return Shipyard::Fast3D::TruncateLightChannel(value);
}
}
namespace CampaignOwnerGeneration {
struct Scope;
static __declspec(thread) Scope* current;
static __declspec(thread) int ownersMode,generationMode;
struct Scope {
    Scope* previous;
    bool enabled;
    std::shared_ptr<Ship::Context> context;
    std::shared_ptr<Ship::ResourceManager> resources;
    std::shared_ptr<Ship::ArchiveManager> archives;
    Scope() : previous(current), enabled(ownersMode!=0) {
        if(enabled) {
            context=Ship::Context::GetInstance();
            if(context)resources=context->GetResourceManager();
            if(resources)archives=resources->GetArchiveManager();
            current=this;
        }
    }
    ~Scope() { if(enabled)current=previous; }
};
struct Certificate {
    unsigned mutation,captured;
    const Interpreter* owner;
    unsigned presentations;
    unsigned long long attempts,hits,avoidedComparisons,oracleChecks,oracleFailures;
    void Mutate() { if(!++mutation) { mutation=1;captured=0;owner=NULL; } }
};
static __declspec(thread) Certificate certificate;
static __declspec(noinline) Ship::Context* ContextFallback() {return Ship::Context::GetInstance().get();}
static __declspec(noinline) Ship::ResourceManager* ResourceFallback() {return Ship::Context::GetInstance()->GetResourceManager().get();}
static __declspec(noinline) Ship::ArchiveManager* ArchiveFallback() {return Ship::Context::GetInstance()->GetResourceManager()->GetArchiveManager().get();}
}
static __forceinline Ship::Context* XboxRunContext() {
    return CampaignOwnerGeneration::current ? CampaignOwnerGeneration::current->context.get() : CampaignOwnerGeneration::ContextFallback();
}
static __forceinline Ship::ResourceManager* XboxRunResourceManager() {
    return CampaignOwnerGeneration::current ? CampaignOwnerGeneration::current->resources.get() : CampaignOwnerGeneration::ResourceFallback();
}
static __forceinline Ship::ArchiveManager* XboxRunArchiveManager() {
    return CampaignOwnerGeneration::current ? CampaignOwnerGeneration::current->archives.get() : CampaignOwnerGeneration::ArchiveFallback();
}

static void* UpdateStreamResource(uint64_t hash) {
    LaneWork::Add(LaneWork::ResourceResolve);
    if(!UpdateStream::packet.active || !UpdateStream::packet.recording)return XboxRunResourceManager()->GetResourceRawPointer(hash);
    std::shared_ptr<Ship::IResource> resource=XboxRunResourceManager()->LoadResource(hash);
    if(resource){if(UpdateStream::packet.owners.size()<8192)UpdateStream::packet.owners.push_back(resource);else UpdateStream::packet.overflow=true;}
    return resource ? resource->GetRawPointer():NULL;
}
static void* UpdateStreamResource(const char* path) {
    LaneWork::Add(LaneWork::ResourceResolve);
    if(!UpdateStream::packet.active || !UpdateStream::packet.recording)return XboxRunResourceManager()->GetResourceRawPointer(path);
    std::shared_ptr<Ship::IResource> resource=XboxRunResourceManager()->LoadResource(path);
    if(resource){if(UpdateStream::packet.owners.size()<8192)UpdateStream::packet.owners.push_back(resource);else UpdateStream::packet.overflow=true;}
    return resource ? resource->GetRawPointer():NULL;
}

static UcodeHandlers ucode_handler_index = ucode_f3dex2;

const static uint32_t f3dex2AttrHandler[] = {
    F3DEX2_G_MTX_PROJECTION, F3DEX2_G_MTX_LOAD,  F3DEX2_G_MTX_PUSH,  F3DEX_G_MTX_NOPUSH,
    F3DEX2_G_CULL_FRONT,     F3DEX2_G_CULL_BACK, F3DEX2_G_CULL_BOTH,
};

const static uint32_t f3dexAttrHandler[] = { F3DEX_G_MTX_PROJECTION, F3DEX_G_MTX_LOAD,   F3DEX_G_MTX_PUSH,
                                             F3DEX_G_MTX_NOPUSH,     F3DEX_G_CULL_FRONT, F3DEX_G_CULL_BACK,
                                             F3DEX_G_CULL_BOTH };

typedef const uint32_t (*UcodeAttributePointer)[7];
static const std::array<UcodeAttributePointer, 6> ucode_attr_handlers = { {
    &f3dexAttrHandler,  // ucode_f3db
    &f3dexAttrHandler,  // ucode_f3d
    &f3dexAttrHandler,  // ucode_f3dex
    &f3dexAttrHandler,  // ucode_f3exb
    &f3dex2AttrHandler, // ucode_f3ex2
    &f3dex2AttrHandler, // ucode_s2dex
} };

static uint32_t get_attr(Attribute attr) {
    const auto ucode_map = ucode_attr_handlers[ucode_handler_index];
    // assert(ucode_map->contains(attr) && "Attribute not found in the current ucode handler");
    return (*ucode_map)[attr];
}



const size_t MAX_TRI_BUFFER = 256;

Interpreter::Interpreter() : mRenderingState(), mTextureCache(), mXboxTileTrialEnabled(false), mXboxTileCaptureEnabled(false), mXboxDiscardGameDepth(false), mXboxCanDiscardGameColor(false), mPrevCombiner(mColorCombinerPool.end()), mTexUploadBuffer(nullptr), mGfxCurrentWindowDimensions(), mCurWindowPosX(), mCurWindowPosY(), mCurDimensions(), mPrvDimensions(), mGameWindowViewport(), mNativeDimensions(), mPrevNativeDimensions(), mGfxFrameBuffer(), mMsaaLevel(1), mDroppedFrame(), mBufVboLen(), mBufVboNumTris(), mWapi(nullptr), mRapi(nullptr), mFbActive(), mRendersToFb(), mGameFb(), mGameFbMsaaResolved() {
    mXboxTrianglePairActive = false;
    mXboxTrianglePairPrepared = false;
    memset(mXboxDeferredVertices, 0, sizeof(mXboxDeferredVertices));
    memset(mXboxDeferredContexts, 0, sizeof(mXboxDeferredContexts));
    mXboxDeferredReplay = false;
    mXboxContextProbeCapture = false;
    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;
    std::fill(mSegmentPointers, mSegmentPointers + sizeof(mSegmentPointers)/sizeof(mSegmentPointers[0]), 0);
    mRsp = Shipyard::Fast3D::NewValueInitialized<RSP>();
    mRsp->xboxMPDirty = false;
    mRdp = Shipyard::Fast3D::NewValueInitialized<RDP>();
    mBufVbo = new float[MAX_TRI_BUFFER * (32 * 3)];
}

Interpreter::~Interpreter() {
    delete mRsp;
    delete mRdp;
    delete[] mBufVbo;
}

static std::weak_ptr<Interpreter> mInstance;
typedef Shipyard::Fast3D::DispatchOwner<Interpreter> XboxDispatchOwner;
static __declspec(thread) XboxDispatchOwner* sXboxDispatchOwner = 0;
static __forceinline Interpreter* XboxDispatchInterpreter() {
    if (sXboxDispatchOwner) return sXboxDispatchOwner->Get(mInstance);
    return XboxDispatchOwner::TemporaryBorrow(mInstance);
}
// Set a cached pointer to the instance so we don't need to go through the window every time
void GfxSetInstance(std::shared_ptr<Interpreter> gfx) {
    mInstance = gfx;
    XboxDispatchOwner::Invalidate(sXboxDispatchOwner);
}

void Interpreter::Flush() {
    CampaignTriRun::cache.Reset();
    if (mBufVboLen > 0) {
        LaneWork::Add(LaneWork::NativeDraw);
        StreamOutputOracle::Draw(mBufVbo,mBufVboLen,mBufVboNumTris);
        mRapi->DrawTriangles(mBufVbo, mBufVboLen, mBufVboNumTris);
        mBufVboLen = 0;
        mBufVboNumTris = 0;
    }
}

ShaderProgram* Interpreter::LookupOrCreateShaderProgram(uint64_t id0, uint64_t id1) {
    ShaderProgram* prg = mRapi->LookupShader(id0, id1);
    if (prg == nullptr) {
        (mXboxPipelineKey.valid=false, mRapi->UnloadShader(mRenderingState.mShaderProgram));
        prg = mRapi->CreateAndLoadNewShader(id0, id1);
        mRenderingState.mShaderProgram = prg;
    }
    return prg;
}

const char* Interpreter::CCMUXtoStr(uint32_t ccmux) {
    static const std::array<const char*, 16> tbl = { {
        "G_CCMUX_COMBINED",
        "G_CCMUX_TEXEL0",
        "G_CCMUX_TEXEL1",
        "G_CCMUX_PRIMITIVE",
        "G_CCMUX_SHADE",
        "G_CCMUX_ENVIRONMENT",
        "G_CCMUX_1",
        "G_CCMUX_COMBINED_ALPHA",
        "G_CCMUX_TEXEL0_ALPHA",
        "G_CCMUX_TEXEL1_ALPHA",
        "G_CCMUX_PRIMITIVE_ALPHA",
        "G_CCMUX_SHADE_ALPHA",
        "G_CCMUX_ENV_ALPHA",
        "G_CCMUX_LOD_FRACTION",
        "G_CCMUX_PRIM_LOD_FRAC",
        "G_CCMUX_K5",
    } };
    if (ccmux > tbl.size()) {
        return "G_CCMUX_0";
    }
    return tbl[ccmux];
}

// Seems unused
const char* Interpreter::ACMUXtoStr(uint32_t acmux) {
    static const std::array<const char*, 8> tbl = { {
        "G_ACMUX_COMBINED or G_ACMUX_LOD_FRACTION",
        "G_ACMUX_TEXEL0",
        "G_ACMUX_TEXEL1",
        "G_ACMUX_PRIMITIVE",
        "G_ACMUX_SHADE",
        "G_ACMUX_ENVIRONMENT",
        "G_ACMUX_1 or G_ACMUX_PRIM_LOD_FRAC",
        "G_ACMUX_0",
    } };
    return tbl[acmux];
}

void Interpreter::GenerateCC(ColorCombiner* comb, const ColorCombinerKey& key) {
    const bool is2Cyc = (key.options & SHADER_OPT(_2CYC)) != 0;

    uint8_t c[2][2][4];
    uint64_t shaderId0 = 0;
    uint32_t shaderId1 = key.options;
    uint8_t shaderInputMapping[2][7] = { { 0 } };
    bool usedTextures[2] = {};
    for (uint32_t i = 0; i < 2 && (i == 0 || is2Cyc); i++) {
        uint32_t rgbA = (key.combine_mode >> (i * 28)) & 0xf;
        uint32_t rgbB = (key.combine_mode >> (i * 28 + 4)) & 0xf;
        uint32_t rgbC = (key.combine_mode >> (i * 28 + 8)) & 0x1f;
        uint32_t rgbD = (key.combine_mode >> (i * 28 + 13)) & 7;
        uint32_t alphaA = (key.combine_mode >> (i * 28 + 16)) & 7;
        uint32_t alphaB = (key.combine_mode >> (i * 28 + 16 + 3)) & 7;
        uint32_t alphaC = (key.combine_mode >> (i * 28 + 16 + 6)) & 7;
        uint32_t alphaD = (key.combine_mode >> (i * 28 + 16 + 9)) & 7;

        if (rgbA >= 8) {
            rgbA = G_CCMUX_0;
        }
        if (rgbB >= 8) {
            rgbB = G_CCMUX_0;
        }
        if (rgbC >= 16) {
            rgbC = G_CCMUX_0;
        }
        if (rgbD == 7) {
            rgbD = G_CCMUX_0;
        }

        if (rgbA == rgbB || rgbC == G_CCMUX_0) {
            // Normalize
            rgbA = G_CCMUX_0;
            rgbB = G_CCMUX_0;
            rgbC = G_CCMUX_0;
        }
        if (alphaA == alphaB || alphaC == G_ACMUX_0) {
            // Normalize
            alphaA = G_ACMUX_0;
            alphaB = G_ACMUX_0;
            alphaC = G_ACMUX_0;
        }
        if (i == 1) {
            if (rgbA != G_CCMUX_COMBINED && rgbB != G_CCMUX_COMBINED && rgbC != G_CCMUX_COMBINED &&
                rgbD != G_CCMUX_COMBINED) {
                // First cycle RGB not used, so clear it away
                c[0][0][0] = c[0][0][1] = c[0][0][2] = c[0][0][3] = G_CCMUX_0;
            }
            if (rgbC != G_CCMUX_COMBINED_ALPHA && alphaA != G_ACMUX_COMBINED && alphaB != G_ACMUX_COMBINED &&
                alphaD != G_ACMUX_COMBINED) {
                // First cycle ALPHA not used, so clear it away
                c[0][1][0] = c[0][1][1] = c[0][1][2] = c[0][1][3] = G_ACMUX_0;
            }
        }

        c[i][0][0] = rgbA;
        c[i][0][1] = rgbB;
        c[i][0][2] = rgbC;
        c[i][0][3] = rgbD;
        c[i][1][0] = alphaA;
        c[i][1][1] = alphaB;
        c[i][1][2] = alphaC;
        c[i][1][3] = alphaD;
    }
    if (!is2Cyc) {
        for (uint32_t i = 0; i < 2; i++) {
            for (uint32_t k = 0; k < 4; k++) {
                c[1][i][k] = i == 0 ? G_CCMUX_0 : G_ACMUX_0;
            }
        }
    }
    {
        uint8_t inputNumber[32] = { 0 };
        uint32_t nextInputNumber = SHADER_INPUT_1;
        for (uint32_t i = 0; i < 2 && (i == 0 || is2Cyc); i++) {
            for (uint32_t j = 0; j < 4; j++) {
                uint32_t val = 0;
                switch (c[i][0][j]) {
                    case G_CCMUX_0:
                        val = SHADER_0;
                        break;
                    case G_CCMUX_1:
                        val = SHADER_1;
                        break;
                    case G_CCMUX_TEXEL0:
                        val = SHADER_TEXEL0;
                        // Set the opposite texture when reading from the second cycle color options
                        if (i == 0) {
                            usedTextures[0] = true;
                        } else {
                            usedTextures[1] = true;
                        }
                        break;
                    case G_CCMUX_TEXEL1:
                        val = SHADER_TEXEL1;
                        if (i == 0) {
                            usedTextures[1] = true;
                        } else {
                            usedTextures[0] = true;
                        }
                        break;
                    case G_CCMUX_TEXEL0_ALPHA:
                        val = SHADER_TEXEL0A;
                        if (i == 0) {
                            usedTextures[0] = true;
                        } else {
                            usedTextures[1] = true;
                        }
                        break;
                    case G_CCMUX_TEXEL1_ALPHA:
                        val = SHADER_TEXEL1A;
                        if (i == 0) {
                            usedTextures[1] = true;
                        } else {
                            usedTextures[0] = true;
                        }
                        break;
                    case G_CCMUX_NOISE:
                        val = SHADER_NOISE;
                        break;
                    case G_CCMUX_PRIMITIVE:
                    case G_CCMUX_PRIMITIVE_ALPHA:
                    case G_CCMUX_PRIM_LOD_FRAC:
                    case G_CCMUX_SHADE:
                    case G_CCMUX_ENVIRONMENT:
                    case G_CCMUX_ENV_ALPHA:
                    case G_CCMUX_LOD_FRACTION:
                        if (inputNumber[c[i][0][j]] == 0) {
                            shaderInputMapping[0][nextInputNumber - 1] = c[i][0][j];
                            inputNumber[c[i][0][j]] = nextInputNumber++;
                        }
                        val = inputNumber[c[i][0][j]];
                        break;
                    case G_CCMUX_COMBINED:
                        val = SHADER_COMBINED;
                        break;
                    default:
                        fprintf(stderr, "Unsupported ccmux: %d\n", c[i][0][j]);
                        break;
                }
                shaderId0 |= (uint64_t)val << (i * 32 + j * 4);
            }
        }
    }
    {
        uint8_t inputNumber[16] = { 0 };
        uint32_t nextInputNumber = SHADER_INPUT_1;
        for (uint32_t i = 0; i < 2; i++) {
            for (uint32_t j = 0; j < 4; j++) {
                uint32_t val = 0;
                switch (c[i][1][j]) {
                    case G_ACMUX_0:
                        val = SHADER_0;
                        break;
                    case G_ACMUX_TEXEL0:
                        val = SHADER_TEXEL0;
                        // Set the opposite texture when reading from the second cycle color options
                        if (i == 0) {
                            usedTextures[0] = true;
                        } else {
                            usedTextures[1] = true;
                        }
                        break;
                    case G_ACMUX_TEXEL1:
                        val = SHADER_TEXEL1;
                        if (i == 0) {
                            usedTextures[1] = true;
                        } else {
                            usedTextures[0] = true;
                        }
                        break;
                    case G_ACMUX_LOD_FRACTION:
                        // case G_ACMUX_COMBINED: same numerical value
                        if (j != 2) {
                            val = SHADER_COMBINED;
                            break;
                        }
                        c[i][1][j] = G_CCMUX_LOD_FRACTION;
                        /* fall through */; // for G_ACMUX_LOD_FRACTION
                    case G_ACMUX_1:
                        // case G_ACMUX_PRIM_LOD_FRAC: same numerical value
                        if (j != 2) {
                            val = SHADER_1;
                            break;
                        }
                        /* fall through */; // for G_ACMUX_PRIM_LOD_FRAC
                    case G_ACMUX_PRIMITIVE:
                    case G_ACMUX_SHADE:
                    case G_ACMUX_ENVIRONMENT:
                        if (inputNumber[c[i][1][j]] == 0) {
                            shaderInputMapping[1][nextInputNumber - 1] = c[i][1][j];
                            inputNumber[c[i][1][j]] = nextInputNumber++;
                        }
                        val = inputNumber[c[i][1][j]];
                        break;
                }
                shaderId0 |= (uint64_t)val << (i * 32 + 16 + j * 4);
            }
        }
    }
    comb->shader_id0 = shaderId0;
    comb->shader_id1 = shaderId1;
    comb->usedTextures[0] = usedTextures[0];
    comb->usedTextures[1] = usedTextures[1];
    // comb->prg = gfx_lookup_or_create_mShaderProgram(shader_id0, shader_id1);
    memcpy(comb->shader_input_mapping, shaderInputMapping, sizeof(shaderInputMapping));
}

__forceinline ColorCombiner* Interpreter::LookupOrCreateColorCombiner(const ColorCombinerKey& key) {
    if (mPrevCombiner != mColorCombinerPool.end() && mPrevCombiner->first == key) {
        return &mPrevCombiner->second;
    }
    return XboxLookupColorCombinerCold(key);
}

__declspec(noinline) ColorCombiner* Interpreter::XboxLookupColorCombinerCold(const ColorCombinerKey& key) {
    mPrevCombiner = mColorCombinerPool.find(key);
    if (mPrevCombiner != mColorCombinerPool.end()) {
        return &mPrevCombiner->second;
    }
    Flush();
    mPrevCombiner = mColorCombinerPool.insert(std::make_pair(key, ColorCombiner())).first;
    GenerateCC(&mPrevCombiner->second, key);
    return &mPrevCombiner->second;
}

namespace LaneTextures {
static unsigned epoch=1;
static TextureCacheNode* Find(int i,const TextureCacheKey& key);
static void Save(int i,TextureCacheNode* node);
}
void Interpreter::TextureCacheClear() {
    ++LaneTextures::epoch;
    mXboxTextureHashCache.Clear();
    Flush();
    (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
    { auto&& _configRange14995 = mTextureCache.map; auto _configIt14995 = Shipyard::Resources::begin(_configRange14995); auto _configEnd14995 = Shipyard::Resources::end(_configRange14995); for (; _configIt14995 != _configEnd14995; ++_configIt14995) { const auto& entry = *_configIt14995; 
        mTextureCache.free_texture_ids.push_back(entry.second.texture_id);
     } }
    mTextureCache.map.clear();
    mTextureCache.lru.clear();
}

bool Interpreter::TextureCacheLookup(int i, const TextureCacheKey& key) {
    TextureCacheNode* xboxBoundNode = mXboxTextureBindings.Bound<TextureCacheNode>(i);
    TextureCacheNode* certified=xboxBoundNode && xboxBoundNode->first==key ? xboxBoundNode : LaneTextures::Find(i,key);
    TextureCacheMap::iterator it;
    if(certified)it=certified->second.lru_location->it;
    else {LaneWork::Add(LaneWork::TextureSearch);it=mTextureCache.map.find(key);}
    TextureCacheNode** n = &mRenderingState.mTextures[i];

    if (it != mTextureCache.map.end()) {
        TextureCacheNode* node=&*it;
        const Shipyard::Fast3D::TextureSamplerState sampler(it->second.linear_filter,
                                                             it->second.cms,it->second.cmt);
        if (mXboxTextureBindings.NeedsSelect(i,node,it->second.texture_id,sampler)) {
            Flush();
            (mXboxPipelineKey.valid=false, mRapi->SelectTexture(i,it->second.texture_id));
            mXboxTextureBindings.Selected(i,node,it->second.texture_id,sampler);
        }
        *n = node;LaneTextures::Save(i,node);
        mTextureCache.lru.splice(mTextureCache.lru.end(), mTextureCache.lru,
                                 it->second.lru_location); // move to back
        return true;
    }

    Flush();
    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {
        (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
        // Remove the texture that was least recently used
        it = mTextureCache.lru.front().it;
        mTextureCache.free_texture_ids.push_back(it->second.texture_id);
        ++LaneTextures::epoch;
        mTextureCache.map.erase(it);
        mTextureCache.lru.pop_front();
    }

    uint32_t texture_id;
    if (!mTextureCache.free_texture_ids.empty()) {
        texture_id = mTextureCache.free_texture_ids.back();
        mTextureCache.free_texture_ids.pop_back();
    } else {
        texture_id = mRapi->NewTexture();
    }

    it = mTextureCache.map.insert(std::make_pair(key, TextureCacheValue())).first;
    TextureCacheNode* node = &*it;
    node->second.texture_id = texture_id;
    TextureCacheMapIter location = { it };
    node->second.lru_location = mTextureCache.lru.insert(mTextureCache.lru.end(), location);

    (mXboxPipelineKey.valid=false, mRapi->SelectTexture(i, texture_id));
    (mXboxPipelineKey.valid=false, mRapi->SetSamplerParameters(i, false, 0, 0));
    mXboxTextureBindings.Selected(i,node,texture_id,Shipyard::Fast3D::TextureSamplerState());
    *n = node;LaneTextures::Save(i,node);
    return false;
}

std::string Interpreter::GetBaseTexturePath(const std::string& path) {
    if (Shipyard::Resources::starts_with(path, Ship::IResource::gAltAssetPrefix)) {
        return path.substr(Ship::IResource::gAltAssetPrefix.length());
    }

    return path;
}

void Interpreter::TextureCacheDelete(const uint8_t* origAddr) {
    ++LaneTextures::epoch;
    mXboxTextureHashCache.Clear();
    Flush();
    (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
    while (mTextureCache.map.bucket_count() > 0) {
        TextureCacheKey key = { origAddr, { 0 }, 0, 0, 0 }; // bucket index only depends on the address
        size_t bucket = mTextureCache.map.bucket(key);
        bool again = false;
        for (auto it = mTextureCache.map.begin(bucket); it != mTextureCache.map.end(bucket); ++it) {
            if (it->first.texture_addr == origAddr) {
                mTextureCache.lru.erase(it->second.lru_location);
                mTextureCache.free_texture_ids.push_back(it->second.texture_id);
                mTextureCache.map.erase(it->first);
                again = true;
                break;
            }
        }
        if (!again) {
            break;
        }
    }
}

void Interpreter::ImportTextureRgba16(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureRgba16: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t line_size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes / 2;
    uint32_t height = sizeBytes / mRdp->texture_tile[tile].line_size_bytes;

    // A single line of pixels should not equal the entire image (height == 1 non-withstanding)
    if (fullImageLineSizeBytes == sizeBytes) {
        fullImageLineSizeBytes = width * 2;
    }

    uint32_t i = 0;

    for (uint32_t y = 0; y < height; y++) {
        for (uint32_t x = 0; x < width; x++) {
            uint32_t clrIdx = (y * (fullImageLineSizeBytes / 2)) + (x);

            uint16_t col16 = (addr[2 * clrIdx] << 8) | addr[2 * clrIdx + 1];
            uint8_t a = col16 & 1;
            uint8_t r = col16 >> 11;
            uint8_t g = (col16 >> 6) & 0x1f;
            uint8_t b = (col16 >> 1) & 0x1f;
            mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);
            mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);
            mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);
            mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;

            i++;
        }
    }

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureRgba32(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureRgba32: null texture address for tile {}", tile);
        return;
    }

    uint32_t size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t full_image_line_size_bytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t line_size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;
    SUPPORT_CHECK(full_image_line_size_bytes == line_size_bytes);

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes / 2;
    uint32_t height = (size_bytes / 2) / mRdp->texture_tile[tile].line_size_bytes;
    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(addr, width, height));
}

void Interpreter::ImportTextureIA4(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureIA4: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t lineSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;
    SUPPORT_CHECK(fullImageLineSizeBytes == lineSizeBytes);

    for (uint32_t i = 0; i < sizeBytes * 2; i++) {
        uint8_t byte = addr[i / 2];
        uint8_t part = (byte >> (4 - (i % 2) * 4)) & 0xf;
        uint8_t intensity = part >> 1;
        uint8_t alpha = part & 1;
        uint8_t r = intensity;
        uint8_t g = intensity;
        uint8_t b = intensity;
        mTexUploadBuffer[4 * i + 0] = SCALE_3_8(r);
        mTexUploadBuffer[4 * i + 1] = SCALE_3_8(g);
        mTexUploadBuffer[4 * i + 2] = SCALE_3_8(b);
        mTexUploadBuffer[4 * i + 3] = alpha ? 255 : 0;
    }

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes * 2;
    uint32_t height = sizeBytes / mRdp->texture_tile[tile].line_size_bytes;

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureIA8(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureIA8: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t lineSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;
    SUPPORT_CHECK(fullImageLineSizeBytes == lineSizeBytes);

    for (uint32_t i = 0; i < sizeBytes; i++) {
        uint8_t intensity = addr[i] >> 4;
        uint8_t alpha = addr[i] & 0xf;
        uint8_t r = intensity;
        uint8_t g = intensity;
        uint8_t b = intensity;
        mTexUploadBuffer[4 * i + 0] = SCALE_4_8(r);
        mTexUploadBuffer[4 * i + 1] = SCALE_4_8(g);
        mTexUploadBuffer[4 * i + 2] = SCALE_4_8(b);
        mTexUploadBuffer[4 * i + 3] = SCALE_4_8(alpha);
    }

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes;
    uint32_t height = sizeBytes / mRdp->texture_tile[tile].line_size_bytes;

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureIA16(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureIA16: null texture address for tile {}", tile);
        return;
    }

    uint32_t size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t full_image_line_size_bytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t line_size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes / 2;
    uint32_t height = size_bytes / mRdp->texture_tile[tile].line_size_bytes;

    // A single line of pixels should not equal the entire image (height == 1 non-withstanding)
    if (full_image_line_size_bytes == size_bytes) {
        full_image_line_size_bytes = width * 2;
    }

    uint32_t i = 0;

    for (uint32_t y = 0; y < height; y++) {
        for (uint32_t x = 0; x < width; x++) {
            uint32_t clrIdx = (y * (full_image_line_size_bytes / 2)) + (x);

            uint8_t intensity = addr[2 * clrIdx];
            uint8_t alpha = addr[2 * clrIdx + 1];
            uint8_t r = intensity;
            uint8_t g = intensity;
            uint8_t b = intensity;
            mTexUploadBuffer[4 * i + 0] = r;
            mTexUploadBuffer[4 * i + 1] = g;
            mTexUploadBuffer[4 * i + 2] = b;
            mTexUploadBuffer[4 * i + 3] = alpha;

            i++;
        }
    }

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureI4(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureI4: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t lineSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes * 2;
    uint32_t height = sizeBytes / mRdp->texture_tile[tile].line_size_bytes;

    // A single line of pixels should not equal the entire image (height == 1 non-withstanding)
    if (fullImageLineSizeBytes == sizeBytes) {
        fullImageLineSizeBytes = width / 2;
    }

    uint32_t i = 0;

    for (uint32_t y = 0; y < height; y++) {
        for (uint32_t x = 0; x < width; x++) {
            uint32_t clrIdx = (y * (fullImageLineSizeBytes * 2)) + (x);

            uint8_t byte = addr[clrIdx / 2];
            uint8_t part = (byte >> (4 - (clrIdx % 2) * 4)) & 0xf;
            uint8_t intensity = part;
            uint8_t r = intensity;
            uint8_t g = intensity;
            uint8_t b = intensity;
            uint8_t a = intensity;
            mTexUploadBuffer[4 * i + 0] = SCALE_4_8(r);
            mTexUploadBuffer[4 * i + 1] = SCALE_4_8(g);
            mTexUploadBuffer[4 * i + 2] = SCALE_4_8(b);
            mTexUploadBuffer[4 * i + 3] = SCALE_4_8(a);

            i++;
        }
    }

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureI8(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureI8: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t full_image_line_size_bytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t line_size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    for (uint32_t i = 0; i < sizeBytes; i++) {
        uint8_t intensity = addr[i];
        mTexUploadBuffer[4 * i + 0] = intensity;
        mTexUploadBuffer[4 * i + 1] = intensity;
        mTexUploadBuffer[4 * i + 2] = intensity;
        mTexUploadBuffer[4 * i + 3] = intensity;
    }

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes;
    uint32_t height = sizeBytes / mRdp->texture_tile[tile].line_size_bytes;

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureCi4(int tile, bool importReplacement) {
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureCi4: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t lineSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;
    uint32_t palIdx = mRdp->texture_tile[tile].palette; // 0-15

    const uint8_t* palette;

    if (palIdx > 7)
        palette = mRdp->palettes[palIdx / 8]; // 16 pixel entries, 16 bits each
    else
        palette = mRdp->palettes[palIdx / 8] + (palIdx % 8) * 16 * 2;

    SUPPORT_CHECK(fullImageLineSizeBytes == lineSizeBytes);

    for (uint32_t i = 0; i < sizeBytes * 2; i++) {
        uint8_t byte = addr[i / 2];
        uint8_t idx = (byte >> (4 - (i % 2) * 4)) & 0xf;
        uint16_t col16 = (palette[idx * 2] << 8) | palette[idx * 2 + 1]; // Big endian load
        uint8_t a = col16 & 1;
        uint8_t r = col16 >> 11;
        uint8_t g = (col16 >> 6) & 0x1f;
        uint8_t b = (col16 >> 1) & 0x1f;
        mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);
        mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);
        mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);
        mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;
    }

    uint32_t resultLineSizeBytes = mRdp->texture_tile[tile].line_size_bytes;
    if (metadata->h_byte_scale != 1) {
        resultLineSizeBytes *= metadata->h_byte_scale;
    }

    uint32_t width = resultLineSizeBytes * 2;
    uint32_t height = sizeBytes / resultLineSizeBytes;

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureCi8(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureCi8: null texture address for tile {}", tile);
        return;
    }

    uint32_t sizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t lineSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    for (uint32_t i = 0, j = 0; i < sizeBytes; j += fullImageLineSizeBytes - lineSizeBytes) {
        for (uint32_t k = 0; k < lineSizeBytes; i++, k++, j++) {
            uint8_t idx = addr[j];
            uint16_t col16 = (mRdp->palettes[idx / 128][(idx % 128) * 2] << 8) |
                             mRdp->palettes[idx / 128][(idx % 128) * 2 + 1]; // Big endian load
            uint8_t a = col16 & 1;
            uint8_t r = col16 >> 11;
            uint8_t g = (col16 >> 6) & 0x1f;
            uint8_t b = (col16 >> 1) & 0x1f;
            mTexUploadBuffer[4 * i + 0] = SCALE_5_8(r);
            mTexUploadBuffer[4 * i + 1] = SCALE_5_8(g);
            mTexUploadBuffer[4 * i + 2] = SCALE_5_8(b);
            mTexUploadBuffer[4 * i + 3] = a ? 255 : 0;
        }
    }

    uint32_t resultLineSizeBytes = mRdp->texture_tile[tile].line_size_bytes;
    if (metadata->h_byte_scale != 1) {
        resultLineSizeBytes *= metadata->h_byte_scale;
    }

    uint32_t width = resultLineSizeBytes;
    uint32_t height = sizeBytes / resultLineSizeBytes;

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::ImportTextureImg(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureImg: null texture address for tile {}", tile);
        return;
    }

    uint16_t width = metadata->width;
    uint16_t height = metadata->height;
    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(addr, width, height));
}

void Interpreter::ImportTextureRaw(int tile, bool importReplacement) {
    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* addr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr;

    if (addr == nullptr) {
        SPDLOG_ERROR("ImportTextureRaw: null texture address for tile {}", tile);
        return;
    }

    uint16_t width = metadata->width;
    uint16_t height = metadata->height;
    Fast::TextureType type = metadata->type;
    std::shared_ptr<Fast::Texture> resource = metadata->resource;

    // if texture type is CI4 or CI8 we need to apply tlut to it
    switch (type.GetValue()) {
        case Fast::TextureType::Palette4bpp:
            ImportTextureCi4(tile, importReplacement);
            return;
        case Fast::TextureType::Palette8bpp:
            ImportTextureCi8(tile, importReplacement);
            return;
        default:
            break;
    }

    uint32_t numLoadedBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes;
    uint32_t numOriginallyLoadedBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].orig_size_bytes;

    uint32_t resultOrigLineSize = mRdp->texture_tile[tile].line_size_bytes;
    switch (mRdp->texture_tile[tile].siz) {
        case G_IM_SIZ_32b:
            resultOrigLineSize *= 2;
            break;
    }
    uint32_t resultOrigHeight = numOriginallyLoadedBytes / resultOrigLineSize;
    uint32_t resultNewLineSize = resultOrigLineSize * metadata->h_byte_scale;
    uint32_t resultNewHeight = resultOrigHeight * metadata->v_pixel_scale;

    if (resultNewLineSize == 4 * width && resultNewHeight == height) {
        // Can use the texture directly since it has the correct dimensions
        (mXboxPipelineKey.valid=false, mRapi->UploadTexture(addr, width, height));
        return;
    }

    uint32_t fullImageLineSizeBytes =
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes;
    uint32_t line_size_bytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes;

    // Get the resource's true image size
    uint32_t resourceImageSizeBytes = resource->ImageDataSize;
    uint32_t safeFullImageLineSizeBytes = fullImageLineSizeBytes;
    uint32_t safeLineSizeBytes = line_size_bytes;
    uint32_t safeLoadedBytes = numLoadedBytes;

    // Sometimes the texture load commands will specify a size larger than the authentic texture
    // Normally the OOB info is read as garbage, but will cause a crash on some platforms
    // Restrict the bytes to a safe amount
    if (numLoadedBytes > resourceImageSizeBytes) {
        safeLoadedBytes = resourceImageSizeBytes;
        safeLineSizeBytes = resourceImageSizeBytes;
        safeFullImageLineSizeBytes = resourceImageSizeBytes;
    }

    // Safely only copy the amount of bytes the resource can allow
    for (uint32_t i = 0, j = 0; i < safeLoadedBytes; i += safeLineSizeBytes, j += safeFullImageLineSizeBytes) {
        memcpy(mTexUploadBuffer + i, addr + j, safeLineSizeBytes);
    }

    // Set the remaining bytes to load as 0
    if (numLoadedBytes > resourceImageSizeBytes) {
        memset(mTexUploadBuffer + resourceImageSizeBytes, 0, numLoadedBytes - resourceImageSizeBytes);
    }

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, resultNewLineSize / 4, resultNewHeight));
}

void Interpreter::ImportTexture(int i, int tile, bool importReplacement) {
    LaneWork::Add(LaneWork::TextureImport);LaneWork::Add(LaneWork::TextureMetadata);
    uint8_t fmt = mRdp->texture_tile[tile].fmt;
    uint8_t siz = mRdp->texture_tile[tile].siz;
    uint32_t texFlags = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].tex_flags;
    uint32_t tmemIdex = mRdp->texture_tile[tile].tmem_index;
    uint8_t paletteIndex = mRdp->texture_tile[tile].palette;
    uint32_t origSizeBytes = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].orig_size_bytes;

    const RawTexMetadata* metadata = &mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata;
    const uint8_t* origAddr =
        importReplacement && (metadata->resource != nullptr)
            ? mMaskedTextures.find(GetBaseTexturePath(metadata->resource->GetInitData()->Path))->second.replacementData
            : mRdp->loaded_texture[tmemIdex].addr;

    if (origAddr == nullptr) {
        SPDLOG_ERROR("ImportTexture: null texture address for tile {}", tile);
        return;
    }

    TextureCacheKey key;
    if (fmt == G_IM_FMT_CI) {
        { TextureCacheKey shipyardAggregate = { origAddr, { mRdp->palettes[0], mRdp->palettes[1] }, fmt, siz, paletteIndex, origSizeBytes }; key = shipyardAggregate; }
    } else {
        { TextureCacheKey shipyardAggregate = { origAddr, {}, fmt, siz, paletteIndex, origSizeBytes }; key = shipyardAggregate; }
    }

    if (TextureCacheLookup(i, key)) {
        return;
    }

    if ((texFlags & TEX_FLAG_LOAD_AS_IMG) != 0) {
        ImportTextureImg(tile, importReplacement);
        return;
    }

    // if load as raw is set then we load_raw();
    if ((texFlags & TEX_FLAG_LOAD_AS_RAW) != 0) {
        ImportTextureRaw(tile, importReplacement);
        return;
    }

    switch (fmt) {
        case G_IM_FMT_RGBA:
            if (siz == G_IM_SIZ_16b) {
                ImportTextureRgba16(tile, importReplacement);
            } else if (siz == G_IM_SIZ_32b) {
                ImportTextureRgba32(tile, importReplacement);
            } else {
                SPDLOG_ERROR("RGBA Texture that isn't 16 or 32 bit. Size = {}", siz);
                // OTRTODO: Sometimes, seemingly randomly, we end up here. Could be a bad dlist, could be
                // something F3D does not have supported. Further investigation is needed.
            }
            break;
        case G_IM_FMT_IA:
            if (siz == G_IM_SIZ_4b) {
                ImportTextureIA4(tile, importReplacement);
            } else if (siz == G_IM_SIZ_8b) {
                ImportTextureIA8(tile, importReplacement);
            } else if (siz == G_IM_SIZ_16b) {
                ImportTextureIA16(tile, importReplacement);
            } else {
                SPDLOG_ERROR("IA Texture that isn't 4, 8, or 16 bit. Size = {}", siz);
                ;
            }
            break;
        case G_IM_FMT_CI:
            if (siz == G_IM_SIZ_4b) {
                ImportTextureCi4(tile, importReplacement);
            } else if (siz == G_IM_SIZ_8b) {
                ImportTextureCi8(tile, importReplacement);
            } else {
                SPDLOG_ERROR("CI Texture that isn't 4 or 8 bit. Size = {}", siz);
            }
            break;
        case G_IM_FMT_I:
            if (siz == G_IM_SIZ_4b) {
                ImportTextureI4(tile, importReplacement);
            } else if (siz == G_IM_SIZ_8b) {
                ImportTextureI8(tile, importReplacement);
            } else {
                SPDLOG_ERROR("I Texture that isn't 4 or 8 bit. Size = {}", siz);
            }
            break;
        case G_IM_FMT_YUV:
            SPDLOG_ERROR("YUV Textures not supported");
            break;
        default:
            SPDLOG_ERROR("Invalid texture format. Fmt = {}", fmt);
            break;
    }
}

void Interpreter::ImportTextureMask(int i, int tile) {
    uint32_t tmemIndex = mRdp->texture_tile[tile].tmem_index;
    RawTexMetadata metadata = mRdp->loaded_texture[tmemIndex].raw_tex_metadata;

    if (metadata.resource == nullptr) {
        return;
    }

    auto maskIter = mMaskedTextures.find(GetBaseTexturePath(metadata.resource->GetInitData()->Path));
    if (maskIter == mMaskedTextures.end()) {
        return;
    }

    const uint8_t* orig_addr = maskIter->second.mask;

    if (orig_addr == nullptr) {
        return;
    }

    TextureCacheKey key = { orig_addr, {}, 0, 0, 0, 0 };

    if (TextureCacheLookup(i, key)) {
        return;
    }

    uint32_t width = mRdp->texture_tile[tile].line_size_bytes;
    uint32_t height = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].orig_size_bytes /
                      mRdp->texture_tile[tile].line_size_bytes;
    switch (mRdp->texture_tile[tile].siz) {
        case G_IM_SIZ_4b:
            width *= 2;
            break;
        case G_IM_SIZ_8b:
        default:
            break;
        case G_IM_SIZ_16b:
            width /= 2;
            break;
        case G_IM_SIZ_32b:
            width /= 4;
            break;
    }

    for (uint32_t texIndex = 0; texIndex < width * height; texIndex++) {
        uint8_t masked = orig_addr[texIndex];
        if (masked) {
            mTexUploadBuffer[4 * texIndex + 0] = 0;
            mTexUploadBuffer[4 * texIndex + 1] = 0;
            mTexUploadBuffer[4 * texIndex + 2] = 0;
            mTexUploadBuffer[4 * texIndex + 3] = 0xFF;
        } else {
            mTexUploadBuffer[4 * texIndex + 0] = 0;
            mTexUploadBuffer[4 * texIndex + 1] = 0;
            mTexUploadBuffer[4 * texIndex + 2] = 0;
            mTexUploadBuffer[4 * texIndex + 3] = 0;
        }
    }

    (mXboxPipelineKey.valid=false, mRapi->UploadTexture(mTexUploadBuffer, width, height));
}

void Interpreter::NormalizeVector(float v[3]) {
    float s = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    v[0] /= s;
    v[1] /= s;
    v[2] /= s;
}

void Interpreter::TransposedMatrixMul(float res[3], const float a[3], const float b[4][4]) {
    res[0] = a[0] * b[0][0] + a[1] * b[0][1] + a[2] * b[0][2];
    res[1] = a[0] * b[1][0] + a[1] * b[1][1] + a[2] * b[1][2];
    res[2] = a[0] * b[2][0] + a[1] * b[2][1] + a[2] * b[2][2];
}

void Interpreter::MatrixMul(float res[4][4], const float a[4][4], const float b[4][4]) {
    float tmp[4][4];
    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            tmp[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] + a[i][3] * b[3][j];
        }
    }
    memcpy(res, tmp, sizeof(tmp));
}

void Interpreter::CalculateNormalDir(const F3DLight_t* light, float coeffs[3]) {
    float light_dir[3] = { light->dir[0] / 127.0f, light->dir[1] / 127.0f, light->dir[2] / 127.0f };

    Interpreter::TransposedMatrixMul(coeffs, light_dir,
                                     mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1]);
    Interpreter::NormalizeVector(coeffs);
}

void Interpreter::EnsureMatrixProduct() {
    if (!mRsp->xboxMPDirty) return;
    MatrixMul(mRsp->MP_matrix, mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1], mRsp->P_matrix);
    mRsp->xboxMPDirty = false;
}


namespace LaneGeometry {
typedef std::unordered_map<Mtx*,MtxF> MatrixMap;
struct __declspec(align(16)) MatrixState {
    float mv[11][4][4],projection[4][4],mp[4][4];
    unsigned size;bool known[11],projectionKnown,mpKnown,dirty;
};
struct __declspec(align(16)) Batch {
    float matrix[3][4][4];unsigned offset[3],count,first,width,height;bool valid;
    Batch():valid(false){}
};
static MatrixState states[3];static std::vector<Batch> batches;static std::vector<LoadedVertex> output;
void Begin(){
    memset(states,0,sizeof(states));for(unsigned l=0;l<3;++l)states[l].size=1;
    batches.clear();output.clear();if(batches.capacity()<4096)batches.reserve(4096);if(output.capacity()<32768)output.reserve(32768);
}
static bool Recording(){return LaneWork::geometryMode && LaneWork::lane==0 && LaneWork::laneCount==3 && LaneWork::matrixMaps &&
    UpdateStream::packet.active && UpdateStream::packet.recording && !UpdateStream::packet.conditional;}
static bool Product(MatrixState& s){
    if(s.dirty){s.mpKnown=s.size && s.known[s.size-1] && s.projectionKnown;
        if(s.mpKnown)Interpreter::MatrixMul(s.mp,s.mv[s.size-1],s.projection);s.dirty=false;}
    return s.mpKnown;
}
static void Matrix(unsigned parameters,const int32_t* addr,const float base[4][4],unsigned projection,unsigned load,unsigned push){
    if(!Recording())return;
    const MatrixMap* maps=static_cast<const MatrixMap*>(LaneWork::matrixMaps);
    __declspec(align(16)) float raw[4][4];bool rawReady=false;
    for(unsigned lane=1;lane<3;++lane){
        MatrixState& state=states[lane];__declspec(align(16)) float matrix[4][4];
        MatrixMap::const_iterator it=maps[lane].find((Mtx*)addr);
        if(it==maps[lane].end()){
            if(!rawReady){
                if(maps[0].find((Mtx*)addr)==maps[0].end())memcpy(raw,base,64);
                else {
#ifndef GBI_FLOATS
                    for(int i=0;i<4;++i)for(int j=0;j<4;j+=2){
                        int32_t ip=addr[i*2+j/2];uint32_t fp=addr[8+i*2+j/2];
                        raw[i][j]=(int32_t)((ip&0xffff0000)|(fp>>16))/65536.0f;
                        raw[i][j+1]=(int32_t)((ip<<16)|(fp&0xffff))/65536.0f;
                    }
#else
                    memcpy(raw,addr,64);
#endif
                }
                rawReady=true;
            }
            memcpy(matrix,raw,64);
        }
        else if(!Shipyard::Fast3D::NearestRounding() || !Shipyard::Fast3D::QuantizeMatrix(it->second.mf,matrix)){
            for(int i=0;i<4;++i)for(int j=0;j<4;++j){float v=it->second.mf[i][j];int value=(int)(v*65536.0f);matrix[i][j]=value*(1.0f/65536.0f);}
        }
        if(parameters&projection){
            if(parameters&load){memcpy(state.projection,matrix,64);state.projectionKnown=true;}
            else if(state.projectionKnown)Interpreter::MatrixMul(state.projection,matrix,state.projection);
        }else{
            if((parameters&push) && state.size<11){
                ++state.size;
                if(!(parameters&load)){state.known[state.size-1]=state.size>1 && state.known[state.size-2];
                    if(state.known[state.size-1])memcpy(state.mv[state.size-1],state.mv[state.size-2],64);}
            }
            if(parameters&load){if(!state.size)++state.size;memcpy(state.mv[state.size-1],matrix,64);state.known[state.size-1]=true;}
            else if(state.size && state.known[state.size-1])Interpreter::MatrixMul(state.mv[state.size-1],matrix,state.mv[state.size-1]);
        }
        state.dirty=true;
    }
}
static void Pop(unsigned count){if(!Recording())return;
    for(unsigned lane=1;lane<3;++lane)for(unsigned i=0;i<count;++i){MatrixState& s=states[lane];if(s.size){if(s.size==1)Product(s);--s.size;if(s.size)s.dirty=true;}}
}
static UpdateStream::Instruction* VertexOp(){
    UpdateStream::Packet& p=UpdateStream::packet;
    if(!p.active || (!p.recording&&!p.replaying) || p.current>=p.instructions.size())return NULL;
    UpdateStream::Instruction& op=p.instructions[p.current];return op.kind==UpdateStream::Vertices?&op:NULL;
}
static bool Consume(Interpreter* owner,unsigned count,unsigned first){
    if(!LaneWork::geometryMode || LaneWork::lane<1 || LaneWork::lane>2 || owner->mFbActive)return false;
    UpdateStream::Instruction* op=VertexOp();if(!op || op->positionPlan>=batches.size())return false;
    const Batch& b=batches[op->positionPlan];const unsigned lane=LaneWork::lane;owner->EnsureMatrixProduct();
    if(!b.valid || b.count!=count || b.first!=first || b.width!=owner->mCurDimensions.width || b.height!=owner->mCurDimensions.height ||
       memcmp(b.matrix[lane],owner->mRsp->MP_matrix,64)){LaneWork::Add(LaneWork::MatrixGuardMiss);return false;}
    for(unsigned i=0;i<count;++i){LoadedVertex& dst=owner->mRsp->loaded_vertices[first+i];const LoadedVertex& src=output[b.offset[lane]+i];
        memcpy(&dst.x,&src.x,16);dst.clip_rej=src.clip_rej;}
    LaneWork::Add(LaneWork::FutureConsumed,count);return true;
}
static bool Produce(Interpreter* owner,unsigned count,unsigned first,const F3DVtx* source){
    if(!Recording() || owner->mFbActive || count>64 || first+count>64 || !Shipyard::Fast3D::NearestRounding())return false;
    UpdateStream::Instruction* op=VertexOp();if(!op || !Product(states[1]) || !Product(states[2]) || batches.size()>=4096 || output.size()+2*count>65536)return false;
    owner->EnsureMatrixProduct();Batch b;b.count=count;b.first=first;b.width=owner->mCurDimensions.width;b.height=owner->mCurDimensions.height;
    memcpy(b.matrix[0],owner->mRsp->MP_matrix,64);memcpy(b.matrix[1],states[1].mp,64);memcpy(b.matrix[2],states[2].mp,64);
    b.offset[1]=unsigned(output.size());b.offset[2]=b.offset[1]+count;output.resize(output.size()+2*count);
    void* targets[3]={&owner->mRsp->loaded_vertices[first],&output[b.offset[1]],&output[b.offset[2]]};
    if(!Shipyard::Fast3D::CampaignTransformThree(source,count,b.matrix,targets,sizeof(LoadedVertex))){output.resize(b.offset[1]);return false;}
    const float denominator=float(b.width)/float(b.height);
    for(unsigned lane=0;lane<3;++lane){LoadedVertex* v=static_cast<LoadedVertex*>(targets[lane]);
        for(unsigned i=0;i<count;++i)v[i].x=v[i].x*(4.0f/3.0f)/denominator;
        Shipyard::Fast3D::ClipVertices(v,count,false);
        if(LaneWork::enabled){LaneWork::counts[lane][LaneWork::TransformVertices]+=count;if(lane)LaneWork::counts[lane][LaneWork::FuturePrepared]+=count;}
    }
    LaneWork::Add(LaneWork::SourceDecode,count);b.valid=true;op->positionPlan=unsigned(batches.size());batches.push_back(b);return true;
}
}

void Interpreter::GfxSpMatrix(uint8_t parameters, const int32_t* addr) {
    if(UpdateStream::packet.active && UpdateStream::packet.recording && UpdateStream::packet.current<UpdateStream::packet.instructions.size()) {
        UpdateStream::Instruction& op=UpdateStream::packet.instructions[UpdateStream::packet.current];
        op.kind=UpdateStream::Matrix;op.payload[0]=parameters;op.payload[1]=unsigned(uintptr_t(addr));
    }
    __declspec(align(16)) float matrix[4][4];

    { auto it = mCurMtxReplacements->find((Mtx*)addr); if (it != mCurMtxReplacements->end()) {
        if (!Shipyard::Fast3D::NearestRounding() || !Shipyard::Fast3D::QuantizeMatrix(it->second.mf, matrix)) {
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) {
                float v = it->second.mf[i][j];
                int as_int = (int)(v * 65536.0f);
                matrix[i][j] = as_int * (1.0f / 65536.0f);
            }
        }
        }
    } else {
#ifndef GBI_FLOATS
        // Original GBI where fixed point matrices are used
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j += 2) {
                int32_t int_part = addr[i * 2 + j / 2];
                uint32_t frac_part = addr[8 + i * 2 + j / 2];
                matrix[i][j] = (int32_t)((int_part & 0xffff0000) | (frac_part >> 16)) / 65536.0f;
                matrix[i][j + 1] = (int32_t)((int_part << 16) | (frac_part & 0xffff)) / 65536.0f;
            }
        }
#else
        // For a modified GBI where fixed point values are replaced with floats
        memcpy(matrix, addr, sizeof(matrix));
#endif
    } }

    const int8_t mtx_projection = get_attr(MTX_PROJECTION);
    const int8_t mtx_load = get_attr(MTX_LOAD);
    const int8_t mtx_push = get_attr(MTX_PUSH);
    LaneGeometry::Matrix(parameters,addr,matrix,mtx_projection,mtx_load,mtx_push);

    if (parameters & mtx_projection) {
        if (parameters & mtx_load) {
            memcpy(mRsp->P_matrix, matrix, sizeof(matrix));
        } else {
            MatrixMul(mRsp->P_matrix, matrix, mRsp->P_matrix);
        }
    } else { // G_MTX_MODELVIEW
        if ((parameters & mtx_push) && mRsp->modelview_matrix_stack_size < 11) {
            ++mRsp->modelview_matrix_stack_size;
            if (!(parameters & mtx_load))
            memcpy(mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1],
                   mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 2], sizeof(matrix));
        }
        if (parameters & mtx_load) {
            if (mRsp->modelview_matrix_stack_size == 0)
                ++mRsp->modelview_matrix_stack_size;
            memcpy(mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1], matrix, sizeof(matrix));
        } else {
            MatrixMul(mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1], matrix,
                      mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1]);
        }
        CampaignDeferredState::snapshot.Invalidate(); mRsp->lights_changed = 1;
    }
    mRsp->xboxMPDirty = true;
}

void Interpreter::GfxSpPopMatrix(uint32_t count) {
    LaneGeometry::Pop(count);
    while (count--) {
        if (mRsp->modelview_matrix_stack_size > 0) {
            if (mRsp->modelview_matrix_stack_size == 1) EnsureMatrixProduct();
            --mRsp->modelview_matrix_stack_size;
            if (mRsp->modelview_matrix_stack_size > 0) {
                mRsp->xboxMPDirty = true;
            }
        }
    }
    CampaignDeferredState::snapshot.Invalidate(); mRsp->lights_changed = true;
}

float Interpreter::AdjXForAspectRatio(float x) const {
    if (mFbActive) {
        return x;
    } else {
        return x * (4.0f / 3.0f) / ((float)mCurDimensions.width / (float)mCurDimensions.height);
    }
}

// Scale the width and height value based on the ratio of the viewport to the native size
void Interpreter::AdjustWidthHeightForScale(uint32_t& width, uint32_t& height, uint32_t nativeWidth,
                                            uint32_t nativeHeight) const {
    width = Shipyard::Fast3D::Round(width * (mCurDimensions.width / (2.0f * (nativeWidth / 2))));
    height = Shipyard::Fast3D::Round(height * (mCurDimensions.height / (2.0f * (nativeHeight / 2))));

    if (width == 0) {
        width = 1;
    }
    if (height == 0) {
        height = 1;
    }
}



namespace LaneLighting {
struct Batch {XboxDeferredContext context;unsigned start,count,first;};
struct Attributes {float u,v;uint8_t r,g,b,valid;};
static std::vector<Batch> batches;static std::vector<Attributes> values;
static unsigned batchCount,valueCount,batchStorage,valueStorage;
static unsigned slots[MAX_VERTICES];
void BeginPass(){memset(slots,0xff,sizeof(slots));}
void Begin(){batchCount=valueCount=0;BeginPass();}
static void Discard(unsigned slot){if(slot<MAX_VERTICES)slots[slot]=~0U;}
static bool Same(const XboxDeferredContext& a,const XboxDeferredContext& b){
    return a.count==b.count && a.scaleS==b.scaleS && a.scaleT==b.scaleT &&
        !memcmp(a.ambient,b.ambient,sizeof(a.ambient)) &&
        !memcmp(a.lights,b.lights,a.count*sizeof(XboxDeferredLight));
}
static void Bind(unsigned count,unsigned first,const XboxDeferredContext& context){
    UpdateStream::Packet& p=UpdateStream::packet;
    if(!LaneWork::mode || CampaignLightMath::mode!=1 || !p.active ||
       (!p.recording&&!p.replaying) || p.current>=p.instructions.size())return;
    UpdateStream::Instruction& op=p.instructions[p.current];
    if(op.kind!=UpdateStream::Vertices)return;
    if(op.lightPlan==~0U){
        if(!p.recording || batchCount>=4096 || valueCount+count>65536)return;
        const unsigned index=batchCount++;
        if(index==batchStorage){batches.push_back(Batch());++batchStorage;}
        Batch& batch=batches[index];batch.context=context;batch.start=valueCount;batch.count=count;batch.first=first;
        valueCount+=count;
        if(valueCount>valueStorage){values.resize(valueCount);valueStorage=valueCount;}
        for(unsigned i=0;i<count;++i)values[batch.start+i].valid=0;
        op.lightPlan=index;
    }
    if(op.lightPlan>=batchCount)return;
    const Batch& batch=batches[op.lightPlan];LaneWork::Add(LaneWork::DependencyCheck);
    if(batch.count!=count || batch.first!=first || !Same(batch.context,context))return;
    for(unsigned i=0;i<count;++i)slots[first+i]=batch.start+i;
}
static bool Load(unsigned slot,LoadedVertex* output){
    const unsigned index=slots[slot];if(index>=valueCount)return false;
    const Attributes& a=values[index];if(!a.valid)return false;
    output->u=a.u;output->v=a.v;output->color.r=a.r;output->color.g=a.g;output->color.b=a.b;
    LaneWork::Add(LaneWork::LightReuse);return true;
}
static void Save(unsigned slot,const LoadedVertex* input){
    const unsigned index=slots[slot];if(index>=valueCount)return;
    Attributes& a=values[index];a.u=input->u;a.v=input->v;a.r=input->color.r;a.g=input->color.g;a.b=input->color.b;a.valid=1;
}
}

// MODERN DEFERRED LIT FOG BEGIN
void Interpreter::XboxDiscardVertex(size_t index) {
    LaneLighting::Discard(unsigned(index));
    if (index >= MAX_VERTICES) return;
    XboxDeferredVertex& pending = mXboxDeferredVertices[index];
    if (pending.context) {
        --pending.context->references;
        pending.context = NULL;
    }
}

// MODERN VTX HASH PHASE PROFILE BEGIN
static __declspec(thread) ModernFrameProfile::VtxHashSample* sModernVtxHashSample = NULL;
static __declspec(thread) int sCampaignVtxBatch;
static __declspec(thread) unsigned long long sCampaignVtxBatches,sCampaignVtxFallbacks,sCampaignVtxChecks,sCampaignVtxMismatches;
static __declspec(noinline) bool CampaignDeferredPositions(Interpreter* owner,size_t count,size_t first,const F3DVtx* source) {
    if(LaneGeometry::Consume(owner,unsigned(count),unsigned(first)))return true;
    if(LaneGeometry::Produce(owner,unsigned(count),unsigned(first),source))return true;
    LaneWork::Add(LaneWork::SourceDecode,unsigned(count));LaneWork::Add(LaneWork::TransformVertices,unsigned(count));
    owner->EnsureMatrixProduct();
    if(!Shipyard::Fast3D::NearestRounding())return false;
    LoadedVertex* positions=&owner->mRsp->loaded_vertices[first];
    Shipyard::Fast3D::TransformPhaseHook hook;
    if(sModernVtxHashSample) {
        hook.enterVertices=ModernFrameProfile::EnterVtxTransformLoop;
        hook.context=sModernVtxHashSample;
        ModernFrameProfile::BeginVtxTransform(*sModernVtxHashSample,(unsigned)count);
    }
    const bool ok=sModernVtxHashSample ?
        Shipyard::Fast3D::CampaignTransformDirectProfiled(source,count,owner->mRsp->MP_matrix,positions,false,sizeof(LoadedVertex),&hook) :
        Shipyard::Fast3D::CampaignTransformDirect(source,count,owner->mRsp->MP_matrix,positions,false,sizeof(LoadedVertex));
    if(sModernVtxHashSample) {
        ModernFrameProfile::EndVtxTransform(*sModernVtxHashSample,ok);
        sModernVtxHashSample->vmx=ok;
    }
    if(!ok)return false;
    const bool aspect=!owner->mFbActive;
    const float denominator=aspect ? float(owner->mCurDimensions.width)/float(owner->mCurDimensions.height) : 1.0f;
    for(size_t i=0;i<count;++i) {
        LoadedVertex& d=owner->mRsp->loaded_vertices[first+i];
        d.x=aspect ? positions[i].x*(4.0f/3.0f)/denominator : owner->AdjXForAspectRatio(positions[i].x);
        // VMX already published x/y/z/w directly into the cached RSP array.
    }
    Shipyard::Fast3D::ClipVertices(&owner->mRsp->loaded_vertices[first],count,false);
    return true;
}
// MODERN VTX HASH PHASE PROFILE END

bool Interpreter::XboxTryDeferVertices(size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {
    LaneWork::Add(LaneWork::DeferredSetup);
    if (mXboxDeferredReplay) return false;
    if (!vertices || !n_vertices || n_vertices > MAX_VERTICES ||
        dest_index > MAX_VERTICES || n_vertices > MAX_VERTICES - dest_index) {
        return false;
    }
    if (!Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx), mRsp, sizeof(*mRsp))) {
        // A command may reinterpret earlier loaded-vertex bytes as its
        // source. Restore every pending slot before the eager fallback reads
        // any of the RSP. This branch is outside the normal disjoint path.
        for (size_t i = 0; i < MAX_VERTICES; ++i) XboxMaterializeVertex(i);
        for (size_t i = 0; i < n_vertices; ++i) XboxDiscardVertex(dest_index + i);
        return false;
    }
    for (size_t i = 0; i < n_vertices; ++i) XboxDiscardVertex(dest_index + i);
    if ((mRsp->geometry_mode & (G_LIGHTING | G_FOG | G_TEXTURE_GEN)) != (G_LIGHTING | G_FOG) ||
        (mRsp->geometry_mode & G_LIGHTING_POSITIONAL) ||
        mRsp->current_num_lights == 0 || mRsp->current_num_lights > MAX_LIGHTS + 1) {
        return false;
    }

    CampaignDeferredState::Snapshot& snapshot=CampaignDeferredState::snapshot;
    const bool reuseCandidate=sCampaignVtxBatch && snapshot.owner==this && snapshot.captured==snapshot.epoch &&
        snapshot.context && !mRsp->lights_changed && ucode_handler_index==UcodeHandlers::ucode_f3dex2;
    XboxDeferredContext* context=reuseCandidate ? static_cast<XboxDeferredContext*>(snapshot.context):NULL;
    if(context && sCampaignVtxBatch==2) {
        // Compare to what the original snapshot builder would copy, field by field.
        ++snapshot.checks;
        bool same=context->count==mRsp->current_num_lights-1 &&
            context->scaleS==mRsp->texture_scaling_factor.s && context->scaleT==mRsp->texture_scaling_factor.t &&
            context->fogMul==Shipyard::Fast3D::SignedShortFloat(mRsp->fog_mul) && context->fogOffset==Shipyard::Fast3D::SignedShortFloat(mRsp->fog_offset);
        if(same) {
            for(unsigned c=0;c<3;++c)if(context->ambient[c]!=mRsp->current_lights[context->count].l.col[c])same=false;
            for(unsigned i=0;i<context->count;++i)for(unsigned c=0;c<3;++c)
                if(memcmp(&context->lights[i].coeff[c],&mRsp->current_lights_coeffs[i][c],sizeof(float)) ||
                   context->lights[i].color[c]!=(float)mRsp->current_lights[i].l.col[c])same=false;
        }
        if(!same){++snapshot.failures;context=NULL;snapshot.Invalidate();}
    }
    const bool reused=context!=NULL;
    for (size_t i = 0; !context && i < MAX_VERTICES; ++i) {

        if (!mXboxDeferredContexts[i].references) {
            context = &mXboxDeferredContexts[i];
            break;
        }
    }
    if (mXboxContextProbeCapture) {
        // Include exhausted searches; no counter work occurs inside the scan.
        const unsigned scanned = context ? (unsigned)(context - mXboxDeferredContexts) + 1 : MAX_VERTICES;
        ++mXboxContextSearchAttempts;
        mXboxContextSlotsScanned += scanned;
        if (scanned > mXboxContextMaxScan) mXboxContextMaxScan = scanned;
    }
    if (!context) return false;

    if(!reused) {
    CAMPAIGN_DIAGNOSTIC_COUNT(++snapshot.created;);LaneWork::Add(LaneWork::LightSetup);
    // The eager path refreshes these on its first lit vertex.
    if (mRsp->lights_changed) {
        for (int i = 0; i < mRsp->current_num_lights - 1; ++i)
            CalculateNormalDir(&mRsp->current_lights[i].l, mRsp->current_lights_coeffs[i]);
        CalculateNormalDir(&mRsp->lookat[0], mRsp->current_lookat_coeffs[0]);
        CalculateNormalDir(&mRsp->lookat[1], mRsp->current_lookat_coeffs[1]);
        mRsp->lights_changed = false;
    }
    context->count = mRsp->current_num_lights - 1;
    for (int c = 0; c < 3; ++c) context->ambient[c] = mRsp->current_lights[context->count].l.col[c];
    for (int i = 0; i < context->count; ++i) {
        for (int c = 0; c < 3; ++c) {
            context->lights[i].coeff[c] = mRsp->current_lights_coeffs[i][c];
            context->lights[i].color[c] = (float)mRsp->current_lights[i].l.col[c];
        }
    }
    CampaignLightMath::Eligibility& mathEligibility=CampaignLightMath::eligible[context-mXboxDeferredContexts];
    mathEligibility.context=context;
    mathEligibility.valid=context->count<=32;
    for(unsigned i=0;i<context->count;++i)
        for(unsigned c=0;c<3;++c) {
            const float value=context->lights[i].coeff[c];
            if(!(value>=-2.0f && value<=2.0f))mathEligibility.valid=false;
        }
    context->scaleS = mRsp->texture_scaling_factor.s;
    context->scaleT = mRsp->texture_scaling_factor.t;
    context->fogMul = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_mul);
    context->fogOffset = Shipyard::Fast3D::SignedShortFloat(mRsp->fog_offset);
    snapshot.owner=this;snapshot.context=context;snapshot.captured=snapshot.epoch;
    } else CAMPAIGN_DIAGNOSTIC_COUNT(++snapshot.reused;);


    // Reuse the authoritative VMX/aspect/clip transform with attributes off.
    struct ReplayGuard {
        Interpreter* self;
        uint32_t mode;
        ReplayGuard(Interpreter* s) : self(s), mode(s->mRsp->geometry_mode) {
            self->mXboxDeferredReplay = true;
            self->mRsp->geometry_mode &= ~(G_LIGHTING | G_FOG);
        }
        ~ReplayGuard() {
            self->mRsp->geometry_mode = mode;
            self->mXboxDeferredReplay = false;
        }
    };
    {
        ReplayGuard guard(this);
        if (sModernVtxHashSample) ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);
        if(sCampaignVtxBatch && CampaignDeferredPositions(this,n_vertices,dest_index,vertices)) {
            CAMPAIGN_DIAGNOSTIC_COUNT(++sCampaignVtxBatches;);
            if(sCampaignVtxBatch==2) {
                static __declspec(thread) float before[MAX_VERTICES][4];
                static __declspec(thread) unsigned char clip[MAX_VERTICES];
                for(size_t i=0;i<n_vertices;++i) {
                    memcpy(before[i],&mRsp->loaded_vertices[dest_index+i].x,16);
                    clip[i]=mRsp->loaded_vertices[dest_index+i].clip_rej;
                }
                XboxGfxSpVertexEager(n_vertices,dest_index,vertices);
                for(size_t i=0;i<n_vertices;++i) {
                    ++sCampaignVtxChecks;
                    if(memcmp(before[i],&mRsp->loaded_vertices[dest_index+i].x,16) ||
                        clip[i]!=mRsp->loaded_vertices[dest_index+i].clip_rej)++sCampaignVtxMismatches;
                }
            }
        } else {
            if(sCampaignVtxBatch)CAMPAIGN_DIAGNOSTIC_COUNT(++sCampaignVtxFallbacks;);
            XboxGfxSpVertexEager(n_vertices,dest_index,vertices);
        }
    }
    if (sModernVtxHashSample) {
        sModernVtxHashSample->deferred = true;
        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashInsert);
    }
    LaneWork::Add(LaneWork::StaticAttributes,unsigned(n_vertices));
    for (size_t i = 0; i < n_vertices; ++i) {
        XboxDeferredVertex& pending = mXboxDeferredVertices[dest_index + i];
        pending.source = vertices[i];
        pending.context = context;
    }
    LaneLighting::Bind(unsigned(n_vertices),unsigned(dest_index),*context);
    context->references += (uint8_t)n_vertices;
    return true;
}

void Interpreter::XboxMaterializeVertexOriginal(size_t index) {
    if (index >= MAX_VERTICES) return;
    XboxDeferredVertex& pending = mXboxDeferredVertices[index];
    XboxDeferredContext* context = pending.context;
    if (!context) return;
    LaneWork::Add(LaneWork::Materialize);
    LoadedVertex* d = &mRsp->loaded_vertices[index];
    if(!LaneLighting::Load(unsigned(index),d)){
    LaneWork::Add(LaneWork::LightEvaluate);LaneWork::Add(LaneWork::AttributeEvaluate);
    const F3DVtx_t* v = &pending.source.v;
    const F3DVtx_tn* vn = &pending.source.n;
    short U = v->tc[0] * context->scaleS >> 16;
    short V = v->tc[1] * context->scaleT >> 16;
    d->u = U;
    d->v = V;
    int r = context->ambient[0], g = context->ambient[1], b = context->ambient[2];
    const float normal[3] = { (float)vn->n[0], (float)vn->n[1], (float)vn->n[2] };
    for (int i = 0; i < context->count; ++i) {
        float intensity = 0;
        intensity += normal[0] * context->lights[i].coeff[0];
        intensity += normal[1] * context->lights[i].coeff[1];
        intensity += normal[2] * context->lights[i].coeff[2];
        intensity /= 127.0f;
        if (intensity > 0.0f) {
            r += intensity * context->lights[i].color[0];
            g += intensity * context->lights[i].color[1];
            b += intensity * context->lights[i].color[2];
        }
    }
    d->color.r = r > 255 ? 255 : r;
    d->color.g = g > 255 ? 255 : g;
    d->color.b = b > 255 ? 255 : b;
    LaneLighting::Save(unsigned(index),d);
    }
    LaneWork::Add(LaneWork::FogEvaluate);
    float w = d->w;
    if (fabsf(w) < 0.001f) w = 0.001f;
    float winv = 1.0f / w;
    if (winv < 0.0f) winv = std::numeric_limits<int16_t>::max();
    float fog_z = d->z * winv * context->fogMul + context->fogOffset;
    fog_z = Ship::Math::clamp(fog_z, 0.0f, 255.0f);
    d->color.a = fog_z;
    XboxDiscardVertex(index);
}
void Interpreter::XboxMaterializeVertexMath(size_t index) {
    if (index >= MAX_VERTICES) return;
    XboxDeferredVertex& pending = mXboxDeferredVertices[index];
    XboxDeferredContext* context = pending.context;
    if (!context) return;
    LaneWork::Add(LaneWork::Materialize);
    LoadedVertex* d = &mRsp->loaded_vertices[index];
    if(!LaneLighting::Load(unsigned(index),d)){
    LaneWork::Add(LaneWork::LightEvaluate);LaneWork::Add(LaneWork::AttributeEvaluate);
    const F3DVtx_t* v = &pending.source.v;
    const F3DVtx_tn* vn = &pending.source.n;
    short U = v->tc[0] * context->scaleS >> 16;
    short V = v->tc[1] * context->scaleT >> 16;
    d->u = Shipyard::Fast3D::SignedShortFloat(U);
    d->v = Shipyard::Fast3D::SignedShortFloat(V);
    float r = Shipyard::Fast3D::LightByteFloat(context->ambient[0]), g = Shipyard::Fast3D::LightByteFloat(context->ambient[1]), b = Shipyard::Fast3D::LightByteFloat(context->ambient[2]);
    const float normal[3] = { Shipyard::Fast3D::NormalByteFloat(vn->n[0]), Shipyard::Fast3D::NormalByteFloat(vn->n[1]), Shipyard::Fast3D::NormalByteFloat(vn->n[2]) };
    for (int i = 0; i < context->count; ++i) {
        float intensity = 0;
        intensity += normal[0] * context->lights[i].coeff[0];
        intensity += normal[1] * context->lights[i].coeff[1];
        intensity += normal[2] * context->lights[i].coeff[2];
        intensity /= 127.0f;
        if (intensity > 0.0f) {
            r = CampaignLightMath::Truncate(r + intensity * context->lights[i].color[0]);
            g = CampaignLightMath::Truncate(g + intensity * context->lights[i].color[1]);
            b = CampaignLightMath::Truncate(b + intensity * context->lights[i].color[2]);
        }
    }
    d->color.r = r > 255 ? 255 : r;
    d->color.g = g > 255 ? 255 : g;
    d->color.b = b > 255 ? 255 : b;
    LaneLighting::Save(unsigned(index),d);
    }
    LaneWork::Add(LaneWork::FogEvaluate);
    float w = d->w;
    if (fabsf(w) < 0.001f) w = 0.001f;
    float winv = 1.0f / w;
    if (winv < 0.0f) winv = std::numeric_limits<int16_t>::max();
    float fog_z = d->z * winv * context->fogMul + context->fogOffset;
    fog_z = Ship::Math::clamp(fog_z, 0.0f, 255.0f);
    d->color.a = fog_z;
    XboxDiscardVertex(index);
}
void Interpreter::XboxMaterializeVertex(size_t index) {
    if(!CampaignLightMath::mode) { XboxMaterializeVertexOriginal(index);return; }
    if(index>=MAX_VERTICES)return;
    XboxDeferredContext* context=mXboxDeferredVertices[index].context;
    if(!context)return;
    const size_t slot=context-mXboxDeferredContexts;
    if(slot>=MAX_VERTICES || CampaignLightMath::eligible[slot].context!=context || !CampaignLightMath::eligible[slot].valid) {
        CAMPAIGN_DIAGNOSTIC_COUNT(++CampaignLightMath::fallbacks;);XboxMaterializeVertexOriginal(index);return;
    }
    CAMPAIGN_DIAGNOSTIC_COUNT(++CampaignLightMath::calls;);
    if(CampaignLightMath::mode==2) {
        LoadedVertex before=mRsp->loaded_vertices[index];
        const unsigned char references=context->references;
        XboxMaterializeVertexMath(index);
        LoadedVertex actual=mRsp->loaded_vertices[index];
        mRsp->loaded_vertices[index]=before;
        mXboxDeferredVertices[index].context=context;context->references=references;
        XboxMaterializeVertexOriginal(index);
        ++CampaignLightMath::checks;
        if(memcmp(&actual,&mRsp->loaded_vertices[index],sizeof(actual)))++CampaignLightMath::mismatches;
    } else XboxMaterializeVertexMath(index);
}


void Interpreter::XboxTakeContextSearchCounts(unsigned* attempts, unsigned* slots, unsigned* maximum) {
    *attempts = mXboxContextSearchAttempts;
    *slots = mXboxContextSlotsScanned;
    *maximum = mXboxContextMaxScan;
    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;
}
// MODERN DEFERRED LIT FOG END

void Interpreter::GfxSpVertex(size_t n_vertices,size_t dest_index,const F3DVtx* vertices) {
    UpdateStream::CaptureVertices(n_vertices,dest_index,vertices,mRsp,sizeof(*mRsp));
    if(sCampaignVtxBatch) {
        if(sModernVtxHashSample && !mXboxDeferredReplay)
            ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample,ModernFrameProfile::VtxHashDeferred);
        if(XboxTryDeferVertices(n_vertices,dest_index,vertices))return;
    }
    XboxGfxSpVertexEager(n_vertices,dest_index,vertices);
}
void Interpreter::XboxGfxSpVertexEager(size_t n_vertices, size_t dest_index, const F3DVtx* vertices) {
    LaneWork::Add(LaneWork::SourceDecode,unsigned(n_vertices));
    LaneWork::Add(LaneWork::TransformVertices,unsigned(n_vertices));LaneWork::Add(LaneWork::StaticAttributes,unsigned(n_vertices));
    if (sModernVtxHashSample && !mXboxDeferredReplay)
        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashDeferred);
    if (!sCampaignVtxBatch && XboxTryDeferVertices(n_vertices, dest_index, vertices)) return;
    if (sModernVtxHashSample && !mXboxDeferredReplay)
        ModernFrameProfile::AdvanceVtxHash(*sModernVtxHashSample, ModernFrameProfile::VtxHashTransform);
    EnsureMatrixProduct();
    static_assert(sizeof(F3DVtx) == 16, "Fast3D vertex input stride");
    static_assert(sizeof(LoadedVertex) == Shipyard::Fast3D::ClipVertexStride &&
                  offsetof(LoadedVertex, clip_rej) == Shipyard::Fast3D::ClipByteOffset &&
                  offsetof(LoadedVertex, x) == 0, "Fast3D clip layout");
    __declspec(align(16)) float shipyardTransformed[MAX_VERTICES][4];
    const size_t shipyardTransformFirst = dest_index;
    const bool shipyardTransformBatch = vertices != nullptr && n_vertices > 0 &&
        n_vertices <= MAX_VERTICES && dest_index <= MAX_VERTICES &&
        n_vertices <= MAX_VERTICES - dest_index &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices, n_vertices * sizeof(F3DVtx), mRsp, sizeof(*mRsp));
    const bool shipyardVectorEligible = shipyardTransformBatch &&
        Shipyard::Fast3D::NearestRounding();
    Shipyard::Fast3D::TransformPhaseHook shipyardPhaseHook;
    if (shipyardVectorEligible && sModernVtxHashSample) {
        shipyardPhaseHook.enterVertices = ModernFrameProfile::EnterVtxTransformLoop;
        shipyardPhaseHook.context = sModernVtxHashSample;
        ModernFrameProfile::BeginVtxTransform(*sModernVtxHashSample, (unsigned)n_vertices);
    }
    const bool shipyardVectorPositions = shipyardVectorEligible &&
        (sModernVtxHashSample
             ? Shipyard::Fast3D::TransformPositionsProfiled(
                   vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed,
                   false, 16, &shipyardPhaseHook)
             : Shipyard::Fast3D::TransformPositions(
                   vertices, n_vertices, mRsp->MP_matrix, shipyardTransformed));
    if (shipyardVectorEligible && sModernVtxHashSample)
        ModernFrameProfile::EndVtxTransform(*sModernVtxHashSample, shipyardVectorPositions);
    if (sModernVtxHashSample) sModernVtxHashSample->vmx = shipyardVectorPositions;
    bool shipyardAspectReady = false;
    float shipyardAspectDenominator;
    const bool shipyardLightColorBatch = shipyardTransformBatch && mRsp->current_num_lights > 0 && mRsp->current_num_lights <= MAX_LIGHTS + 1;
    bool shipyardLightColorReady[MAX_LIGHTS] = {};
    float shipyardLightColors[MAX_LIGHTS][3];
    for (size_t i = 0; i < n_vertices; i++, dest_index++) {
        const F3DVtx_t* v = &vertices[i].v;
        const F3DVtx_tn* vn = &vertices[i].n;
        struct LoadedVertex* d = &mRsp->loaded_vertices[dest_index];

        if (v == nullptr) {
            return;
        }

        float x, y, z, w;
        if (shipyardVectorPositions) {
            x = shipyardTransformed[i][0];
            y = shipyardTransformed[i][1];
            z = shipyardTransformed[i][2];
            w = shipyardTransformed[i][3];
        } else {
        x = v->ob[0] * mRsp->MP_matrix[0][0] + v->ob[1] * mRsp->MP_matrix[1][0] +
                  v->ob[2] * mRsp->MP_matrix[2][0] + mRsp->MP_matrix[3][0];
        y = v->ob[0] * mRsp->MP_matrix[0][1] + v->ob[1] * mRsp->MP_matrix[1][1] +
                  v->ob[2] * mRsp->MP_matrix[2][1] + mRsp->MP_matrix[3][1];
        z = v->ob[0] * mRsp->MP_matrix[0][2] + v->ob[1] * mRsp->MP_matrix[1][2] +
                  v->ob[2] * mRsp->MP_matrix[2][2] + mRsp->MP_matrix[3][2];
        w = v->ob[0] * mRsp->MP_matrix[0][3] + v->ob[1] * mRsp->MP_matrix[1][3] +
                  v->ob[2] * mRsp->MP_matrix[2][3] + mRsp->MP_matrix[3][3];

        }

        // MODERN DEFERRED POSITION REPLAY BEGIN
        // This path is reached only after a disjoint source and a successful
        // VMX transform. Pending vertices get their UV and color from the
        // captured source/context at materialization; only position and clip
        // may be observed before then.
        if (mXboxDeferredReplay && shipyardVectorPositions) {
            if (shipyardTransformBatch && !mFbActive) {
                if (!shipyardAspectReady) {
                    shipyardAspectDenominator = (float)mCurDimensions.width / (float)mCurDimensions.height;
                    shipyardAspectReady = true;
                }
                x = x * (4.0f / 3.0f) / shipyardAspectDenominator;
            } else {
                x = AdjXForAspectRatio(x);
            }
            d->x = x;
            d->y = y;
            d->z = z;
            d->w = w;
            continue;
        }
        // MODERN DEFERRED POSITION REPLAY END
        float world_pos[3] = { 0.0 };
        if (mRsp->geometry_mode & G_LIGHTING_POSITIONAL) {
            float(*mtx)[4] = mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1];
            world_pos[0] = v->ob[0] * mtx[0][0] + v->ob[1] * mtx[1][0] + v->ob[2] * mtx[2][0] + mtx[3][0];
            world_pos[1] = v->ob[0] * mtx[0][1] + v->ob[1] * mtx[1][1] + v->ob[2] * mtx[2][1] + mtx[3][1];
            world_pos[2] = v->ob[0] * mtx[0][2] + v->ob[1] * mtx[1][2] + v->ob[2] * mtx[2][2] + mtx[3][2];
        }

        if (shipyardTransformBatch && !mFbActive) {
            if (!shipyardAspectReady) {
                shipyardAspectDenominator = (float)mCurDimensions.width / (float)mCurDimensions.height;
                shipyardAspectReady = true;
            }
            x = x * (4.0f / 3.0f) / shipyardAspectDenominator;
        } else {
            x = AdjXForAspectRatio(x);
        }

        short U = v->tc[0] * mRsp->texture_scaling_factor.s >> 16;
        short V = v->tc[1] * mRsp->texture_scaling_factor.t >> 16;

        if (mRsp->geometry_mode & G_LIGHTING) {
            const bool shipyardNormalBatch = shipyardTransformBatch && (mRsp->current_num_lights > 1 || (mRsp->geometry_mode & G_TEXTURE_GEN));
            float shipyardNormal[3];
            if (shipyardNormalBatch) {
                shipyardNormal[0] = (float)vn->n[0];
                shipyardNormal[1] = (float)vn->n[1];
                shipyardNormal[2] = (float)vn->n[2];
            }

            if (mRsp->lights_changed) {
                for (int i = 0; i < mRsp->current_num_lights - 1; i++) {
                    CalculateNormalDir(&mRsp->current_lights[i].l, mRsp->current_lights_coeffs[i]);
                }
                /*static const Light_t lookat_x = {{0, 0, 0}, 0, {0, 0, 0}, 0, {127, 0, 0}, 0};
                static const Light_t lookat_y = {{0, 0, 0}, 0, {0, 0, 0}, 0, {0, 127, 0}, 0};*/
                CalculateNormalDir(&mRsp->lookat[0], mRsp->current_lookat_coeffs[0]);
                CalculateNormalDir(&mRsp->lookat[1], mRsp->current_lookat_coeffs[1]);
                mRsp->lights_changed = false;
            }

            int r = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[0];
            int g = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[1];
            int b = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[2];

            for (int i = 0; i < mRsp->current_num_lights - 1; i++) {
                float intensity = 0;
                if ((mRsp->geometry_mode & G_LIGHTING_POSITIONAL) && (mRsp->current_lights[i].p.unk3 != 0)) {
                    // Calculate distance from the light to the vertex
                    float dist_vec[3] = { mRsp->current_lights[i].p.pos[0] - world_pos[0],
                                          mRsp->current_lights[i].p.pos[1] - world_pos[1],
                                          mRsp->current_lights[i].p.pos[2] - world_pos[2] };
                    float dist_sq =
                        dist_vec[0] * dist_vec[0] + dist_vec[1] * dist_vec[1] +
                        dist_vec[2] * dist_vec[2] * 2; // The *2 comes from GLideN64, unsure of why it does it
                    float dist = sqrt(dist_sq);

                    // Transform distance vector (which acts as a direction light vector) into model's space
                    float light_model[3];
                    TransposedMatrixMul(light_model, dist_vec,
                                        mRsp->modelview_matrix_stack[mRsp->modelview_matrix_stack_size - 1]);

                    // Calculate intensity for each axis using standard formula for intensity
                    float light_intensity[3];
                    for (int light_i = 0; light_i < 3; light_i++) {
                        light_intensity[light_i] = 4.0f * light_model[light_i] / dist_sq;
                        light_intensity[light_i] = Shipyard::Fast3D::Clamp(light_intensity[light_i], -1.0f, 1.0f);
                    }

                    // Adjust intensity based on surface normal and sum up total
                    float total_intensity =
                        light_intensity[0] * (shipyardNormalBatch ? shipyardNormal[0] : vn->n[0]) + light_intensity[1] * (shipyardNormalBatch ? shipyardNormal[1] : vn->n[1]) + light_intensity[2] * (shipyardNormalBatch ? shipyardNormal[2] : vn->n[2]);
                    total_intensity = Shipyard::Fast3D::Clamp(total_intensity, -1.0f, 1.0f);

                    // Attenuate intensity based on attenuation values.
                    // Example formula found at https://ogldev.org/www/tutorial20/tutorial20.html
                    // Specific coefficients for MM's microcode sourced from GLideN64
                    // https://github.com/gonetz/GLideN64/blob/3b43a13a80dfc2eb6357673440b335e54eaa3896/src/gSP.cpp#L636
                    float distf = floorf(dist);
                    float attenuation = (distf * mRsp->current_lights[i].p.unk7 * 2.0f +
                                         distf * distf * mRsp->current_lights[i].p.unkE / 8.0f) /
                                            (float)0xFFFF +
                                        1.0f;
                    intensity = total_intensity / attenuation;
                } else {
                    intensity += (shipyardNormalBatch ? shipyardNormal[0] : vn->n[0]) * mRsp->current_lights_coeffs[i][0];
                    intensity += (shipyardNormalBatch ? shipyardNormal[1] : vn->n[1]) * mRsp->current_lights_coeffs[i][1];
                    intensity += (shipyardNormalBatch ? shipyardNormal[2] : vn->n[2]) * mRsp->current_lights_coeffs[i][2];
                    intensity /= 127.0f;
                }
                if (intensity > 0.0f) {
                    if (shipyardLightColorBatch && !shipyardLightColorReady[i]) {
                        shipyardLightColors[i][0] = (float)mRsp->current_lights[i].l.col[0];
                        shipyardLightColors[i][1] = (float)mRsp->current_lights[i].l.col[1];
                        shipyardLightColors[i][2] = (float)mRsp->current_lights[i].l.col[2];
                        shipyardLightColorReady[i] = true;
                    }

                    r += intensity * (shipyardLightColorBatch ? shipyardLightColors[i][0] : mRsp->current_lights[i].l.col[0]);
                    g += intensity * (shipyardLightColorBatch ? shipyardLightColors[i][1] : mRsp->current_lights[i].l.col[1]);
                    b += intensity * (shipyardLightColorBatch ? shipyardLightColors[i][2] : mRsp->current_lights[i].l.col[2]);
                }
            }

            d->color.r = r > 255 ? 255 : r;
            d->color.g = g > 255 ? 255 : g;
            d->color.b = b > 255 ? 255 : b;

            if (mRsp->geometry_mode & G_TEXTURE_GEN) {
                float dotx = 0, doty = 0;
                dotx += (shipyardNormalBatch ? shipyardNormal[0] : vn->n[0]) * mRsp->current_lookat_coeffs[0][0];
                dotx += (shipyardNormalBatch ? shipyardNormal[1] : vn->n[1]) * mRsp->current_lookat_coeffs[0][1];
                dotx += (shipyardNormalBatch ? shipyardNormal[2] : vn->n[2]) * mRsp->current_lookat_coeffs[0][2];
                doty += (shipyardNormalBatch ? shipyardNormal[0] : vn->n[0]) * mRsp->current_lookat_coeffs[1][0];
                doty += (shipyardNormalBatch ? shipyardNormal[1] : vn->n[1]) * mRsp->current_lookat_coeffs[1][1];
                doty += (shipyardNormalBatch ? shipyardNormal[2] : vn->n[2]) * mRsp->current_lookat_coeffs[1][2];

                dotx /= 127.0f;
                doty /= 127.0f;

                dotx = Ship::Math::clamp(dotx, -1.0f, 1.0f);
                doty = Ship::Math::clamp(doty, -1.0f, 1.0f);

                if (mRsp->geometry_mode & G_TEXTURE_GEN_LINEAR) {
                    // Not sure exactly what formula we should use to get accurate values
                    /*dotx = (2.906921f * dotx * dotx + 1.36114f) * dotx;
                    doty = (2.906921f * doty * doty + 1.36114f) * doty;
                    dotx = (dotx + 1.0f) / 4.0f;
                    doty = (doty + 1.0f) / 4.0f;*/
                    dotx = acosf(-dotx) /* M_PI */ * 0.159155f;
                    doty = acosf(-doty) /* M_PI */ * 0.159155f;
                } else {
                    dotx = (dotx + 1.0f) / 4.0f;
                    doty = (doty + 1.0f) / 4.0f;
                }

                U = (int32_t)(dotx * mRsp->texture_scaling_factor.s);
                V = (int32_t)(doty * mRsp->texture_scaling_factor.t);
            }
        } else {
            d->color.r = v->cn[0];
            d->color.g = v->cn[1];
            d->color.b = v->cn[2];
        }

        d->u = U;
        d->v = V;

        if (!shipyardVectorPositions) {
        // trivial clip rejection
        d->clip_rej = 0;
        if (x < -w) {
            d->clip_rej |= 1; // CLIP_LEFT
        }
        if (x > w) {
            d->clip_rej |= 2; // CLIP_RIGHT
        }
        if (y < -w) {
            d->clip_rej |= 4; // CLIP_BOTTOM
        }
        if (y > w) {
            d->clip_rej |= 8; // CLIP_TOP
        }
        // if (z < -w) d->clip_rej |= 16; // CLIP_NEAR
        if (z > w) {
            d->clip_rej |= 32; // CLIP_FAR
        }

        }

        d->x = x;
        d->y = y;
        d->z = z;
        d->w = w;

        if (mRsp->geometry_mode & G_FOG) {
            if (fabsf(w) < 0.001f) {
                // To avoid division by zero
                w = 0.001f;
            }

            float winv = 1.0f / w;
            if (winv < 0.0f) {
                winv = std::numeric_limits<int16_t>::max();
            }

            float fog_z = z * winv * mRsp->fog_mul + mRsp->fog_offset;
            fog_z = Ship::Math::clamp(fog_z, 0.0f, 255.0f);
            d->color.a = fog_z; // Use alpha variable to store fog factor
        } else {
            d->color.a = v->cn[3];
        }
    }
    if (shipyardVectorPositions) {
        Shipyard::Fast3D::ClipVertices(&mRsp->loaded_vertices[shipyardTransformFirst],
                                      n_vertices, false);
    }
}

void Interpreter::GfxSpModifyVertex(uint16_t vtx_idx, uint8_t where, uint32_t val) {
    SUPPORT_CHECK(where == G_MWO_POINT_ST);
    XboxMaterializeVertex(vtx_idx);

    int16_t s = (int16_t)(val >> 16);
    int16_t t = (int16_t)val;

    LoadedVertex* v = &mRsp->loaded_vertices[vtx_idx];
    v->u = s;
    v->v = t;
}

// MODERN MATERIAL CACHE BEGIN
struct ModernGeometryKey {
    uint32_t tileLine,originalSize;
    unsigned rounding;
    float uls,ult,lrs,lrt;
    uint8_t siz,cms,cmt;
    bool operator==(const ModernGeometryKey& rhs) const {
        return tileLine==rhs.tileLine && originalSize==rhs.originalSize &&
            rounding==rhs.rounding &&
            uls==rhs.uls && ult==rhs.ult && lrs==rhs.lrs && lrt==rhs.lrt &&
            siz==rhs.siz && cms==rhs.cms && cmt==rhs.cmt;
    }
};
struct ModernGeometryValue {
    uint32_t width,height,boundWidth,boundHeight,clampMask;
    uint8_t cms,cmt;
};
template<class Tile,class Loaded> struct ModernGeometryBuilder {
    const Tile& tileState;
    const Loaded& loadedState;
    __declspec(noinline) void Rebuild(ModernGeometryValue& result) {
        // TEST REBUILD GEOMETRY
        uint32_t width,height,boundWidth,boundHeight,clampMask=0;
            uint8_t cms = tileState.cms;
            uint8_t cmt = tileState.cmt;

            uint32_t tex_size_bytes = loadedState.orig_size_bytes;
            uint32_t line_size = tileState.line_size_bytes;

            if (line_size == 0) {
                line_size = 1;
            }

            height = tex_size_bytes / line_size;
            switch (tileState.siz) {
                case G_IM_SIZ_4b:
                    line_size <<= 1;
                    break;
                case G_IM_SIZ_8b:
                    break;
                case G_IM_SIZ_16b:
                    line_size /= G_IM_SIZ_16b_LINE_BYTES;
                    break;
                case G_IM_SIZ_32b:
                    line_size /= G_IM_SIZ_32b_LINE_BYTES; // this is 2!
                    height /= 2;
                    break;
            }
            width = line_size;

            boundWidth = (tileState.lrs - tileState.uls + 4) / 4;
            boundHeight = (tileState.lrt - tileState.ult + 4) / 4;

            uint32_t tex_width1 = width << (cms & G_TX_MIRROR);
            uint32_t tex_height1 = height << (cmt & G_TX_MIRROR);

            if ((cms & G_TX_CLAMP) && ((cms & G_TX_MIRROR) || tex_width1 != boundWidth)) {
                clampMask |= 1;
                cms &= ~G_TX_CLAMP;
            }
            if ((cmt & G_TX_CLAMP) && ((cmt & G_TX_MIRROR) || tex_height1 != boundHeight)) {
                clampMask |= 2;
                cmt &= ~G_TX_CLAMP;
            }


        result.width=width;result.height=height;
        result.boundWidth=boundWidth;result.boundHeight=boundHeight;
        result.clampMask=clampMask;result.cms=cms;result.cmt=cmt;
    }
};
template<class Tile,class Loaded>
const ModernGeometryValue& ModernGeometry(
    Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue>& cache,
    const Tile& tileState,const Loaded& loadedState) {
    ModernGeometryKey key={tileState.line_size_bytes,loadedState.orig_size_bytes,
        _controlfp(0,0)&_MCW_RC,
        tileState.uls,tileState.ult,tileState.lrs,tileState.lrt,
        tileState.siz,tileState.cms,tileState.cmt};
    ModernGeometryBuilder<Tile,Loaded> builder={tileState,loadedState};
    return cache.Load(key,builder);
}
static __declspec(thread) Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue> sModernGeometry0;
static __declspec(thread) Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue> sModernGeometry1;
// MODERN MATERIAL CACHE END


namespace LaneSemantic {
struct MaterialKey {
    uint64_t combine;
    unsigned otherH,otherL,shaderId,flags;
    bool operator==(const MaterialKey& r)const{return combine==r.combine && otherH==r.otherH && otherL==r.otherL && shaderId==r.shaderId && flags==r.flags;}
};
struct PackKey { unsigned data[30]; };
struct PackedLayout {
    unsigned stride,textureOffset[2],fogOffset,shadeRgb[7],shadeAlpha[7],rgbCount,alphaCount;
    bool halfTexel;float row[32];CampaignPreparedPack::CoordinatePlan uv[2][2];
};
struct Plan {
    TextureCacheNode* nodes[4];unsigned nodeEpoch[4];
    bool packValid;PackKey packKey;PackedLayout pack;
    MaterialKey key;ColorCombiner* comb;uint64_t ccId;
    bool alpha,fog,grayscale,valid;
    ModernGeometryKey geometryKeys[2];ModernGeometryValue geometry[2];unsigned geometryMask;
    Plan():packValid(false),comb(NULL),valid(false),geometryMask(0){memset(nodes,0,sizeof(nodes));memset(nodeEpoch,0,sizeof(nodeEpoch));}
};
static std::vector<Plan> plans;
static unsigned planCount,planStorage;
void BeginUpdate(){planCount=0;if(!planStorage && plans.capacity()<2048)plans.reserve(2048);}
// Existing elements are reused; only certificate validity is reset. No saved
// values are readable until their corresponding certificate has been populated.
static __declspec(noinline) Plan* AllocatePlan(UpdateStream::Instruction& op){
    if(planCount>=8192)return NULL;
    const unsigned index=planCount;
    if(index==planStorage){plans.push_back(Plan());++planStorage;}
    Plan& plan=plans[index];plan.valid=false;plan.packValid=false;plan.geometryMask=0;
    memset(plan.nodes,0,sizeof(plan.nodes));memset(plan.nodeEpoch,0,sizeof(plan.nodeEpoch));
    op.materialPlan=index;++planCount;return &plan;
}
static Plan* Current(){
    UpdateStream::Packet& p=UpdateStream::packet;
    if(!LaneWork::mode || !p.active || p.current>=p.instructions.size())return NULL;
    UpdateStream::Instruction& op=p.instructions[p.current];
    const unsigned code=op.word0>>24;
    if(op.ucode!=4)return NULL;
    if(op.materialPlan==~0U)return AllocatePlan(op);
    return &plans[op.materialPlan];
}
static MaterialKey Key(const RDP& r){
    MaterialKey k;k.combine=r.combine_mode;k.otherH=r.other_mode_h;k.otherL=r.other_mode_l;k.shaderId=r.current_shader.id;
    k.flags=unsigned(r.grayscale)|unsigned(r.current_shader.enabled)<<1 |
        unsigned(r.loaded_texture[0].masked)<<2 | unsigned(r.loaded_texture[1].masked)<<3 |
        unsigned(r.loaded_texture[0].blended)<<4 | unsigned(r.loaded_texture[1].blended)<<5;
    return k;
}
template<class Tile,class Loaded>
static const ModernGeometryValue& Geometry(Plan* plan,unsigned index,
    Shipyard::Fast3D::MaterialValueCache<ModernGeometryKey,ModernGeometryValue>& cache,const Tile& tile,const Loaded& loaded){
    ModernGeometryKey key={tile.line_size_bytes,loaded.orig_size_bytes,_controlfp(0,0)&_MCW_RC,
        tile.uls,tile.ult,tile.lrs,tile.lrt,tile.siz,tile.cms,tile.cmt};
    LaneWork::Add(LaneWork::DependencyCheck);
    if(plan && (plan->geometryMask&(1U<<index)) && plan->geometryKeys[index]==key){LaneWork::Add(LaneWork::GeometryReuse);return plan->geometry[index];}
    LaneWork::Add(LaneWork::GeometryPrepare);
    const ModernGeometryValue& value=ModernGeometry(cache,tile,loaded);
    if(!plan)return value;
    plan->geometryKeys[index]=key;plan->geometry[index]=value;plan->geometryMask|=1U<<index;
    return plan->geometry[index];
}
}

static __declspec(thread) Shipyard::Fast3D::ProjectionValueCache sModernCullProjection[MAX_VERTICES + 4];
static __declspec(thread) bool sModernCullRoundingBatch = true;

static __declspec(thread) ModernFrameProfile::Tri2Sample* sModernTri2Sample = NULL;

void Interpreter::GfxSpTri1(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {
    LaneWork::Add(LaneWork::Cull);
    struct LoadedVertex* v1 = &mRsp->loaded_vertices[vtx1_idx];
    struct LoadedVertex* v2 = &mRsp->loaded_vertices[vtx2_idx];
    struct LoadedVertex* v3 = &mRsp->loaded_vertices[vtx3_idx];
    struct LoadedVertex* v_arr[3] = { v1, v2, v3 };

    // if (rand()%2) return;

    if (v1->clip_rej & v2->clip_rej & v3->clip_rej) {
        // The whole triangle lies outside the visible area
        return;
    }

    const uint32_t cull_both = get_attr(CULL_BOTH);
    const uint32_t cull_front = get_attr(CULL_FRONT);
    const uint32_t cull_back = get_attr(CULL_BACK);

    if ((mRsp->geometry_mode & cull_both) != 0) {
        // MODERN CULL CACHE BEGIN
        Shipyard::Fast3D::ProjectionValueCache& p1 = sModernCullProjection[vtx1_idx];
        Shipyard::Fast3D::ProjectionValueCache& p2 = sModernCullProjection[vtx2_idx];
        Shipyard::Fast3D::ProjectionValueCache& p3 = sModernCullProjection[vtx3_idx];
        if (sModernCullRoundingBatch) {
            // No callbacks or rounding-mode writes occur among these divisions.
            const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();
            p1.Load(v1->x, v1->y, v1->w, projectionRounding);
            p2.Load(v2->x, v2->y, v2->w, projectionRounding);
            p3.Load(v3->x, v3->y, v3->w, projectionRounding);
        } else {
            p1.Load(v1->x, v1->y, v1->w);
            p2.Load(v2->x, v2->y, v2->w);
            p3.Load(v3->x, v3->y, v3->w);
        }
        float dx1 = p1.x - p2.x;
        float dy1 = p1.y - p2.y;
        float dx2 = p3.x - p2.x;
        float dy2 = p3.y - p2.y;
        float cross = dx1 * dy2 - dy1 * dx2;
        // MODERN CULL CACHE END
        if ((v1->w < 0) ^ (v2->w < 0) ^ (v3->w < 0)) {
            // If one vertex lies behind the eye, negating cross will give the correct result.
            // If all vertices lie behind the eye, the triangle will be rejected anyway.
            cross = -cross;
        }

        // If inverted culling is requested, negate the cross
        if (ucode_handler_index == UcodeHandlers::ucode_f3dex2 &&
            (mRsp->extra_geometry_mode & G_EX_INVERT_CULLING) == 1) {
            cross = -cross;
        }

        auto cull_type = mRsp->geometry_mode & cull_both;

        if (cull_type == cull_front) {
            if (cross <= 0) {
                return;
            }
        } else if (cull_type == cull_back) {
            if (cross >= 0) {
                return;
            }
        } else if (cull_type == cull_both) {
            // Why is this even an option?
            return;
        }
    }

    // MODERN TRIANGLE MATERIALIZATION GUARD BEGIN
    // Most surviving triangles reuse already materialized vertex slots. Keep
    // the authoritative materializer for pending slots and for every other
    // consumer; avoid its call/early-return cost for clean triangle inputs.
    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
        *sModernTri2Sample, ModernFrameProfile::Tri2Materialize);
    XboxMaterializeVertex(vtx1_idx);
    if (vtx2_idx < MAX_VERTICES && mXboxDeferredVertices[vtx2_idx].context)
        XboxMaterializeVertex(vtx2_idx);
    if (vtx3_idx < MAX_VERTICES && mXboxDeferredVertices[vtx3_idx].context)
        XboxMaterializeVertex(vtx3_idx);
    // MODERN TRIANGLE MATERIALIZATION GUARD END
    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
        *sModernTri2Sample, ModernFrameProfile::Tri2Pipeline);
    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect);
    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
        *sModernTri2Sample, ModernFrameProfile::Tri2Cull);
}

__declspec(noinline) void Interpreter::XboxPrepareTrianglePipeline() {
    CampaignTriRun::cache.Reset();
    // MODERN PIPELINE PHASE PROFILE BEGIN
    ModernFrameProfile::PipelinePreparationSample xboxPrepSample;
    ModernFrameProfile::BeginPipelinePreparation(xboxPrepSample);
    mXboxPipelineKey.valid=false;
// SHIPYARD ORIGINAL RECONCILIATION BEGIN
    bool depth_test = (mRsp->geometry_mode & G_ZBUFFER) == G_ZBUFFER;
    bool depth_mask = (mRdp->other_mode_l & Z_UPD) == Z_UPD;
    uint8_t depth_test_and_mask = (depth_test ? 1 : 0) | (depth_mask ? 2 : 0);
    if (depth_test_and_mask != mRenderingState.depth_test_and_mask) {
        Flush();
        (mXboxPipelineKey.valid=false, mRapi->SetDepthTestAndMask(depth_test, depth_mask));
        mRenderingState.depth_test_and_mask = depth_test_and_mask;
    }

    bool zmode_decal = (mRdp->other_mode_l & ZMODE_DEC) == ZMODE_DEC;
    if (zmode_decal != mRenderingState.decal_mode) {
        Flush();
        (mXboxPipelineKey.valid=false, mRapi->SetZmodeDecal(zmode_decal));
        mRenderingState.decal_mode = zmode_decal;
    }

    if (mRdp->viewport_or_scissor_changed) {
        if (memcmp(&mRdp->viewport, &mRenderingState.viewport, sizeof(mRdp->viewport)) != 0) {
            Flush();
            (mXboxPipelineKey.valid=false, mRapi->SetViewport(mRdp->viewport.x, mRdp->viewport.y, mRdp->viewport.width, mRdp->viewport.height));
            mRenderingState.viewport = mRdp->viewport;
        }
        if (memcmp(&mRdp->scissor, &mRenderingState.scissor, sizeof(mRdp->scissor)) != 0) {
            Flush();
            (mXboxPipelineKey.valid=false, mRapi->SetScissor(mRdp->scissor.x, mRdp->scissor.y, mRdp->scissor.width, mRdp->scissor.height));
            mRenderingState.scissor = mRdp->scissor;
        }
        mRdp->viewport_or_scissor_changed = false;
    }

    LaneSemantic::Plan* semanticPlan=LaneSemantic::Current();
    const LaneSemantic::MaterialKey semanticKey=LaneSemantic::Key(*mRdp);
    LaneWork::Add(LaneWork::DependencyCheck);
    const bool semanticHit=semanticPlan && semanticPlan->valid && semanticPlan->key==semanticKey;
    uint64_t cc_id;bool use_alpha,use_fog,use_grayscale;ColorCombiner* comb;
    if(semanticHit){
        LaneWork::Add(LaneWork::MaterialReuse);
        cc_id=semanticPlan->ccId;use_alpha=semanticPlan->alpha;use_fog=semanticPlan->fog;use_grayscale=semanticPlan->grayscale;comb=semanticPlan->comb;
    }else{
        LaneWork::Add(LaneWork::MaterialClassify);
    cc_id = mRdp->combine_mode;
    uint64_t cc_options = 0;
    use_alpha = ((mRdp->other_mode_l & (3 << 20)) == (G_BL_CLR_MEM << 20) &&
                      (mRdp->other_mode_l & (3 << 16)) == (G_BL_1MA << 16)) ||
                     ((mRdp->other_mode_l & (3 << 22)) == (G_BL_CLR_MEM << 22) &&
                      (mRdp->other_mode_l & (3 << 18)) == (G_BL_1MA << 18));
    use_fog = (mRdp->other_mode_l >> 30) == G_BL_CLR_FOG;
    bool texture_edge = (mRdp->other_mode_l & CVG_X_ALPHA) == CVG_X_ALPHA;
    bool use_noise = (mRdp->other_mode_l & (3U << G_MDSFT_ALPHACOMPARE)) == G_AC_DITHER;
    bool use_2cyc = (mRdp->other_mode_h & (3U << G_MDSFT_CYCLETYPE)) == G_CYC_2CYCLE;
    bool alpha_threshold = (mRdp->other_mode_l & (3U << G_MDSFT_ALPHACOMPARE)) == G_AC_THRESHOLD;
    bool invisible =
        (mRdp->other_mode_l & (3 << 24)) == (G_BL_0 << 24) && (mRdp->other_mode_l & (3 << 20)) == (G_BL_CLR_MEM << 20);
    use_grayscale = mRdp->grayscale;
    auto shader = mRdp->current_shader;

    if (texture_edge) {
        if (use_alpha) {
            alpha_threshold = true;
            texture_edge = false;
        }
        use_alpha = true;
    }

    if (use_alpha) {
        cc_options |= SHADER_OPT(ALPHA);
    }
    if (use_fog) {
        cc_options |= SHADER_OPT(FOG);
    }
    if (texture_edge) {
        cc_options |= SHADER_OPT(TEXTURE_EDGE);
    }
    if (use_noise) {
        cc_options |= SHADER_OPT(NOISE);
    }
    if (use_2cyc) {
        cc_options |= SHADER_OPT(_2CYC);
    }
    if (alpha_threshold) {
        cc_options |= SHADER_OPT(ALPHA_THRESHOLD);
    }
    if (invisible) {
        cc_options |= SHADER_OPT(INVISIBLE);
    }
    if (use_grayscale) {
        cc_options |= SHADER_OPT(GRAYSCALE);
    }
    if (mRdp->loaded_texture[0].masked) {
        cc_options |= SHADER_OPT(TEXEL0_MASK);
    }
    if (mRdp->loaded_texture[1].masked) {
        cc_options |= SHADER_OPT(TEXEL1_MASK);
    }
    if (mRdp->loaded_texture[0].blended) {
        cc_options |= SHADER_OPT(TEXEL0_BLEND);
    }
    if (mRdp->loaded_texture[1].blended) {
        cc_options |= SHADER_OPT(TEXEL1_BLEND);
    }
    if (shader.enabled) {
        cc_options |= SHADER_OPT(USE_SHADER);
        cc_options |= (shader.id << 17);
    }

    ColorCombinerKey key;
    key.combine_mode = mRdp->combine_mode;
    key.options = cc_options;

    // If we are not using alpha, clear the alpha components of the combiner as they have no effect
    if (!use_alpha && !shader.enabled) {
        key.combine_mode &= ~((0xfff << 16) | ((uint64_t)0xfff << 44));
    }

    comb = LookupOrCreateColorCombiner(key);

        if(semanticPlan){semanticPlan->packValid=false;semanticPlan->key=semanticKey;semanticPlan->ccId=cc_id;semanticPlan->alpha=use_alpha;semanticPlan->fog=use_fog;
            semanticPlan->grayscale=use_grayscale;semanticPlan->comb=comb;semanticPlan->valid=true;semanticPlan->geometryMask=0;}
    }
    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, ModernFrameProfile::PipelineGeometrySampler);

    uint32_t tm = 0;
    uint32_t tex_width[2], tex_height[2], tex_width2[2], tex_height2[2];

    for (int i = 0; i < 2; i++) {
        uint32_t tile = mRdp->first_tile_index + i;
        if (comb->usedTextures[i]) {
            if (mRdp->textures_changed[i]) {
                ModernFrameProfile::EnterPipelineTextureImport(xboxPrepSample);
                Flush();
                ImportTexture(i, tile, false);
                if (mRdp->loaded_texture[i].masked) {
                    ImportTextureMask(SHADER_FIRST_MASK_TEXTURE + i, tile);
                }
                if (mRdp->loaded_texture[i].blended) {
                    ImportTexture(SHADER_FIRST_REPLACEMENT_TEXTURE + i, tile, true);
                }
                mRdp->textures_changed[i] = false;
                ModernFrameProfile::ExitPipelineTextureImport(xboxPrepSample);
            }

            uint8_t cms = 0, cmt = 0;
            const ModernGeometryValue& geometry = LaneSemantic::Geometry(semanticPlan,i,
                i ? sModernGeometry1 : sModernGeometry0,mRdp->texture_tile[tile],
                mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index]);
            cms=geometry.cms;cmt=geometry.cmt;
            tex_width[i]=geometry.width;tex_height[i]=geometry.height;
            tex_width2[i]=geometry.boundWidth;tex_height2[i]=geometry.boundHeight;
            tm |= geometry.clampMask << (2 * i);

            if (mRenderingState.mTextures[i] == nullptr) {
                continue;
            }

            bool linear_filter = (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            const Shipyard::Fast3D::TextureSamplerState desiredSampler(linear_filter,cms,cmt);
            if (linear_filter != mRenderingState.mTextures[i]->second.linear_filter ||
                cms != mRenderingState.mTextures[i]->second.cms || cmt != mRenderingState.mTextures[i]->second.cmt ||
                mXboxTextureBindings.NeedsSampler(i,desiredSampler) ||
                (mRdp->loaded_texture[i].blended &&
                 mXboxTextureBindings.NeedsSampler(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler))) {
                Flush();

                // Set the same sampler params on the blended texture. Needed for opengl.
                if (mRdp->loaded_texture[i].blended) {
                    (mXboxPipelineKey.valid=false, mRapi->SetSamplerParameters(SHADER_FIRST_REPLACEMENT_TEXTURE + i, linear_filter, cms, cmt));
                    mXboxTextureBindings.SamplerChanged(SHADER_FIRST_REPLACEMENT_TEXTURE+i,desiredSampler);
                }

                (mXboxPipelineKey.valid=false, mRapi->SetSamplerParameters(i, linear_filter, cms, cmt));
                mXboxTextureBindings.SamplerChanged(i,desiredSampler);
                mRenderingState.mTextures[i]->second.linear_filter = linear_filter;
                mRenderingState.mTextures[i]->second.cms = cms;
                mRenderingState.mTextures[i]->second.cmt = cmt;
            }
        }
    }

    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, ModernFrameProfile::PipelineShaderTransitions);
    struct ShaderProgram* prg = comb->prg[tm];
    if (prg == NULL) {
        comb->prg[tm] = prg =
            LookupOrCreateShaderProgram(comb->shader_id0, comb->shader_id1 | tm * SHADER_OPT(TEXEL0_CLAMP_S));
    }
    if (prg != mRenderingState.mShaderProgram) {
        Flush();
        (mXboxPipelineKey.valid=false, mRapi->UnloadShader(mRenderingState.mShaderProgram));
        (mXboxPipelineKey.valid=false, mRapi->LoadShader(prg));
        mRenderingState.mShaderProgram = prg;
    }
    if (use_alpha != mRenderingState.alpha_blend) {
        Flush();
        (mXboxPipelineKey.valid=false, mRapi->SetUseAlpha(use_alpha));
        mRenderingState.alpha_blend = use_alpha;
    }
    uint8_t numInputs;
    bool usedTextures[2];

    Shipyard::Fast3D::ShaderMetadata xboxMetadata;
    if (!comb->xboxShaderMetadata.Lookup(tm, mRapi, prg, xboxMetadata)) {
        mRapi->ShaderGetInfo(prg, &xboxMetadata.numInputs, xboxMetadata.usedTextures);
        comb->xboxShaderMetadata.Store(tm, mRapi, prg, xboxMetadata);
    }
    numInputs = xboxMetadata.numInputs;
    usedTextures[0] = xboxMetadata.usedTextures[0];
    usedTextures[1] = xboxMetadata.usedTextures[1];

    struct GfxClipParameters clip_parameters = mXboxClipParameters;

// SHIPYARD ORIGINAL RECONCILIATION END
    ModernFrameProfile::AdvancePipelinePreparation(xboxPrepSample, ModernFrameProfile::PipelineFinalCapture);
    XboxTrianglePipelineResult& p=mXboxPipelineResult;
    p.comb=comb;p.ccId=cc_id;p.tm=tm;
    p.alpha=use_alpha;p.fog=use_fog;p.grayscale=use_grayscale;
    p.blendColor=false;p.redirect=false;p.numInputs=numInputs;p.clip=clip_parameters;
    for(unsigned i=0;i<2;++i) {
        p.usedTextures[i]=usedTextures[i];
        p.effectiveTile[i]=mRdp->first_tile_index+i;
        if(comb->usedTextures[i]) {
            p.width[i]=tex_width[i];p.height[i]=tex_height[i];
            p.boundWidth[i]=tex_width2[i];p.boundHeight[i]=tex_height2[i];
        } else {
            p.width[i]=p.height[i]=p.boundWidth[i]=p.boundHeight[i]=0;
        }
        p.widthFloat[i]=p.heightFloat[i]=p.boundWidthFloat[i]=p.boundHeightFloat[i]=0;
    }
    mXboxPipelineKey.Capture(*this,p);
    CampaignTriRun::cache.lodMaterial=false;
    for(unsigned j=0;j<p.numInputs;++j)
        for(unsigned k=0;k<1U+unsigned(p.alpha);++k)
            if(p.comb->shader_input_mapping[k][j]==G_CCMUX_LOD_FRACTION)
                CampaignTriRun::cache.lodMaterial=true;
    ModernFrameProfile::EndPipelinePreparation(xboxPrepSample);
    // MODERN PIPELINE PHASE PROFILE END
}


// A TRI2-only run certifies all material/texture/layout state. Non-TRI2
// commands, Run, pipeline preparation and Flush invalidate the run epoch.
// The first emitted triangle prepares the template using the original packer.
__declspec(noinline) bool Interpreter::XboxEmitPreparedTriangle(uint8_t a,uint8_t b,uint8_t c,bool rect) {
    CampaignTriRun::Rows& cache=CampaignTriRun::cache;
    CampaignPreparedPack::Layout& l=CampaignPreparedPack::layout;
    CampaignOwnerGeneration::Certificate& cert=CampaignOwnerGeneration::certificate;
    if(!cache.mode || rect || !mXboxTrianglePairActive || !mXboxPipelineKey.valid ||
       ucode_handler_index!=UcodeHandlers::ucode_f3dex2 || l.owner!=this ||
       l.epoch!=cache.epoch || !l.stride || cert.owner!=this || cert.captured!=cert.mutation)
        return false;
    unsigned w;memcpy(&w,&mRsp->loaded_vertices[a].w,4);
    if(cache.lodMaterial && (mRdp->other_mode_l&G_TL_LOD) && cache.lodW!=w)return false;
    if(CampaignOwnerGeneration::generationMode==2) {
        ++cert.oracleChecks;
        if(!mXboxPipelineKey.Matches(*this)){++cert.oracleFailures;return false;}
    }
    if(sModernTri2Sample)ModernFrameProfile::AdvanceTri2(*sModernTri2Sample,ModernFrameProfile::Tri2Pack);
    const XboxTrianglePipelineResult& p=mXboxPipelineResult;
    const unsigned indices[3]={a,b,c};
    float* output=mBufVbo+mBufVboLen;
    unsigned hits=0;
    for(unsigned i=0;i<3;++i) {
        float* dst=output+i*l.stride;
        if(cache.Has(indices[i])) {
            memcpy(dst,mBufVbo+cache.starts[indices[i]],l.stride*sizeof(float));
            ++hits;
            continue;
        }
        CAMPAIGN_DIAGNOSTIC_COUNT(++l.misses;);LaneWork::Add(LaneWork::DynamicPack);
        // Constants already have their exact original bit representation.
        memcpy(dst,l.row,l.stride*sizeof(float));
        const LoadedVertex& v=mRsp->loaded_vertices[indices[i]];
        dst[0]=v.x;dst[1]=p.clip.invertY ? -v.y:v.y;
        dst[2]=p.clip.z_is_from_0_to_1 ? (v.z+v.w)/2.0f:v.z;dst[3]=v.w;
        for(unsigned t=0;t<2;++t)if(l.textureOffset[t]) {
            const unsigned offset=l.textureOffset[t];
            dst[offset]=l.uv[t][0].Apply(v.u,l.halfTexel);
            dst[offset+1]=l.uv[t][1].Apply(v.v,l.halfTexel);
        }
        if(l.fogOffset)dst[l.fogOffset+3]=Shipyard::Fast3D::UnitColor(v.color.a);
        if(l.rgbCount) {
            const float r=Shipyard::Fast3D::UnitColor(v.color.r);
            const float g=Shipyard::Fast3D::UnitColor(v.color.g);
            const float b=Shipyard::Fast3D::UnitColor(v.color.b);
            for(unsigned j=0;j<l.rgbCount;++j){float* d=dst+l.shadeRgb[j];d[0]=r;d[1]=g;d[2]=b;}
        }
        if(l.alphaCount) {
            const float alpha=p.fog ? 1.0f:Shipyard::Fast3D::UnitColor(v.color.a);
            for(unsigned j=0;j<l.alphaCount;++j)dst[l.shadeAlpha[j]]=alpha;
        }
    }
    CAMPAIGN_DIAGNOSTIC_COUNT(++l.triangles;);
    if(cache.mode==2) {
        memcpy(l.expected,output,3*l.stride*sizeof(float));l.pending=true;
        return false; // Original packer overwrites the same rows; compare before Flush.
    }
    CAMPAIGN_DIAGNOSTIC_COUNT(++cert.attempts;++cert.hits;);
    if(!(mXboxTrianglePairActive && mXboxTrianglePairPrepared && mXboxPipelineKey.valid))CAMPAIGN_DIAGNOSTIC_COUNT(++cert.avoidedComparisons;);
    if(ModernFrameProfile::CaptureTrianglePipeline())ModernFrameProfile::ObserveTrianglePipeline(true);
    CAMPAIGN_DIAGNOSTIC_COUNT(cache.rows+=3;cache.hits+=hits;++cache.triangles;if(hits==3)++cache.full;);
    for(unsigned i=0;i<3;++i){cache.starts[indices[i]]=mBufVboLen+i*l.stride;cache.stamps[indices[i]]=cache.epoch;}
    mBufVboLen+=3*l.stride;
    mXboxCanDiscardGameColor=false;mXboxTrianglePairPrepared=true;
    // The run cache supersedes pair-local storage; never expose stale pair rows.
    mXboxPairPacked.Reset();
    if(++mBufVboNumTris==MAX_TRI_BUFFER) {
        if(sModernTri2Sample)ModernFrameProfile::AdvanceTri2(*sModernTri2Sample,ModernFrameProfile::Tri2Flush);
        Flush();mXboxTrianglePairPrepared=false;
        if(sModernTri2Sample)ModernFrameProfile::AdvanceTri2(*sModernTri2Sample,ModernFrameProfile::Tri2Pack);
    }
    return true;
}

namespace LaneSemantic {
static Plan* Existing(){
    UpdateStream::Packet& p=UpdateStream::packet;
    if(!LaneWork::mode || !p.active || (!p.recording&&!p.replaying) || p.current>=p.instructions.size())return NULL;
    const unsigned index=p.instructions[p.current].materialPlan;return index<planCount?&plans[index]:NULL;
}
static PackKey MakePackKey(const Interpreter* gfx){
    PackKey k={};const RDP& r=*gfx->mRdp;const XboxTrianglePipelineResult& p=gfx->mXboxPipelineResult;
    memcpy(&k.data[0],&r.prim_color,4);memcpy(&k.data[1],&r.env_color,4);
    memcpy(&k.data[2],&r.fog_color,4);memcpy(&k.data[3],&r.grayscale_color,4);
    k.data[4]=r.prim_lod_fraction;k.data[5]=p.numInputs;k.data[6]=p.tm;
    k.data[7]=unsigned(p.alpha)|unsigned(p.fog)<<1|unsigned(p.grayscale)<<2|unsigned(p.clip.invertY)<<3|unsigned(p.clip.z_is_from_0_to_1)<<4;
    k.data[8]=r.other_mode_h;k.data[9]=unsigned(p.usedTextures[0])|unsigned(p.usedTextures[1])<<1;
    for(unsigned t=0;t<2;++t){const unsigned j=10+10*t;
        k.data[j+8]=unsigned(p.ccId);k.data[j+9]=unsigned(p.ccId>>32);
        if(!p.usedTextures[t])continue;
        const auto& tile=r.texture_tile[r.first_tile_index+t];
        k.data[j]=p.width[t];k.data[j+1]=p.height[t];k.data[j+2]=p.boundWidth[t];k.data[j+3]=p.boundHeight[t];
        k.data[j+4]=tile.shifts;k.data[j+5]=tile.shiftt;
        memcpy(&k.data[j+6],&tile.uls,4);memcpy(&k.data[j+7],&tile.ult,4);
    }
    return k;
}
static void SaveLayout(Interpreter* gfx){
    Plan* plan=Existing();if(!plan || plan->packValid || !gfx->mXboxTrianglePairActive ||
       (CampaignTriRun::cache.lodMaterial && (gfx->mRdp->other_mode_l&G_TL_LOD)))return;
    const CampaignPreparedPack::Layout& a=CampaignPreparedPack::layout;
    if(a.owner!=gfx || !a.stride || a.pending)return;
    PackedLayout& b=plan->pack;b.stride=a.stride;b.fogOffset=a.fogOffset;b.rgbCount=a.rgbCount;b.alphaCount=a.alphaCount;b.halfTexel=a.halfTexel;
    memcpy(b.textureOffset,a.textureOffset,sizeof(b.textureOffset));memcpy(b.shadeRgb,a.shadeRgb,sizeof(b.shadeRgb));memcpy(b.shadeAlpha,a.shadeAlpha,sizeof(b.shadeAlpha));
    memcpy(b.row,a.row,sizeof(b.row));memcpy(b.uv,a.uv,sizeof(b.uv));plan->packKey=MakePackKey(gfx);plan->packValid=true;
}
static bool RestoreLayout(Interpreter* gfx,bool rect){
    if(rect || !gfx->mXboxTrianglePairActive || CampaignTriRun::cache.mode!=1)return false;
    Plan* plan=Existing();if(!plan || !plan->packValid)return false;
    CampaignOwnerGeneration::Certificate& cert=CampaignOwnerGeneration::certificate;
    const bool hit=gfx->mXboxPipelineKey.valid && cert.owner==gfx && cert.captured==cert.mutation;
    if(!hit && !gfx->mXboxPipelineKey.Matches(*gfx))gfx->XboxPrepareTrianglePipeline();
    cert.owner=gfx;cert.captured=cert.mutation;
    if(!plan->packValid || (CampaignTriRun::cache.lodMaterial && (gfx->mRdp->other_mode_l&G_TL_LOD)))return false;
    const PackKey key=MakePackKey(gfx);LaneWork::Add(LaneWork::DependencyCheck);
    if(memcmp(&key,&plan->packKey,sizeof(key))){plan->packValid=false;return false;}
    const PackedLayout& a=plan->pack;CampaignPreparedPack::Layout& b=CampaignPreparedPack::layout;
    b.owner=gfx;b.epoch=CampaignTriRun::cache.epoch;b.stride=a.stride;b.fogOffset=a.fogOffset;b.rgbCount=a.rgbCount;b.alphaCount=a.alphaCount;b.halfTexel=a.halfTexel;b.pending=false;
    memcpy(b.textureOffset,a.textureOffset,sizeof(a.textureOffset));memcpy(b.shadeRgb,a.shadeRgb,sizeof(a.shadeRgb));memcpy(b.shadeAlpha,a.shadeAlpha,sizeof(a.shadeAlpha));
    memcpy(b.row,a.row,sizeof(a.row));memcpy(b.uv,a.uv,sizeof(a.uv));LaneWork::Add(LaneWork::LayoutReuse);return true;
}
}

namespace LaneTextures {
static TextureCacheNode* Find(int i,const TextureCacheKey& key){
    LaneSemantic::Plan* p=LaneSemantic::Existing();
    if(!p || unsigned(i)>=4 || p->nodeEpoch[i]!=epoch || !p->nodes[i])return NULL;
    TextureCacheNode* node=p->nodes[i];
    if(!(node->first==key))return NULL;
    LaneWork::Add(LaneWork::TextureNodeReuse);return node;
}
static void Save(int i,TextureCacheNode* node){
    LaneSemantic::Plan* p=LaneSemantic::Existing();if(!p || unsigned(i)>=4)return;
    p->nodes[i]=node;p->nodeEpoch[i]=epoch;
}
}
void Interpreter::XboxEmitTriangle(uint8_t a,uint8_t b,uint8_t c,bool rect) {
    if(XboxEmitPreparedTriangle(a,b,c,rect))return;
    if(LaneSemantic::RestoreLayout(this,rect) && XboxEmitPreparedTriangle(a,b,c,rect))return;
    XboxEmitTriangleOriginal(a,b,c,rect);LaneSemantic::SaveLayout(this);
}

__declspec(noinline) void Interpreter::XboxEmitTriangleOriginal(uint8_t vtx1_idx, uint8_t vtx2_idx, uint8_t vtx3_idx, bool is_rect) {
    mXboxCanDiscardGameColor = false;
    struct LoadedVertex* v1 = &mRsp->loaded_vertices[vtx1_idx];
    struct LoadedVertex* v2 = &mRsp->loaded_vertices[vtx2_idx];
    struct LoadedVertex* v3 = &mRsp->loaded_vertices[vtx3_idx];
    struct LoadedVertex* v_arr[3] = { v1, v2, v3 };

    const bool xboxPairPackSecond = mXboxTrianglePairActive && mXboxTrianglePairPrepared && mXboxPipelineKey.valid && mXboxPairPacked.valid;
    CampaignOwnerGeneration::Certificate& certificate=CampaignOwnerGeneration::certificate;
    const bool generationHit=CampaignOwnerGeneration::generationMode && mXboxPipelineKey.valid &&
        certificate.owner==this && certificate.captured==certificate.mutation;
    CAMPAIGN_DIAGNOSTIC_COUNT(++certificate.attempts;);
    bool xboxPipelineHit;
    if(generationHit) {
        CAMPAIGN_DIAGNOSTIC_COUNT(++certificate.hits;);
        if(!(mXboxTrianglePairActive && mXboxTrianglePairPrepared && mXboxPipelineKey.valid))
            CAMPAIGN_DIAGNOSTIC_COUNT(++certificate.avoidedComparisons;);
        if(CampaignOwnerGeneration::generationMode==2) {
            ++certificate.oracleChecks;
            xboxPipelineHit=mXboxPipelineKey.Matches(*this);
            if(!xboxPipelineHit)++certificate.oracleFailures;
        } else xboxPipelineHit=true;
    } else xboxPipelineHit=(mXboxTrianglePairActive && mXboxTrianglePairPrepared && mXboxPipelineKey.valid) || mXboxPipelineKey.Matches(*this);
    if (ModernFrameProfile::CaptureTrianglePipeline())
        ModernFrameProfile::ObserveTrianglePipeline(xboxPipelineHit);
    if(!xboxPipelineHit)XboxPrepareTrianglePipeline();
    certificate.owner=this;certificate.captured=certificate.mutation;

    mXboxTrianglePairPrepared = mXboxTrianglePairActive && mXboxPipelineKey.valid;
    // MODERN TRI2 PACKED REUSE BEGIN
    const bool xboxPairPackFirst = mXboxTrianglePairActive && !mXboxPairPacked.valid && mXboxPipelineKey.valid;
    uint32_t xboxPairFirstWBits;
    memcpy(&xboxPairFirstWBits, &v1->w, sizeof(xboxPairFirstWBits));
    const bool xboxPairPackReuse = xboxPairPackSecond && mXboxPairPacked.CanReuse(mBufVboLen, xboxPipelineHit,
        (mRdp->other_mode_l & G_TL_LOD) != 0, xboxPairFirstWBits);
    const uint8_t xboxPairIndices[3] = {vtx1_idx, vtx2_idx, vtx3_idx};
    size_t xboxPairStarts[3];
    // MODERN TRI2 PACKED REUSE END
    if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
        *sModernTri2Sample, ModernFrameProfile::Tri2Pack);

    const XboxTrianglePipelineResult& p=mXboxPipelineResult;
    ColorCombiner* comb=p.comb;
    const bool use_alpha=p.alpha;
    const uint32_t tm=p.tm;
    const uint32_t* tex_width=p.width;const uint32_t* tex_height=p.height;
    const uint32_t* tex_width2=p.boundWidth;const uint32_t* tex_height2=p.boundHeight;
    const bool use_fog=p.fog,use_grayscale=p.grayscale;
    const uint8_t numInputs=p.numInputs;
    const bool* usedTextures=p.usedTextures;
    const GfxClipParameters& clip_parameters=p.clip;

    float* shipyardVertexOutput = mBufVbo + mBufVboLen;
    CampaignTriRun::Rows& runCache=CampaignTriRun::cache;
    const size_t runStart=mBufVboLen;
    if(runCache.lodMaterial && (mRdp->other_mode_l & G_TL_LOD)) {
        if(runCache.lodW!=xboxPairFirstWBits)runCache.Reset();
        runCache.lodW=xboxPairFirstWBits;
    }
    const bool runEligible=mXboxTrianglePairActive && mXboxPipelineKey.valid &&
        ucode_handler_index==UcodeHandlers::ucode_f3dex2;
    const bool runHits[3]={runEligible && runCache.Has(vtx1_idx),
        runEligible && runCache.Has(vtx2_idx),runEligible && runCache.Has(vtx3_idx)};
    const bool runCopy=runCache.mode==1 && (runHits[0]||runHits[1]||runHits[2]);
    if(runEligible) {
        CAMPAIGN_DIAGNOSTIC_COUNT(runCache.rows+=3;runCache.hits+=unsigned(runHits[0])+unsigned(runHits[1])+unsigned(runHits[2]););
        CAMPAIGN_DIAGNOSTIC_COUNT(++runCache.triangles;if(runHits[0]&&runHits[1]&&runHits[2])++runCache.full;);
        for(unsigned i=0;i<3;++i) {
            bool pairHit=false;
            if(xboxPairPackReuse)
                for(unsigned j=0;j<3;++j)if(mXboxPairPacked.indices[j]==xboxPairIndices[i])pairHit=true;
            CAMPAIGN_DIAGNOSTIC_COUNT(if(runHits[i]&&!pairHit)++runCache.additional;);
        }
    }

    float shipyardClampS[2];
    float shipyardClampT[2];
    for (int t = 0; t < 2; ++t) {
        if (!usedTextures[t]) continue;
        if (tm & (1 << 2 * t)) shipyardClampS[t] = (tex_width2[t] - 0.5f) / tex_width[t];
        if (tm & (1 << 2 * t + 1)) shipyardClampT[t] = (tex_height2[t] - 0.5f) / tex_height[t];
    }
    float shipyardFog[3];
    if (use_fog) {
        shipyardFog[0] = Shipyard::Fast3D::UnitColor(mRdp->fog_color.r);
        shipyardFog[1] = Shipyard::Fast3D::UnitColor(mRdp->fog_color.g);
        shipyardFog[2] = Shipyard::Fast3D::UnitColor(mRdp->fog_color.b);
    }
    float shipyardGrayscale[4];
    if (use_grayscale) {
        shipyardGrayscale[0] = Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.r);
        shipyardGrayscale[1] = Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.g);
        shipyardGrayscale[2] = Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.b);
        shipyardGrayscale[3] = Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.a);
    }
    const float* shipyardMaterialInputs[2][sizeof(comb->shader_input_mapping[0]) / sizeof(comb->shader_input_mapping[0][0])];
    // MODERN COLUMN PACK BEGIN
    // Layout and material branches are shared by the three output rows.
    // The paired TRI2 copy path below retains its original byte-copy logic.
    size_t xboxColumnStride = 0;
    size_t xboxTextureOffset[2] = {0, 0};
    size_t xboxFogOffset = 0, xboxGrayOffset = 0, xboxInputOffset = 0;
    {
        xboxColumnStride = 4;
        for (int t = 0; t < 2; ++t) {
            if (!usedTextures[t]) continue;
            xboxTextureOffset[t] = xboxColumnStride;
            xboxColumnStride += 2 + unsigned((tm & (1 << (2 * t))) != 0) +
                unsigned((tm & (1 << (2 * t + 1))) != 0);
        }
        xboxFogOffset = use_fog ? xboxColumnStride : 0;
        if (use_fog) xboxColumnStride += 4;
        xboxGrayOffset = use_grayscale ? xboxColumnStride : 0;
        if (use_grayscale) xboxColumnStride += 4;
        xboxInputOffset = xboxColumnStride;
        xboxColumnStride += size_t(numInputs) * (use_alpha ? 4 : 3);
    }
    if (!runCopy && !xboxPairPackReuse && xboxColumnStride <= 32) {
        LaneWork::Add(LaneWork::StaticPack,3);LaneWork::Add(LaneWork::DynamicPack,3);
        float* const xboxRows[3] = {
            shipyardVertexOutput,
            shipyardVertexOutput + xboxColumnStride,
            shipyardVertexOutput + 2 * xboxColumnStride
        };
        if (xboxPairPackFirst) {
            for (int i = 0; i < 3; ++i)
                xboxPairStarts[i] = size_t(xboxRows[i] - mBufVbo);
        }
        for (int i = 0; i < 3; ++i) {
            const LoadedVertex& v = *v_arr[i];
            float z = v.z;
            if (clip_parameters.z_is_from_0_to_1) z = (z + v.w) / 2.0f;
            xboxRows[i][0] = v.x;
            xboxRows[i][1] = clip_parameters.invertY ? -v.y : v.y;
            xboxRows[i][2] = z;
            xboxRows[i][3] = v.w;
        }
        const bool xboxHalfTexel = !is_rect &&
            (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
        for (int t = 0; t < 2; ++t) {
            if (!usedTextures[t]) continue;
            size_t offset = xboxTextureOffset[t];
            const auto& tile = mRdp->texture_tile[mRdp->first_tile_index + t];
            for (int i = 0; i < 3; ++i) {
                xboxRows[i][offset] = Shipyard::Fast3D::Coordinate(
                    v_arr[i]->u, tile.shifts, tile.uls, xboxHalfTexel, tex_width[t]);
                xboxRows[i][offset + 1] = Shipyard::Fast3D::Coordinate(
                    v_arr[i]->v, tile.shiftt, tile.ult, xboxHalfTexel, tex_height[t]);
            }
            offset += 2;
            if (tm & (1 << 2 * t)) {
                for (int i = 0; i < 3; ++i) xboxRows[i][offset] = shipyardClampS[t];
                ++offset;
            }
            if (tm & (1 << (2 * t + 1)))
                for (int i = 0; i < 3; ++i) xboxRows[i][offset] = shipyardClampT[t];
        }
        if (use_fog) {
            for (int i = 0; i < 3; ++i) {
                xboxRows[i][xboxFogOffset] = shipyardFog[0];
                xboxRows[i][xboxFogOffset + 1] = shipyardFog[1];
                xboxRows[i][xboxFogOffset + 2] = shipyardFog[2];
                xboxRows[i][xboxFogOffset + 3] =
                    Shipyard::Fast3D::UnitColor(v_arr[i]->color.a);
            }
        }
        if (use_grayscale) {
            for (int i = 0; i < 3; ++i)
                for (int c = 0; c < 4; ++c)
                    xboxRows[i][xboxGrayOffset + c] = shipyardGrayscale[c];
        }
        for (int j = 0; j < numInputs; ++j) {
            for (int k = 0; k < 1 + (use_alpha ? 1 : 0); ++k) {
                const size_t offset = xboxInputOffset + size_t(j) * (use_alpha ? 4 : 3) +
                    (k ? 3 : 0);
                shipyardMaterialInputs[k][j] = xboxRows[0] + offset;
                const unsigned mapping = comb->shader_input_mapping[k][j];
                if (mapping == G_CCMUX_SHADE) {
                    for (int i = 0; i < 3; ++i) {
                        const RGBA& shade = v_arr[i]->color;
                        if (k == 0) {
                            xboxRows[i][offset] = Shipyard::Fast3D::UnitColor(shade.r);
                            xboxRows[i][offset + 1] = Shipyard::Fast3D::UnitColor(shade.g);
                            xboxRows[i][offset + 2] = Shipyard::Fast3D::UnitColor(shade.b);
                        } else {
                            xboxRows[i][offset] = use_fog ? 1.0f :
                                Shipyard::Fast3D::UnitColor(shade.a);
                        }
                    }
                    continue;
                }
                const RGBA* color;
                RGBA tmp;
                switch (mapping) {
                case G_CCMUX_PRIMITIVE: color = &mRdp->prim_color; break;
                case G_CCMUX_ENVIRONMENT: color = &mRdp->env_color; break;
                case G_CCMUX_PRIMITIVE_ALPHA:
                    tmp.r = tmp.g = tmp.b = mRdp->prim_color.a; color = &tmp; break;
                case G_CCMUX_ENV_ALPHA:
                    tmp.r = tmp.g = tmp.b = mRdp->env_color.a; color = &tmp; break;
                case G_CCMUX_PRIM_LOD_FRAC:
                    tmp.r = tmp.g = tmp.b = mRdp->prim_lod_fraction; color = &tmp; break;
                case G_CCMUX_LOD_FRACTION:
                    if (mRdp->other_mode_l & G_TL_LOD) {
                        float distance_frac = (v1->w - 3000.0f) / 3000.0f;
                        if (distance_frac < 0.0f) distance_frac = 0.0f;
                        if (distance_frac > 1.0f) distance_frac = 1.0f;
                        tmp.r = tmp.g = tmp.b = tmp.a = distance_frac * 255.0f;
                    } else {
                        tmp.r = tmp.g = tmp.b = tmp.a = 255.0f;
                    }
                    color = &tmp;
                    break;
                case G_ACMUX_PRIM_LOD_FRAC:
                    tmp.a = mRdp->prim_lod_fraction; color = &tmp; break;
                default:
                    memset(&tmp, 0, sizeof(tmp)); color = &tmp; break;
                }
                if (k == 0) {
                    const float r = Shipyard::Fast3D::UnitColor(color->r);
                    const float g = Shipyard::Fast3D::UnitColor(color->g);
                    const float b = Shipyard::Fast3D::UnitColor(color->b);
                    for (int i = 0; i < 3; ++i) {
                        xboxRows[i][offset] = r;
                        xboxRows[i][offset + 1] = g;
                        xboxRows[i][offset + 2] = b;
                    }
                } else {
                    const float alpha = Shipyard::Fast3D::UnitColor(color->a);
                    for (int i = 0; i < 3; ++i) xboxRows[i][offset] = alpha;
                }
            }
        }
        shipyardVertexOutput += 3 * xboxColumnStride;
    } else {
    // MODERN COLUMN PACK FALLBACK BEGIN
    for (int i = 0; i < 3; i++) {
        if (xboxPairPackFirst) xboxPairStarts[i] = size_t(shipyardVertexOutput - mBufVbo);
        if(runCopy && runHits[i]) {
            float* row=shipyardVertexOutput;
            memcpy(row,mBufVbo+runCache.starts[xboxPairIndices[i]],runCache.stride*sizeof(float));
            shipyardVertexOutput+=runCache.stride;
            if(i==0) {
                for(unsigned j=0;j<numInputs;++j) {
                    shipyardMaterialInputs[0][j]=row+xboxInputOffset+j*(use_alpha?4:3);
                    if(use_alpha)shipyardMaterialInputs[1][j]=shipyardMaterialInputs[0][j]+3;
                }
            }
            continue;
        }
        if (xboxPairPackReuse && mXboxPairPacked.CopyVertex(xboxPairIndices[i], shipyardVertexOutput, mBufVbo)) {
            if (i == 0) mXboxPairPacked.RestoreMaterials(shipyardMaterialInputs, mBufVbo, numInputs, use_alpha);
            continue;
        }
        LaneWork::Add(LaneWork::StaticPack);LaneWork::Add(LaneWork::DynamicPack);
        float z = v_arr[i]->z, w = v_arr[i]->w;
        if (clip_parameters.z_is_from_0_to_1) {
            z = (z + w) / 2.0f;
        }

        *shipyardVertexOutput++ = v_arr[i]->x;
        *shipyardVertexOutput++ = clip_parameters.invertY ? -v_arr[i]->y : v_arr[i]->y;
        *shipyardVertexOutput++ = z;
        *shipyardVertexOutput++ = w;

        for (int t = 0; t < 2; t++) {
            if (!usedTextures[t]) {
                continue;
            }
            const bool shipyardHalfTexel = !is_rect &&
                (mRdp->other_mode_h & (3U << G_MDSFT_TEXTFILT)) != G_TF_POINT;
            *shipyardVertexOutput++ = Shipyard::Fast3D::Coordinate(
                v_arr[i]->u, mRdp->texture_tile[mRdp->first_tile_index + t].shifts,
                mRdp->texture_tile[mRdp->first_tile_index + t].uls,
                shipyardHalfTexel, tex_width[t]);
            *shipyardVertexOutput++ = Shipyard::Fast3D::Coordinate(
                v_arr[i]->v, mRdp->texture_tile[mRdp->first_tile_index + t].shiftt,
                mRdp->texture_tile[mRdp->first_tile_index + t].ult,
                shipyardHalfTexel, tex_height[t]);

            bool clampS = tm & (1 << 2 * t);
            bool clampT = tm & (1 << 2 * t + 1);

            if (clampS) {
                *shipyardVertexOutput++ = shipyardClampS[t];
            }

            if (clampT) {
                *shipyardVertexOutput++ = shipyardClampT[t];
            }
        }

        if (use_fog) {
            *shipyardVertexOutput++ = shipyardFog[0];
            *shipyardVertexOutput++ = shipyardFog[1];
            *shipyardVertexOutput++ = shipyardFog[2];
            *shipyardVertexOutput++ = Shipyard::Fast3D::UnitColor(v_arr[i]->color.a); // fog factor (not alpha)
        }

        if (use_grayscale) {
            *shipyardVertexOutput++ = shipyardGrayscale[0];
            *shipyardVertexOutput++ = shipyardGrayscale[1];
            *shipyardVertexOutput++ = shipyardGrayscale[2];
            *shipyardVertexOutput++ = shipyardGrayscale[3]; // lerp interpolation factor (not alpha)
        }

        for (int j = 0; j < numInputs; j++) {
            RGBA* color;
            RGBA tmp;
            for (int k = 0; k < 1 + (use_alpha ? 1 : 0); k++) {
                // Begin shared invariant material reuse.
                if (i != 0 && comb->shader_input_mapping[k][j] != G_CCMUX_SHADE) {
                    const float* input = shipyardMaterialInputs[k][j];
                    *shipyardVertexOutput++ = input[0];
                    if (k == 0) {
                        *shipyardVertexOutput++ = input[1];
                        *shipyardVertexOutput++ = input[2];
                    }
                    continue;
                }
                if (i == 0) shipyardMaterialInputs[k][j] = shipyardVertexOutput;
                // End shared invariant material reuse.
                switch (comb->shader_input_mapping[k][j]) {
                        // Note: CCMUX constants and ACMUX constants used here have same value, which is why this works
                        // (except LOD fraction).
                    case G_CCMUX_PRIMITIVE:
                        color = &mRdp->prim_color;
                        break;
                    case G_CCMUX_SHADE:
                        color = &v_arr[i]->color;
                        break;
                    case G_CCMUX_ENVIRONMENT:
                        color = &mRdp->env_color;
                        break;
                    case G_CCMUX_PRIMITIVE_ALPHA: {
                        tmp.r = tmp.g = tmp.b = mRdp->prim_color.a;
                        color = &tmp;
                        break;
                    }
                    case G_CCMUX_ENV_ALPHA: {
                        tmp.r = tmp.g = tmp.b = mRdp->env_color.a;
                        color = &tmp;
                        break;
                    }
                    case G_CCMUX_PRIM_LOD_FRAC: {
                        tmp.r = tmp.g = tmp.b = mRdp->prim_lod_fraction;
                        color = &tmp;
                        break;
                    }
                    case G_CCMUX_LOD_FRACTION: {
                        if (mRdp->other_mode_l & G_TL_LOD) {
                            // "Hack" that works for Bowser - Peach painting
                            float distance_frac = (v1->w - 3000.0f) / 3000.0f;
                            if (distance_frac < 0.0f) {
                                distance_frac = 0.0f;
                            }
                            if (distance_frac > 1.0f) {
                                distance_frac = 1.0f;
                            }
                            tmp.r = tmp.g = tmp.b = tmp.a = distance_frac * 255.0f;
                        } else {
                            tmp.r = tmp.g = tmp.b = tmp.a = 255.0f;
                        }
                        color = &tmp;
                        break;
                    }
                    case G_ACMUX_PRIM_LOD_FRAC:
                        tmp.a = mRdp->prim_lod_fraction;
                        color = &tmp;
                        break;
                    default:
                        memset(&tmp, 0, sizeof(tmp));
                        color = &tmp;
                        break;
                }
                if (k == 0) {
                    *shipyardVertexOutput++ = Shipyard::Fast3D::UnitColor(color->r);
                    *shipyardVertexOutput++ = Shipyard::Fast3D::UnitColor(color->g);
                    *shipyardVertexOutput++ = Shipyard::Fast3D::UnitColor(color->b);
                } else {
                    if (use_fog && color == &v_arr[i]->color) {
                        // Shade alpha is 100% for fog
                        *shipyardVertexOutput++ = 1.0f;
                    } else {
                        *shipyardVertexOutput++ = Shipyard::Fast3D::UnitColor(color->a);
                    }
                }
            }
        }

        // struct RGBA *color = &v_arr[i]->color;
        // mBufVbo[mBufVboLen++] = color->r / 255.0f;
        // mBufVbo[mBufVboLen++] = color->g / 255.0f;
        // mBufVbo[mBufVboLen++] = color->b / 255.0f;
        // mBufVbo[mBufVboLen++] = color->a / 255.0f;
    }

    }
    // MODERN COLUMN PACK END
    mBufVboLen = (size_t)(shipyardVertexOutput - mBufVbo);
    CampaignPreparedPack::Layout& prepared=CampaignPreparedPack::layout;
    if(prepared.pending) {
        ++prepared.checks;
        if(mBufVboLen-runStart!=3*prepared.stride ||
           memcmp(prepared.expected,mBufVbo+runStart,3*prepared.stride*sizeof(float)))++prepared.failures;
        prepared.pending=false;
    }
    if(runEligible && xboxColumnStride && xboxColumnStride<=32) {
        LaneWork::Add(LaneWork::LayoutPrepare);
        prepared.owner=this;prepared.epoch=runCache.epoch;prepared.stride=xboxColumnStride;
        memcpy(prepared.row,mBufVbo+runStart,xboxColumnStride*sizeof(float));
        prepared.textureOffset[0]=usedTextures[0]?xboxTextureOffset[0]:0;
        prepared.textureOffset[1]=usedTextures[1]?xboxTextureOffset[1]:0;
        prepared.fogOffset=xboxFogOffset;
        for(unsigned t=0;t<2;++t)if(usedTextures[t]) {
            const auto& tile=mRdp->texture_tile[mRdp->first_tile_index+t];
            prepared.uv[t][0].Prepare(tile.shifts,tile.uls,p.width[t]);
            prepared.uv[t][1].Prepare(tile.shiftt,tile.ult,p.height[t]);
        }

        prepared.halfTexel=!is_rect && (mRdp->other_mode_h&(3U<<G_MDSFT_TEXTFILT))!=G_TF_POINT;
        prepared.rgbCount=prepared.alphaCount=0;
        for(unsigned j=0;j<numInputs;++j) {
            const unsigned offset=xboxInputOffset+j*(use_alpha?4:3);
            if(comb->shader_input_mapping[0][j]==G_CCMUX_SHADE)prepared.shadeRgb[prepared.rgbCount++]=offset;
            if(use_alpha && comb->shader_input_mapping[1][j]==G_CCMUX_SHADE)prepared.shadeAlpha[prepared.alphaCount++]=offset+3;
        }
    } else prepared.owner=NULL;

    if(runEligible) {
        const size_t stride=(mBufVboLen-runStart)/3;
        if(stride && stride<=32 && stride*3==mBufVboLen-runStart) {
            for(unsigned i=0;i<3;++i) {
                if(runCache.mode==2 && runHits[i]) {
                    ++runCache.checks;
                    if(runCache.stride!=stride || memcmp(mBufVbo+runCache.starts[xboxPairIndices[i]],
                        mBufVbo+runStart+i*stride,stride*sizeof(float)))++runCache.mismatches;
                }
            }
            runCache.stride=stride;
            for(unsigned i=0;i<3;++i) {
                runCache.starts[xboxPairIndices[i]]=runStart+i*stride;
                runCache.stamps[xboxPairIndices[i]]=runCache.epoch;
            }
        } else runCache.Reset();
    }

    if (xboxPairPackFirst) {
        mXboxPairPacked.Capture(xboxPairIndices, xboxPairStarts, mBufVboLen, xboxPairFirstWBits);
        mXboxPairPacked.CaptureMaterials(shipyardMaterialInputs, mBufVbo, numInputs, use_alpha);
    }

    if (++mBufVboNumTris == MAX_TRI_BUFFER) {
        // if (++mBufVbo_num_tris == 1) {
        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
            *sModernTri2Sample, ModernFrameProfile::Tri2Flush);
        Flush();
        if (sModernTri2Sample) ModernFrameProfile::AdvanceTri2(
            *sModernTri2Sample, ModernFrameProfile::Tri2Pack);
        mXboxTrianglePairPrepared = false;
        mXboxPairPacked.Reset();
    }
}

void Interpreter::GfxSpGeometryMode(uint32_t clear, uint32_t set) {
    mRsp->geometry_mode &= ~clear;
    mRsp->geometry_mode |= set;
}

void Interpreter::GfxSpExtraGeometryMode(uint32_t clear, uint32_t set) {
    mRsp->extra_geometry_mode &= ~clear;
    mRsp->extra_geometry_mode |= set;
}

void Interpreter::AdjustVIewportOrScissor(XYWidthHeight* area) {
    if (!mFbActive) {
        // Adjust the y origin based on the y-inversion for the active framebuffer
        GfxClipParameters clipParameters = mRapi->GetClipParameters();
        if (clipParameters.invertY) {
            area->y -= area->height;
        } else {
            area->y = mNativeDimensions.height - area->y;
        }

        area->width *= RATIO_X(mActiveFrameBuffer, mCurDimensions);
        area->height *= RATIO_Y(mActiveFrameBuffer, mCurDimensions);
        area->x *= RATIO_X(mActiveFrameBuffer, mCurDimensions);
        area->y *= RATIO_Y(mActiveFrameBuffer, mCurDimensions);

        if (!mRendersToFb || (mMsaaLevel > 1 && mCurDimensions.width == mGameWindowViewport.width &&
                              mCurDimensions.height == mGameWindowViewport.height)) {
            area->x += mGameWindowViewport.x;
            area->y += mGfxCurrentWindowDimensions.height - (mGameWindowViewport.y + mGameWindowViewport.height);
        }
    } else {
        area->y = mActiveFrameBuffer->second.orig_height - area->y;

        if (mActiveFrameBuffer->second.resize) {
            area->width *= RATIO_X(mActiveFrameBuffer, mCurDimensions);
            area->height *= RATIO_Y(mActiveFrameBuffer, mCurDimensions);
            area->x *= RATIO_X(mActiveFrameBuffer, mCurDimensions);
            area->y *= RATIO_Y(mActiveFrameBuffer, mCurDimensions);
        }
    }
}

void Interpreter::CalcAndSetViewport(const F3DVp_t* viewport) {
    // 2 bits fraction
    float width = 2.0f * viewport->vscale[0] / 4.0f;
    float height = 2.0f * viewport->vscale[1] / 4.0f;
    float x = (viewport->vtrans[0] / 4.0f) - width / 2.0f;
    float y = ((viewport->vtrans[1] / 4.0f) + height / 2.0f);

    mRdp->viewport.x = x;
    mRdp->viewport.y = y;
    mRdp->viewport.width = width;
    mRdp->viewport.height = height;

    AdjustVIewportOrScissor(&mRdp->viewport);

    mRdp->viewport_or_scissor_changed = true;
}

void Interpreter::GfxSpMovememF3dex2(uint8_t index, uint8_t offset, const void* data) {
    if(UpdateStream::packet.active && UpdateStream::packet.recording && UpdateStream::packet.current<UpdateStream::packet.instructions.size()) {
        UpdateStream::Instruction& op=UpdateStream::packet.instructions[UpdateStream::packet.current];
        op.kind=UpdateStream::MoveMemory;op.payload[0]=index;op.payload[1]=offset;op.payload[2]=unsigned(uintptr_t(data));
    }
    CampaignDeferredState::snapshot.Invalidate();
    switch (index) {
        case F3DEX2_G_MV_VIEWPORT:
            CalcAndSetViewport((const F3DVp_t*)data);
            break;
        case F3DEX2_G_MV_LIGHT: {
            int lightidx = offset / 24 - 2;
            if (lightidx >= 0 && lightidx <= MAX_LIGHTS) { // skip lookat
                // NOTE: reads out of bounds if it is an ambient light
                memcpy(mRsp->current_lights + lightidx, data, sizeof(F3DLight));
            } else if (lightidx < 0) {
                memcpy(mRsp->lookat + offset / 24, data, sizeof(F3DLight_t)); // TODO Light?
            }
            break;
        }
    }
}

void Interpreter::GfxSpMovememF3d(uint8_t index, uint8_t offset, const void* data) {
    CampaignDeferredState::snapshot.Invalidate();
    switch (index) {
        case F3DEX_G_MV_VIEWPORT:
            CalcAndSetViewport((const F3DVp_t*)data);
            break;
        case F3DEX_G_MV_LOOKATY:
        case F3DEX_G_MV_LOOKATX:
            memcpy(mRsp->lookat + (index - F3DEX_G_MV_LOOKATY) / 2, data, sizeof(F3DLight_t));
            break;
        case F3DEX_G_MV_L0:
        case F3DEX_G_MV_L1:
        case F3DEX_G_MV_L2:
        case F3DEX_G_MV_L3:
        case F3DEX_G_MV_L4:
        case F3DEX_G_MV_L5:
        case F3DEX_G_MV_L6:
        case F3DEX_G_MV_L7:
            // NOTE: reads out of bounds if it is an ambient light
            memcpy(mRsp->current_lights + (index - F3DEX_G_MV_L0) / 2, data, sizeof(F3DLight_t));
            break;
    }
}

void Interpreter::GfxSpMovewordF3dex2(uint8_t index, uint16_t offset, uintptr_t data) {
    if(index==G_MW_FOG)CampaignDeferredState::snapshot.Invalidate();
    switch (index) {
        case G_MW_NUMLIGHT:
            mRsp->current_num_lights = data / 24 + 1; // add ambient light
            CampaignDeferredState::snapshot.Invalidate(); mRsp->lights_changed = true;
            break;
        case G_MW_FOG:
            mRsp->fog_mul = (int16_t)(data >> 16);
            mRsp->fog_offset = (int16_t)data;
            break;
        case G_MW_SEGMENT: {
            int segNumber = offset / 4;
            mSegmentPointers[segNumber] = data;
        } break;
        case G_MW_SEGMENT_INTERP: {
            if(UpdateStream::packet.active)UpdateStream::packet.conditional=true;
            int segNumber = offset % 16;
            int segIndex = offset / 16;

            if (segIndex == mInterpolationIndex)
                mSegmentPointers[segNumber] = data;
        } break;
    }
}

void Interpreter::GfxSpMovewordF3d(uint8_t index, uint16_t offset, uintptr_t data) {
    if(index==G_MW_FOG)CampaignDeferredState::snapshot.Invalidate();
    switch (index) {
        case G_MW_NUMLIGHT:
            // Ambient light is included
            // The 31st bit is a flag that lights should be recalculated
            mRsp->current_num_lights = (data - 0x80000000U) / 32;
            CampaignDeferredState::snapshot.Invalidate(); mRsp->lights_changed = true;
            break;
        case G_MW_FOG:
            mRsp->fog_mul = (int16_t)(data >> 16);
            mRsp->fog_offset = (int16_t)data;
            break;
        case G_MW_SEGMENT: {
            int segNumber = offset / 4;
            mSegmentPointers[segNumber] = data;
        } break;
        case G_MW_SEGMENT_INTERP: {
            if(UpdateStream::packet.active)UpdateStream::packet.conditional=true;
            int segNumber = offset % 16;
            int segIndex = offset / 16;

            if (segIndex == mInterpolationIndex)
                mSegmentPointers[segNumber] = data;
        } break;
    }
}

void Interpreter::GfxSpTexture(uint16_t sc, uint16_t tc, uint8_t level, uint8_t tile, uint8_t on) {
    if(mRsp->texture_scaling_factor.s!=sc || mRsp->texture_scaling_factor.t!=tc)
        CampaignDeferredState::snapshot.Invalidate();
    mRsp->texture_scaling_factor.s = sc;
    mRsp->texture_scaling_factor.t = tc;
    if (mRdp->first_tile_index != tile) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }

    mRdp->first_tile_index = tile;
}

void Interpreter::GfxDpSetScissor(uint32_t mode, uint32_t ulx, uint32_t uly, uint32_t lrx, uint32_t lry) {
    float x = ulx / 4.0f;
    float y = lry / 4.0f;
    float width = (lrx - ulx) / 4.0f;
    float height = (lry - uly) / 4.0f;

    mRdp->scissor.x = x;
    mRdp->scissor.y = y;
    mRdp->scissor.width = width;
    mRdp->scissor.height = height;

    AdjustVIewportOrScissor(&mRdp->scissor);

    mRdp->viewport_or_scissor_changed = true;
}

void Interpreter::GfxDpSetTextureImage(uint32_t format, uint32_t size, uint32_t width, const char* texPath,
                                       uint32_t texFlags, const RawTexMetadata& rawTexMetdata, const void* addr) {
    UpdateStream::CaptureTexture(format,size,width,texFlags,rawTexMetdata,addr);
    // fprintf(stderr, "GfxDpSetTextureImage: %s (width=%d; size=0x%X)\n",
    //         rawTexMetdata.resource ? rawTexMetdata.resource->GetInitData()->Path.c_str() : nullptr, width, size);
    mRdp->texture_to_load.addr = (const uint8_t*)addr;
    mRdp->texture_to_load.siz = size;
    mRdp->texture_to_load.width = width;
    mRdp->texture_to_load.tex_flags = texFlags;
    mRdp->texture_to_load.raw_tex_metadata = rawTexMetdata;
}

void Interpreter::GfxDpSetTile(uint8_t fmt, uint32_t siz, uint32_t line, uint32_t tmem, uint8_t tile, uint32_t palette,
                               uint32_t cmt, uint32_t maskt, uint32_t shiftt, uint32_t cms, uint32_t masks,
                               uint32_t shifts) {
    // OTRTODO:
    // SUPPORT_CHECK(tmem == 0 || tmem == 256);

    if (cms == G_TX_WRAP && masks == G_TX_NOMASK) {
        cms = G_TX_CLAMP;
    }
    if (cmt == G_TX_WRAP && maskt == G_TX_NOMASK) {
        cmt = G_TX_CLAMP;
    }

    const bool xboxTileTrial = mXboxTileTrialEnabled;
    const bool xboxTileCapture = mXboxTileCaptureEnabled;
    bool xboxSameTileState = false;
    if (xboxTileTrial || xboxTileCapture) {
        const bool xboxCouldAvoidDirty =
            !mRdp->textures_changed[0] || !mRdp->textures_changed[1];
        if (xboxCouldAvoidDirty || xboxTileCapture) {
            const auto& previous = mRdp->texture_tile[tile];
            xboxSameTileState =
            previous.palette == static_cast<uint8_t>(palette) &&
            previous.fmt == static_cast<uint8_t>(fmt) &&
            previous.siz == static_cast<uint8_t>(siz) &&
            previous.cms == static_cast<uint8_t>(cms) &&
            previous.cmt == static_cast<uint8_t>(cmt) &&
            previous.shifts == static_cast<uint8_t>(shifts) &&
            previous.shiftt == static_cast<uint8_t>(shiftt) &&
            previous.line_size_bytes == line * 8 &&
            previous.tmem == static_cast<uint16_t>(tmem) &&
            previous.tmem_index == static_cast<uint8_t>(tmem != 0);
            if (xboxTileCapture)
                ModernFrameProfile::ObserveTileState(0, xboxSameTileState,
                            xboxSameTileState && xboxCouldAvoidDirty);
        }
    }
    mRdp->texture_tile[tile].palette = palette; // palette should set upper 4 bits of color index in 4b mode
    mRdp->texture_tile[tile].fmt = fmt;
    mRdp->texture_tile[tile].siz = siz;
    mRdp->texture_tile[tile].cms = cms;
    mRdp->texture_tile[tile].cmt = cmt;
    mRdp->texture_tile[tile].shifts = shifts;
    mRdp->texture_tile[tile].shiftt = shiftt;
    mRdp->texture_tile[tile].line_size_bytes = line * 8;

    mRdp->texture_tile[tile].tmem = tmem;
    // mRdp->texture_tile[tile].tmem_index = tmem / 256; // tmem is the 64-bit word offset, so 256 words means 2 kB

    mRdp->texture_tile[tile].tmem_index =
        tmem != 0; // assume one texture is loaded at address 0 and another texture at any other address

    if (!xboxTileTrial || !xboxSameTileState) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
}

void Interpreter::GfxDpSetTileSize(uint8_t tile, uint16_t uls, uint16_t ult, uint16_t lrs, uint16_t lrt) {
    const bool xboxTileTrial = mXboxTileTrialEnabled;
    const bool xboxTileCapture = mXboxTileCaptureEnabled;
    bool xboxSameTileState = false;
    if (xboxTileTrial || xboxTileCapture) {
        const bool xboxCouldAvoidDirty =
            !mRdp->textures_changed[0] || !mRdp->textures_changed[1];
        if (xboxCouldAvoidDirty || xboxTileCapture) {
            const auto& previous = mRdp->texture_tile[tile];
            xboxSameTileState =
            previous.uls == static_cast<float>(uls) &&
            previous.ult == static_cast<float>(ult) &&
            previous.lrs == static_cast<float>(lrs) &&
            previous.lrt == static_cast<float>(lrt);
            if (xboxTileCapture)
                ModernFrameProfile::ObserveTileState(1, xboxSameTileState,
                            xboxSameTileState && xboxCouldAvoidDirty);
        }
    }
    mRdp->texture_tile[tile].uls = uls;
    mRdp->texture_tile[tile].ult = ult;
    mRdp->texture_tile[tile].lrs = lrs;
    mRdp->texture_tile[tile].lrt = lrt;
    if (!xboxTileTrial || !xboxSameTileState) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
}

void Interpreter::GfxDpLoadTlut(uint8_t tile, uint32_t high_index) {
    SUPPORT_CHECK(mRdp->texture_to_load.siz == G_IM_SIZ_16b);

    if (mRdp->texture_tile[tile].tmem == 256) {
        mRdp->palettes[0] = mRdp->texture_to_load.addr;
        if (high_index == 255) {
            mRdp->palettes[1] = mRdp->texture_to_load.addr + 2 * 128;
        }
    } else {
        mRdp->palettes[1] = mRdp->texture_to_load.addr;
    }
}

void Interpreter::GfxDpLoadBlock(uint8_t tile, uint32_t uls, uint32_t ult, uint32_t lrs, uint32_t dxt) {
    SUPPORT_CHECK(uls == 0);
    SUPPORT_CHECK(ult == 0);

    // The lrs field rather seems to be number of pixels to load
    uint32_t word_size_shift = 0;
    switch (mRdp->texture_to_load.siz) {
        case G_IM_SIZ_4b:
            word_size_shift = -1;
            break;
        case G_IM_SIZ_8b:
            word_size_shift = 0;
            break;
        case G_IM_SIZ_16b:
            word_size_shift = 1;
            break;
        case G_IM_SIZ_32b:
            word_size_shift = 2;
            break;
    }
    uint32_t orig_size_bytes =
        word_size_shift > 0 ? (lrs + 1) << word_size_shift : (lrs + 1) >> (-(int64_t)word_size_shift);
    uint32_t size_bytes = orig_size_bytes;
    if (mRdp->texture_to_load.raw_tex_metadata.h_byte_scale != 1 ||
        mRdp->texture_to_load.raw_tex_metadata.v_pixel_scale != 1) {
        size_bytes *= mRdp->texture_to_load.raw_tex_metadata.h_byte_scale;
        size_bytes *= mRdp->texture_to_load.raw_tex_metadata.v_pixel_scale;
    }
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].orig_size_bytes = orig_size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes = size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes = size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes = size_bytes;
    // assert(size_bytes <= 4096 && "bug: too big texture");
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].tex_flags = mRdp->texture_to_load.tex_flags;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata = mRdp->texture_to_load.raw_tex_metadata;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr = mRdp->texture_to_load.addr;
    // fprintf(stderr, "GfxDpLoadBlock: line_size = 0x%x; orig = 0x%x; bpp=%d; lrs=%d\n", size_bytes,
    // orig_size_bytes,
    //         mRdp->texture_to_load.siz, lrs);

    if (mMaskedTextures.empty()) {
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].masked = false;
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].blended = false;
    } else {
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
    }

    mRdp->textures_changed[mRdp->texture_tile[tile].tmem_index] = true;
}

void Interpreter::GfxDpLoadTile(uint8_t tile, uint32_t uls, uint32_t ult, uint32_t lrs, uint32_t lrt) {
    SUPPORT_CHECK(tile == G_TX_LOADTILE);

    uint32_t word_size_shift = 0;
    switch (mRdp->texture_to_load.siz) {
        case G_IM_SIZ_4b:
            word_size_shift = 0;
            break;
        case G_IM_SIZ_8b:
            word_size_shift = 0;
            break;
        case G_IM_SIZ_16b:
            word_size_shift = 1;
            break;
        case G_IM_SIZ_32b:
            word_size_shift = 2;
            break;
    }

    uint32_t offset_x = uls >> G_TEXTURE_IMAGE_FRAC;
    uint32_t offset_y = ult >> G_TEXTURE_IMAGE_FRAC;
    uint32_t tile_width = ((lrs - uls) >> G_TEXTURE_IMAGE_FRAC) + 1;
    uint32_t tile_height = ((lrt - ult) >> G_TEXTURE_IMAGE_FRAC) + 1;
    uint32_t full_image_width = mRdp->texture_to_load.width;

    uint32_t offset_x_in_bytes = offset_x << word_size_shift;
    uint32_t tile_line_size_bytes = tile_width << word_size_shift;
    uint32_t full_image_line_size_bytes = full_image_width << word_size_shift;

    uint32_t orig_size_bytes = tile_line_size_bytes * tile_height;
    uint32_t size_bytes = orig_size_bytes;
    uint32_t start_offset_bytes = full_image_line_size_bytes * offset_y + offset_x_in_bytes;

    float h_byte_scale = mRdp->texture_to_load.raw_tex_metadata.h_byte_scale;
    float v_pixel_scale = mRdp->texture_to_load.raw_tex_metadata.v_pixel_scale;

    if (h_byte_scale != 1 || v_pixel_scale != 1) {
        start_offset_bytes = h_byte_scale * (v_pixel_scale * offset_y * full_image_line_size_bytes + offset_x_in_bytes);
        size_bytes *= h_byte_scale * v_pixel_scale;
        full_image_line_size_bytes *= h_byte_scale;
        tile_line_size_bytes *= h_byte_scale;
    }

    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].orig_size_bytes = orig_size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].size_bytes = size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].full_image_line_size_bytes = full_image_line_size_bytes;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].line_size_bytes = tile_line_size_bytes;

    //    assert(size_bytes <= 4096 && "bug: too big texture");
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].tex_flags = mRdp->texture_to_load.tex_flags;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].raw_tex_metadata = mRdp->texture_to_load.raw_tex_metadata;
    mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].addr = mRdp->texture_to_load.addr + start_offset_bytes;

    if (mMaskedTextures.empty()) {
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].masked = false;
        mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index].blended = false;
    } else {
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
    }

    mRdp->texture_tile[tile].uls = uls;
    mRdp->texture_tile[tile].ult = ult;
    mRdp->texture_tile[tile].lrs = lrs;
    mRdp->texture_tile[tile].lrt = lrt;

    mRdp->textures_changed[mRdp->texture_tile[tile].tmem_index] = true;
}

/*static uint8_t color_comb_component(uint32_t v) {
    switch (v) {
        case G_CCMUX_TEXEL0:
            return CC_TEXEL0;
        case G_CCMUX_TEXEL1:
            return CC_TEXEL1;
        case G_CCMUX_PRIMITIVE:
            return CC_PRIM;
        case G_CCMUX_SHADE:
            return CC_SHADE;
        case G_CCMUX_ENVIRONMENT:
            return CC_ENV;
        case G_CCMUX_TEXEL0_ALPHA:
            return CC_TEXEL0A;
        case G_CCMUX_LOD_FRACTION:
            return CC_LOD;
        default:
            return CC_0;
    }
}

static inline uint32_t color_comb(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    return color_comb_component(a) |
           (color_comb_component(b) << 3) |
           (color_comb_component(c) << 6) |
           (color_comb_component(d) << 9);
}

static void GfxDpSetCombineMode(uint32_t rgb, uint32_t alpha) {
    mRdp->combine_mode = rgb | (alpha << 12);
}*/

void Interpreter::GfxDpSetCombineMode(uint32_t rgb, uint32_t alpha, uint32_t rgb_cyc2, uint32_t alpha_cyc2) {
    mRdp->combine_mode = rgb | (alpha << 16) | ((uint64_t)rgb_cyc2 << 28) | ((uint64_t)alpha_cyc2 << 44);
}

static inline uint32_t color_comb(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    return (a & 0xf) | ((b & 0xf) << 4) | ((c & 0x1f) << 8) | ((d & 7) << 13);
}

static inline uint32_t alpha_comb(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    return (a & 7) | ((b & 7) << 3) | ((c & 7) << 6) | ((d & 7) << 9);
}

void Interpreter::GfxDpSetGrayscaleColor(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    mRdp->grayscale_color.r = r;
    mRdp->grayscale_color.g = g;
    mRdp->grayscale_color.b = b;
    mRdp->grayscale_color.a = a;
}

void Interpreter::GfxDpSetEnvColor(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    mRdp->env_color.r = r;
    mRdp->env_color.g = g;
    mRdp->env_color.b = b;
    mRdp->env_color.a = a;
}

void Interpreter::GfxDpSetPrimColor(uint8_t m, uint8_t l, uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    mRdp->prim_lod_fraction = l;
    mRdp->prim_color.r = r;
    mRdp->prim_color.g = g;
    mRdp->prim_color.b = b;
    mRdp->prim_color.a = a;
}

void Interpreter::GfxDpSetFogColor(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    mRdp->fog_color.r = r;
    mRdp->fog_color.g = g;
    mRdp->fog_color.b = b;
    mRdp->fog_color.a = a;
}

void Interpreter::GfxDpSetBlendColor(uint8_t r, uint8_t g, uint8_t b, uint8_t a) {
    // TODO: Implement this command..
}

void Interpreter::GfxDpSetFillColor(uint32_t packed_color) {
    uint16_t col16 = (uint16_t)packed_color;
    uint32_t r = col16 >> 11;
    uint32_t g = (col16 >> 6) & 0x1f;
    uint32_t b = (col16 >> 1) & 0x1f;
    uint32_t a = col16 & 1;
    mRdp->fill_color.r = SCALE_5_8(r);
    mRdp->fill_color.g = SCALE_5_8(g);
    mRdp->fill_color.b = SCALE_5_8(b);
    mRdp->fill_color.a = a * 255;
}

void Interpreter::GfxDrawRectangle(int32_t ulx, int32_t uly, int32_t lrx, int32_t lry) {
    uint32_t saved_other_mode_h = mRdp->other_mode_h;
    uint32_t cycle_type = (mRdp->other_mode_h & (3U << G_MDSFT_CYCLETYPE));

    if (cycle_type == G_CYC_COPY) {
        mRdp->other_mode_h = (mRdp->other_mode_h & ~(3U << G_MDSFT_TEXTFILT)) | G_TF_POINT;
    }

    // U10.2 coordinates
    float ulxf = ulx;
    float ulyf = uly;
    float lrxf = lrx;
    float lryf = lry;

    ulxf = ulxf / (4.0f * HALF_SCREEN_WIDTH(mActiveFrameBuffer)) - 1.0f;
    ulyf = -(ulyf / (4.0f * HALF_SCREEN_HEIGHT(mActiveFrameBuffer))) + 1.0f;
    lrxf = lrxf / (4.0f * HALF_SCREEN_WIDTH(mActiveFrameBuffer)) - 1.0f;
    lryf = -(lryf / (4.0f * HALF_SCREEN_HEIGHT(mActiveFrameBuffer))) + 1.0f;

    ulxf = AdjXForAspectRatio(ulxf);
    lrxf = AdjXForAspectRatio(lrxf);

    struct LoadedVertex* ul = &mRsp->loaded_vertices[MAX_VERTICES + 0];
    struct LoadedVertex* ll = &mRsp->loaded_vertices[MAX_VERTICES + 1];
    struct LoadedVertex* lr = &mRsp->loaded_vertices[MAX_VERTICES + 2];
    struct LoadedVertex* ur = &mRsp->loaded_vertices[MAX_VERTICES + 3];

    ul->x = ulxf;
    ul->y = ulyf;
    ul->z = -1.0f;
    ul->w = 1.0f;

    ll->x = ulxf;
    ll->y = lryf;
    ll->z = -1.0f;
    ll->w = 1.0f;

    lr->x = lrxf;
    lr->y = lryf;
    lr->z = -1.0f;
    lr->w = 1.0f;

    ur->x = lrxf;
    ur->y = ulyf;
    ur->z = -1.0f;
    ur->w = 1.0f;

    // The coordinates for texture rectangle shall bypass the viewport setting
    struct XYWidthHeight default_viewport;
    if (!mFbActive) {
        { XYWidthHeight shipyardAggregate = { 0, (int16_t)mNativeDimensions.height, mNativeDimensions.width, mNativeDimensions.height }; default_viewport = shipyardAggregate; }
    } else {
        { XYWidthHeight shipyardAggregate = { 0, (int16_t)mActiveFrameBuffer->second.orig_height, mActiveFrameBuffer->second.orig_width,
                             mActiveFrameBuffer->second.orig_height }; default_viewport = shipyardAggregate; }
    }

    struct XYWidthHeight viewport_saved = mRdp->viewport;
    uint32_t geometry_mode_saved = mRsp->geometry_mode;

    AdjustVIewportOrScissor(&default_viewport);

    mRdp->viewport = default_viewport;
    mRdp->viewport_or_scissor_changed = true;
    mRsp->geometry_mode = 0;

    GfxSpTri1(MAX_VERTICES + 0, MAX_VERTICES + 1, MAX_VERTICES + 3, true);
    GfxSpTri1(MAX_VERTICES + 1, MAX_VERTICES + 2, MAX_VERTICES + 3, true);

    mRsp->geometry_mode = geometry_mode_saved;
    mRdp->viewport = viewport_saved;
    mRdp->viewport_or_scissor_changed = true;

    if (cycle_type == G_CYC_COPY) {
        mRdp->other_mode_h = saved_other_mode_h;
    }
}

void Interpreter::GfxDpTextureRectangle(int32_t ulx, int32_t uly, int32_t lrx, int32_t lry, uint8_t tile, int16_t uls,
                                        int16_t ult, int16_t dsdx, int16_t dtdy, bool flip) {
    // printf("render %d at %d\n", tile, lrx);
    uint64_t saved_combine_mode = mRdp->combine_mode;
    if ((mRdp->other_mode_h & (3U << G_MDSFT_CYCLETYPE)) == G_CYC_COPY) {
        // Per RDP Command Summary Set Tile's shift s and this dsdx should be set to 4 texels
        // Divide by 4 to get 1 instead
        dsdx >>= 2;

        // Color combiner is turned off in copy mode
        GfxDpSetCombineMode(color_comb(0, 0, 0, G_CCMUX_TEXEL0), alpha_comb(0, 0, 0, G_ACMUX_TEXEL0), 0, 0);

        // Per documentation one extra pixel is added in this modes to each edge
        lrx += 1 << 2;
        lry += 1 << 2;
    }

    // uls and ult are S10.5
    // dsdx and dtdy are S5.10
    // lrx, lry, ulx, uly are U10.2
    // lrs, lrt are S10.5
    if (flip) {
        dsdx = -dsdx;
        dtdy = -dtdy;
    }
    int16_t width = !flip ? lrx - ulx : lry - uly;
    int16_t height = !flip ? lry - uly : lrx - ulx;
    float lrs = ((uls << 7) + dsdx * width) >> 7;
    float lrt = ((ult << 7) + dtdy * height) >> 7;

    LoadedVertex* ul = &mRsp->loaded_vertices[MAX_VERTICES + 0];
    LoadedVertex* ll = &mRsp->loaded_vertices[MAX_VERTICES + 1];
    LoadedVertex* lr = &mRsp->loaded_vertices[MAX_VERTICES + 2];
    LoadedVertex* ur = &mRsp->loaded_vertices[MAX_VERTICES + 3];
    ul->u = uls;
    ul->v = ult;
    lr->u = lrs;
    lr->v = lrt;
    if (!flip) {
        ll->u = uls;
        ll->v = lrt;
        ur->u = lrs;
        ur->v = ult;
    } else {
        ll->u = lrs;
        ll->v = ult;
        ur->u = uls;
        ur->v = lrt;
    }

    uint8_t saved_tile = mRdp->first_tile_index;
    if (saved_tile != tile) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
    mRdp->first_tile_index = tile;

    GfxDrawRectangle(ulx, uly, lrx, lry);
    if (saved_tile != tile) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
    mRdp->first_tile_index = saved_tile;
    mRdp->combine_mode = saved_combine_mode;
}

void Interpreter::GfxDpImageRectangle(int32_t tile, int32_t w, int32_t h, int32_t ulx, int32_t uly, int16_t uls,
                                      int16_t ult, int32_t lrx, int32_t lry, int16_t lrs, int16_t lrt) {

    LoadedVertex* ul = &mRsp->loaded_vertices[MAX_VERTICES + 0];
    LoadedVertex* ll = &mRsp->loaded_vertices[MAX_VERTICES + 1];
    LoadedVertex* lr = &mRsp->loaded_vertices[MAX_VERTICES + 2];
    LoadedVertex* ur = &mRsp->loaded_vertices[MAX_VERTICES + 3];
    ul->u = uls * 32;
    ul->v = ult * 32;
    lr->u = lrs * 32;
    lr->v = lrt * 32;
    ll->u = uls * 32;
    ll->v = lrt * 32;
    ur->u = lrs * 32;
    ur->v = ult * 32;

    // ensure we have the correct texture size, format and starting position
    mRdp->texture_tile[tile].siz = G_IM_SIZ_8b;
    mRdp->texture_tile[tile].fmt = G_IM_FMT_RGBA;
    mRdp->texture_tile[tile].cms = 0;
    mRdp->texture_tile[tile].cmt = 0;
    mRdp->texture_tile[tile].shifts = 0;
    mRdp->texture_tile[tile].shiftt = 0;
    mRdp->texture_tile[tile].uls = 0 * 4;
    mRdp->texture_tile[tile].ult = 0 * 4;
    mRdp->texture_tile[tile].lrs = w * 4;
    mRdp->texture_tile[tile].lrt = h * 4;
    mRdp->texture_tile[tile].line_size_bytes = w << (mRdp->texture_tile[tile].siz >> 1);

    auto& loadtex = mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index];
    loadtex.full_image_line_size_bytes = loadtex.line_size_bytes = mRdp->texture_tile[tile].line_size_bytes;
    loadtex.size_bytes = loadtex.orig_size_bytes = loadtex.line_size_bytes * h;

    uint8_t saved_tile = mRdp->first_tile_index;
    if (saved_tile != tile) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
    mRdp->first_tile_index = tile;

    GfxDrawRectangle(ulx, uly, lrx, lry);
    if (saved_tile != tile) {
        mRdp->textures_changed[0] = true;
        mRdp->textures_changed[1] = true;
    }
    mRdp->first_tile_index = saved_tile;
}

void Interpreter::GfxDpFillRectangle(int32_t ulx, int32_t uly, int32_t lrx, int32_t lry) {
    if (mRdp->color_image_address == mRdp->z_buf_address) {
        // Don't clear Z buffer here since we already did it with glClear
        return;
    }
    uint32_t mode = (mRdp->other_mode_h & (3U << G_MDSFT_CYCLETYPE));

    // OTRTODO: This is a bit of a hack for widescreen screen fades, but it'll work for now...
    if (ulx == 0 && uly == 0 && lrx == (319 * 4) && lry == (239 * 4)) {
        ulx = -1024;
        uly = -1024;
        lrx = 2048;
        lry = 2048;
    }

    if (mode == G_CYC_COPY || mode == G_CYC_FILL) {
        // Per documentation one extra pixel is added in this modes to each edge
        lrx += 1 << 2;
        lry += 1 << 2;
    }

    // The backend also requires a pending, idle, single-sample game target.
    // This consumer proves its first color operation overwrites every pixel.
    if (mXboxCanDiscardGameColor) {
        const LoadedVertex* corners = &mRsp->loaded_vertices[MAX_VERTICES];
        const bool fullOpaqueFill = !mFbActive && mRendersToFb &&
            mMsaaLevel == 1 && mBufVboLen == 0 && mBufVboNumTris == 0 &&
            mode == G_CYC_FILL && mRdp->other_mode_l ==
                (G_AC_NONE | G_ZS_PIXEL | G_RM_NOOP | G_RM_NOOP2) &&
            mRdp->fill_color.a == 255 && !mRdp->grayscale &&
            !mRdp->current_shader.enabled &&
            ModernFast3D::FullGameFillCovers(
                mNativeDimensions.width, mNativeDimensions.height,
                mCurDimensions.width, mCurDimensions.height,
                ulx, uly, lrx, lry,
                mRdp->scissor.x, mRdp->scissor.y,
                mRdp->scissor.width, mRdp->scissor.height,
                corners[0].clip_rej, corners[1].clip_rej,
                corners[2].clip_rej, corners[3].clip_rej);
        if (fullOpaqueFill)
            Fast::ShipyardXenos::TryDiscardGameFramebufferColor();
        // A partial first fill or backend rejection cannot be retried.
        mXboxCanDiscardGameColor = false;
    }

    for (int i = MAX_VERTICES; i < MAX_VERTICES + 4; i++) {
        LoadedVertex* v = &mRsp->loaded_vertices[i];
        v->color = mRdp->fill_color;
    }

    uint64_t saved_combine_mode = mRdp->combine_mode;

    if (mode == G_CYC_FILL) {
        GfxDpSetCombineMode(color_comb(0, 0, 0, G_CCMUX_SHADE), alpha_comb(0, 0, 0, G_ACMUX_SHADE), 0, 0);
    }

    GfxDrawRectangle(ulx, uly, lrx, lry);
    mRdp->combine_mode = saved_combine_mode;
}

void Interpreter::GfxDpSetZImage(void* zBufAddr) {
    mRdp->z_buf_address = zBufAddr;
}

void Interpreter::GfxDpSetColorImage(uint32_t format, uint32_t size, uint32_t width, void* address) {
    mRdp->color_image_address = address;
}

void Interpreter::GfxSpSetOtherMode(uint32_t shift, uint32_t num_bits, uint64_t mode) {
    uint64_t mask = (((uint64_t)1 << num_bits) - 1) << shift;
    uint64_t om = mRdp->other_mode_l | ((uint64_t)mRdp->other_mode_h << 32);
    om = (om & ~mask) | mode;
    mRdp->other_mode_l = (uint32_t)om;
    mRdp->other_mode_h = (uint32_t)(om >> 32);
}

void Interpreter::GfxDpSetOtherMode(uint32_t h, uint32_t l) {
    mRdp->other_mode_h = h;
    mRdp->other_mode_l = l;
}

void Interpreter::Gfxs2dexBgCopy(F3DuObjBg* bg) {
    /*
    bg->b.imageX = 0;
    bg->b.imageW = width * 4;
    bg->b.frameX = frameX * 4;
    bg->b.imageY = 0;
    bg->b.imageH = height * 4;
    bg->b.frameY = frameY * 4;
    bg->b.imagePtr = source;
    bg->b.imageLoad = G_BGLT_LOADTILE;
    bg->b.imageFmt = fmt;
    bg->b.imageSiz = siz;
    bg->b.imagePal = 0;
    bg->b.imageFlip = 0;
    */

    uintptr_t data = (uintptr_t)bg->b.imagePtr;

    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    if ((bool)gfx_check_image_signature((char*)data)) {
        std::shared_ptr<Fast::Texture> tex = std::static_pointer_cast<Fast::Texture>(
            Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess((char*)data));
        texFlags = tex->Flags;
        rawTexMetadata.width = tex->Width;
        rawTexMetadata.height = tex->Height;
        rawTexMetadata.h_byte_scale = tex->HByteScale;
        rawTexMetadata.v_pixel_scale = tex->VPixelScale;
        rawTexMetadata.type = tex->Type;
        rawTexMetadata.resource = tex;
        data = (uintptr_t) reinterpret_cast<char*>(tex->ImageData);
    }

    s16 dsdx = 4 << 10;
    s16 uls = bg->b.imageX << 3;
    // Flip flag only flips horizontally
    if (bg->b.imageFlip == G_BG_FLAG_FLIPS) {
        dsdx = -dsdx;
        uls = (bg->b.imageW - bg->b.imageX) << 3;
    }

    SUPPORT_CHECK(bg->b.imageSiz == G_IM_SIZ_16b);
    GfxDpSetTextureImage(G_IM_FMT_RGBA, G_IM_SIZ_16b, 0, nullptr, texFlags, rawTexMetadata, (void*)data);
    GfxDpSetTile(G_IM_FMT_RGBA, G_IM_SIZ_16b, 0, 0, G_TX_LOADTILE, 0, 0, 0, 0, 0, 0, 0);
    GfxDpLoadBlock(G_TX_LOADTILE, 0, 0, (bg->b.imageW * bg->b.imageH >> 4) - 1, 0);
    GfxDpSetTile(bg->b.imageFmt, G_IM_SIZ_16b, bg->b.imageW >> 4, 0, G_TX_RENDERTILE, bg->b.imagePal, 0, 0, 0, 0, 0, 0);
    GfxDpSetTileSize(G_TX_RENDERTILE, 0, 0, bg->b.imageW, bg->b.imageH);
    GfxDpTextureRectangle(bg->b.frameX, bg->b.frameY, bg->b.frameX + bg->b.imageW - 4, bg->b.frameY + bg->b.imageH - 4,
                          G_TX_RENDERTILE, uls, bg->b.imageY << 3, dsdx, 1 << 10, false);
}

void Interpreter::Gfxs2dexBg1cyc(F3DuObjBg* bg) {
    uintptr_t data = (uintptr_t)bg->b.imagePtr;

    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    if ((bool)gfx_check_image_signature((char*)data)) {
        std::shared_ptr<Fast::Texture> tex = std::static_pointer_cast<Fast::Texture>(
            Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess((char*)data));
        texFlags = tex->Flags;
        rawTexMetadata.width = tex->Width;
        rawTexMetadata.height = tex->Height;
        rawTexMetadata.h_byte_scale = tex->HByteScale;
        rawTexMetadata.v_pixel_scale = tex->VPixelScale;
        rawTexMetadata.type = tex->Type;
        rawTexMetadata.resource = tex;
        data = (uintptr_t) reinterpret_cast<char*>(tex->ImageData);
    }

    // TODO: Implement bg scaling correctly
    s16 uls = bg->b.imageX >> 2;
    s16 lrs = bg->b.imageW >> 2;

    s16 dsdxRect = 1 << 10;
    s16 ulsRect = bg->b.imageX << 3;
    // Flip flag only flips horizontally
    if (bg->b.imageFlip == G_BG_FLAG_FLIPS) {
        dsdxRect = -dsdxRect;
        ulsRect = (bg->b.imageW - bg->b.imageX) << 3;
    }

    GfxDpSetTextureImage(bg->b.imageFmt, bg->b.imageSiz, bg->b.imageW >> 2, nullptr, texFlags, rawTexMetadata,
                         (void*)data);
    GfxDpSetTile(bg->b.imageFmt, bg->b.imageSiz, 0, 0, G_TX_LOADTILE, 0, 0, 0, 0, 0, 0, 0);
    GfxDpLoadBlock(G_TX_LOADTILE, 0, 0, (bg->b.imageW * bg->b.imageH >> 4) - 1, 0);
    GfxDpSetTile(bg->b.imageFmt, bg->b.imageSiz, (((lrs - uls) * bg->b.imageSiz) + 7) >> 3, 0, G_TX_RENDERTILE,
                 bg->b.imagePal, 0, 0, 0, 0, 0, 0);
    GfxDpSetTileSize(G_TX_RENDERTILE, 0, 0, bg->b.imageW, bg->b.imageH);

    GfxDpTextureRectangle(bg->b.frameX, bg->b.frameY, bg->b.frameW, bg->b.frameH, G_TX_RENDERTILE, ulsRect,
                          bg->b.imageY << 3, dsdxRect, 1 << 10, false);
}

void Interpreter::Gfxs2dexRecyCopy(F3DuObjSprite* spr) {
    s16 dsdx = 4 << 10;
     s16 uls = spr->s.objX << 3;
    // Flip flag only flips horizontally
    if (spr->s.imageFlags == G_BG_FLAG_FLIPS) {
        dsdx = -dsdx;
        uls = (spr->s.imageW - spr->s.objX) << 3;
    }

    int realX = spr->s.objX >> 2;
    int realY = spr->s.objY >> 2;
    int realW = (((spr->s.imageW)) >> 5);
    int realH = (((spr->s.imageH)) >> 5);
    float realSW = spr->s.scaleW / 1024.0f;
    float realSH = spr->s.scaleH / 1024.0f;

    int testX = (realX + (realW / realSW));
    int testY = (realY + (realH / realSH));

    GfxDpTextureRectangle(realX << 2, realY << 2, testX << 2, testY << 2, G_TX_RENDERTILE,
                          (s32)mRdp->texture_tile[0].uls << 3, (s32)mRdp->texture_tile[0].ult << 3,
                          (float)(1 << 10) * realSW, (float)(1 << 10) * realSH, false);
}

void* Interpreter::SegAddr(uintptr_t w1) {
    // Segmented?
    if (w1 & 1) {
        uint32_t segNum = (uint32_t)(w1 >> 24);

        uint32_t offset = w1 & 0x00FFFFFE;

        if (mSegmentPointers[segNum] != 0) {
            return (void*)(mSegmentPointers[segNum] + offset);
        } else {
            return (void*)w1;
        }
    } else {
        return (void*)w1;
    }
}

#define C0(pos, width) ((cmd->words.w0 >> (pos)) & ((1U << width) - 1))
#define C1(pos, width) ((cmd->words.w1 >> (pos)) & ((1U << width) - 1))

void GfxExecStack::start(F3DGfx* dlist) {
    while (!cmd_stack.empty())
        cmd_stack.pop();
    gfx_path.clear();
    cmd_stack.push(dlist);
    disp_stack.clear();
}

void GfxExecStack::stop() {
    while (!cmd_stack.empty())
        cmd_stack.pop();
    gfx_path.clear();
}

F3DGfx*& GfxExecStack::currCmd() {
    return cmd_stack.top();
}

void GfxExecStack::openDisp(const char* file, int line) {
    CodeDisp entry = { file, line };
    disp_stack.push_back(entry);
}
void GfxExecStack::closeDisp() {
    disp_stack.pop_back();
}
const std::vector<GfxExecStack::CodeDisp>& GfxExecStack::getDisp() const {
    return disp_stack;
}

void GfxExecStack::branch(F3DGfx* caller) {
    F3DGfx* old = cmd_stack.top();
    cmd_stack.pop();
    cmd_stack.push(nullptr);
    cmd_stack.push(old);

    gfx_path.push_back(caller);
}

void GfxExecStack::call(F3DGfx* caller, F3DGfx* callee) {
    cmd_stack.push(callee);
    gfx_path.push_back(caller);
}

F3DGfx* GfxExecStack::ret() {
    F3DGfx* cmd = cmd_stack.top();

    cmd_stack.pop();
    if (!gfx_path.empty()) {
        gfx_path.pop_back();
    }

    while (cmd_stack.size() > 0 && cmd_stack.top() == nullptr) {
        cmd_stack.pop();
        if (!gfx_path.empty()) {
            gfx_path.pop_back();
        }
    }
    return cmd;
}

void gfx_set_framebuffer(int fb, float noise_scale);
void gfx_reset_framebuffer();
void gfx_copy_framebuffer(int fb_dst_id, int fb_src_id, bool copyOnce, bool* hasCopiedPtr);

// The main type of the handler function. These function will take a pointer to a pointer to a Gfx. It needs to be a
// double pointer because we sometimes need to increment and decrement the underlying pointer Returns false if the
// current opcode should be incremented after the handler ends.
typedef bool (*GfxOpcodeHandlerFunc)(F3DGfx** gfx);

bool gfx_load_ucode_handler_f3dex2(F3DGfx** cmd) {
    StreamEntryCounts::Handler(0);
    Interpreter* gfx = XboxDispatchInterpreter();
    CampaignDeferredState::snapshot.Invalidate(); gfx->mRsp->fog_mul = 0;
    gfx->mRsp->fog_offset = 0;
    return false;
}

bool gfx_cull_dl_handler_f3dex2(F3DGfx** cmd) {
    StreamEntryCounts::Handler(1);
    // TODO:
    return false;
}

bool gfx_marker_handler_otr(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(2);
    Interpreter* gfx = XboxDispatchInterpreter();
    (*cmd0)++;
    F3DGfx* cmd = (*cmd0);
    gfx->mMarkerOn = true;
    return false;
}

bool gfx_invalidate_tex_cache_handler_f3dex2(F3DGfx** cmd) {
    StreamEntryCounts::Handler(3);
    Interpreter* gfx = XboxDispatchInterpreter();
    const uintptr_t texAddr = (*cmd)->words.w1;

    if (texAddr == 0) {
        gfx->TextureCacheClear();
    } else {
        gfx->TextureCacheDelete((const uint8_t*)texAddr);
    }
    return false;
}

bool gfx_noop_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(4);
    F3DGfx* cmd = *cmd0;
    const char* filename = (const char*)(cmd)->words.w1;
    uint32_t p = C0(16, 8);
    uint32_t l = C0(0, 16);
    if (p == 7) {
        g_exec_stack.openDisp(filename, l);
    } else if (p == 8) {
        if (g_exec_stack.disp_stack.size() == 0) {
            SPDLOG_WARN("CLOSE_DISPS without matching open {}:{}", p, l);
        } else {
            g_exec_stack.closeDisp();
        }
    }
    return false;
}

bool gfx_mtx_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(5);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    uintptr_t mtxAddr = cmd->words.w1;

    gfx->GfxSpMatrix(C0(0, 8) ^ F3DEX2_G_MTX_PUSH, (const int32_t*)gfx->SegAddr(mtxAddr));
    return false;
}
// Seems to be the same for all other non F3DEX2 microcodes...
bool gfx_mtx_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(6);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    uintptr_t mtxAddr = cmd->words.w1;

    gfx->GfxSpMatrix(C0(16, 8), (const int32_t*)gfx->SegAddr(cmd->words.w1));
    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_mtx_otr_filepath_handler_custom_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(7);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    const char* fileName = (const char*)cmd->words.w1;
    const int32_t* mtx = (const int32_t*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(
        (const char*)fileName);

    if (mtx != NULL) {
        gfx->GfxSpMatrix(C0(0, 8) ^ F3DEX2_G_MTX_PUSH, mtx);
    }

    return false;
}

bool gfx_mtx_otr_filepath_handler_custom_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(8);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_mtx_otr_filepath_handler_custom_f3dex2(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    const char* fileName = (const char*)cmd->words.w1;
    const int32_t* mtx = (const int32_t*)UpdateStreamResource(
        (const char*)fileName);

    if (mtx != NULL) {
        gfx->GfxSpMatrix(C0(0, 8) ^ F3DEX2_G_MTX_PUSH, mtx);
    }

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_mtx_otr_filepath_handler_custom_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(9);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    const char* fileName = (const char*)cmd->words.w1;
    const int32_t* mtx = (const int32_t*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(
        (const char*)fileName);

    if (mtx != NULL) {
        gfx->GfxSpMatrix(C0(16, 8), mtx);
    }

    return false;
}

bool gfx_mtx_otr_filepath_handler_custom_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(10);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_mtx_otr_filepath_handler_custom_f3d(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    const char* fileName = (const char*)cmd->words.w1;
    const int32_t* mtx = (const int32_t*)UpdateStreamResource(
        (const char*)fileName);

    if (mtx != NULL) {
        gfx->GfxSpMatrix(C0(16, 8), mtx);
    }

    return false;
}

bool gfx_mtx_otr_filepath_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(11);
    if (ucode_handler_index == ucode_f3dex2) {
        return gfx_mtx_otr_filepath_handler_custom_f3dex2(cmd0);
    } else {
        return gfx_mtx_otr_filepath_handler_custom_f3d(cmd0);
    }
}

static __declspec(noinline) bool CampaignOriginal_gfx_mtx_otr_handler_custom_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(12);
    (*cmd0)++;
    F3DGfx* cmd = *cmd0;

    const uint64_t hash = ((uint64_t)cmd->words.w0 << 32) + cmd->words.w1;
    const int32_t* mtx =
        (const int32_t*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);

    if (mtx != NULL) {
        Interpreter* gfx = XboxDispatchInterpreter();
        cmd--;
        gfx->GfxSpMatrix(C0(0, 8) ^ F3DEX2_G_MTX_PUSH, mtx);
        cmd++;
    }

    return false;
}

bool gfx_mtx_otr_handler_custom_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(13);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_mtx_otr_handler_custom_f3dex2(cmd0);
    (*cmd0)++;
    F3DGfx* cmd = *cmd0;

    const uint64_t hash = ((uint64_t)cmd->words.w0 << 32) + cmd->words.w1;
    const int32_t* mtx =
        (const int32_t*)UpdateStreamResource(hash);

    if (mtx != NULL) {
        Interpreter* gfx = XboxDispatchInterpreter();
        cmd--;
        gfx->GfxSpMatrix(C0(0, 8) ^ F3DEX2_G_MTX_PUSH, mtx);
        cmd++;
    }

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_mtx_otr_handler_custom_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(14);
    Interpreter* gfx = XboxDispatchInterpreter();
    (*cmd0)++;
    F3DGfx* cmd = *cmd0;

    const uint64_t hash = ((uint64_t)cmd->words.w0 << 32) + cmd->words.w1;
    const int32_t* mtx =
        (const int32_t*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);
    if (mtx != nullptr) {
        cmd--;
        gfx->GfxSpMatrix(C0(16, 8), mtx);
        cmd++;
    }
    return false;
}

bool gfx_mtx_otr_handler_custom_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(15);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_mtx_otr_handler_custom_f3d(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    (*cmd0)++;
    F3DGfx* cmd = *cmd0;

    const uint64_t hash = ((uint64_t)cmd->words.w0 << 32) + cmd->words.w1;
    const int32_t* mtx =
        (const int32_t*)UpdateStreamResource(hash);
    if (mtx != nullptr) {
        cmd--;
        gfx->GfxSpMatrix(C0(16, 8), mtx);
        cmd++;
    }
    return false;
}

bool gfx_mtx_otr_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(16);
    if (ucode_handler_index == ucode_f3dex2) {
        return gfx_mtx_otr_handler_custom_f3dex2(cmd0);
    } else {
        return gfx_mtx_otr_handler_custom_f3d(cmd0);
    }
}

bool gfx_pop_mtx_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(17);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpPopMatrix((uint32_t)(cmd->words.w1 / 64));

    return false;
}

bool gfx_pop_mtx_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(18);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpPopMatrix(1);

    return false;
}

bool gfx_movemem_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(19);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpMovememF3dex2(C0(0, 8), C0(8, 8) * 8, gfx->SegAddr(cmd->words.w1));

    return false;
}

bool gfx_movemem_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(20);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpMovememF3d(C0(16, 8), 0, gfx->SegAddr(cmd->words.w1));

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_movemem_handler_otr(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(21);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    const uint8_t index = C1(24, 8);
    const uint8_t offset = C1(16, 8);
    const uint8_t hasOffset = C1(8, 8);

    (*cmd0)++;

    const uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

    if (ucode_handler_index == ucode_f3dex2) {
        gfx->GfxSpMovememF3dex2(index, offset,
                                Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash));
    } else {
        auto light = (Fast::LightEntry*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);
        uintptr_t data = (uintptr_t)&light->Ambient;
        gfx->GfxSpMovememF3d(index, offset, (void*)(data + (hasOffset == 1 ? 0x8 : 0)));
    }
    return false;
}

bool gfx_movemem_handler_otr(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(22);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_movemem_handler_otr(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    const uint8_t index = C1(24, 8);
    const uint8_t offset = C1(16, 8);
    const uint8_t hasOffset = C1(8, 8);

    (*cmd0)++;

    const uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

    if (ucode_handler_index == ucode_f3dex2) {
        gfx->GfxSpMovememF3dex2(index, offset,
                                UpdateStreamResource(hash));
    } else {
        auto light = (Fast::LightEntry*)UpdateStreamResource(hash);
        uintptr_t data = (uintptr_t)&light->Ambient;
        gfx->GfxSpMovememF3d(index, offset, (void*)(data + (hasOffset == 1 ? 0x8 : 0)));
    }
    return false;
}

int16_t Interpreter::CreateShader(const std::string& path) {
    auto shader = XboxRunArchiveManager()->LoadFile(path);
    if (shader == nullptr || !shader->IsLoaded) {
        return -1;
    }
    shader_ids.push_back(std::string(shader->Buffer->data()));
    return shader_ids.size() - 1;
}

bool gfx_set_shader_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(23);
    Interpreter* gfx = XboxDispatchInterpreter();

    F3DGfx* cmd = *cmd0;
    char* file = (char*)cmd->words.w1;

    if (file == nullptr) {
        { ShaderMod shipyardAggregate = ShaderMod( 0, 0, false ); gfx->mRsp->current_shader = shipyardAggregate; }
        return false;
    }

    const auto path = std::string(file);
    const auto shaderId = gfx->CreateShader(path);
    { ShaderMod shipyardAggregate = ShaderMod( true, shaderId, (uint8_t)C0(16, 1) ); gfx->mRdp->current_shader = shipyardAggregate; }
    return false;
}

bool gfx_moveword_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(24);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpMovewordF3dex2(C0(16, 8), C0(0, 16), cmd->words.w1);

    return false;
}

bool gfx_moveword_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(25);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpMovewordF3d(C0(0, 8), C0(8, 16), cmd->words.w1);

    return false;
}

bool gfx_texture_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(26);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTexture(C1(16, 16), C1(0, 16), C0(11, 3), C0(8, 3), C0(1, 7));

    return false;
}

// Seems to be the same for all other non F3DEX2 microcodes...
bool gfx_texture_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(27);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTexture(C1(16, 16), C1(0, 16), C0(11, 3), C0(8, 3), C0(0, 8));

    return false;
}

// Almost all versions of the microcode have their own version of this opcode
bool gfx_vtx_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(28);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), (const F3DVtx*)gfx->SegAddr(cmd->words.w1));

    return false;
}

bool gfx_vtx_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(29);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    gfx->GfxSpVertex(C0(10, 6), C0(17, 7), (const F3DVtx*)gfx->SegAddr(cmd->words.w1));

    return false;
}

bool gfx_vtx_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(30);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpVertex((C0(0, 16)) / sizeof(F3DVtx), C0(16, 4), (const F3DVtx*)gfx->SegAddr(cmd->words.w1));

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_vtx_hash_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(31);
    Interpreter* gfx = XboxDispatchInterpreter();
    ModernFrameProfile::VtxHashSample sample;
    ModernFrameProfile::BeginVtxHash(sample);
    struct ProfileScope {
        ModernFrameProfile::VtxHashSample* previous;
        ModernFrameProfile::VtxHashSample& sample;
        explicit ProfileScope(ModernFrameProfile::VtxHashSample& value)
            : previous(NULL), sample(value) {
            if (sample.sampled) {
                previous = sModernVtxHashSample;
                sModernVtxHashSample = &sample;
            }
        }
        ~ProfileScope() {
            if (sample.sampled) sModernVtxHashSample = previous;
            ModernFrameProfile::EndVtxHash(sample);
        }
    } profileScope(sample);
    // Offset added to the start of the vertices
    const uintptr_t offset = (*cmd0)->words.w1;
    // This is a two-part display list command, so increment the instruction pointer so we can get the CRC64
    // hash from the second
    (*cmd0)++;
    const uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

    // We need to know if the offset is a cached pointer or not. An offset greater than one million is not a
    // real offset, so it must be a real pointer
    if (offset > 0xFFFFF) {
        if (sample.sampled) sample.route = ModernFrameProfile::VtxHashPointer;
        (*cmd0)--;
        F3DGfx* cmd = *cmd0;
        gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), (F3DVtx*)offset);
        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);
        (*cmd0)++;
    } else {
        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashLookup);
        F3DVtx* vtx = (F3DVtx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);
        if (sample.sampled) sample.route = vtx ? ModernFrameProfile::VtxHashResolved : ModernFrameProfile::VtxHashMissing;

        if (vtx != NULL) {
            vtx = (F3DVtx*)((char*)vtx + offset);

            (*cmd0)--;
            F3DGfx* cmd = *cmd0;

            // TODO: WTF??
            cmd->words.w1 = (uintptr_t)vtx;

            gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), vtx);
            ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);
            (*cmd0)++;
        }
    }
    return false;
}

bool gfx_vtx_hash_handler_custom(F3DGfx** cmd0) {
    LaneWork::Add(LaneWork::ResourceResolve);
    StreamEntryCounts::Handler(32);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_vtx_hash_handler_custom(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    ModernFrameProfile::VtxHashSample sample;
    ModernFrameProfile::BeginVtxHash(sample);
    struct ProfileScope {
        ModernFrameProfile::VtxHashSample* previous;
        ModernFrameProfile::VtxHashSample& sample;
        explicit ProfileScope(ModernFrameProfile::VtxHashSample& value)
            : previous(NULL), sample(value) {
            if (sample.sampled) {
                previous = sModernVtxHashSample;
                sModernVtxHashSample = &sample;
            }
        }
        ~ProfileScope() {
            if (sample.sampled) sModernVtxHashSample = previous;
            ModernFrameProfile::EndVtxHash(sample);
        }
    } profileScope(sample);
    // Offset added to the start of the vertices
    const uintptr_t offset = (*cmd0)->words.w1;
    // This is a two-part display list command, so increment the instruction pointer so we can get the CRC64
    // hash from the second
    (*cmd0)++;
    const uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

    // We need to know if the offset is a cached pointer or not. An offset greater than one million is not a
    // real offset, so it must be a real pointer
    if (offset > 0xFFFFF) {
        if (sample.sampled) sample.route = ModernFrameProfile::VtxHashPointer;
        (*cmd0)--;
        F3DGfx* cmd = *cmd0;
        gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), (F3DVtx*)offset);
        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);
        (*cmd0)++;
    } else {
        ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashLookup);
        F3DVtx* vtx = (F3DVtx*)UpdateStreamResource(hash);
        if (sample.sampled) sample.route = vtx ? ModernFrameProfile::VtxHashResolved : ModernFrameProfile::VtxHashMissing;

        if (vtx != NULL) {
            vtx = (F3DVtx*)((char*)vtx + offset);

            (*cmd0)--;
            F3DGfx* cmd = *cmd0;

            // TODO: WTF??
            cmd->words.w1 = (uintptr_t)vtx;

            gfx->GfxSpVertex(C0(12, 8), C0(1, 7) - C0(12, 8), vtx);
            ModernFrameProfile::AdvanceVtxHash(sample, ModernFrameProfile::VtxHashFinish);
            (*cmd0)++;
        }
    }
    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_vtx_otr_filepath_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(33);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    char* fileName = (char*)cmd->words.w1;
    (*cmd0)++;
    cmd = *cmd0;
    size_t vtxCnt = cmd->words.w0;
    size_t vtxIdxOff = cmd->words.w1 >> 16;
    size_t vtxDataOff = cmd->words.w1 & 0xFFFF;
    F3DVtx* vtx =
        (F3DVtx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer((const char*)fileName);
    vtx += vtxDataOff;

    gfx->GfxSpVertex(vtxCnt, vtxIdxOff, vtx);
    return false;
}

bool gfx_vtx_otr_filepath_handler_custom(F3DGfx** cmd0) {
    LaneWork::Add(LaneWork::ResourceResolve);
    StreamEntryCounts::Handler(34);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_vtx_otr_filepath_handler_custom(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    char* fileName = (char*)cmd->words.w1;
    (*cmd0)++;
    cmd = *cmd0;
    size_t vtxCnt = cmd->words.w0;
    size_t vtxIdxOff = cmd->words.w1 >> 16;
    size_t vtxDataOff = cmd->words.w1 & 0xFFFF;
    F3DVtx* vtx =
        (F3DVtx*)UpdateStreamResource((const char*)fileName);
    vtx += vtxDataOff;

    gfx->GfxSpVertex(vtxCnt, vtxIdxOff, vtx);
    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_dl_otr_filepath_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(35);
    F3DGfx* cmd = *cmd0;
    char* fileName = (char*)cmd->words.w1;
    F3DGfx* nDL =
        (F3DGfx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer((const char*)fileName);

    if (C0(16, 1) == 0 && nDL != nullptr) {
        g_exec_stack.call(*cmd0, nDL);
    } else {
        if (nDL != nullptr) {
            (*cmd0) = nDL;
            g_exec_stack.branch(cmd);
            return true; // shortcut cmd increment
        } else {
            assert(0 && "???");
            // gfx_path.pop_back();
            // cmd = cmd_stack.top();
            // cmd_stack.pop();
        }
    }
    return false;
}

bool gfx_dl_otr_filepath_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(36);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_dl_otr_filepath_handler_custom(cmd0);
    F3DGfx* cmd = *cmd0;
    char* fileName = (char*)cmd->words.w1;
    F3DGfx* nDL =
        (F3DGfx*)UpdateStreamResource((const char*)fileName);

    if (C0(16, 1) == 0 && nDL != nullptr) {
        g_exec_stack.call(*cmd0, nDL);
    } else {
        if (nDL != nullptr) {
            (*cmd0) = nDL;
            g_exec_stack.branch(cmd);
            return true; // shortcut cmd increment
        } else {
            assert(0 && "???");
            // gfx_path.pop_back();
            // cmd = cmd_stack.top();
            // cmd_stack.pop();
        }
    }
    return false;
}

// The original F3D microcode doesn't seem to have this opcode. Glide handles it as part of moveword
bool gfx_modify_vtx_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(37);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    gfx->GfxSpModifyVertex(C0(1, 15), C0(16, 8), (uint32_t)cmd->words.w1);
    return false;
}

// F3D, F3DEX, and F3DEX2 do the same thing but F3DEX2 has its own opcode number
bool gfx_dl_handler_common(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(38);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    F3DGfx* subGFX = (F3DGfx*)gfx->SegAddr(cmd->words.w1);
    if (C0(16, 1) == 0) {
        // Push return address
        if (subGFX != nullptr) {
            g_exec_stack.call(*cmd0, subGFX);
        }
    } else {
        (*cmd0) = subGFX;
        g_exec_stack.branch(cmd);
        return true; // shortcut cmd increment
    }
    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_dl_otr_hash_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(39);
    F3DGfx* cmd = *cmd0;
    if (C0(16, 1) == 0) {
        // Push return address
        (*cmd0)++;

        uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

        F3DGfx* gfx = (F3DGfx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);

        if (gfx != 0) {
            g_exec_stack.call(cmd, gfx);
        }
    } else {
        Interpreter* gfx = XboxDispatchInterpreter();
        assert(0 && "????");
        (*cmd0) = (F3DGfx*)gfx->SegAddr((*cmd0)->words.w1);
        return true;
    }
    return false;
}

bool gfx_dl_otr_hash_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(40);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_dl_otr_hash_handler_custom(cmd0);
    F3DGfx* cmd = *cmd0;
    if (C0(16, 1) == 0) {
        // Push return address
        (*cmd0)++;

        uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

        F3DGfx* gfx = (F3DGfx*)UpdateStreamResource(hash);

        if (gfx != 0) {
            g_exec_stack.call(cmd, gfx);
        }
    } else {
        Interpreter* gfx = XboxDispatchInterpreter();
        assert(0 && "????");
        (*cmd0) = (F3DGfx*)gfx->SegAddr((*cmd0)->words.w1);
        return true;
    }
    return false;
}
bool gfx_dl_index_handler(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(41);
    // Compute seg addr by converting an index value to a offset value
    // handling 32 vs 64 bit size differences for Gfx
    // adding 1 to trigger the segaddr flow
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = (*cmd0);
    uint8_t segNum = (uint8_t)(cmd->words.w1 >> 24);
    uint32_t index = (uint32_t)(cmd->words.w1 & 0x00FFFFFF);
    uintptr_t segAddr = (segNum << 24) | (index * sizeof(F3DGfx)) + 1;

    F3DGfx* subGFX = (F3DGfx*)gfx->SegAddr(segAddr);
    if (C0(16, 1) == 0) {
        // Push return address
        if (subGFX != nullptr) {
            g_exec_stack.call((*cmd0), subGFX);
        }
    } else {
        (*cmd0) = subGFX;
        g_exec_stack.branch(cmd);
        return true; // shortcut cmd increment
    }
    return false;
}

// TODO handle special OTR opcodes later...
bool gfx_pushcd_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(42);
    gfx_push_current_dir((char*)(*cmd0)->words.w1);
    return false;
}

// TODO handle special OTR opcodes later...
static __declspec(noinline) bool CampaignOriginal_gfx_branch_z_otr_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(43);
    if(UpdateStream::packet.active)UpdateStream::packet.conditional=true;
    // Push return address
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = (*cmd0);

    uint8_t vbidx = (uint8_t)((*cmd0)->words.w0 & 0x00000FFF);
    uint32_t zval = (uint32_t)((*cmd0)->words.w1);

    (*cmd0)++;

    if (gfx->mRsp->loaded_vertices[vbidx].z <= zval ||
        (gfx->mRsp->extra_geometry_mode & G_EX_ALWAYS_EXECUTE_BRANCH) != 0) {
        uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

        F3DGfx* gfx = (F3DGfx*)Ship::Context::GetInstance()->GetResourceManager()->GetResourceRawPointer(hash);

        if (gfx != 0) {
            (*cmd0) = gfx;
            g_exec_stack.branch(cmd);
            return true; // shortcut cmd increment
        }
    }
    return false;
}

bool gfx_branch_z_otr_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(44);
    if(UpdateStream::packet.active)UpdateStream::packet.conditional=true;
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_branch_z_otr_handler_f3dex2(cmd0);
    // Push return address
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = (*cmd0);

    uint8_t vbidx = (uint8_t)((*cmd0)->words.w0 & 0x00000FFF);
    uint32_t zval = (uint32_t)((*cmd0)->words.w1);

    (*cmd0)++;

    if (gfx->mRsp->loaded_vertices[vbidx].z <= zval ||
        (gfx->mRsp->extra_geometry_mode & G_EX_ALWAYS_EXECUTE_BRANCH) != 0) {
        uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (*cmd0)->words.w1;

        F3DGfx* gfx = (F3DGfx*)UpdateStreamResource(hash);

        if (gfx != 0) {
            (*cmd0) = gfx;
            g_exec_stack.branch(cmd);
            return true; // shortcut cmd increment
        }
    }
    return false;
}

// F3D, F3DEX, and F3DEX2 do the same thing but F3DEX2 has its own opcode number
bool gfx_end_dl_handler_common(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(45);
    Interpreter* gfx = XboxDispatchInterpreter();
    gfx->mMarkerOn = false;
    *cmd0 = g_exec_stack.ret();
    return true;
}

bool gfx_set_prim_depth_handler_rdp(F3DGfx** cmd) {
    StreamEntryCounts::Handler(46);
    // TODO Implement this command...
    return false;
}

// Only on F3DEX2
bool gfx_geometry_mode_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(47);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpGeometryMode(~C0(0, 24), (uint32_t)cmd->words.w1);
    return false;
}

// Only on F3DEX and older
bool gfx_set_geometry_mode_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(48);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpGeometryMode(0, (uint32_t)cmd->words.w1);
    return false;
}

// Only on F3DEX and older
bool gfx_clear_geometry_mode_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(49);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpGeometryMode((uint32_t)cmd->words.w1, 0);
    return false;
}

bool gfx_tri1_otr_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(50);
    Interpreter* gfx = XboxDispatchInterpreter();

    F3DGfx* cmd = *cmd0;
    uint8_t v00 = (uint8_t)(cmd->words.w0 & 0x0000FFFF);
    uint8_t v01 = (uint8_t)(cmd->words.w1 >> 16);
    uint8_t v02 = (uint8_t)(cmd->words.w1 & 0x0000FFFF);
    gfx->GfxSpTri1(v00, v01, v02, false);

    return false;
}

bool gfx_tri1_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(51);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTri1(C0(16, 8) / 2, C0(8, 8) / 2, C0(0, 8) / 2, false);

    return false;
}

bool gfx_tri1_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(52);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);

    return false;
}

bool gfx_tri1_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(53);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTri1(C1(16, 8) / 10, C1(8, 8) / 10, C1(0, 8) / 10, false);

    return false;
}

// F3DEX, and F3DEX2 share a tri2 function, however F3DEX has a different quad function.
bool gfx_tri2_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(54);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    // MODERN TRI2 PAIR CERTIFICATE BEGIN
    struct PairScope {
        Interpreter* owner;
        ModernFrameProfile::Tri2Sample sample;
        ModernFrameProfile::Tri2Sample* previous;
        explicit PairScope(Interpreter* p) : owner(p) {
            // MODERN TRI2 PHASE PROFILE BEGIN
            previous = sModernTri2Sample;
            ModernFrameProfile::BeginTri2(sample);
            sModernTri2Sample = sample.sampled ? &sample : NULL;
            owner->mXboxTrianglePairActive = true;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
        ~PairScope() {
            ModernFrameProfile::EndTri2(sample);
            sModernTri2Sample = previous;
            // MODERN TRI2 PHASE PROFILE END
            owner->mXboxTrianglePairActive = false;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
    } scope(gfx);
    // MODERN TRI2 PAIR CERTIFICATE END

    gfx->GfxSpTri1(C0(17, 7), C0(9, 7), C0(1, 7), false);
    gfx->GfxSpTri1(C1(17, 7), C1(9, 7), C1(1, 7), false);
    return false;
}

static void ExecutePreparedTriPair(Interpreter* gfx,unsigned first,unsigned second) {
    // MODERN TRI2 PAIR CERTIFICATE BEGIN
    struct PairScope {
        Interpreter* owner;
        ModernFrameProfile::Tri2Sample sample;
        ModernFrameProfile::Tri2Sample* previous;
        explicit PairScope(Interpreter* p) : owner(p) {
            // MODERN TRI2 PHASE PROFILE BEGIN
            previous = sModernTri2Sample;
            ModernFrameProfile::BeginTri2(sample);
            sModernTri2Sample = sample.sampled ? &sample : NULL;
            owner->mXboxTrianglePairActive = true;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
        ~PairScope() {
            ModernFrameProfile::EndTri2(sample);
            sModernTri2Sample = previous;
            // MODERN TRI2 PHASE PROFILE END
            owner->mXboxTrianglePairActive = false;
            owner->mXboxTrianglePairPrepared = false;
            owner->mXboxPairPacked.Reset();
        }
    } scope(gfx);
    // MODERN TRI2 PAIR CERTIFICATE END

    gfx->GfxSpTri1(((first >> 16) & 255), ((first >> 8) & 255), ((first >> 0) & 255), false);
    gfx->GfxSpTri1(((second >> 16) & 255), ((second >> 8) & 255), ((second >> 0) & 255), false);

}

bool gfx_quad_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(55);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTri1(C0(16, 8) / 2, C0(8, 8) / 2, C0(0, 8) / 2, false);
    gfx->GfxSpTri1(C1(16, 8) / 2, C1(8, 8) / 2, C1(0, 8) / 2, false);
    return false;
}

bool gfx_quad_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(56);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpTri1(C1(16, 8) / 2, C1(8, 8) / 2, C1(0, 8) / 2, false);
    gfx->GfxSpTri1(C1(16, 8) / 2, C1(0, 8) / 2, C1(24, 8) / 2, false);
    return false;
}

bool gfx_othermode_l_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(57);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpSetOtherMode(31 - C0(8, 8) - C0(0, 8), C0(0, 8) + 1, cmd->words.w1);

    return false;
}

bool gfx_othermode_l_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(58);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpSetOtherMode(C0(8, 8), C0(0, 8), cmd->words.w1);

    return false;
}

bool gfx_othermode_h_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(59);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpSetOtherMode(63 - C0(8, 8) - C0(0, 8), C0(0, 8) + 1, (uint64_t)cmd->words.w1 << 32);

    return false;
}

// Only on F3DEX and older
bool gfx_set_geometry_mode_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(60);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpGeometryMode(0, (uint32_t)cmd->words.w1);
    return false;
}

// Only on F3DEX and older
bool gfx_clear_geometry_mode_handler_f3dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(61);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpGeometryMode((uint32_t)cmd->words.w1, 0);
    return false;
}

bool gfx_othermode_h_handler_f3d(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(62);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxSpSetOtherMode(C0(8, 8) + 32, C0(0, 8), (uint64_t)cmd->words.w1 << 32);

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_set_timg_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(63);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    uintptr_t i = (uintptr_t)gfx->SegAddr(cmd->words.w1);

    char* imgData = (char*)i;
    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetdata;

    if ((i & 1) != 1) {
        if (gfx_check_image_signature(imgData) == 1) {
            const auto resourceManager = Ship::Context::GetInstance()->GetResourceManager();
            const uint64_t cacheKey = static_cast<uint64_t>(reinterpret_cast<uintptr_t>(imgData));
            const unsigned lookupGeneration = resourceManager->GetXboxLookupGeneration();
            std::shared_ptr<Fast::Texture> tex =
                gfx->mXboxTextureHashCache.Lookup(cacheKey, imgData, lookupGeneration);
            if (ModernFrameProfile::CaptureResourceLookups())
                ModernFrameProfile::ObserveTexturePathCache(tex != nullptr);
            if (!tex) {
                tex = std::static_pointer_cast<Fast::Texture>(
                    resourceManager->LoadResourceProcess(imgData));
                if (tex && !tex->IsDirty() &&
                    resourceManager->GetXboxLookupGeneration() == lookupGeneration)
                    gfx->mXboxTextureHashCache.Store(cacheKey, imgData, lookupGeneration, tex);
            }

            if (tex == nullptr) {
                (*cmd0)++;
                return false;
            }

            i = (uintptr_t) reinterpret_cast<char*>(tex->ImageData);
            texFlags = tex->Flags;
            rawTexMetdata.width = tex->Width;
            rawTexMetdata.height = tex->Height;
            rawTexMetdata.h_byte_scale = tex->HByteScale;
            rawTexMetdata.v_pixel_scale = tex->VPixelScale;
            rawTexMetdata.type = tex->Type;
            rawTexMetdata.resource = tex;
        }
    }

    gfx->GfxDpSetTextureImage(C0(21, 3), C0(19, 2), C0(0, 12) + 1, imgData, texFlags, rawTexMetdata, (void*)i);

    return false;
}

bool gfx_set_timg_handler_rdp(F3DGfx** cmd0) {
    LaneWork::Add(LaneWork::TextureMetadata);
    StreamEntryCounts::Handler(64);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_set_timg_handler_rdp(cmd0);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    uintptr_t i = (uintptr_t)gfx->SegAddr(cmd->words.w1);

    char* imgData = (char*)i;
    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetdata;

    if ((i & 1) != 1) {
        if (gfx_check_image_signature(imgData) == 1) {
            const auto resourceManager = XboxRunResourceManager();
            const uint64_t cacheKey = static_cast<uint64_t>(reinterpret_cast<uintptr_t>(imgData));
            const unsigned lookupGeneration = resourceManager->GetXboxLookupGeneration();
            std::shared_ptr<Fast::Texture> tex =
                gfx->mXboxTextureHashCache.Lookup(cacheKey, imgData, lookupGeneration);
            if (ModernFrameProfile::CaptureResourceLookups())
                ModernFrameProfile::ObserveTexturePathCache(tex != nullptr);
            if (!tex) {
                tex = std::static_pointer_cast<Fast::Texture>(
                    resourceManager->LoadResourceProcess(imgData));
                if (tex && !tex->IsDirty() &&
                    resourceManager->GetXboxLookupGeneration() == lookupGeneration)
                    gfx->mXboxTextureHashCache.Store(cacheKey, imgData, lookupGeneration, tex);
            }

            if (tex == nullptr) {
                (*cmd0)++;
                return false;
            }

            i = (uintptr_t) reinterpret_cast<char*>(tex->ImageData);
            texFlags = tex->Flags;
            rawTexMetdata.width = tex->Width;
            rawTexMetdata.height = tex->Height;
            rawTexMetdata.h_byte_scale = tex->HByteScale;
            rawTexMetdata.v_pixel_scale = tex->VPixelScale;
            rawTexMetdata.type = tex->Type;
            rawTexMetdata.resource = tex;
        }
    }

    gfx->GfxDpSetTextureImage(C0(21, 3), C0(19, 2), C0(0, 12) + 1, imgData, texFlags, rawTexMetdata, (void*)i);

    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_set_timg_otr_hash_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(65);
    uintptr_t addr = (*cmd0)->words.w1;
    (*cmd0)++;
    uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (uint64_t)(*cmd0)->words.w1;

    const auto resourceManager = Ship::Context::GetInstance()->GetResourceManager();
    // MODERN TEXTURE HASH PHASE PROFILE
    ModernFrameProfile::TextureHashSample xboxTextureHashSample;
    ModernFrameProfile::BeginTextureHash(xboxTextureHashSample);
    Interpreter* gfx = XboxDispatchInterpreter();
    const auto archiveManager = resourceManager->GetArchiveManager();
    const unsigned hashEpoch = archiveManager->GetXboxHashEpoch();
    const unsigned lookupGeneration = resourceManager->GetXboxLookupGeneration();
    const auto* archiveHit = gfx->mXboxTextureHashCache.LookupArchive(
        hash, archiveManager.get(), hashEpoch, lookupGeneration);
    if (archiveHit && archiveManager->GetXboxHashEpoch() != hashEpoch)
        archiveHit = NULL;
    const char* fileName = archiveHit ? archiveHit->path.c_str() : archiveManager->HashToCString(hash);
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashFinal);
    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    if (fileName == nullptr) {
        ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
        (*cmd0)++;
        return false;
    }
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashOwningCache);

    std::shared_ptr<Fast::Texture> loadedTexture;
    const auto* pathHit = archiveHit;
    if (!pathHit && archiveManager->GetXboxHashEpoch() == hashEpoch)
        pathHit = gfx->mXboxTextureHashCache.LookupAndCertifyArchive(
            hash, fileName, lookupGeneration, archiveManager.get(), hashEpoch);
    const std::shared_ptr<Fast::Texture>* cachedTexture =
        pathHit ? &pathHit->texture : NULL;
    const std::shared_ptr<Fast::Texture>& texture =
        cachedTexture ? *cachedTexture : loadedTexture;
    if (ModernFrameProfile::CaptureResourceLookups())
        ModernFrameProfile::ObserveTextureHashCache(texture != nullptr);
    if (!texture) {
        ModernFrameProfile::AdvanceTextureHash(
            xboxTextureHashSample, ModernFrameProfile::TextureHashLoader);
        loadedTexture = std::static_pointer_cast<Fast::Texture>(
            resourceManager->LoadResourceProcess(fileName));
        if (texture && !texture->IsDirty() &&
            resourceManager->GetXboxLookupGeneration() == lookupGeneration &&
            archiveManager->GetXboxHashEpoch() == hashEpoch &&
            resourceManager->GetArchiveManager().get() == archiveManager.get())
            gfx->mXboxTextureHashCache.StoreArchive(
                hash, fileName, lookupGeneration, archiveManager.get(), hashEpoch, texture);
    }
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashFinal);
    if (texture != nullptr) {
        texFlags = texture->Flags;
        rawTexMetadata.width = texture->Width;
        rawTexMetadata.height = texture->Height;
        rawTexMetadata.h_byte_scale = texture->HByteScale;
        rawTexMetadata.v_pixel_scale = texture->VPixelScale;
        rawTexMetadata.type = texture->Type;
        rawTexMetadata.resource = texture;

        char* tex = reinterpret_cast<char*>(texture->ImageData);

        if (tex != nullptr) {
            (*cmd0)--;
            uintptr_t oldData = (*cmd0)->words.w1;
            // TODO: wtf??
            (*cmd0)->words.w1 = (uintptr_t)tex;

            // if (ourHash != (uint64_t)-1) {
            //     auto res = ResourceLoad(ourHash);
            // }

            (*cmd0)++;
        }

        (*cmd0)--;
        F3DGfx* cmd = (*cmd0);
        uint32_t fmt = C0(21, 3);
        uint32_t size = C0(19, 2);
        uint32_t width = C0(0, 12) + 1;

        if (tex != NULL) {
            gfx->GfxDpSetTextureImage(fmt, size, width, fileName, texFlags, rawTexMetadata, tex);
        }
    } else {
        SPDLOG_ERROR("G_SETTIMG_OTR_HASH: Texture is null");
    }

    (*cmd0)++;
    ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
    return false;
}

bool gfx_set_timg_otr_hash_handler_custom(F3DGfx** cmd0) {
    LaneWork::Add(LaneWork::TextureMetadata);
    LaneWork::Add(LaneWork::ResourceResolve);
    StreamEntryCounts::Handler(66);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_set_timg_otr_hash_handler_custom(cmd0);
    uintptr_t addr = (*cmd0)->words.w1;
    (*cmd0)++;
    uint64_t hash = ((uint64_t)(*cmd0)->words.w0 << 32) + (uint64_t)(*cmd0)->words.w1;

    const auto resourceManager = XboxRunResourceManager();
    // MODERN TEXTURE HASH PHASE PROFILE
    ModernFrameProfile::TextureHashSample xboxTextureHashSample;
    ModernFrameProfile::BeginTextureHash(xboxTextureHashSample);
    Interpreter* gfx = XboxDispatchInterpreter();
    const auto archiveManager = XboxRunArchiveManager();
    const unsigned hashEpoch = archiveManager->GetXboxHashEpoch();
    const unsigned lookupGeneration = resourceManager->GetXboxLookupGeneration();
    const auto* archiveHit = gfx->mXboxTextureHashCache.LookupArchive(
        hash, archiveManager, hashEpoch, lookupGeneration);
    if (archiveHit && archiveManager->GetXboxHashEpoch() != hashEpoch)
        archiveHit = NULL;
    const char* fileName = archiveHit ? archiveHit->path.c_str() : archiveManager->HashToCString(hash);
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashFinal);
    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    if (fileName == nullptr) {
        ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
        (*cmd0)++;
        return false;
    }
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashOwningCache);

    std::shared_ptr<Fast::Texture> loadedTexture;
    const auto* pathHit = archiveHit;
    if (!pathHit && archiveManager->GetXboxHashEpoch() == hashEpoch)
        pathHit = gfx->mXboxTextureHashCache.LookupAndCertifyArchive(
            hash, fileName, lookupGeneration, archiveManager, hashEpoch);
    const std::shared_ptr<Fast::Texture>* cachedTexture =
        pathHit ? &pathHit->texture : NULL;
    const std::shared_ptr<Fast::Texture>& texture =
        cachedTexture ? *cachedTexture : loadedTexture;
    if (ModernFrameProfile::CaptureResourceLookups())
        ModernFrameProfile::ObserveTextureHashCache(texture != nullptr);
    if (!texture) {
        ModernFrameProfile::AdvanceTextureHash(
            xboxTextureHashSample, ModernFrameProfile::TextureHashLoader);
        loadedTexture = std::static_pointer_cast<Fast::Texture>(
            resourceManager->LoadResourceProcess(fileName));
        if (texture && !texture->IsDirty() &&
            resourceManager->GetXboxLookupGeneration() == lookupGeneration &&
            archiveManager->GetXboxHashEpoch() == hashEpoch &&
            XboxRunArchiveManager() == archiveManager)
            gfx->mXboxTextureHashCache.StoreArchive(
                hash, fileName, lookupGeneration, archiveManager, hashEpoch, texture);
    }
    ModernFrameProfile::AdvanceTextureHash(
        xboxTextureHashSample, ModernFrameProfile::TextureHashFinal);
    if (texture != nullptr) {
        texFlags = texture->Flags;
        rawTexMetadata.width = texture->Width;
        rawTexMetadata.height = texture->Height;
        rawTexMetadata.h_byte_scale = texture->HByteScale;
        rawTexMetadata.v_pixel_scale = texture->VPixelScale;
        rawTexMetadata.type = texture->Type;
        rawTexMetadata.resource = texture;

        char* tex = reinterpret_cast<char*>(texture->ImageData);

        if (tex != nullptr) {
            (*cmd0)--;
            uintptr_t oldData = (*cmd0)->words.w1;
            // TODO: wtf??
            (*cmd0)->words.w1 = (uintptr_t)tex;

            // if (ourHash != (uint64_t)-1) {
            //     auto res = ResourceLoad(ourHash);
            // }

            (*cmd0)++;
        }

        (*cmd0)--;
        F3DGfx* cmd = (*cmd0);
        uint32_t fmt = C0(21, 3);
        uint32_t size = C0(19, 2);
        uint32_t width = C0(0, 12) + 1;

        if (tex != NULL) {
            gfx->GfxDpSetTextureImage(fmt, size, width, fileName, texFlags, rawTexMetadata, tex);
        }
    } else {
        SPDLOG_ERROR("G_SETTIMG_OTR_HASH: Texture is null");
    }

    (*cmd0)++;
    ModernFrameProfile::EndTextureHash(xboxTextureHashSample);
    return false;
}

static __declspec(noinline) bool CampaignOriginal_gfx_set_timg_otr_filepath_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(67);
    F3DGfx* cmd = *cmd0;
    const char* fileName = (char*)cmd->words.w1;

    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    std::shared_ptr<Fast::Texture> texture = std::static_pointer_cast<Fast::Texture>(
        Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess(fileName));
    if (texture != nullptr) {
        Interpreter* gfx = XboxDispatchInterpreter();
        texFlags = texture->Flags;
        rawTexMetadata.width = texture->Width;
        rawTexMetadata.height = texture->Height;
        rawTexMetadata.h_byte_scale = texture->HByteScale;
        rawTexMetadata.v_pixel_scale = texture->VPixelScale;
        rawTexMetadata.type = texture->Type;
        rawTexMetadata.resource = texture;

        uint32_t fmt = C0(21, 3);
        uint32_t size = C0(19, 2);
        uint32_t width = C0(0, 12) + 1;

        gfx->GfxDpSetTextureImage(fmt, size, width, fileName, texFlags, rawTexMetadata,
                                  reinterpret_cast<char*>(texture->ImageData));
    } else {
        SPDLOG_ERROR("G_SETTIMG_OTR_FILEPATH: Texture is null");
    }
    return false;
}

bool gfx_set_timg_otr_filepath_handler_custom(F3DGfx** cmd0) {
    LaneWork::Add(LaneWork::TextureMetadata);
    LaneWork::Add(LaneWork::ResourceResolve);
    StreamEntryCounts::Handler(68);
    if(!CampaignOwnerGeneration::ownersMode)return CampaignOriginal_gfx_set_timg_otr_filepath_handler_custom(cmd0);
    F3DGfx* cmd = *cmd0;
    const char* fileName = (char*)cmd->words.w1;

    uint32_t texFlags = 0;
    RawTexMetadata rawTexMetadata;

    std::shared_ptr<Fast::Texture> texture = std::static_pointer_cast<Fast::Texture>(
        XboxRunResourceManager()->LoadResourceProcess(fileName));
    if (texture != nullptr) {
        Interpreter* gfx = XboxDispatchInterpreter();
        texFlags = texture->Flags;
        rawTexMetadata.width = texture->Width;
        rawTexMetadata.height = texture->Height;
        rawTexMetadata.h_byte_scale = texture->HByteScale;
        rawTexMetadata.v_pixel_scale = texture->VPixelScale;
        rawTexMetadata.type = texture->Type;
        rawTexMetadata.resource = texture;

        uint32_t fmt = C0(21, 3);
        uint32_t size = C0(19, 2);
        uint32_t width = C0(0, 12) + 1;

        gfx->GfxDpSetTextureImage(fmt, size, width, fileName, texFlags, rawTexMetadata,
                                  reinterpret_cast<char*>(texture->ImageData));
    } else {
        SPDLOG_ERROR("G_SETTIMG_OTR_FILEPATH: Texture is null");
    }
    return false;
}

bool gfx_set_fb_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(69);
    F3DGfx* cmd = *cmd0;
    Interpreter* gfx = XboxDispatchInterpreter();
    gfx->Flush();

    if (cmd->words.w1) {
        gfx->SetFrameBuffer((int32_t)cmd->words.w1, 1.0f);
        gfx->mActiveFrameBuffer = gfx->mFrameBuffers.find((int32_t)cmd->words.w1);
        gfx->mFbActive = true;
    } else {
        gfx->ResetFrameBuffer();
        gfx->mFbActive = false;
        gfx->mActiveFrameBuffer = gfx->mFrameBuffers.end();
    }
    return false;
}

bool gfx_reset_fb_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(70);
    Interpreter* gfx = XboxDispatchInterpreter();
    gfx->Flush();
    gfx->mFbActive = false;
    gfx->mActiveFrameBuffer = gfx->mFrameBuffers.end();
    (gfx->mXboxPipelineKey.valid=false, gfx->mRapi->StartDrawToFramebuffer(gfx->mRendersToFb ? gfx->mGameFb : 0,
                                       (float)gfx->mCurDimensions.height / gfx->mNativeDimensions.height));
    // Force viewport and scissor to reapply against the main framebuffer, in case a previous smaller
    // framebuffer truncated the values
    gfx->mRdp->viewport_or_scissor_changed = true;
    { XYWidthHeight shipyardAggregate = {}; gfx->mRenderingState.viewport = shipyardAggregate; }
    { XYWidthHeight shipyardAggregate = {}; gfx->mRenderingState.scissor = shipyardAggregate; }
    return false;
}

bool gfx_copy_fb_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(71);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    bool* hasCopiedPtr = (bool*)cmd->words.w1;

    gfx->Flush();
    gfx->CopyFrameBuffer(C0(11, 11), C0(0, 11), (bool)C0(22, 1), hasCopiedPtr);
    return false;
}

bool gfx_read_fb_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(72);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    int32_t width, height;
     int32_t ulx, uly;
    uint16_t* rgba16Buffer = (uint16_t*)cmd->words.w1;
    int fbId = C0(0, 8);
    bool bswap = C0(8, 1);
    ++(*cmd0);
    cmd = *cmd0;
    // Specifying the upper left origin value is unused and unsupported at the renderer level
    ulx = C0(0, 16);
    uly = C0(16, 16);
    width = C1(0, 16);
    height = C1(16, 16);

    gfx->Flush();
    gfx->mRapi->ReadFramebufferToCPU(fbId, width, height, rgba16Buffer);

#ifndef IS_BIGENDIAN
    // byteswap the output to BE
    if (bswap) {
        for (size_t i = 0; i < (size_t)width * height; i++) {
            rgba16Buffer[i] = BE16SWAP(rgba16Buffer[i]);
        }
    }
#endif

    return false;
}

bool gfx_register_blended_texture_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(73);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    // Flush incase we are replacing a previous blended texture that hasn't been finialized to the GPU
    gfx->Flush();

    char* timg = (char*)cmd->words.w1;

    ++(*cmd0);
    cmd = *cmd0;

    uint8_t* mask = (uint8_t*)cmd->words.w0;
    uint8_t* replacementTex = (uint8_t*)cmd->words.w1;

    if (!gfx_check_image_signature(timg)) {
        SPDLOG_ERROR(
            "OTR_G_REGBLENDEDTEX: Texture is not a valid OTR resource name, unable to register blended texture");
        return false;
    }

    // With no mask, we should clear the blended texture
    if (mask == nullptr) {
        gfx->UnregisterBlendedTexture(timg);
    } else {
        gfx->RegisterBlendedTexture(timg, mask, replacementTex);
    }

    return false;
}

bool gfx_set_timg_fb_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(74);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->Flush();
    (gfx->mXboxTextureBindings.Invalidate(), gfx->mXboxPipelineKey.valid=false);
    (gfx->mXboxPipelineKey.valid=false, gfx->mRapi->SelectTextureFb((uint32_t)cmd->words.w1));
    gfx->mRdp->textures_changed[0] = false;
    gfx->mRdp->textures_changed[1] = false;
    return false;
}

bool gfx_set_grayscale_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(75);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->mRdp->grayscale = cmd->words.w1;
    return false;
}

bool gfx_load_block_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(76);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpLoadBlock(C1(24, 3), C0(12, 12), C0(0, 12), C1(12, 12), C1(0, 12));
    return false;
}

bool gfx_load_tile_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(77);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpLoadTile(C1(24, 3), C0(12, 12), C0(0, 12), C1(12, 12), C1(0, 12));
    return false;
}

bool gfx_set_tile_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(78);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetTile(C0(21, 3), C0(19, 2), C0(9, 9), C0(0, 9), C1(24, 3), C1(20, 4), C1(18, 2), C1(14, 4), C1(10, 4),
                      C1(8, 2), C1(4, 4), C1(0, 4));
    return false;
}

bool gfx_set_tile_size_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(79);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetTileSize(C1(24, 3), C0(12, 12), C0(0, 12), C1(12, 12), C1(0, 12));
    return false;
}

bool gfx_set_tile_size_interp_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(80);
    F3DGfx* cmd = *cmd0;
    Interpreter* gfx = XboxDispatchInterpreter();

    if (gfx->mInterpolationIndex == gfx->mInterpolationIndexTarget) {
        int tile = C1(24, 3);
        gfx->GfxDpSetTileSize(C1(24, 3), C0(12, 12), C0(0, 12), C1(12, 12), C1(0, 12));
        ++(*cmd0);
        memcpy(&gfx->mRdp->texture_tile[tile].uls, &(*cmd0)->words.w0, sizeof(float));
        memcpy(&gfx->mRdp->texture_tile[tile].ult, &(*cmd0)->words.w1, sizeof(float));
        ++(*cmd0);
        memcpy(&gfx->mRdp->texture_tile[tile].lrs, &(*cmd0)->words.w0, sizeof(float));
        memcpy(&gfx->mRdp->texture_tile[tile].lrt, &(*cmd0)->words.w1, sizeof(float));
    } else {
        ++(*cmd0);
        ++(*cmd0);
    }

    return false;
}

bool gfx_set_interpolation_index_target(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(81);
    F3DGfx* cmd = *cmd0;
    Interpreter* gfx = XboxDispatchInterpreter();

    gfx->mInterpolationIndexTarget = cmd->words.w1;
    return false;
}

bool gfx_load_tlut_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(82);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpLoadTlut(C1(24, 3), C1(14, 10));
    return false;
}

bool gfx_set_env_color_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(83);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetEnvColor(C1(24, 8), C1(16, 8), C1(8, 8), C1(0, 8));
    return false;
}

bool gfx_set_prim_color_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(84);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetPrimColor(C0(8, 8), C0(0, 8), C1(24, 8), C1(16, 8), C1(8, 8), C1(0, 8));
    return false;
}

bool gfx_set_fog_color_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(85);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetFogColor(C1(24, 8), C1(16, 8), C1(8, 8), C1(0, 8));
    return false;
}

bool gfx_set_blend_color_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(86);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetBlendColor(C1(24, 8), C1(16, 8), C1(8, 8), C1(0, 8));
    return false;
}

bool gfx_set_fill_color_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(87);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetFillColor((uint32_t)cmd->words.w1);
    return false;
}

bool gfx_set_intensity_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(88);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetGrayscaleColor(C1(24, 8), C1(16, 8), C1(8, 8), C1(0, 8));
    return false;
}

bool gfx_set_combine_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(89);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;

    gfx->GfxDpSetCombineMode(
        color_comb(C0(20, 4), C1(28, 4), C0(15, 5), C1(15, 3)), alpha_comb(C0(12, 3), C1(12, 3), C0(9, 3), C1(9, 3)),
        color_comb(C0(5, 4), C1(24, 4), C0(0, 5), C1(6, 3)), alpha_comb(C1(21, 3), C1(3, 3), C1(18, 3), C1(0, 3)));
    return false;
}

bool gfx_tex_rect_and_flip_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(90);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    int8_t opcode = (int8_t)(cmd->words.w0 >> 24);
    int32_t lrx, lry, tile, ulx, uly;
    uint32_t uls, ult, dsdx, dtdy;

    lrx = C0(12, 12);
    lry = C0(0, 12);
    tile = C1(24, 3);
    ulx = C1(12, 12);
    uly = C1(0, 12);
    // TODO make sure I don't need to increment cmd0
    ++(*cmd0);
    cmd = *cmd0;
    uls = C1(16, 16);
    ult = C1(0, 16);
    ++(*cmd0);
    cmd = *cmd0;
    dsdx = C1(16, 16);
    dtdy = C1(0, 16);

    gfx->GfxDpTextureRectangle(ulx, uly, lrx, lry, tile, uls, ult, dsdx, dtdy, opcode == RDP_G_TEXRECTFLIP);
    return false;
}

bool gfx_tex_rect_wide_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(91);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    int8_t opcode = (int8_t)(cmd->words.w0 >> 24);
    int32_t lrx, lry, tile, ulx, uly;
    uint32_t uls, ult, dsdx, dtdy;

    lrx = static_cast<int32_t>((C0(0, 24) << 8)) >> 8;
    lry = static_cast<int32_t>((C1(0, 24) << 8)) >> 8;
    tile = C1(24, 3);
    ++(*cmd0);
    cmd = *cmd0;
    ulx = static_cast<int32_t>((C0(0, 24) << 8)) >> 8;
    uly = static_cast<int32_t>((C1(0, 24) << 8)) >> 8;
    ++(*cmd0);
    cmd = *cmd0;
    uls = C0(16, 16);
    ult = C0(0, 16);
    dsdx = C1(16, 16);
    dtdy = C1(0, 16);
    gfx->GfxDpTextureRectangle(ulx, uly, lrx, lry, tile, uls, ult, dsdx, dtdy, opcode == RDP_G_TEXRECTFLIP);
    return false;
}

bool gfx_image_rect_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(92);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *cmd0;
    int16_t tile, iw, ih;
    int16_t x0, y0, s0, t0;
    int16_t x1, y1, s1, t1;
    tile = C0(0, 3);
    iw = C1(16, 16);
    ih = C1(0, 16);
    cmd = ++(*cmd0);
    x0 = C0(16, 16);
    y0 = C0(0, 16);
    s0 = C1(16, 16);
    t0 = C1(0, 16);
    cmd = ++(*cmd0);
    x1 = C0(16, 16);
    y1 = C0(0, 16);
    s1 = C1(16, 16);
    t1 = C1(0, 16);
    gfx->GfxDpImageRectangle(tile, iw, ih, x0, y0, s0, t0, x1, y1, s1, t1);

    return false;
}

bool gfx_fill_rect_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(93);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxDpFillRectangle(C1(12, 12), C1(0, 12), C0(12, 12), C0(0, 12));
    return false;
}

bool gfx_fill_wide_rect_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(94);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);
    int32_t lrx, lry, ulx, uly;

    lrx = (int32_t)(C0(0, 24) << 8) >> 8;
    lry = (int32_t)(C1(0, 24) << 8) >> 8;
    cmd = ++(*cmd0);
    ulx = (int32_t)(C0(0, 24) << 8) >> 8;
    uly = (int32_t)(C1(0, 24) << 8) >> 8;
    gfx->GfxDpFillRectangle(ulx, uly, lrx, lry);

    return false;
}

bool gfx_SetScissor_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(95);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxDpSetScissor(C1(24, 2), C0(12, 12), C0(0, 12), C1(12, 12), C1(0, 12));
    return false;
}

bool gfx_set_z_img_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(96);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxDpSetZImage(gfx->SegAddr(cmd->words.w1));
    return false;
}

bool gfx_set_c_img_handler_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(97);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxDpSetColorImage(C0(21, 3), C0(19, 2), C0(0, 11), gfx->SegAddr(cmd->words.w1));
    return false;
}

bool gfx_rdp_set_other_mode_rdp(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(98);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxDpSetOtherMode(C0(0, 24), (uint32_t)cmd->words.w1);
    return false;
}

bool gfx_bg_copy_handler_s2dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(99);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    if (!gfx->mMarkerOn) {
        gfx->Gfxs2dexBgCopy((F3DuObjBg*)cmd->words.w1); // not gfx->SegAddr here it seems
    }
    return false;
}

bool gfx_bg_1cyc_handler_s2dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(100);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->Gfxs2dexBg1cyc((F3DuObjBg*)cmd->words.w1);
    return false;
}

bool gfx_obj_rectangle_handler_s2dex(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(101);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    if (!gfx->mMarkerOn) {
        gfx->Gfxs2dexRecyCopy((F3DuObjSprite*)cmd->words.w1); // not gfx->SegAddr here it seems
    }
    return false;
}

bool gfx_extra_geometry_mode_handler_custom(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(102);
    Interpreter* gfx = XboxDispatchInterpreter();
    F3DGfx* cmd = *(cmd0);

    gfx->GfxSpExtraGeometryMode(~C0(0, 24), (uint32_t)cmd->words.w1);
    return false;
}

bool gfx_stubbed_command_handler(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(103);
    return false;
}

bool gfx_spnoop_command_handler_f3dex2(F3DGfx** cmd0) {
    StreamEntryCounts::Handler(104);
    return false;
}

struct UcodeEntry { int8_t opcode; const char* name; GfxOpcodeHandlerFunc handler; };
class UcodeHandler {
  public:
    UcodeHandler(const UcodeEntry* initializer, size_t count) {
        std::fill(mHandlers, mHandlers + sizeof(mHandlers)/sizeof(mHandlers[0]),
                  std::pair<const char*, GfxOpcodeHandlerFunc>(nullptr, nullptr));
        for (size_t i=0; i<count; ++i) {
            const UcodeEntry& entry=initializer[i];
            mHandlers[static_cast<uint8_t>(entry.opcode)] = std::make_pair(entry.name, entry.handler);
        }
    }

    inline bool contains(int8_t opcode) const {
        return mHandlers[static_cast<uint8_t>(opcode)].first != nullptr;
    }

    inline const std::pair<const char*, GfxOpcodeHandlerFunc>& at(int8_t opcode) const {
        return mHandlers[static_cast<uint8_t>(opcode)];
    }

    UcodeHandler(const UcodeHandler& otr, const UcodeHandler& rdp,
                 const UcodeHandler& ucode) {
        for (unsigned i = 0; i < 256; ++i) {
            const std::pair<const char*, GfxOpcodeHandlerFunc>& o = otr.mHandlers[i];
            const std::pair<const char*, GfxOpcodeHandlerFunc>& r = rdp.mHandlers[i];
            mHandlers[i] = o.first ? o : (r.first ? r : ucode.mHandlers[i]);
        }
    }

  private:
    std::pair<const char*, GfxOpcodeHandlerFunc> mHandlers[256 /* complete uint8_t opcode domain */];
};

static const UcodeEntry rdpHandlersEntries[] = {
    { RDP_G_SETTARGETINTERPINDEX, "G_SETTARGETINTERPINDEX", gfx_set_interpolation_index_target },
    { RDP_G_SETTILESIZE_INTERP, "G_SETTILESIZE_INTERP", gfx_set_tile_size_interp_handler_rdp },
    { RDP_G_TEXRECT, "G_TEXRECT", gfx_tex_rect_and_flip_handler_rdp },
    { RDP_G_TEXRECTFLIP, "G_TEXRECTFLIP", gfx_tex_rect_and_flip_handler_rdp },
    { RDP_G_RDPLOADSYNC, "mRdpLOADSYNC", gfx_stubbed_command_handler },
    { RDP_G_RDPPIPESYNC, "mRdpPIPESYNC", gfx_stubbed_command_handler },
    { RDP_G_RDPTILESYNC, "mRdpTILESYNC", gfx_stubbed_command_handler },
    { RDP_G_RDPFULLSYNC, "mRdpFULLSYNC", gfx_stubbed_command_handler },
    { RDP_G_SETSCISSOR, "G_SETSCISSOR", gfx_SetScissor_handler_rdp },
    { RDP_G_SETPRIMDEPTH, "G_SETPRIMDEPTH", gfx_set_prim_depth_handler_rdp },
    { RDP_G_RDPSETOTHERMODE, "mRdpSETOTHERMODE", gfx_rdp_set_other_mode_rdp },
    { RDP_G_LOADTLUT, "G_LOADTLUT", gfx_load_tlut_handler_rdp },
    { RDP_G_SETTILESIZE, "G_SETTILESIZE", gfx_set_tile_size_handler_rdp },
    { RDP_G_LOADBLOCK, "G_LOADBLOCK", gfx_load_block_handler_rdp },
    { RDP_G_LOADTILE, "G_LOADTILE", gfx_load_tile_handler_rdp },
    { RDP_G_SETTILE, "G_SETTILE", gfx_set_tile_handler_rdp },
    { RDP_G_FILLRECT, "G_FILLRECT", gfx_fill_rect_handler_rdp },
    { RDP_G_SETFILLCOLOR, "G_SETFILLCOLOR", gfx_set_fill_color_handler_rdp },
    { RDP_G_SETFOGCOLOR, "G_SETFOGCOLOR", gfx_set_fog_color_handler_rdp },
    { RDP_G_SETBLENDCOLOR, "G_SETBLENDCOLOR", gfx_set_blend_color_handler_rdp },
    { RDP_G_SETPRIMCOLOR, "G_SETPRIMCOLOR", gfx_set_prim_color_handler_rdp },
    { RDP_G_SETENVCOLOR, "G_SETENVCOLOR", gfx_set_env_color_handler_rdp },
    { RDP_G_SETCOMBINE, "G_SETCOMBINE", gfx_set_combine_handler_rdp },
    { RDP_G_SETTIMG, "G_SETTIMG", gfx_set_timg_handler_rdp },
    { RDP_G_SETZIMG, "G_SETZIMG", gfx_set_z_img_handler_rdp },
    { RDP_G_SETCIMG, "G_SETCIMG", gfx_set_c_img_handler_rdp }
};
static const UcodeHandler rdpHandlers(rdpHandlersEntries, sizeof(rdpHandlersEntries)/sizeof(rdpHandlersEntries[0]));

static const UcodeEntry otrHandlersEntries[] = {
    { OTR_G_SETTIMG_OTR_HASH, "G_SETTIMG_OTR_HASH", gfx_set_timg_otr_hash_handler_custom },
    { OTR_G_SETFB, "G_SETFB", gfx_set_fb_handler_custom },
    { OTR_G_RESETFB, "G_RESETFB", gfx_reset_fb_handler_custom },
    { OTR_G_SETTIMG_FB, "G_SETTIMG_FB", gfx_set_timg_fb_handler_custom },
    { OTR_G_VTX_OTR_FILEPATH, "G_VTX_OTR_FILEPATH", gfx_vtx_otr_filepath_handler_custom },
    { OTR_G_SETTIMG_OTR_FILEPATH, "G_SETTIMG_OTR_FILEPATH", gfx_set_timg_otr_filepath_handler_custom },
    { OTR_G_TRI1_OTR, "G_TRI1_OTR", gfx_tri1_otr_handler_f3dex2 },
    { OTR_G_DL_OTR_FILEPATH, "G_DL_OTR_FILEPATH", gfx_dl_otr_filepath_handler_custom },
    { OTR_G_PUSHCD, "G_PUSHCD", gfx_pushcd_handler_custom },
    { OTR_G_MTX_OTR_FILEPATH, "G_MTX_OTR_FILEPATH", gfx_mtx_otr_filepath_handler_custom },
    { OTR_G_DL_OTR_HASH, "G_DL_OTR_HASH", gfx_dl_otr_hash_handler_custom },
    { OTR_G_VTX_OTR_HASH, "G_VTX_OTR_HASH", gfx_vtx_hash_handler_custom },
    { OTR_G_MARKER, "G_MARKER", gfx_marker_handler_otr },
    { OTR_G_INVALTEXCACHE, "G_INVALTEXCACHE", gfx_invalidate_tex_cache_handler_f3dex2 },
    { OTR_G_BRANCH_Z_OTR, "G_BRANCH_Z_OTR", gfx_branch_z_otr_handler_f3dex2 },
    { OTR_G_MTX_OTR, "G_MTX_OTR", gfx_mtx_otr_handler_custom },
    { OTR_G_TEXRECT_WIDE, "G_TEXRECT_WIDE", gfx_tex_rect_wide_handler_custom },
    { OTR_G_FILLWIDERECT, "G_FILLWIDERECT", gfx_fill_wide_rect_handler_custom },
    { OTR_G_SETGRAYSCALE, "G_SETGRAYSCALE", gfx_set_grayscale_handler_custom },
    { OTR_G_EXTRAGEOMETRYMODE, "G_EXTRAGEOMETRYMODE", gfx_extra_geometry_mode_handler_custom },
    { OTR_G_COPYFB, "G_COPYFB", gfx_copy_fb_handler_custom },
    { OTR_G_IMAGERECT, "G_IMAGERECT", gfx_image_rect_handler_custom },
    { OTR_G_DL_INDEX, "G_DL_INDEX", gfx_dl_index_handler },
    { OTR_G_READFB, "G_READFB", gfx_read_fb_handler_custom },
    { OTR_G_REGBLENDEDTEX, "G_REGBLENDEDTEX", gfx_register_blended_texture_handler_custom },
    { OTR_G_SETINTENSITY, "G_SETINTENSITY", gfx_set_intensity_handler_custom },
    { OTR_G_MOVEMEM_HASH, "OTR_G_MOVEMEM_HASH", gfx_movemem_handler_otr },
    { OTR_G_LOAD_SHADER, "G_LOAD_SHADER", gfx_set_shader_custom }
};
static const UcodeHandler otrHandlers(otrHandlersEntries, sizeof(otrHandlersEntries)/sizeof(otrHandlersEntries[0]));

static const UcodeEntry f3dex2HandlersEntries[] = {
    { F3DEX2_G_NOOP, "G_NOOP", gfx_noop_handler_f3dex2 },
    { F3DEX2_G_SPNOOP, "G_SPNOOP", gfx_noop_handler_f3dex2 },
    { F3DEX2_G_CULLDL, "G_CULLDL", gfx_cull_dl_handler_f3dex2 },
    { F3DEX2_G_MTX, "G_MTX", gfx_mtx_handler_f3dex2 },
    { F3DEX2_G_POPMTX, "G_POPMTX", gfx_pop_mtx_handler_f3dex2 },
    { F3DEX2_G_MOVEMEM, "G_MOVEMEM", gfx_movemem_handler_f3dex2 },
    { F3DEX2_G_MOVEWORD, "G_MOVEWORD", gfx_moveword_handler_f3dex2 },
    { F3DEX2_G_TEXTURE, "G_TEXTURE", gfx_texture_handler_f3dex2 },
    { F3DEX2_G_VTX, "G_VTX", gfx_vtx_handler_f3dex2 },
    { F3DEX2_G_MODIFYVTX, "G_MODIFYVTX", gfx_modify_vtx_handler_f3dex2 },
    { F3DEX2_G_DL, "G_DL", gfx_dl_handler_common },
    { F3DEX2_G_ENDDL, "G_ENDDL", gfx_end_dl_handler_common },
    { F3DEX2_G_GEOMETRYMODE, "G_GEOMETRYMODE", gfx_geometry_mode_handler_f3dex2 },
    { F3DEX2_G_TRI1, "G_TRI1", gfx_tri1_handler_f3dex2 },
    { F3DEX2_G_TRI2, "G_TRI2", gfx_tri2_handler_f3dex },
    { F3DEX2_G_QUAD, "G_QUAD", gfx_quad_handler_f3dex2 },
    { F3DEX2_G_SETOTHERMODE_L, "G_SETOTHERMODE_L", gfx_othermode_l_handler_f3dex2 },
    { F3DEX2_G_SETOTHERMODE_H, "G_SETOTHERMODE_H", gfx_othermode_h_handler_f3dex2 }
};
static const UcodeHandler f3dex2Handlers(f3dex2HandlersEntries, sizeof(f3dex2HandlersEntries)/sizeof(f3dex2HandlersEntries[0]));

static const UcodeEntry f3dexHandlersEntries[] = {
    { F3DEX_G_NOOP, "G_NOOP", gfx_noop_handler_f3dex2 },
    { F3DEX_G_CULLDL, "G_CULLDL", gfx_cull_dl_handler_f3dex2 },
    { F3DEX_G_MTX, "G_MTX", gfx_mtx_handler_f3d },
    { F3DEX_G_POPMTX, "G_POPMTX", gfx_pop_mtx_handler_f3d },
    { F3DEX_G_MOVEMEM, "G_POPMEM", gfx_movemem_handler_f3d },
    { F3DEX_G_MOVEWORD, "G_MOVEWORD", gfx_moveword_handler_f3d },
    { F3DEX_G_TEXTURE, "G_TEXTURE", gfx_texture_handler_f3d },
    { F3DEX_G_SETOTHERMODE_L, "G_SETOTHERMODE_L", gfx_othermode_l_handler_f3d },
    { F3DEX_G_SETOTHERMODE_H, "G_SETOTHERMODE_H", gfx_othermode_h_handler_f3d },
    { F3DEX_G_SETGEOMETRYMODE, "G_SETGEOMETRYMODE", gfx_set_geometry_mode_handler_f3dex },
    { F3DEX_G_CLEARGEOMETRYMODE, "G_CLEARGEOMETRYMODE", gfx_clear_geometry_mode_handler_f3dex },
    { F3DEX_G_VTX, "G_VTX", gfx_vtx_handler_f3dex },
    { F3DEX_G_TRI1, "G_TRI1", gfx_tri1_handler_f3dex },
    { F3DEX_G_MODIFYVTX, "G_MODIFYVTX", gfx_modify_vtx_handler_f3dex2 },
    { F3DEX_G_DL, "G_DL", gfx_dl_handler_common },
    { F3DEX_G_ENDDL, "G_ENDDL", gfx_end_dl_handler_common },
    { F3DEX_G_TRI2, "G_TRI2", gfx_tri2_handler_f3dex },
    { F3DEX_G_SPNOOP, "G_SPNOOP", gfx_spnoop_command_handler_f3dex2 },
    { F3DEX_G_RDPHALF_1, "mRdpHALF_1", gfx_stubbed_command_handler },
    { F3DEX_G_QUAD, "G_QUAD", gfx_quad_handler_f3dex }
};
static const UcodeHandler f3dexHandlers(f3dexHandlersEntries, sizeof(f3dexHandlersEntries)/sizeof(f3dexHandlersEntries[0]));

static const UcodeEntry f3dHandlersEntries[] = {
    { F3DEX_G_NOOP, "G_NOOP", gfx_noop_handler_f3dex2 },
    { F3DEX_G_CULLDL, "G_CULLDL", gfx_cull_dl_handler_f3dex2 },
    { F3DEX_G_MTX, "G_MTX", gfx_mtx_handler_f3d },
    { F3DEX_G_POPMTX, "G_POPMTX", gfx_pop_mtx_handler_f3d },
    { F3DEX_G_MOVEMEM, "G_POPMEM", gfx_movemem_handler_f3d },
    { F3DEX_G_MOVEWORD, "G_MOVEWORD", gfx_moveword_handler_f3d },
    { F3DEX_G_TEXTURE, "G_TEXTURE", gfx_texture_handler_f3d },
    { F3DEX_G_SETOTHERMODE_L, "G_SETOTHERMODE_L", gfx_othermode_l_handler_f3d },
    { F3DEX_G_SETOTHERMODE_H, "G_SETOTHERMODE_H", gfx_othermode_h_handler_f3d },
    { F3DEX_G_SETGEOMETRYMODE, "G_SETGEOMETRYMODE", gfx_set_geometry_mode_handler_f3dex },
    { F3DEX_G_CLEARGEOMETRYMODE, "G_CLEARGEOMETRYMODE", gfx_clear_geometry_mode_handler_f3dex },
    { F3DEX_G_VTX, "G_VTX", gfx_vtx_handler_f3d },
    { F3DEX_G_TRI1, "G_TRI1", gfx_tri1_handler_f3d },
    { F3DEX_G_MODIFYVTX, "G_MODIFYVTX", gfx_modify_vtx_handler_f3dex2 },
    { F3DEX_G_DL, "G_DL", gfx_dl_handler_common },
    { F3DEX_G_ENDDL, "G_ENDDL", gfx_end_dl_handler_common },
    { F3DEX_G_TRI2, "G_TRI2", gfx_tri2_handler_f3dex },
    { F3DEX_G_SPNOOP, "G_SPNOOP", gfx_spnoop_command_handler_f3dex2 },
    { F3DEX_G_RDPHALF_1, "mRdpHALF_1", gfx_stubbed_command_handler }
};
static const UcodeHandler f3dHandlers(f3dHandlersEntries, sizeof(f3dHandlersEntries)/sizeof(f3dHandlersEntries[0]));

// LUSTODO: These S2DEX commands have different opcode numbers on F3DEX2 vs other ucodes. More research needs to be done
// to see if the implementations are different.
static const UcodeEntry s2dexHandlersEntries[] = {
    { F3DEX2_G_BG_COPY, "G_BG_COPY", gfx_bg_copy_handler_s2dex },
    { F3DEX2_G_BG_1CYC, "G_BG_1CYC", gfx_bg_1cyc_handler_s2dex },
    { F3DEX2_G_OBJ_RENDERMODE, "G_OBJ_RENDERMODE", gfx_stubbed_command_handler },
    { F3DEX2_G_OBJ_RECTANGLE_R, "G_OBJ_RECTANGLE_R", gfx_stubbed_command_handler },
    { F3DEX2_G_OBJ_RECTANGLE, "G_OBJ_RECTANGLE", gfx_obj_rectangle_handler_s2dex },
    { F3DEX2_G_DL, "G_DL", gfx_dl_handler_common },
    { F3DEX2_G_ENDDL, "G_ENDDL", gfx_end_dl_handler_common }
};
static const UcodeHandler s2dexHandlers(s2dexHandlersEntries, sizeof(s2dexHandlersEntries)/sizeof(s2dexHandlersEntries[0]));

static const UcodeHandler f3dDispatch(otrHandlers, rdpHandlers, f3dHandlers);
static const UcodeHandler f3dexDispatch(otrHandlers, rdpHandlers, f3dexHandlers);
static const UcodeHandler f3dex2Dispatch(otrHandlers, rdpHandlers, f3dex2Handlers);
static const UcodeHandler s2dexDispatch(otrHandlers, rdpHandlers, s2dexHandlers);

static const std::array<const UcodeHandler*, 6> ucode_handlers = { {
    &f3dDispatch,    // ucode_f3db
    &f3dDispatch,    // ucode_f3d
    &f3dexDispatch,  // ucode_f3dex
    &f3dexDispatch,  // ucode_f3dexb
    &f3dex2Dispatch, // ucode_f3dex2
    &s2dexDispatch,  // ucode_s2dex
} };

const char* GfxGetOpcodeName(int8_t opcode) {
    if (ucode_handler_index < ucode_handlers.size()) {
        const auto& handler = ucode_handlers[ucode_handler_index]->at(opcode);
        if (handler.first) return handler.first;
        SPDLOG_CRITICAL("Unhandled OP code: 0x{:X}, for loaded ucode: {}", (uint8_t)opcode,
                        (uint32_t)ucode_handler_index);
    } else {
        // Preserve the original OTR/RDP priority even for an invalid ucode.
        if (otrHandlers.contains(opcode)) return otrHandlers.at(opcode).first;
        if (rdpHandlers.contains(opcode)) return rdpHandlers.at(opcode).first;
        SPDLOG_CRITICAL("Unhandled OP code: 0x{:X}, invalid ucode: {}", (uint8_t)opcode,
                        (uint32_t)ucode_handler_index);
    }
    return nullptr;
}

// TODO, implement a system where we can get the current opcode handler by writing to the GWords. If the powers that be
// are OK with that...
static void gfx_set_ucode_handler(UcodeHandlers ucode) {
    // Loaded ucode must be in range of the supported ucode_handlers
    assert(ucode < ucode_max);
    Interpreter* gfx = XboxDispatchInterpreter();
    ucode_handler_index = ucode;

    // Reset some RSP state values upon ucode load to deal with hardware quirks discovered by emulators
    switch (ucode) {
        case ucode_f3d:
        case ucode_f3db:
        case ucode_f3dex:
        case ucode_f3dexb:
        case ucode_f3dex2:
            CampaignDeferredState::snapshot.Invalidate(); gfx->mRsp->fog_mul = 0;
            gfx->mRsp->fog_offset = 0;
            break;
        default:
            break;
    }
}


// Additional command words are consumed directly into existing Arguments.
// The old zero-initialized inline array left missing tail words at zero;
// preserve that behavior without reading beyond the handler-consumed span.
static __forceinline unsigned CapturedExtra(F3DGfx* before,uintptr_t bytes,unsigned index,unsigned word) {
    return Shipyard::Fast3D::CapturedExtraWord(before,bytes,index,word);
}
static void CapturePreparedHandler(GfxOpcodeHandlerFunc handler,F3DGfx* before,F3DGfx* after) {
    UpdateStream::Packet& p=UpdateStream::packet;
    if(!p.active || !p.recording || p.current>=p.instructions.size())return;
    UpdateStream::Instruction& op=p.instructions[p.current];
    if(handler==gfx_end_dl_handler_common){op.kind=UpdateStream::EndList;return;}
    if(handler==gfx_dl_handler_common || handler==gfx_dl_otr_hash_handler_custom ||
       handler==gfx_dl_otr_filepath_handler_custom || handler==gfx_dl_index_handler){op.kind=UpdateStream::Flow;return;}
    const uintptr_t bytes=uintptr_t(after)-uintptr_t(before);
    if(bytes%sizeof(F3DGfx) || bytes/sizeof(F3DGfx)>2){p.conditional=true;return;}
    F3DGfx* cmd=before; // Decode synchronously after the selected handler, as before.
    if(handler==gfx_load_block_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,3));
        values.value[1]=unsigned(C0(12,12));
        values.value[2]=unsigned(C0(0,12));
        values.value[3]=unsigned(C1(12,12));
        values.value[4]=unsigned(C1(0,12));
        op.kind=UpdateStream::LoadBlock;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_load_tile_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,3));
        values.value[1]=unsigned(C0(12,12));
        values.value[2]=unsigned(C0(0,12));
        values.value[3]=unsigned(C1(12,12));
        values.value[4]=unsigned(C1(0,12));
        op.kind=UpdateStream::LoadTile;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_tile_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(21,3));
        values.value[1]=unsigned(C0(19,2));
        values.value[2]=unsigned(C0(9,9));
        values.value[3]=unsigned(C0(0,9));
        values.value[4]=unsigned(C1(24,3));
        values.value[5]=unsigned(C1(20,4));
        values.value[6]=unsigned(C1(18,2));
        values.value[7]=unsigned(C1(14,4));
        values.value[8]=unsigned(C1(10,4));
        values.value[9]=unsigned(C1(8,2));
        values.value[10]=unsigned(C1(4,4));
        values.value[11]=unsigned(C1(0,4));
        op.kind=UpdateStream::SetTile;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_tile_size_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,3));
        values.value[1]=unsigned(C0(12,12));
        values.value[2]=unsigned(C0(0,12));
        values.value[3]=unsigned(C1(12,12));
        values.value[4]=unsigned(C1(0,12));
        op.kind=UpdateStream::TileSize;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_load_tlut_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,3));
        values.value[1]=unsigned(C1(14,10));
        op.kind=UpdateStream::LoadTlut;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_env_color_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,8));
        values.value[1]=unsigned(C1(16,8));
        values.value[2]=unsigned(C1(8,8));
        values.value[3]=unsigned(C1(0,8));
        op.kind=UpdateStream::EnvColor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_prim_color_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(8,8));
        values.value[1]=unsigned(C0(0,8));
        values.value[2]=unsigned(C1(24,8));
        values.value[3]=unsigned(C1(16,8));
        values.value[4]=unsigned(C1(8,8));
        values.value[5]=unsigned(C1(0,8));
        op.kind=UpdateStream::PrimColor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_fog_color_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,8));
        values.value[1]=unsigned(C1(16,8));
        values.value[2]=unsigned(C1(8,8));
        values.value[3]=unsigned(C1(0,8));
        op.kind=UpdateStream::FogColor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_blend_color_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,8));
        values.value[1]=unsigned(C1(16,8));
        values.value[2]=unsigned(C1(8,8));
        values.value[3]=unsigned(C1(0,8));
        op.kind=UpdateStream::BlendColor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_fill_color_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::FillColor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_SetScissor_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,2));
        values.value[1]=unsigned(C0(12,12));
        values.value[2]=unsigned(C0(0,12));
        values.value[3]=unsigned(C1(12,12));
        values.value[4]=unsigned(C1(0,12));
        op.kind=UpdateStream::Scissor;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_fill_rect_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(12,12));
        values.value[1]=unsigned(C1(0,12));
        values.value[2]=unsigned(C0(12,12));
        values.value[3]=unsigned(C0(0,12));
        op.kind=UpdateStream::FillRect;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_pop_mtx_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(cmd->words.w1/64);
        op.kind=UpdateStream::PopMatrix;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_geometry_mode_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(~C0(0,24));
        values.value[1]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::Geometry;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_moveword_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(16,8));
        values.value[1]=unsigned(C0(0,16));
        values.value[2]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::MoveWord;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_texture_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(16,16));
        values.value[1]=unsigned(C1(0,16));
        values.value[2]=unsigned(C0(11,3));
        values.value[3]=unsigned(C0(8,3));
        values.value[4]=unsigned(C0(1,7));
        op.kind=UpdateStream::TextureScale;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_othermode_l_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(31-C0(8,8)-C0(0,8));
        values.value[1]=unsigned(C0(0,8)+1);
        values.value[2]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::OtherLow;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_othermode_h_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(63-C0(8,8)-C0(0,8));
        values.value[1]=unsigned(C0(0,8)+1);
        values.value[2]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::OtherHigh;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_rdp_set_other_mode_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(0,24));
        values.value[1]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::RdpOther;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_combine_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(color_comb(C0(20,4),C1(28,4),C0(15,5),C1(15,3)));
        values.value[1]=unsigned(alpha_comb(C0(12,3),C1(12,3),C0(9,3),C1(9,3)));
        values.value[2]=unsigned(color_comb(C0(5,4),C1(24,4),C0(0,5),C1(6,3)));
        values.value[3]=unsigned(alpha_comb(C1(21,3),C1(3,3),C1(18,3),C1(0,3)));
        op.kind=UpdateStream::Combine;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_grayscale_handler_custom){UpdateStream::Arguments values={};
        values.value[0]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::Grayscale;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_interpolation_index_target){UpdateStream::Arguments values={};
        values.value[0]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::InterpolationTarget;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_intensity_handler_custom){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,8));
        values.value[1]=unsigned(C1(16,8));
        values.value[2]=unsigned(C1(8,8));
        values.value[3]=unsigned(C1(0,8));
        op.kind=UpdateStream::Intensity;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_marker_handler_otr){UpdateStream::Arguments values={};
        op.kind=UpdateStream::Marker;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_noop_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(16,8));
        values.value[1]=unsigned(C0(0,16));
        values.value[2]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::DisplayAnnotation;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_load_ucode_handler_f3dex2){UpdateStream::Arguments values={};
        op.kind=UpdateStream::ResetFog;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_stubbed_command_handler){UpdateStream::Arguments values={};
        op.kind=UpdateStream::NoWork;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_spnoop_command_handler_f3dex2){UpdateStream::Arguments values={};
        op.kind=UpdateStream::SpNoop;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_cull_dl_handler_f3dex2){UpdateStream::Arguments values={};
        op.kind=UpdateStream::CullNoop;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_prim_depth_handler_rdp){UpdateStream::Arguments values={};
        op.kind=UpdateStream::PrimDepthNoop;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_tri1_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(16,8)/2);
        values.value[1]=unsigned(C0(8,8)/2);
        values.value[2]=unsigned(C0(0,8)/2);
        op.kind=UpdateStream::Triangle;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_quad_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(16,8)/2);
        values.value[1]=unsigned(C0(8,8)/2);
        values.value[2]=unsigned(C0(0,8)/2);
        values.value[3]=unsigned(C1(16,8)/2);
        values.value[4]=unsigned(C1(8,8)/2);
        values.value[5]=unsigned(C1(0,8)/2);
        op.kind=UpdateStream::Quad;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_pushcd_handler_custom){UpdateStream::Arguments values={};
        op.kind=UpdateStream::Directory;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_z_img_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(uintptr_t(XboxDispatchInterpreter()->SegAddr(cmd->words.w1)));
        op.kind=UpdateStream::DepthImage;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_c_img_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C0(21,3));
        values.value[1]=unsigned(C0(19,2));
        values.value[2]=unsigned(C0(0,11));
        values.value[3]=unsigned(uintptr_t(XboxDispatchInterpreter()->SegAddr(cmd->words.w1)));
        op.kind=UpdateStream::ColorImage;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_fill_wide_rect_handler_custom){UpdateStream::Arguments values={};
        values.value[0]=unsigned(int32_t(unsigned(CapturedExtra(before,bytes,1,0))<<8)>>8);
        values.value[1]=unsigned(int32_t(unsigned(CapturedExtra(before,bytes,1,1))<<8)>>8);
        values.value[2]=unsigned(int32_t(unsigned(before[0].words.w0)<<8)>>8);
        values.value[3]=unsigned(int32_t(unsigned(before[0].words.w1)<<8)>>8);
        op.kind=UpdateStream::WideFill;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_tex_rect_wide_handler_custom){UpdateStream::Arguments values={};
        values.value[0]=unsigned(int32_t(unsigned(CapturedExtra(before,bytes,1,0))<<8)>>8);
        values.value[1]=unsigned(int32_t(unsigned(CapturedExtra(before,bytes,1,1))<<8)>>8);
        values.value[2]=unsigned(int32_t(unsigned(before[0].words.w0)<<8)>>8);
        values.value[3]=unsigned(int32_t(unsigned(before[0].words.w1)<<8)>>8);
        values.value[4]=unsigned(C1(24,3));
        values.value[5]=unsigned((CapturedExtra(before,bytes,2,0)>>16)&65535);
        values.value[6]=unsigned(CapturedExtra(before,bytes,2,0)&65535);
        values.value[7]=unsigned((CapturedExtra(before,bytes,2,1)>>16)&65535);
        values.value[8]=unsigned(CapturedExtra(before,bytes,2,1)&65535);
        values.value[9]=unsigned(int8_t(op.word0>>24)==RDP_G_TEXRECTFLIP);
        op.kind=UpdateStream::WideTexture;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_set_tile_size_interp_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(24,3));
        values.value[1]=unsigned(C0(12,12));
        values.value[2]=unsigned(C0(0,12));
        values.value[3]=unsigned(C1(12,12));
        values.value[4]=unsigned(C1(0,12));
        values.value[5]=unsigned(CapturedExtra(before,bytes,1,0));
        values.value[6]=unsigned(CapturedExtra(before,bytes,1,1));
        values.value[7]=unsigned(CapturedExtra(before,bytes,2,0));
        values.value[8]=unsigned(CapturedExtra(before,bytes,2,1));
        op.kind=UpdateStream::InterpolatedTile;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_invalidate_tex_cache_handler_f3dex2){UpdateStream::Arguments values={};
        values.value[0]=unsigned(cmd->words.w1);
        op.kind=UpdateStream::InvalidateTexture;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_tex_rect_and_flip_handler_rdp){UpdateStream::Arguments values={};
        values.value[0]=unsigned(C1(12,12));
        values.value[1]=unsigned(C1(0,12));
        values.value[2]=unsigned(C0(12,12));
        values.value[3]=unsigned(C0(0,12));
        values.value[4]=unsigned(C1(24,3));
        values.value[5]=unsigned((CapturedExtra(before,bytes,1,1)>>16)&65535);
        values.value[6]=unsigned(CapturedExtra(before,bytes,1,1)&65535);
        values.value[7]=unsigned((CapturedExtra(before,bytes,2,1)>>16)&65535);
        values.value[8]=unsigned(CapturedExtra(before,bytes,2,1)&65535);
        values.value[9]=unsigned(int8_t(op.word0>>24)==RDP_G_TEXRECTFLIP);
        op.kind=UpdateStream::TextureRectangle;op.payload[0]=unsigned(p.arguments.size());p.arguments.push_back(values);return;}
    if(handler==gfx_tri2_handler_f3dex) {
        op.kind=UpdateStream::TrianglePair;
        op.payload[0]=((op.word0>>17)&127)<<16 | ((op.word0>>9)&127)<<8 | ((op.word0>>1)&127);
        op.payload[1]=((op.word1>>17)&127)<<16 | ((op.word1>>9)&127)<<8 | ((op.word1>>1)&127);
    }
}
static bool ReplayPreparedUpdate(Interpreter* gfx) {
    UpdateStream::Packet& p=UpdateStream::packet;
    if(UpdateStream::mode!=1 || !p.active || p.recording || p.overflow || p.conditional || !p.matching || p.instructions.empty())return false;
    // Changes observed between presentations invalidate the complete packet.
    // Its resource references remain pinned until the authentic update ends.
    if(p.resourceGeneration!=XboxRunResourceManager()->GetXboxLookupGeneration() ||
       p.archiveEpoch!=XboxRunArchiveManager()->GetXboxHashEpoch())return false;
    if(!p.sealed){
        bool fence=false;p.sealed=true;
        for(unsigned j=0;j<p.instructions.size();++j){
            const unsigned kind=p.instructions[j].kind;
            if(kind==UpdateStream::Generic){p.supported=false;break;}
            if(kind==UpdateStream::Flow || kind==UpdateStream::NoWork || kind==UpdateStream::SpNoop ||
               kind==UpdateStream::CullNoop || kind==UpdateStream::PrimDepthNoop || kind==UpdateStream::Directory){fence=true;continue;}
            p.executable.push_back(j|(fence?0x80000000U:0));fence=false;
        }
    }
    if(!p.supported)return false;
    if(StreamOutputOracle::enabled){
        for(size_t j=0;j<p.instructions.size();++j){
            const UpdateStream::Instruction& v=p.instructions[j];
            if(v.kind==UpdateStream::Vertices){++p.inputChecks;
                if(memcmp(v.vertexSource,&p.vertices[v.payload[2]],v.payload[0]*sizeof(F3DVtx))!=0){++p.inputFailures;return false;}}
        }
    }
    p.replaying=true;
    CAMPAIGN_DIAGNOSTIC_COUNT(p.omitted+=p.instructions.size()-p.executable.size(););
    for(size_t run=0;run<p.executable.size();++run) {
        const unsigned encoded=p.executable[run],i=encoded&0x7fffffffU;
        if(encoded&0x80000000U){CampaignOwnerGeneration::certificate.Mutate();CampaignTriRun::cache.Reset();}
        if(StreamEntryCounts::enabled)++StreamEntryCounts::prepared[StreamEntryCounts::bucket];
        p.current=i;UpdateStream::Instruction& op=p.instructions[i];const unsigned code=op.word0>>24;
        if(code!=F3DEX2_G_TRI1 && code!=F3DEX2_G_TRI2 && code!=F3DEX2_G_VTX && code!=0x32 && code!=F3DEX2_G_MTX && code!=F3DEX2_G_POPMTX)
            CampaignOwnerGeneration::certificate.Mutate();
        if(code!=F3DEX2_G_TRI2)CampaignTriRun::cache.Reset();
        ModernFrameProfile::CommandSampler::Token sample;
        if(ModernFrameProfile::commandSampler.enabled)sample=ModernFrameProfile::commandSampler.Begin(code,op.ucode);
        switch(op.kind) {
        case UpdateStream::Flow:break;
        case UpdateStream::EndList:gfx->mMarkerOn=false;break;
        case UpdateStream::Ucode:gfx_set_ucode_handler((UcodeHandlers)(op.word0&0xffffff));break;
        case UpdateStream::Vertices:
            gfx->GfxSpVertex(op.payload[0],op.payload[1],&p.vertices[op.payload[2]]);CAMPAIGN_DIAGNOSTIC_COUNT(++p.typedVertices;);break;
        case UpdateStream::TextureImage: {
            const UpdateStream::TextureInput& t=p.textures[op.payload[0]];
            gfx->GfxDpSetTextureImage(t.format,t.size,t.width,NULL,t.flags,t.metadata,t.address);CAMPAIGN_DIAGNOSTIC_COUNT(++p.typedTextures;);break;
        }
        case UpdateStream::TrianglePair:ExecutePreparedTriPair(gfx,op.payload[0],op.payload[1]);CAMPAIGN_DIAGNOSTIC_COUNT(++p.typedTriangles;);break;
        case UpdateStream::LoadBlock: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpLoadBlock(a[0],a[1],a[2],a[3],a[4]);break;}
        case UpdateStream::LoadTile: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpLoadTile(a[0],a[1],a[2],a[3],a[4]);break;}
        case UpdateStream::SetTile: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetTile(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10],a[11]);break;}
        case UpdateStream::TileSize: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetTileSize(a[0],a[1],a[2],a[3],a[4]);break;}
        case UpdateStream::LoadTlut: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpLoadTlut(a[0],a[1]);break;}
        case UpdateStream::EnvColor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetEnvColor(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::PrimColor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetPrimColor(a[0],a[1],a[2],a[3],a[4],a[5]);break;}
        case UpdateStream::FogColor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetFogColor(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::BlendColor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetBlendColor(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::FillColor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetFillColor(a[0]);break;}
        case UpdateStream::Scissor: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetScissor(a[0],a[1],a[2],a[3],a[4]);break;}
        case UpdateStream::FillRect: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpFillRectangle(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::PopMatrix: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpPopMatrix(a[0]);break;}
        case UpdateStream::Geometry: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpGeometryMode(a[0],a[1]);break;}
        case UpdateStream::MoveWord: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpMovewordF3dex2(a[0],a[1],a[2]);break;}
        case UpdateStream::TextureScale: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpTexture(a[0],a[1],a[2],a[3],a[4]);break;}
        case UpdateStream::OtherLow: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpSetOtherMode(a[0],a[1],a[2]);break;}
        case UpdateStream::OtherHigh: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpSetOtherMode(a[0],a[1],uint64_t(a[2])<<32);break;}
        case UpdateStream::RdpOther: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetOtherMode(a[0],a[1]);break;}
        case UpdateStream::Combine: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetCombineMode(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::Grayscale: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->mRdp->grayscale=a[0];break;}
        case UpdateStream::InterpolationTarget: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->mInterpolationIndexTarget=a[0];break;}
        case UpdateStream::Intensity: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetGrayscaleColor(a[0],a[1],a[2],a[3]);break;}
        case UpdateStream::Marker: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->mMarkerOn=true;break;}
        case UpdateStream::DisplayAnnotation: { const unsigned* a=p.arguments[op.payload[0]].value;if(a[0]==7)g_exec_stack.openDisp((const char*)a[2],a[1]);
            else if(a[0]==8){if(g_exec_stack.disp_stack.empty())SPDLOG_WARN("CLOSE_DISPS without matching open {}:{}",a[0],a[1]);else g_exec_stack.closeDisp();}break;}
        case UpdateStream::ResetFog: { const unsigned* a=p.arguments[op.payload[0]].value;CampaignDeferredState::snapshot.Invalidate();gfx->mRsp->fog_mul=0;gfx->mRsp->fog_offset=0;break;}
        case UpdateStream::NoWork: { const unsigned* a=p.arguments[op.payload[0]].value;break;}
        case UpdateStream::SpNoop: { const unsigned* a=p.arguments[op.payload[0]].value;break;}
        case UpdateStream::CullNoop: { const unsigned* a=p.arguments[op.payload[0]].value;break;}
        case UpdateStream::PrimDepthNoop: { const unsigned* a=p.arguments[op.payload[0]].value;break;}
        case UpdateStream::Triangle: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpTri1(a[0],a[1],a[2],false);break;}
        case UpdateStream::Quad: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxSpTri1(a[0],a[1],a[2],false);gfx->GfxSpTri1(a[3],a[4],a[5],false);break;}
        case UpdateStream::Directory: { const unsigned* a=p.arguments[op.payload[0]].value;break;}
        case UpdateStream::DepthImage: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetZImage((void*)a[0]);break;}
        case UpdateStream::ColorImage: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpSetColorImage(a[0],a[1],a[2],(void*)a[3]);break;}
        case UpdateStream::WideFill: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpFillRectangle(int32_t(a[0]),int32_t(a[1]),int32_t(a[2]),int32_t(a[3]));break;}
        case UpdateStream::WideTexture: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpTextureRectangle(int32_t(a[0]),int32_t(a[1]),int32_t(a[2]),int32_t(a[3]),a[4],a[5],a[6],a[7],a[8],a[9]);break;}
        case UpdateStream::InterpolatedTile: { const unsigned* a=p.arguments[op.payload[0]].value;if(gfx->mInterpolationIndex==gfx->mInterpolationIndexTarget){
             gfx->GfxDpSetTileSize(a[0],a[1],a[2],a[3],a[4]);
             memcpy(&gfx->mRdp->texture_tile[a[0]].uls,a+5,4);memcpy(&gfx->mRdp->texture_tile[a[0]].ult,a+6,4);
             memcpy(&gfx->mRdp->texture_tile[a[0]].lrs,a+7,4);memcpy(&gfx->mRdp->texture_tile[a[0]].lrt,a+8,4);}break;}
        case UpdateStream::InvalidateTexture: { const unsigned* a=p.arguments[op.payload[0]].value;if(a[0]==0)gfx->TextureCacheClear();else gfx->TextureCacheDelete((const uint8_t*)a[0]);break;}
        case UpdateStream::TextureRectangle: { const unsigned* a=p.arguments[op.payload[0]].value;gfx->GfxDpTextureRectangle(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9]);break;}
        case UpdateStream::Matrix:gfx->GfxSpMatrix(op.payload[0],(const int32_t*)op.payload[1]);break;
        case UpdateStream::MoveMemory:gfx->GfxSpMovememF3dex2(op.payload[0],op.payload[1],(const void*)op.payload[2]);break;
        default: break; // Generic packets are rejected before execution.
        }
        if(ModernFrameProfile::commandSampler.enabled)ModernFrameProfile::commandSampler.End(sample);
        CAMPAIGN_DIAGNOSTIC_COUNT(++p.replayed;);
    }
    CAMPAIGN_DIAGNOSTIC_COUNT(p.commands+=p.instructions.size();p.repeated+=p.instructions.size(););p.cursor=unsigned(p.instructions.size());
    while(!g_exec_stack.cmd_stack.empty())g_exec_stack.cmd_stack.pop();
    g_exec_stack.gfx_path.clear();
    return true;
}

static void gfx_step() {
    if(StreamEntryCounts::enabled)++StreamEntryCounts::walk[StreamEntryCounts::bucket];
    auto& cmd = g_exec_stack.currCmd();
    auto cmd0 = cmd;
    int8_t opcode = (int8_t)(cmd->words.w0 >> 24);
    UpdateStream::Observe(cmd,unsigned(ucode_handler_index));

    if(ucode_handler_index!=UcodeHandlers::ucode_f3dex2 ||
        (uint8_t(opcode)!=F3DEX2_G_TRI1 && uint8_t(opcode)!=F3DEX2_G_TRI2 &&
         uint8_t(opcode)!=F3DEX2_G_VTX && uint8_t(opcode)!=0x32 &&
         uint8_t(opcode)!=F3DEX2_G_MTX && uint8_t(opcode)!=F3DEX2_G_POPMTX))
        CampaignOwnerGeneration::certificate.Mutate();

    if(opcode != F3DEX2_G_TRI2 || ucode_handler_index != UcodeHandlers::ucode_f3dex2)
        CampaignTriRun::cache.Reset();

#ifdef USE_GBI_TRACE
    if (cmd->words.trace.valid &&
        Ship::Context::GetInstance()->GetConsoleVariables()->GetInteger("gEnableGFXTrace", 0)) {
#define TRACE                                  \
    "\n====================================\n" \
    " - CMD: {:02X}\n"                         \
    " - Path: {}:{}\n"                         \
    " - W0: {:08X}\n"                          \
    " - W1: {:08X}\n"                          \
    "===================================="
        SPDLOG_INFO(TRACE, (uint8_t)opcode, cmd->words.trace.file, cmd->words.trace.idx, cmd->words.w0, cmd->words.w1);
    }
#endif

    if (opcode == F3DEX2_G_LOAD_UCODE) {
        gfx_set_ucode_handler((UcodeHandlers)(cmd->words.w0 & 0xFFFFFF));
        ++cmd;
        return;
        // Instead of having a handler for each ucode for switching ucode, just check for it early and return.
    }

    if (ucode_handler_index < ucode_handlers.size()) {
        const auto& handler = ucode_handlers[ucode_handler_index]->at(opcode);
        if (handler.first) {
            const bool moved=handler.second(&cmd);
            CapturePreparedHandler(handler.second,cmd0,handler.second==gfx_end_dl_handler_common?cmd0:cmd);
            if(moved)return;
        } else {
            SPDLOG_CRITICAL("Unhandled OP code: 0x{:X}, for loaded ucode: {}", (uint8_t)opcode,
                            (uint32_t)ucode_handler_index);
        }
    } else {
        // Invalid ucode retains the independent OTR/RDP dispatch paths.
        if (otrHandlers.contains(opcode)) {
            if (otrHandlers.at(opcode).second(&cmd)) return;
        } else if (rdpHandlers.contains(opcode)) {
            if (rdpHandlers.at(opcode).second(&cmd)) return;
        } else {
            SPDLOG_CRITICAL("Unhandled OP code: 0x{:X}, invalid ucode: {}", (uint8_t)opcode,
                            (uint32_t)ucode_handler_index);
        }
    }

    ++cmd;
}

void Interpreter::SpReset() {
    (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
    EnsureMatrixProduct();
    mRsp->modelview_matrix_stack_size = 1;
    mRsp->current_num_lights = 2;
    CampaignDeferredState::snapshot.Invalidate(); mRsp->lights_changed = true;
    mRsp->lookat[0].dir[0] = 0;
    mRsp->lookat[0].dir[1] = 127;
    mRsp->lookat[0].dir[2] = 0;
    mRsp->lookat[1].dir[0] = 127;
    mRsp->lookat[1].dir[1] = 0;
    mRsp->lookat[1].dir[2] = 0;
    CalculateNormalDir(&mRsp->lookat[0], mRsp->current_lookat_coeffs[0]);
    CalculateNormalDir(&mRsp->lookat[1], mRsp->current_lookat_coeffs[1]);
}

void Interpreter::GetDimensions(uint32_t* width, uint32_t* height, int32_t* posX, int32_t* posY) {
    mWapi->GetDimensions(width, height, posX, posY);
}

void Interpreter::Init(class GfxWindowBackend* wapi, class GfxRenderingAPI* rapi, const char* game_name,
                       bool start_in_fullscreen, uint32_t width, uint32_t height, uint32_t posX, uint32_t posY) {
    mWapi = wapi;
    mRapi = rapi;
    (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
    mWapi->Init(game_name, rapi->GetName(), start_in_fullscreen, width, height, posX, posY);
    (mXboxPipelineKey.valid=false, mRapi->Init());
    mXboxClipParameters = mRapi->GetClipParameters();
    for (std::map<ColorCombinerKey, ColorCombiner>::iterator entry = mColorCombinerPool.begin();
         entry != mColorCombinerPool.end(); ++entry) {
        entry->second.xboxShaderMetadata.Invalidate();
    }
    (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(0, width, height, 1, false, true, true, true));
    mCurDimensions.internal_mul =
        Ship::Context::GetInstance()->GetConsoleVariables()->GetFloat(CVAR_INTERNAL_RESOLUTION, 1);
    mMsaaLevel = Ship::Context::GetInstance()->GetConsoleVariables()->GetInteger(CVAR_MSAA_VALUE, 1);

    mCurDimensions.width = width;
    mCurDimensions.height = height;

    mGameFb = mRapi->CreateFramebuffer();
    mGameFbMsaaResolved = mRapi->CreateFramebuffer();

    mNativeDimensions.width = SCREEN_WIDTH;
    mNativeDimensions.height = SCREEN_HEIGHT;

    for (int i = 0; i < MAX_SEGMENT_POINTERS; i++) {
        mSegmentPointers[i] = 0;
    }

    if (mTexUploadBuffer == nullptr) {
        // We cap texture max to 8k, because why would you need more?
        int max_tex_size = std::min(8192, mRapi->GetMaxTextureSize());
        mTexUploadBuffer = (uint8_t*)malloc(max_tex_size * max_tex_size * 4);
    }

    ucode_handler_index = UcodeHandlers::ucode_f3dex2;
}

void Interpreter::Destroy() {
    // TODO: should also destroy rapi, and any other resources acquired in fast3d
    free(mTexUploadBuffer);
    mWapi->Destroy();

    // Texture cache and loaded textures store references to Resources which need to be unreferenced.
    TextureCacheClear();
    mRdp->texture_to_load.raw_tex_metadata.resource = nullptr;
    mRdp->loaded_texture[0].raw_tex_metadata.resource = nullptr;
    mRdp->loaded_texture[1].raw_tex_metadata.resource = nullptr;
}

GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI() {
    Flush();
    (mXboxTextureBindings.Invalidate(), mXboxPipelineKey.valid=false);
    return mRapi;
}

void Interpreter::HandleWindowEvents() {
    mWapi->HandleEvents();
}

bool Interpreter::IsFrameReady() {
    return mWapi->IsFrameReady();
}

bool Interpreter::ViewportMatchesRendererResolution() {
#ifdef __APPLE__
    // Always treat the viewport as not matching the render resolution on mac
    // to avoid issues with retina scaling.
    return false;
#else
    if (mCurDimensions.width == mGameWindowViewport.width && mCurDimensions.height == mGameWindowViewport.height) {
        return true;
    }
    return false;
#endif
}

void Interpreter::StartFrame() {
    mWapi->GetDimensions(&mGfxCurrentWindowDimensions.width, &mGfxCurrentWindowDimensions.height, &mCurWindowPosX,
                         &mCurWindowPosY);
    if (mCurDimensions.height == 0) {
        // Avoid division by zero
        mCurDimensions.height = 1;
    }
    mCurDimensions.aspect_ratio = (float)mCurDimensions.width / (float)mCurDimensions.height;

    // Update the framebuffer sizes when the viewport or native dimension changes
    if (mCurDimensions.width != mPrvDimensions.width || mCurDimensions.height != mPrvDimensions.height ||
        mNativeDimensions.width != mPrevNativeDimensions.width ||
        mNativeDimensions.height != mPrevNativeDimensions.height) {

        { auto&& _configRange163317 = mFrameBuffers; auto _configIt163317 = Shipyard::Resources::begin(_configRange163317); auto _configEnd163317 = Shipyard::Resources::end(_configRange163317); for (; _configIt163317 != _configEnd163317; ++_configIt163317) { auto& fb = *_configIt163317; 
            uint32_t width = fb.second.orig_width, height = fb.second.orig_height;
            if (fb.second.resize) {
                AdjustWidthHeightForScale(width, height, fb.second.native_width, fb.second.native_height);
            }
            if (width != fb.second.applied_width || height != fb.second.applied_height) {
                (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(fb.first, width, height, 1, true, true, true, true));
                fb.second.applied_width = width;
                fb.second.applied_height = height;
            }
         } }
    }

    mPrvDimensions = mCurDimensions;
    mPrevNativeDimensions = mNativeDimensions;
    if (!ViewportMatchesRendererResolution() || mMsaaLevel > 1) {
        mRendersToFb = true;
        if (!ViewportMatchesRendererResolution()) {
            (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(mGameFb, mCurDimensions.width, mCurDimensions.height, mMsaaLevel, true,
                                               true, true, true));
        } else {
            // MSAA framebuffer needs to be resolved to an equally sized target when complete, which must therefore
            // match the window size
            (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(mGameFb, mGfxCurrentWindowDimensions.width,
                                               mGfxCurrentWindowDimensions.height, mMsaaLevel, false, true, true, true));
        }
        if (mMsaaLevel > 1 && !ViewportMatchesRendererResolution()) {
            (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(mGameFbMsaaResolved, mCurDimensions.width, mCurDimensions.height, 1,
                                               false, false, false, false));
        }
    } else {
        mRendersToFb = false;
    }

    mFbActive = false;
}

GfxExecStack g_exec_stack = {};

void Interpreter::RunGuiOnly() {
    mXboxTextureHashCache.Clear();
    SpReset();

    mGetPixelDepthPending.clear();
    mGetPixelDepthCached.clear();

    (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(0, mGfxCurrentWindowDimensions.width, mGfxCurrentWindowDimensions.height, 1,
                                       false, true, true, !mRendersToFb));
    (mXboxPipelineKey.valid=false, mRapi->StartFrame());
    (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(mRendersToFb ? mGameFb : 0, (float)mCurDimensions.height / mNativeDimensions.height));
    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(false, true));
    mRdp->viewport_or_scissor_changed = true;
    { XYWidthHeight shipyardAggregate = {}; mRenderingState.viewport = shipyardAggregate; }
    { XYWidthHeight shipyardAggregate = {}; mRenderingState.scissor = shipyardAggregate; }

    Flush();
    mGfxFrameBuffer = 0;

    if (mRendersToFb) {
        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));
        (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(true, true));
        if (mMsaaLevel > 1) {
            if (!ViewportMatchesRendererResolution()) {
                (mXboxPipelineKey.valid=false, mRapi->ResolveMSAAColorBuffer(mGameFbMsaaResolved, mGameFb));
                mGfxFrameBuffer = (uintptr_t)mRapi->GetFramebufferTextureId(mGameFbMsaaResolved);
            } else {
                (mXboxPipelineKey.valid=false, mRapi->ResolveMSAAColorBuffer(0, mGameFb));
            }
        } else {
            mGfxFrameBuffer = (uintptr_t)mRapi->GetFramebufferTextureId(mGameFb);
        }
    } else if (mFbActive) {
        // Failsafe reset to main framebuffer to prevent softlocking the renderer
        mFbActive = 0;
        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));

        assert(0 && "active framebuffer was never reset back to original");
    }
}

void Interpreter::Run(Gfx* commands, const std::unordered_map<Mtx*, MtxF>& mtx_replacements) {
    sModernCullRoundingBatch = CVarGetInteger("gSettings.XboxCullRoundingBatch", 1) != 0;
    CampaignDeferredState::snapshot.Invalidate();
    CampaignLightMath::mode=CVarGetInteger("gSettings.XboxCampaignLightMath",0);
    CampaignOwnerGeneration::ownersMode=CVarGetInteger("gSettings.XboxCampaignRunOwners",0);
    CampaignOwnerGeneration::generationMode=CVarGetInteger("gSettings.XboxCampaignGeneration",0);
    CampaignOwnerGeneration::Scope serviceOwners;
    CampaignOwnerGeneration::certificate.Mutate();
    CampaignOwnerGeneration::certificate.owner=NULL;
    CampaignOwnerGeneration::Certificate& cert=CampaignOwnerGeneration::certificate;
    if(++cert.presentations==360) {
        SPDLOG_INFO("pipeline-generation mode={} attempts={} hits={} avoided_comparisons={} oracle_checks={} oracle_failures={} owners={}",
            CampaignOwnerGeneration::generationMode,cert.attempts,cert.hits,cert.avoidedComparisons,cert.oracleChecks,cert.oracleFailures,CampaignOwnerGeneration::ownersMode);
        SPDLOG_INFO("light-math mode={} calls={} fallbacks={} checks={} mismatches={}",CampaignLightMath::mode,CampaignLightMath::calls,CampaignLightMath::fallbacks,CampaignLightMath::checks,CampaignLightMath::mismatches);
        CampaignLightMath::calls=CampaignLightMath::fallbacks=CampaignLightMath::checks=CampaignLightMath::mismatches=0;
        cert.presentations=0;
        cert.attempts=cert.hits=cert.avoidedComparisons=cert.oracleChecks=cert.oracleFailures=0;
    }


    CampaignTriRun::Rows& runCache=CampaignTriRun::cache;
    runCache.Reset();
    runCache.mode=CVarGetInteger("gSettings.XboxCampaignTriRun",0);
    sCampaignVtxBatch=CVarGetInteger("gSettings.XboxCampaignVtxBatch",0);
    if(++runCache.presentations == 360) {
        SPDLOG_INFO("tri-run mode={} rows={} hits={} triangles={} full={} checks={} mismatches={}",
            runCache.mode,runCache.rows,runCache.hits,runCache.triangles,runCache.full,
            runCache.checks,runCache.mismatches);
        SPDLOG_INFO("vtx-batch mode={} batches={} fallbacks={} checks={} mismatches={}",sCampaignVtxBatch,sCampaignVtxBatches,sCampaignVtxFallbacks,sCampaignVtxChecks,sCampaignVtxMismatches);
        sCampaignVtxBatches=sCampaignVtxFallbacks=sCampaignVtxChecks=sCampaignVtxMismatches=0;
        CampaignDeferredState::Snapshot& state=CampaignDeferredState::snapshot;
        SPDLOG_INFO("deferred-state mode={} reused={} created={} checks={} mismatches={}",
            sCampaignVtxBatch,state.reused,state.created,state.checks,state.failures);
        state.reused=state.created=state.checks=state.failures=0;
        CampaignPreparedPack::Layout& pack=CampaignPreparedPack::layout;
        SPDLOG_INFO("prepared-pack mode={} triangles={} misses={} checks={} mismatches={}",
            runCache.mode,pack.triangles,pack.misses,pack.checks,pack.failures);
        pack.triangles=pack.misses=pack.checks=pack.failures=0;
        runCache.presentations=0;runCache.rows=runCache.hits=runCache.triangles=runCache.full=0;
        SPDLOG_INFO("tri-run additional_rows={}",runCache.additional);
        runCache.additional=0;
        runCache.checks=runCache.mismatches=0;
    }

    mXboxContextProbeCapture = ModernFrameProfile::CaptureTrianglePipeline();
    mXboxContextSearchAttempts = mXboxContextSlotsScanned = mXboxContextMaxScan = 0;
    ModernFrameProfile::Begin(ModernFrameProfile::InterpreterSetup);
    SpReset();

    mGetPixelDepthPending.clear();
    mGetPixelDepthCached.clear();

    mCurMtxReplacements = &mtx_replacements;

    (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(0, mGfxCurrentWindowDimensions.width, mGfxCurrentWindowDimensions.height, 1,
                                       false, true, true, !mRendersToFb));
    mXboxTileTrialEnabled =
        CVarGetInteger("gSettings.XboxTileStateDedupTrialProfile", 0) != 0;
    mXboxTileCaptureEnabled = ModernFrameProfile::CaptureResourceLookups() &&
        CVarGetInteger("gSettings.XboxTileStateDedupCaptureProfile", 0) != 0;
    Fast::ShipyardXenos::SetTilingGuardTrialEnabled(
        CVarGetInteger("gSettings.XboxTilingGuardTrialProfile", 0) != 0);
    Fast::ShipyardXenos::SetTile1PredicationTrialEnabled(
        CVarGetInteger("gSettings.XboxTile1PredicationTrialProfile", 0) != 0);
    (mXboxPipelineKey.valid=false, mRapi->StartFrame());
    (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(mRendersToFb ? mGameFb : 0, (float)mCurDimensions.height / mNativeDimensions.height));
    const bool xboxFullColorClear =
        CVarGetInteger("gSettings.XboxFullColorClearProfile", 0) != 0;
    mXboxCanDiscardGameColor =
        mRendersToFb && mMsaaLevel == 1 && !xboxFullColorClear;
    mXboxPipelineKey.valid = false;
    if (mXboxCanDiscardGameColor)
        Fast::ShipyardXenos::BeginGameFramebufferDepthClear();
    else
        mRapi->ClearFramebuffer(xboxFullColorClear, true);
    mRdp->viewport_or_scissor_changed = true;
    { XYWidthHeight shipyardAggregate = {}; mRenderingState.viewport = shipyardAggregate; }
    { XYWidthHeight shipyardAggregate = {}; mRenderingState.scissor = shipyardAggregate; }

    auto dbg = Ship::Context::GetInstance()->GetGfxDebugger();
    {
    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);
    g_exec_stack.start((F3DGfx*)commands);
    UpdateStream::BeginPass(mInterpolationIndex);
    ModernFrameProfile::End(ModernFrameProfile::InterpreterSetup);
    ModernFrameProfile::Begin(ModernFrameProfile::CommandWalk);
    if(dbg->IsDebugging() || !ReplayPreparedUpdate(this))
    while (!g_exec_stack.cmd_stack.empty()) {
        auto cmd = g_exec_stack.cmd_stack.top();

        if (dbg->IsDebugging()) {
            g_exec_stack.gfx_path.push_back(cmd);
            if (dbg->HasBreakPoint(g_exec_stack.gfx_path)) {
                // On a breakpoint with the active framebuffer still set, we need to reset back to prevent
                // soft locking the renderer
                if (mFbActive) {
                    mFbActive = 0;
                    (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(mRendersToFb ? mGameFb : 0, 1));
                }

                break;
            }
            g_exec_stack.gfx_path.pop_back();
        }
        if (ModernFrameProfile::commandSampler.enabled) {
            const ModernFrameProfile::CommandSampler::Token sample =
                ModernFrameProfile::commandSampler.Begin(static_cast<unsigned>(cmd->words.w0 >> 24),
                                                          static_cast<unsigned>(ucode_handler_index));
            gfx_step();
            ModernFrameProfile::commandSampler.End(sample);
        } else {
            gfx_step();
        }
    }
    }

    if(UpdateStream::packet.active && UpdateStream::packet.recording) {
        UpdateStream::packet.resourceGeneration=XboxRunResourceManager()->GetXboxLookupGeneration();
        UpdateStream::packet.archiveEpoch=XboxRunArchiveManager()->GetXboxHashEpoch();
    }
    UpdateStream::EndPass();
    ModernFrameProfile::End(ModernFrameProfile::CommandWalk);
    ModernFrameProfile::Begin(ModernFrameProfile::InterpreterFinish);
    Flush();
    StreamOutputOracle::End();
    mGfxFrameBuffer = 0;


    if (mRendersToFb) {
        if (mXboxDiscardGameDepth) Fast::ShipyardXenos::DiscardFramebufferDepth(mGameFb);
        mXboxDiscardGameDepth = false;
        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));
        (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(true, true));
        if (mMsaaLevel > 1) {
            if (!ViewportMatchesRendererResolution()) {
                (mXboxPipelineKey.valid=false, mRapi->ResolveMSAAColorBuffer(mGameFbMsaaResolved, mGameFb));
                mGfxFrameBuffer = (uintptr_t)mRapi->GetFramebufferTextureId(mGameFbMsaaResolved);
            } else {
                (mXboxPipelineKey.valid=false, mRapi->ResolveMSAAColorBuffer(0, mGameFb));
            }
        } else {
            mGfxFrameBuffer = (uintptr_t)mRapi->GetFramebufferTextureId(mGameFb);
        }
    } else if (mFbActive) {
        // Failsafe reset to main framebuffer to prevent softlocking the renderer
        mFbActive = 0;
        (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, 1));

        assert(0 && "active framebuffer was never reset back to original");
    }
    ModernFrameProfile::End(ModernFrameProfile::InterpreterFinish);
}

void Interpreter::EndFrame() {
    // Direct 720p rendering needs depth only after the final replay.
    if (mRendersToFb || mXboxDiscardGameDepth)
        Fast::ShipyardXenos::DiscardPresentationDepthOnEnd();
    if (mRendersToFb) {
        Fast::ShipyardXenos::DiscardPresentationColorOnEnd();
    }
    ModernFrameProfile::Begin(ModernFrameProfile::PresentEndFrame);
    (mXboxPipelineKey.valid=false, mRapi->EndFrame());
    ModernFrameProfile::End(ModernFrameProfile::PresentEndFrame);
    ModernFrameProfile::Begin(ModernFrameProfile::PresentSwapBegin);
    mWapi->SwapBuffersBegin();
    ModernFrameProfile::End(ModernFrameProfile::PresentSwapBegin);
    ModernFrameProfile::Begin(ModernFrameProfile::PresentFinishRender);
    (mXboxPipelineKey.valid=false, mRapi->FinishRender());
    ModernFrameProfile::End(ModernFrameProfile::PresentFinishRender);
    ModernFrameProfile::Begin(ModernFrameProfile::PresentSwapEnd);
    mWapi->SwapBuffersEnd();
    ModernFrameProfile::End(ModernFrameProfile::PresentSwapEnd);
}

void gfx_set_target_ucode(UcodeHandlers ucode) {
    ucode_handler_index = ucode;
}

int Interpreter::GetTargetFps() {
    return mWapi->GetTargetFps();
}

void Interpreter::SetTargetFps(int fps) {
    mWapi->SetTargetFps(fps);
}

void Interpreter::SetMaxFrameLatency(int latency) {
    mWapi->SetMaxFrameLatency(latency);
}

int Interpreter::CreateFrameBuffer(uint32_t width, uint32_t height, uint32_t native_width, uint32_t native_height,
                                   uint8_t resize) {
    uint32_t orig_width = width, orig_height = height;
    if (resize) {
        AdjustWidthHeightForScale(width, height, native_width, native_height);
    }

    int fb = mRapi->CreateFramebuffer();
    (mXboxPipelineKey.valid=false, mRapi->UpdateFramebufferParameters(fb, width, height, 1, true, true, true, true));

    { FBInfo shipyardAggregate = {
        orig_width, orig_height, width, height, native_width, native_height, static_cast<bool>(resize)
    }; mFrameBuffers[fb] = shipyardAggregate; }
    return fb;
}

void Interpreter::SetFrameBuffer(int fb, float noiseScale) {
    mXboxCanDiscardGameColor = false;
    (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(fb, noiseScale));
    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(false, true));
}

void Interpreter::CopyFrameBuffer(int fb_dst_id, int fb_src_id, bool copyOnce, bool* hasCopiedPtr) {
    mXboxCanDiscardGameColor = false;
    // Do not copy again if we have already copied before
    if (copyOnce && hasCopiedPtr != nullptr && *hasCopiedPtr) {
        return;
    }

    if (fb_src_id == 0 && mRendersToFb) {
        // read from the framebuffer we've been rendering to
        fb_src_id = mGameFb;
    }

    int srcX0, srcY0, srcX1, srcY1;
    int dstX0, dstY0, dstX1, dstY1;

    // When rendering to the main window buffer or MSAA is enabled with a buffer size equal to the view port,
    // then the source coordinates must account for any docked ImGui elements
    if (fb_src_id == 0 || (mMsaaLevel > 1 && mCurDimensions.width == mGameWindowViewport.width &&
                           mCurDimensions.height == mGameWindowViewport.height)) {
        srcX0 = mGameWindowViewport.x;
        srcY0 = mGameWindowViewport.y;
        srcX1 = mGameWindowViewport.x + mGameWindowViewport.width;
        srcY1 = mGameWindowViewport.y + mGameWindowViewport.height;
    } else {
        srcX0 = 0;
        srcY0 = 0;
        srcX1 = mCurDimensions.width;
        srcY1 = mCurDimensions.height;
    }

    dstX0 = 0;
    dstY0 = 0;
    dstX1 = mCurDimensions.width;
    dstY1 = mCurDimensions.height;

    (mXboxPipelineKey.valid=false, mRapi->CopyFramebuffer(fb_dst_id, fb_src_id, srcX0, srcY0, srcX1, srcY1, dstX0, dstY0, dstX1, dstY1));

    // Set the copied pointer if we have one
    if (hasCopiedPtr != nullptr) {
        *hasCopiedPtr = true;
    }
}

void Interpreter::ResetFrameBuffer() {
    (mXboxPipelineKey.valid=false, mRapi->StartDrawToFramebuffer(0, (float)mCurDimensions.height / mNativeDimensions.height));
}

void Interpreter::AdjustPixelDepthCoordinates(float& x, float& y) {
    x = x * RATIO_X(mActiveFrameBuffer, mCurDimensions) -
        (mNativeDimensions.width * RATIO_X(mActiveFrameBuffer, mCurDimensions) - mCurDimensions.width) / 2;
    y *= RATIO_Y(mActiveFrameBuffer, mCurDimensions);
    if (!mRendersToFb || (mMsaaLevel > 1 && mCurDimensions.width == mGameWindowViewport.width &&
                          mCurDimensions.height == mGameWindowViewport.height)) {
        x += mGameWindowViewport.x;
        y += mGfxCurrentWindowDimensions.height - (mGameWindowViewport.y + mGameWindowViewport.height);
    }
}

void Interpreter::GetPixelDepthPrepare(float x, float y) {
    AdjustPixelDepthCoordinates(x, y);
    mGetPixelDepthPending.insert(std::make_pair(x, y));
}

uint16_t Interpreter::GetPixelDepth(float x, float y) {
    AdjustPixelDepthCoordinates(x, y);

    { auto it = mGetPixelDepthCached.find(std::make_pair(x, y)); if (it != mGetPixelDepthCached.end()) {
        return it->second;
    } }

    mGetPixelDepthPending.insert(std::make_pair(x, y));

    std::unordered_map<std::pair<float, float>, uint16_t, hash_pair_ff> res =
        mRapi->GetPixelDepth(mRendersToFb ? mGameFb : 0, mGetPixelDepthPending);
    mGetPixelDepthCached.insert(res.begin(), res.end());
    mGetPixelDepthPending.clear();

    return mGetPixelDepthCached.find(std::make_pair(x, y))->second;
}

void gfx_push_current_dir(char* path) {
    (void)gfx_check_image_signature(path);
}

int32_t gfx_check_image_signature(const char* imgData) {
    uintptr_t i = (uintptr_t)(imgData);

    if ((i & 1) == 1) {
        return 0;
    }

    if (i != 0) {
        return std::strncmp(imgData, "__OTR__", 7) == 0;
    }

    return 0;
}

void Interpreter::RegisterBlendedTexture(const char* name, uint8_t* mask, uint8_t* replacement) {
    if (gfx_check_image_signature(name)) {
        name += 7;
    }

    if (gfx_check_image_signature(reinterpret_cast<char*>(replacement))) {
        Fast::Texture* tex = std::static_pointer_cast<Fast::Texture>(
                                 Ship::Context::GetInstance()->GetResourceManager()->LoadResourceProcess(
                                     reinterpret_cast<char*>(replacement)))
                                 .get();

        replacement = tex->ImageData;
    }

    MaskedTextureEntry entry = { mask, replacement };
    mMaskedTextures[name] = entry;
}

void Interpreter::UnregisterBlendedTexture(const char* name) {
    if (gfx_check_image_signature(name)) {
        name += 7;
    }

    mMaskedTextures.erase(name);
}

// New getters and setters
void Interpreter::SetNativeDimensions(float width, float height) {
    mNativeDimensions.width = width;
    mNativeDimensions.height = height;
}

void Interpreter::SetResolutionMultiplier(float multiplier) {
    mCurDimensions.internal_mul = multiplier;
}

void Interpreter::SetMsaaLevel(uint32_t level) {
    mMsaaLevel = level;
}

void Interpreter::GetCurDimensions(uint32_t* width, uint32_t* height) {
    *width = mCurDimensions.width;
    *height = mCurDimensions.height;
}

} // namespace Fast

void gfx_cc_get_features(uint64_t shader_id0, uint32_t shader_id1, struct CCFeatures* cc_features) {
    for (int i = 0; i < 2; i++) {
        for (int j = 0; j < 2; j++) {
            for (int k = 0; k < 4; k++) {
                cc_features->c[i][j][k] = shader_id0 >> i * 32 + j * 16 + k * 4 & 0xf;
            }
        }
    }

    cc_features->opt_alpha = (shader_id1 & SHADER_OPT(ALPHA)) != 0;
    cc_features->opt_fog = (shader_id1 & SHADER_OPT(FOG)) != 0;
    cc_features->opt_texture_edge = (shader_id1 & SHADER_OPT(TEXTURE_EDGE)) != 0;
    cc_features->opt_noise = (shader_id1 & SHADER_OPT(NOISE)) != 0;
    cc_features->opt_2cyc = (shader_id1 & SHADER_OPT(_2CYC)) != 0;
    cc_features->opt_alpha_threshold = (shader_id1 & SHADER_OPT(ALPHA_THRESHOLD)) != 0;
    cc_features->opt_invisible = (shader_id1 & SHADER_OPT(INVISIBLE)) != 0;
    cc_features->opt_grayscale = (shader_id1 & SHADER_OPT(GRAYSCALE)) != 0;

    cc_features->clamp[0][0] = shader_id1 & SHADER_OPT(TEXEL0_CLAMP_S);
    cc_features->clamp[0][1] = shader_id1 & SHADER_OPT(TEXEL0_CLAMP_T);
    cc_features->clamp[1][0] = shader_id1 & SHADER_OPT(TEXEL1_CLAMP_S);
    cc_features->clamp[1][1] = shader_id1 & SHADER_OPT(TEXEL1_CLAMP_T);

    if (shader_id1 & SHADER_OPT(USE_SHADER)) {
        cc_features->shader_id = (shader_id1 >> 17) & 0xFFFF;
    }

    cc_features->usedTextures[0] = false;
    cc_features->usedTextures[1] = false;
    cc_features->used_masks[0] = false;
    cc_features->used_masks[1] = false;
    cc_features->used_blend[0] = false;
    cc_features->used_blend[1] = false;
    cc_features->numInputs = 0;

    for (int c = 0; c < 2; c++) {
        for (int i = 0; i < 2; i++) {
            for (int j = 0; j < 4; j++) {
                if (cc_features->c[c][i][j] >= SHADER_INPUT_1 && cc_features->c[c][i][j] <= SHADER_INPUT_7) {
                    if (cc_features->c[c][i][j] > cc_features->numInputs) {
                        cc_features->numInputs = cc_features->c[c][i][j];
                    }
                }
                if (cc_features->c[c][i][j] == SHADER_TEXEL0 || cc_features->c[c][i][j] == SHADER_TEXEL0A) {
                    cc_features->usedTextures[0] = true;
                    if (cc_features->opt_2cyc) {
                        cc_features->usedTextures[1] = true;
                    }
                }
                if (cc_features->c[c][i][j] == SHADER_TEXEL1 || cc_features->c[c][i][j] == SHADER_TEXEL1A) {
                    cc_features->usedTextures[1] = true;
                    if (cc_features->opt_2cyc) {
                        cc_features->usedTextures[0] = true;
                    }
                }
            }
        }
    }

    for (int c = 0; c < 2; c++) {
        cc_features->do_single[c][0] = cc_features->c[c][0][2] == SHADER_0;
        cc_features->do_single[c][1] = cc_features->c[c][1][2] == SHADER_0;
        cc_features->do_multiply[c][0] = cc_features->c[c][0][1] == SHADER_0 && cc_features->c[c][0][3] == SHADER_0;
        cc_features->do_multiply[c][1] = cc_features->c[c][1][1] == SHADER_0 && cc_features->c[c][1][3] == SHADER_0;
        cc_features->do_mix[c][0] = cc_features->c[c][0][1] == cc_features->c[c][0][3];
        cc_features->do_mix[c][1] = cc_features->c[c][1][1] == cc_features->c[c][1][3];
        cc_features->color_alpha_same[c] = (shader_id0 >> c * 32 & 0xffff) == (shader_id0 >> c * 32 + 16 & 0xffff);
    }

    if (cc_features->usedTextures[0] && shader_id1 & SHADER_OPT(TEXEL0_MASK)) {
        cc_features->used_masks[0] = true;
    }
    if (cc_features->usedTextures[1] && shader_id1 & SHADER_OPT(TEXEL1_MASK)) {
        cc_features->used_masks[1] = true;
    }

    if (cc_features->usedTextures[0] && shader_id1 & SHADER_OPT(TEXEL0_BLEND)) {
        cc_features->used_blend[0] = true;
    }
    if (cc_features->usedTextures[1] && shader_id1 & SHADER_OPT(TEXEL1_BLEND)) {
        cc_features->used_blend[1] = true;
    }
}

extern "C" int gfx_create_framebuffer(uint32_t width, uint32_t height, uint32_t native_width, uint32_t native_height,
                                      uint8_t resize) {
    return Fast::mInstance.lock().get()->CreateFrameBuffer(width, height, native_width, native_height, resize);
}

extern "C" void gfx_texture_cache_clear() {
    Fast::mInstance.lock().get()->TextureCacheClear();
}
