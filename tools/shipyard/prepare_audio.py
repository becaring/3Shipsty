"""Project the current AudioPlayer/matrix decoder and native XAudio2 backend."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct
import subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from platform_base import resolve as resolve_platform_base

OUT = ROOT / "scratch/audio-xdk"
OWN = ROOT / "platform/shipyard/audio"
PLATFORM_BASE = resolve_platform_base(ROOT)


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Audio source pattern changed: " + old[:80])
    return text.replace(old, new)


def transform(name, text):
    if name.endswith("/Audio.h"):
        text = once(
            text,
            "enum class AudioBackend { WASAPI, SDL, COREAUDIO, NUL };",
            "struct AudioBackend : Shipyard::Binary::ScopedEnum<AudioBackend> {\n    enum Value {"
            " WASAPI, SDL, COREAUDIO, NUL, XAUDIO2 };\n    AudioBackend() {}\n   "
            " AudioBackend(Value value) : Shipyard::Binary::ScopedEnum<AudioBackend>(value) {}\n   "
            " explicit AudioBackend(int value) : Shipyard::Binary::ScopedEnum<AudioBackend>(value)"
            " {}\n};",
        )
        text = '#include "binary/compat.h"\n' + text
    if name.endswith("/Audio.cpp"):
        text = once(
            text,
            '#include "ship/controller/controldeck/ControlDeck.h"',
            '#include "ship/config/Config.h"\n#include <spdlog/spdlog.h>\n#ifdef _XBOX\n#include'
            ' "audio/XAudio2AudioPlayer.h"\n#endif',
        )
        text = text.replace("#ifdef _WIN32", "#if defined(_WIN32) && !defined(_XBOX)")
        text = text.replace(
            "switch (GetCurrentAudioBackend())", "switch (GetCurrentAudioBackend().GetValue())"
        )
        old = """        case AudioBackend::SDL:
            mAudioPlayer = std::make_shared<SDLAudioPlayer>(this->mAudioSettings);
            break;"""
        text = once(
            text,
            old,
            "#ifdef _XBOX\n        case AudioBackend::XAUDIO2:\n            mAudioPlayer ="
            " std::make_shared<XAudio2AudioPlayer>(this->mAudioSettings);\n           "
            " break;\n#else\n"
            + old
            + "\n#endif",
        )
        text = once(
            text,
            "    mAvailableAudioBackends->push_back(AudioBackend::SDL);",
            "#ifdef _XBOX\n    mAvailableAudioBackends->push_back(AudioBackend::XAUDIO2);\n#else\n "
            "   mAvailableAudioBackends->push_back(AudioBackend::SDL);\n#endif",
        )
    if name.endswith("/AudioPlayer.h"):
        text = once(
            text,
            '#include "ship/audio/AudioChannelsSetting.h"',
            '#include "ship/audio/AudioSettings.h"',
        )
        text = re.sub(r"struct AudioSettings \{.*?\n\};", "", text, flags=re.S)
        text = once(
            text,
            "AudioPlayer(AudioSettings settings) : mAudioSettings(settings)",
            "AudioPlayer(AudioSettings settings) : mAudioSettings(settings), mInitialized(false)",
        )
        text = once(text, "bool mInitialized = false;", "bool mInitialized;")
        text = text.replace(
            "#ifdef _WIN32",
            "#if defined(_WIN32) && !defined(_XBOX) && !defined(SHIPYARD_AUDIO_TEST)",
        )
        text = text.replace(
            '#include "SDLAudioPlayer.h"',
            "#if !defined(_XBOX) && !defined(SHIPYARD_AUDIO_TEST)\n#include"
            ' "SDLAudioPlayer.h"\n#endif',
        )
    if name.endswith("/AudioPlayer.cpp"):
        text = text.replace(
            "std::make_unique<SoundMatrixDecoder>(mAudioSettings.SampleRate)",
            "std::unique_ptr<SoundMatrixDecoder>(new"
            " SoundMatrixDecoder(mAudioSettings.SampleRate))",
        )
        text = once(
            text,
            "const auto [surroundOut, surroundLen] = mSoundMatrixDecoder->Process(buf, len);",
            "const auto surround = mSoundMatrixDecoder->Process(buf, len);\n    const uint8_t*"
            " const surroundOut=std::get<0>(surround);\n    const int"
            " surroundLen=std::get<1>(surround);",
        )
    if name.endswith("/SoundMatrixDecoder.h"):
        text = text.replace("~SoundMatrixDecoder() = default;", "~SoundMatrixDecoder() {}")
        text = text.replace("static constexpr int gMaxDelay", "static const int gMaxDelay")
        text = text.replace("double X[4] = {};", "double X[4];").replace(
            "double Y[4] = {};", "double Y[4];"
        )
        text = once(
            text,
            "struct BiquadCascade {",
            "struct BiquadCascade {\n        BiquadCascade() { for(int i=0;i<4;++i)"
            " X[i]=Y[i]=0.0; }",
        )
        for member in ("Freq", "FreqMin", "FreqMax", "SweepRate"):
            text = text.replace("double " + member + " = 0;", "double " + member + ";")
        text = (
            text.replace("double XHist[4] = {};", "double XHist[4];")
            .replace("double YHist[4] = {};", "double YHist[4];")
            .replace("bool Ready = false;", "bool Ready;")
        )
        text = once(
            text,
            "struct AllPassChain {",
            "struct AllPassChain {\n        AllPassChain() : Freq(0), FreqMin(0), FreqMax(0),"
            " SweepRate(0), Ready(false) {\n            for(int i=0;i<4;++i)"
            " XHist[i]=YHist[i]=0.0;\n        }",
        )
        text = (
            text.replace(
                "std::array<float, gMaxDelay> Data = {};", "std::array<float, gMaxDelay> Data;"
            )
            .replace("int Head = 0;", "int Head;")
            .replace("int Length = 0;", "int Length;")
        )
        text = once(
            text,
            "struct CircularDelay {",
            "struct CircularDelay {\n        CircularDelay() : Head(0), Length(0) { for(int"
            " i=0;i<gMaxDelay;++i) Data[i]=0.0f; }",
        )
        text = text.replace("int32_t mDelayLength = 0;", "int32_t mDelayLength;").replace(
            "double mAllPassBaseRate = 1.0;", "double mAllPassBaseRate;"
        )
    if name.endswith("/SoundMatrixDecoder.cpp"):
        text = (
            text.replace("constexpr float ", "const float ")
            .replace("constexpr int ", "const int ")
            .replace("constexpr double ", "const double ")
        )
        text = once(
            text,
            "SoundMatrixDecoder::SoundMatrixDecoder(int32_t sampleRate) {",
            "SoundMatrixDecoder::SoundMatrixDecoder(int32_t sampleRate) : mDelayLength(0),"
            " mAllPassBaseRate(1.0) {",
        )
        for member in ("mPhaseLeftMain", "mPhaseLeftCross", "mPhaseRightMain", "mPhaseRightCross"):
            text = text.replace(member + " = {};", member + " = AllPassChain();")
        for member in (
            "mCenterHighPass",
            "mCenterLowPass",
            "mSurrLeftMainHP",
            "mSurrLeftCrossHP",
            "mSurrRightMainHP",
            "mSurrRightCrossHP",
            "mSubLowPass",
        ):
            text = text.replace(member + " = {};", member + " = BiquadCascade();")
        for member in ("mDelaySurrLeft", "mDelaySurrRight"):
            text = text.replace(member + " = {};", member + " = CircularDelay();")
        text = once(
            text,
            "return { reinterpret_cast<const uint8_t*>(mSurroundBuffer.data()), samplePairs * 6 *"
            " sizeof(int16_t) };",
            "return std::tuple<const uint8_t*, int>(reinterpret_cast<const"
            " uint8_t*>(mSurroundBuffer.data()), static_cast<int>(samplePairs * 6 *"
            " sizeof(int16_t)));",
        )
    text = text.replace(" final :", " :").replace(" override", "")
    return text


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    pending = {}
    for name, expected in lock["sources"].items():
        text = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError("Audio input drift: " + name)
        pending[name] = transform(name, text)
    for name, text in pending.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            {n: hashlib.sha256(t.encode()).hexdigest() for n, t in pending.items()}, indent=2
        )
        + "\n",
    )


def build():
    prepare()
    resource = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_resources.py"))
    includes = [
        PLATFORM_BASE / "sources",
        OUT / "generated/include",
        ROOT / "scratch/configuration-xdk/generated/include",
        ROOT / "scratch/resource-manager-xdk/generated/include",
    ] + resource["includes"](True)
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = [
        "/nologo",
        "/c",
        "/TP",
        "/EHsc",
        "/GR",
        "/MT",
        "/O2",
        "/fp:precise",
        "/D_XBOX",
        "/D_XBOX_VER=200",
        "/DNOMINMAX",
        "/DSPDLOG_ACTIVE_LEVEL=0",
        "/I" + str(sdk / "include/xbox"),
    ] + ["/I" + str(p) for p in includes]
    sources = [
        OUT / "generated/src/ship/audio" / (n + ".cpp")
        for n in ("SoundMatrixDecoder", "AudioPlayer", "NullAudioPlayer", "Audio")
    ]
    sources += [
        PLATFORM_BASE / "sources/audio/PcmBufferPool.cpp",
        PLATFORM_BASE / "sources/audio/XAudio2AudioPlayer.cpp",
        OWN / "audio_log.cpp",
    ]
    records = []
    for source in sources:
        obj = folder / (source.stem + ".obj")
        command = [str(sdk / "bin/win32/cl.exe")] + flags + [str(source), "/Fo" + str(obj)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), result.stdout + result.stderr)
        label = (
            "shipyard/" + source.relative_to(PLATFORM_BASE).as_posix()
            if source.is_relative_to(PLATFORM_BASE)
            else source.relative_to(ROOT).as_posix()
        )
        records.append(dict(source=label, exit=result.returncode, command=command))
        if not result.returncode and struct.unpack_from("<H", obj.read_bytes())[0] != 0x1F2:
            raise ValueError("Not a Xenon object")
    stable(folder / "build.json", json.dumps(records, indent=2) + "\n")
    for row in records:
        print(str(row["exit"]) + " " + row["source"])
    if any(r["exit"] for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    else:
        prepare()
