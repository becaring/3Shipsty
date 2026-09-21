import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]

class GameProjectionTests(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
