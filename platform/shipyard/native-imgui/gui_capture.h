// Capture only during a render-owned handoff with game and synthesis idle.
#pragma once
#include "imgui.h"
#include <stdint.h>
namespace ModernOverlap { class GuiFrameCache; }
void Shipyard_ImGuiBeginCapture(ModernOverlap::GuiFrameCache* cache, bool suppressDraw = true);
bool Shipyard_ImGuiEndCapture();
bool Shipyard_ImGuiCaptureDrawData(ImDrawData* data);
uintptr_t Shipyard_ImGuiCaptureGameTexture(uintptr_t texture);
void Shipyard_ImGuiDrawCache(ModernOverlap::GuiFrameCache& cache, uintptr_t texture);
