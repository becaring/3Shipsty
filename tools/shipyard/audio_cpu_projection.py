"""Freeze audio controls during synthesis and use VMX saturated lanes with exact results.
Scalar DSP handles partial overlap, unaligned data and gain mixes.
"""

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Audio CPU anchor drift: ' + old[:90])
    return text.replace(old, new)


CONTROLS = r'''
static __declspec(thread) int modernAudioCpuActive;
static __declspec(thread) float modernAudioCpuMaster;
static __declspec(thread) int modernAudioCpuOctave;
static __declspec(thread) int modernAudioCpuMirror;
void ModernAudioCpuBegin(void) {
    modernAudioCpuMaster = (float)CVarGetInteger(CVAR_SETTING("Volume.Master"), 40) / 100.0f;
    modernAudioCpuOctave = CVarGetInteger(CVAR_AUDIO("ExperimentalOctaveDrop"), 0);
    modernAudioCpuMirror = CVarGetInteger(CVAR_ENHANCEMENT("MirroredWorld"), 0);
    modernAudioCpuActive = 1;
}
void ModernAudioCpuEnd(void) { modernAudioCpuActive = 0; }
int ModernAudioCpuMirrored(void) {
    return modernAudioCpuActive ? modernAudioCpuMirror : CVarGetInteger(CVAR_ENHANCEMENT("MirroredWorld"), 0);
}
static float ModernAudioCpuMaster(void) {
    return modernAudioCpuActive ? modernAudioCpuMaster : (float)CVarGetInteger(CVAR_SETTING("Volume.Master"), 40) / 100.0f;
}
static int ModernAudioCpuOctave(void) {
    return modernAudioCpuActive ? modernAudioCpuOctave : CVarGetInteger(CVAR_AUDIO("ExperimentalOctaveDrop"), 0);
}
'''

VMX = r'''
#if defined(_XBOX) && defined(_M_PPC)
#include <vectorintrinsics.h>
static int ModernAudioCpuSaturate(int16_t* out, const int16_t* in, int bytes, int subtract) {
    uintptr_t output = (uintptr_t)out, input = (uintptr_t)in;
    int offset;
    if (bytes <= 0 || ((output | input | (uintptr_t)bytes) & 15)) return 0;
    /* Partial overlap has scalar sample-to-sample feedback. */
    if (output != input && output < input + bytes && input < output + bytes) return 0;
    for (offset = 0; offset < bytes; offset += 16) {
        __vector4 left = __lvx(out, offset);
        __vector4 right = __lvx(in, offset);
        __vector4 result = subtract ? __vsubshs(left, right) : __vaddshs(left, right);
        __stvx(result, out, offset);
    }
    return 1;
}
static int ModernAudioCpuInterleave(int16_t* out, const int16_t* left, const int16_t* right, int bytes) {
    uintptr_t output = (uintptr_t)out, l = (uintptr_t)left, r = (uintptr_t)right;
    int offset;
    if (bytes <= 0 || ((output | l | r | (uintptr_t)bytes) & 15)) return 0;
    if ((output < l + bytes && l < output + 2 * bytes) ||
        (output < r + bytes && r < output + 2 * bytes)) return 0;
    for (offset = 0; offset < bytes; offset += 16) {
        __vector4 a = __lvx(left, offset), b = __lvx(right, offset);
        __stvx(__vmrghh(a, b), out, offset * 2);
        __stvx(__vmrglh(a, b), out, offset * 2 + 16);
    }
    return 1;
}
#endif
'''


def game(name, text):
    if name == 'soh/src/code/audio_playback.c':
        text = once(text, '(float)CVarGetInteger(CVAR_SETTING("Volume.Master"), 40) / 100.0f', 'ModernAudioCpuMaster()')
        text = once(text, 'CVarGetInteger(CVAR_AUDIO("ExperimentalOctaveDrop"), 0)', 'ModernAudioCpuOctave()')
        text = once(text, '#include <libultraship/bridge.h>', '#include <libultraship/bridge.h>\n' + CONTROLS)
    elif name == 'soh/src/code/audio_synthesis.c':
        text = once(text, '#include "global.h"',
                    '#include "global.h"\nvoid ModernAudioCpuBegin(void);\n'
                    'void ModernAudioCpuEnd(void);\nint ModernAudioCpuMirrored(void);')
        text = once(text, '    cmdP = cmdStart;\n', '    ModernAudioCpuBegin();\n    cmdP = cmdStart;\n')
        text = once(text, '    *cmdCnt = cmdP - cmdStart;\n    return cmdP;', '    *cmdCnt = cmdP - cmdStart;\n    ModernAudioCpuEnd();\n    return cmdP;')
        text = once(text, 'CVarGetInteger(CVAR_ENHANCEMENT("MirroredWorld"), 0)', 'ModernAudioCpuMirrored()')
    elif name == 'soh/soh/mixer.c':
        text = once(text, 'void aClearBufferImpl(', VMX + '\nvoid aClearBufferImpl(')
        text = once(text, '    union {\n        int16_t as_s16', '    __declspec(align(16)) union {\n        int16_t as_s16')
        anchor = 'void aMixImpl(uint16_t count, int16_t gain, uint16_t in_addr, uint16_t out_addr) {'
        text = once(text, anchor, anchor + r'''
#if defined(_XBOX) && defined(_M_PPC)
    if (gain == -0x8000 && ModernAudioCpuSaturate(BUF_S16(out_addr), BUF_S16(in_addr),
        ROUND_UP_32(ROUND_DOWN_16(count << 4)), 1)) return;
#endif
''')
        anchor = '    int nbytes = ROUND_UP_64(ROUND_DOWN_16(count));\n\n    do {'
        text = once(text, anchor, r'''    int nbytes = ROUND_UP_64(ROUND_DOWN_16(count));
#if defined(_XBOX) && defined(_M_PPC)
    if (ModernAudioCpuSaturate(out, in, nbytes, 0)) return;
#endif

    do {''')
        text = once(text, '    int16_t* d = BUF_S16(dest);\n    while (count > 0) {', r'''    int16_t* d = BUF_S16(dest);
#if defined(_XBOX) && defined(_M_PPC)
    if (ModernAudioCpuInterleave(d, l, r, count * 8)) return;
#endif
    while (count > 0) {''')
    return text


def application(text):
    # Keep the checked predicate locked through synthesis and completion.
    start = text.index('void OTRAudio_Thread() {')
    end = text.index('extern "C" void OTRAudio_Init()', start)
    part = text[start:end]
    part = once(part, '        {\n            Shipyard::Async::unique_lock<Shipyard::Async::mutex> Lock(audio.mutex);',
                '        Shipyard::Async::unique_lock<Shipyard::Async::mutex> Lock(audio.mutex);')
    part = once(part, '        }\n        Shipyard::Async::unique_lock<Shipyard::Async::mutex> Lock(audio.mutex);', '')
    return text[:start] + part + text[end:]


def matrix(text):
    old = '    double c = (1.0 - chain.Freq) / (1.0 + chain.Freq);'
    new = r'''    // Four chains advance the same frequency; retain double arithmetic exactly.
    static __declspec(thread) bool coefficientReady = false;
    static __declspec(thread) double coefficientFrequency;
    static __declspec(thread) double coefficientValue;
    if (!coefficientReady || coefficientFrequency != chain.Freq) {
        coefficientFrequency = chain.Freq;
        coefficientValue = (1.0 - chain.Freq) / (1.0 + chain.Freq);
        coefficientReady = true;
    }
    double c = coefficientValue;'''
    return once(text, old, new)


def profile_header(text):
    text = once(text, '    ThreadSample() { Reset(false); }',
                '    ThreadSample() { memset(this, 0, sizeof(*this)); }')
    return once(text, '    void Reset(bool requested) {\n        memset(this, 0, sizeof(*this));',
                '    void Reset(bool requested) {\n        if (!requested) { enabled = false; return; }\n        memset(this, 0, sizeof(*this));')
