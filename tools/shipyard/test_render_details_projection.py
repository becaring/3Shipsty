"""Reject missing Flush attribution and preserve texture lookup results."""

import unittest
from render_details_projection import transform


class ProjectionTests(unittest.TestCase):
    def test_unknown_flush_boundary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unclassified Flush"):
            transform(
                "void Interpreter::Mystery() {\n    Flush();\n}\n", texture_hooks=False
            )

    def test_inline_flush_cannot_silently_escape_attribution(self):
        with self.assertRaisesRegex(ValueError, "Unattributed Flush"):
            transform(
                "void Interpreter::Run() { if (ready) Flush(); }", texture_hooks=False
            )

    def test_empty_and_nonempty_flushes_share_one_observation_boundary(self):
        source = "void Interpreter::Flush() {\n    if (mBufVboLen > 0) {}\n}\nvoid Interpreter::Run(Gfx* commands) {\n    Flush();\n}\n"
        projected = transform(source, texture_hooks=False)
        self.assertEqual(
            projected.count(
                "ModernFrameProfile::ObserveFlush(mBufVboLen ? mBufVboNumTris : 0);"
            ),
            1,
        )
        self.assertEqual(
            projected.count(
                "ModernFrameProfile::SetFlushReason(ModernFrameProfile::FlushFrameEnd);"
            ),
            1,
        )
        self.assertEqual(projected.count("    Flush();"), 1)

    def test_texture_cache_hit_and_miss_keep_their_returns(self):
        source = (
            "bool Interpreter::TextureCacheLookup(int i, const TextureCacheKey& key) {\n"
            "    if (hit) {\n        return true;\n    }\n    return false;\n}\n"
            "void Interpreter::ImportTexture(int i, int tile, bool importReplacement) {\n}\n"
            "void Interpreter::ImportTextureMask(int i, int tile) {\n}\n"
        )
        projected = transform(source)
        self.assertIn("ObserveTextureLookup(true);\n        return true;", projected)
        self.assertIn("ObserveTextureLookup(false);\n    return false;", projected)
        self.assertEqual(projected.count("ObserveTextureImport(false);"), 1)
        self.assertEqual(projected.count("ObserveTextureImport(true);"), 1)

    def test_gui_only_frame_completion_has_its_own_flush_attribution(self):
        projected = transform(
            "void Interpreter::RunGuiOnly() {\n    Flush();\n}\n", texture_hooks=False
        )
        self.assertIn("FlushFrameEnd", projected)


if __name__ == "__main__":
    unittest.main()
