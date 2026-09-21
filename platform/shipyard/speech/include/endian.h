#pragma once
#include <stdint.h>
#define LITTLE_ENDIAN 1234
#define BIG_ENDIAN 4321
#ifdef _XBOX
#define BYTE_ORDER BIG_ENDIAN
#else
#define BYTE_ORDER LITTLE_ENDIAN
#endif
static __inline uint16_t ShipyardSpeechSwap16(uint16_t x){return (uint16_t)((x<<8)|(x>>8));}
static __inline uint32_t ShipyardSpeechSwap32(uint32_t x){return ((x&255U)<<24)|((x&65280U)<<8)|((x>>8)&65280U)|(x>>24);}
static __inline uint64_t ShipyardSpeechSwap64(uint64_t x){return ((uint64_t)ShipyardSpeechSwap32((uint32_t)x)<<32)|ShipyardSpeechSwap32((uint32_t)(x>>32));}
#if BYTE_ORDER == BIG_ENDIAN
#define le16toh(x) ShipyardSpeechSwap16(x)
#define le32toh(x) ShipyardSpeechSwap32(x)
#define le64toh(x) ShipyardSpeechSwap64(x)
#define htole16(x) ShipyardSpeechSwap16(x)
#define htole32(x) ShipyardSpeechSwap32(x)
#define htole64(x) ShipyardSpeechSwap64(x)
#define be16toh(x) (x)
#define be32toh(x) (x)
#define be64toh(x) (x)
#define htobe16(x) (x)
#define htobe32(x) (x)
#define htobe64(x) (x)
#else
#define le16toh(x) (x)
#define le32toh(x) (x)
#define le64toh(x) (x)
#define htole16(x) (x)
#define htole32(x) (x)
#define htole64(x) (x)
#define be16toh(x) ShipyardSpeechSwap16(x)
#define be32toh(x) ShipyardSpeechSwap32(x)
#define be64toh(x) ShipyardSpeechSwap64(x)
#define htobe16(x) ShipyardSpeechSwap16(x)
#define htobe32(x) ShipyardSpeechSwap32(x)
#define htobe64(x) ShipyardSpeechSwap64(x)
#endif
