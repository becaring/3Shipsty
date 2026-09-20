#include "ship/utils/binarytools/BinaryReader.h"
#include "ship/utils/binarytools/BinaryWriter.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include "ship/utils/binarytools/Stream.h"
#include "ship/utils/binarytools/endianness.h"
#if !defined(_XBOX) || !defined(_M_PPC)
#error Native Xbox compiler required
#endif
#ifndef IS_BIGENDIAN
#error Xbox must select big endian
#endif
typedef char NativeIsBig[(Ship::Endianness::Native == Ship::Endianness::Big) ? 1 : -1];
typedef char PointerWidth[(sizeof(void*) == 4) ? 1 : -1];
typedef char EnumWidth[(sizeof(Ship::Endianness) == sizeof(int)) ? 1 : -1];
typedef char SeekWidth[(sizeof(Ship::SeekOffsetType) == sizeof(int)) ? 1 : -1];
int instantiate(char* bytes, size_t count) {
    Ship::BinaryReader reader(bytes, count);
    reader.SetEndianness(Ship::Endianness::Little);
    reader.Seek(0, Ship::SeekOffsetType::Start);
    Ship::BinaryWriter writer;
    writer.Write(reader.ReadUInt32());
    return int(writer.GetLength());
}
