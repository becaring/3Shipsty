#pragma once
#include <xtl.h>
namespace Fast {
extern IDirect3DDevice9* xenos_device;
void InitializeNativeDisplay();
void BeginNativeGuiDraw();
void InvalidateNativeGuiState();
void ShutdownNativeDisplay();
}
