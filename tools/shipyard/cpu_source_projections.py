"""Write the reviewed CPU source projections without changing the pinned inputs.
Build records name and hash both the shared input and the compiled projection.
"""

import hashlib
from pathlib import Path


def materialize_headers(root):
    from audio_cpu_projection import profile_header

    original = root / "platform/shipyard/application/thread_profile.h"
    directory = root / "scratch/cpu-source-xdk/generated/include"
    output = directory / "application/thread_profile.h"
    data = original.read_bytes()
    encoded = profile_header(data.decode("utf-8-sig").replace("\r\n", "\n")).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file() or output.read_bytes() != encoded:
        output.write_bytes(encoded)
    return directory.relative_to(root).as_posix(), {
        "source": original.relative_to(root).as_posix(),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "output": output.relative_to(root).as_posix(),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def materialize(name, root, platform):
    if name == "platform/shipyard/xenos/services.cpp":
        from services_cpu_projection import project
    else:
        return name, None
    original = platform / name[len("shipyard/"):] if name.startswith("shipyard/") else root / name
    data = original.read_bytes()
    projected = project(data.decode("utf-8-sig").replace("\r\n", "\n"))
    output = root / "scratch/cpu-source-xdk/generated" / name.replace("/", "__")
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = projected.encode("utf-8")
    if not output.is_file() or output.read_bytes() != encoded:
        output.write_bytes(encoded)
    return output.relative_to(root).as_posix(), {
        "source": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "include_directory": original.parent.as_posix(),
    }
