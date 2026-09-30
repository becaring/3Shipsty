using Shipyard::LegacySave::Bytes;
using Shipyard::LegacySave::Order;
using Shipyard::LegacySave::Little;
using Shipyard::LegacySave::Big;
using Shipyard::LegacySave::SaveContext_v0;
static void Header(unsigned char *bytes) {
    const unsigned char magic[] = {2, 1, 0, 0x98, 9, 0x10, 0x21, 'Z', 'E', 'L', 'D', 'A'};
    memcpy(bytes, magic, sizeof(magic));
}
static bool Rejected(const void *p, size_t length) {
    try {
        Shipyard::LegacySave::Validate(Bytes(p, length));
        return false;
    } catch (const std::runtime_error &) {
        return true;
    }
}
static unsigned long long digest = 1469598103934665603ULL;
static void Hash(const void *pointer, size_t size) {
    const unsigned char *bytes = static_cast<const unsigned char *>(pointer);
    for (size_t i = 0; i < size; ++i) {
        digest ^= bytes[i];
        digest *= 1099511628211ULL;
    }
}
int main(int argc, char **argv) {
    try {
        assert(argc == 2);
        for (unsigned value = 0; value < 65536; ++value) {
            unsigned char le[] = {static_cast<unsigned char>(value), static_cast<unsigned char>(value >> 8)};
            unsigned char be[] = {le[1], le[0]};
            u16 unsignedValue = 0;
            s16 signedValue = 0, expectedSigned;
            u16 bits = static_cast<u16>(value);
            memcpy(&expectedSigned, &bits, 2);
            Bytes(le, 2).Scalar(0, unsignedValue, Little);
            assert(unsignedValue == bits);
            Bytes(be, 2).Scalar(0, unsignedValue, Big);
            assert(unsignedValue == bits);
            Bytes(le, 2).Scalar(0, signedValue, Little);
            assert(signedValue == expectedSigned);
            Bytes(be, 2).Scalar(0, signedValue, Big);
            assert(signedValue == expectedSigned);
        }
        for (unsigned bit = 0; bit < 32; ++bit) {
            u32 bits = (1u << bit) ^ 0xA5F08013u, decodedBits = 0;
            s32 decodedSigned, expectedSigned;
            unsigned char le[4], be[4];
            for (unsigned i = 0; i < 4; ++i) {
                le[i] = static_cast<unsigned char>(bits >> (8 * i));
                be[3 - i] = le[i];
            }
            memcpy(&expectedSigned, &bits, 4);
            Bytes(le, 4).Scalar(0, decodedBits, Little);
            assert(decodedBits == bits);
            Bytes(be, 4).Scalar(0, decodedBits, Big);
            assert(decodedBits == bits);
            Bytes(le, 4).Scalar(0, decodedSigned, Little);
            assert(decodedSigned == expectedSigned);
            Bytes(be, 4).Scalar(0, decodedSigned, Big);
            assert(decodedSigned == expectedSigned);
        }
        static unsigned char little[0x8000], big[0x8000];
        static SaveContext expected, actual;
        unsigned compared = 0;
        for (unsigned round = 0; round < 32; ++round) {
            memset(Producer::capture, 0, sizeof(Producer::capture));
            Header(Producer::capture);
            for (unsigned slot = 0; slot < 3; ++slot) {
                Producer::Fill(round, slot);
                Producer::Sram_WriteSave(NULL);
            }
            memcpy(little, Producer::capture, sizeof(little));
            memset(Producer::capture, 0, sizeof(Producer::capture));
            Header(Producer::capture);
            for (unsigned slot = 0; slot < 3; ++slot) {
                Producer::Fill(round, slot);
                Producer::WriteBig(slot);
            }
            memcpy(big, Producer::capture, sizeof(big));
            assert(Shipyard::LegacySave::Validate(Bytes(little, sizeof(little))) == Little);
            assert(Shipyard::LegacySave::Validate(Bytes(big, sizeof(big))) == Big);
            for (unsigned slot = 0; slot < 3; ++slot) {
                SaveContext_v0 source, decoded;
                memcpy(&source, little + Shipyard::LegacySave::Slot(slot), sizeof(source));
                memset(&expected, 0, sizeof(expected));
                OriginalCopy(source, expected);
                for (unsigned order = 0; order < 2; ++order) {
                    const unsigned char *data = order ? big : little;
                    Shipyard::LegacySave::Decode(Bytes(data, 0x3CE8), slot, order ? Big : Little, decoded);
                    memset(&actual, 0, sizeof(actual));
                    Shipyard::LegacySave::CopyV0Save(decoded, actual);
                    assert(!memcmp(&actual, &expected, sizeof(actual)));
                    Hash(&actual, sizeof(actual));
                    ++compared;
                }
            }
        }
        // Every possible shorter input must fail before any dereference. Full
        // primary contexts suffice; backup slots are deliberately not consumed.
        for (size_t length = 0; length < 0x3CE8; ++length)
            assert(Rejected(little, length));
        assert(!Rejected(little, 0x3CE8));
        std::vector<unsigned char> unaligned(sizeof(little) + 1);
        memcpy(&unaligned[1], little, sizeof(little));
        assert(Shipyard::LegacySave::Validate(Bytes(&unaligned[1], sizeof(little))) == Little);
        SaveContext_v0 decoded;
        Shipyard::LegacySave::Decode(Bytes(&unaligned[1], sizeof(little)), 0, Little, decoded);
        bool slotRejected = false;
        try {
            Shipyard::LegacySave::Decode(Bytes(little, sizeof(little)), 3, Little, decoded);
        } catch (const std::out_of_range &) {
            slotRejected = true;
        }
        assert(slotRejected);
        unsigned char saved = little[3];
        little[3] ^= 1;
        assert(Rejected(little, sizeof(little)));
        little[3] = saved;
        little[0x20 + 0x1C] ^= 1;
        assert(Rejected(little, sizeof(little)));
        little[0x20 + 0x1C] ^= 1;
        little[0x20 + 0x74] ^= 1;
        assert(Rejected(little, sizeof(little)));
        little[0x20 + 0x74] ^= 1;
        // Mixed producer order in one image is unsupported, not guessed per slot.
        memcpy(unaligned.data(), little, sizeof(little));
        memcpy(unaligned.data() + 0x1470, big + 0x1470, 0x1428);
        assert(Rejected(unaligned.data(), sizeof(little)));
        // Both checksum interpretations can pass. The capacity heuristic must
        // not silently choose LE for the donor's ambiguous 0x0101 case.
        memset(&Producer::backing, 0, sizeof(Producer::backing));
        memset(Producer::capture, 0, sizeof(Producer::capture));
        Header(Producer::capture);
        memcpy(Producer::backing.context.newf, "ZELDAZ", 6);
        Producer::backing.context.healthCapacity = 0x0101;
        Producer::Sram_WriteSave(NULL);
        Bytes ambiguous(Producer::capture, sizeof(Producer::capture));
        assert(Shipyard::LegacySave::Checksum(ambiguous, 0, Little) &&
               Shipyard::LegacySave::Checksum(ambiguous, 0, Big));
        assert(Rejected(Producer::capture, sizeof(Producer::capture)));
        // A modified capacity is accepted when checksum and age resolve order;
        // vanilla hearts are only an ambiguity tiebreaker, not a blanket filter.
        Producer::backing.context.healthCapacity = 0x2222;
        Producer::backing.context.linkAge = 1;
        Producer::Sram_WriteSave(NULL);
        assert(Shipyard::LegacySave::Validate(Bytes(Producer::capture, sizeof(Producer::capture))) == Little);
        // Real stdio producer archive and real runtime read, without an alternate
        // filesystem. Verify validation never changes the source bytes.
        {
            std::ofstream out(argv[1], std::ios::binary);
            out.write(reinterpret_cast<char *>(little), sizeof(little));
            assert(out.good());
        }
        std::vector<unsigned char> read = Shipyard::LegacySave::Read(argv[1]);
        assert(read.size() == sizeof(little) && !memcmp(&read[0], little, sizeof(little)));
        Shipyard::LegacySave::Validate(Bytes(&read[0], read.size()));
        assert(Shipyard::LegacySave::Read(argv[1]) == read);
        bool failedRead = false;
        try {
            Shipyard::LegacySave::Read(std::string(argv[1]) + ".absent");
        } catch (const std::runtime_error &) {
            failedRead = true;
        }
        assert(failedRead);
        memset(Producer::capture, 0, sizeof(Producer::capture));
        Header(Producer::capture);
        assert(!Rejected(Producer::capture, sizeof(Producer::capture)));
        std::cout << "PASS " << compared
                  << " complete modern SaveContext comparisons; 15592 truncations; LE/BE, checksum, mixed/ambiguous, "
                     "unaligned, modified-capacity, real read; digest "
                  << std::hex << digest << "\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << "\n";
        return 2;
    }
}
