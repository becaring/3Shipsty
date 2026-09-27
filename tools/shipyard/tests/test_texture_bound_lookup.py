"""Differential coverage for the projected same-bound texture cache hit."""
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
import prepare_fast3d
from xbox360_platform import texture_state


class BoundTextureLookupTests(unittest.TestCase):
    def test_projected_fast_hit_keeps_the_authoritative_hit_body(self):
        source = (ROOT / "libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected = prepare_fast3d.texture_bindings(source)
        begin = projected.index("bool Interpreter::TextureCacheLookup(")
        end = projected.index("\nstd::string Interpreter::GetBaseTexturePath", begin)
        body = projected[begin:end]
        self.assertIn("mXboxTextureBindings.Bound<TextureCacheNode>(i)", body)
        self.assertIn("xboxBoundNode->first == key", body)
        self.assertIn("xboxBoundNode->second.lru_location->it", body)
        self.assertIn("mTextureCache.map.find(key)", body)
        self.assertIn("mTextureCache.lru.splice(mTextureCache.lru.end(), mTextureCache.lru,", body)
        self.assertIn("mXboxTextureBindings.NeedsSelect(i,node,it->second.texture_id,sampler)", body)

    def test_bound_certificate_survives_mixed_key_and_invalidation_sequences(self):
        # Model the actual map/LRU/binding contract. The fast lookup may use a
        # bound node only until an eviction, clear, delete, or backend change.
        class Cache:
            def __init__(self, fast):
                self.fast = fast
                self.data = {}
                self.lru = []
                self.bound = [None, None]
                self.finds = 0
                self.hits = 0
                self.next_id = 1
                self.free_ids = []

            def lookup(self, slot, key):
                bound = self.bound[slot]
                if self.fast and bound is not None and bound[0] == key:
                    assert self.data[key] == bound[1]
                    value = bound[1]
                else:
                    self.finds += 1
                    value = self.data.get(key)
                if value is not None:
                    self.hits += 1
                    self.lru.remove(key)
                    self.lru.append(key)
                    self.bound[slot] = (key, value)
                    return True
                if len(self.data) == 4:
                    old = self.lru.pop(0)
                    self.free_ids.append(self.data.pop(old))
                    self.bound = [None, None]
                value = self.free_ids.pop() if self.free_ids else self.next_id
                if value == self.next_id:
                    self.next_id += 1
                self.data[key] = value
                self.lru.append(key)
                self.bound[slot] = (key, value)
                return False

            def invalidate(self, kind, key=None):
                self.bound = [None, None]
                if kind == "clear":
                    self.free_ids.extend(self.data.values())
                    self.data.clear()
                    self.lru.clear()
                elif kind == "delete":
                    for member in list(self.data):
                        if member[0] == key:
                            self.free_ids.append(self.data.pop(member))
                            self.lru.remove(member)

            def state(self):
                return (self.data.copy(), self.lru[:], self.bound[:],
                        self.free_ids[:], self.next_id, self.hits)

        rng = random.Random(0xD1FF)
        original, fast = Cache(False), Cache(True)
        for _ in range(4000):
            op = rng.randrange(20)
            if op == 0:
                for cache in (original, fast):
                    cache.invalidate("clear")
            elif op == 1:
                addr = rng.randrange(5)
                for cache in (original, fast):
                    cache.invalidate("delete", addr)
            elif op == 2:
                for cache in (original, fast):
                    cache.invalidate("backend")
            else:
                slot = rng.randrange(2)
                # Favor repeated bound textures while still testing key fields.
                key = fast.bound[slot][0] if op > 8 and fast.bound[slot] else (rng.randrange(5), rng.randrange(3))
                self.assertEqual(original.lookup(slot, key), fast.lookup(slot, key))
            self.assertEqual(original.state(), fast.state())
        self.assertGreater(original.finds - fast.finds, 1000)

    def test_texture_image_metadata_is_borrowed_until_state_copy(self):
        header = (ROOT / "libultraship/include/fast/interpreter.h").read_text(encoding="utf-8-sig")
        source = (ROOT / "libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected_header = prepare_fast3d.header(header)[0]
        projected_source = texture_state.metadata_reference(source)
        signature = "const RawTexMetadata& rawTexMetdata, const void* addr)"
        self.assertIn(signature, projected_header)
        self.assertIn(signature, projected_source)
        begin = projected_source.index("void Interpreter::GfxDpSetTextureImage(")
        end = projected_source.index("\nvoid Interpreter::GfxDpSetTile(", begin)
        self.assertIn("mRdp->texture_to_load.raw_tex_metadata = rawTexMetdata;", projected_source[begin:end])


if __name__ == "__main__":
    unittest.main()
