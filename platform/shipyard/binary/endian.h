#ifndef SHIPYARD_BINARY_ENDIAN_H
#define SHIPYARD_BINARY_ENDIAN_H
/* Native byte order for C and C++ consumers. BSWAP remains unconditional. */
#if (defined(_XBOX) && defined(_M_PPC)) || (defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)) || defined(__BIG_ENDIAN__)
#define SHIPYARD_BIG_ENDIAN 1
#else
#define SHIPYARD_BIG_ENDIAN 0
#endif
#endif
