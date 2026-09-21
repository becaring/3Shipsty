# Genuine modern Network on Xbox

`prepare_network.py --build` compiles the complete locked stable 9.2.3 Network.cpp
with **ENABLE_REMOTE_CONTROL enabled**, the actual XDK transport, and all 23
Anchor string constant definitions. Complete Network, CrowdControl, Sail, Anchor,
AnchorClient, RoomState and AnchorRoomWindow declarations are retained. No remote
application behavior or transport is replaced by empty providers.

The release workflow explicitly sets BUILD_REMOTE_CONTROL=1. The generated
Network header rejects a consuming translation unit without ENABLE_REMOTE_CONTROL:
this must be a consistent application build flag, not merely a Network.cpp flag.
Otherwise the conditional socket members would give consumers different classes.

## Transport and ownership

The narrow API implements the reached SDL_net 2.x client operations using actual
XDK/Winsock socket/connect/send/recv/select/close. Its C linkage and network-order
IPaddress contract match the existing API. Send loops until the requested bytes
are written or an error occurs, preserving its partial-byte return; receive
returns the actual count or closure/error. Socket sets retain capacity and poll
behavior. TCP_NODELAY is enabled for the real-time connection. Additional accept
and peer-address operations preserve the API's listening-socket behavior.

API references: [SDL_net TCP implementation](https://github.com/libsdl-org/SDL_net/blob/release-2.2.0/SDLnetTCP.c)
and [socket-set implementation](https://github.com/libsdl-org/SDL_net/blob/release-2.2.0/SDLnetselect.c).
This is an independent Xbox platform implementation, not a bundled SDL_net fork.

Numeric addresses use inet_addr and ports use htons. Those values are already
network byte order when copied into sockaddr_in, including on big-endian Xenon.
DNS uses the actual asynchronous XNetDnsLookup/event/XNetDnsRelease boundary;
the desktop validation build uses getaddrinfo. There are no byte swaps on JSON
or its UTF-8 stream. TLS holds per-thread transport error text.

SDLNet_Init explicitly owns a reference-counted XNetStartup then WSAStartup;
final SDLNet_Quit reverses that ownership. No connection implicitly initializes
the platform. The Xbox configuration requests XNET_STARTUP_BYPASS_SECURITY for
PC/remote-control peers. XDK winsockx.h lines 1689-1706 documents that this flag
works with the devkit library and is ignored by the retail library. Xenia and
physical-console networking therefore still require validation with the actual
linked runtime; native compilation does not establish external connectivity.

**Startup integration:** call/check SDLNet_Init before OTRGlobals/resource or RNG
initialization, so the existing XNetRandom users share this lifetime. Move the
existing late InitOTR SDLNet_Init call rather than accidentally leaving an extra
reference. Call SDLNet_Quit after every remote/save/audio/resource worker has
joined and Context has released its resources. The current early DeinitOTR quit
call must move to that final platform teardown boundary.

## Narrow compatibility changes

- std::thread uses the existing owned joining-thread primitive. Receive, callback,
  outgoing processing and framing remain in the genuine Network class (D).
- Public isEnabled/isConnected retain their boolean read/assignment contract via
  an interlocked flag wrapper. This removes unsynchronized cross-thread plain-bool
  accesses; it changes storage size, so every consumer must use the same header.
  Current source inventory only reads/assigns these values, never takes bool* (D).
- One native mutex protects socket publication, SendDataToRemote and close, so
  a main-thread send cannot dereference a socket freed by the receive worker (D).
- DNS failure returns from Enable after the real error log. Upstream continued
  with INADDR_NONE, which SDL_net interprets as a listening address; that is not a
  successful connection to the requested remote (C).
- Network and Anchor provide distinct default/value constructors. Ordinary
  default initialization retains indeterminate fields; the existing storage-free
  ValueInit tag preserves the zeros of empty/value construction. Anchor's five
  defaults, CrowdControl Response's default type and Effect's default category
  are retained. Effect's array/unique_ptr/state fields remain in the actual type.
  Inline Anchor constants become one native definition each (A).
- AnchorRoomWindow's inherited constructors explicitly forward to the existing
  GuiWindow, and override syntax is lowered. No additional window is introduced.

Use `value_expressions()` when projecting `new Anchor()` in OTRGlobals and
`new Effect()` in CrowdControl.cpp. CrowdControl/Sail themselves retain implicit
constructors, including their normal inherited value-initialization behavior.
Future explicit empty construction of Network/Anchor/Response/Effect needs the
same tagged boundary. The base GuiWindow constructor contract remains owned by
the existing GUI provider.

## Verification and remaining work

```
C:/Python313/python.exe -B tools/shipyard/test_network.py
```

Four checks pass. The full real Network.cpp executes against Winsock loopback:
nine valid null-delimited JSON packets, split and coalesced receives, malformed
JSON rejection, UTF-8, a 2100-byte packet, a 524288-byte outgoing message,
disconnect/reconnect with incomplete-frame reset, and joined shutdown. Actual
callback overrides only observe the existing Network path. The host uses the
upstream JSON and spdlog libraries; the native object compiles against the owned
current projected providers. It does not substitute a network/parser/game loop.

The test verifies init reference counting, final WSACleanup, address/port byte
order, errors, and Network default versus value initialization. All connections
were to 127.0.0.1. No production server or non-loopback connection was attempted.
XNet DNS and additional listener APIs are native-compiled but not Xbox-executed.

Build recipes are `scratch/network-xdk/xdk/build.json`. Production inputs are
transport.cpp, generated Network.cpp and generated AnchorConstants.cpp. Exclude
declarations.cpp and loopback.cpp. Map AnchorConstants.cpp to Anchor.h's 23 inline
definitions; no Anchor.cpp behavior is supplied by that file. The canonical
include root is `scratch/network-xdk/generated/soh`; `includes()` exposes its
closure. Host receipts are `scratch/network-xdk/host/{compile,run}.json` and the
test run is recorded in verification.log.

CrowdControl/Sail/Anchor application implementations remain to compile against
these declarations and native mutex/thread spelling. Native Network preserves
the upstream reconnect/poll loops and OS blocking-connect behavior; retry pacing
and cancellation under unavailable remote hosts still need runtime assessment.
This work does not claim Anchor synchronization, CrowdControl effects, Xenia
network connectivity, or physical Xbox networking has executed.
