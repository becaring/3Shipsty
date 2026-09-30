"""Compile all pinned savestate serialization and request methods for Xenon."""

import argparse, hashlib, json, re, struct, subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/savestates"
OUT = ROOT / "scratch/savestates-xdk"
BASE = "soh/soh/Enhancements/"


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError("Savestate source drift: " + name)
        texts[name] = text
    text = texts[BASE + "savestates.cpp"]
    text = once(text, '#include "savestates.h"', '#include "soh/Enhancements/savestates.h"')
    text = text.replace('#include "../../src/overlays/', '#include "src/overlays/')
    text = once(
        text,
        "#include <libultraship/libultraship.h>",
        "#include <ship/Context.h>\n#include <ship/window/Window.h>\n#include"
        " <ship/window/gui/Gui.h>\n#include <ship/window/gui/GameOverlay.h>",
    )
    text = text.replace(
        "std::unique_lock<std::mutex>", "Shipyard::Async::unique_lock<Shipyard::Async::mutex>"
    )
    assert text.count("switch (request.type)") == 2
    text = text.replace("switch (request.type)", "switch (request.type.GetValue())")
    assert text.count("static_cast<int>(request.type)") == 2
    text = text.replace("static_cast<int>(request.type)", "request.type.GetValue()")
    text = text.replace("[[unlikely]] ", "")
    for old, new, count in [
        (
            "!this->states.contains(request.slot)",
            "this->states.find(request.slot) == this->states.end()",
            1,
        ),
        (
            "this->states.contains(request.slot)",
            "this->states.find(request.slot) != this->states.end()",
            1,
        ),
        ("states.contains(request.slot)", "states.find(request.slot) != states.end()", 1),
    ]:
        assert text.count(old) == count, old
        text = text.replace(old, new)
    outputs = {
        BASE + "savestates.cpp": text,
        BASE + "savestates_extern.inc": texts[BASE + "savestates_extern.inc"],
    }
    for name, text in outputs.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated={n: hashlib.sha256(t.encode()).hexdigest() for n, t in outputs.items()},
                native_runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = json.loads((ROOT / "scratch/application-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(OUT / "generated/soh")]
    source = OUT / "generated" / BASE / "savestates.cpp"
    obj = folder / "savestates.obj"
    command = flags + [str(source), "/Fo" + str(obj)]
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    stable(obj.with_suffix(".log"), r.stdout + r.stderr)
    stable(
        folder / "build.json",
        json.dumps(
            [
                dict(
                    source=source.relative_to(ROOT).as_posix(),
                    command=command,
                    exit=r.returncode,
                    production=True,
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    object_sha256=(
                        hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None
                    ),
                )
            ],
            indent=2,
        )
        + "\n",
    )
    print("savestates.cpp", r.returncode)
    if r.returncode:
        print("\n".join(l for l in r.stdout.splitlines() if "error " in l)[:4500])
        raise SystemExit(1)
    assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
