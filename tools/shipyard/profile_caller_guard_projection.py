"""Avoid out-of-line phase bookkeeping when Begin did not select a sample."""

import re


MARKER = "// MODERN PROFILE CALLER GUARDS"
_CALLS = (
    ("xboxPrepSample", "(?:AdvancePipelinePreparation|EnterPipelineTextureImport|"
     "ExitPipelineTextureImport|EndPipelinePreparation)", 6),
    ("xboxTextureHashSample", "(?:AdvanceTextureHash|EndTextureHash)", 6),
)


def remove_instrumentation(source: str) -> str:
    if MARKER not in source:
        return source
    for sample, methods, _ in _CALLS:
        pattern = re.compile(
            rf"^(?P<indent>[ \t]*)if \({sample}\.sampled\) \{{\n"
            rf"(?P=indent)    (?P<call>ModernFrameProfile::{methods}\("
            rf"\s*{sample}\b[^;]*;)\n(?P=indent)\}}",
            re.MULTILINE,
        )
        source = pattern.sub(
            lambda m: m["indent"] + m["call"].replace("\n    ", "\n"), source
        )
    return source.removeprefix(MARKER + "\n")


def transform(source: str) -> str:
    if MARKER in source:
        return source
    for sample, methods, expected in _CALLS:
        pattern = re.compile(
            rf"^(?P<indent>[ \t]*)(?P<call>ModernFrameProfile::{methods}\("
            rf"\s*{sample}\b[^;]*;)",
            re.MULTILINE,
        )

        def guard(match: re.Match) -> str:
            indent = match["indent"]
            call = match["call"].replace("\n", "\n    ")
            return f"{indent}if ({sample}.sampled) {{\n{indent}    {call}\n{indent}}}"

        source, count = pattern.subn(guard, source)
        if count != expected:
            raise RuntimeError(
                f"profile caller guards: expected {expected} {sample} calls, found {count}"
            )
    return MARKER + "\n" + source
