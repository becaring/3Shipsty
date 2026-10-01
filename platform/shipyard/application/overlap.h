// C game hooks marshal renderer work and retain borrowed storage until replay ends.
#ifndef MODERN_APPLICATION_OVERLAP_H
#define MODERN_APPLICATION_OVERLAP_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
int Shipyard_OverlapIsGameWorker(void);
int Shipyard_OverlapDrawGui(int begin);
void Shipyard_OverlapFence(void);
int Shipyard_OverlapRunFrame(void (*runFrame)(void));
void Shipyard_OverlapShutdown(void);
typedef void (*ShipyardOverlapRelease)(void* owner, void* data, const char* file, int line);
int Shipyard_OverlapDeferRelease(ShipyardOverlapRelease release, void* owner, void* data,
                               const char* file, int line);
void Shipyard_OverlapReleaseArena(void* arena);
void Shipyard_OverlapRetryAllocation(void);
void Shipyard_OverlapSaveStateBoundary(int restoring);
void Shipyard_OverlapTouchWritableSpan(void* pointer, size_t bytes);
void Shipyard_OverlapRunOnRender(void (*callback)(void*), void* context);
int Shipyard_OverlapInputBlocked(unsigned kind, int* value);
int Shipyard_OverlapMasterQuest(uint32_t* value);
struct GraphicsContext;
void Shipyard_OverlapRunGraphCallback(struct GraphicsContext* graphics,
    void (*callback)(struct GraphicsContext*, void*), void* parameter);
#ifdef __cplusplus
}
#include <memory>
namespace Ship { class IResource; }
void Shipyard_OverlapRetainResource(const std::shared_ptr<Ship::IResource>& resource);
#endif
#endif
