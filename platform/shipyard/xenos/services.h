#pragma once
#include <xtl.h>
#include <d3dx9.h>
#include <stdint.h>
#include <string>
void Shipyard_Log(const char*,...);
__declspec(noreturn) void Shipyard_Fatal(const char*,HRESULT);
inline void Shipyard_Check(HRESULT result,const char* operation){if(FAILED(result))Shipyard_Fatal(operation,result);}
double Shipyard_Time();
bool Shipyard_WriteFile(const char*,const void*,size_t);
bool Shipyard_VerifyFast3DReuse();
void Shipyard_SetGraphicsVerification(bool);
