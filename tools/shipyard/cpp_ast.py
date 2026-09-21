"""Owned host-only tree-sitter C++ parser used by compiler projections."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scratch/python-tools'))
import tree_sitter
import tree_sitter_cpp

PARSER = tree_sitter.Parser(tree_sitter.Language(tree_sitter_cpp.language()))


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def tx(node): return node.text.decode()
def field(node, name): return node.child_by_field_name(name)
