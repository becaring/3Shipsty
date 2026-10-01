"""Stamp overlap audio requests without changing the sequential synthesis path."""

from prepare_configuration import once


def header(text):
    text = '#include "application/overlap_audio.h"\n' + text
    return once(
        text,
        "struct OTRAudioState {",
        "struct OTRAudioState {\n    ModernOverlap::AudioWorkState overlap;",
    )


def source(text):
    text = once(
        text,
        "#define AUDIO_FRAMES_PER_UPDATE (R_UPDATE_RATE > 0 ? R_UPDATE_RATE : 1)",
        "#define AUDIO_FRAMES_PER_UPDATE (audio.overlap.generation ? audio.overlap.divisor : "
        "(R_UPDATE_RATE > 0 ? R_UPDATE_RATE : 1))",
    )
    text = once(
        text,
        "        ModernFrameProfile::Begin(ModernFrameProfile::AudioGenerate);",
        "        if (audio.overlap.generation)\n"
        "            ModernFrameProfile::BeginThreadSample(audio.overlap.sample, audio.overlap.profile, false);\n"
        "        ModernFrameProfile::Begin(ModernFrameProfile::AudioGenerate);",
    )
    text = once(
        text,
        "        audio.processing = false;\n        audio.cv_from_thread.notify_one();",
        "        if (audio.overlap.generation) {\n"
        "            ModernFrameProfile::EndThreadSample();\n"
        "            audio.overlap.Complete();\n"
        "        }\n        audio.processing = false;\n"
        "        audio.cv_from_thread.notify_all();",
    )
    # The original Graph path uses its original live divisor and profiler.
    return once(
        text,
        "        audio.processing = true;",
        "        audio.overlap.generation = 0;\n        audio.processing = true;",
    )
