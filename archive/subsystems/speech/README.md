# Real Xbox speech synthesis

This provider compiles the complete pinned Shipwright 9.2.3 `tts.cpp`,
`ShuffleSpeak.cpp`, `SpeechSynthesizer.cpp`, and optional `SpeechLogger.cpp`.
`XboxSpeechSynthesizer` implements the existing speech interface with the real
eSpeak NG formant engine and a private XAudio2 source voice. The game hooks,
language selection, text resources, TTS menu/file-select announcements, and
ShuffleSpeak randomizer behavior remain the modern application implementations.
SpeechLogger is retained as an ordinary upstream provider, never substituted for
Xbox speech.

## Provenance and dependency scope

`sources.lock.json` locks the six application source/header inputs to the pinned
9.2.3 release. The generator refuses changed inputs. It also checks the dependency
checkout's exact commit and clean tracked-source status before generating copies.

* Official eSpeak NG repository: https://github.com/espeak-ng/espeak-ng
* Release 1.52.0: https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0
* Exact commit: `4870adfa25b1a32b4361592f1be8a40337c58d6c`
* License: **GPL-3.0-or-later**. This is a new static runtime dependency, not
  permissively licensed Xbox code. Release packaging must retain its notices and
  provide the corresponding source/build changes under the applicable license.
  The checkout contains `COPYING` and individual source notices; do not describe
  the resulting dependency as MIT or omit it from release source distribution.
* Official Sonic build dependency: https://github.com/waywardgeek/sonic,
  `fbf75c3d6d846bad3bb3d456cbc5d07d9fd8c104`, exactly as specified by eSpeak's
  `cmake/deps.cmake`. CMake fetches it even with `USE_LIBSONIC=OFF`. It is **not
  linked into this runtime**.

Engine configuration keeps the real default formant/Klatt synthesis, dictionary,
Unicode, language, and voice processing. `USE_ASYNC=0` uses the engine's existing
synchronous callback mode because Xbox owns the worker. Desktop audio, Sonic,
external MBROLA, and experimental speechplayer integrations are disabled; none
is used by SoH's default eSpeak voice path. This is 28 complete engine C units
plus six complete Unicode C units, selected from the official CMake manifest.

## Narrow compatibility boundaries

| Class | Change | Ownership |
|---|---|---|
| A: C language | The existing deterministic game C lowering handles C99/C11 declarations, compound literals, designated initializers and `_Bool` after XDK preprocessing. `LookupCharName` gains a return-type typedef to distinguish a pointer return from a bool function-pointer declarator in that existing lowering. | Generic Shipyard engine compatibility |
| A/B: C++ language/library | Existing hook/ShipInit/literal projection preserves the full TTS and ShuffleSpeak implementations. Seven numeric `to_string` calls explicitly select the available integer overload; strings remain exact UTF-8 octal bytes on XDK. | 3Shipsty source projection |
| C/E: platform/filesystem | XDK `xtl.h` replaces desktop `windows.h` for the engine. Desktop registry/environment path discovery is gated out on Xbox; the real engine reads its standard files at `game:\espeak-ng-data`. Target CRT forwarding headers are generated from pinned inputs. | Generic Shipyard |
| B: formatting | A local C99-return-semantics `snprintf` adapter wraps the actual XDK CRT. TTS calls the already tested SoH resource formatting wrapper. | Generic Shipyard / application boundary |
| D: async/lifetime | One joined Xbox worker supplies the existing synchronous eSpeak callback. Requests own copied text/language, replace pending work, cancel active synthesis, and retain PCM until XAudio completes. | Generic Shipyard |
| F/G: data/audio | The standard engine data files acquire narrow native-structure endian conversions on load; emitted signed PCM bytes become native 16-bit samples in aligned XAudio buffers. | Generic Shipyard |
| I: linkage | Static eSpeak API declarations suppress desktop DLL import/export decoration using `SHIPYARD_ESPEAK_STATIC`. | Generic Shipyard |

No upstream/reference file is edited. Generated sources and engine/tool checkouts
remain under `scratch/speech-xdk`. The engine's compilation/tool entry points are
retained, but Xbox startup never calls dictionary or phoneme compilation.

## Worker and audio ownership

Shipyard `sources/speech/SpeechQueue.h` owns one critical section, an event, copied strings, and an
interlocked request generation. A newer request cancels current synthesis;
`Speak("", language)` cancels without synthesizing, matching the real TTS cancel
call and SAPI's purge-before-speak behavior. The worker invokes genuine
`espeak_SetVoiceByProperties` and `espeak_Synth` with the full UTF-8 byte length.
Initialization uses checked NG status APIs rather than the legacy initialization
function, which can return a sample rate after some initialization failures.

The backend creates a private XAudio2 instance/mastering/source voice. The XDK
documentation explicitly supports multiple instances (`SoH360/scratch/xdk-docs/
xaudio_to_xaudio2.htm`). Four 16-byte-aligned PCM blocks stay owned until their
actual `OnBufferEnd` callback. This follows the existing Shipyard audio pool's
alignment and ownership rules without replacing game audio. Sample-rate changes
drain queued audio and recreate the speech source voice on the synthesis worker.

Shutdown invalidates work, wakes waiters, joins the worker, then destroys voices,
releases the engine and eSpeak state, and frees synchronization/PCM storage.
`IXAudio2Voice_DestroyVoice.htm` guarantees no later callback or audio-data read
after it returns. Voice destruction happens on the synthesis worker/main shutdown
thread, never from an XAudio callback. Allocation, missing-data, voice and engine
errors report actual failures through debug output/stderr; no logger fallback or
fake success is supplied. Call Init/Uninitialize/destruction on the application's
serialized lifecycle after gameplay callbacks stop; the upstream base class's
`mInitialized` flag itself is not a concurrent lifetime API.

## Endian proof and data packaging

Shipyard `sources/speech/data_boundary.c` owns the eSpeak data and PCM conversions.
These are **PC-generated eSpeak data files**, not N64 bytes or native Xbox data.
The packaged files stay in the standard upstream format.

| Boundary | Exact conversion |
|---|---|
| `phontab` | Each 16-byte `PHONEME_TAB`: two little-endian u32 fields and one u16 program field become native. Table names/counts and the remaining byte fields are untouched. |
| `phonindex` | The instruction array is little-endian u16 and becomes native u16. |
| `intonations` | `TUNE` is 68 bytes; its first 64 bytes stay unchanged and its final reserved int becomes native. |
| `phondata` | Version/sample-rate header and waveform/envelope bytes already use explicit byte decoding and stay unchanged. The official `phondata-manifest` identifies spectral sequences: convert the sequence u16 length and each frame's flags/seven frequency shorts. Frame strides remain 44 or 64 bytes according to the actual Klatt flag. Bounds, ordering and required manifest are checked; no missing-manifest fallback exists. |
| `*_dict` | Existing upstream `ARCH_BIG`/`Reverse4Bytes` handles dictionary headers. Do not swap these a second time. |
| Synthesis callback PCM | `wavegen.c` emits little-endian bytes even when its API passes `short*`. Decode those bytes into actual native signed 16-bit samples before XAudio submission. |

Actual XDK COFF initializers prove `PHONEME_TAB=16`, `TUNE=68`, `frame_t=64`,
`frame_t2=44`, all used field offsets, 16-bit short, 32-bit int/pointer, and
`BYTE_ORDER=4321`. The boundary test independently computes every changed field
from the full real generated data and compares all other bytes unchanged.

Build data on the PC, then copy the **entire** generated
`scratch/speech-xdk/host-ninja/espeak-ng-data` directory next to the XEX as
`espeak-ng-data`. Keep `phondata-manifest`, `phontab`, `phonindex`, `phondata`,
`intonations`, dictionaries, `lang`, and `voices`. `data-manifest.json` records
every packaged input hash. No ROM, custom asset archive, or Xbox extraction is
involved. Existing SoH O2R/OTR speech JSON continues through the real resource
manager independently of the engine's standard voice/dictionary data.

## Build and integration

Prerequisites: existing canonical application/randomizer-content projections,
XDK, VS2022 host compiler/Windows SDK, CMake, and Ninja. The main dependency setup
acquires the checkouts pinned by `dependencies.lock.json` in the owned speech
scratch directory, which clean regeneration preserves:

```powershell
python -B tools/shipyard/setup_dependencies.py
C:\Python313\python.exe -B tools/shipyard/test_speech.py
```

The full test builds official PC data/tooling, original and projected host
engines, every native engine/application TU, and real contracts. Standalone
native regeneration is available with `prepare_speech.py --engine` and
`prepare_speech.py --application`. Build JSON records contain complete commands,
source hashes, lowering statistics, object hashes and confirmed PPC COFF machine.
The root provider generator can consume these recipes just like existing batches.

Root integration, intentionally not performed by this isolated workstream:

1. Put `scratch/speech-xdk/generated/soh` ahead of the original application include
   root and provide the generated eSpeak public include root. Add
   `SHIPYARD_ESPEAK_STATIC` to consumers of the Xbox header. The scoped engine
   `config.h` include directory belongs only on engine compilations, to avoid
   colliding with unrelated dependencies' configuration headers.
2. In the generated **real** OTRGlobals startup constructor selection, select
   `new XboxSpeechSynthesizer()` under `_XBOX` **before** `_WIN32` can select SAPI.
   Keep the actual `SpeechSynthesizer::Instance` definition and Init call in
   OTRGlobals. A failed Init stays failed and is already diagnosed by this backend.
3. During actual application teardown, after callbacks stop, invoke
   `DestroyXboxSpeechSynthesizer(SpeechSynthesizer::Instance)` and clear Instance.
   The upstream base lacks a virtual destructor: ordinary deletion through the
   base pointer would skip worker/voice teardown. Calling Uninitialize first is
   also safe but does not replace correct concrete destruction.
4. Add the 34 engine units and six production application/backend units listed in
   the two build records. Include each full `tts.cpp`, `ShuffleSpeak.cpp`,
   `SpeechSynthesizer.cpp`, and `SpeechLogger.cpp` exactly once. Do not add desktop
   SAPI/Darwin/dlopen ESpeak implementations to this Xbox target.
5. Link the existing real XAudio2/XDK runtime libraries and package the PC data
   directory. Existing startup/game/audio ownership remains unchanged.

## Verification and remaining execution

`test_speech.py`: **six tests pass** (43.514 seconds on 2026-09-21).
All 34 real engine units and six application/backend units produce XDK PPC BE
objects; the additional ABI probe verifies the actual target layouts. Every
original application function remains in the generated function inventory.

Original/projected host engines produce identical actual samples and hashes for
the exact modern locale strings `en-US`, `de-DE`, and `fr-FR`, through two real
initialize/terminate cycles. Initial utterances contain 67,063 / 48,740 / 54,311
samples at 22,050 Hz. Callback cancellation stops each at the second callback
with 1,324 retained samples. The same real queue passes copied-input, latest-work,
empty-cancel and joined-stop contracts. Audible WAV artifacts are in
`scratch/speech-xdk/synthesis-{original,projected}/speech-{en-US,de-DE,fr-FR}.wav`.
The deterministic seed is test-only; production keeps upstream seeding behavior.

Endian comparisons cover 10,092 phontab fields, 21,658 phonindex fields, 28,581
phondata fields and 34 intonation fields, plus signed PCM edge cases, invalid data
and missing manifest. Generation repeatability is verified.

These tests execute the real engines on Windows and compile the actual backend
for Xbox; they **do not execute XDK C-lowered code, the XAudio worker, or gameplay
hooks on Xenon**. Integration must next exercise actual menu/file-select speech,
all three languages, rapid cancellation, game-audio mixing, disable/re-enable and
application teardown in Xenia. Physical Xbox audio timing/quality still requires
the user's hardware evidence. No runtime or hardware success is claimed here.
