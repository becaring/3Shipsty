"""The soft-dust probe counts emitted draws without changing effect behavior."""

import unittest

from tools.shipyard.prepare_game import ROOT, project_header


SOURCE = 'soh/src/overlays/effects/ovl_Effect_Ss_Dust/z_eff_ss_dust.c'
DECLARATION = (
    'extern void Shipyard_FrameProfileDustDraw(float posX, float posY, float posZ, '
    'float eyeX, float eyeY, float eyeZ, float scale, unsigned flags);\n'
)
CALL = (
    '        Shipyard_FrameProfileDustDraw(this->pos.x, this->pos.y, this->pos.z,\n'
    '                                      play->view.eye.x, play->view.eye.y, play->view.eye.z,\n'
    '                                      scale, (unsigned)this->rDrawFlags);\n'
)


class DustProjectionTests(unittest.TestCase):
    def test_exact_draw_hook_and_no_other_effect_edits(self):
        raw = (ROOT / SOURCE).read_bytes()
        projected, changes = project_header(SOURCE, raw)
        original = raw.decode('utf-8-sig').replace('\r\n', '\n')
        text = projected.decode()
        self.assertEqual(text.count(DECLARATION), 1)
        self.assertEqual(text.count(CALL), 1)
        self.assertIn('gSPDisplayList(POLY_XLU_DISP++, this->gfx);\n' + CALL, text)
        self.assertLess(text.index('    if (mtx != NULL) {'), text.index(CALL))
        self.assertLess(text.index(CALL), text.index('    CLOSE_DISPS(gfxCtx);', text.index(CALL)))
        self.assertEqual(text.replace(DECLARATION, '').replace(CALL, ''), original)
        self.assertEqual(len(changes), 1)


if __name__ == '__main__':
    unittest.main()
