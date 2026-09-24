#pragma once
#include "shipyard_imgui_xenos.h"
#include "services.h"
#include "native_display.h"
void Shipyard_ImGuiPlatformInit();
void Shipyard_ImGuiPlatformShutdown();
void Shipyard_ImGuiPlatformNewFrame(unsigned width,unsigned height,bool menuVisible);
void Shipyard_ImGuiPlatformDrawCursor();
