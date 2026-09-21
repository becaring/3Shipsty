# Vorbis decoder dependency

Current AudioSampleFactory uses actual libvorbisfile. Upstream discovers Vorbis
as a system package, so this port explicitly pins stable v1.3.7 at
0657aee69dec8508a0011f47f3b69d7538e9d262 rather than presenting it as an upstream
gitlink. Source URL, tag object and receipt are in dependencies.lock.json.

`python -B tools/shipyard/prepare_vorbis.py --build` inventories all 22 source
units from the dependency's CMake lists. Each is preprocessed with XDK headers
and mechanically lowers C declarations/loops for the XDK C frontend. All native
objects are checked for PowerPC BE COFF. No decoder algorithm is substituted.
The existing pinned Ogg headers/library supply the container interface.

`--host` builds the same complete library for audio factory differential tests.
`tools/shipyard/test_soh_audio_samples.py` exercises actual Vorbis decode and
opposite output byte orders against the release's original factory workers.
Host SIMD versus native PPC fallback rounding can differ by a least-significant
PCM bit; native decoder execution/quality has not yet been measured.
