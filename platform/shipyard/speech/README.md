# Xbox speech synthesis

The port uses the game's TTS and ShuffleSpeak code with eSpeak NG and a separate
XAudio2 voice. The Xbox worker runs eSpeak's synchronous callback mode. A new
request cancels current speech; an empty request cancels without speaking.

`sources.lock.json` pins the game inputs. eSpeak NG 1.52.0 is pinned to
`4870adfa25b1a32b4361592f1be8a40337c58d6c`. It is GPL-3.0-or-later: retain its
notices and corresponding source/build changes in release distribution. The
Sonic checkout required by eSpeak's build is not linked into the Xbox runtime.

Run dependency setup and normal regeneration first. The focused checks are:

```powershell
python -B tools/shipyard/prepare_speech.py --build
python -B tools/shipyard/test_speech.py
```

Package the standard PC-generated `espeak-ng-data` directory beside the game.
The backend reads it at `game:\espeak-ng-data`. Keep `phondata-manifest`; it is
needed to decode native structures correctly. The adapter converts selected
little-endian data fields and PCM samples, not the whole data directory.

Stop gameplay speech callbacks before shutdown. Cancel pending work, join the
worker, and destroy voices before freeing their PCM buffers. Keep each buffer
alive until XAudio reports it finished. Never destroy a voice from its callback.

Host tests compare synthesis samples, cancellation, data conversion, and queue
shutdown. XDK compilation does not test audible output. Check menu/file-select
speech in all supported languages, rapid cancellation, mixing with game audio,
disable/re-enable, and shutdown in Xenia and on hardware.

The [earlier audit](../../../archive/subsystems/speech/README.md) preserves the
data layouts, dependency details, and recorded test results.
