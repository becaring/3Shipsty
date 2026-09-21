#pragma once
#include "async/native.h"
void ShipyardAudioLog(const char* format, ...);
__declspec(noreturn) void ShipyardAudioFatal(const char* operation, HRESULT result);
double ShipyardAudioTime();
