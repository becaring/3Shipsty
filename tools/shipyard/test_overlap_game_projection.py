"""Check loop ownership and arena lifetime hooks against the pinned game source."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class OverlapGameProjectionTests(unittest.TestCase):
    def test_outer_loop_keeps_original_state_machine(self):
        from overlap_game_projection import project

        name = "soh/src/code/graph.c"
        source = (ROOT / name).read_text(encoding="utf-8-sig")
        projected = project(name, source)
        start = source.index("static void RunFrame() {")
        end = source.index("void Graph_ThreadEntry", start)
        self.assertIn(source[start:end], projected)
        self.assertIn("if (!Shipyard_OverlapRunFrame(RunFrame)) RunFrame();", projected)
        self.assertIn("    Shipyard_OverlapShutdown();", projected)

    def test_public_arena_free_and_hidden_realloc_paths_are_covered(self):
        from overlap_game_projection import project

        name = "soh/src/code/__osMalloc.c"
        source = project(name, (ROOT / name).read_text(encoding="utf-8-sig"))
        self.assertIn(
            "Shipyard_OverlapDeferRelease(Shipyard_ArenaFree, arena, ptr, NULL, 0)",
            source,
        )
        self.assertIn(
            "Shipyard_OverlapDeferRelease(Shipyard_ArenaFreeDebug, arena, ptr, file, line)",
            source,
        )
        start = source.index(
            "void* __osRealloc(Arena* arena, void* ptr, size_t newSize) {"
        )
        end = source.index("    ArenaImpl_Lock(arena);", start)
        self.assertIn("Shipyard_OverlapFence();", source[start:end])


if __name__ == "__main__":
    unittest.main()
