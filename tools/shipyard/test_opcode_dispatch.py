"""The projected Fast3D interpreter resolves each opcode once per command."""

import os

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/shipyard"))

from cpp_ast import PARSER, walk

lock = json.loads((ROOT / "platform-base.lock.json").read_text())
sys.path.insert(0, str(Path(os.environ.get("XBOX360_PLATFORM_BASE", ROOT / lock["base"])).resolve() / "python"))
from xbox360_platform import fast3d_opcode


class OpcodeDispatchTests(unittest.TestCase):
    def test_pinned_interpreter_uses_composed_dispatch(self):
        source = (ROOT / "libultraship/src/fast/interpreter.cpp").read_text()
        projected, tables = fast3d_opcode.lower(
            source, PARSER, walk, fast3d_opcode.FAST3D_TABLES, composed_dispatch=True
        )
        self.assertEqual(6, len(tables))
        step = projected.split("static void gfx_step() {", 1)[1].split("\n}", 1)[0]
        name = projected.split("const char* GfxGetOpcodeName(int8_t opcode) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("const auto& handler = ucode_handlers[ucode_handler_index]->at(opcode);", step)
        self.assertIn("const auto& handler = ucode_handlers[ucode_handler_index]->at(opcode);", name)
        fast_step = step.split("// Invalid ucode retains", 1)[0]
        fast_name = name.split("// Preserve the original OTR/RDP priority", 1)[0]
        self.assertNotIn("otrHandlers.contains(opcode)", fast_step)
        self.assertNotIn("rdpHandlers.contains(opcode)", fast_step)
        self.assertNotIn("otrHandlers.contains(opcode)", fast_name)
        self.assertNotIn("rdpHandlers.contains(opcode)", fast_name)
        self.assertIn("if (otrHandlers.contains(opcode))", step)
        self.assertIn("if (rdpHandlers.contains(opcode))", step)
        self.assertIn("f3dex2Dispatch(otrHandlers, rdpHandlers, f3dex2Handlers)", projected)


if __name__ == "__main__":
    unittest.main()
