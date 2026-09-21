# Current SoH frame interpolation

The complete pinned frame_interpolation.cpp compiles for XDK; all recorder,
branch traversal, actor/camera handling, matrix and angle methods remain.
This is SoH application compatibility work, not an alternate interpolation
system or an imported 4.0.5 optimization. No mathematics were changed.

`python -B tools/shipyard/prepare_interpolation.py --build` verifies three source
hashes and emits the full translation unit. The unused LUS umbrella include is
removed. The OTR FPS call uses the already-existing Ship_GetInterpolationFPS C
bridge: its exact forwarding body is hash-verified, not reimplemented or faked.

XDK A/B/H adaptations: scoped Op enum; two condition initializers with identical
lexical scope; range loops; pre-C++17 vector insert/back spellings; typed factories
for 13 aggregate assignments, retaining omitted-field zero initialization; and
explicit names for the 12 payload types. XDK rejected the original std::pair
inside the recording union with C2621. Its local pointer/integer label is now a
POD with the same lexicographic comparison. The union remains a union, avoiding
a large per-record expansion. Compile-time native checks require its 72-byte
payload and 8-byte label; the host checks the corresponding 80-byte payload.

`python -B tools/shipyard/test_interpolation.py` checks reproducibility, all
production function inventories, and verbatim preservation of unchanged methods.
The bounded host audit executes 589,824 integer-angle cases, float angles/matrix
interpolation, matrix inverses/singular failure, label comparisons and complete
pure recorder methods/lifecycle against original and generated source. Both
outputs match. Five service-dependent functions are excluded only from this
host audit, without supplying fake OTR or matrix functions. They remain in the
production generator and full native object. Original host includes normalize
the unused umbrella and exact existing FPS bridge only.

Receipts: scratch/interpolation-xdk/{manifest.json,verification.json,xdk/build.json}.
Actual paired game frames, complete traversal/matrix-service execution and Xbox
performance remain unvalidated; this is not first-gameplay evidence.
