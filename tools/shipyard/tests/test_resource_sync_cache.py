"""Guard the XDK synchronous resource-cache fast path against source drift."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from prepare_resource_manager import transform


class SyncCacheFastPath(unittest.TestCase):
    def test_hit_avoids_future_without_changing_miss(self):
        source = (ROOT / "libultraship/src/ship/resource/ResourceManager.cpp").read_text(
            encoding="utf-8-sig"
        )
        projected = transform("src/ship/resource/ResourceManager.cpp", source)
        start = projected.index(
            "std::shared_ptr<IResource> ResourceManager::LoadResource(const ResourceIdentifier&"
        )
        end = projected.index(
            "std::shared_ptr<IResource> ResourceManager::LoadResource(const std::string&", start
        )
        body = projected[start:end]
        lookup = body.index("auto cachedResource = GetCachedResource(identifier, loadExact);")
        early_return = body.index("return cachedResource;", lookup)
        inline_miss = body.index("resource = LoadResourceProcess(identifier, loadExact, initData);")
        self.assertLess(lookup, early_return)
        self.assertLess(early_return, inline_miss)
        self.assertEqual(body.count("GetCachedResource(identifier, loadExact)"), 1)
        # A miss loads on the calling thread; no worker handoff or future.
        self.assertNotIn("LoadResourceAsync(", body)
        self.assertNotIn(".get()", body)
        self.assertIn("if (resource == nullptr)", body[inline_miss:])
        # The async API retains its original cache and worker behavior.
        async_start = projected.index("ResourceManager::LoadResourceAsync(const ResourceIdentifier&")
        async_end = projected.index("ResourceManager::LoadResourceAsync(const std::string&", async_start)
        async_body = projected[async_start:async_end]
        self.assertIn("GetCachedResource(identifier, loadExact)", async_body)
        self.assertIn("mThreadPool->submit_task(", async_body)


if __name__ == "__main__":
    unittest.main()
