"""Generic current ImGui syntax projection, donor hashes in provenance.json."""

import re
from cpp_ast import PARSER, walk, tx, field


def default_members(text):
    permitted = {
        "ImGuiDemoWindowData",
        "ExampleTreeNode",
        "ExampleDualListBox",
        "ExampleAppPropertyEditor",
        "ExampleAppDocuments",
        "ExampleAssetsBrowser",
        "ImTriangulatorNodeSpan",
        "ImTriangulator",
        "ImGuiTextIndex",
        "ImGuiTypingSelectState",
        "ImGuiMetricsConfig",
        "MergeGroup",
    }
    data = text.encode()
    parsed = data.replace(b"IMGUI_API", b"         ")
    edits = []
    for node in walk(PARSER.parse(parsed).root_node):
        if node.type != "struct_specifier":
            continue
        name, body = tx(field(node, "name")), field(node, "body")
        if not body or name not in permitted:
            continue
        defaults = [c for c in body.named_children if c.type == "field_declaration" and field(c, "default_value")]
        if not defaults:
            continue
        init = []
        for member in defaults:
            decl, value = field(member, "declarator"), field(member, "default_value")
            names = [n for n in walk(decl) if n.type == "field_identifier"]
            if len(names) != 1:
                raise RuntimeError("Ambiguous initialized member")
            member_name = tx(names[0])
            val = tx(value)
            if decl.type == "array_declarator":
                if val != '""':
                    raise RuntimeError("Unsupported member array initializer")
                val = ""  # Original empty string zero-initializes every char.
            init.append(member_name + "(" + val + ")")
            edits.append((decl.end_byte, value.end_byte, b""))
        constructors = []
        for child in body.named_children:
            if child.type != "function_definition":
                continue
            decl = field(child, "declarator")
            if decl and tx(field(decl, "declarator")) == name:
                constructors.append(child)
        if not constructors:
            edits.append(
                (
                    body.start_byte + 1,
                    body.start_byte + 1,
                    ("\n    " + name + "() : " + ", ".join(init) + " {}\n").encode(),
                )
            )
        else:
            for constructor in constructors:
                if any(c.type == "field_initializer_list" for c in constructor.named_children):
                    raise RuntimeError("Existing explicit initializers need review: " + name)
                block = field(constructor, "body")
                edits.append((block.start_byte, block.start_byte, (" : " + ", ".join(init) + " ").encode()))
    for begin, end, replacement in sorted(edits, reverse=True):
        data = data[:begin] + replacement + data[end:]
    return data.decode()


def callback_lambdas(text):
    # XDK lambdas cannot convert to function pointers. These actual no-capture
    # callbacks become local static member functions, retaining their bodies.
    data = text.encode()
    edits, insertions = [], {}
    for node in walk(PARSER.parse(data.replace(b"IMGUI_API", b"         ")).root_node):
        if node.type != "lambda_expression":
            continue
        capture = next(c for c in node.named_children if c.type == "lambda_capture_specifier")
        if tx(capture) != "[]":
            raise RuntimeError("Capturing ImGui callback needs separate lowering")
        declarator, block = field(node, "declarator"), field(node, "body")
        parameters = field(declarator, "parameters")
        body_text = data[block.start_byte : block.end_byte].decode()
        if "GetClipboardTextFn" in body_text or "return ((const char**)data)[n]" in body_text:
            result = "const char*"
        elif "SetClipboardTextFn" in body_text or "array[n] = selected;" in body_text:
            result = "void"
        elif (
            "return (ImGuiID)idx;" in body_text
            or "return items[idx];" in body_text
            or "return (*p_items)[idx];" in body_text
            or "return self->Items[idx].ID;" in body_text
        ):
            result = "ImGuiID"
        else:
            raise RuntimeError("Unaudited callback return type: " + body_text)
        owner = node.parent
        while owner and owner.type != "function_definition":
            owner = owner.parent
        if owner is None:
            raise RuntimeError("Callback outside a function")
        scope = field(owner, "body")
        name = "ShipyardCallback" + str(node.start_byte)
        definition = "\nstruct " + name + " { static " + result + " Invoke" + tx(parameters) + " " + body_text + " };\n"
        insertions.setdefault(scope.start_byte + 1, []).append(definition)
        edits.append((node.start_byte, node.end_byte, (name + "::Invoke").encode()))
    edits.extend((pos, pos, "".join(values).encode()) for pos, values in insertions.items())
    for start, end, value in sorted(edits, reverse=True):
        data = data[:start] + value + data[end:]
    return data.decode()


def enum_definitions_before_use(text):
    # MSVC16 supports enum underlying types, but not opaque declarations.
    # Move the actual definition intact; do not replace enum types with ints.
    for forward in list(re.finditer(r"^enum (\w+)\s*:\s*(\w+)\s*;", text, re.M)):
        name, base = forward.groups()
        pattern = r"^enum " + name + r"\s*:\s*" + base + r"\s*\{.*?^\};"
        matches = list(re.finditer(pattern, text, re.M | re.S))
        if len(matches) != 1:
            raise RuntimeError("Ambiguous enum definition: " + name)
        definition = matches[0].group()
        text = text[: matches[0].start()] + "\n" * definition.count("\n") + text[matches[0].end() :]
        text = re.sub(r"^enum " + name + r"\s*:\s*" + base + r"\s*;", lambda _: definition, text, count=1, flags=re.M)
    return text


def lower_ranges(source, begin="ShipyardImGuiBegin", end="ShipyardImGuiEnd"):
    for iteration in range(64):
        edits = []
        for node in walk(PARSER.parse(source).root_node):
            if node.type != "for_range_loop":
                continue
            if any(n.type == "for_range_loop" for n in list(walk(node))[1:]):
                continue
            right = node.child_by_field_name("right")
            body = node.child_by_field_name("body")
            decl = node.child_by_field_name("declarator")
            if right.type == "initializer_list":
                raise ValueError("Unaudited initializer-list range")
            opening = next(n for n in node.children if n.type == "(")
            declaration = source[opening.end_byte : decl.end_byte].decode().strip()
            if "[" in declaration:
                raise ValueError("Structured-binding range must be lowered explicitly first")
            suffix = str(node.start_byte)
            rng = "_configRange" + suffix
            it = "_configIt" + suffix
            stop = "_configEnd" + suffix
            inner = body.text.decode()[1:-1] if body.type == "compound_statement" else body.text.decode()
            replacement = (
                "{ auto&& "
                + rng
                + " = "
                + right.text.decode()
                + "; auto "
                + it
                + " = "
                + begin
                + "("
                + rng
                + "); auto "
                + stop
                + " = "
                + end
                + "("
                + rng
                + "); for (; "
                + it
                + " != "
                + stop
                + "; ++"
                + it
                + ") { "
                + declaration
                + " = *"
                + it
                + "; "
                + inner
                + " } }"
            )
            edits.append((node.start_byte, node.end_byte, replacement.encode()))
        if not edits:
            return source
        for start, stop, value in sorted(edits, reverse=True):
            source = source[:start] + value + source[stop:]
    raise ValueError("Unexpected range nesting")
