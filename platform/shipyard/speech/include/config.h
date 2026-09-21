#pragma once
#define PACKAGE_VERSION "1.52.0"
#define HAVE_MKSTEMP 0
#define USE_ASYNC 0
#define USE_KLATT 1
#define USE_LIBPCAUDIO 0
#define USE_LIBSONIC 0
#define USE_MBROLA 0
#define USE_SPEECHPLAYER 0
#define __has_include(x) 0
#define __has_include_next(x) 0
#define PATH_ESPEAK_DATA "game:\\espeak-ng-data"
#define S_ISDIR(mode) (((mode) & _S_IFMT) == _S_IFDIR)
#include "speech/format.h"
#undef snprintf
#define snprintf ShipyardSpeechSnprintf
