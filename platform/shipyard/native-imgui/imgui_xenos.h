#pragma once
#include "imgui.h"
#include "services.h"
#include "native_display.h"
#include <vector>
#include <stdint.h>
void Shipyard_ImGuiRendererInit();
void Shipyard_ImGuiRendererNewFrame();
void Shipyard_ImGuiRendererShutdown();
void Shipyard_ImGuiRender(ImDrawData*);
ImTextureID Shipyard_ImGuiUploadRGBA(const unsigned char*,int,int);
void Shipyard_ImGuiDestroyTexture(ImTextureID);
void Shipyard_ImGuiPlatformInit();
void Shipyard_ImGuiPlatformShutdown();
void Shipyard_ImGuiPlatformNewFrame(unsigned width,unsigned height);
inline float Shipyard_FloatUnitU8(uint8_t value){return static_cast<float>(value)/255.0f;}
