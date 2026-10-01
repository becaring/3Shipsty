"""Exercise lifetime boundaries against the selected source, including no-op paths."""

from pathlib import Path
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
