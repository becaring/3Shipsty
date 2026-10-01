// Resource owners follow both recording and replay until their last CPU reader.
#pragma once
#include <memory>
#include "application/overlap.h"
namespace Ship { class IResource; }
void Shipyard_OverlapRetainResource(const std::shared_ptr<Ship::IResource>& resource);
inline std::shared_ptr<Ship::IResource> Shipyard_OverlapKeepResource(const std::shared_ptr<Ship::IResource>& resource) {
    Shipyard_OverlapRetainResource(resource);
    return resource;
}
