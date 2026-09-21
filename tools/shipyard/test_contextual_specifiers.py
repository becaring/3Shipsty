"""Contextual C++ keywords must not corrupt application identifiers or strings."""
import unittest
from prepare_resource_manager import syntax

class ContextualSpecifiers(unittest.TestCase):
    def test_only_virtual_specifiers_are_removed(self):
        original = '''class C final : public B { void f() override final;
int overrideIndex; int override; int final;
void g() { data.override = overrideIndex; }
const char* text = " override final :"; // override final :
};'''
        expected = original.replace('C final :', 'C :').replace('f() override final;', 'f();')
        self.assertEqual(expected, syntax(original))

if __name__ == '__main__': unittest.main()
