"""Explicit lowering of the three audited delegating-constructor families."""

MAPTYPE = "std::unordered_map<CONTROLLERBUTTONS_T, std::string>"


def lower(relative, text, ast):
    if not relative.endswith(
        ("/ControllerDefaultMappings.cpp", "/libultraship/controller/controldeck/ControlDeck.cpp")
    ):
        return text
    data = text.encode()
    functions = []
    name = "ControlDeck" if relative.endswith("/ControlDeck.cpp") else "ControllerDefaultMappings"
    for node in ast["walk"](ast["PARSER"].parse(data).root_node):
        if node.type != "function_definition":
            continue
        decl = node.child_by_field_name("declarator")
        if decl.child_by_field_name("declarator").text.decode() == name + "::" + name:
            functions.append((len(decl.child_by_field_name("parameters").named_children), node))
    funcs = dict(functions)
    if name == "ControllerDefaultMappings":
        if set(funcs) != {0, 6}:
            raise ValueError("DefaultMappings ctor signatures changed")
        primary = funcs[6]
        parameters = primary.child_by_field_name("declarator").child_by_field_name("parameters").named_children
        declarations = []
        for p in parameters:
            typ = p.child_by_field_name("type").text.decode()
            identifier = p.child_by_field_name("declarator").text.decode()
            declarations.append(typ + " " + identifier + ";")
        body = primary.child_by_field_name("body").text.decode()[1:-1]
        replacement = name + "::" + name + "() {\n" + "\n".join(declarations) + body + "\n}"
        node = funcs[0]
        return ast["apply"](data, [(node.start_byte, node.end_byte, replacement.encode())]).decode()
    if set(funcs) != {0, 1, 3}:
        raise ValueError("ControlDeck ctor signatures changed")
    body = funcs[3].child_by_field_name("body").text.decode()[1:-1]
    initializer = next(n for n in funcs[1].named_children if n.type == "field_initializer_list")
    args = next(n for n in ast["walk"](initializer) if n.type == "argument_list").named_children
    if len(args) != 3:
        raise ValueError("ControlDeck delegate args changed")
    names = args[2].text.decode()
    declarations = "static " + MAPTYPE + " ShipyardDefaultButtonNames() { return " + names + "; }\n"
    edits = []
    for count in (0, 1):
        params = "std::vector<CONTROLLERBUTTONS_T> additionalBitmasks" if count else ""
        additional = "additionalBitmasks" if count else "std::vector<CONTROLLERBUTTONS_T>()"
        replacement = (
            "ControlDeck::ControlDeck("
            + params
            + ")\n: Ship::ControlDeck("
            + additional
            + ", std::make_shared<LUS::ControllerDefaultMappings>(), ShipyardDefaultButtonNames()), mPads(nullptr) {\n"
        )
        if not count:
            replacement += "std::vector<CONTROLLERBUTTONS_T> additionalBitmasks;\n"
        replacement += MAPTYPE + " buttonNames=ShipyardDefaultButtonNames();\n" + body + "\n}"
        node = funcs[count]
        edits.append((node.start_byte, node.end_byte, replacement.encode()))
    text = ast["apply"](data, edits).decode()
    if text.count("namespace LUS {") != 1:
        raise ValueError("ControlDeck namespace changed")
    return text.replace("namespace LUS {", "namespace LUS {\n" + declarations)
