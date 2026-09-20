#include "ship/utils/binarytools/endianness.h"
#if !defined(_XBOX) || !defined(_M_PPC)
#error Native Xbox preprocessing required
#endif
#ifndef IS_BIGENDIAN
#error Original endian detection fails on Xbox PowerPC
#endif
typedef char BigEndianSwapIdentity[(BE32SWAP_CONST(0x12345678) == 0x12345678) ? 1 : -1];
typedef char LittleEndianSwap[(LE32SWAP_CONST(0x12345678) == 0x78563412) ? 1 : -1];
