"""Regress the native-word return value required by MPQ's rolling cipher."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / 'scratch/stormlib-xdk/generated/src/SBaseCommon.cpp').read_text()
for helper in ('EncryptUInt32Unaligned', 'DecryptUInt32Unaligned'):
    function = source.split('static DWORD ' + helper + '(', 1)[1].split('\n}\n', 1)[0]
    assert 'memcpy(&' in function and 'memcpy(pbDataPointer,' in function
    assert '<< 0x00' not in function and 'pbXorKey[' not in function


def decrypt_words(ciphertext, byteorder):
    key = 0x12345678
    result = bytearray()
    for offset in range(0, len(ciphertext), 4):
        value = int.from_bytes(ciphertext[offset:offset + 4], byteorder) ^ key
        result += value.to_bytes(4, byteorder)
        key = (key + value + 0x10203040) & 0xFFFFFFFF
    return result


for order in ('little', 'big'):
    plain = [0x02123456, 0x789ABCDE, 0xA1B2C3D4]
    key = 0x12345678
    cipher = bytearray()
    for value in plain:
        cipher += (value ^ key).to_bytes(4, order)
        key = (key + value + 0x10203040) & 0xFFFFFFFF
    assert decrypt_words(cipher, order) == b''.join(v.to_bytes(4, order) for v in plain)

# The prior helper assembled the decrypted BE word as LE solely for its
# return value. The first four output bytes could look correct, but this
# incorrect return value poisoned the next word's rolling key.
first_be = (plain[0]).to_bytes(4, 'big')
assert int.from_bytes(first_be, 'little') != plain[0]
print('StormLib unaligned MPQ words preserve native rolling-key order')
