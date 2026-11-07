"""Generate AudioCollection and its sequence enum."""

import argparse, hashlib, json, re, struct, subprocess
from dependency_sources import ROOT
from prepare_archives import stable
from prepare_configuration import once
from cpp_ast import PARSER, walk

OWN = ROOT / "platform/shipyard/audio-collection"
OUT = ROOT / "scratch/audio-collection-xdk"
BASE = "soh/soh/Enhancements/audio/"


def prepare():
    lock = json.loads((OWN / "sources.lock.json").read_text())
    texts = {}
    for name, digest in lock["sources"].items():
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        if hashlib.sha256(text.encode()).hexdigest() != digest:
            raise ValueError("Audio collection input drift: " + name)
        texts[name] = text
    header = texts[BASE + "AudioCollection.h"]
    enum = next(
        n.text.decode()
        for n in walk(PARSER.parse(header.encode()).root_node)
        if n.type == "enum_specifier" and n.child_by_field_name("name").text == b"SeqType"
    )
    header = once(header, enum + ";", '#include "soh/Enhancements/audio/sequence_type.h"')
    header = once(header, "bool shufflePoolInitialized = false;", "bool shufflePoolInitialized;")
    text = texts[BASE + "AudioCollection.cpp"]
    text = once(
        text,
        "AudioCollection::AudioCollection() {",
        "AudioCollection::AudioCollection() : shufflePoolInitialized(false) {",
    )
    text = once(
        text,
        "    sequenceMap = {",
        """    // Preserve the exact source table and std::map first-key insertion semantics.
    struct RowInfo { uint16_t sequenceId; const char* label; const char* sfxKey;
        SeqType category; bool canBeReplaced; bool canBeUsedAsReplacement; };
    struct Row { uint16_t first; RowInfo second; };
    static const Row rows[] = {""",
    )
    text = once(
        text,
        "    // clang-format on\n}",
        """    // clang-format on
    for (size_t i=0; i<sizeof(rows)/sizeof(rows[0]); ++i) {
        const RowInfo& row=rows[i].second;
        SequenceInfo info={row.sequenceId,row.label,row.sfxKey,row.category,row.canBeReplaced,row.canBeUsedAsReplacement};
        sequenceMap.insert(std::make_pair(rows[i].first,info));
    }
}""",
    )
    text = once(
        text,
        "#include <libultraship/classes.h>",
        "#include <ship/Context.h>\n#include <ship/window/Window.h>\n#include"
        " <ship/window/gui/Gui.h>",
    )
    text = once(
        text,
        "#include <soh/OTRGlobals.h>",
        "// No OTRGlobals declarations are used in this translation unit.",
    )
    text = once(text, "#include <filesystem>", '#include "filesystem/filesystem.h"')
    text = once(text, "std::filesystem::path", "xbox_compat::filesystem::path")
    text = once(
        text,
        "sequenceMap.emplace(seqNum, info);",
        "sequenceMap.insert(std::make_pair(seqNum, info));",
    )
    text = once(
        text,
        "!sequenceMap.contains(replacementSeq)",
        "sequenceMap.find(replacementSeq) == sequenceMap.end()",
    )
    text = once(
        text,
        "return sequenceMap.contains(seqId);",
        "return sequenceMap.find(seqId) != sequenceMap.end();",
    )
    text = once(
        text,
        "for (auto& [seqId, seqInfo] : sequenceMap) {",
        "for (auto it=sequenceMap.begin(); it!=sequenceMap.end(); ++it) {\n        SequenceInfo&"
        " seqInfo=it->second;",
    )
    text = once(
        text,
        """Notification::Emit({ .message = "Currently playing: " + std::string(sequenceName),
                             .remainingTime = (float)CVarGetInteger(CVAR_AUDIO("SeqNameOverlayDuration"), 5) });""",
        """Notification::Options notification;
        notification.message = "Currently playing: " + std::string(sequenceName);
        notification.remainingTime = (float)CVarGetInteger(CVAR_AUDIO("SeqNameOverlayDuration"), 5);
        Notification::Emit(notification);""",
    )
    generated = {
        BASE + "AudioCollection.h": header,
        BASE + "AudioCollection.cpp": text,
        BASE + "sequence_type.h": "#pragma once\n" + enum + ";\n",
    }
    for name, text in generated.items():
        stable(OUT / "generated" / name, text)
    stable(
        OUT / "manifest.json",
        json.dumps(
            dict(
                upstream_commit=lock["upstream_commit"],
                sources=lock["sources"],
                generated={n: hashlib.sha256(t.encode()).hexdigest() for n, t in generated.items()},
                sequence_rows=len(
                    re.findall(
                        r"^\s*SEQUENCE_MAP_ENTRY\(", texts[BASE + "AudioCollection.cpp"], re.M
                    )
                ),
                runtime_executed=False,
            ),
            indent=2,
        )
        + "\n",
    )


def build():
    prepare()
    folder = OUT / "xdk"
    folder.mkdir(parents=True, exist_ok=True)
    flags = json.loads((ROOT / "scratch/soh-menus-xdk/xdk/build.json").read_text())[0]["command"][
        :-2
    ]
    flags[1:1] = ["/I" + str(OUT / "generated/soh")]
    probe = folder / "declarations.cpp"
    stable(
        probe,
        '#include "soh/Enhancements/audio/sequence_type.h"\n#include'
        ' "soh/Enhancements/audio/AudioCollection.h"\nextern "C" const unsigned long'
        " AudioCollectionABI[]={sizeof(AudioCollection),sizeof(SequenceInfo),SEQ_BGM_CUSTOM};\n",
    )
    rows = []
    for source in [OUT / "generated" / BASE / "AudioCollection.cpp", probe]:
        obj = folder / (source.stem + ".obj")
        command = flags + [str(source), "/Fo" + str(obj)]
        r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        stable(obj.with_suffix(".log"), r.stdout + r.stderr)
        rows.append(
            dict(
                source=source.relative_to(ROOT).as_posix(),
                command=command,
                exit=r.returncode,
                production=source != probe,
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                object_sha256=(
                    hashlib.sha256(obj.read_bytes()).hexdigest() if not r.returncode else None
                ),
            )
        )
        print(source.name, r.returncode)
        if r.returncode:
            print("\n".join(l for l in r.stdout.splitlines() if "error " in l)[:4000])
        else:
            assert struct.unpack_from("<H", obj.read_bytes())[0] == 0x1F2
    stable(folder / "build.json", json.dumps(rows, indent=2) + "\n")
    if any(r["exit"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    a = p.parse_args()
    build() if a.build else prepare()
