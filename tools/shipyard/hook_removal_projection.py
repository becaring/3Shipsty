"""Remove keyed hooks by their unique map key while retaining queue timing."""

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Hook removal source drift")
    return text.replace(old, new)


def project(text):
    for suffix, key in [("ID", "id"), ("Ptr", "ptr")]:
        group = "RegisteredGameHooks<H>::functionsFor" + suffix + "[" + key + "]"
        old = """            for (auto it = GROUP.begin();
                 it != GROUP.end();) {
                if (it->first == *hookIdIt) {
                    it = GROUP.erase(it);
                    RegisteredGameHooks<H>::hookData.erase(*hookIdIt);
                    remove = true;
                    break;
                } else {
                    ++it;
                }
            }""".replace("GROUP", group)
        new = """            if (GROUP.erase(*hookIdIt) != 0) {
                RegisteredGameHooks<H>::hookData.erase(*hookIdIt);
                remove = true;
            }""".replace("GROUP", group)
        text = once(text, old, new)
        group = "idGroup" if suffix == "ID" else "ptrGroup"
        old = """                for (auto it = GROUP.second.begin(); it != GROUP.second.end();) {
                    if (it->first == hookId) {
                        it = GROUP.second.erase(it);
                        RegisteredGameHooks<H>::hookData.erase(hookId);
                    } else {
                        ++it;
                    }
                }""".replace("GROUP", group)
        new = """                if (GROUP.second.erase(hookId) != 0) {
                    RegisteredGameHooks<H>::hookData.erase(hookId);
                }""".replace("GROUP", group)
        text = once(text, old, new)
    return text
