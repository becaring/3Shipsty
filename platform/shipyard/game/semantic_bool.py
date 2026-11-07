"""Fail-closed scalar/pointer _Bool conversions for preprocessed game C.

Storage becomes a byte only after scalar stores, casts, returns and direct-call
arguments are canonicalized. This intentionally refuses arrays, typedefs,
bitfields, aggregate initializers, indirect boolean calls and compound stores.
"""
import re


def parse_view(source):
    # XDK headers remain byte-identical in emitted C. Their compiler intrinsics
    # need not be understood by tree-sitter, so mask those header spans only.
    view = bytearray(source)
    offset = 0
    active = True
    for line in source.splitlines(keepends=True):
        marker = re.match(rb'#line \d+ "([^"]+)"', line)
        if marker:
            name = re.sub(rb'\\+', b'/', marker[1].lower())
            active = b'microsoft xbox 360 sdk/' not in name
        if not active or marker:
            view[offset:offset + len(line)] = re.sub(rb'[^\r\n]', b' ', line)
        offset += len(line)
    return bytes(view)


def lower(source, parser, pointer_boundaries=()):
    view = parse_view(source)
    positions = set()
    def builtin(match):
        if match[0] == b'_Bool':
            positions.add(match.start())
            return b'bool '
        return match[0]
    view = re.sub(rb'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|\b_Bool\b', builtin, view, flags=re.S)
    tree = parser.parse(view)
    scopes, functions, fields, bool_aggregates = {}, {}, {}, set()
    edits, wraps = [], set()
    stats = dict(types=0, initializers=0, stores=0, returns=0, casts=0, arguments=0)
    scope_types = {'translation_unit', 'compound_statement', 'function_definition', 'for_statement'}
    def text(node):
        return source[node.start_byte:node.end_byte] if node else b''
    def children(node):
        return node.named_children if node else []
    def walk(node):
        yield node
        for child in children(node):
            yield from walk(child)
    def scope(node):
        while node and node.type not in scope_types:
            node = node.parent
        return node
    def declarators(node):
        return node.children_by_field_name('declarator')
    def base(node):
        typ = node.child_by_field_name('type')
        return 'bool' if typ and typ.start_byte in positions else text(typ).decode(errors='replace')
    def shape(node, typ):
        depth = 0
        function = None
        while node and node.type not in ('identifier', 'field_identifier', 'type_identifier'):
            if node.type in ('array_declarator', 'abstract_array_declarator') and typ == 'bool':
                raise ValueError('Boolean arrays require element/aggregate conversion auditing')
            if node.type in ('pointer_declarator', 'abstract_pointer_declarator'):
                depth += 1
            if node.type == 'function_declarator':
                function = node
            nested = node.child_by_field_name('declarator')
            if not nested and node.type == 'parenthesized_declarator' and len(node.named_children) == 1:
                nested = node.named_children[0]
            node = nested
        return text(node), (typ, depth), function
    def normalize(node, category):
        if not node:
            raise ValueError('Missing boolean conversion value')
        if node.type == 'initializer_list':
            values = [n for n in children(node) if n.type != 'comment']
            if len(values) != 1:
                raise ValueError('Non-scalar boolean initializer')
            node = values[0]
        wraps.add((node.start_byte, node.end_byte))
        stats[category] += 1
    def declare(node):
        if node.type not in ('declaration', 'function_definition', 'parameter_declaration', 'field_declaration', 'type_definition'):
            return
        typ = base(node)
        if typ == 'bool' and any(n.type == 'bitfield_clause' for n in children(node)):
            raise ValueError('Boolean bitfields are not audited')
        owner = scope(node.parent)
        if node.type == 'parameter_declaration':
            owner = node.parent
            while owner and owner.type not in ('function_definition', 'declaration'):
                owner = owner.parent
            if owner and owner.type == 'declaration':
                owner = None
        for decl in declarators(node):
            name, dtype, func = shape(decl, typ)
            if typ == 'bool' and node.type == 'type_definition' and not func:
                raise ValueError('Boolean typedef aliases are not audited')
            if func:
                params = []
                for param in children(func.child_by_field_name('parameters')):
                    if param.type == 'parameter_declaration':
                        ds = declarators(param)
                        params.append(shape(ds[0], base(param))[1] if ds else (base(param), 0))
                if dtype[1] and any(p[0] == 'bool' for p in params):
                    raise ValueError('Boolean function-pointer declarations require an indirect-call audit')
                if node.type == 'type_definition':
                    # Function pointers returning bool need no caller input
                    # conversion; every bool definition normalizes return.
                    continue
                contract = (dtype, params)
                relevant = typ == 'bool' or any(p[0] == 'bool' for p in params)
                previous = functions.get(name)
                previous_relevant = previous and (previous[0][0] == 'bool' or any(p[0] == 'bool' for p in previous[1]))
                if name in functions and functions[name] != contract and (relevant or previous_relevant):
                    raise ValueError('Conflicting function declaration: ' + name.decode())
                functions[name] = contract
            elif node.type == 'field_declaration':
                fields.setdefault(name, set()).add(dtype)
            elif owner:
                scopes.setdefault(owner.id, {}).setdefault(name, []).append((node.start_byte, dtype))
            if dtype == ('bool', 0) and not func and decl.type == 'init_declarator':
                normalize(decl.child_by_field_name('value'), 'initializers')
    nodes = list(walk(tree.root_node))
    for node in nodes:
        declare(node)
        if node.type in ('struct_specifier', 'union_specifier') and node.child_by_field_name('body'):
            if any(child.start_byte in positions for child in walk(node)):
                tag = text(node.child_by_field_name('name'))
                if tag:
                    bool_aggregates.add((b'struct ' if node.type == 'struct_specifier' else b'union ') + tag)
                if node.parent and node.parent.type == 'type_definition':
                    bool_aggregates.update(text(d) for d in declarators(node.parent))
        if node.start_byte in positions and node.type in ('primitive_type', 'type_identifier'):
            edits.append((node.start_byte, node.start_byte + 5, b'unsigned char'))
            stats['types'] += 1
    # Follow only explicit aggregate aliases/embedded fields; do not mistake
    # an unrelated same-named member for a known aggregate layout.
    changed = True
    while changed:
        changed = False
        for node in nodes:
            candidates = set()
            if node.type == 'type_definition' and base(node).encode() in bool_aggregates:
                candidates.update(text(d) for d in declarators(node))
            if node.type in ('struct_specifier', 'union_specifier') and node.child_by_field_name('body'):
                body = node.child_by_field_name('body')
                embedded = any(base(field).encode() in bool_aggregates for field in children(body) if field.type == 'field_declaration')
                if embedded:
                    tag = text(node.child_by_field_name('name'))
                    if tag:
                        candidates.add((b'struct ' if node.type == 'struct_specifier' else b'union ') + tag)
                    if node.parent and node.parent.type == 'type_definition':
                        candidates.update(text(d) for d in declarators(node.parent))
            if candidates - bool_aggregates:
                bool_aggregates.update(candidates)
                changed = True
    if {e[0] for e in edits} != positions:
        raise ValueError('Unresolved _Bool token/context in C AST')
    def expr_type(node):
        if not node:
            return None
        if node.type == 'parenthesized_expression':
            return expr_type(node.named_children[0])
        if node.type == 'identifier':
            owner = scope(node.parent)
            while owner:
                records = [r for r in scopes.get(owner.id, {}).get(text(node), []) if r[0] <= node.start_byte]
                if records:
                    return records[-1][1]
                owner = scope(owner.parent)
        if node.type == 'field_expression':
            kinds = fields.get(text(node.child_by_field_name('field')), set())
            if any(k[0] == 'bool' for k in kinds):
                if len(kinds) != 1:
                    raise ValueError('Ambiguous boolean field name: ' + text(node).decode())
                return next(iter(kinds))
        if node.type == 'pointer_expression':
            operand = expr_type(node.child_by_field_name('argument'))
            if operand:
                return (operand[0], operand[1] + (1 if text(node.child_by_field_name('operator')) == b'&' else -1))
        if node.type == 'subscript_expression':
            operand = expr_type(node.child_by_field_name('argument'))
            if operand and operand[1] > 0:
                return (operand[0], operand[1] - 1)
        if node.type == 'update_expression':
            return expr_type(node.child_by_field_name('argument'))
        if node.type == 'assignment_expression':
            return expr_type(node.child_by_field_name('left'))
        if node.type == 'conditional_expression':
            left = expr_type(node.child_by_field_name('consequence'))
            right = expr_type(node.child_by_field_name('alternative'))
            return left if left == right else None
        if node.type == 'binary_expression':
            left = expr_type(node.child_by_field_name('left'))
            right = expr_type(node.child_by_field_name('right'))
            operator = text(node.child_by_field_name('operator'))
            if left and left[0] == 'bool' and left[1] > 0 and operator in (b'+', b'-'):
                return ('ptrdiff_t', 0) if right == left and operator == b'-' else left
            if right and right[0] == 'bool' and right[1] > 0 and operator == b'+':
                return right
        if node.type == 'call_expression':
            called = functions.get(text(node.child_by_field_name('function')))
            return called[0] if called else None
        return None
    for node in nodes:
        if node.type == 'ERROR' and any(n.start_byte in positions for n in walk(node)):
            raise ValueError('Boolean declaration/expression overlaps an unparsed AST region')
        if node.type == 'assignment_expression':
            dtype = expr_type(node.child_by_field_name('left'))
            rhs_type = expr_type(node.child_by_field_name('right'))
            if rhs_type and rhs_type[0] == 'bool' and rhs_type[1] > 0 and dtype != rhs_type:
                raise ValueError('Boolean pointer escapes through incompatible assignment')
            if dtype == ('bool', 0):
                operator = node.child_by_field_name('operator')
                left = node.child_by_field_name('left')
                if text(operator) == b'|=' and left.type == 'identifier':
                    edits.extend([(operator.start_byte, operator.end_byte, b'= !!(' + text(left) + b' |'),
                                  (node.end_byte, node.end_byte, b')')])
                    stats['stores'] += 1
                elif text(operator) != b'=':
                    raise ValueError('Compound boolean stores require single-evaluation auditing')
                else:
                    normalize(node.child_by_field_name('right'), 'stores')
        if node.type == 'update_expression' and expr_type(node.child_by_field_name('argument')) == ('bool', 0):
            raise ValueError('Boolean increment/decrement is not audited')
        if node.type == 'cast_expression':
            typ = node.child_by_field_name('type')
            operand_type = expr_type(node.child_by_field_name('value'))
            if operand_type and operand_type[0] == 'bool' and operand_type[1] > 0:
                raise ValueError('Boolean pointer casts require alias auditing')
            if base(typ) == 'bool':
                if typ.child_by_field_name('declarator'):
                    raise ValueError('Boolean pointer casts require alias auditing')
                normalize(node.child_by_field_name('value'), 'casts')
        if node.type == 'return_statement':
            function = node.parent
            while function and function.type != 'function_definition':
                function = function.parent
            if function and base(function) == 'bool':
                if any(shape(d, 'bool')[1][1] for d in declarators(function)):
                    raise ValueError('Returning boolean storage pointers requires alias auditing')
                normalize(node.named_children[0], 'returns')
        if node.type == 'call_expression':
            params = functions.get(text(node.child_by_field_name('function')))
            args = children(node.child_by_field_name('arguments'))
            if params:
                for argument, dtype in zip(args, params[1]):
                    if dtype == ('bool', 0):
                        normalize(argument, 'arguments')
            # A boolean storage address may escape only through a declared
            # boolean pointer parameter, so unknown/void* writers cannot bypass
            # canonicalization unnoticed.
            for index, argument in enumerate(args):
                dtype = expr_type(argument)
                if dtype and dtype[0] == 'bool' and dtype[1] > 0:
                    if not params or index >= len(params[1]) or params[1][index] != dtype:
                        boundary = (text(node.child_by_field_name('function')).decode(), index)
                        if boundary not in pointer_boundaries:
                            raise ValueError('Boolean pointer escapes through an untyped/incompatible call')
        if node.type == 'initializer_list':
            parent = node.parent
            if parent and parent.type == 'init_declarator':
                decl = parent.parent
                if decl and base(decl) not in ('bool', 'int', 'unsigned char'):
                    # Struct/array aggregates with boolean fields need typed
                    # positional/designator conversion. Never guess a field.
                    typ = base(decl).encode()
                    if typ in bool_aggregates:
                        raise ValueError('Boolean aggregate initializer requires typed field conversion')
        if node.type == 'compound_literal_expression':
            typ = node.child_by_field_name('type')
            if base(typ) == 'bool' or base(typ).encode() in bool_aggregates:
                raise ValueError('Boolean compound-literal aggregate requires typed field conversion')
        if node.type == 'init_declarator':
            initializer = node.child_by_field_name('value')
            dtype = expr_type(initializer)
            if dtype and dtype[0] == 'bool' and dtype[1] > 0:
                declared = shape(node, base(node.parent))[1]
                if declared != dtype:
                    raise ValueError('Boolean pointer escapes through incompatible initializer')
    for start, end in wraps:
        edits.extend([(start, start, b'!!('), (end, end, b')')])
    for start, end, value in sorted(edits, reverse=True):
        source = source[:start] + value + source[end:]
    return source, stats
