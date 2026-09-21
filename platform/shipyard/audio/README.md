# Current AudioPlayer and native XAudio2

The real pinned Audio, AudioPlayer, SoundMatrixDecoder and NullAudioPlayer
remain the application audio implementation. The generated factory registers
XAudio2 and constructs `shared_ptr<XAudio2AudioPlayer>` before converting it to
the base pointer, preserving the derived deleter despite upstream's nonvirtual
AudioPlayer destructor. Null is retained solely as upstream's explicit/error
fallback; its selection is not evidence of working audio.

The native buffer ownership and voice lifecycle come from SoH360, carried into
the modern AudioPlayer interface using Smash360's generic implementation.
Exact donor hashes and classification are in `donor-provenance.json`. Imported
work comprises aligned persistent blocks, callback release, frame accounting,
priming, backpressure, error publication and voice-before-storage teardown.
Old game workers, mixer cadence, resampling and Smash application logic are not
imported. The Smash-specific rejection of raw 5.1 is removed: this backend
honors AudioPlayer's stereo/raw51/matrix51 contract; the current SoH game selects
stereo or matrix51 and supplies stereo input to the real matrix decoder.

Modern upstream owns the 32 kHz sample rate, 1024 sample-length setting and
1680-frame target supplied in OTRGlobals. The worker's actual 528/560 choices
and authentic frame divisor remain in OTRGlobals. The backend obtains settings
through AudioPlayer getters, not old donor 44.1 kHz constants. Capacity is eight
blocks, each at least one configured sample length or one eighth of the desired
reserve, bounded at 16384 frames per block. No samples are dropped when busy.

Matrix projection changes only language syntax: default member state moves to
constructors, reset assignments use value-constructed current state types,
runtime-used constexpr scalars become const, make_unique becomes unique_ptr
construction, and the tuple return/binding is spelled for the XDK. Filter,
phase, gain, delay, saturation and output-order calculations are unchanged.
AudioSettings is the same extracted current definition used by Context.

Native PCM is signed 16-bit in host order, as in the authoritative SoH360
XAudio2 implementation. No desktop WAV byte swap is added to mixer output.
The donor points to ATG WaveFile's native sample convention; the installed
minimal SDK has no sample source to independently check here. Actual target
PCM/channel behavior must therefore still be validated through Xenia and later
user hardware evidence. Host output parity does not establish target audio.

```powershell
python -B tools/shipyard/prepare_configuration.py
python -B tools/shipyard/prepare_audio.py --build
python -B tools/shipyard/tests/test_audio.py
```

All seven current/native TUs compile. Host original/projected matrix output
matches across 65 blocks, state resets and three rates: 32000, 44100 and 48000.
Logical PCM checksums are `f424f92c`, `e26ef9f5`, `5d0d0c6d`. The real AudioPlayer
is exercised with a test-only observing device for stereo/matrix/raw routing
and reinitialization; the native pool is exercised for aligned ownership,
exhaustion, concurrent completion notification and reuse. That observing device
is never an application backend. XAudio2 itself has not executed in Xenia.

Factory/config registration is generated, but full Context/application linking
and thread/reinitialization integration remain required. Diagnostics use the
actual spdlog path, and fatal voice callbacks terminate without unwinding an
exception across the XAudio2 ABI.
