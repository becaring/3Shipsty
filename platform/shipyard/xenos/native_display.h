#pragma once
#include <xtl.h>
#include <stdint.h>
namespace Fast {
extern IDirect3DDevice9* xenos_device;
void InitializeNativeDisplay();
void NativeDisplaySize(uint32_t* width, uint32_t* height);
HRESULT PresentNativeStartupUI();
void BeginNativeGuiDraw();
void InvalidateNativeGuiState();
void ShutdownNativeDisplay();
}
