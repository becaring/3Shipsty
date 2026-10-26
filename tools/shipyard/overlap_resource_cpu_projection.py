"""Retain each frequently reused resource once per reader packet.
A bounded pointer cache only suppresses duplicates; collisions keep additional owners.
"""

from pathlib import Path


def runtime(text):
    old = "typedef std::vector<std::shared_ptr<Ship::IResource> > ResourceOwners;"
    if text.count(old) != 1:
        raise ValueError("Overlap resource owner declaration changed")
    return text.replace(old, '''class ResourceOwners : public std::vector<std::shared_ptr<Ship::IResource> > {
    const Ship::IResource* recent[256];
  public:
    ResourceOwners() { memset(recent, 0, sizeof(recent)); }
    void clear() {
        memset(recent, 0, sizeof(recent));
        std::vector<std::shared_ptr<Ship::IResource> >::clear();
    }
    void push_back(const std::shared_ptr<Ship::IResource>& resource) {
        const Ship::IResource* pointer = resource.get();
        const uintptr_t address = reinterpret_cast<uintptr_t>(pointer);
        const size_t slot = ((address >> 4) ^ (address >> 12)) & 255;
        if (recent[slot] == pointer) return;
        std::vector<std::shared_ptr<Ship::IResource> >::push_back(resource);
        recent[slot] = pointer;
    }
};
class ResourceReaderScope {
    ResourceOwners& owners;
  public:
    explicit ResourceReaderScope(ResourceOwners& storage) : owners(storage) {}
    ~ResourceReaderScope() { owners.clear(); }
};''')


def application(text):
    include = '#include "application/overlap_runtime.inc"'
    if text.count(include) != 1:
        raise ValueError("Overlap runtime include changed")
    source = Path(__file__).resolve().parents[2] / "platform/shipyard/application/overlap_runtime.inc"
    body = runtime(source.read_text(encoding="utf-8"))
    if body.count("    ResourceOwners retainedResources;") != 1 or body.count("    GameWorker worker;") != 1:
        raise ValueError("Render resource owner storage changed")
    body = body.replace("    GameWorker worker;", "    GameWorker worker;\n    ResourceOwners renderResources;")
    body = body.replace("    ResourceOwners retainedResources;",
                        "    ResourceReaderScope resourceRead(owner.renderResources);\n"
                        "    ResourceOwners& retainedResources = owner.renderResources;")
    return text.replace(include, body)
