#pragma once
#include "imgui.h"
void Shipyard_ImGuiRendererInit();
void Shipyard_ImGuiRendererNewFrame();
void Shipyard_ImGuiRendererShutdown();
void Shipyard_ImGuiRender(ImDrawData*);
void Shipyard_ImGuiPlatformInit();
void Shipyard_ImGuiPlatformShutdown();
void Shipyard_ImGuiPlatformNewFrame(unsigned width,unsigned height);
