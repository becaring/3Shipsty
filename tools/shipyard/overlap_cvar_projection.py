"""Own renderer CVar keys and values for one immutable replay batch."""

from prepare_configuration import once

MAP = "std::unordered_map<Shipyard::ConsoleVariables::NameKey, std::shared_ptr<CVar>, Shipyard::ConsoleVariables::NameHash>"
METHODS = r"""
namespace {
__declspec(thread) const ConsoleVariable* overlapSnapshotOwner = nullptr;
__declspec(thread) const ConsoleVariable::Snapshot* overlapSnapshot = nullptr;
}
const ConsoleVariable::Snapshot& ConsoleVariable::ReadVariables() const {
    return overlapSnapshotOwner == this && overlapSnapshot ? *overlapSnapshot : mVariables;
}
void ConsoleVariable::UseSnapshot(const Snapshot* snapshot) const {
    overlapSnapshotOwner = snapshot ? this : nullptr;
    overlapSnapshot = snapshot;
}
void ConsoleVariable::CaptureSnapshot(Snapshot& snapshot) const {
    // Keep all names, including mod CVars. Reuse storage only after replay retires.
    for (Snapshot::iterator cursor = snapshot.begin(); cursor != snapshot.end();) {
        Snapshot::const_iterator live = mVariables.find(cursor->first);
        if (live == mVariables.end() || !live->second) cursor = snapshot.erase(cursor);
        else ++cursor;
    }
    for (Snapshot::const_iterator cursor = mVariables.begin(); cursor != mVariables.end(); ++cursor) {
        if (!cursor->second) continue;
        const CVar& original = *cursor->second;
        std::shared_ptr<CVar>& copy = snapshot[cursor->first];
        // Get() may have handed ownership to a caller beyond the previous replay.
        if (!copy || copy.use_count() != 1) copy = std::make_shared<CVar>();
        if (copy->Type == ConsoleVariableType::String) {
            if (original.Type == ConsoleVariableType::String &&
                (copy->String == original.String || (copy->String && original.String &&
                 strcmp(copy->String, original.String) == 0))) continue;
            free(copy->String);
            copy->String = nullptr;
        }
        copy->Type = original.Type;
        switch (original.Type.GetValue()) {
            case ConsoleVariableType::Integer: copy->Integer = original.Integer; break;
            case ConsoleVariableType::Float: copy->Float = original.Float; break;
            case ConsoleVariableType::String:
                copy->String = original.String ? strdup(original.String) : nullptr;
                break;
            case ConsoleVariableType::Color: copy->Color = original.Color; break;
            case ConsoleVariableType::Color24: copy->Color24 = original.Color24; break;
        }
    }
}
"""


def header(text):
    text = once(
        text,
        "    ConsoleVariable();",
        "    typedef " + MAP + " Snapshot;\n"
        "    void CaptureSnapshot(Snapshot& snapshot) const;\n"
        "    void UseSnapshot(const Snapshot* snapshot) const;\n    ConsoleVariable();",
    )
    return once(
        text,
        "    " + MAP + " mVariables;",
        "    const Snapshot& ReadVariables() const;\n    Snapshot mVariables;",
    )


def source(text):
    text = once(text, "namespace Ship {", "namespace Ship {\n" + METHODS)
    lookup = "mVariables.find(Shipyard::ConsoleVariables::NameKey(name, Shipyard::ConsoleVariables::NameKey::Borrow))"
    if text.count(lookup) != 6:
        raise ValueError("CVar reader projection drift")
    # Limit replacement to the six leading readers, before the first setter.
    readers, setters = text.split("void ConsoleVariable::SetInteger", 1)
    readers = readers.replace(
        "    auto it = " + lookup,
        "    const Snapshot& variables = ReadVariables();\n    auto it = "
        + lookup.replace("mVariables", "variables"),
    )
    readers = readers.replace(
        "    auto found = " + lookup,
        "    const Snapshot& variables = ReadVariables();\n    auto found = "
        + lookup.replace("mVariables", "variables"),
    )
    readers = readers.replace("!= mVariables.end()", "!= variables.end()")
    # Snapshot capture itself iterates the live map while game and audio are idle.
    readers = readers.replace("cursor != variables.end()", "cursor != mVariables.end()")
    return readers + "void ConsoleVariable::SetInteger" + setters
