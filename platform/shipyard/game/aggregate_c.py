"""Audited rvalue compound literals; typed helpers preserve scalar conversions."""
import semantic_bool

ARITIES = {b'Color_RGB8': 3, b'Color_RGBA8': 4, b'GetItemEntry': 15}


def ordered_designators(source, parser, permitted):
    """Remove designators only where source-locked field order is identical."""
    def walk(node):
        yield node
        for child in node.named_children: yield from walk(child)
    edits = []
    patterns = []
    for node in walk(parser.parse(source).root_node):
        if node.type != 'initializer_list': continue
        children = [child for child in node.named_children if child.type != 'comment']
        pairs = [child for child in children if child.type == 'initializer_pair']
        if not pairs: continue
        if len(pairs) != len(children): raise ValueError('Mixed designated/positional initialization requires type audit')
        names = []
        for pair in pairs:
            designators = [child for child in pair.named_children if child.type == 'field_designator']
            if len(designators) != 1: raise ValueError('Nested/array designator requires type audit')
            names.append(designators[0].text.decode().removeprefix('.'))
        pattern = tuple(names)
        if pattern not in permitted: raise ValueError('Designator order differs from audited type: ' + str(pattern))
        patterns.append(pattern)
        for pair in pairs:
            value = pair.child_by_field_name('value')
            if value is None: raise ValueError('Designated initializer value missing')
            edits.append((pair.start_byte, value.start_byte, b''))
    for begin, end, replacement in sorted(edits, reverse=True):
        source = source[:begin] + replacement + source[end:]
    return source, patterns


def lower(source, parser):
    def walk(node):
        yield node
        for child in node.named_children: yield from walk(child)
    edits = []
    for node in walk(parser.parse(semantic_bool.parse_view(source)).root_node):
        if node.type != 'compound_literal_expression': continue
        typ = node.child_by_field_name('type')
        if not typ or typ.text not in ARITIES: continue
        owner = node.parent
        while owner and owner.type != 'function_definition': owner = owner.parent
        if not owner: raise ValueError('File-scope compound object requires storage-preserving projection')
        parent = node.parent
        while parent and parent.type == 'parenthesized_expression': parent = parent.parent
        if parent and parent.type in ('pointer_expression', 'update_expression', 'field_expression'):
            raise ValueError('Compound object lvalue/address use requires lifetime-preserving projection')
        if parent and parent.type == 'assignment_expression' and parent.child_by_field_name('left') == node:
            raise ValueError('Compound object assignment target requires storage')
        value = node.child_by_field_name('value')
        args = [child for child in value.named_children if child.type != 'comment']
        if any(child.type == 'initializer_pair' for child in args):
            raise ValueError('Compound designated initialization requires typed ordering')
        if len(args) != ARITIES[typ.text]:
            raise ValueError('Compound field count changed: ' + typ.text.decode())
        body = source[value.start_byte + 1:value.end_byte - 1]
        edits.append((node.start_byte, node.end_byte, b'Shipyard_Make' + typ.text + b'(' + body + b')'))
    for begin, end, replacement in sorted(edits, reverse=True):
        source = source[:begin] + replacement + source[end:]
    return source, len(edits)
