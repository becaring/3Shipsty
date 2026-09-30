"""Guard the binary display-list repair for shared gameplay_keep vertex loads."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/shipyard"))
from prepare_fast_resources import transform


class SharedVertexRepair(unittest.TestCase):
    def test_binary_reader_repairs_before_returning(self):
        name = "src/fast/resource/factory/DisplayListFactory.cpp"
        source = (ROOT / "libultraship" / name).read_text(encoding="utf-8-sig")
        projected = transform(name, source)
        helper = projected.index("void XboxRepairSharedVertexLoads(std::vector<Gfx>& commands, const std::string& path)")
        binary = projected.index("ResourceFactoryBinaryDisplayListV0::ReadResource(")
        xml = projected.index("ResourceFactoryXMLDisplayListV0::ReadResource(")
        call = projected.index("XboxRepairSharedVertexLoads(displayList->Instructions, initData->Path);")
        self.assertLess(helper, binary)
        self.assertLess(binary, call)
        self.assertLess(call, xml)
        self.assertEqual(projected.count("XboxRepairSharedVertexLoads("), 2)
        # Both damaged lists load four vertices at index 0 from the same span.
        for path in ("objects/object_zo/gZoraRipplesModelDL", "objects/object_fish/gFishingRippleModelDL"):
            self.assertIn('{ "' + path + '", "objects/gameplay_keep/gameplay_keepVtx_01A120", 4 }', projected)
        # Only the exact damaged shape is rebuilt; the swallowed command is restored.
        body = projected[helper:binary]
        self.assertIn("(w0 & 0x00FFFFFF) != 0 || commands[i].words.w1 != 0", body)
        self.assertIn("commands.insert(commands.begin() + (i + 2), swallowed);", body)


if __name__ == "__main__":
    unittest.main()
