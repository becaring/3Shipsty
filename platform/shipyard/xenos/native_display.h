#pragma once
#include <xtl.h>
namespace Fast {
extern IDirect3DDevice9* xenos_device;
void InitializeNativeDisplay();
HRESULT PresentNativeStartupUI();
void BeginNativeGuiDraw();
void InvalidateNativeGuiState();
void ShutdownNativeDisplay();
}
