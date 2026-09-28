import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]

class GameProjectionTests(unittest.TestCase):
    def test_game_update_profile_wraps_only_the_update_call(self):
        module = self.module()
        name = 'soh/src/code/graph.c'
        output, _ = module.project_header(name, (ROOT / name).read_bytes())
        self.assertEqual(output.count(b'Shipyard_FrameProfileGameUpdateBegin();'), 1)
        self.assertEqual(output.count(b'Shipyard_FrameProfileGameUpdateEnd();'), 1)
        begin = output.index(b'Shipyard_FrameProfileGameUpdateBegin();')
        update = output.index(b'GameState_Update(gameState);', begin)
        end = output.index(b'Shipyard_FrameProfileGameUpdateEnd();', update)
        self.assertLess(begin, update)
        self.assertLess(update, end)

    def test_game_update_subphases_wrap_the_real_calls(self):
        module = self.module()
        cases = (
            ('soh/src/code/z_play.c', b'Shipyard_FrameProfilePlayUpdate', b'Play_Update(play);'),
            ('soh/src/code/z_play.c', b'Shipyard_FrameProfilePlayDrawRecord', b'FrameInterpolation_StartRecord();',
             b'Play_Draw(play);', b'FrameInterpolation_StopRecord();'),
            ('soh/src/code/z_play.c', b'Shipyard_FrameProfileSceneRoomDraw', b'Scene_Draw(play);',
             b'Room_Draw(play, &play->roomCtx.curRoom, roomDrawFlags & 3);',
             b'Room_Draw(play, &play->roomCtx.prevRoom, roomDrawFlags & 3);'),
            ('soh/src/code/z_play.c', b'Shipyard_FrameProfileActorDraw',
             b'func_800315AC(play, &play->actorCtx);'),
            ('soh/src/code/game.c', b'Shipyard_FrameProfileGameStateDraw', b'GameState_Draw(gameState, gfxCtx);'),
        )
        for name, prefix, *calls in cases:
            with self.subTest(phase=prefix):
                output, _ = module.project_header(name, (ROOT / name).read_bytes())
                begin = prefix + b'Begin();'
                end = prefix + b'End();'
                self.assertEqual(output.count(begin), 1)
                self.assertEqual(output.count(end), 1)
                begin_at = output.index(begin)
                end_at = output.index(end, begin_at)
                call_positions = [output.index(call, begin_at) for call in calls]
                self.assertEqual(call_positions, sorted(call_positions))
                self.assertTrue(all(begin_at < pos < end_at for pos in call_positions))

    def test_actor_draw_samples_callbacks_and_separates_effects(self):
        module = self.module()
        name = 'soh/src/code/z_actor.c'
        output, _ = module.project_header(name, (ROOT / name).read_bytes())
        start = output.index(b'void func_800315AC(')
        end = output.index(b'void func_80031A28(', start)
        body = output[start:end]
        self.assertEqual(body.count(b'Shipyard_FrameProfileActorInstanceBegin(actor->id)'), 1)
        self.assertEqual(body.count(b'Shipyard_FrameProfileActorInstanceEnd(actor->id, actorProfileStart)'), 1)
        self.assertLess(body.index(b'Shipyard_FrameProfileActorInstanceBegin(actor->id)'),
                        body.index(b'Actor_Draw(play, actor);'))
        self.assertLess(body.index(b'Actor_Draw(play, actor);'),
                        body.index(b'Shipyard_FrameProfileActorInstanceEnd(actor->id, actorProfileStart)'))
        for phase, call in ((b'Effect', b'Effect_DrawAll(play->state.gfxCtx);'),
                            (b'EffectSs', b'EffectSs_DrawAll(play);'),
                            (b'LightsGlow', b'Lights_DrawGlow(play);')):
            begin = b'Shipyard_FrameProfile' + phase + b'Begin();'
            finish = b'Shipyard_FrameProfile' + phase + b'End();'
            self.assertEqual(body.count(begin), 1)
            self.assertEqual(body.count(finish), 1)
            self.assertLess(body.index(begin), body.index(call))
            self.assertLess(body.index(call), body.index(finish))

    def test_actor_draw_sample_boundaries_preserve_callback_and_shadow_order(self):
        module = self.module()
        name = 'soh/src/code/z_actor.c'
        output, _ = module.project_header(name, (ROOT / name).read_bytes())
        start = output.index(b'void Actor_Draw(PlayState* play, Actor* actor) {')
        end = output.index(b'void func_800315AC(', start)
        body = output[start:end]
        markers = (
            b'Lights_Draw(lights, play->state.gfxCtx);',
            b'Shipyard_FrameProfileActorInstanceAdvance(actor->id, 1);',
            b'Actor_SetObjectDependency(play, actor);',
            b'Shipyard_FrameProfileActorInstanceAdvance(actor->id, 2);',
            b'actor->draw(actor, play);',
            b'Shipyard_FrameProfileActorInstanceAdvance(actor->id, 3);',
            b'Shipyard_FrameProfileActorInstanceAdvance(actor->id, 4);',
            b'actor->shape.shadowDraw(actor, lights, play);',
            b'Shipyard_FrameProfileActorInstanceAdvance(actor->id, 5);',
            b'FrameInterpolation_RecordCloseChild();',
        )
        positions = [body.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        for stage in range(1, 6):
            self.assertEqual(body.count(f'Shipyard_FrameProfileActorInstanceAdvance(actor->id, {stage});'.encode()), 1)

    def module(self):
        path = ROOT / 'tools/shipyard/prepare_game.py'
        self.assertTrue(path.is_file(), 'game compiler projection missing')
        spec = importlib.util.spec_from_file_location('prepare_game', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_true_c_boolean_stores_calls_pointers_and_returns(self):
        module = self.module()
        original = b'const char *s="_Bool this"; /* this */\n_Bool f(int this) { return this; }\nvoid sink(_Bool b); void set(_Bool *p, int x) { *p=x; } void caller(void) { _Bool b=256; sink(-256); set(&b,256); }\n'
        output, _ = module.lower_c(original)
        self.assertIn(b'"_Bool this"', output)
        self.assertIn(b'/* this */', output)
        self.assertIn(b'unsigned char f(int this) { return !!(this); }', output)
        self.assertIn(b'b=!!(256)', output)
        self.assertIn(b'sink(!!(-256))', output)
        self.assertIn(b'*p=!!(x)', output)
        self.assertNotIn(b'extern "C"', output)

    def test_unknown_boolean_pointer_writer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.module().lower_c(b'void unknown(void*); void f(void) { _Bool b=0; unknown(&b); }')

    def test_bool_compound_store_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Compound boolean'):
            self.module().lower_c(b'void f(void) { _Bool b=0; b+=256; }')

    def test_typed_compound_rvalue_and_lifetime_rejections(self):
        output, stats = self.module().lower_c(b'typedef struct { unsigned char r,g,b; } Color_RGB8; Color_RGB8 f(int x) { return (Color_RGB8){x++,256,-1}; }')
        self.assertIn(b'Shipyard_MakeColor_RGB8(x++,256,-1)', output)
        self.assertEqual(stats['typed_compound_literals'], 1)
        for code in [b'void f(void) { &(Color_RGB8){1,2,3}; }',
                     b'Color_RGB8 *p=&(Color_RGB8){1,2,3};',
                     b'void f(void) { (Color_RGB8){1,2}; }',
                     b'void f(void) { (Color_RGB8){.r=1,.g=2,.b=3}; }']:
            with self.assertRaises(ValueError): self.module().lower_c(code)

    def test_message_factories_and_randomizer_macro(self):
        module = self.module()
        name = 'libultraship/include/libultraship/libultra/message.h'
        output, _ = module.project_header(name, (ROOT / name).read_bytes())
        self.assertIn(b'Shipyard_MesgPtr', output)
        self.assertNotIn(b'((OSMesg){', output)
        name = 'soh/soh/Enhancements/randomizer/randomizerEnums.h'
        output, _ = module.project_header(name, (ROOT / name).read_bytes())
        self.assertNotIn(b'__VA_OPT__', output)

    def test_xbox_main_pins_title_thread_before_startup(self):
        module = self.module()
        name = 'soh/src/code/main.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertEqual(output.count(b'XSetThreadProcessor(GetCurrentThread(), 0)'), 1)
        self.assertLess(output.index(b'XSetThreadProcessor(GetCurrentThread(), 0)'),
                        output.index(b'GameConsole_Init();'))
        self.assertLess(output.index(b'GameConsole_Init();'), output.index(b'Shipyard_TryInitOTR(argc, argv))'))
        self.assertIn(b'#ifdef _XBOX\n#include <xtl.h>\nextern void Shipyard_InstallStartupFaultHandler(void);\nextern int Shipyard_TryInitOTR(int argc, char* argv[]);\n#endif', output)
        self.assertLess(output.index(b'Shipyard_InstallStartupFaultHandler();'),
                        output.index(b'GameConsole_Init();'))
        self.assertIn(b'if (!Shipyard_TryInitOTR(argc, argv)) return 1;', output)
        self.assertTrue(any('application-thread placement' in change for change in changes))

    def test_bool_pointer_alias_and_aggregate_initialization_rejected(self):
        for code in [b'void f(void) { _Bool b=0; void *p=&b; }',
                     b'void f(void) { _Bool b=0; void *p; p=&b; }',
                     b'typedef struct { _Bool enabled; } Flags; Flags f={256};',
                     b'struct Flags { _Bool enabled; }; struct Flags f={256};']:
            with self.assertRaises(ValueError):
                self.module().lower_c(code)

    def test_nested_boolean_aggregate_and_indirect_input_rejected(self):
        for code in [b'typedef struct { _Bool b; } F; typedef F Alias; Alias a={256};',
                     b'typedef struct { _Bool b; } F; typedef struct { F f; } G; G g={{256}};',
                     b'typedef void (*Fn)(_Bool);', b'int f(void) { return (_Bool){256}; }']:
            with self.assertRaises(ValueError):
                self.module().lower_c(code)

    def test_case_declaration_scope_preserves_fallthrough_visibility(self):
        output, _ = self.module().lower_c(b'int f(int x) { switch(x) { case 0: x++; int value=x; case 1: return value; default: return 0; } }')
        self.assertIn(b'{ int value=x; case 1: return value;', output)
        self.assertIn(b'default: return 0; } }', output)

    def test_is_zero_does_not_replace_float_suffix(self):
        name='soh/include/z64math.h'
        output, _=self.module().project_header(name,(ROOT/name).read_bytes())
        self.assertIn(b'#define IS_ZERO(value) (fabsf(value) < 0.008f)',output)

    def test_xbox_runtime_state_trace_is_projected_at_real_state_boundaries(self):
        module = self.module()
        name = 'soh/src/code/graph.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertIn(b'Shipyard_RuntimeTrace("GAMESTATE init begin', output)
        self.assertIn(b'Shipyard_RuntimeTrace("GAMESTATE first frame', output)
        self.assertIn(b'Shipyard_RuntimeTrace("GAMESTATE transition', output)
        self.assertIn(b'#ifndef _XBOX\n        if (!hasSetupSkybox)', output)
        self.assertTrue(any('gamestate boundary trace' in change for change in changes))

    def test_file_select_trace_is_bounded_and_reports_fade_state(self):
        module = self.module()
        name = 'soh/src/overlays/gamestates/ovl_file_choose/z_file_choose.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertIn(b'FILESELECT frame=%u menu=%d config=%d fill=%d', output)
        self.assertIn(b'this->state.frames < 12', output)
        self.assertIn(b'Skybox_InitWithEnvironment(&this->state, &this->envCtx, &this->skyboxCtx', output)
        self.assertTrue(any('file-select fade trace' in change for change in changes))

    def test_skybox_owner_environment_is_explicit(self):
        module = self.module()
        name = 'soh/src/code/z_vr_box.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertIn(b'Skybox_SetupEnvironment(EnvironmentContext* envCtx', output)
        self.assertIn(b'Skybox_InitContext(state, envCtx, skyboxCtx, skyboxId)', output)
        self.assertIn(b'Skybox_InitContext(state, &((PlayState*)state)->envCtx', output)
        self.assertNotIn(b'play->envCtx.skybox', output)
        self.assertTrue(any('owner-aware skybox' in change for change in changes))

    def test_message_trace_brackets_tables_and_font_without_skipping_them(self):
        module = self.module()
        name = 'soh/src/code/z_construct.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        for marker in (b'MESSAGE tables begin', b'MESSAGE tables end',
                       b'MESSAGE font begin', b'MESSAGE font end'):
            self.assertEqual(output.count(marker), 1)
        self.assertIn(b'    Message_SetTables();', output)
        self.assertIn(b'        Font_LoadOrderedFontNTSC(&play->msgCtx.font);', output)
        self.assertTrue(any('message-table' in change for change in changes))

    def test_japanese_o2r_codes_are_converted_only_on_native_font_copies(self):
        module = self.module()
        font_name = 'soh/src/code/z_kanfont.c'
        font, font_changes = module.project_header(font_name, (ROOT / font_name).read_bytes())
        self.assertIn(b'destination[index] = (u16)bytes[index * 2] | ((u16)bytes[index * 2 + 1] << 8);', font)
        self.assertIn(b'Shipyard_CopyJpnMessage(font->msgBufWide, msgEntry->segment, size);', font)
        self.assertNotIn(b'memcpy(font->msgBuf, msgEntry->segment, size);', font)
        self.assertTrue(any('serialized Japanese ordered-font' in change for change in font_changes))

        message_name = 'soh/src/code/z_message_PAL.c'
        message, message_changes = module.project_header(message_name, (ROOT / message_name).read_bytes())
        self.assertIn(b'if (gSaveContext.language == LANGUAGE_JPN && !sDisplayNextMessageAsEnglish)', message)
        self.assertIn(b'Shipyard_CopyJpnMessage(font->msgBufWide, src, font->msgLength);', message)
        self.assertIn(b'memcpy(font->msgBuf, src, font->msgLength);', message)
        self.assertTrue(any('serialized Japanese dialog' in change for change in message_changes))

        # Representative ordered-font code units, including the real terminator.
        serialized = bytes.fromhex('4f 82 50 82 a0 82 70 81')
        self.assertEqual([int.from_bytes(serialized[i:i + 2], 'little')
                          for i in range(0, len(serialized), 2)],
                         [0x824f, 0x8250, 0x82a0, 0x8170])
        self.assertEqual(int.from_bytes(serialized[4:6], 'big'), 0xa082)

    def test_jpeg_magic_is_checked_as_serialized_bytes_on_xenon(self):
        module = self.module()
        name = 'soh/src/code/z_room.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        function = output.split(b's32 swapAndConvertJPEG(void* data) {', 1)[1].split(b'void Room_DrawBackground2D(', 1)[0]
        self.assertIn(b'jpegBytes[0] == 0xFF && jpegBytes[1] == 0xD8', function)
        self.assertIn(b'jpegBytes[2] == 0xFF && jpegBytes[3] == 0xE0', function)
        self.assertNotIn(b'BE32SWAP(*(u32*)data)', function)
        self.assertIn(b'ResourceMgr_LoadJPEG(data, size)', function)
        magic = bytes.fromhex('ffd8ffe0')
        self.assertEqual(int.from_bytes(magic, 'big'), 0xFFD8FFE0)
        self.assertNotEqual(int.from_bytes(magic, 'little'), 0xFFD8FFE0)
        self.assertTrue(any('JPEG background decode' in change for change in changes))

    def test_game_c_uses_xenon_native_endian_for_packed_runtime_fields(self):
        module = self.module()
        name = 'libultraship/include/ship/utils/binarytools/endianness.h'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertEqual(output.count(b'defined(_XBOX) && defined(_M_PPC)'), 2)
        self.assertIn(b'#define IS_BIGENDIAN', output)
        self.assertIn(b'#define BE32SWAP(x) (x)', output)
        self.assertIn(b'#define LE32SWAP(x) BOMSWAP32(x)', output)
        self.assertTrue(any('packed colors and audio commands' in change for change in changes))

    def test_audio_state_probe_is_bounded_after_real_synthesis(self):
        module = self.module()
        name = 'soh/src/code/code_800E4FE0.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        self.assertEqual(output.count(b'AUDIO synth task='), 1)
        self.assertLess(output.index(b'AudioSynth_Update(gAudioContext.curAbiCmdBuf'),
                        output.index(b'AUDIO synth task='))
        self.assertIn(b'gAudioContext.totalTaskCnt == 1200', output)
        self.assertTrue(any('native synthesis states' in change for change in changes))

    def test_gameplay_init_trace_brackets_real_startup_calls(self):
        module = self.module()
        name = 'soh/src/code/z_play.c'
        output, changes = module.project_header(name, (ROOT / name).read_bytes())
        for marker in (b'PLAY_INIT realloc begin', b'PLAY_INIT realloc end',
                       b'PLAY_INIT kaleido end', b'PLAY_INIT cameras end',
                       b'PLAY_INIT regs end', b'PLAY_INIT message end',
                       b'PLAY_INIT gameover end', b'PLAY_INIT sound end',
                       b'PLAY_INIT effects end', b'PLAY_INIT soft effects end',
                       b'PLAY_INIT collision end', b'PLAY_INIT animation end',
                       b'PLAY_INIT systems end', b'PLAY_INIT cutscene triggers end',
                       b'PLAY_INIT skybox begin',
                       b'PLAY_INIT scene begin', b'PLAY_INIT scene end',
                       b'PLAY_INIT actors begin', b'PLAY_INIT actors end',
                       b'PLAY_INIT room end'):
            self.assertEqual(output.count(marker), 1)
        self.assertIn(b'Skybox_Setup(play, &play->skyboxCtx, SKYBOX_NORMAL_SKY);', output)
        self.assertLess(output.index(b'Skybox_Setup(play, &play->skyboxCtx, SKYBOX_NORMAL_SKY);'),
                        output.index(b'    Play_SpawnScene('))
        self.assertTrue(any('Play_Init allocation' in change for change in changes))

if __name__ == '__main__':
    unittest.main()
