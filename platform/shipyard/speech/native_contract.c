#include "config.h"
#include <stddef.h>
#include "speech.h"
#include "synthesize.h"
#ifndef ARCH_BIG
#error Xenon eSpeak must use its existing big-endian dictionary reader
#endif
/* Read the actual PPC COFF initializers; do not infer target layout from x64. */
unsigned int ShipyardSpeechABI[] = {
    sizeof(PHONEME_TAB), offsetof(PHONEME_TAB, mnemonic),
    offsetof(PHONEME_TAB, phflags), offsetof(PHONEME_TAB, program),
    sizeof(TUNE), offsetof(TUNE, spare2), sizeof(frame_t), sizeof(frame_t2),
    offsetof(frame_t, frflags), offsetof(frame_t, ffreq),
    offsetof(frame_t, length), offsetof(frame_t2, length),
    sizeof(short), sizeof(int), sizeof(void*), BYTE_ORDER
};
