#include "ship/utils/binarytools/BinaryReader.h"
#include "ship/utils/binarytools/BinaryWriter.h"
#include "ship/utils/binarytools/MemoryStream.h"
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <type_traits>
#ifdef SHIPYARD_PROJECTED
#include "binary/compat.h"
#endif

static_assert(!std::is_convertible<Ship::Endianness, int>::value, "scoped endian must not implicitly convert");
static_assert(!std::is_convertible<Ship::SeekOffsetType, int>::value, "scoped seek must not implicitly convert");
static_assert(!std::is_convertible<Ship::Endianness, Ship::SeekOffsetType>::value, "enum domains stay distinct");

static void check(bool value, const char* label) {
    if (!value) throw std::runtime_error(label);
}
static std::vector<char> load(const char* path) {
    std::ifstream file(path, std::ios::binary);
    check(file.good(), "fixture open");
    return std::vector<char>(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}
static void numeric(const char* path, Ship::Endianness order) {
    std::vector<char> bytes = load(path);
    Ship::BinaryReader reader(bytes.data(), bytes.size());
    check(reader.GetEndianness() == Ship::Endianness::Native, "reader default endian");
    reader.SetEndianness(order);
    check(reader.ReadInt8() == -42 && reader.ReadUByte() == 240, "8 bits");
    check(reader.ReadInt16() == -12345 && reader.ReadUInt16() == 0xfedc, "16 bits");
    check(reader.ReadInt32() == -123456789 && reader.ReadUInt32() == 0xfedcba98U, "32 bits");
    check(reader.ReadInt64() == -0x0102030405060708LL, "signed 64");
    check(reader.ReadUInt64() == 0xfedcba9876543210ULL, "unsigned 64");
    check(reader.ReadFloat() == 1.5f && reader.ReadDouble() == -1234.125, "floating point");
    check(std::isinf(reader.ReadFloat()) && std::isinf(reader.ReadDouble()), "infinity");
    check(std::signbit(reader.ReadFloat()) && std::signbit(reader.ReadDouble()), "negative zero");
    bool floatError = false, doubleError = false;
    try { reader.ReadFloat(); } catch (const std::runtime_error& e) {
        floatError = std::string(e.what()) == "BinaryReader::ReadFloat(): Error reading stream";
    }
    try { reader.ReadDouble(); } catch (const std::runtime_error& e) {
        doubleError = std::string(e.what()) == "BinaryReader::ReadDouble(): Error reading stream";
    }
    check(floatError && doubleError, "NaN exception text");
    check(reader.ReadString() == "abc", "length-prefixed string");
    check(reader.ReadCString() == std::string("xy\0", 3), "CString retains terminator");
    check(reader.ReadCString() == "z", "CString EOF termination");
    check(reader.GetBaseAddress() == bytes.size(), "cursor");

    Ship::BinaryWriter writer;
    writer.SetEndianness(order);
    writer.Write(int8_t(-42)); writer.Write(uint8_t(240));
    writer.Write(int16_t(-12345)); writer.Write(uint16_t(0xfedc));
    writer.Write(int32_t(-123456789)); writer.Write(uint32_t(0xfedcba98U));
    writer.Write(int64_t(-0x0102030405060708LL)); writer.Write(uint64_t(0xfedcba9876543210ULL));
    writer.Write(1.5f); writer.Write(-1234.125);
    writer.Write(std::numeric_limits<float>::infinity());
    writer.Write(-std::numeric_limits<double>::infinity());
    writer.Write(-0.0f); writer.Write(-0.0);
    writer.Write(uint32_t(0x7fc00000)); writer.Write(uint64_t(0x7ff8000000000000ULL));
    writer.Write(std::string("abc"));
    char tail[] = {'x', 'y', 0, 'z'}; writer.Write(tail, sizeof(tail));
    check(writer.ToVector() == bytes, "writer independently packed bytes");
    check(writer.GetLength() == bytes.size() && writer.GetBaseAddress() == bytes.size(), "writer length");
    writer.Close(); check(writer.ToVector() == bytes, "writer Close no-op");
    std::cout << "numeric/writer=pass\n";
}
static void limits_and_ownership() {
#ifdef SHIPYARD_PROJECTED
    std::unique_ptr<char[]> zeroed = Shipyard::Binary::MakeZeroedChars(16);
    for (int i = 0; i < 16; ++i) check(zeroed[i] == 0, "make_unique replacement value initializes");
    check(Shipyard::Binary::IsNaN(Shipyard::Binary::QuietNaN()), "NaN helper");
#endif
    char raw[] = {'a', 'b', 'c', 'd', 'e', 'f'};
    Ship::MemoryStream copied(raw, sizeof(raw));
    raw[0] = 'z'; check(copied.ReadByte() == 'a', "raw input copied");
    std::shared_ptr<std::vector<char>> data(new std::vector<char>(raw, raw + sizeof(raw)));
    std::shared_ptr<Ship::MemoryStream> stream(new Ship::MemoryStream(data));
    std::weak_ptr<Ship::MemoryStream> lifetime(stream);
    Ship::BinaryReader reader(stream);
    (*data)[1] = 'X'; data.reset(); stream.reset();
    reader.Seek(1, Ship::SeekOffsetType::Start);
    check(!lifetime.expired() && reader.ReadChar() == 'X', "reader retains shared storage");
    reader.Seek(-1, Ship::SeekOffsetType::Current); check(reader.ReadChar() == 'X', "relative seek");
    reader.Seek(1, Ship::SeekOffsetType::End); check(reader.ReadChar() == 'e', "end-minus-one-minus-offset");
    reader.Seek(0, Ship::SeekOffsetType::Start);
    char pair[2] = {}; reader.Read(pair, 2); check(pair[0] == 'z' && pair[1] == 'X', "bounded bulk read");
    reader.Close(); check(reader.ReadChar() == 'c', "Close no-op");
    reader.Seek(sizeof(raw), Ship::SeekOffsetType::Start);
    bool byteError = false, bulkError = false;
    try { reader.ReadUByte(); } catch (const std::out_of_range&) { byteError = true; }
    reader.Seek(sizeof(raw), Ship::SeekOffsetType::Start);
    try { reader.Read(pair, 1); } catch (const std::out_of_range&) { bulkError = true; }
    check(byteError && bulkError, "read beginning at EOF throws");
    // Upstream bulk reads do not validate the full span; never exercise an
    // out-of-allocation memcpy here or misrepresent that behavior as safe.
    Ship::BinaryReader owning(new Ship::MemoryStream(raw, sizeof(raw)));
    check(owning.ReadChar() == 'z', "raw Stream ownership constructor");
    Ship::BinaryWriter nativeWriter(new Ship::MemoryStream());
    const uint32_t native = 0x12345678;
    nativeWriter.Write(native);
    std::vector<char> result = nativeWriter.ToVector();
    check(result.size() == sizeof(native) && !memcmp(result.data(), &native, sizeof(native)), "native writer default");
    std::shared_ptr<Ship::MemoryStream> target(new Ship::MemoryStream());
    Ship::BinaryWriter sharedWriter(target); sharedWriter.Write(int32_t(11), int32_t(22));
    sharedWriter.Seek(0, Ship::SeekOffsetType::Start);
    Ship::BinaryReader nativeReader(target);
    check(nativeReader.ReadInt32() == 11 && nativeReader.ReadInt32() == 22, "shared writer pair");
    std::cout << "ownership/seek/limits/exceptions=pass\n";
}
int main(int argc, char** argv) {
    try {
        check(argc == 3, "fixture arguments");
        numeric(argv[1], Ship::Endianness::Little); numeric(argv[2], Ship::Endianness::Big);
        limits_and_ownership();
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
    return 0;
}
