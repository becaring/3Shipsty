#pragma once
#include <math.h>
/* Capture XDK's own double-operation/float-conversion semantics before its
 * function-like macros can bind to game locals named sin/cos or expand inside
 * declarations. Each argument is evaluated once at the function call. */
static __inline float Shipyard_XdkSinf(float value) { return sinf(value); }
static __inline float Shipyard_XdkCosf(float value) { return cosf(value); }
static __inline float Shipyard_XdkFloorf(float value) { return floorf(value); }
static __inline float Shipyard_XdkCeilf(float value) { return ceilf(value); }
static __inline float Shipyard_XdkFabsf(float value) { return fabsf(value); }
static __inline float Shipyard_XdkSqrtf(float value) { return sqrtf(value); }
static __inline float Shipyard_XdkFmodf(float left, float right) { return fmodf(left, right); }
#undef sinf
#undef cosf
#undef floorf
#undef ceilf
#undef fabsf
#undef sqrtf
#undef fmodf
#define sinf Shipyard_XdkSinf
#define cosf Shipyard_XdkCosf
#define floorf Shipyard_XdkFloorf
#define ceilf Shipyard_XdkCeilf
#define fabsf Shipyard_XdkFabsf
#define sqrtf Shipyard_XdkSqrtf
#define fmodf Shipyard_XdkFmodf
