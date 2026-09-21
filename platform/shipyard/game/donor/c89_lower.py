"""Lower C99 block/for declarations for the XDK C compiler.

Input has already passed through the XDK preprocessor. A late declaration starts
a nested scope ending with its original block; initializers stay at the exact
execution point. A for declaration moves into a scope around that loop. This
does not hoist evaluation, rename variables, or change loop control flow.
"""
from pathlib import Path
import sys
import re
import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scratch/python-tools'))
from tree_sitter import Language, Parser
import tree_sitter_c

PARSER = Parser(Language(tree_sitter_c.language()))


def lower(source: bytes) -> tuple[bytes, int]:
    # Headers need no lowering. Mask them in the parser view (not the output):
    # this avoids parsing the compiler-specific XDK intrinsic declarations and
    # keeps byte offsets identical to the preprocessed compiler input.
    if b'#line ' in source:
        view = bytearray(source)
        offset = 0
        active = False
        for line in source.splitlines(keepends=True):
            marker = re.match(rb'#line \d+ "([^"]+)"', line)
            if marker:
                name = re.sub(rb'\\+', b'/', marker[1].lower())
                active = b'/upstream/' in name and name.endswith((b'.c', b'.inc'))
            if not active or marker:
                view[offset:offset+len(line)] = re.sub(rb'[^\r\n]', b' ', line)
            offset += len(line)
        parse_source = bytes(view)
    else:
        parse_source = source
    tree = PARSER.parse(parse_source)
    inserts = {}
    edits = []
    count = 0

    def insert(at, text):
        inserts[at] = inserts.get(at, b'') + text

    def visit(node):
        nonlocal count
        if node.type == 'initializer_pair':
            designator = node.child_by_field_name('designator')
            value = node.child_by_field_name('value')
            declaration = node.parent
            while declaration and declaration.type != 'declaration':
                declaration = declaration.parent
            decl_type = declaration.child_by_field_name('type') if declaration else None
            if (designator and source[designator.start_byte:designator.end_byte] == b'.f'
                    and decl_type and source[decl_type.start_byte:decl_type.end_byte] == b'CutsceneData'):
                token = source[value.start_byte:value.end_byte].strip()
                token = re.sub(rb'[()\s]', b'', token)
                if not re.fullmatch(rb'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[fF]?', token):
                    raise ValueError('Nonliteral CutsceneData float: ' + repr(token))
                bits = struct.unpack('>I', struct.pack('>f', float(token.rstrip(b'fF'))))[0]
                edits.append((node.start_byte, node.end_byte, f'0x{bits:08X}U'.encode()))
                count += 1
                return
        if node.type == 'compound_statement':
            had_statement = False
            scopes = 0
            for child in node.named_children:
                if child.type in ('comment', 'preproc_call'):
                    continue
                if child.type in ('declaration', 'type_definition'):
                    if had_statement:
                        insert(child.start_byte, b'{ ')
                        scopes += 1
                        count += 1
                        had_statement = False
                else:
                    had_statement = True
            if scopes:
                insert(node.end_byte - 1, b'} ' * scopes)
        if node.type == 'for_statement':
            init = node.child_by_field_name('initializer')
            if init is not None and init.type == 'declaration':
                # Keep newlines inside the declaration so #line diagnostics
                # remain accurate for the original loop body.
                decl = source[init.start_byte:init.end_byte]
                insert(node.start_byte, b'{ ' + decl + b' ')
                edits.append((init.start_byte, init.end_byte, b';'))
                insert(node.end_byte, b' }')
                count += 1
        for child in node.named_children:
            visit(child)

    visit(tree.root_node)
    edits.extend((at, at, text) for at, text in inserts.items())
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source, count
