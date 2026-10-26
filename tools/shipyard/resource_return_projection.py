"""Avoid retaining an already retained result at forwarding resource-load boundaries.
The cache lookup and final loader keep the owner; mutation fences remain unchanged.
"""


def resource_manager(text):
    for signature, names in (
        ("ResourceManager::LoadResource(const ResourceIdentifier& identifier", ("cachedResource", "resource")),
        ("ResourceManager::LoadResourceProcess(const ResourceIdentifier& identifier", ("cachedResource",)),
    ):
        begin = text.index(signature)
        end = text.index("\n}", begin)
        body = text[begin:end]
        for name in names:
            old = "return Shipyard_OverlapKeepResource(" + name + ");"
            if body.count(old) != 1:
                raise ValueError("Resource lifetime return changed: " + signature + ": " + name)
            body = body.replace(old, "return " + name + ";")
        text = text[:begin] + body + text[end:]
    return text


def resource_helpers(text):
    old = "return (char*)ResourceMgr_GetResourceDataByNameHandlingMQ(filePath);"
    if text.count(old) != 1:
        raise ValueError("Texture resolution fallback changed")
    return text.replace(old, "// The first lookup already selected and retained this resource.\n    return (char*)res->GetRawPointer();")
