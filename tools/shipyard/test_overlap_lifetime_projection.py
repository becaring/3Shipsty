"""Exercise lifetime boundaries against the selected source, including no-op paths."""

from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class LifetimeProjectionTests(unittest.TestCase):
    def source(self, name):
        from overlap_lifetime_projection import project

        return project(name, (ROOT / name).read_text(encoding="utf-8-sig"))

    def test_skin_checks_borrowed_vertices_without_extra_pool_allocation(self):
        text = self.source("soh/src/code/z_skin.c")
        self.assertIn(
            "Shipyard_OverlapTouchWritableSpan(vtxBuf, data->totalVtxCount * sizeof(Vtx))",
            text,
        )
        self.assertIn("vtxBuf = vtxEntry->buf[vtxEntry->index]", text)
        self.assertIn(
            "gSPSegment(POLY_OPA_DISP++, 0x08, vtxEntry->buf[vtxEntry->index])", text
        )
        self.assertNotIn("Graph_Alloc(gfxCtx, data->totalVtxCount * sizeof(Vtx))", text)
        self.assertNotIn("Shipyard_OverlapFence();", text)

    def test_font_slot_writes_wait_only_when_bytes_change(self):
        text = self.source("soh/src/code/z_kanfont.c")
        self.assertEqual(text.count("Shipyard_OverlapFence();"), 5)
        self.assertIn(
            "if (memcmp(font->iconBuf, msgStaticTbl[4 + icon], strlen(msgStaticTbl[4 + icon]) + 1) != 0) {"
            " Shipyard_OverlapFence(); memcpy(font->iconBuf,",
            text,
        )
        text = self.source("soh/src/code/z_message_PAL.c")
        self.assertEqual(
            text.count(
                "if (font->charTexBuf[0] != messageTableEntry->typePos) { Shipyard_OverlapFence();"
                " font->charTexBuf[0] = messageTableEntry->typePos; }"
            ),
            5,
        )

    def test_actor_destroy_waits_before_callback(self):
        text = self.source("soh/src/code/z_actor.c")
        start = text.index("void Actor_Destroy(")
        end = text.index("void Actor_UpdatePos", start)
        body = text[start:end]
        self.assertLess(
            body.index("Shipyard_OverlapFence();"),
            body.index("actor->destroy(actor, play)"),
        )

    def test_empty_debug_vectors_do_not_fence(self):
        text = self.source("soh/soh/Enhancements/debugger/colViewer.cpp")
        self.assertIn(
            "if (!opaDl.empty() || !xluDl.empty()) Shipyard_OverlapFence();", text
        )

    def test_disabled_viewer_preserves_borrowed_lists_and_reenable_fences(self):
        from overlap_lifetime_projection import functions

        text = self.source("soh/soh/Enhancements/debugger/colViewer.cpp")
        (function,) = functions(text, "DrawColViewer")
        fixture = ROOT / "tools/shipyard/tests/col_viewer_lifetime_fixture.cpp"
        source = fixture.read_text().replace("// DRAW_COL_VIEWER", function.text.decode())
        folder = ROOT / "scratch/col-viewer-lifetime"
        folder.mkdir(parents=True, exist_ok=True)
        unit = folder / "contract.cpp"
        unit.write_text(source)
        compiler, env = runpy.run_path(str(ROOT / "tools/shipyard/tests/test_binary.py"))[
            "host_environment"
        ]()
        executable = folder / "contract.exe"
        build = subprocess.run(
            [str(compiler), "/nologo", "/std:c++20", "/EHsc", "/MD", "/O2", str(unit),
             "/Fo:" + str(folder) + "/", "/Fe:" + str(executable)],
            cwd=folder, env=env, capture_output=True, text=True,
        )
        (folder / "build.log").write_text(build.stdout + build.stderr)
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        result = subprocess.run([str(executable)], cwd=folder, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_graphics_reads_use_snapshot_and_native_mutations_dispatch(self):
        text = self.source("soh/soh/OTRGlobals.cpp")
        self.assertIn("Shipyard_OverlapCaptureGraphics", text)
        self.assertIn(
            "if (Shipyard_OverlapIsGameWorker()) return shipyardGraphics.aspect;", text
        )
        self.assertIn("Shipyard_OverlapRunOnRender", text)

    def test_patch_fences_only_if_instruction_changes(self):
        text = self.source("soh/soh/ResourceManagerHelpers.cpp")
        self.assertIn("memcmp(gfx, &instruction, sizeof(Gfx)) != 0", text)


if __name__ == "__main__":
    unittest.main()
